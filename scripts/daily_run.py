#!/usr/bin/env python3
"""Daily market scanner - checks for Turtle Trading signals.

Usage:
    python scripts/daily_run.py
    python scripts/daily_run.py --symbols SPY QQQ GLD
    python scripts/daily_run.py --from-db
"""

import asyncio
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import yfinance as yf

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.backtesting.data_loader import SMALL_ACCOUNT_ETF_UNIVERSE
from src.adapters.repositories.alert_repository import PostgresAlertRepository
from src.adapters.repositories.position_repository import PostgresOpenPositionRepository
from src.application.commands.log_alert import AlertLogger
from src.domain.models.enums import Direction, System
from src.domain.models.market import Bar
from src.domain.services.channels import calculate_all_channels
from src.domain.services.signal_detector import SignalDetector
from src.domain.services.volatility import calculate_n


# Use the validated 15-ETF small account universe
# This matches the backtest configuration exactly
# See: docs/research/small-account-turtle-findings.md
DEFAULT_UNIVERSE = SMALL_ACCOUNT_ETF_UNIVERSE


def fetch_bars(symbol: str, days: int = 70) -> list[Bar]:
    """Fetch historical bars from Yahoo Finance directly."""
    end = date.today()
    start = end - timedelta(days=int(days * 1.5) + 10)  # Buffer for weekends/holidays

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, end=end + timedelta(days=1), auto_adjust=True)

    if df is None or df.empty:
        return []

    bars = []
    for idx, row in df.iterrows():
        try:
            bar = Bar(
                symbol=symbol,
                date=idx.date() if hasattr(idx, "date") else idx,
                open=Decimal(str(round(row["Open"], 6))),
                high=Decimal(str(round(row["High"], 6))),
                low=Decimal(str(round(row["Low"], 6))),
                close=Decimal(str(round(row["Close"], 6))),
                volume=int(row["Volume"]) if row["Volume"] > 0 else 0,
            )
            bars.append(bar)
        except Exception:
            continue

    return bars[-days:] if len(bars) > days else bars


def fetch_current_price(symbol: str) -> Decimal | None:
    """Fetch current price from Yahoo Finance."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info

        price = (
            getattr(info, "last_price", None)
            or getattr(info, "previous_close", None)
            or getattr(info, "regular_market_price", None)
        )

        if price and price > 0:
            return Decimal(str(round(price, 6)))
    except Exception:
        pass
    return None


async def scan_symbol(symbol: str, detector: SignalDetector) -> dict:
    """Scan a single symbol for signals."""
    result = {
        "symbol": symbol,
        "price": None,
        "n_value": None,
        "dc20_upper": None,
        "dc20_lower": None,
        "dc55_upper": None,
        "dc55_lower": None,
        "signals": [],
        "error": None,
    }

    try:
        # Run synchronous Yahoo calls in executor
        loop = asyncio.get_event_loop()
        bars = await loop.run_in_executor(None, lambda: fetch_bars(symbol, 70))

        if len(bars) < 55:
            result["error"] = f"Insufficient data: {len(bars)} bars"
            return result

        # Get current price
        price = await loop.run_in_executor(None, lambda: fetch_current_price(symbol))
        if price is None:
            # Fall back to last close
            price = bars[-1].close if bars else None

        if price is None:
            result["error"] = "Could not get price"
            return result

        result["price"] = float(price)

        # Calculate N (ATR)
        n_result = calculate_n(bars[-20:], period=20)
        result["n_value"] = float(n_result.value)

        # Calculate Donchian channels
        channels = calculate_all_channels(bars)
        dc20 = channels.get("dc_20")
        dc55 = channels.get("dc_55")

        if dc20:
            result["dc20_upper"] = float(dc20.upper)
            result["dc20_lower"] = float(dc20.lower)
        if dc55:
            result["dc55_upper"] = float(dc55.upper)
            result["dc55_lower"] = float(dc55.lower)

        # Detect signals
        if dc20 and dc55:
            signals = detector.detect_all_signals(
                symbol=symbol,
                current_price=price,
                donchian_20=dc20,
                donchian_55=dc55,
            )
            result["signals"] = [
                {
                    "type": s.signal_type.value,
                    "system": s.system.value,
                    "direction": s.direction.value,
                    "price": float(s.price),
                    "channel": float(s.channel_value),
                }
                for s in signals
            ]
    except Exception as e:
        result["error"] = str(e)

    return result


async def main(symbols: list[str] | None = None):
    """Run the daily market scanner."""
    universe = symbols or DEFAULT_UNIVERSE

    print("=" * 60)
    print(f"TURTLE TRADING SIGNAL SCANNER - {date.today()}")
    print("=" * 60)
    print(f"\nScanning {len(universe)} markets...")
    print()

    # Initialize repositories and logger
    alert_repo = PostgresAlertRepository()
    position_repo = PostgresOpenPositionRepository()
    alert_logger = AlertLogger(alert_repo, position_repo)

    # Initialize signal detector
    detector = SignalDetector()

    # Scan all symbols
    results = []
    for symbol in universe:
        print(f"  Scanning {symbol}...", end=" ", flush=True)
        result = await scan_symbol(symbol, detector)
        results.append(result)

        if result["error"]:
            print(f"ERROR: {result['error']}")
        elif result["signals"]:
            print(f"SIGNAL DETECTED!")
            # Log each signal to database
            for sig in result["signals"]:
                try:
                    await alert_logger.log_signal(
                        symbol=symbol,
                        direction=Direction(sig["direction"]),
                        system=System(sig["system"]),
                        price=Decimal(str(sig["price"])),
                        details={
                            "signal_type": sig["type"],
                            "channel_value": sig["channel"],
                            "n_value": result["n_value"],
                        },
                    )
                except Exception as e:
                    print(f"    (alert log failed: {e})")
        else:
            print("no signal")

    # Summary
    print("\n" + "=" * 60)
    print("SCAN RESULTS")
    print("=" * 60)

    signals_found = [r for r in results if r["signals"]]
    errors = [r for r in results if r["error"]]

    if signals_found:
        print(f"\n*** {len(signals_found)} SIGNAL(S) FOUND ***\n")
        for r in signals_found:
            print(f"  {r['symbol']} @ ${r['price']:.2f}")
            for sig in r["signals"]:
                print(f"    -> {sig['system']} {sig['direction'].upper()} {sig['type']}")
                print(f"       Channel: ${sig['channel']:.2f}")
    else:
        print("\nNo signals detected today.")

    if errors:
        print(f"\n{len(errors)} error(s) occurred:")
        for r in errors:
            print(f"  {r['symbol']}: {r['error']}")

    # Print levels for reference
    print("\n" + "-" * 60)
    print("CHANNEL LEVELS (for manual verification)")
    print("-" * 60)
    print(f"{'Symbol':<8} {'Price':>10} {'N':>8} {'DC20 Hi':>10} {'DC20 Lo':>10} {'DC55 Hi':>10} {'DC55 Lo':>10}")
    print("-" * 60)

    for r in results:
        if not r["error"] and r["price"]:
            print(
                f"{r['symbol']:<8} "
                f"{r['price']:>10.2f} "
                f"{r['n_value']:>8.2f} "
                f"{r['dc20_upper']:>10.2f} "
                f"{r['dc20_lower']:>10.2f} "
                f"{r['dc55_upper']:>10.2f} "
                f"{r['dc55_lower']:>10.2f}"
            )

    print()
    return signals_found


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Turtle Trading Signal Scanner")
    parser.add_argument("--symbols", nargs="+", help="Symbols to scan")
    args = parser.parse_args()

    asyncio.run(main(args.symbols))

#!/usr/bin/env python3
"""Daily market scanner - checks for Turtle Trading signals with optional auto-execution.

Usage:
    python scripts/daily_run.py                          # Detection only (current behavior)
    python scripts/daily_run.py --symbols SPY QQQ GLD    # Scan specific symbols
    python scripts/daily_run.py --auto-execute --dry-run # Show what would execute
    python scripts/daily_run.py --auto-execute           # Execute entry orders
"""

import asyncio
import logging
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

import yfinance as yf
from dotenv import load_dotenv
from ib_insync import IB, Stock, MarketOrder, StopOrder

# Add src to path and load environment
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

from src.adapters.backtesting.data_loader import SMALL_ACCOUNT_ETF_UNIVERSE
from src.adapters.mappers.correlation_mapper import get_etf_correlation_group
from src.adapters.repositories.alert_repository import PostgresAlertRepository
from src.adapters.repositories.event_repository import PostgresEventRepository
from src.adapters.repositories.position_repository import PostgresOpenPositionRepository
from src.adapters.repositories.run_repository import PostgresRunRepository
from src.adapters.repositories.trade_repository import PostgresTradeRepository
from src.application.commands.log_alert import AlertLogger
from src.application.commands.log_event import (
    EventLogger,
    build_market_context,
    build_signal_context,
)
from src.application.commands.log_run import RunLogger
from src.domain.models.event import EventType, OutcomeType
from src.domain.models.enums import Direction, System
from src.domain.models.market import Bar, NValue
from src.domain.models.portfolio import Portfolio
from src.domain.models.position import Position, PyramidLevel
from src.domain.models.signal import Signal
from src.domain.rules import RISK_PER_TRADE
from src.domain.services.channels import calculate_all_channels
from src.domain.services.limit_checker import LimitChecker
from src.domain.services.s1_filter import S1Filter
from src.domain.services.signal_detector import SignalDetector
from src.domain.services.volatility import calculate_n

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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


# =============================================================================
# AUTO-EXECUTION FUNCTIONS
# =============================================================================


async def get_account_equity(ib: IB) -> Decimal:
    """Get account equity from IBKR."""
    account_values = await ib.accountSummaryAsync()
    for av in account_values:
        if av.tag == "NetLiquidation":
            return Decimal(str(av.value))
    raise RuntimeError("Could not get account equity")


def calculate_unit_size(equity: Decimal, n_value: Decimal) -> int:
    """Calculate unit size for stocks (point_value = 1).

    Rule 4: Unit = (Risk × Equity) / (N × PointValue)
    For stocks, point_value = 1, so Unit = (0.005 × Equity) / N
    """
    risk_amount = equity * RISK_PER_TRADE
    if n_value <= 0:
        return 0
    raw_size = risk_amount / n_value
    return int(raw_size.quantize(Decimal("1"), rounding=ROUND_DOWN))


async def execute_entry(
    ib: IB,
    symbol: str,
    direction: Direction,
    system: System,
    current_price: Decimal,
    n_value: Decimal,
    alert_logger: AlertLogger,
) -> dict:
    """Execute an entry order: buy shares, place stop.

    Args:
        ib: IBKR connection
        symbol: Stock symbol (e.g., 'QQQ')
        direction: LONG or SHORT
        system: S1 or S2
        current_price: Current market price
        n_value: Current N (ATR) value
        alert_logger: Alert logger for dashboard

    Returns:
        Dict with execution details
    """
    # Check for existing pending orders for this symbol (prevent duplicates)
    await ib.reqAllOpenOrdersAsync()
    await asyncio.sleep(0.5)
    for existing_trade in ib.trades():
        if existing_trade.contract.symbol == symbol:
            order_type = existing_trade.order.orderType
            status = existing_trade.orderStatus.status
            logger.warning(f"  {symbol}: SKIPPED - pending {order_type} order exists (status={status})")
            return {"success": False, "reason": f"Pending order exists: {order_type} {status}"}

    # Get account equity
    try:
        equity = await get_account_equity(ib)
    except Exception as e:
        return {"success": False, "reason": f"Could not get account equity: {e}"}

    # Calculate unit size (Rule 4)
    unit_size = calculate_unit_size(equity, n_value)

    if unit_size < 1:
        return {"success": False, "reason": f"Unit size too small: {unit_size}"}

    # Check margin before placing order
    notional_value = float(current_price) * unit_size
    try:
        account_values = {v.tag: float(v.value) for v in ib.accountValues() if v.currency == "USD"}
        buying_power = account_values.get("BuyingPower", 0)
        # Use 50% of buying power as safety buffer
        if notional_value > buying_power * 0.5:
            logger.warning(f"  {symbol}: SKIPPED - insufficient margin (need ${notional_value:,.0f}, have ${buying_power:,.0f} BP)")
            return {"success": False, "reason": f"Insufficient margin: ${notional_value:,.0f} > 50% of ${buying_power:,.0f}"}
    except Exception as e:
        logger.warning(f"  {symbol}: Could not check margin: {e}")
        # Continue anyway - IBKR will reject if truly insufficient

    # Create contract
    contract = Stock(symbol, "SMART", "USD")
    await ib.qualifyContractsAsync(contract)

    # Determine order action
    action = "BUY" if direction == Direction.LONG else "SELL"
    stop_action = "SELL" if direction == Direction.LONG else "BUY"

    # Calculate stop price (2N from current price - will be recalculated on fill)
    # Using current_price as estimate since we don't have fill price yet
    if direction == Direction.LONG:
        stop_price = float(current_price - (2 * n_value))
    else:
        stop_price = float(current_price + (2 * n_value))

    logger.info(f"  {symbol}: EXECUTING ENTRY - {action} {unit_size} shares at market")
    logger.info(f"  {symbol}: STOP will be @ ${stop_price:.2f} (2N from ${current_price:.2f})")

    # Use BRACKET ORDER to ensure stop is always placed with entry
    # This guarantees the stop activates when entry fills - no orphan entries!
    bracket = ib.bracketOrder(
        action=action,
        quantity=unit_size,
        limitPrice=0,  # Not used for market orders
        takeProfitPrice=0,  # No take profit
        stopLossPrice=stop_price,
    )

    # Modify parent to be market order (bracket defaults to limit)
    parent = bracket[0]
    parent.orderType = "MKT"
    parent.tif = "DAY"

    # Modify stop loss order
    stop_order = bracket[2]  # bracket = [parent, takeProfit, stopLoss]
    stop_order.tif = "GTC"
    stop_order.outsideRth = True

    # Place the bracket (parent + stop)
    for o in [parent, stop_order]:
        ib.placeOrder(contract, o)
        await asyncio.sleep(0.3)

    logger.info(f"  {symbol}: BRACKET ORDER placed (entry + stop linked)")

    # Wait for fill (30s timeout) - but stop is already attached!
    timeout = 30
    start = asyncio.get_event_loop().time()
    parent_trade = None
    for t in ib.trades():
        if t.order.orderId == parent.orderId:
            parent_trade = t
            break

    if parent_trade:
        while parent_trade.orderStatus.status not in ("Filled", "Cancelled", "Inactive", "PreSubmitted"):
            await asyncio.sleep(0.5)
            if asyncio.get_event_loop().time() - start > timeout:
                break

    # Check final status
    filled = False
    fill_price = current_price  # Default to current price if not filled yet
    filled_qty = unit_size

    if parent_trade and parent_trade.orderStatus.status == "Filled":
        fill_price = Decimal(str(parent_trade.orderStatus.avgFillPrice))
        filled_qty = int(parent_trade.orderStatus.filled)
        filled = True
        logger.info(f"  {symbol}: FILLED {filled_qty} shares @ ${fill_price:.2f}")
    elif parent_trade and parent_trade.orderStatus.status == "PreSubmitted":
        logger.info(f"  {symbol}: Order queued for market open (stop attached)")
    else:
        logger.warning(f"  {symbol}: Order status: {parent_trade.orderStatus.status if parent_trade else 'unknown'}")

    # Recalculate stop price based on fill (if filled)
    if filled:
        if direction == Direction.LONG:
            stop_price = float(fill_price - (2 * n_value))
        else:
            stop_price = float(fill_price + (2 * n_value))
    stop_price = Decimal(str(stop_price))

    # Log POSITION_OPENED to alerts database (only if filled)
    if filled:
        try:
            await alert_logger.log_position_opened(
                symbol=symbol,
                direction=direction,
                system=system,
                entry_price=fill_price,
                contracts=filled_qty,
                stop_price=stop_price,
                n_value=n_value,
            )
        except Exception as e:
            logger.error(f"  {symbol}: Failed to log alert: {e}")

    return {
        "success": True,
        "filled": filled,
        "queued": not filled,  # True if queued for tomorrow
        "filled_qty": filled_qty,
        "fill_price": float(fill_price),
        "stop_price": float(stop_price),
        "unit_size": unit_size,
    }


async def build_portfolio_from_ibkr(ib: IB) -> Portfolio:
    """Build portfolio from IBKR positions for limit checking."""
    positions_dict = {}

    for pos in ib.positions():
        if pos.position == 0:
            continue

        symbol = pos.contract.symbol
        quantity = int(pos.position)
        avg_cost = Decimal(str(pos.avgCost))

        direction = Direction.LONG if quantity > 0 else Direction.SHORT
        correlation_group = get_etf_correlation_group(symbol)

        # Create minimal position for limit checking
        pyramid = PyramidLevel(
            level=1,
            entry_price=avg_cost,
            contracts=abs(quantity),
            n_at_entry=Decimal("1"),  # Placeholder
        )

        n_value = NValue(
            value=Decimal("1"),
            calculated_at=datetime.now(),
            symbol=symbol,
        )

        position = Position(
            symbol=symbol,
            direction=direction,
            system=System.S1,  # Default
            correlation_group=correlation_group,
            pyramid_levels=(pyramid,),
            current_stop=Decimal("0"),  # Unknown
            initial_entry_price=avg_cost,
            initial_n=n_value,
        )
        positions_dict[symbol] = position

    return Portfolio(positions=positions_dict)


def check_entry_allowed(
    portfolio: Portfolio,
    symbol: str,
    limit_checker: LimitChecker,
) -> tuple[bool, str]:
    """Check if new entry is allowed by position limits."""
    correlation_group = get_etf_correlation_group(symbol)

    result = limit_checker.can_add_position(
        portfolio=portfolio,
        symbol=symbol,
        units_to_add=1,
        correlation_group=correlation_group,
    )

    return result.allowed, result.reason


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

        # Calculate Donchian channels (exclude current bar for breakout detection)
        channels = calculate_all_channels(bars, exclude_current=True)
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
                    "type": "breakout",
                    "system": s.system.value,
                    "direction": s.direction.value,
                    "price": float(s.breakout_price),
                    "channel": float(s.channel_value),
                }
                for s in signals
            ]
    except Exception as e:
        result["error"] = str(e)

    return result


async def main(
    symbols: list[str] | None = None,
    auto_execute: bool = False,
    dry_run: bool = False,
):
    """Run the daily market scanner with optional auto-execution.

    Args:
        symbols: Symbols to scan (default: SMALL_ACCOUNT_ETF_UNIVERSE)
        auto_execute: If True, execute orders for actionable signals
        dry_run: If True, show what would execute but don't place orders
    """
    universe = symbols or DEFAULT_UNIVERSE

    print("=" * 60)
    print(f"TURTLE TRADING SIGNAL SCANNER - {date.today()}")
    if auto_execute:
        print(">>> AUTO-EXECUTION ENABLED <<<")
    if dry_run:
        print(">>> DRY RUN MODE - No orders will be executed <<<")
    print("=" * 60)
    print(f"\nScanning {len(universe)} markets...")
    print()

    # Initialize repositories and loggers
    alert_repo = PostgresAlertRepository()
    position_repo = PostgresOpenPositionRepository()
    trade_repo = PostgresTradeRepository()
    run_repo = PostgresRunRepository()
    event_repo = PostgresEventRepository()
    alert_logger = AlertLogger(alert_repo, position_repo)
    run_logger = RunLogger(run_repo)
    event_logger = EventLogger(event_repo)

    # Start run and event logging
    run = run_logger.start_scanner_run(len(universe))
    event_logger.start_run("scanner")
    await event_logger.log_scanner_started(symbols=universe, dry_run=dry_run)

    # Initialize signal detector and S1 filter
    detector = SignalDetector()
    s1_filter = S1Filter(trade_repo)

    # Initialize limit checker
    limit_checker = LimitChecker()

    # Connect to IBKR if auto-executing
    ib = None
    portfolio = Portfolio()
    existing_symbols = set()

    if auto_execute:
        ib = IB()
        try:
            await ib.connectAsync("127.0.0.1", 7497, clientId=99)
            logger.info(f"Connected to IBKR: {ib.managedAccounts()}")

            # Build portfolio from current positions
            portfolio = await build_portfolio_from_ibkr(ib)
            existing_symbols = set(portfolio.positions.keys())
            logger.info(f"Loaded {len(portfolio.positions)} existing positions: {existing_symbols}")

        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            logger.error("Auto-execution disabled, running in detection-only mode")
            auto_execute = False
            ib = None

    # Scan all symbols
    results = []
    signals_to_execute = []

    for symbol in universe:
        print(f"  Scanning {symbol}...", end=" ", flush=True)
        result = await scan_symbol(symbol, detector)
        results.append(result)

        if result["error"]:
            print(f"ERROR: {result['error']}")
            continue

        if not result["signals"]:
            print("no signal")
            continue

        print("SIGNAL DETECTED!")

        # Process each signal
        for sig in result["signals"]:
            direction = Direction(sig["direction"])
            system = System(sig["system"])

            # Apply S1 filter for S1 signals (Rule 7)
            if system == System.S1:
                signal_obj = Signal(
                    symbol=symbol,
                    direction=direction,
                    system=system,
                    breakout_price=Decimal(str(sig["price"])),
                    channel_value=Decimal(str(sig["channel"])),
                )
                filter_result = await s1_filter.should_take_signal(signal_obj)

                if not filter_result.take_signal:
                    print(f"    {system.value} {direction.value.upper()} FILTERED: {filter_result.reason}")
                    continue

            # Check if we already have a position
            if symbol in existing_symbols:
                print(f"    {system.value} {direction.value.upper()} SKIPPED: Already have position in {symbol}")
                continue

            # Check position limits
            if auto_execute:
                allowed, reason = check_entry_allowed(portfolio, symbol, limit_checker)
                if not allowed:
                    print(f"    {system.value} {direction.value.upper()} LIMIT EXCEEDED: {reason}")
                    continue

            # Log signal to database (always, even if not executing)
            try:
                await alert_logger.log_signal(
                    symbol=symbol,
                    direction=direction,
                    system=system,
                    price=Decimal(str(sig["price"])),
                    details={
                        "signal_type": sig["type"],
                        "channel_value": sig["channel"],
                        "n_value": result["n_value"],
                    },
                )
            except Exception as e:
                print(f"    (alert log failed: {e})")

            print(f"    {system.value} {direction.value.upper()} -> ACTIONABLE")

            # Queue for execution if auto-execute enabled
            if auto_execute:
                signals_to_execute.append({
                    "symbol": symbol,
                    "direction": direction,
                    "system": system,
                    "price": Decimal(str(sig["price"])),
                    "n_value": Decimal(str(result["n_value"])),
                })

    # Execute queued signals
    executions = []
    if signals_to_execute and ib:
        print("\n" + "=" * 60)
        print("EXECUTING ENTRIES")
        print("=" * 60)

        for sig in signals_to_execute:
            if dry_run:
                print(f"  {sig['symbol']}: WOULD EXECUTE {sig['direction'].value.upper()} "
                      f"(N={sig['n_value']:.2f})")
                executions.append({"signal": sig, "result": {"success": False, "reason": "Dry run"}})
            else:
                exec_result = await execute_entry(
                    ib=ib,
                    symbol=sig["symbol"],
                    direction=sig["direction"],
                    system=sig["system"],
                    current_price=sig["price"],
                    n_value=sig["n_value"],
                    alert_logger=alert_logger,
                )
                executions.append({"signal": sig, "result": exec_result})

                if exec_result["success"]:
                    print(f"  {sig['symbol']}: SUCCESS - {exec_result['filled_qty']} shares "
                          f"@ ${exec_result['fill_price']:.2f}, stop @ ${exec_result['stop_price']:.2f}")
                else:
                    print(f"  {sig['symbol']}: FAILED - {exec_result['reason']}")

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

    # Execution summary
    if executions:
        successful = [e for e in executions if e["result"].get("success")]
        failed = [e for e in executions if not e["result"].get("success") and not dry_run]
        print(f"\nEXECUTION SUMMARY:")
        print(f"  Queued: {len(signals_to_execute)}")
        if dry_run:
            print(f"  Would execute: {len(signals_to_execute)} (dry run)")
        else:
            print(f"  Successful: {len(successful)}")
            print(f"  Failed: {len(failed)}")

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

    # Complete event logging
    signals_detected = sum(len(r.get("signals", [])) for r in results)
    errors_count = len(errors)
    await event_logger.log_scanner_completed(
        symbols_scanned=len(universe),
        signals_detected=signals_detected,
        signals_approved=len(signals_to_execute),
        positions_opened=len([e for e in executions if e["result"].get("success")]) if executions else 0,
        errors=errors_count,
        dry_run=dry_run,
    )

    # Complete run logging
    if errors_count > 0:
        await run_logger.complete_run(run)
    else:
        await run_logger.complete_run(run)

    # Disconnect from IBKR
    if ib and ib.isConnected():
        ib.disconnect()
        logger.info("Disconnected from IBKR")

    return signals_found


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Turtle Trading Signal Scanner")
    parser.add_argument("--symbols", nargs="+", help="Symbols to scan")
    parser.add_argument(
        "--auto-execute",
        action="store_true",
        help="Automatically execute orders for actionable signals",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would execute without placing orders (requires --auto-execute)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.symbols, auto_execute=args.auto_execute, dry_run=args.dry_run))

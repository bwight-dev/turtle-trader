#!/usr/bin/env python3
"""Run Turtle Trading backtest.

Usage:
    python scripts/backtest.py
    python scripts/backtest.py --start 2024-01-01 --end 2025-12-31
    python scripts/backtest.py --equity 100000
    python scripts/backtest.py --symbols SPY QQQ GLD
    python scripts/backtest.py --no-short
    python scripts/backtest.py --output results.json
"""

import argparse
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.backtesting import (
    ETF_UNIVERSE,
    BacktestConfig,
    BacktestEngine,
)


def main():
    parser = argparse.ArgumentParser(
        description="Run Turtle Trading backtest on historical data"
    )

    # Date range
    parser.add_argument(
        "--start",
        type=str,
        default="2024-01-01",
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2025-12-31",
        help="End date (YYYY-MM-DD)",
    )

    # Capital
    parser.add_argument(
        "--equity",
        type=float,
        default=50000,
        help="Starting equity (default: 50000)",
    )

    # Universe
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Specific symbols to trade (default: full ETF universe)",
    )

    # Strategy options
    parser.add_argument(
        "--no-s1",
        action="store_true",
        help="Disable S1 (20-day) system",
    )
    parser.add_argument(
        "--no-s2",
        action="store_true",
        help="Disable S2 (55-day) system",
    )
    parser.add_argument(
        "--no-short",
        action="store_true",
        help="Long-only mode (no short positions)",
    )
    parser.add_argument(
        "--no-pyramid",
        action="store_true",
        help="Disable pyramiding",
    )

    # Risk
    parser.add_argument(
        "--risk",
        type=float,
        default=0.005,
        help="Risk per unit as decimal (default: 0.005 = 0.5%%)",
    )
    parser.add_argument(
        "--max-risk",
        type=float,
        default=0.15,
        help="Max total risk cap as decimal (default: 0.15 = 15%%)",
    )

    # Output
    parser.add_argument(
        "--output",
        type=str,
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output",
    )

    args = parser.parse_args()

    # Build config
    config = BacktestConfig(
        start_date=date.fromisoformat(args.start),
        end_date=date.fromisoformat(args.end),
        initial_equity=Decimal(str(args.equity)),
        risk_per_unit=Decimal(str(args.risk)),
        max_total_risk=Decimal(str(args.max_risk)),
        use_s1=not args.no_s1,
        use_s2=not args.no_s2,
        allow_short=not args.no_short,
        use_pyramiding=not args.no_pyramid,
    )

    symbols = args.symbols or ETF_UNIVERSE

    # Print header
    if not args.quiet:
        print("\n" + "=" * 60)
        print("TURTLE TRADING BACKTEST")
        print("=" * 60)
        print(f"Period: {config.start_date} to {config.end_date}")
        print(f"Initial Equity: ${config.initial_equity:,.0f}")
        print(f"Risk per Unit: {config.risk_per_unit * 100:.1f}%")
        print(f"Max Total Risk: {config.max_total_risk * 100:.0f}%")
        print(f"Universe: {len(symbols)} symbols")
        print(f"Systems: {'S1 ' if config.use_s1 else ''}{'S2' if config.use_s2 else ''}")
        print(f"Direction: {'Long/Short' if config.allow_short else 'Long Only'}")
        print(f"Pyramiding: {'Yes' if config.use_pyramiding else 'No'}")
        print("=" * 60)

    # Run backtest
    engine = BacktestEngine(config=config, symbols=symbols)
    result = engine.run(show_progress=not args.quiet)

    # Print results
    if result.metrics:
        print(result.summary)

        # Additional diagnostics
        print("\nDIAGNOSTICS")
        print("-" * 40)
        print(f"Signals Generated: {result.signals_generated}")
        print(f"Signals Filtered (S1 rule): {result.signals_filtered}")
        print(f"Signals Skipped (size < 1): {result.signals_skipped_size}")
        print(f"Signals Skipped (limits): {result.signals_skipped_limits}")
        print(f"Pyramid Adds: {result.pyramid_triggers}")
        print(f"Stop Exits: {result.stop_exits}")
        print(f"Breakout Exits: {result.breakout_exits}")

        # Top trades
        if result.trades:
            print("\nTOP 5 WINNERS")
            print("-" * 40)
            winners = sorted(result.trades, key=lambda t: t.net_pnl, reverse=True)[:5]
            for t in winners:
                print(f"  {t.symbol:6} {t.direction:5} {t.system}: ${t.net_pnl:>10,.2f} ({t.entry_date} to {t.exit_date})")

            print("\nTOP 5 LOSERS")
            print("-" * 40)
            losers = sorted(result.trades, key=lambda t: t.net_pnl)[:5]
            for t in losers:
                print(f"  {t.symbol:6} {t.direction:5} {t.system}: ${t.net_pnl:>10,.2f} ({t.entry_date} to {t.exit_date})")

    # Save to file if requested
    if args.output:
        output_data = {
            "config": {
                "start_date": str(config.start_date),
                "end_date": str(config.end_date),
                "initial_equity": float(config.initial_equity),
                "risk_per_unit": float(config.risk_per_unit),
                "symbols": symbols,
            },
            "metrics": {
                "total_return_pct": float(result.metrics.total_return_pct),
                "annualized_return_pct": float(result.metrics.annualized_return_pct),
                "max_drawdown_pct": float(result.metrics.max_drawdown_pct),
                "sharpe_ratio": float(result.metrics.sharpe_ratio),
                "win_rate": float(result.metrics.win_rate),
                "profit_factor": float(result.metrics.profit_factor),
                "total_trades": result.metrics.total_trades,
            } if result.metrics else {},
            "trades": [
                {
                    "symbol": t.symbol,
                    "system": t.system,
                    "direction": t.direction,
                    "entry_date": str(t.entry_date),
                    "entry_price": float(t.entry_price),
                    "exit_date": str(t.exit_date),
                    "exit_price": float(t.exit_price),
                    "exit_reason": t.exit_reason,
                    "contracts": float(t.contracts),
                    "net_pnl": float(t.net_pnl),
                }
                for t in result.trades
            ],
            "equity_curve": [
                {
                    "date": str(p.date),
                    "equity": float(p.equity),
                    "drawdown_pct": float(p.drawdown_pct),
                }
                for p in result.equity_curve
            ],
        }

        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()

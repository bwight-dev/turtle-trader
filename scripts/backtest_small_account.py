#!/usr/bin/env python3
"""Compare Turtle Trading strategies for $50k small accounts.

Runs comparative backtests:
1. ORIGINAL: Full ETF universe (32 markets), no floor (death spiral expected)
2. SMALL_ACCOUNT: 7-market universe, 60% sizing floor (anti-death-spiral)
3. CONCENTRATED: Full universe, 60% floor (hybrid approach)

Based on research from:
- Tom Basso's "7 Market" study (Market Wizards)
- Jerry Parker's small account ETF advice
- Salem Abraham's approach (accept volatility)

Usage:
    python scripts/backtest_small_account.py
    python scripts/backtest_small_account.py --start 2020-01-01 --end 2025-12-31
    python scripts/backtest_small_account.py --equity 100000
"""

import argparse
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.backtesting import (
    ETF_UNIVERSE,
    SMALL_ACCOUNT_ETF_UNIVERSE,
    BacktestConfig,
    BacktestEngine,
    BacktestResult,
)


def print_comparison_header(equity: Decimal, start: date, end: date) -> None:
    """Print the comparison header."""
    print("\n" + "=" * 80)
    print("SMALL ACCOUNT TURTLE TRADING COMPARISON")
    print("=" * 80)
    print(f"Period: {start} to {end}")
    print(f"Initial Equity: ${equity:,.0f}")
    print("=" * 80)
    print()
    print("STRATEGIES:")
    print("  1. ORIGINAL    - Full ETF universe (31 markets), no sizing floor")
    print("  2. SMALL_ACCT  - 15-market universe, 60% sizing floor")
    print("  3. CONCENTRATED- Full universe, 60% sizing floor")
    print("=" * 80)


def print_result_summary(name: str, result: BacktestResult) -> None:
    """Print a concise summary of backtest results."""
    m = result.metrics
    if not m:
        print(f"\n{name}: NO TRADES EXECUTED")
        return

    print(f"\n{'─' * 80}")
    print(f"  {name}")
    print(f"{'─' * 80}")

    # Key metrics in columns
    print(f"  {'Final Equity:':<20} ${m.final_equity:>12,.0f}  │  "
          f"{'Total Return:':<16} {m.total_return_pct:>7.1f}%")
    print(f"  {'Max Drawdown:':<20} {m.max_drawdown_pct:>12.1f}%  │  "
          f"{'Sharpe Ratio:':<16} {m.sharpe_ratio:>7.2f}")
    print(f"  {'Calmar Ratio:':<20} {m.calmar_ratio:>12.2f}  │  "
          f"{'Win Rate:':<16} {m.win_rate:>7.1f}%")
    print(f"  {'Total Trades:':<20} {m.total_trades:>12}  │  "
          f"{'Profit Factor:':<16} {m.profit_factor:>7.2f}")

    # Diagnostics
    print()
    print(f"  Signals: {result.signals_generated} generated → "
          f"{result.signals_filtered} filtered (S1) → "
          f"{result.signals_skipped_size} skipped (size<1) → "
          f"{result.signals_skipped_limits} skipped (limits)")
    print(f"  Executions: {m.total_trades} trades, "
          f"{result.pyramid_triggers} pyramids, "
          f"{result.stop_exits} stops, "
          f"{result.breakout_exits} breakout exits")


def print_comparison_table(results: dict[str, BacktestResult]) -> None:
    """Print side-by-side comparison table."""
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)

    # Header
    print(f"\n{'Metric':<25} ", end="")
    for name in results:
        print(f"{name:>15}", end="  ")
    print()
    print("-" * 80)

    # Metrics to compare
    metrics = [
        ("Final Equity", lambda m: f"${m.final_equity:,.0f}" if m else "N/A"),
        ("Total Return %", lambda m: f"{m.total_return_pct:.1f}%" if m else "N/A"),
        ("Max Drawdown %", lambda m: f"{m.max_drawdown_pct:.1f}%" if m else "N/A"),
        ("Sharpe Ratio", lambda m: f"{m.sharpe_ratio:.2f}" if m else "N/A"),
        ("Calmar Ratio", lambda m: f"{m.calmar_ratio:.2f}" if m else "N/A"),
        ("Win Rate %", lambda m: f"{m.win_rate:.1f}%" if m else "N/A"),
        ("Profit Factor", lambda m: f"{m.profit_factor:.2f}" if m else "N/A"),
        ("Total Trades", lambda m: f"{m.total_trades}" if m else "N/A"),
        ("Avg Trade P&L", lambda m: f"${m.avg_trade_pnl:,.0f}" if m else "N/A"),
    ]

    for metric_name, getter in metrics:
        print(f"{metric_name:<25} ", end="")
        for result in results.values():
            value = getter(result.metrics)
            print(f"{value:>15}", end="  ")
        print()

    print("-" * 80)

    # Signals comparison
    print(f"\n{'Signal Flow':<25} ", end="")
    for name in results:
        print(f"{name:>15}", end="  ")
    print()
    print("-" * 80)

    signal_metrics = [
        ("Generated", lambda r: r.signals_generated),
        ("Filtered (S1)", lambda r: r.signals_filtered),
        ("Skipped (size<1)", lambda r: r.signals_skipped_size),
        ("Skipped (limits)", lambda r: r.signals_skipped_limits),
        ("Executed", lambda r: r.metrics.total_trades if r.metrics else 0),
    ]

    for metric_name, getter in signal_metrics:
        print(f"{metric_name:<25} ", end="")
        for result in results.values():
            value = getter(result)
            print(f"{value:>15}", end="  ")
        print()


def print_verdict(results: dict[str, BacktestResult]) -> None:
    """Print analysis and recommendation."""
    print("\n" + "=" * 80)
    print("ANALYSIS & RECOMMENDATION")
    print("=" * 80)

    original = results.get("ORIGINAL")
    small_acct = results.get("SMALL_ACCT")
    concentrated = results.get("CONCENTRATED")

    # Check for death spiral (original)
    if original and original.metrics:
        skip_rate = (original.signals_skipped_size /
                     max(original.signals_generated, 1) * 100)
        if skip_rate > 80:
            print(f"\n⚠️  DEATH SPIRAL DETECTED in ORIGINAL:")
            print(f"   {skip_rate:.0f}% of signals skipped due to insufficient size")
            print(f"   This confirms the capital requirements problem.")

    # Compare small account to concentrated
    if small_acct and small_acct.metrics and concentrated and concentrated.metrics:
        sa_return = small_acct.metrics.total_return_pct
        conc_return = concentrated.metrics.total_return_pct
        sa_dd = small_acct.metrics.max_drawdown_pct
        conc_dd = concentrated.metrics.max_drawdown_pct
        sa_sharpe = small_acct.metrics.sharpe_ratio
        conc_sharpe = concentrated.metrics.sharpe_ratio

        print("\n📊 COMPARISON: SMALL_ACCT vs CONCENTRATED")

        if sa_sharpe > conc_sharpe:
            print(f"   ✓ SMALL_ACCT has better risk-adjusted returns (Sharpe: {sa_sharpe:.2f} vs {conc_sharpe:.2f})")
        else:
            print(f"   ✓ CONCENTRATED has better risk-adjusted returns (Sharpe: {conc_sharpe:.2f} vs {sa_sharpe:.2f})")

        if sa_dd < conc_dd:
            print(f"   ✓ SMALL_ACCT has lower drawdown ({sa_dd:.1f}% vs {conc_dd:.1f}%)")
        else:
            print(f"   ✓ CONCENTRATED has lower drawdown ({conc_dd:.1f}% vs {sa_dd:.1f}%)")

    # Recommendation
    print("\n🎯 RECOMMENDATION:")

    best_strategy = None
    best_calmar = Decimal("-999")

    for name, result in results.items():
        if result.metrics and result.metrics.calmar_ratio > best_calmar:
            best_calmar = result.metrics.calmar_ratio
            best_strategy = name

    if best_strategy:
        best_result = results[best_strategy]
        print(f"   Use {best_strategy} strategy")
        print(f"   - Calmar Ratio: {best_result.metrics.calmar_ratio:.2f}")
        print(f"   - Expected drawdown: {best_result.metrics.max_drawdown_pct:.1f}%")
        print(f"   - Win rate: {best_result.metrics.win_rate:.1f}%")

        if best_strategy == "SMALL_ACCT":
            print("\n   15-market universe provides good diversification")
            print("   while remaining manageable for a $50k account.")
        elif best_strategy == "CONCENTRATED":
            print("\n   The 60% sizing floor prevents death spiral while")
            print("   maintaining broader diversification.")

    print("\n" + "=" * 80)


def run_comparison(
    start_date: date,
    end_date: date,
    initial_equity: Decimal,
    show_progress: bool = True,
) -> dict[str, BacktestResult]:
    """Run all three backtest configurations."""

    results = {}

    # 1. ORIGINAL: Full universe, no floor
    print("\n[1/3] Running ORIGINAL (full universe, no floor)...")
    config_original = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_equity=initial_equity,
        risk_per_unit=Decimal("0.005"),  # 0.5% per Parker
        max_total_risk=Decimal("0.15"),
        min_notional_floor=None,  # No floor = death spiral risk
    )
    engine = BacktestEngine(config=config_original, symbols=ETF_UNIVERSE)
    results["ORIGINAL"] = engine.run(show_progress=show_progress)

    # 2. SMALL_ACCT: 15-market universe, 60% floor
    print("\n[2/3] Running SMALL_ACCT (15 markets, 60% floor)...")
    config_small = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_equity=initial_equity,
        risk_per_unit=Decimal("0.005"),
        max_total_risk=Decimal("0.15"),
        min_notional_floor=Decimal("0.60"),  # 60% floor
        max_units_correlated=4,  # Tighter for small portfolio
        max_units_total=10,  # Max ~10 units
    )
    engine = BacktestEngine(config=config_small, symbols=SMALL_ACCOUNT_ETF_UNIVERSE)
    results["SMALL_ACCT"] = engine.run(show_progress=show_progress)

    # 3. CONCENTRATED: Full universe, 60% floor
    print("\n[3/3] Running CONCENTRATED (full universe, 60% floor)...")
    config_conc = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_equity=initial_equity,
        risk_per_unit=Decimal("0.005"),
        max_total_risk=Decimal("0.15"),
        min_notional_floor=Decimal("0.60"),  # 60% floor
    )
    engine = BacktestEngine(config=config_conc, symbols=ETF_UNIVERSE)
    results["CONCENTRATED"] = engine.run(show_progress=show_progress)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Compare Turtle Trading strategies for small accounts"
    )

    parser.add_argument(
        "--start",
        type=str,
        default="2020-01-01",
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2025-12-31",
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--equity",
        type=float,
        default=50000,
        help="Starting equity (default: 50000)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal progress output",
    )

    args = parser.parse_args()

    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)
    initial_equity = Decimal(str(args.equity))

    # Print header
    print_comparison_header(initial_equity, start_date, end_date)

    # Run all backtests
    results = run_comparison(
        start_date=start_date,
        end_date=end_date,
        initial_equity=initial_equity,
        show_progress=not args.quiet,
    )

    # Print individual results
    for name, result in results.items():
        print_result_summary(name, result)

    # Print comparison table
    print_comparison_table(results)

    # Print verdict
    print_verdict(results)


if __name__ == "__main__":
    main()

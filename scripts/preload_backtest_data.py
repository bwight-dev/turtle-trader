#!/usr/bin/env python3
"""Preload historical data for backtesting.

This script fetches historical OHLCV data from Yahoo Finance
and stores it in a local SQLite cache for fast backtesting.

Usage:
    python scripts/preload_backtest_data.py
    python scripts/preload_backtest_data.py --start 2024-01-01 --end 2025-12-31
    python scripts/preload_backtest_data.py --symbols SPY QQQ GLD
    python scripts/preload_backtest_data.py --stats
    python scripts/preload_backtest_data.py --clear
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.backtesting.data_loader import (
    ETF_UNIVERSE,
    HistoricalDataLoader,
)


def main():
    parser = argparse.ArgumentParser(
        description="Preload historical data for backtesting"
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Start date (YYYY-MM-DD). Default: 2 years ago",
    )
    parser.add_argument(
        "--end",
        type=str,
        help="End date (YYYY-MM-DD). Default: today",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Specific symbols to load (default: full ETF universe)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show cache statistics and exit",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the cache and exit",
    )
    parser.add_argument(
        "--clear-symbol",
        type=str,
        help="Clear cache for a specific symbol",
    )
    parser.add_argument(
        "--cache-path",
        type=str,
        default="data/backtest_cache.db",
        help="Path to cache file",
    )

    args = parser.parse_args()

    loader = HistoricalDataLoader(cache_path=args.cache_path)

    # Handle stats
    if args.stats:
        stats = loader.get_cache_stats()
        print("\n" + "=" * 50)
        print("BACKTEST DATA CACHE STATISTICS")
        print("=" * 50)
        print(f"Cache file: {args.cache_path}")
        print(f"Symbols cached: {stats['symbols']}")
        print(f"Total bars: {stats['total_bars']:,}")
        print(f"Date range: {stats['earliest_date']} to {stats['latest_date']}")
        print("\nBy Symbol:")
        print("-" * 50)
        for symbol, info in sorted(stats["by_symbol"].items()):
            print(f"  {symbol:6} {info['bars']:5} bars  ({info['start']} to {info['end']})")
        return

    # Handle clear
    if args.clear:
        confirm = input("Clear ALL cached data? (yes/no): ")
        if confirm.lower() == "yes":
            loader.clear_cache()
            print("Cache cleared.")
        else:
            print("Cancelled.")
        return

    if args.clear_symbol:
        loader.clear_cache(args.clear_symbol)
        print(f"Cache cleared for {args.clear_symbol}")
        return

    # Parse dates
    end_date = date.fromisoformat(args.end) if args.end else date.today()
    start_date = (
        date.fromisoformat(args.start)
        if args.start
        else end_date - timedelta(days=730)
    )

    symbols = args.symbols or ETF_UNIVERSE

    print("\n" + "=" * 50)
    print("PRELOADING BACKTEST DATA")
    print("=" * 50)
    print(f"Symbols: {len(symbols)}")
    print(f"Date range: {start_date} to {end_date}")
    print(f"Cache: {args.cache_path}")
    print("=" * 50 + "\n")

    # Preload
    results = loader.preload_universe(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        show_progress=True,
    )

    # Summary
    success = sum(1 for v in results.values() if v > 0)
    failed = sum(1 for v in results.values() if v == 0)
    total_bars = sum(results.values())

    print("\n" + "=" * 50)
    print("PRELOAD COMPLETE")
    print("=" * 50)
    print(f"Successful: {success}/{len(symbols)}")
    print(f"Failed: {failed}")
    print(f"Total bars loaded: {total_bars:,}")

    if failed > 0:
        print("\nFailed symbols:")
        for symbol, count in results.items():
            if count == 0:
                print(f"  - {symbol}")


if __name__ == "__main__":
    main()

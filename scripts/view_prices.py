#!/usr/bin/env python3
"""
View Latest Prices - Simple Script

Shows the most recent price for all tracked symbols.
Organized by ETFs and Stocks.

Usage:
    ./venv/bin/python3 scripts/view_prices.py
"""

import sys
import os

# Add parent directory to path so we can import from src/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher import get_latest_prices
from config import WATCHLIST_ETFS, WATCHLIST_STOCKS

def main():
    # Get latest prices for all symbols
    all_symbols = WATCHLIST_ETFS + WATCHLIST_STOCKS
    prices = get_latest_prices(all_symbols)

    if not prices:
        print("No price data found. Run update_data.py first.")
        return

    # Get the date (should be same for all symbols)
    sample_date = next(iter(prices.values()))['date']

    print()
    print("=" * 50)
    print(f"LATEST PRICES - {sample_date}")
    print("=" * 50)

    # Show ETFs
    print("\n📊 ETFs:")
    print("-" * 50)
    for symbol in WATCHLIST_ETFS:
        if symbol in prices:
            price = prices[symbol]['close']
            print(f"  {symbol:6}  ${price:8.2f}")
        else:
            print(f"  {symbol:6}  No data")

    # Show Stocks
    print("\n📈 Stocks:")
    print("-" * 50)
    for symbol in WATCHLIST_STOCKS:
        if symbol in prices:
            price = prices[symbol]['close']
            print(f"  {symbol:6}  ${price:8.2f}")
        else:
            print(f"  {symbol:6}  No data")

    print()
    print("=" * 50)
    print(f"Total symbols: {len(prices)}/{len(all_symbols)}")
    print("=" * 50)
    print()

if __name__ == "__main__":
    main()

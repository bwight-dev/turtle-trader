#!/usr/bin/env python3
"""
Update Price Data - Simple Script

Downloads latest price data for all tracked symbols from Yahoo Finance.
Saves data to data/prices.db

Usage:
    ./venv/bin/python3 scripts/update_data.py
"""

import sys
import os

# Add parent directory to path so we can import from src/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher import update_all_symbols

def main():
    print()
    print("Starting price data update...")
    print()

    # Run the update
    result = update_all_symbols()

    # Show final summary
    if result['failed']:
        print()
        print("⚠️  Some symbols failed to update:")
        for symbol in result['failed']:
            print(f"  - {symbol}")

    print()

if __name__ == "__main__":
    main()

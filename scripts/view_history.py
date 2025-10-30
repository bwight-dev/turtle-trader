#!/usr/bin/env python3
"""
View Price History - Simple Script

Shows detailed price history for a specific symbol.

Usage:
    ./venv/bin/python3 scripts/view_history.py SPY         # Shows last 5 days
    ./venv/bin/python3 scripts/view_history.py SPY 10      # Shows last 10 days
    ./venv/bin/python3 scripts/view_history.py AAPL 20     # Shows last 20 days
"""

import sys
import os
import sqlite3
import pandas as pd

# Add parent directory to path so we can import from src/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_PRICES, ALL_SYMBOLS

def main():
    # Parse command line arguments
    if len(sys.argv) < 2:
        print()
        print("Usage: ./venv/bin/python3 scripts/view_history.py SYMBOL [DAYS]")
        print()
        print("Examples:")
        print("  ./venv/bin/python3 scripts/view_history.py SPY")
        print("  ./venv/bin/python3 scripts/view_history.py SPY 10")
        print()
        print(f"Available symbols: {', '.join(ALL_SYMBOLS)}")
        print()
        return

    symbol = sys.argv[1].upper()
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    # Validate symbol
    if symbol not in ALL_SYMBOLS:
        print(f"\n❌ Error: {symbol} is not in your watchlist.")
        print(f"Available symbols: {', '.join(ALL_SYMBOLS)}\n")
        return

    try:
        # Connect to database
        conn = sqlite3.connect(DB_PRICES)

        # Query price history
        query = f"""
        SELECT date, open, high, low, close, volume
        FROM {symbol}
        ORDER BY date DESC
        LIMIT {days}
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            print(f"\n❌ No data found for {symbol}.")
            print("Run: ./venv/bin/python3 scripts/update_data.py\n")
            return

        # Reverse so oldest is first
        df = df.iloc[::-1].reset_index(drop=True)

        # Display results
        print()
        print("=" * 80)
        print(f"{symbol} - Last {len(df)} Days")
        print("=" * 80)
        print()

        # Format the dataframe for nice display
        df['open'] = df['open'].apply(lambda x: f"${x:8.2f}")
        df['high'] = df['high'].apply(lambda x: f"${x:8.2f}")
        df['low'] = df['low'].apply(lambda x: f"${x:8.2f}")
        df['close'] = df['close'].apply(lambda x: f"${x:8.2f}")
        df['volume'] = df['volume'].apply(lambda x: f"{x:,}")

        # Rename columns for display
        df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']

        print(df.to_string(index=False))
        print()
        print("=" * 80)
        print()

    except sqlite3.OperationalError:
        print(f"\n❌ Table {symbol} does not exist in database.")
        print("Run: ./venv/bin/python3 scripts/update_data.py\n")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}\n")

if __name__ == "__main__":
    main()

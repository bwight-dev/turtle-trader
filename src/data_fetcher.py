"""
Data Fetcher Module - Turtle Trading System

This module handles downloading historical price data from Yahoo Finance
and storing it in a SQLite database for later analysis.

Functions:
    - fetch_historical_data: Download OHLCV data from Yahoo Finance
    - save_to_database: Store price data in SQLite
    - get_latest_prices: Retrieve most recent prices from database
    - update_all_symbols: Update all symbols in watchlist
"""

import yfinance as yf
import pandas as pd
import sqlite3
import time
import os
from datetime import datetime
from typing import Optional, Dict, List, Tuple

# Import configuration settings
from config import ALL_SYMBOLS, DB_PRICES

# ==================================================================
# CONFIGURATION - Modify these values if needed
# ==================================================================

# Number of retry attempts for failed downloads
MAX_RETRIES = 3

# Delay between retries (seconds)
RETRY_DELAY = 2

# Default period for historical data
# Options: '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max'
DEFAULT_PERIOD = '6mo'


# ==================================================================
# FUNCTION: fetch_historical_data
# ==================================================================

def fetch_historical_data(symbol: str, period: str = DEFAULT_PERIOD) -> Optional[pd.DataFrame]:
    """
    Download historical price data from Yahoo Finance.

    Args:
        symbol: Stock or ETF ticker symbol (e.g., 'SPY', 'AAPL')
        period: Time period to download. Options:
                '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max'
                Default is '6mo' (6 months)

    Returns:
        pandas DataFrame with columns: Date, Open, High, Low, Close, Volume
        Returns None if download fails after all retries

    Example:
        >>> df = fetch_historical_data('SPY', '1mo')
        >>> print(df.head())
    """

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Download data using yfinance
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)

            # Check if we got valid data
            if df.empty:
                print(f"  Warning: No data returned for {symbol}")
                return None

            # Reset index to make Date a column instead of index
            df = df.reset_index()

            # Rename columns to match our standard format
            # yfinance uses 'Date' for the date column
            df = df.rename(columns={
                'Date': 'Date',
                'Open': 'Open',
                'High': 'High',
                'Low': 'Low',
                'Close': 'Close',
                'Volume': 'Volume'
            })

            # Keep only the columns we need (drop Dividends, Stock Splits, etc.)
            df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]

            # Convert Date to string format (YYYY-MM-DD) for SQLite storage
            df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')

            # Remove any rows with null values
            df = df.dropna()

            return df

        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"  Attempt {attempt}/{MAX_RETRIES} failed for {symbol}: {str(e)}")
                print(f"  Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  ERROR: Failed to fetch {symbol} after {MAX_RETRIES} attempts: {str(e)}")
                return None

    return None


# ==================================================================
# FUNCTION: save_to_database
# ==================================================================

def save_to_database(symbol: str, dataframe: pd.DataFrame, db_path: str = DB_PRICES) -> bool:
    """
    Save price data to SQLite database.

    Creates a separate table for each symbol. If the table exists,
    it updates existing records and inserts new ones (upsert behavior).

    Args:
        symbol: Stock/ETF ticker symbol (used as table name)
        dataframe: pandas DataFrame with columns: Date, Open, High, Low, Close, Volume
        db_path: Path to SQLite database file (default from config.DB_PRICES)

    Returns:
        True if save was successful, False otherwise

    Table Schema:
        CREATE TABLE {symbol} (
            date TEXT PRIMARY KEY,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER
        )
    """

    try:
        # Ensure the data directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            print(f"  Created directory: {db_dir}")

        # Connect to SQLite database (creates file if doesn't exist)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create table for this symbol if it doesn't exist
        # Using symbol as table name (e.g., 'SPY', 'AAPL')
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {symbol} (
            date TEXT PRIMARY KEY,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER
        )
        """
        cursor.execute(create_table_sql)

        # Insert or update data using REPLACE INTO
        # REPLACE = DELETE + INSERT (updates if date exists, inserts if new)
        for _, row in dataframe.iterrows():
            cursor.execute(
                f"""
                REPLACE INTO {symbol} (date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row['Date'],
                    float(row['Open']),
                    float(row['High']),
                    float(row['Low']),
                    float(row['Close']),
                    int(row['Volume'])
                )
            )

        # Commit changes and close connection
        conn.commit()
        conn.close()

        return True

    except Exception as e:
        print(f"  ERROR: Failed to save {symbol} to database: {str(e)}")
        return False


# ==================================================================
# FUNCTION: get_latest_prices
# ==================================================================

def get_latest_prices(symbols_list: List[str], db_path: str = DB_PRICES) -> Dict[str, Dict[str, any]]:
    """
    Retrieve the most recent price data for multiple symbols from database.

    Args:
        symbols_list: List of ticker symbols (e.g., ['SPY', 'AAPL', 'MSFT'])
        db_path: Path to SQLite database file (default from config.DB_PRICES)

    Returns:
        Dictionary mapping symbol to its latest price and date:
        {
            'SPY': {'close': 685.88, 'date': '2025-10-28'},
            'AAPL': {'close': 234.52, 'date': '2025-10-28'},
            ...
        }
        Missing symbols are excluded from the result.

    Example:
        >>> prices = get_latest_prices(['SPY', 'AAPL'])
        >>> print(f"SPY: ${prices['SPY']['close']:.2f}")
    """

    result = {}

    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Query each symbol's most recent data
        for symbol in symbols_list:
            try:
                # Get the most recent row (latest date) for this symbol
                cursor.execute(
                    f"""
                    SELECT date, close
                    FROM {symbol}
                    ORDER BY date DESC
                    LIMIT 1
                    """
                )

                row = cursor.fetchone()

                if row:
                    result[symbol] = {
                        'date': row[0],
                        'close': row[1]
                    }
                else:
                    print(f"  Warning: No data found for {symbol} in database")

            except sqlite3.OperationalError:
                # Table doesn't exist for this symbol
                print(f"  Warning: Table {symbol} does not exist in database")
                continue

        conn.close()

    except Exception as e:
        print(f"  ERROR: Failed to retrieve latest prices: {str(e)}")

    return result


# ==================================================================
# FUNCTION: update_all_symbols
# ==================================================================

def update_all_symbols() -> Dict[str, any]:
    """
    Update price data for all symbols in the watchlist.

    This is the main function to run daily to keep your database current.
    It downloads the latest data for all symbols defined in config.ALL_SYMBOLS
    and stores them in the database.

    Returns:
        Dictionary with update summary:
        {
            'successful': ['SPY', 'AAPL', ...],  # List of successfully updated symbols
            'failed': ['XYZ', ...],              # List of failed symbols
            'total': 20,                         # Total symbols attempted
            'success_count': 18,                 # Number of successful updates
            'timestamp': '2025-10-28 16:15:00'  # When the update ran
        }

    Example:
        >>> result = update_all_symbols()
        >>> print(f"Updated {result['success_count']}/{result['total']} symbols")
    """

    print("=" * 60)
    print("UPDATING PRICE DATA FOR ALL SYMBOLS")
    print("=" * 60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Symbols to update: {len(ALL_SYMBOLS)}")
    print()

    successful = []
    failed = []

    for i, symbol in enumerate(ALL_SYMBOLS, 1):
        print(f"[{i}/{len(ALL_SYMBOLS)}] Fetching {symbol}...")

        # Download data
        df = fetch_historical_data(symbol, period=DEFAULT_PERIOD)

        if df is not None and not df.empty:
            # Save to database
            if save_to_database(symbol, df):
                # Get the latest price to display
                latest_date = df.iloc[-1]['Date']
                latest_close = df.iloc[-1]['Close']
                print(f"   Updated {symbol}: ${latest_close:.2f} ({latest_date})")
                print(f"    Saved {len(df)} days of data to database")
                successful.append(symbol)
            else:
                print(f"   Failed to save {symbol} to database")
                failed.append(symbol)
        else:
            print(f"   Failed to fetch data for {symbol}")
            failed.append(symbol)

        print()  # Blank line between symbols

    # Summary
    print("=" * 60)
    print("UPDATE COMPLETE")
    print("=" * 60)
    print(f"Successful: {len(successful)}/{len(ALL_SYMBOLS)}")
    print(f"Failed: {len(failed)}/{len(ALL_SYMBOLS)}")

    if failed:
        print(f"Failed symbols: {', '.join(failed)}")

    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    return {
        'successful': successful,
        'failed': failed,
        'total': len(ALL_SYMBOLS),
        'success_count': len(successful),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }


# ==================================================================
# MAIN - For testing this module directly
# ==================================================================

if __name__ == "__main__":
    """
    Test the data fetcher by running:
        python src/data_fetcher.py

    This will update all symbols in your watchlist.
    """

    print("Running data fetcher in test mode...\n")
    result = update_all_symbols()

    # Test get_latest_prices
    print("\n" + "=" * 60)
    print("TESTING get_latest_prices()")
    print("=" * 60)

    prices = get_latest_prices(ALL_SYMBOLS[:5])  # Test with first 5 symbols
    for symbol, data in prices.items():
        print(f"{symbol}: ${data['close']:.2f} (as of {data['date']})")

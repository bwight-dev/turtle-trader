"""
Signal Calculator Module - Turtle Trading System

This module calculates Donchian Channel breakouts and generates trading signals.
The Donchian Channel is the highest high and lowest low over a specified period.

Entry Signals: 55-day breakout (price exceeds 55-day high/low)
Exit Signals: 20-day breakout (price exceeds 20-day high/low in opposite direction)

Functions:
    - calculate_donchian: Calculate Donchian Channel levels
    - get_current_levels: Get current price and channel levels for a symbol
    - check_breakout: Check if there's a trading signal
    - scan_all_symbols: Scan all watchlist symbols for signals
"""

import pandas as pd
import sqlite3
from typing import Optional, Dict, List
from datetime import datetime

# Import configuration settings
from config import ALL_SYMBOLS, DB_PRICES, ENTRY_PERIOD, EXIT_PERIOD

# ==================================================================
# CONFIGURATION - Modify these values if needed
# ==================================================================

# Number of days of data to fetch for calculations
# Must be at least ENTRY_PERIOD + some buffer
LOOKBACK_DAYS = 60


# ==================================================================
# FUNCTION: calculate_donchian
# ==================================================================

def calculate_donchian(dataframe: pd.DataFrame, period: int) -> pd.DataFrame:
    """
    Calculate Donchian Channel levels for a given period.

    The Donchian Channel consists of:
    - Upper band: Highest high over the period
    - Lower band: Lowest low over the period

    Args:
        dataframe: pandas DataFrame with columns: Date, Open, High, Low, Close, Volume
        period: Number of days for the rolling window (e.g., 55 or 20)

    Returns:
        DataFrame with added columns:
        - donchian_high_{period}: Highest high over the period
        - donchian_low_{period}: Lowest low over the period

    Example:
        >>> df = calculate_donchian(price_data, 55)
        >>> print(df[['Date', 'Close', 'donchian_high_55', 'donchian_low_55']])
    """

    # Make a copy to avoid modifying the original dataframe
    df = dataframe.copy()

    # Calculate rolling high over the period
    # This finds the maximum 'High' price in the last N days
    df[f'donchian_high_{period}'] = df['high'].rolling(window=period).max()

    # Calculate rolling low over the period
    # This finds the minimum 'Low' price in the last N days
    df[f'donchian_low_{period}'] = df['low'].rolling(window=period).min()

    return df


# ==================================================================
# FUNCTION: get_current_levels
# ==================================================================

def get_current_levels(symbol: str, db_path: str = DB_PRICES) -> Optional[Dict]:
    """
    Get current price and Donchian Channel levels for a symbol.

    Reads the last LOOKBACK_DAYS of price data from the database,
    calculates both entry (55-day) and exit (20-day) Donchian levels,
    and returns the current state.

    Args:
        symbol: Stock/ETF ticker symbol (e.g., 'SPY', 'AAPL')
        db_path: Path to SQLite database file

    Returns:
        Dictionary with current levels:
        {
            'symbol': 'SPY',
            'current_price': 685.88,
            'date': '2025-10-28',
            'entry_high': 685.54,  # 55-day high
            'entry_low': 652.45,   # 55-day low
            'exit_high': 685.54,   # 20-day high
            'exit_low': 652.84,    # 20-day low
        }

        Returns None if insufficient data or errors occur.

    Example:
        >>> levels = get_current_levels('SPY')
        >>> print(f"Entry level: ${levels['entry_high']:.2f}")
    """

    try:
        # Connect to database
        conn = sqlite3.connect(db_path)

        # Query the last LOOKBACK_DAYS of data for this symbol
        query = f"""
        SELECT date, open, high, low, close, volume
        FROM {symbol}
        ORDER BY date DESC
        LIMIT {LOOKBACK_DAYS}
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        # Check if we have enough data
        if df.empty or len(df) < ENTRY_PERIOD:
            print(f"  Warning: Insufficient data for {symbol} (need {ENTRY_PERIOD} days, have {len(df)})")
            return None

        # Sort by date ascending (oldest first) for rolling calculations
        df = df.sort_values('date').reset_index(drop=True)

        # Calculate 55-day Donchian (entry signals)
        df = calculate_donchian(df, ENTRY_PERIOD)

        # Calculate 20-day Donchian (exit signals)
        df = calculate_donchian(df, EXIT_PERIOD)

        # FIX: Shift Donchian values by 1 day
        # This ensures we compare today's price against YESTERDAY's Donchian levels
        # (not including today's data in the Donchian calculation)
        # For breakout detection, we need to check if today broke ABOVE/BELOW
        # the channel that existed BEFORE today
        df[f'donchian_high_{ENTRY_PERIOD}'] = df[f'donchian_high_{ENTRY_PERIOD}'].shift(1)
        df[f'donchian_low_{ENTRY_PERIOD}'] = df[f'donchian_low_{ENTRY_PERIOD}'].shift(1)
        df[f'donchian_high_{EXIT_PERIOD}'] = df[f'donchian_high_{EXIT_PERIOD}'].shift(1)
        df[f'donchian_low_{EXIT_PERIOD}'] = df[f'donchian_low_{EXIT_PERIOD}'].shift(1)

        # Get the most recent row (latest data)
        latest = df.iloc[-1]

        # Build result dictionary
        result = {
            'symbol': symbol,
            'date': latest['date'],
            'current_price': float(latest['close']),
            'entry_high': float(latest[f'donchian_high_{ENTRY_PERIOD}']),
            'entry_low': float(latest[f'donchian_low_{ENTRY_PERIOD}']),
            'exit_high': float(latest[f'donchian_high_{EXIT_PERIOD}']),
            'exit_low': float(latest[f'donchian_low_{EXIT_PERIOD}']),
        }

        return result

    except sqlite3.OperationalError as e:
        print(f"  Error: Table {symbol} not found in database")
        return None
    except Exception as e:
        print(f"  Error getting levels for {symbol}: {str(e)}")
        return None


# ==================================================================
# FUNCTION: check_breakout
# ==================================================================

def check_breakout(symbol: str, db_path: str = DB_PRICES, is_open_position: bool = False) -> Optional[Dict]:
    """
    Check if there's a trading signal for a symbol.

    Analyzes the current price relative to Donchian Channel levels
    and determines if there's an entry or exit signal.

    Signal Logic:
    - BUY: Current price > 55-day high (long entry)
    - SELL: Current price < 55-day low (short entry)
    - EXIT_LONG: Current price < 20-day low (exit long position)
    - EXIT_SHORT: Current price > 20-day high (exit short position)
    - NONE: No signal

    Args:
        symbol: Stock/ETF ticker symbol
        db_path: Path to SQLite database file
        is_open_position: True if this symbol has an open position (prioritizes exit signals)

    Returns:
        Dictionary with signal information:
        {
            'symbol': 'SPY',
            'signal': 'BUY',  # or 'SELL', 'EXIT_LONG', 'EXIT_SHORT', 'NONE'
            'current_price': 685.88,
            'entry_high': 685.54,
            'entry_low': 652.45,
            'exit_high': 685.54,
            'exit_low': 652.84,
            'reason': 'Price broke above 55-day high'
        }

        Returns None if data unavailable.

    Example:
        >>> signal = check_breakout('SPY')
        >>> if signal and signal['signal'] != 'NONE':
        ...     print(f"{signal['symbol']}: {signal['signal']} - {signal['reason']}")
    """

    # Get current levels
    levels = get_current_levels(symbol, db_path)

    if levels is None:
        return None

    # Extract values for easier reading
    price = levels['current_price']
    entry_high = levels['entry_high']
    entry_low = levels['entry_low']
    exit_high = levels['exit_high']
    exit_low = levels['exit_low']

    # Initialize result
    signal_dict = {
        'symbol': symbol,
        'signal': 'NONE',
        'current_price': price,
        'date': levels['date'],
        'entry_high': entry_high,
        'entry_low': entry_low,
        'exit_high': exit_high,
        'exit_low': exit_low,
        'reason': 'No signal'
    }

    # Check for signals based on current price vs. Donchian levels
    # Note: Use small buffer to account for floating point comparison
    # A breakout means price is ABOVE the high or BELOW the low

    # ENTRY SIGNALS (55-day breakout)
    if price > entry_high:
        signal_dict['signal'] = 'BUY'
        signal_dict['reason'] = f'Price ${price:.2f} broke above 55-day high ${entry_high:.2f}'

    elif price < entry_low:
        signal_dict['signal'] = 'SELL'
        signal_dict['reason'] = f'Price ${price:.2f} broke below 55-day low ${entry_low:.2f}'

    # EXIT SIGNALS (20-day breakout in opposite direction)
    # For long positions: exit if price breaks below 20-day low
    # For short positions: exit if price breaks above 20-day high
    # Note: We don't know position direction without portfolio info,
    # so we report both types of exit signals

    if price < exit_low:
        # Could be an exit signal for long positions
        if signal_dict['signal'] == 'NONE':
            signal_dict['signal'] = 'EXIT_LONG'
            signal_dict['reason'] = f'Price ${price:.2f} broke below 20-day low ${exit_low:.2f}'

    elif price > exit_high:
        # Could be an exit signal for short positions
        if signal_dict['signal'] == 'NONE':
            signal_dict['signal'] = 'EXIT_SHORT'
            signal_dict['reason'] = f'Price ${price:.2f} broke above 20-day high ${exit_high:.2f}'

    return signal_dict


# ==================================================================
# FUNCTION: scan_all_symbols
# ==================================================================

def scan_all_symbols(open_positions: Optional[List[str]] = None) -> List[Dict]:
    """
    Scan all watchlist symbols for trading signals.

    Checks each symbol in config.ALL_SYMBOLS for entry or exit signals.
    Prioritizes exit signals for open positions.

    Args:
        open_positions: List of symbols with open positions (e.g., ['SPY', 'AAPL'])
                       If None, assumes no open positions.

    Returns:
        List of signal dictionaries for symbols with active signals:
        [
            {
                'symbol': 'SPY',
                'signal': 'BUY',
                'current_price': 685.88,
                'reason': 'Price broke above 55-day high',
                ...
            },
            ...
        ]

        Only returns symbols where signal != 'NONE'.

    Example:
        >>> signals = scan_all_symbols(open_positions=['SPY'])
        >>> for sig in signals:
        ...     print(f"{sig['symbol']}: {sig['signal']}")
    """

    if open_positions is None:
        open_positions = []

    print("=" * 60)
    print("SCANNING FOR TRADING SIGNALS")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Symbols to scan: {len(ALL_SYMBOLS)}")
    print(f"Open positions: {len(open_positions)}")
    print()

    all_signals = []

    # Scan all symbols
    for i, symbol in enumerate(ALL_SYMBOLS, 1):
        print(f"[{i}/{len(ALL_SYMBOLS)}] Checking {symbol}...", end=" ")

        # Check if this symbol has an open position
        is_open = symbol in open_positions

        # Check for signals
        signal = check_breakout(symbol, is_open_position=is_open)

        if signal is None:
            print("No data")
            continue

        # Only collect signals that are not 'NONE'
        if signal['signal'] != 'NONE':
            print(f">> SIGNAL: {signal['signal']}")
            all_signals.append(signal)
        else:
            print("No signal")

    # Summary
    print()
    print("=" * 60)
    print("SCAN COMPLETE")
    print("=" * 60)
    print(f"Total signals found: {len(all_signals)}")

    if all_signals:
        print()
        print("Signals:")
        for sig in all_signals:
            print(f"  {sig['symbol']:6} {sig['signal']:12} ${sig['current_price']:8.2f}")

    print()

    return all_signals


# ==================================================================
# MAIN - For testing this module directly
# ==================================================================

if __name__ == "__main__":
    """
    Test the signal calculator by running:
        python src/signals.py

    This will scan all symbols for signals.
    """

    print("Running signal calculator in test mode...\n")

    # Test with a specific symbol first
    print("Testing with SPY:")
    print("-" * 60)
    levels = get_current_levels('SPY')
    if levels:
        print(f"Symbol: {levels['symbol']}")
        print(f"Date: {levels['date']}")
        print(f"Current Price: ${levels['current_price']:.2f}")
        print(f"Entry High (55-day): ${levels['entry_high']:.2f}")
        print(f"Entry Low (55-day): ${levels['entry_low']:.2f}")
        print(f"Exit High (20-day): ${levels['exit_high']:.2f}")
        print(f"Exit Low (20-day): ${levels['exit_low']:.2f}")

    print("\n")

    signal = check_breakout('SPY')
    if signal:
        print(f"Signal: {signal['signal']}")
        print(f"Reason: {signal['reason']}")

    print("\n\n")

    # Scan all symbols
    signals = scan_all_symbols()

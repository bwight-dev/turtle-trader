"""
Position Sizing Module - Turtle Trading System

This module calculates proper position sizes based on ATR (Average True Range)
and the 2% risk rule. Position sizing is critical in the Turtle Trading system
to ensure consistent risk management across all trades.

Key Concepts:
- ATR measures volatility (average price movement per day)
- 2% Risk Rule: Risk no more than 2% of account on any single trade
- Stop Loss: Placed at 2  ATR from entry
- Position Size: Calculated so that if stop is hit, loss = 2% of account

Functions:
    - calculate_atr: Calculate Average True Range from OHLC data
    - get_position_size: Calculate shares to buy based on risk
    - calculate_stop_loss: Calculate stop loss price
    - validate_position_size: Check if position meets portfolio limits
"""

import pandas as pd
import numpy as np
import sqlite3
from typing import Dict, Tuple, Optional, List

# Import configuration settings
from config import (
    ATR_PERIOD,
    ATR_MULTIPLIER,
    RISK_PER_TRADE,
    MAX_POSITIONS,
    DB_PRICES,
    ALLOW_FRACTIONAL_SHARES,
    FRACTIONAL_PRECISION
)


# ==================================================================
# FUNCTION: calculate_atr
# ==================================================================

def calculate_atr(dataframe: pd.DataFrame, period: int = ATR_PERIOD) -> float:
    """
    Calculate Average True Range (ATR) - a measure of volatility.

    The True Range for each day is the maximum of:
    1. High - Low (today's range)
    2. |High - Previous Close| (gap up from yesterday)
    3. |Low - Previous Close| (gap down from yesterday)

    ATR is the rolling average of True Range over the specified period.

    Args:
        dataframe: pandas DataFrame with columns: high, low, close
                  Must be sorted by date (oldest first)
        period: Number of days for ATR calculation (default from config)

    Returns:
        Float: Most recent ATR value

    Example:
        >>> df = get_price_data('SPY')
        >>> atr = calculate_atr(df, 20)
        >>> print(f"ATR: ${atr:.2f}")
    """

    if len(dataframe) < period + 1:
        raise ValueError(f"Insufficient data: need {period + 1} days, have {len(dataframe)}")

    df = dataframe.copy()

    # Calculate True Range components
    # 1. Today's High - Today's Low
    df['hl'] = df['high'] - df['low']

    # 2. |Today's High - Yesterday's Close|
    df['hc'] = abs(df['high'] - df['close'].shift(1))

    # 3. |Today's Low - Yesterday's Close|
    df['lc'] = abs(df['low'] - df['close'].shift(1))

    # True Range = max of the three components
    df['tr'] = df[['hl', 'hc', 'lc']].max(axis=1)

    # ATR = rolling average of True Range
    df['atr'] = df['tr'].rolling(window=period).mean()

    # Return the most recent ATR value
    return float(df['atr'].iloc[-1])


# ==================================================================
# FUNCTION: get_atr_for_symbol
# ==================================================================

def get_atr_for_symbol(symbol: str, period: int = ATR_PERIOD, db_path: str = DB_PRICES) -> Optional[float]:
    """
    Get the current ATR for a symbol from the database.

    Reads recent price data and calculates ATR.

    Args:
        symbol: Stock/ETF ticker symbol
        period: ATR calculation period (default from config)
        db_path: Path to price database

    Returns:
        Float: Current ATR value, or None if insufficient data

    Example:
        >>> atr = get_atr_for_symbol('SPY')
        >>> print(f"SPY ATR: ${atr:.2f}")
    """

    try:
        # Connect to database
        conn = sqlite3.connect(db_path)

        # Get enough data for ATR calculation (period + buffer)
        query = f"""
        SELECT date, high, low, close
        FROM {symbol}
        ORDER BY date DESC
        LIMIT {period + 10}
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        if len(df) < period + 1:
            print(f"  Warning: Insufficient data for ATR calculation on {symbol}")
            return None

        # Sort oldest first for calculations
        df = df.sort_values('date').reset_index(drop=True)

        # Calculate ATR
        atr = calculate_atr(df, period)

        return atr

    except Exception as e:
        print(f"  Error calculating ATR for {symbol}: {str(e)}")
        return None


# ==================================================================
# FUNCTION: calculate_stop_loss
# ==================================================================

def calculate_stop_loss(symbol: str, entry_price: float, direction: str = 'LONG',
                       atr: Optional[float] = None) -> float:
    """
    Calculate stop loss price based on ATR.

    Turtle Trading uses 2  ATR for stop loss distance.

    Args:
        symbol: Stock/ETF ticker symbol
        entry_price: Entry price for the trade
        direction: 'LONG' or 'SHORT'
        atr: ATR value (if None, will calculate from database)

    Returns:
        Float: Stop loss price

    Example:
        >>> stop = calculate_stop_loss('SPY', 685.88, 'LONG')
        >>> print(f"Stop loss: ${stop:.2f}")
    """

    # Get ATR if not provided
    if atr is None:
        atr = get_atr_for_symbol(symbol)
        if atr is None:
            raise ValueError(f"Cannot calculate ATR for {symbol}")

    # Calculate stop distance (ATR  multiplier from config)
    stop_distance = atr * ATR_MULTIPLIER

    # Calculate stop price based on direction
    if direction.upper() == 'LONG':
        # For long positions: stop below entry
        stop_price = entry_price - stop_distance
    elif direction.upper() == 'SHORT':
        # For short positions: stop above entry
        stop_price = entry_price + stop_distance
    else:
        raise ValueError(f"Invalid direction: {direction}. Must be 'LONG' or 'SHORT'")

    return float(stop_price)


# ==================================================================
# FUNCTION: get_position_size
# ==================================================================

def get_position_size(symbol: str, entry_price: float, account_value: float,
                     risk_percent: float = RISK_PER_TRADE,
                     atr: Optional[float] = None) -> Dict:
    """
    Calculate position size based on 2% risk rule and ATR.

    Position Sizing Formula:
    1. Risk Amount = Account Value  Risk Percent (2%)
    2. Stop Distance = ATR  Multiplier (2)
    3. Shares = Risk Amount / Stop Distance
    4. Round shares DOWN to whole number
    5. Actual Risk = Shares  Stop Distance

    Args:
        symbol: Stock/ETF ticker symbol
        entry_price: Intended entry price
        account_value: Current account value (total capital)
        risk_percent: Risk per trade as decimal (default 0.02 = 2%)
        atr: ATR value (if None, will calculate from database)

    Returns:
        Dictionary with position sizing details:
        {
            'symbol': 'SPY',
            'entry_price': 685.88,
            'atr': 8.50,
            'stop_distance': 17.00,      # ATR  2
            'stop_price': 668.88,         # entry - stop_distance
            'risk_amount': 269.79,        # 2% of account
            'shares': 15,                 # Rounded down
            'position_value': 10288.20,   # shares  entry_price
            'actual_risk': 255.00,        # shares  stop_distance
            'risk_percent': 0.0189        # actual_risk / account_value
        }

    Example:
        >>> position = get_position_size('SPY', 685.88, 13489.57)
        >>> print(f"Buy {position['shares']} shares at ${position['entry_price']:.2f}")
        >>> print(f"Stop loss: ${position['stop_price']:.2f}")
    """

    # Get ATR if not provided
    if atr is None:
        atr = get_atr_for_symbol(symbol)
        if atr is None:
            raise ValueError(f"Cannot calculate ATR for {symbol}")

    # Step 1: Calculate risk amount (how much $ we're willing to lose)
    risk_amount = account_value * risk_percent

    # Step 2: Calculate stop distance (how far away is the stop loss)
    stop_distance = atr * ATR_MULTIPLIER

    # Step 3: Calculate stop price
    stop_price = entry_price - stop_distance  # For LONG positions

    # Step 4: Calculate raw share count
    # If we buy X shares and stop gets hit, we lose X  stop_distance
    # We want that loss to equal risk_amount
    # So: X  stop_distance = risk_amount
    # Therefore: X = risk_amount / stop_distance
    shares_raw = risk_amount / stop_distance

    # Step 5: Round shares based on configuration
    if ALLOW_FRACTIONAL_SHARES:
        # Round to specified precision (e.g., 3 decimals = 1.427 shares)
        # Use ROUND_DOWN to never risk more than intended
        from decimal import Decimal, ROUND_DOWN
        shares = float(Decimal(str(shares_raw)).quantize(
            Decimal(10) ** -FRACTIONAL_PRECISION,
            rounding=ROUND_DOWN
        ))
    else:
        # Round DOWN to whole shares (never risk more than intended)
        shares = int(np.floor(shares_raw))

    # Step 6: Calculate actual risk with rounded shares
    actual_risk = shares * stop_distance

    # Step 7: Calculate position value (total cost to buy these shares)
    position_value = shares * entry_price

    # Step 8: Calculate actual risk percentage
    actual_risk_percent = actual_risk / account_value if account_value > 0 else 0

    # Build result dictionary
    result = {
        'symbol': symbol,
        'entry_price': round(entry_price, 2),
        'atr': round(atr, 2),
        'stop_distance': round(stop_distance, 2),
        'stop_price': round(stop_price, 2),
        'risk_amount': round(risk_amount, 2),
        'shares': shares,
        'position_value': round(position_value, 2),
        'actual_risk': round(actual_risk, 2),
        'risk_percent': round(actual_risk_percent, 4)
    }

    return result


# ==================================================================
# FUNCTION: validate_position_size
# ==================================================================

def validate_position_size(position_dict: Dict, account_value: float,
                          open_positions: Optional[List[Dict]] = None) -> Tuple[bool, str]:
    """
    Validate if a position meets portfolio risk limits.

    Checks:
    1. Position doesn't exceed individual position size limit
    2. Total portfolio risk doesn't exceed 12% (6 positions  2%)
    3. Sufficient capital available for the trade

    Args:
        position_dict: Position dictionary from get_position_size()
        account_value: Current account value
        open_positions: List of open position dicts with 'actual_risk' and 'position_value'

    Returns:
        Tuple: (is_valid: bool, reason: str)
        - (True, "Valid") if position passes all checks
        - (False, reason) if position fails any check

    Example:
        >>> position = get_position_size('SPY', 685.88, 13489.57)
        >>> is_valid, reason = validate_position_size(position, 13489.57, [])
        >>> print(f"Valid: {is_valid}, Reason: {reason}")
    """

    if open_positions is None:
        open_positions = []

    # Check 1: Maximum number of positions
    if len(open_positions) >= MAX_POSITIONS:
        return (False, f"Maximum positions ({MAX_POSITIONS}) already open")

    # Check 2: Individual position risk exceeds limit
    if position_dict['risk_percent'] > RISK_PER_TRADE * 1.1:  # Allow 10% buffer
        return (False, f"Position risk ({position_dict['risk_percent']:.2%}) exceeds limit ({RISK_PER_TRADE:.2%})")

    # Check 3: Total portfolio risk
    total_portfolio_risk = position_dict['actual_risk']
    for pos in open_positions:
        if 'actual_risk' in pos:
            total_portfolio_risk += pos['actual_risk']

    max_portfolio_risk = account_value * MAX_POSITIONS * RISK_PER_TRADE
    if total_portfolio_risk > max_portfolio_risk:
        portfolio_risk_percent = total_portfolio_risk / account_value
        max_risk_percent = MAX_POSITIONS * RISK_PER_TRADE
        return (False, f"Total portfolio risk ({portfolio_risk_percent:.2%}) would exceed limit ({max_risk_percent:.2%})")

    # Check 4: Sufficient capital available
    capital_in_positions = sum(pos.get('position_value', 0) for pos in open_positions)
    available_capital = account_value - capital_in_positions
    required_capital = position_dict['position_value']

    if required_capital > available_capital:
        return (False, f"Insufficient capital: need ${required_capital:,.2f}, have ${available_capital:,.2f}")

    # Check 5: Minimum position size
    if ALLOW_FRACTIONAL_SHARES:
        # For fractional shares, require at least 0.001 shares
        min_shares = 10 ** -FRACTIONAL_PRECISION
        if position_dict['shares'] < min_shares:
            return (False, f"Position too small: {position_dict['shares']} shares (volatility too high for account size)")
    else:
        # For whole shares, require at least 1 share
        if position_dict['shares'] < 1:
            return (False, f"Position too small: {position_dict['shares']} shares (volatility too high for account size)")

    # All checks passed
    return (True, "Valid")


# ==================================================================
# MAIN - For testing this module directly
# ==================================================================

if __name__ == "__main__":
    """
    Test the position sizing module by running:
        python src/position_sizing.py

    This will calculate position size for SPY.
    """

    print("Running position sizing in test mode...\n")

    # Test parameters
    test_symbol = 'SPY'
    test_entry_price = 687.60
    test_account_value = 13489.57

    print("=" * 60)
    print(f"TEST: Position Sizing for {test_symbol}")
    print("=" * 60)
    print(f"Entry Price: ${test_entry_price:.2f}")
    print(f"Account Value: ${test_account_value:,.2f}")
    print(f"Risk Per Trade: {RISK_PER_TRADE:.1%}")
    print()

    # Test ATR calculation
    print("Step 1: Calculate ATR...")
    atr = get_atr_for_symbol(test_symbol)
    if atr:
        print(f"  ATR ({ATR_PERIOD} days): ${atr:.2f}")
    else:
        print("  Failed to calculate ATR")
        exit(1)

    print()

    # Test stop loss calculation
    print("Step 2: Calculate Stop Loss...")
    stop = calculate_stop_loss(test_symbol, test_entry_price, 'LONG', atr)
    print(f"  Stop Price: ${stop:.2f}")
    print(f"  Stop Distance: ${test_entry_price - stop:.2f} ({ATR_MULTIPLIER}  ATR)")

    print()

    # Test position sizing
    print("Step 3: Calculate Position Size...")
    position = get_position_size(test_symbol, test_entry_price, test_account_value, atr=atr)

    print(f"  Risk Amount: ${position['risk_amount']:,.2f} ({RISK_PER_TRADE:.1%} of account)")
    print(f"  Shares to Buy: {position['shares']}")
    print(f"  Position Value: ${position['position_value']:,.2f}")
    print(f"  Actual Risk: ${position['actual_risk']:,.2f} ({position['risk_percent']:.2%})")

    print()

    # Test validation
    print("Step 4: Validate Position...")
    is_valid, reason = validate_position_size(position, test_account_value, [])
    print(f"  Valid: {is_valid}")
    print(f"  Reason: {reason}")

    print()
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

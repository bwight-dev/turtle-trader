#!/usr/bin/env python3
"""
Calculate Position Size - Simple Script

Calculates how many shares to buy for a given symbol based on:
- Current ATR (volatility)
- Account value
- 2% risk rule

Usage:
    ./venv/bin/python3 scripts/calculate_position.py SPY 687.60
    ./venv/bin/python3 scripts/calculate_position.py SPY 687.60 15000

Arguments:
    SYMBOL      - Stock/ETF ticker (e.g., SPY, AAPL)
    ENTRY_PRICE - Intended entry price
    ACCOUNT     - Account value (optional, defaults to config.INITIAL_CAPITAL)
"""

import sys
import os

# Add parent directory to path so we can import from src/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.position_sizing import get_position_size, validate_position_size
from config import INITIAL_CAPITAL, ALL_SYMBOLS

def main():
    # Parse command line arguments
    if len(sys.argv) < 3:
        print()
        print("Usage: ./venv/bin/python3 scripts/calculate_position.py SYMBOL ENTRY_PRICE [ACCOUNT_VALUE]")
        print()
        print("Examples:")
        print("  ./venv/bin/python3 scripts/calculate_position.py SPY 687.60")
        print("  ./venv/bin/python3 scripts/calculate_position.py AAPL 269.12 15000")
        print()
        print(f"Available symbols: {', '.join(ALL_SYMBOLS)}")
        print()
        return

    symbol = sys.argv[1].upper()
    try:
        entry_price = float(sys.argv[2])
    except ValueError:
        print(f"\nError: Invalid entry price '{sys.argv[2]}'. Must be a number.\n")
        return

    # Use provided account value or default from config
    if len(sys.argv) > 3:
        try:
            account_value = float(sys.argv[3])
        except ValueError:
            print(f"\nError: Invalid account value '{sys.argv[3]}'. Must be a number.\n")
            return
    else:
        account_value = INITIAL_CAPITAL

    # Validate symbol
    if symbol not in ALL_SYMBOLS:
        print(f"\nWarning: {symbol} is not in your watchlist.")
        print(f"Watchlist: {', '.join(ALL_SYMBOLS)}\n")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return

    try:
        # Calculate position size
        print()
        print("=" * 70)
        print(f"POSITION SIZING FOR {symbol}")
        print("=" * 70)
        print(f"Entry Price:     ${entry_price:,.2f}")
        print(f"Account Value:   ${account_value:,.2f}")
        print()

        position = get_position_size(symbol, entry_price, account_value)

        print("VOLATILITY:")
        print("-" * 70)
        print(f"  ATR (20-day):           ${position['atr']:,.2f}")
        print(f"  Stop Distance (2x ATR): ${position['stop_distance']:,.2f}")
        print(f"  Stop Loss Price:        ${position['stop_price']:,.2f}")
        print()

        print("POSITION SIZING:")
        print("-" * 70)
        print(f"  Risk Amount (2%):       ${position['risk_amount']:,.2f}")
        print(f"  Shares to Buy:          {position['shares']:,}")
        print(f"  Total Cost:             ${position['position_value']:,.2f}")
        print()

        print("RISK ANALYSIS:")
        print("-" * 70)
        print(f"  Max Loss (if stop hit): ${position['actual_risk']:,.2f}")
        print(f"  Actual Risk Percent:    {position['risk_percent']:.2%}")
        print()

        # Validate position
        is_valid, reason = validate_position_size(position, account_value, [])

        print("VALIDATION:")
        print("-" * 70)
        if is_valid:
            print(f"  Status: VALID")
            print(f"  Reason: {reason}")
        else:
            print(f"  Status: INVALID")
            print(f"  Reason: {reason}")

        print()
        print("=" * 70)

        if is_valid:
            print()
            print("TRADE SUMMARY:")
            print(f"  BUY {position['shares']} shares of {symbol} @ ${entry_price:.2f}")
            print(f"  Stop Loss: ${position['stop_price']:.2f}")
            print(f"  Risk: ${position['actual_risk']:.2f} ({position['risk_percent']:.2%})")
            print()

    except Exception as e:
        print(f"\nError: {str(e)}\n")

if __name__ == "__main__":
    main()

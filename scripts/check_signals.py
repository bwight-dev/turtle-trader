#!/usr/bin/env python3
"""
Check Trading Signals - Simple Script

Scans all symbols for Donchian Channel breakout signals.
Shows BUY, SELL, and EXIT signals based on current prices.

Usage:
    ./venv/bin/python3 scripts/check_signals.py
"""

import sys
import os

# Add parent directory to path so we can import from src/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.signals import scan_all_symbols, check_breakout

def main():
    """
    Scan all symbols and display any active signals.
    """

    print()

    # Option to check a single symbol
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper()
        print(f"Checking {symbol} for signals...")
        print("=" * 60)

        signal = check_breakout(symbol)

        if signal is None:
            print(f"\nNo data available for {symbol}")
            print("Run: ./venv/bin/python3 scripts/update_data.py\n")
            return

        print(f"\nSymbol: {signal['symbol']}")
        print(f"Date: {signal['date']}")
        print(f"Current Price: ${signal['current_price']:.2f}")
        print()
        print("Entry Levels (55-day Donchian):")
        print(f"  High: ${signal['entry_high']:.2f}")
        print(f"  Low:  ${signal['entry_low']:.2f}")
        print()
        print("Exit Levels (20-day Donchian):")
        print(f"  High: ${signal['exit_high']:.2f}")
        print(f"  Low:  ${signal['exit_low']:.2f}")
        print()
        print(f"Signal: {signal['signal']}")
        print(f"Reason: {signal['reason']}")
        print()

    else:
        # Scan all symbols
        signals = scan_all_symbols()

        # Display detailed results
        if signals:
            print("\n" + "=" * 60)
            print("DETAILED SIGNAL INFORMATION")
            print("=" * 60)

            for sig in signals:
                print()
                print(f"Symbol: {sig['symbol']}")
                print(f"Signal: {sig['signal']}")
                print(f"Current Price: ${sig['current_price']:.2f}")
                print(f"Reason: {sig['reason']}")
                print(f"Entry High: ${sig['entry_high']:.2f}")
                print(f"Entry Low: ${sig['entry_low']:.2f}")
                print("-" * 60)

        print()

if __name__ == "__main__":
    main()

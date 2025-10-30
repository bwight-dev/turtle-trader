#!/usr/bin/env python3
"""
View Portfolio - Simple Script

View your current portfolio including open positions, account balance,
and unrealized P&L.

Usage:
    ./venv/bin/python3 scripts/view_portfolio.py               # Paper trading (default)
    ./venv/bin/python3 scripts/view_portfolio.py --real        # Real trading
    ./venv/bin/python3 scripts/view_portfolio.py --paper       # Paper trading (explicit)
"""

import sys
import os

# Add parent directory to path so we can import from src/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.portfolio import get_open_positions, get_portfolio_summary, get_account_balance, calculate_trading_edge
from src.data_fetcher import get_latest_prices
from config import ALL_SYMBOLS

def main():
    # Parse arguments
    trade_type = 'PAPER'  # Default to paper for safety
    if '--real' in sys.argv:
        trade_type = 'REAL'
    elif '--paper' in sys.argv:
        trade_type = 'PAPER'

    print()
    print("=" * 70)
    print(f"PORTFOLIO SUMMARY - {trade_type} TRADING")
    print("=" * 70)
    print()

    # Get account balance
    balance = get_account_balance(trade_type)
    print(f"Account Balance: ${balance:,.2f}")
    print()

    # Get open positions
    positions = get_open_positions(trade_type)

    if not positions:
        print("No open positions")
        print()
    else:
        # Get current prices for all open symbols
        symbols = [pos['symbol'] for pos in positions]
        current_prices = get_latest_prices(symbols)

        # Get portfolio summary with current prices
        summary = get_portfolio_summary(trade_type, current_prices)

        print(f"Open Positions: {summary['num_positions']}")
        print(f"Total Invested: ${summary['total_invested']:,.2f}")
        print(f"Unrealized P&L: ${summary['unrealized_pnl']:,.2f}")
        print()

        # Show each position
        print("POSITIONS:")
        print("-" * 70)
        for pos in summary['positions']:
            print(f"#{pos['id']} - {pos['symbol']} ({pos['direction']})")
            print(f"  Entry:        {pos['shares']} shares @ ${pos['entry_price']:.2f} = ${pos['entry_value']:,.2f}")
            if pos['current_price']:
                print(f"  Current:      ${pos['current_price']:.2f} = ${pos['current_value']:,.2f}")
                pnl_sign = "+" if pos['unrealized_pnl'] >= 0 else ""
                pnl_pct = (pos['unrealized_pnl'] / pos['entry_value']) * 100 if pos['entry_value'] > 0 else 0
                print(f"  Unrealized:   {pnl_sign}${pos['unrealized_pnl']:.2f} ({pnl_sign}{pnl_pct:.2f}%)")
            print(f"  Stop Loss:    ${pos['stop_price']:.2f}")
            print(f"  Exit Level:   ${pos['exit_level']:.2f}")
            print(f"  Days Held:    {pos['days_held']}")
            print()

    # Show trading statistics
    print("=" * 70)
    print("TRADING STATISTICS")
    print("=" * 70)
    edge = calculate_trading_edge(trade_type)

    if edge['total_trades'] == 0:
        print("No closed trades yet")
    else:
        print(f"Total Trades:     {edge['total_trades']}")
        print(f"Winning Trades:   {edge['winning_trades']} ({edge['win_percent']:.1%})")
        print(f"Losing Trades:    {edge['losing_trades']}")
        print(f"Average Win:      ${edge['avg_win']:.2f}")
        print(f"Average Loss:     ${edge['avg_loss']:.2f}")
        print(f"Trading Edge:     ${edge['edge']:.2f}")
        print(f"Total P&L:        ${edge['total_pnl']:.2f}")
        print(f"Largest Win:      ${edge['largest_win']:.2f}")
        print(f"Largest Loss:     ${edge['largest_loss']:.2f}")

    print()
    print("=" * 70)
    print()

if __name__ == "__main__":
    main()

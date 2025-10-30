#!/usr/bin/env python3
"""
Turtle Trading System - Main Daily Runner

This is the main orchestrator that runs the complete trading workflow:
1. Updates price data
2. Scans for signals
3. Calculates position sizes
4. Shows portfolio summary
5. Displays trading statistics

Usage:
    python main.py --now              # Run scan immediately (paper)
    python main.py --now --real       # Run scan immediately (real)
    python main.py --schedule         # Run daily at 4:15 PM (paper)
    python main.py --schedule --real  # Run daily at 4:15 PM (real)
"""

import sys
import argparse
from datetime import datetime
from typing import List, Dict

# Import our modules
from src.data_fetcher import update_all_symbols, get_latest_prices
from src.signals import scan_all_symbols, check_breakout
from src.position_sizing import get_position_size, validate_position_size
from src.portfolio import (
    get_open_positions,
    get_portfolio_summary,
    calculate_trading_edge,
    get_account_balance
)
from config import ALL_SYMBOLS, SCAN_TIME, INITIAL_CAPITAL


# ==================================================================
# FUNCTION: run_daily_scan
# ==================================================================

def run_daily_scan(trade_type: str = 'PAPER') -> Dict:
    """
    Run the complete daily trading workflow.

    Args:
        trade_type: 'PAPER' or 'REAL' (default 'PAPER' for safety)

    Returns:
        Dictionary with scan results

    Workflow:
        1. Update price data
        2. Get open positions
        3. Scan for signals
        4. Calculate position sizes
        5. Get portfolio summary
        6. Display results
    """

    # Header
    print()
    print("=" * 70)
    print(f"TURTLE TRADING SYSTEM - Daily Scan [{trade_type}]")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    # STEP 1: Update price data
    print("[1/6] Updating Price Data...")
    update_result = update_all_symbols()
    if update_result['success_count'] < len(ALL_SYMBOLS):
        print(f"  Warning: Only updated {update_result['success_count']}/{update_result['total']} symbols")
        if update_result['failed']:
            print(f"  Failed: {', '.join(update_result['failed'])}")
    else:
        print(f"  Updated {update_result['success_count']}/{update_result['total']} symbols successfully")
    print()

    # STEP 2: Get account and portfolio info
    print("[2/6] Checking Portfolio...")
    account_balance = get_account_balance(trade_type)
    open_positions = get_open_positions(trade_type)
    print(f"  Account Balance: ${account_balance:,.2f}")
    print(f"  Open Positions: {len(open_positions)}")
    print()

    # STEP 3: Scan for signals
    print("[3/6] Scanning for Signals...")
    open_symbols = [pos['symbol'] for pos in open_positions]

    # We'll manually scan to separate entry vs exit signals
    entry_signals = []
    exit_signals = []

    for symbol in ALL_SYMBOLS:
        signal = check_breakout(symbol)
        if signal and signal['signal'] != 'NONE':
            # Check if this is an exit signal for an open position
            if symbol in open_symbols:
                if signal['signal'] in ['EXIT_LONG', 'EXIT_SHORT']:
                    exit_signals.append(signal)
            else:
                # Entry signals for symbols we don't have positions in
                if signal['signal'] in ['BUY', 'SELL']:
                    entry_signals.append(signal)

    print(f"  Found {len(entry_signals)} entry signal(s)")
    print(f"  Found {len(exit_signals)} exit signal(s)")
    print()

    # STEP 4: Calculate position sizes for entry signals
    print("[4/6] Calculating Position Sizes...")
    sized_signals = []
    for signal in entry_signals:
        try:
            position = get_position_size(
                signal['symbol'],
                signal['current_price'],
                account_balance
            )
            # Validate the position
            is_valid, reason = validate_position_size(position, account_balance, open_positions)
            signal['position'] = position
            signal['valid'] = is_valid
            signal['validation_reason'] = reason
            sized_signals.append(signal)
        except Exception as e:
            print(f"  Error sizing {signal['symbol']}: {str(e)}")

    if sized_signals:
        print(f"  Calculated position sizes for {len(sized_signals)} signal(s)")
    else:
        print(f"  No position sizes to calculate")
    print()

    # STEP 5: Get portfolio summary with current prices
    print("[5/6] Getting Portfolio Summary...")
    current_prices = get_latest_prices(ALL_SYMBOLS)
    portfolio_summary = get_portfolio_summary(trade_type, current_prices)
    print(f"  Portfolio value tracked")
    print()

    # STEP 6: Get trading statistics
    print("[6/6] Calculating Trading Statistics...")
    trading_stats = calculate_trading_edge(trade_type)
    print(f"  Statistics calculated")
    print()

    # ================================================================
    # DISPLAY RESULTS
    # ================================================================

    # Entry Signals
    if sized_signals:
        print("=" * 70)
        print("ENTRY SIGNALS")
        print("=" * 70)
        print()

        for i, signal in enumerate(sized_signals, 1):
            pos = signal['position']
            print(f"{i}. {signal['signal']} {signal['symbol']} @ ${signal['current_price']:.2f}")
            print(f"   Breakout: {signal['reason']}")
            print(f"   Position Size: {pos['shares']} shares (${pos['position_value']:,.2f})")
            print(f"   Stop Loss: ${pos['stop_price']:.2f}")
            print(f"   Risk: ${pos['actual_risk']:.2f} ({pos['risk_percent']:.2%})")
            if not signal['valid']:
                print(f"   WARNING: {signal['validation_reason']}")
            print()
    else:
        print("=" * 70)
        print("ENTRY SIGNALS")
        print("=" * 70)
        print("  No entry signals today")
        print()

    # Exit Signals
    if exit_signals:
        print("=" * 70)
        print("EXIT SIGNALS")
        print("=" * 70)
        print()

        for i, signal in enumerate(exit_signals, 1):
            print(f"{i}. {signal['signal']} {signal['symbol']} @ ${signal['current_price']:.2f}")
            print(f"   Reason: {signal['reason']}")
            print()
    else:
        print("=" * 70)
        print("EXIT SIGNALS")
        print("=" * 70)
        print("  No exit signals today")
        print()

    # Portfolio Status
    print("=" * 70)
    print("PORTFOLIO STATUS")
    print("=" * 70)

    if portfolio_summary['num_positions'] == 0:
        print("  No open positions")
    else:
        print(f"  Open Positions: {portfolio_summary['num_positions']}")
        print(f"  Total Invested: ${portfolio_summary['total_invested']:,.2f}")
        if portfolio_summary['unrealized_pnl'] is not None:
            pnl_sign = "+" if portfolio_summary['unrealized_pnl'] >= 0 else ""
            print(f"  Unrealized P&L: {pnl_sign}${portfolio_summary['unrealized_pnl']:,.2f}")
        print()

        for pos in portfolio_summary['positions']:
            print(f"  - {pos['symbol']}: {pos['shares']} shares @ ${pos['entry_price']:.2f}")
            if pos['current_price']:
                pnl_sign = "+" if pos['unrealized_pnl'] >= 0 else ""
                print(f"    Current: ${pos['current_price']:.2f} | P&L: {pnl_sign}${pos['unrealized_pnl']:.2f}")
            print(f"    Exit if below: ${pos['exit_level']:.2f}")
            print()

    print()

    # Trading Statistics
    print("=" * 70)
    print("TRADING STATISTICS")
    print("=" * 70)

    if trading_stats['total_trades'] == 0:
        print("  No closed trades yet")
    else:
        print(f"  Total Trades: {trading_stats['total_trades']}")
        print(f"  Win Rate: {trading_stats['win_percent']:.1%} ({trading_stats['winning_trades']}/{trading_stats['total_trades']})")
        print(f"  Average Win: ${trading_stats['avg_win']:.2f}")
        print(f"  Average Loss: ${trading_stats['avg_loss']:.2f}")
        print(f"  Edge: ${trading_stats['edge']:.2f}")
        pnl_sign = "+" if trading_stats['total_pnl'] >= 0 else ""
        print(f"  Total P&L: {pnl_sign}${trading_stats['total_pnl']:.2f}")

    print()

    # Footer
    print("=" * 70)
    print(f"Scan Complete - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    return {
        'entry_signals': sized_signals,
        'exit_signals': exit_signals,
        'portfolio': portfolio_summary,
        'stats': trading_stats
    }


# ==================================================================
# FUNCTION: schedule_daily_run
# ==================================================================

def schedule_daily_run(trade_type: str = 'PAPER') -> None:
    """
    Schedule the daily scan to run at configured time.

    Args:
        trade_type: 'PAPER' or 'REAL' (default 'PAPER')

    Note: This will run indefinitely. Press Ctrl+C to stop.
    """

    try:
        import schedule
        import time
    except ImportError:
        print("Error: 'schedule' library not installed")
        print("Install with: pip install schedule")
        return

    # Schedule the scan
    schedule.every().day.at(SCAN_TIME).do(run_daily_scan, trade_type=trade_type)

    print()
    print("=" * 70)
    print(f"TURTLE TRADING SYSTEM - Scheduled Runner [{trade_type}]")
    print("=" * 70)
    print(f"Scan scheduled for {SCAN_TIME} daily")
    print("Press Ctrl+C to stop")
    print("=" * 70)
    print()

    # Keep running
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        print("\n\nScheduler stopped by user")


# ==================================================================
# MAIN - Command Line Interface
# ==================================================================

def main():
    """
    Main entry point with command line argument parsing.
    """

    parser = argparse.ArgumentParser(
        description='Turtle Trading System - Daily Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --now              Run scan immediately (paper trading)
  python main.py --now --real       Run scan immediately (real trading)
  python main.py --schedule         Schedule daily scan (paper trading)
  python main.py --schedule --real  Schedule daily scan (real trading)

Note: Paper trading is the default for safety.
Use --real flag to trade with real account.
        """
    )

    parser.add_argument(
        '--now',
        action='store_true',
        help='Run scan immediately'
    )

    parser.add_argument(
        '--schedule',
        action='store_true',
        help=f'Run on schedule (daily at {SCAN_TIME})'
    )

    parser.add_argument(
        '--real',
        action='store_true',
        help='Use REAL trading account (default is PAPER)'
    )

    parser.add_argument(
        '--paper',
        action='store_true',
        help='Use PAPER trading account (default)'
    )

    args = parser.parse_args()

    # Determine trade type (default to PAPER for safety)
    trade_type = 'REAL' if args.real else 'PAPER'

    # Validate arguments
    if args.now and args.schedule:
        print("Error: Cannot use both --now and --schedule")
        print("Choose one: --now for immediate run, --schedule for daily runs")
        sys.exit(1)

    # Run based on arguments
    if args.now:
        run_daily_scan(trade_type)
    elif args.schedule:
        schedule_daily_run(trade_type)
    else:
        parser.print_help()
        print()
        print("Error: Must specify --now or --schedule")
        sys.exit(1)


if __name__ == "__main__":
    main()

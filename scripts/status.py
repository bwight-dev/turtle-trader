#!/usr/bin/env python3
"""Status dashboard for Turtle Trading system.

Shows:
- Current positions from IBKR
- Recent logs
- launchd job status
- Last signals and trades

Usage:
    python scripts/status.py [--logs N] [--full]
"""

import argparse
import asyncio
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / 'logs'


def print_header(title: str):
    """Print a section header."""
    print()
    print('=' * 70)
    print(f' {title}')
    print('=' * 70)


def check_launchd_jobs():
    """Check status of launchd jobs."""
    print_header('LAUNCHD JOBS')

    jobs = [
        ('com.turtle.daily', 'Daily Scanner'),
        ('com.turtle.monitor', 'Position Monitor'),
    ]

    for job_id, name in jobs:
        try:
            result = subprocess.run(
                ['launchctl', 'list', job_id],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                # Parse output
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split('\t')
                    pid = parts[0] if parts[0] != '-' else 'Not running'
                    status = parts[1]
                    print(f'  {name:20} PID: {pid:10} Status: {status}')
                else:
                    print(f'  {name:20} Loaded but not running')
            else:
                print(f'  {name:20} NOT LOADED')
        except Exception as e:
            print(f'  {name:20} Error: {e}')


def show_recent_logs(log_file: str, lines: int = 20):
    """Show recent lines from a log file."""
    log_path = LOGS_DIR / log_file

    if not log_path.exists():
        print(f'  (no log file: {log_file})')
        return

    try:
        result = subprocess.run(
            ['tail', f'-{lines}', str(log_path)],
            capture_output=True,
            text=True
        )
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                print(f'  {line}')
        else:
            print('  (empty)')
    except Exception as e:
        print(f'  Error reading log: {e}')


def show_logs(num_lines: int = 20):
    """Show recent logs."""
    print_header('DAILY SCANNER LOG')
    show_recent_logs('daily.log', num_lines)

    print_header('POSITION MONITOR LOG')
    show_recent_logs('monitor.log', num_lines)


async def show_positions():
    """Show current IBKR positions."""
    print_header('CURRENT POSITIONS')

    try:
        from ib_insync import IB
        ib = IB()
        await ib.connectAsync('127.0.0.1', 7497, clientId=97, timeout=5)

        positions = ib.positions()
        if not positions:
            print('  No open positions')
        else:
            print(f'  {"Symbol":<8} {"Qty":>8} {"Avg Cost":>12} {"Mkt Value":>12}')
            print('  ' + '-' * 44)
            for pos in positions:
                if pos.position != 0:
                    mkt_value = abs(pos.position) * pos.avgCost
                    print(f'  {pos.contract.symbol:<8} {int(pos.position):>8} ${pos.avgCost:>10.2f} ${mkt_value:>10.2f}')

        # Open orders
        orders = ib.openOrders()
        if orders:
            print()
            print('  OPEN ORDERS:')
            for order in orders:
                print(f'    {order.action} {int(order.totalQuantity)} {order.orderType}')

        ib.disconnect()

    except Exception as e:
        print(f'  Cannot connect to IBKR: {e}')
        print('  (Make sure TWS is running)')


def show_help():
    """Show available commands."""
    print_header('QUICK COMMANDS')
    print('''
  View logs in real-time:
    tail -f logs/monitor.log
    tail -f logs/daily.log

  Start/stop launchd jobs:
    launchctl load ~/Library/LaunchAgents/com.turtle.monitor.plist
    launchctl unload ~/Library/LaunchAgents/com.turtle.monitor.plist

  Manual runs:
    python scripts/daily_run.py              # Signal scanner
    python scripts/monitor_positions.py --once   # Single position check
    python scripts/monitor_positions.py      # Continuous monitor

  Check job status:
    launchctl list | grep turtle
''')


async def main():
    parser = argparse.ArgumentParser(description='Turtle Trading status dashboard')
    parser.add_argument('--logs', type=int, default=15, help='Number of log lines to show')
    parser.add_argument('--full', action='store_true', help='Show full logs')
    args = parser.parse_args()

    print()
    print('=' * 70)
    print(f' TURTLE TRADING STATUS - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)

    # Positions
    await show_positions()

    # Jobs
    check_launchd_jobs()

    # Logs
    lines = 50 if args.full else args.logs
    show_logs(lines)

    # Help
    show_help()


if __name__ == '__main__':
    asyncio.run(main())

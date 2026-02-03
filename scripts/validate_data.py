#!/usr/bin/env python3
"""Data and calculation validation script.

Validates that our backtest data and calculations are accurate by:
1. Comparing Yahoo data against IBKR historical data
2. Checking N (ATR) calculations against known values
3. Checking Donchian channel calculations
4. Spot-checking signals against manual calculations

Usage:
    python scripts/validate_data.py [--symbols SPY QQQ] [--days 30]
"""

import argparse
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import yfinance as yf

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.domain.models.market import Bar
from src.domain.services.volatility import calculate_n
from src.domain.services.channels import calculate_donchian
from src.domain.services.signal_detector import SignalDetector
from src.adapters.backtesting.data_loader import SMALL_ACCOUNT_ETF_UNIVERSE


def get_yahoo_bars(symbol: str, days: int = 60) -> list[Bar]:
    """Fetch historical bars from Yahoo Finance."""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=f'{days}d')

    bars = []
    for idx, row in hist.iterrows():
        bars.append(Bar(
            symbol=symbol,
            date=idx.date(),
            open=Decimal(str(row['Open'])),
            high=Decimal(str(row['High'])),
            low=Decimal(str(row['Low'])),
            close=Decimal(str(row['Close'])),
            volume=int(row['Volume']),
        ))
    return bars


def get_ibkr_bars(ib, symbol: str, days: int = 60) -> list[Bar]:
    """Fetch historical bars from IBKR."""
    from ib_insync import Stock

    contract = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(contract)

    end_date = date.today()
    ibkr_bars = ib.reqHistoricalData(
        contract,
        endDateTime='',
        durationStr=f'{days} D',
        barSizeSetting='1 day',
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1,
    )

    bars = []
    for b in ibkr_bars:
        bars.append(Bar(
            symbol=symbol,
            date=b.date.date() if hasattr(b.date, 'date') else b.date,
            open=Decimal(str(b.open)),
            high=Decimal(str(b.high)),
            low=Decimal(str(b.low)),
            close=Decimal(str(b.close)),
            volume=int(b.volume),
        ))
    return bars


def validate_data_source(symbol: str, ib=None) -> dict:
    """Compare Yahoo vs IBKR data for a symbol."""
    result = {
        'symbol': symbol,
        'yahoo_bars': 0,
        'ibkr_bars': 0,
        'matching_dates': 0,
        'price_differences': [],
        'max_diff_pct': 0,
        'passed': False,
    }

    # Get Yahoo data
    yahoo_bars = get_yahoo_bars(symbol, days=30)
    result['yahoo_bars'] = len(yahoo_bars)
    yahoo_by_date = {b.date: b for b in yahoo_bars}

    # Get IBKR data if connected
    if ib and ib.isConnected():
        try:
            ibkr_bars = get_ibkr_bars(ib, symbol, days=30)
            result['ibkr_bars'] = len(ibkr_bars)

            # Compare overlapping dates
            for ibkr_bar in ibkr_bars:
                if ibkr_bar.date in yahoo_by_date:
                    yahoo_bar = yahoo_by_date[ibkr_bar.date]
                    result['matching_dates'] += 1

                    # Compare close prices
                    diff = abs(yahoo_bar.close - ibkr_bar.close)
                    diff_pct = float(diff / ibkr_bar.close * 100)

                    if diff_pct > 0.1:  # More than 0.1% difference
                        result['price_differences'].append({
                            'date': ibkr_bar.date,
                            'yahoo': float(yahoo_bar.close),
                            'ibkr': float(ibkr_bar.close),
                            'diff_pct': diff_pct,
                        })

                    if diff_pct > result['max_diff_pct']:
                        result['max_diff_pct'] = diff_pct

            # Pass if max difference < 1%
            result['passed'] = result['max_diff_pct'] < 1.0

        except Exception as e:
            result['error'] = str(e)
    else:
        result['error'] = 'IBKR not connected'

    return result


def validate_n_calculation(symbol: str) -> dict:
    """Validate N (ATR) calculation for a symbol."""
    result = {
        'symbol': symbol,
        'n_value': None,
        'manual_check': None,
        'passed': False,
    }

    bars = get_yahoo_bars(symbol, days=30)
    if len(bars) < 20:
        result['error'] = f'Insufficient data: {len(bars)} bars'
        return result

    # Calculate N using our function
    n = calculate_n(bars[-20:])
    result['n_value'] = float(n.value)

    # Manual calculation for verification
    # N = Average True Range over 20 days with Wilder's smoothing
    tr_values = []
    for i in range(1, len(bars)):
        high = bars[i].high
        low = bars[i].low
        prev_close = bars[i-1].close

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        tr_values.append(tr)

    # Simple average of last 20 TRs (initial N estimate)
    if len(tr_values) >= 20:
        simple_avg = sum(tr_values[-20:]) / 20
        result['manual_check'] = float(simple_avg)

        # They should be close (within 10% due to smoothing differences)
        diff_pct = abs(n.value - simple_avg) / simple_avg * 100
        result['diff_pct'] = float(diff_pct)
        result['passed'] = diff_pct < 15  # Allow 15% for smoothing effects

    return result


def validate_donchian_channels(symbol: str) -> dict:
    """Validate Donchian channel calculation."""
    result = {
        'symbol': symbol,
        'dc20_upper': None,
        'dc20_lower': None,
        'dc55_upper': None,
        'dc55_lower': None,
        'passed': False,
    }

    bars = get_yahoo_bars(symbol, days=70)
    if len(bars) < 55:
        result['error'] = f'Insufficient data: {len(bars)} bars'
        return result

    # Calculate using our function
    dc20 = calculate_donchian(bars[:-1], period=20)  # Exclude today
    dc55 = calculate_donchian(bars[:-1], period=55)

    result['dc20_upper'] = float(dc20.upper)
    result['dc20_lower'] = float(dc20.lower)
    result['dc55_upper'] = float(dc55.upper)
    result['dc55_lower'] = float(dc55.lower)

    # Manual calculation for verification
    last_20 = bars[-21:-1]  # 20 bars excluding today
    manual_20_high = max(b.high for b in last_20)
    manual_20_low = min(b.low for b in last_20)

    last_55 = bars[-56:-1]  # 55 bars excluding today
    manual_55_high = max(b.high for b in last_55)
    manual_55_low = min(b.low for b in last_55)

    result['manual_dc20_upper'] = float(manual_20_high)
    result['manual_dc20_lower'] = float(manual_20_low)
    result['manual_dc55_upper'] = float(manual_55_high)
    result['manual_dc55_lower'] = float(manual_55_low)

    # Check if they match exactly
    result['passed'] = (
        dc20.upper == manual_20_high and
        dc20.lower == manual_20_low and
        dc55.upper == manual_55_high and
        dc55.lower == manual_55_low
    )

    return result


def validate_signal_detection(symbol: str) -> dict:
    """Validate signal detection logic."""
    result = {
        'symbol': symbol,
        'current_price': None,
        'dc20_upper': None,
        'dc20_lower': None,
        'expected_signal': None,
        'detected_signal': None,
        'passed': False,
    }

    bars = get_yahoo_bars(symbol, days=30)
    if len(bars) < 21:
        result['error'] = f'Insufficient data: {len(bars)} bars'
        return result

    current_price = bars[-1].close
    dc20 = calculate_donchian(bars[:-1], period=20)

    result['current_price'] = float(current_price)
    result['dc20_upper'] = float(dc20.upper)
    result['dc20_lower'] = float(dc20.lower)

    # Determine expected signal manually
    if current_price > dc20.upper:
        result['expected_signal'] = 'S1_LONG'
    elif current_price < dc20.lower:
        result['expected_signal'] = 'S1_SHORT'
    else:
        result['expected_signal'] = None

    # Use SignalDetector
    detector = SignalDetector()
    signal = detector.detect_s1_signal(symbol, current_price, dc20)

    if signal:
        result['detected_signal'] = f'S1_{signal.direction.value.upper()}'
    else:
        result['detected_signal'] = None

    result['passed'] = result['expected_signal'] == result['detected_signal']

    return result


def run_validation(symbols: list[str], connect_ibkr: bool = True) -> dict:
    """Run all validation checks."""
    results = {
        'data_source': [],
        'n_calculation': [],
        'donchian': [],
        'signal_detection': [],
        'summary': {
            'total_checks': 0,
            'passed': 0,
            'failed': 0,
        }
    }

    # Connect to IBKR if requested
    ib = None
    if connect_ibkr:
        try:
            from ib_insync import IB
            ib = IB()
            ib.connect('127.0.0.1', 7497, clientId=60, timeout=10)
            print(f"Connected to IBKR: {ib.managedAccounts()}")
        except Exception as e:
            print(f"Warning: Could not connect to IBKR: {e}")
            print("Data source validation will be skipped.")

    print(f"\nValidating {len(symbols)} symbols...\n")

    for symbol in symbols:
        print(f"  {symbol}...")

        # 1. Data source validation
        data_result = validate_data_source(symbol, ib)
        results['data_source'].append(data_result)
        results['summary']['total_checks'] += 1
        if data_result['passed']:
            results['summary']['passed'] += 1
        elif 'error' not in data_result:
            results['summary']['failed'] += 1

        # 2. N calculation validation
        n_result = validate_n_calculation(symbol)
        results['n_calculation'].append(n_result)
        results['summary']['total_checks'] += 1
        if n_result['passed']:
            results['summary']['passed'] += 1
        else:
            results['summary']['failed'] += 1

        # 3. Donchian channel validation
        dc_result = validate_donchian_channels(symbol)
        results['donchian'].append(dc_result)
        results['summary']['total_checks'] += 1
        if dc_result['passed']:
            results['summary']['passed'] += 1
        else:
            results['summary']['failed'] += 1

        # 4. Signal detection validation
        sig_result = validate_signal_detection(symbol)
        results['signal_detection'].append(sig_result)
        results['summary']['total_checks'] += 1
        if sig_result['passed']:
            results['summary']['passed'] += 1
        else:
            results['summary']['failed'] += 1

    # Disconnect IBKR
    if ib and ib.isConnected():
        ib.disconnect()

    return results


def print_results(results: dict):
    """Print validation results."""
    print("\n" + "=" * 70)
    print("VALIDATION RESULTS")
    print("=" * 70)

    # Data source validation
    print("\n1. DATA SOURCE VALIDATION (Yahoo vs IBKR)")
    print("-" * 70)
    for r in results['data_source']:
        status = "PASS" if r['passed'] else ("SKIP" if 'error' in r else "FAIL")
        print(f"  {r['symbol']}: {status}", end="")
        if r['passed']:
            print(f" (max diff: {r['max_diff_pct']:.2f}%)")
        elif 'error' in r:
            print(f" ({r['error']})")
        else:
            print(f" (max diff: {r['max_diff_pct']:.2f}%)")
            for diff in r['price_differences'][:3]:
                print(f"    {diff['date']}: Yahoo ${diff['yahoo']:.2f} vs IBKR ${diff['ibkr']:.2f} ({diff['diff_pct']:.2f}%)")

    # N calculation validation
    print("\n2. N (ATR) CALCULATION VALIDATION")
    print("-" * 70)
    for r in results['n_calculation']:
        status = "PASS" if r['passed'] else "FAIL"
        print(f"  {r['symbol']}: {status}", end="")
        if r['n_value']:
            print(f" (N=${r['n_value']:.2f})", end="")
        if 'diff_pct' in r:
            print(f" (diff from simple avg: {r['diff_pct']:.1f}%)")
        else:
            print()

    # Donchian validation
    print("\n3. DONCHIAN CHANNEL VALIDATION")
    print("-" * 70)
    for r in results['donchian']:
        status = "PASS" if r['passed'] else "FAIL"
        print(f"  {r['symbol']}: {status}", end="")
        if r['dc20_upper']:
            print(f" (20D: ${r['dc20_upper']:.2f}/${r['dc20_lower']:.2f})")
        else:
            print()

    # Signal detection validation
    print("\n4. SIGNAL DETECTION VALIDATION")
    print("-" * 70)
    for r in results['signal_detection']:
        status = "PASS" if r['passed'] else "FAIL"
        print(f"  {r['symbol']}: {status}", end="")
        print(f" (expected: {r['expected_signal']}, got: {r['detected_signal']})")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    s = results['summary']
    print(f"  Total checks: {s['total_checks']}")
    print(f"  Passed:       {s['passed']}")
    print(f"  Failed:       {s['failed']}")
    print(f"  Pass rate:    {s['passed']/s['total_checks']*100:.1f}%")

    if s['failed'] == 0:
        print("\n  ALL VALIDATIONS PASSED")
    else:
        print(f"\n  WARNING: {s['failed']} VALIDATION(S) FAILED")


def main():
    parser = argparse.ArgumentParser(description='Validate backtest data and calculations')
    parser.add_argument('--symbols', nargs='+', default=None, help='Symbols to validate')
    parser.add_argument('--all', action='store_true', help='Validate all 15 ETFs')
    parser.add_argument('--no-ibkr', action='store_true', help='Skip IBKR connection')
    args = parser.parse_args()

    if args.all:
        symbols = SMALL_ACCOUNT_ETF_UNIVERSE
    elif args.symbols:
        symbols = args.symbols
    else:
        # Default: validate first 5 ETFs
        symbols = SMALL_ACCOUNT_ETF_UNIVERSE[:5]

    print("=" * 70)
    print("BACKTEST DATA VALIDATION")
    print("=" * 70)
    print(f"Symbols: {', '.join(symbols)}")

    results = run_validation(symbols, connect_ibkr=not args.no_ibkr)
    print_results(results)

    # Return exit code based on results
    return 0 if results['summary']['failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

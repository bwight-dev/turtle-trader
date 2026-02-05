#!/usr/bin/env python3
"""Position monitoring script for Turtle Trading system.

This script runs continuously during market hours, checking positions every 60 seconds.
It monitors for:
- Stop hits (2N hard stop) -> EXIT
- Breakout exits (10/20-day) -> EXIT
- Pyramid triggers (+½N level) -> ADD UNIT

Usage:
    python scripts/monitor_positions.py [--once] [--interval SECONDS]

Options:
    --once          Run single check and exit (for cron)
    --interval N    Check interval in seconds (default: 60)
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import yfinance as yf
from ib_insync import IB

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.repositories.alert_repository import PostgresAlertRepository
from src.adapters.repositories.position_repository import PostgresOpenPositionRepository
from src.application.commands.log_alert import AlertLogger, is_significant_change
from src.domain.models.alert import OpenPositionSnapshot
from src.domain.models.market import Bar, NValue
from src.domain.models.position import Position, PyramidLevel
from src.domain.models.enums import Direction, System
from src.domain.services.position_monitor import PositionMonitor
from src.domain.services.volatility import calculate_n
from src.domain.services.channels import calculate_donchian

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


def get_yahoo_data(symbol: str, days: int = 60) -> list[Bar]:
    """Fetch price data from Yahoo Finance."""
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


async def get_ibkr_positions(ib: IB) -> list[dict]:
    """Get current positions from IBKR."""
    positions = []
    for pos in ib.positions():
        if pos.position != 0:
            positions.append({
                'symbol': pos.contract.symbol,
                'quantity': int(pos.position),
                'avg_cost': float(pos.avgCost),
            })
    return positions


async def ensure_connected(ib: IB, max_retries: int = 3, retry_delay: int = 10) -> bool:
    """Ensure IBKR connection is alive, reconnect if needed.

    Args:
        ib: IB connection instance
        max_retries: Maximum reconnection attempts
        retry_delay: Seconds between retry attempts

    Returns:
        True if connected, False if all retries failed
    """
    if ib.isConnected():
        return True

    logger.warning("IBKR connection lost, attempting to reconnect...")

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Reconnection attempt {attempt}/{max_retries}...")
            await ib.connectAsync('127.0.0.1', 7497, clientId=98, timeout=10)
            logger.info(f"Reconnected to IBKR: {ib.managedAccounts()}")
            return True
        except Exception as e:
            logger.error(f"Reconnection attempt {attempt} failed: {e}")
            if attempt < max_retries:
                logger.info(f"Waiting {retry_delay}s before next attempt...")
                await asyncio.sleep(retry_delay)

    logger.error(f"Failed to reconnect after {max_retries} attempts")
    return False


async def check_position(symbol: str, quantity: int, avg_cost: float) -> dict:
    """Check a single position against turtle rules."""
    try:
        # Get market data
        bars = get_yahoo_data(symbol)
        if not bars:
            return {'symbol': symbol, 'error': 'No market data'}

        current_price = bars[-1].close

        # Calculate N and channels
        n_value_obj = calculate_n(bars)
        n_value = n_value_obj.value
        dc10 = calculate_donchian(bars, period=10, exclude_current=True)
        dc20 = calculate_donchian(bars, period=20, exclude_current=True)

        # Create position object
        entry_price = Decimal(str(avg_cost))
        stop_price = entry_price - (2 * n_value)
        direction = Direction.LONG if quantity > 0 else Direction.SHORT

        pyramid = PyramidLevel(
            level=1,
            entry_price=entry_price,
            contracts=abs(quantity),
            n_at_entry=n_value,
        )

        position = Position(
            symbol=symbol,
            direction=direction,
            system=System.S2,
            pyramid_levels=(pyramid,),
            current_stop=stop_price,
            initial_entry_price=entry_price,
            initial_n=n_value_obj,
        )

        # Run position monitor
        monitor = PositionMonitor()
        result = monitor.check_position(
            position=position,
            current_price=current_price,
            exit_channel=dc20,
        )

        return {
            'symbol': symbol,
            'quantity': quantity,
            'entry_price': float(entry_price),
            'current_price': float(current_price),
            'stop_price': float(stop_price),
            'exit_low': float(dc20.lower),
            'pyramid_trigger': float(position.next_pyramid_trigger),
            'action': result.action.value,
            'reason': result.reason,
            'pnl': float((current_price - entry_price) * abs(quantity)),
        }

    except Exception as e:
        return {'symbol': symbol, 'error': str(e)}


async def run_monitoring_cycle(
    ib: IB,
    alert_logger: AlertLogger | None = None,
    position_repo: PostgresOpenPositionRepository | None = None,
) -> list[dict]:
    """Run a single monitoring cycle."""
    logger.info("=" * 60)
    logger.info(f"MONITORING CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # Get positions
    positions = await get_ibkr_positions(ib)

    if not positions:
        logger.info("No open positions to monitor")
        return []

    logger.info(f"Checking {len(positions)} position(s)...")

    results = []
    for pos in positions:
        result = await check_position(pos['symbol'], pos['quantity'], pos['avg_cost'])
        results.append(result)

        if 'error' in result:
            logger.error(f"  {pos['symbol']}: ERROR - {result['error']}")
        else:
            action = result['action'].upper()
            if action != 'HOLD':
                logger.warning(f"  {pos['symbol']}: >>> {action} <<< - {result['reason']}")
            else:
                logger.info(
                    f"  {pos['symbol']}: {action} | "
                    f"Price ${result['current_price']:.2f} | "
                    f"Stop ${result['stop_price']:.2f} | "
                    f"P&L ${result['pnl']:.2f}"
                )

            # Update position snapshot if we have alert logging and significant change
            if position_repo and alert_logger:
                try:
                    existing = await position_repo.get(pos['symbol'])
                    if existing:
                        new_price = Decimal(str(result['current_price']))
                        new_pnl = Decimal(str(result['pnl']))
                        new_stop = Decimal(str(result['stop_price']))

                        if is_significant_change(existing, new_price, new_pnl, new_stop):
                            updated = OpenPositionSnapshot(
                                symbol=existing.symbol,
                                direction=existing.direction,
                                system=existing.system,
                                entry_price=existing.entry_price,
                                entry_date=existing.entry_date,
                                contracts=existing.contracts,
                                units=existing.units,
                                current_price=new_price,
                                stop_price=new_stop,
                                unrealized_pnl=new_pnl,
                                n_value=existing.n_value,
                                updated_at=datetime.now(),
                            )
                            await alert_logger.update_position(updated)
                            logger.debug(f"  {pos['symbol']}: Position snapshot updated")
                except Exception as e:
                    logger.debug(f"  {pos['symbol']}: Failed to update snapshot: {e}")

    # Summary
    actions_needed = [r for r in results if r.get('action') not in ['hold', None]]
    if actions_needed:
        logger.warning(f"ACTIONS NEEDED: {len(actions_needed)}")
        for r in actions_needed:
            logger.warning(f"  -> {r['symbol']}: {r['action']} - {r['reason']}")

    logger.info("-" * 60)
    return results


async def main():
    parser = argparse.ArgumentParser(description='Monitor turtle trading positions')
    parser.add_argument('--once', action='store_true', help='Run single check and exit')
    parser.add_argument('--interval', type=int, default=60, help='Check interval in seconds')
    args = parser.parse_args()

    logger.info("Starting Turtle Position Monitor")
    logger.info(f"Mode: {'Single check' if args.once else f'Continuous (every {args.interval}s)'}")

    # Initialize alert repositories for dashboard logging
    alert_repo = PostgresAlertRepository()
    position_repo = PostgresOpenPositionRepository()
    alert_logger = AlertLogger(alert_repo, position_repo)
    logger.info("Alert logging enabled for dashboard")

    # Connect to IBKR
    ib = IB()
    try:
        await ib.connectAsync('127.0.0.1', 7497, clientId=98)
        logger.info(f"Connected to IBKR: {ib.managedAccounts()}")
    except Exception as e:
        logger.error(f"Failed to connect to IBKR: {e}")
        logger.error("Make sure TWS is running with API connections enabled")
        return 1

    try:
        if args.once:
            # Single check
            await run_monitoring_cycle(ib, alert_logger, position_repo)
        else:
            # Continuous monitoring
            cycle = 0
            consecutive_failures = 0
            max_consecutive_failures = 10  # Exit after 10 consecutive reconnection failures

            while True:
                cycle += 1
                logger.info(f"\n[Cycle {cycle}]")

                # Check connection and reconnect if needed
                if not await ensure_connected(ib):
                    consecutive_failures += 1
                    logger.error(f"Connection unavailable (failure {consecutive_failures}/{max_consecutive_failures})")

                    if consecutive_failures >= max_consecutive_failures:
                        logger.error("Too many consecutive connection failures, exiting")
                        logger.error("Check that TWS is running and API connections are enabled")
                        return 1

                    logger.info(f"Next reconnection attempt in {args.interval} seconds...")
                    await asyncio.sleep(args.interval)
                    continue

                # Reset failure counter on successful connection
                consecutive_failures = 0

                await run_monitoring_cycle(ib, alert_logger, position_repo)
                logger.info(f"Next check in {args.interval} seconds...")
                await asyncio.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info("\nMonitoring stopped by user")
    finally:
        if ib.isConnected():
            ib.disconnect()
        logger.info("Disconnected from IBKR")

    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))

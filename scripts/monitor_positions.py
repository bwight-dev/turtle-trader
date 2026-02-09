#!/usr/bin/env python3
"""Position monitoring script for Turtle Trading system.

This script runs continuously during market hours, checking positions every 60 seconds.
It monitors for:
- Stop hits (2N hard stop) -> EXIT (auto-execute)
- Breakout exits (10/20-day) -> EXIT (auto-execute)
- Pyramid triggers (+½N level) -> ADD UNIT (auto-execute)

AUTO-EXECUTION MODE:
When signals are detected, this script automatically:
- Places market orders for pyramids and exits
- Creates/modifies stop orders after pyramids
- Logs all actions to the alerts database

Usage:
    python scripts/monitor_positions.py [--once] [--interval SECONDS] [--dry-run]

Options:
    --once          Run single check and exit (for cron)
    --interval N    Check interval in seconds (default: 60)
    --dry-run       Detect signals but don't execute (log only)
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

import yfinance as yf
from ib_insync import IB, Stock, MarketOrder, StopOrder

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.repositories.alert_repository import PostgresAlertRepository
from src.adapters.repositories.position_repository import PostgresOpenPositionRepository
from src.application.commands.log_alert import AlertLogger, is_significant_change
from src.domain.models.alert import AlertType, OpenPositionSnapshot
from src.domain.models.market import Bar, NValue
from src.domain.models.position import Position, PyramidLevel
from src.domain.models.enums import Direction, System
from src.domain.services.position_monitor import PositionMonitor
from src.domain.services.volatility import calculate_n
from src.domain.services.channels import calculate_donchian
from src.domain.rules import RISK_PER_TRADE

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


# =============================================================================
# AUTO-EXECUTION FUNCTIONS
# =============================================================================


def calculate_unit_size(equity: Decimal, n_value: Decimal) -> int:
    """Calculate unit size for stocks (point_value = 1).

    Rule 4: Unit = (Risk × Equity) / (N × PointValue)
    For stocks, point_value = 1, so Unit = (0.005 × Equity) / N
    """
    risk_amount = equity * RISK_PER_TRADE
    if n_value <= 0:
        return 0
    raw_size = risk_amount / n_value
    return int(raw_size.quantize(Decimal("1"), rounding=ROUND_DOWN))


async def get_account_equity(ib: IB) -> Decimal:
    """Get account equity from IBKR."""
    # Use async version to avoid event loop conflict
    account_values = await ib.accountSummaryAsync()
    for av in account_values:
        if av.tag == 'NetLiquidation':
            return Decimal(str(av.value))
    raise RuntimeError("Could not get account equity")


async def execute_pyramid(
    ib: IB,
    symbol: str,
    direction: Direction,
    current_price: Decimal,
    n_value: Decimal,
    current_quantity: int,
    current_units: int,
    alert_logger: AlertLogger | None = None,
) -> dict:
    """Execute a pyramid order: buy more shares, update stop.

    Args:
        ib: IBKR connection
        symbol: Stock symbol
        direction: LONG or SHORT
        current_price: Current market price
        n_value: Current N (ATR) value
        current_quantity: Current position quantity
        alert_logger: Optional alert logger for dashboard

    Returns:
        Dict with execution details
    """
    # Calculate unit size
    equity = await get_account_equity(ib)
    unit_size = calculate_unit_size(equity, n_value)

    if unit_size < 1:
        logger.warning(f"  {symbol}: Unit size too small ({unit_size}), skipping pyramid")
        return {'success': False, 'reason': 'Unit size too small'}

    # Create stock contract
    contract = Stock(symbol, 'SMART', 'USD')
    await ib.qualifyContractsAsync(contract)

    # Determine order action
    if direction == Direction.LONG:
        action = 'BUY'
        new_stop = current_price - (2 * n_value)
    else:
        action = 'SELL'
        new_stop = current_price + (2 * n_value)

    logger.info(f"  {symbol}: EXECUTING PYRAMID - {action} {unit_size} shares at market")

    # Place market order
    order = MarketOrder(action, unit_size)
    trade = ib.placeOrder(contract, order)

    # Wait for fill (with timeout)
    timeout = 30
    start = asyncio.get_event_loop().time()
    while trade.orderStatus.status not in ('Filled', 'Cancelled', 'Inactive'):
        await asyncio.sleep(0.5)
        if asyncio.get_event_loop().time() - start > timeout:
            logger.error(f"  {symbol}: Order timeout after {timeout}s")
            return {'success': False, 'reason': 'Order timeout'}

    if trade.orderStatus.status != 'Filled':
        logger.error(f"  {symbol}: Order not filled: {trade.orderStatus.status}")
        return {'success': False, 'reason': f'Order {trade.orderStatus.status}'}

    fill_price = Decimal(str(trade.orderStatus.avgFillPrice))
    filled_qty = int(trade.orderStatus.filled)
    logger.info(f"  {symbol}: FILLED {filled_qty} shares @ ${fill_price:.2f}")

    # Calculate new stop based on fill price (2N below new entry)
    if direction == Direction.LONG:
        new_stop = fill_price - (2 * n_value)
    else:
        new_stop = fill_price + (2 * n_value)

    # Cancel existing stop orders for this symbol
    for existing_trade in ib.openTrades():
        if (existing_trade.contract.symbol == symbol and
            existing_trade.order.orderType == 'STP'):
            logger.info(f"  {symbol}: Cancelling old stop order")
            ib.cancelOrder(existing_trade.order)
            await asyncio.sleep(1)

    # Place new stop order for TOTAL position (GTC so it persists)
    new_total_qty = current_quantity + filled_qty
    stop_action = 'SELL' if direction == Direction.LONG else 'BUY'
    stop_order = StopOrder(stop_action, new_total_qty, float(new_stop))
    stop_order.tif = 'GTC'  # Good Till Cancelled
    stop_order.outsideRth = True  # Trigger outside regular trading hours
    stop_trade = ib.placeOrder(contract, stop_order)

    logger.info(f"  {symbol}: NEW STOP @ ${new_stop:.2f} for {new_total_qty} shares")

    # Log to alerts database
    if alert_logger:
        try:
            await alert_logger.log_pyramid(
                symbol=symbol,
                trigger_price=fill_price,
                new_units=current_units + 1,  # Increment unit count
                new_stop=new_stop,
                new_contracts=new_total_qty,
            )
        except Exception as e:
            logger.error(f"  {symbol}: Failed to log alert: {e}")

    return {
        'success': True,
        'filled_qty': filled_qty,
        'fill_price': float(fill_price),
        'new_stop': float(new_stop),
        'new_total_qty': new_total_qty,
    }


async def execute_exit(
    ib: IB,
    symbol: str,
    direction: Direction,
    quantity: int,
    exit_type: str,
    exit_reason: str,
    alert_logger: AlertLogger | None = None,
) -> dict:
    """Execute an exit order: close the position.

    Args:
        ib: IBKR connection
        symbol: Stock symbol
        direction: LONG or SHORT (position direction)
        quantity: Number of shares to close
        exit_type: 'stop' or 'breakout'
        exit_reason: Detailed reason for exit
        alert_logger: Optional alert logger for dashboard

    Returns:
        Dict with execution details
    """
    # Create stock contract
    contract = Stock(symbol, 'SMART', 'USD')
    await ib.qualifyContractsAsync(contract)

    # Close direction is opposite of position
    if direction == Direction.LONG:
        action = 'SELL'
    else:
        action = 'BUY'

    logger.info(f"  {symbol}: EXECUTING EXIT - {action} {abs(quantity)} shares at market")

    # Cancel any existing stop orders first
    for existing_trade in ib.openTrades():
        if (existing_trade.contract.symbol == symbol and
            existing_trade.order.orderType == 'STP'):
            logger.info(f"  {symbol}: Cancelling stop order before exit")
            ib.cancelOrder(existing_trade.order)
            await asyncio.sleep(0.5)

    # Place market order to close
    order = MarketOrder(action, abs(quantity))
    trade = ib.placeOrder(contract, order)

    # Wait for fill (with timeout)
    timeout = 30
    start = asyncio.get_event_loop().time()
    while trade.orderStatus.status not in ('Filled', 'Cancelled', 'Inactive'):
        await asyncio.sleep(0.5)
        if asyncio.get_event_loop().time() - start > timeout:
            logger.error(f"  {symbol}: Exit order timeout after {timeout}s")
            return {'success': False, 'reason': 'Order timeout'}

    if trade.orderStatus.status != 'Filled':
        logger.error(f"  {symbol}: Exit order not filled: {trade.orderStatus.status}")
        return {'success': False, 'reason': f'Order {trade.orderStatus.status}'}

    fill_price = Decimal(str(trade.orderStatus.avgFillPrice))
    filled_qty = int(trade.orderStatus.filled)
    logger.info(f"  {symbol}: EXIT FILLED {filled_qty} shares @ ${fill_price:.2f}")

    # Log to alerts database
    if alert_logger:
        try:
            alert_type = AlertType.EXIT_STOP if exit_type == 'stop' else AlertType.EXIT_BREAKOUT
            await alert_logger.log_exit(
                symbol=symbol,
                alert_type=alert_type,
                exit_price=fill_price,
                details={
                    'direction': direction.value,
                    'contracts': filled_qty,
                    'reason': exit_reason,
                },
            )
        except Exception as e:
            logger.error(f"  {symbol}: Failed to log alert: {e}")

    return {
        'success': True,
        'filled_qty': filled_qty,
        'fill_price': float(fill_price),
    }


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


async def check_position(
    symbol: str,
    quantity: int,
    avg_cost: float,
    position_repo: PostgresOpenPositionRepository | None = None,
) -> dict:
    """Check a single position against turtle rules.

    Args:
        symbol: Stock symbol
        quantity: Position quantity (negative for short)
        avg_cost: Average cost from IBKR
        position_repo: Optional repo to get stored units/stop
    """
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

        # Get stored position data (units, stop) from database
        stored_units = 1
        stored_stop = None
        stored_entry = None
        if position_repo:
            try:
                existing = await position_repo.get(symbol)
                if existing:
                    stored_units = existing.units or 1
                    stored_stop = existing.stop_price
                    stored_entry = existing.entry_price
            except Exception:
                pass  # Fall back to defaults

        # Create position object
        entry_price = stored_entry if stored_entry else Decimal(str(avg_cost))
        direction = Direction.LONG if quantity > 0 else Direction.SHORT

        # Use stored stop if available, otherwise calculate from entry
        if stored_stop:
            stop_price = stored_stop
        elif direction == Direction.LONG:
            stop_price = entry_price - (2 * n_value)
        else:
            stop_price = entry_price + (2 * n_value)

        # Create pyramid levels based on stored unit count
        pyramid_levels = tuple(
            PyramidLevel(
                level=i + 1,
                entry_price=entry_price,
                contracts=abs(quantity) // stored_units,
                n_at_entry=n_value,
            )
            for i in range(stored_units)
        )

        position = Position(
            symbol=symbol,
            direction=direction,
            system=System.S2,
            pyramid_levels=pyramid_levels,
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
            'direction': direction,
            'entry_price': float(entry_price),
            'current_price': float(current_price),
            'current_price_decimal': current_price,  # Keep Decimal for execution
            'stop_price': float(stop_price),
            'stored_stop': stored_stop,  # Keep original for comparison
            'exit_low': float(dc20.lower),
            'exit_high': float(dc20.upper),
            'pyramid_trigger': float(position.next_pyramid_trigger),
            'n_value': n_value,  # Keep for pyramid sizing
            'units': stored_units,  # Track current units
            'action': result.action.value,
            'reason': result.reason,
            'pnl': float((current_price - entry_price) * quantity),  # Signed P&L
        }

    except Exception as e:
        return {'symbol': symbol, 'error': str(e)}


async def run_monitoring_cycle(
    ib: IB,
    alert_logger: AlertLogger | None = None,
    position_repo: PostgresOpenPositionRepository | None = None,
    dry_run: bool = False,
) -> list[dict]:
    """Run a single monitoring cycle.

    Args:
        ib: IBKR connection
        alert_logger: Alert logger for dashboard
        position_repo: Position repository for snapshots
        dry_run: If True, detect signals but don't execute
    """
    logger.info("=" * 60)
    logger.info(f"MONITORING CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if dry_run:
        logger.info(">>> DRY RUN MODE - No orders will be executed <<<")
    logger.info("=" * 60)

    # Get positions
    positions = await get_ibkr_positions(ib)

    if not positions:
        logger.info("No open positions to monitor")
        return []

    logger.info(f"Checking {len(positions)} position(s)...")

    results = []
    for pos in positions:
        result = await check_position(
            pos['symbol'], pos['quantity'], pos['avg_cost'], position_repo
        )
        results.append(result)

        if 'error' in result:
            logger.error(f"  {pos['symbol']}: ERROR - {result['error']}")
            continue

        action = result['action'].upper()

        if action == 'HOLD':
            logger.info(
                f"  {pos['symbol']}: {action} | "
                f"Price ${result['current_price']:.2f} | "
                f"Stop ${result['stop_price']:.2f} | "
                f"P&L ${result['pnl']:.2f}"
            )
        else:
            logger.warning(f"  {pos['symbol']}: >>> {action} <<< - {result['reason']}")

            # AUTO-EXECUTE if not dry run
            if not dry_run:
                if action == 'PYRAMID':
                    exec_result = await execute_pyramid(
                        ib=ib,
                        symbol=result['symbol'],
                        direction=result['direction'],
                        current_price=result['current_price_decimal'],
                        n_value=result['n_value'],
                        current_quantity=abs(result['quantity']),
                        current_units=result.get('units', 1),
                        alert_logger=alert_logger,
                    )
                    result['execution'] = exec_result

                elif action in ('EXIT_STOP', 'EXIT_BREAKOUT'):
                    exec_result = await execute_exit(
                        ib=ib,
                        symbol=result['symbol'],
                        direction=result['direction'],
                        quantity=result['quantity'],
                        exit_type='stop' if action == 'EXIT_STOP' else 'breakout',
                        exit_reason=result['reason'],
                        alert_logger=alert_logger,
                    )
                    result['execution'] = exec_result

        # Update position snapshot if we have alert logging and significant change
        if position_repo and alert_logger and 'error' not in result:
            try:
                existing = await position_repo.get(pos['symbol'])
                if existing:
                    new_price = Decimal(str(result['current_price']))
                    new_pnl = Decimal(str(result['pnl']))
                    # Use stored stop - don't recalculate and overwrite
                    new_stop = existing.stop_price

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
                            stop_price=existing.stop_price,  # Preserve stored stop
                            unrealized_pnl=new_pnl,
                            n_value=existing.n_value,
                            updated_at=datetime.now(),
                        )
                        await alert_logger.update_position(updated)
                        logger.debug(f"  {pos['symbol']}: Position snapshot updated")
            except Exception as e:
                logger.debug(f"  {pos['symbol']}: Failed to update snapshot: {e}")

    # Summary
    actions_executed = [r for r in results if r.get('execution', {}).get('success')]
    actions_failed = [r for r in results if 'execution' in r and not r['execution'].get('success')]

    if actions_executed:
        logger.info(f"ACTIONS EXECUTED: {len(actions_executed)}")
        for r in actions_executed:
            exec = r['execution']
            if 'new_stop' in exec:
                logger.info(f"  -> {r['symbol']}: PYRAMID {exec['filled_qty']} @ ${exec['fill_price']:.2f}, stop ${exec['new_stop']:.2f}")
            else:
                logger.info(f"  -> {r['symbol']}: EXIT {exec['filled_qty']} @ ${exec['fill_price']:.2f}")

    if actions_failed:
        logger.error(f"ACTIONS FAILED: {len(actions_failed)}")
        for r in actions_failed:
            logger.error(f"  -> {r['symbol']}: {r['action']} - {r['execution'].get('reason', 'Unknown')}")

    if dry_run:
        actions_needed = [r for r in results if r.get('action') not in ['hold', None]]
        if actions_needed:
            logger.warning(f"DRY RUN - Would have executed {len(actions_needed)} action(s)")
            for r in actions_needed:
                logger.warning(f"  -> {r['symbol']}: {r['action']} - {r['reason']}")

    logger.info("-" * 60)
    return results


async def main():
    parser = argparse.ArgumentParser(description='Monitor turtle trading positions')
    parser.add_argument('--once', action='store_true', help='Run single check and exit')
    parser.add_argument('--interval', type=int, default=60, help='Check interval in seconds')
    parser.add_argument('--dry-run', action='store_true', help='Detect signals but do not execute orders')
    args = parser.parse_args()

    logger.info("Starting Turtle Position Monitor")
    logger.info(f"Mode: {'Single check' if args.once else f'Continuous (every {args.interval}s)'}")
    if args.dry_run:
        logger.info(">>> DRY RUN MODE - No orders will be executed <<<")

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
            await run_monitoring_cycle(ib, alert_logger, position_repo, dry_run=args.dry_run)
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

                await run_monitoring_cycle(ib, alert_logger, position_repo, dry_run=args.dry_run)
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

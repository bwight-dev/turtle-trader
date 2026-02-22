"""Continuous monitoring loop for Turtle Trading system.

This workflow runs continuously during market hours to monitor positions:
- Check for stop hits (2N hard stop)
- Check for breakout exits (10/20-day)
- Check for pyramid triggers (+½N level)

Priority order (from Position Monitor spec):
1. EXIT_STOP - Stop hit, exit immediately
2. EXIT_BREAKOUT - Breakout exit signal
3. PYRAMID - Add to position at +½N
4. HOLD - No action required

This is separate from the daily workflow which handles new entries.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Callable

from src.application.commands.log_alert import AlertLogger
from src.application.commands.log_trade import TradeLogger
from src.application.commands.modify_stop import ModifyStopCommand
from src.domain.interfaces.broker import Broker
from src.domain.interfaces.data_feed import DataFeed
from src.domain.interfaces.repositories import (
    AlertRepository,
    NValueRepository,
    OpenPositionRepository,
    TradeRepository,
)
from src.domain.models.alert import AlertType
from src.domain.models.enums import Direction, PositionAction
from src.domain.models.portfolio import Portfolio
from src.domain.models.position import Position
from src.domain.services.position_monitor import (
    PositionCheckResult,
    PositionMonitor,
)


class MonitoringStatus(str, Enum):
    """Status of monitoring loop."""

    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class MonitoringAction:
    """An action taken by the monitoring loop."""

    symbol: str
    action: PositionAction
    executed_at: datetime
    success: bool
    details: str = ""
    error: str | None = None

    # For exits
    exit_price: Decimal | None = None
    realized_pnl: Decimal | None = None

    # For pyramids
    pyramid_level: int | None = None
    new_stop: Decimal | None = None


@dataclass
class MonitoringCycleResult:
    """Result of a single monitoring cycle."""

    cycle_number: int
    started_at: datetime
    completed_at: datetime
    positions_checked: int
    actions_taken: list[MonitoringAction] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_actions(self) -> bool:
        """Check if any actions were taken this cycle."""
        return len(self.actions_taken) > 0

    @property
    def exits_executed(self) -> int:
        """Number of exits executed this cycle."""
        return len([
            a for a in self.actions_taken
            if a.action in [PositionAction.EXIT_STOP, PositionAction.EXIT_BREAKOUT]
        ])

    @property
    def pyramids_executed(self) -> int:
        """Number of pyramids executed this cycle."""
        return len([a for a in self.actions_taken if a.action == PositionAction.PYRAMID])


@dataclass
class MonitoringLoopResult:
    """Result of monitoring loop execution."""

    status: MonitoringStatus
    started_at: datetime
    stopped_at: datetime | None = None
    cycles_completed: int = 0
    total_actions: int = 0
    cycle_results: list[MonitoringCycleResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class MonitoringLoop:
    """Continuous monitoring loop for open positions.

    This loop:
    1. Fetches current market prices
    2. Checks each position against rules
    3. Executes exits when stops/breakouts hit
    4. Executes pyramids when triggered
    5. Updates stops after pyramiding
    """

    def __init__(
        self,
        broker: Broker | None = None,
        data_feed: DataFeed | None = None,
        n_repo: NValueRepository | None = None,
        trade_repo: TradeRepository | None = None,
        alert_repo: AlertRepository | None = None,
        position_repo: OpenPositionRepository | None = None,
        check_interval_seconds: float = 60.0,
    ):
        """Initialize the monitoring loop.

        Args:
            broker: Broker for order execution
            data_feed: Data feed for prices
            n_repo: Repository for N values
            trade_repo: Repository for trade logging
            alert_repo: Repository for alert logging (dashboard)
            position_repo: Repository for position snapshots (dashboard)
            check_interval_seconds: Time between monitoring cycles
        """
        self._broker = broker
        self._data_feed = data_feed
        self._n_repo = n_repo
        self._trade_repo = trade_repo
        self._alert_repo = alert_repo
        self._position_repo = position_repo
        self._check_interval = check_interval_seconds

        # Create alert logger if repos provided
        self._alert_logger = (
            AlertLogger(alert_repo, position_repo)
            if alert_repo and position_repo
            else None
        )

        self._status = MonitoringStatus.STOPPED
        self._cycle_count = 0
        self._stop_requested = False

    @property
    def status(self) -> MonitoringStatus:
        """Current monitoring status."""
        return self._status

    @property
    def is_running(self) -> bool:
        """Check if loop is running."""
        return self._status == MonitoringStatus.RUNNING

    async def start(
        self,
        portfolio: Portfolio,
        max_cycles: int | None = None,
        on_cycle_complete: Callable[[MonitoringCycleResult], None] | None = None,
    ) -> MonitoringLoopResult:
        """Start the monitoring loop.

        Args:
            portfolio: Portfolio to monitor
            max_cycles: Optional maximum cycles (None = run until stopped)
            on_cycle_complete: Optional callback after each cycle

        Returns:
            MonitoringLoopResult when loop ends
        """
        self._status = MonitoringStatus.RUNNING
        self._stop_requested = False
        self._cycle_count = 0

        started_at = datetime.now()
        cycle_results = []
        errors = []

        try:
            while not self._stop_requested:
                # Check max cycles
                if max_cycles is not None and self._cycle_count >= max_cycles:
                    break

                # Run monitoring cycle
                cycle_result = await self.run_monitoring_cycle(portfolio)
                cycle_results.append(cycle_result)

                # Callback
                if on_cycle_complete:
                    on_cycle_complete(cycle_result)

                self._cycle_count += 1

                # Wait for next cycle
                if not self._stop_requested:
                    await asyncio.sleep(self._check_interval)

        except Exception as e:
            self._status = MonitoringStatus.ERROR
            errors.append(f"Monitoring loop error: {e}")

        self._status = MonitoringStatus.STOPPED

        return MonitoringLoopResult(
            status=self._status,
            started_at=started_at,
            stopped_at=datetime.now(),
            cycles_completed=self._cycle_count,
            total_actions=sum(len(c.actions_taken) for c in cycle_results),
            cycle_results=cycle_results,
            errors=errors,
        )

    def stop(self) -> None:
        """Request the monitoring loop to stop."""
        self._stop_requested = True

    def pause(self) -> None:
        """Pause the monitoring loop."""
        if self._status == MonitoringStatus.RUNNING:
            self._status = MonitoringStatus.PAUSED

    def resume(self) -> None:
        """Resume a paused monitoring loop."""
        if self._status == MonitoringStatus.PAUSED:
            self._status = MonitoringStatus.RUNNING

    async def run_monitoring_cycle(
        self,
        portfolio: Portfolio,
    ) -> MonitoringCycleResult:
        """Run a single monitoring cycle.

        Checks all positions and takes appropriate actions.

        Args:
            portfolio: Current portfolio state

        Returns:
            MonitoringCycleResult with actions taken
        """
        started_at = datetime.now()
        actions = []
        errors = []

        positions_checked = len(portfolio.positions)

        for symbol, position in portfolio.positions.items():
            try:
                action = await self._check_and_act(position)
                if action:
                    actions.append(action)
            except Exception as e:
                errors.append(f"Error checking {symbol}: {e}")

        return MonitoringCycleResult(
            cycle_number=self._cycle_count + 1,
            started_at=started_at,
            completed_at=datetime.now(),
            positions_checked=positions_checked,
            actions_taken=actions,
            errors=errors,
        )

    async def _check_and_act(
        self,
        position: Position,
    ) -> MonitoringAction | None:
        """Check a position and take action if needed.

        Args:
            position: Position to check

        Returns:
            MonitoringAction if action was taken, None otherwise
        """
        # In full implementation, would:
        # 1. Get current price from data feed
        # 2. Get current channels from calculator
        # 3. Check position with PositionMonitor
        # 4. Execute appropriate action

        # Placeholder - no action in skeleton
        return None

    async def _execute_exit(
        self,
        position: Position,
        check_result: PositionCheckResult,
    ) -> MonitoringAction:
        """Execute an exit for a position.

        Args:
            position: Position to exit
            check_result: Check result with exit details

        Returns:
            MonitoringAction with result
        """
        try:
            if self._broker:
                fill = await self._broker.close_position(position.symbol)

                # Log trade if we have trade repo
                if self._trade_repo:
                    logger = TradeLogger(self._trade_repo)
                    await logger.log_exit(
                        position=position,
                        exit_price=fill.fill_price,
                        exit_reason=check_result.action.value,
                        commission=fill.commission,
                    )

                # Log alert for dashboard
                if self._alert_logger:
                    alert_type = (
                        AlertType.EXIT_STOP
                        if check_result.action == PositionAction.EXIT_STOP
                        else AlertType.EXIT_BREAKOUT
                    )
                    await self._alert_logger.log_exit(
                        symbol=position.symbol,
                        alert_type=alert_type,
                        exit_price=fill.fill_price,
                        details={
                            "reason": check_result.reason,
                            "pnl": float(fill.realized_pnl) if hasattr(fill, 'realized_pnl') else None,
                        },
                    )

                return MonitoringAction(
                    symbol=position.symbol,
                    action=check_result.action,
                    executed_at=datetime.now(),
                    success=True,
                    details=check_result.reason,
                    exit_price=fill.fill_price,
                )
            else:
                return MonitoringAction(
                    symbol=position.symbol,
                    action=check_result.action,
                    executed_at=datetime.now(),
                    success=False,
                    details="No broker configured",
                    error="Broker not available",
                )
        except Exception as e:
            return MonitoringAction(
                symbol=position.symbol,
                action=check_result.action,
                executed_at=datetime.now(),
                success=False,
                error=str(e),
            )

    async def _execute_pyramid(
        self,
        position: Position,
        check_result: PositionCheckResult,
    ) -> MonitoringAction:
        """Execute a pyramid for a position.

        Args:
            position: Position to pyramid
            check_result: Check result with pyramid details

        Returns:
            MonitoringAction with result
        """
        try:
            if self._broker:
                # In full implementation:
                # 1. Calculate unit size
                # 2. Place bracket order
                # 3. Update stop for entire position (Rule 12)

                # Log alert for dashboard
                if self._alert_logger and check_result.new_stop:
                    await self._alert_logger.log_pyramid(
                        symbol=position.symbol,
                        trigger_price=check_result.current_price,
                        new_units=check_result.pyramid_level or (position.unit_count + 1),
                        new_stop=check_result.new_stop,
                        new_contracts=position.total_contracts,  # Would be updated after fill
                    )

                return MonitoringAction(
                    symbol=position.symbol,
                    action=PositionAction.PYRAMID,
                    executed_at=datetime.now(),
                    success=True,
                    details=check_result.reason,
                    pyramid_level=check_result.pyramid_level,
                    new_stop=check_result.new_stop,
                )
            else:
                return MonitoringAction(
                    symbol=position.symbol,
                    action=PositionAction.PYRAMID,
                    executed_at=datetime.now(),
                    success=False,
                    details="No broker configured",
                    error="Broker not available",
                )
        except Exception as e:
            return MonitoringAction(
                symbol=position.symbol,
                action=PositionAction.PYRAMID,
                executed_at=datetime.now(),
                success=False,
                error=str(e),
            )


async def run_monitoring_loop(
    portfolio: Portfolio,
    max_cycles: int = 1,
    check_interval_seconds: float = 60.0,
) -> MonitoringLoopResult:
    """Convenience function to run monitoring loop.

    Args:
        portfolio: Portfolio to monitor
        max_cycles: Maximum cycles to run
        check_interval_seconds: Time between cycles

    Returns:
        MonitoringLoopResult
    """
    loop = MonitoringLoop(check_interval_seconds=check_interval_seconds)
    return await loop.start(portfolio, max_cycles=max_cycles)

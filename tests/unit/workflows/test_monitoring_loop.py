"""Unit tests for MonitoringLoop."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.application.workflows.monitoring_loop import (
    MonitoringAction,
    MonitoringCycleResult,
    MonitoringLoop,
    MonitoringLoopResult,
    MonitoringStatus,
    run_monitoring_loop,
)
from src.domain.models.enums import CorrelationGroup, Direction, PositionAction, System
from src.domain.models.market import NValue
from src.domain.models.portfolio import Portfolio
from src.domain.models.position import Position, PyramidLevel


def make_n_value(value: str = "20") -> NValue:
    """Create test NValue."""
    return NValue(value=Decimal(value), calculated_at=datetime.now())


def make_position(
    symbol: str = "/MGC",
    direction: Direction = Direction.LONG,
    contracts: int = 4,
    entry_price: str = "2800",
    stop_price: str = "2760",
) -> Position:
    """Create a test position."""
    pyramid_levels = tuple(
        PyramidLevel(
            level=i + 1,
            entry_price=Decimal(entry_price) + (i * 10),
            contracts=contracts // 2 if contracts >= 2 else 1,
            n_at_entry=Decimal("20"),
        )
        for i in range(2 if contracts >= 2 else 1)
    )

    return Position(
        symbol=symbol,
        direction=direction,
        system=System.S1,
        correlation_group=CorrelationGroup.METALS,
        pyramid_levels=pyramid_levels,
        current_stop=Decimal(stop_price),
        initial_entry_price=Decimal(entry_price),
        initial_n=make_n_value("20"),
    )


def make_portfolio(*positions: Position) -> Portfolio:
    """Create a portfolio from positions."""
    positions_dict = {pos.symbol: pos for pos in positions}
    return Portfolio(positions=positions_dict)


class TestMonitoringLoopCreation:
    """Tests for MonitoringLoop creation."""

    def test_create_loop(self):
        """Can create monitoring loop."""
        loop = MonitoringLoop()
        assert loop is not None
        assert loop.status == MonitoringStatus.STOPPED

    def test_create_loop_with_interval(self):
        """Can create loop with custom interval."""
        loop = MonitoringLoop(check_interval_seconds=30.0)
        assert loop._check_interval == 30.0


class TestMonitoringCycle:
    """Tests for individual monitoring cycles."""

    async def test_run_monitoring_cycle(self):
        """Can run a single monitoring cycle."""
        loop = MonitoringLoop()
        position = make_position()
        portfolio = make_portfolio(position)

        result = await loop.run_monitoring_cycle(portfolio)

        assert isinstance(result, MonitoringCycleResult)
        assert result.positions_checked == 1
        assert result.cycle_number == 1

    async def test_monitoring_cycle_empty_portfolio(self):
        """Monitoring cycle handles empty portfolio."""
        loop = MonitoringLoop()
        portfolio = Portfolio()

        result = await loop.run_monitoring_cycle(portfolio)

        assert result.positions_checked == 0
        assert len(result.actions_taken) == 0

    async def test_monitoring_cycle_multiple_positions(self):
        """Monitoring cycle checks all positions."""
        loop = MonitoringLoop()
        mgc = make_position(symbol="/MGC")
        mes = make_position(symbol="/MES")
        portfolio = make_portfolio(mgc, mes)

        result = await loop.run_monitoring_cycle(portfolio)

        assert result.positions_checked == 2


class TestMonitoringLoopExecution:
    """Tests for loop execution."""

    async def test_loop_runs_max_cycles(self):
        """Loop respects max_cycles limit."""
        loop = MonitoringLoop(check_interval_seconds=0.01)
        portfolio = make_portfolio(make_position())

        result = await loop.start(portfolio, max_cycles=3)

        assert result.cycles_completed == 3
        assert result.status == MonitoringStatus.STOPPED

    async def test_loop_can_be_stopped(self):
        """Loop can be stopped via callback."""
        loop = MonitoringLoop(check_interval_seconds=0.01)
        portfolio = make_portfolio(make_position())

        # Stop after first cycle via callback
        def stop_after_first(result):
            loop.stop()

        result = await loop.start(
            portfolio,
            max_cycles=100,
            on_cycle_complete=stop_after_first,
        )

        # Should stop after 1 cycle
        assert result.cycles_completed == 1

    async def test_loop_callback_called(self):
        """Callback is called after each cycle."""
        loop = MonitoringLoop(check_interval_seconds=0.01)
        portfolio = make_portfolio(make_position())

        callback_count = 0

        def on_cycle(result):
            nonlocal callback_count
            callback_count += 1

        await loop.start(portfolio, max_cycles=3, on_cycle_complete=on_cycle)

        assert callback_count == 3


class TestMonitoringStatus:
    """Tests for monitoring status."""

    def test_initial_status_stopped(self):
        """Initial status is stopped."""
        loop = MonitoringLoop()
        assert loop.status == MonitoringStatus.STOPPED
        assert loop.is_running is False

    async def test_status_while_running(self):
        """Status is running during execution."""
        loop = MonitoringLoop(check_interval_seconds=0.01)
        portfolio = make_portfolio(make_position())

        status_during = None

        def check_status(result):
            nonlocal status_during
            status_during = loop.status

        await loop.start(portfolio, max_cycles=1, on_cycle_complete=check_status)

        assert status_during == MonitoringStatus.RUNNING

    async def test_status_after_completion(self):
        """Status is stopped after completion."""
        loop = MonitoringLoop(check_interval_seconds=0.01)
        portfolio = make_portfolio(make_position())

        await loop.start(portfolio, max_cycles=1)

        assert loop.status == MonitoringStatus.STOPPED


class TestMonitoringAction:
    """Tests for MonitoringAction dataclass."""

    def test_action_creation(self):
        """Can create MonitoringAction."""
        action = MonitoringAction(
            symbol="/MGC",
            action=PositionAction.EXIT_STOP,
            executed_at=datetime.now(),
            success=True,
            details="Stop hit at 2760",
            exit_price=Decimal("2758"),
        )

        assert action.symbol == "/MGC"
        assert action.action == PositionAction.EXIT_STOP
        assert action.success is True

    def test_action_for_pyramid(self):
        """MonitoringAction tracks pyramid details."""
        action = MonitoringAction(
            symbol="/MGC",
            action=PositionAction.PYRAMID,
            executed_at=datetime.now(),
            success=True,
            pyramid_level=3,
            new_stop=Decimal("2780"),
        )

        assert action.pyramid_level == 3
        assert action.new_stop == Decimal("2780")


class TestMonitoringCycleResult:
    """Tests for MonitoringCycleResult dataclass."""

    def test_cycle_result_has_actions(self):
        """has_actions property works."""
        result_with_actions = MonitoringCycleResult(
            cycle_number=1,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            positions_checked=1,
            actions_taken=[
                MonitoringAction(
                    symbol="/MGC",
                    action=PositionAction.EXIT_STOP,
                    executed_at=datetime.now(),
                    success=True,
                )
            ],
        )
        assert result_with_actions.has_actions is True

        result_no_actions = MonitoringCycleResult(
            cycle_number=1,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            positions_checked=1,
        )
        assert result_no_actions.has_actions is False

    def test_cycle_result_counts_exits(self):
        """exits_executed property counts exits."""
        result = MonitoringCycleResult(
            cycle_number=1,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            positions_checked=2,
            actions_taken=[
                MonitoringAction(
                    symbol="/MGC",
                    action=PositionAction.EXIT_STOP,
                    executed_at=datetime.now(),
                    success=True,
                ),
                MonitoringAction(
                    symbol="/MES",
                    action=PositionAction.EXIT_BREAKOUT,
                    executed_at=datetime.now(),
                    success=True,
                ),
            ],
        )

        assert result.exits_executed == 2

    def test_cycle_result_counts_pyramids(self):
        """pyramids_executed property counts pyramids."""
        result = MonitoringCycleResult(
            cycle_number=1,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            positions_checked=1,
            actions_taken=[
                MonitoringAction(
                    symbol="/MGC",
                    action=PositionAction.PYRAMID,
                    executed_at=datetime.now(),
                    success=True,
                ),
            ],
        )

        assert result.pyramids_executed == 1


class TestMonitoringLoopResult:
    """Tests for MonitoringLoopResult dataclass."""

    def test_loop_result_creation(self):
        """Can create MonitoringLoopResult."""
        result = MonitoringLoopResult(
            status=MonitoringStatus.STOPPED,
            started_at=datetime.now(),
            stopped_at=datetime.now(),
            cycles_completed=5,
            total_actions=2,
        )

        assert result.cycles_completed == 5
        assert result.total_actions == 2


class TestConvenienceFunction:
    """Tests for run_monitoring_loop convenience function."""

    async def test_run_monitoring_loop_function(self):
        """Convenience function works."""
        position = make_position()
        portfolio = make_portfolio(position)

        result = await run_monitoring_loop(
            portfolio=portfolio,
            max_cycles=2,
            check_interval_seconds=0.01,
        )

        assert result.cycles_completed == 2
        assert result.status == MonitoringStatus.STOPPED


class TestMonitoringLoopStatus:
    """Tests for MonitoringStatus enum."""

    def test_status_values(self):
        """MonitoringStatus has expected values."""
        assert MonitoringStatus.RUNNING.value == "running"
        assert MonitoringStatus.PAUSED.value == "paused"
        assert MonitoringStatus.STOPPED.value == "stopped"
        assert MonitoringStatus.ERROR.value == "error"

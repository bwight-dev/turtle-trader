"""Unit tests for ModifyStopCommand."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.adapters.brokers.paper_broker import PaperBroker, PaperBrokerConfig
from src.application.commands.modify_stop import ModifyStopCommand, ModifyStopResult
from src.domain.models.enums import CorrelationGroup, Direction, System
from src.domain.models.market import NValue
from src.domain.models.order import StopModification
from src.domain.models.portfolio import Portfolio
from src.domain.models.position import Position, PyramidLevel


def make_n_value(value: str = "20") -> NValue:
    """Create test NValue."""
    return NValue(value=Decimal(value), calculated_at=datetime.now())


def make_position(
    symbol: str = "/MGC",
    direction: Direction = Direction.LONG,
    stop_price: str = "2760",
    entry_price: str = "2800",
    n_at_entry: str = "20",
    units: int = 2,
) -> Position:
    """Create a test position."""
    pyramid_levels = tuple(
        PyramidLevel(
            level=i + 1,
            entry_price=Decimal(entry_price) + (i * 10),
            contracts=2,
            n_at_entry=Decimal(n_at_entry),
        )
        for i in range(units)
    )

    return Position(
        symbol=symbol,
        direction=direction,
        system=System.S1,
        correlation_group=CorrelationGroup.METALS,
        pyramid_levels=pyramid_levels,
        current_stop=Decimal(stop_price),
        initial_entry_price=Decimal(entry_price),
        initial_n=make_n_value(n_at_entry),
    )


def make_portfolio(*positions: Position) -> Portfolio:
    """Create a portfolio from positions."""
    positions_dict = {pos.symbol: pos for pos in positions}
    return Portfolio(positions=positions_dict)


@pytest.fixture
def broker():
    """Create paper broker for testing."""
    broker = PaperBroker(
        config=PaperBrokerConfig(slippage_ticks=0),
        prices={"/MGC": Decimal("2800"), "/MES": Decimal("6000")},
    )
    # Inject a position for testing
    broker.inject_position(
        symbol="/MGC",
        quantity=4,
        average_cost=Decimal("2800"),
        stop_price=Decimal("2760"),
    )
    return broker


@pytest.fixture
def command(broker):
    """Create ModifyStopCommand."""
    return ModifyStopCommand(broker)


class TestModifyStop:
    """Tests for basic stop modification."""

    async def test_modify_stop_success(self, command, broker):
        """Successfully modify stop price."""
        await broker.connect()

        position = make_position(symbol="/MGC", stop_price="2760")
        portfolio = make_portfolio(position)

        new_portfolio, result = await command.execute(
            portfolio=portfolio,
            symbol="/MGC",
            new_stop=Decimal("2780"),
            reason="Test modification",
        )

        assert result.success is True
        assert result.old_stop == Decimal("2760")
        assert result.new_stop == Decimal("2780")
        assert result.reason == "Test modification"

        # Check portfolio updated
        updated_pos = new_portfolio.get_position("/MGC")
        assert updated_pos.current_stop == Decimal("2780")

    async def test_modify_stop_position_not_in_portfolio(self, command, broker):
        """Fail when position not in portfolio."""
        await broker.connect()

        portfolio = Portfolio()  # Empty portfolio

        new_portfolio, result = await command.execute(
            portfolio=portfolio,
            symbol="/MGC",
            new_stop=Decimal("2780"),
        )

        assert result.success is False
        assert "not found in portfolio" in result.reason

    async def test_modify_stop_position_not_at_broker(self, command, broker):
        """Fail when position not at broker."""
        await broker.connect()

        # Position in portfolio but not at broker
        position = make_position(symbol="/XYZ", stop_price="100")
        portfolio = make_portfolio(position)

        new_portfolio, result = await command.execute(
            portfolio=portfolio,
            symbol="/XYZ",
            new_stop=Decimal("110"),
        )

        assert result.success is False
        assert "no position" in result.error.lower()


class TestPyramidStopUpdate:
    """Tests for pyramid stop update."""

    async def test_pyramid_stop_update_long(self, command, broker):
        """Rule 12: Move all stops to 2N below newest entry (long)."""
        await broker.connect()

        position = make_position(
            symbol="/MGC",
            direction=Direction.LONG,
            stop_price="2760",  # Old stop
            entry_price="2800",
            n_at_entry="20",
        )
        portfolio = make_portfolio(position)

        # Pyramid at 2820, N=20, new stop should be 2820 - 40 = 2780
        new_portfolio, result = await command.execute_pyramid_stop_update(
            portfolio=portfolio,
            symbol="/MGC",
            newest_entry_price=Decimal("2820"),
            n_at_entry=Decimal("20"),
        )

        assert result.success is True
        assert result.new_stop == Decimal("2780")  # 2820 - 2*20

    async def test_pyramid_stop_update_short(self, command, broker):
        """Rule 12: Move all stops to 2N above newest entry (short)."""
        await broker.connect()

        # Set up short position at broker
        broker.reset()
        broker.inject_position(
            symbol="/MGC",
            quantity=-4,  # Short
            average_cost=Decimal("2800"),
            stop_price=Decimal("2840"),
        )

        position = make_position(
            symbol="/MGC",
            direction=Direction.SHORT,
            stop_price="2840",
            entry_price="2800",
            n_at_entry="20",
        )
        portfolio = make_portfolio(position)

        # Pyramid at 2780, N=20, new stop should be 2780 + 40 = 2820
        new_portfolio, result = await command.execute_pyramid_stop_update(
            portfolio=portfolio,
            symbol="/MGC",
            newest_entry_price=Decimal("2780"),
            n_at_entry=Decimal("20"),
        )

        assert result.success is True
        assert result.new_stop == Decimal("2820")  # 2780 + 2*20

    async def test_pyramid_stop_tightens_stop(self, command, broker):
        """Pyramiding should tighten the stop (move it closer to current price)."""
        await broker.connect()

        position = make_position(
            symbol="/MGC",
            direction=Direction.LONG,
            stop_price="2760",  # Initial stop
            entry_price="2800",
            n_at_entry="20",
        )
        portfolio = make_portfolio(position)

        # Pyramid at 2810 (½N above entry), new stop at 2810 - 40 = 2770
        new_portfolio, result = await command.execute_pyramid_stop_update(
            portfolio=portfolio,
            symbol="/MGC",
            newest_entry_price=Decimal("2810"),
            n_at_entry=Decimal("20"),
        )

        assert result.success is True
        assert result.new_stop == Decimal("2770")
        assert result.new_stop > result.old_stop  # Stop tightened


class TestModifyStopResult:
    """Tests for ModifyStopResult properties."""

    def test_result_has_timestamp(self):
        """Result includes execution timestamp."""
        result = ModifyStopResult(
            success=True,
            symbol="/MGC",
        )

        assert result.executed_at is not None
        assert isinstance(result.executed_at, datetime)

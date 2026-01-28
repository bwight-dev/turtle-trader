"""Unit tests for paper broker implementation."""

from decimal import Decimal

import pytest

from src.domain.interfaces.broker import (
    BrokerPosition,
    InsufficientFundsError,
    OpenOrder,
    PositionNotFoundError,
)
from src.domain.models.enums import Direction
from src.domain.models.order import BracketOrder
from src.adapters.brokers.paper_broker import PaperBroker, PaperBrokerConfig


@pytest.fixture
def broker():
    """Create a paper broker with default config."""
    return PaperBroker(
        config=PaperBrokerConfig(
            initial_equity=Decimal("100000"),
            commission_per_contract=Decimal("2.25"),
            slippage_ticks=0,  # No slippage for predictable tests
        ),
        prices={
            "/MGC": Decimal("2800"),
            "/MES": Decimal("6000"),
            "/SIL": Decimal("30"),
        },
    )


@pytest.fixture
def broker_with_slippage():
    """Create a paper broker with slippage enabled."""
    return PaperBroker(
        config=PaperBrokerConfig(
            initial_equity=Decimal("100000"),
            commission_per_contract=Decimal("2.25"),
            slippage_ticks=1,
            tick_size=Decimal("0.10"),
        ),
        prices={"/MGC": Decimal("2800")},
    )


# =============================================================================
# Connection Tests
# =============================================================================


class TestConnection:
    """Tests for broker connection."""

    async def test_connect(self, broker):
        """Broker connects successfully."""
        result = await broker.connect()
        assert result is True
        assert broker.is_connected is True

    async def test_disconnect(self, broker):
        """Broker disconnects."""
        await broker.connect()
        await broker.disconnect()
        assert broker.is_connected is False

    def test_broker_name(self, broker):
        """Broker identifies as paper."""
        assert broker.broker_name == "paper"


# =============================================================================
# Bracket Order Tests
# =============================================================================


class TestBracketOrder:
    """Tests for bracket order execution."""

    async def test_bracket_order_creates_position(self, broker):
        """Bracket order creates a position."""
        await broker.connect()

        order = BracketOrder(
            symbol="/MGC",
            direction=Direction.LONG,
            quantity=2,
            stop_price=Decimal("2760"),  # 2N stop
        )

        fill = await broker.place_bracket_order(order)

        assert fill.symbol == "/MGC"
        assert fill.direction == Direction.LONG
        assert fill.quantity == 2
        assert fill.fill_price == Decimal("2800")
        assert fill.commission == Decimal("4.50")  # 2 * 2.25

        # Verify position created
        pos = await broker.get_position("/MGC")
        assert pos is not None
        assert pos.quantity == 2
        assert pos.average_cost == Decimal("2800")

    async def test_bracket_order_creates_stop(self, broker):
        """Bracket order creates a stop order."""
        await broker.connect()

        order = BracketOrder(
            symbol="/MGC",
            direction=Direction.LONG,
            quantity=2,
            stop_price=Decimal("2760"),
        )

        await broker.place_bracket_order(order)

        # Verify stop order created
        orders = await broker.get_open_orders("/MGC")
        assert len(orders) == 1
        assert orders[0].order_type == "STP"
        assert orders[0].stop_price == Decimal("2760")
        assert orders[0].direction == Direction.SHORT  # Exit direction

    async def test_short_bracket_order(self, broker):
        """Short bracket order works correctly."""
        await broker.connect()

        order = BracketOrder(
            symbol="/MGC",
            direction=Direction.SHORT,
            quantity=2,
            stop_price=Decimal("2840"),  # 2N above entry
        )

        fill = await broker.place_bracket_order(order)

        assert fill.direction == Direction.SHORT

        pos = await broker.get_position("/MGC")
        assert pos.quantity == -2  # Negative for short

        orders = await broker.get_open_orders("/MGC")
        assert orders[0].direction == Direction.LONG  # Buy to cover

    async def test_bracket_order_with_limit(self, broker):
        """Bracket order respects limit price."""
        await broker.connect()

        order = BracketOrder(
            symbol="/MGC",
            direction=Direction.LONG,
            quantity=2,
            entry_price=Decimal("2795"),  # Limit price
            stop_price=Decimal("2755"),
        )

        fill = await broker.place_bracket_order(order)

        # Should fill at limit price (no slippage in this config)
        assert fill.fill_price == Decimal("2795")

    async def test_insufficient_funds_rejected(self, broker):
        """Order rejected when insufficient funds."""
        await broker.connect()

        # Try to buy way more than equity allows
        order = BracketOrder(
            symbol="/MGC",
            direction=Direction.LONG,
            quantity=1000,  # 1000 * 2800 = $2.8M
            stop_price=Decimal("2760"),
        )

        with pytest.raises(InsufficientFundsError):
            await broker.place_bracket_order(order)


# =============================================================================
# Market Order Tests
# =============================================================================


class TestMarketOrder:
    """Tests for market order execution."""

    async def test_market_order_long(self, broker):
        """Market order executes for long."""
        await broker.connect()

        fill = await broker.place_market_order(
            symbol="/MGC",
            direction=Direction.LONG,
            quantity=3,
        )

        assert fill.quantity == 3
        assert fill.fill_price == Decimal("2800")

    async def test_market_order_short(self, broker):
        """Market order executes for short."""
        await broker.connect()

        fill = await broker.place_market_order(
            symbol="/MGC",
            direction=Direction.SHORT,
            quantity=2,
        )

        pos = await broker.get_position("/MGC")
        assert pos.quantity == -2


# =============================================================================
# Close Position Tests
# =============================================================================


class TestClosePosition:
    """Tests for closing positions."""

    async def test_close_full_position(self, broker):
        """Close entire position."""
        await broker.connect()

        # Open position
        order = BracketOrder(
            symbol="/MGC",
            direction=Direction.LONG,
            quantity=2,
            stop_price=Decimal("2760"),
        )
        await broker.place_bracket_order(order)

        # Close it
        broker.set_price("/MGC", Decimal("2850"))  # Price went up
        fill = await broker.close_position("/MGC")

        assert fill.quantity == 2
        assert fill.fill_price == Decimal("2850")

        # Position should be gone
        pos = await broker.get_position("/MGC")
        assert pos is None

    async def test_close_partial_position(self, broker):
        """Close part of a position."""
        await broker.connect()

        order = BracketOrder(
            symbol="/MGC",
            direction=Direction.LONG,
            quantity=4,
            stop_price=Decimal("2760"),
        )
        await broker.place_bracket_order(order)

        fill = await broker.close_position("/MGC", quantity=2)

        assert fill.quantity == 2

        pos = await broker.get_position("/MGC")
        assert pos.quantity == 2  # 2 remaining

    async def test_close_nonexistent_position_raises(self, broker):
        """Closing nonexistent position raises error."""
        await broker.connect()

        with pytest.raises(PositionNotFoundError):
            await broker.close_position("/XYZ")

    async def test_close_calculates_pnl(self, broker):
        """Closing position calculates P&L."""
        await broker.connect()

        order = BracketOrder(
            symbol="/MGC",
            direction=Direction.LONG,
            quantity=2,
            stop_price=Decimal("2760"),
        )
        await broker.place_bracket_order(order)

        # Price went up 50 points
        broker.set_price("/MGC", Decimal("2850"))
        await broker.close_position("/MGC")

        # P&L = 50 * 2 = 100 (before commission)
        value = await broker.get_account_value()
        # Started with 100000, made 100 profit, paid 4.50 + 4.50 commission
        assert value == Decimal("100000") + Decimal("100") - Decimal("9.00")


# =============================================================================
# Stop Modification Tests
# =============================================================================


class TestStopModification:
    """Tests for modifying stop orders."""

    async def test_modify_stop(self, broker):
        """Modify stop price."""
        await broker.connect()

        order = BracketOrder(
            symbol="/MGC",
            direction=Direction.LONG,
            quantity=2,
            stop_price=Decimal("2760"),
        )
        await broker.place_bracket_order(order)

        mod = await broker.modify_stop("/MGC", Decimal("2780"))

        assert mod.old_stop == Decimal("2760")
        assert mod.new_stop == Decimal("2780")

        # Verify stop order updated
        orders = await broker.get_open_orders("/MGC")
        assert orders[0].stop_price == Decimal("2780")

    async def test_modify_stop_no_position_raises(self, broker):
        """Modifying stop with no position raises error."""
        await broker.connect()

        with pytest.raises(PositionNotFoundError):
            await broker.modify_stop("/XYZ", Decimal("100"))

    async def test_cancel_stop(self, broker):
        """Cancel stop order."""
        await broker.connect()

        order = BracketOrder(
            symbol="/MGC",
            direction=Direction.LONG,
            quantity=2,
            stop_price=Decimal("2760"),
        )
        await broker.place_bracket_order(order)

        result = await broker.cancel_stop("/MGC")

        assert result is True

        orders = await broker.get_open_orders("/MGC")
        assert len(orders) == 0


# =============================================================================
# Position Query Tests
# =============================================================================


class TestPositionQueries:
    """Tests for position queries."""

    async def test_get_positions_empty(self, broker):
        """Get positions returns empty when none."""
        await broker.connect()
        positions = await broker.get_positions()
        assert len(positions) == 0

    async def test_get_positions_multiple(self, broker):
        """Get positions returns all positions."""
        await broker.connect()

        await broker.place_bracket_order(
            BracketOrder(
                symbol="/MGC",
                direction=Direction.LONG,
                quantity=2,
                stop_price=Decimal("2760"),
            )
        )
        await broker.place_bracket_order(
            BracketOrder(
                symbol="/MES",
                direction=Direction.SHORT,
                quantity=1,
                stop_price=Decimal("6100"),
            )
        )

        positions = await broker.get_positions()

        assert len(positions) == 2
        symbols = {p.symbol for p in positions}
        assert symbols == {"/MGC", "/MES"}

    async def test_get_open_orders_all(self, broker):
        """Get all open orders."""
        await broker.connect()

        await broker.place_bracket_order(
            BracketOrder(
                symbol="/MGC",
                direction=Direction.LONG,
                quantity=2,
                stop_price=Decimal("2760"),
            )
        )
        await broker.place_bracket_order(
            BracketOrder(
                symbol="/MES",
                direction=Direction.LONG,
                quantity=1,
                stop_price=Decimal("5900"),
            )
        )

        orders = await broker.get_open_orders()
        assert len(orders) == 2

    async def test_get_open_orders_filtered(self, broker):
        """Get open orders filtered by symbol."""
        await broker.connect()

        await broker.place_bracket_order(
            BracketOrder(
                symbol="/MGC",
                direction=Direction.LONG,
                quantity=2,
                stop_price=Decimal("2760"),
            )
        )
        await broker.place_bracket_order(
            BracketOrder(
                symbol="/MES",
                direction=Direction.LONG,
                quantity=1,
                stop_price=Decimal("5900"),
            )
        )

        orders = await broker.get_open_orders("/MGC")
        assert len(orders) == 1
        assert orders[0].symbol == "/MGC"


# =============================================================================
# Account Tests
# =============================================================================


class TestAccount:
    """Tests for account information."""

    async def test_get_account_value(self, broker):
        """Get account value includes unrealized P&L."""
        await broker.connect()

        # Open position
        await broker.place_bracket_order(
            BracketOrder(
                symbol="/MGC",
                direction=Direction.LONG,
                quantity=2,
                stop_price=Decimal("2760"),
            )
        )

        # Price goes up
        broker.set_price("/MGC", Decimal("2810"))

        value = await broker.get_account_value()

        # Started with 100000
        # Paid 4.50 commission
        # Unrealized P&L = 10 * 2 = 20
        assert value == Decimal("100000") - Decimal("4.50") + Decimal("20")

    async def test_get_buying_power(self, broker):
        """Get buying power returns equity."""
        await broker.connect()
        power = await broker.get_buying_power()
        assert power == Decimal("100000")


# =============================================================================
# Slippage Tests
# =============================================================================


class TestSlippage:
    """Tests for slippage simulation."""

    async def test_slippage_on_long_entry(self, broker_with_slippage):
        """Long entry gets worse fill (higher price)."""
        broker = broker_with_slippage
        await broker.connect()

        order = BracketOrder(
            symbol="/MGC",
            direction=Direction.LONG,
            quantity=1,
            stop_price=Decimal("2760"),
        )

        fill = await broker.place_bracket_order(order)

        # 1 tick slippage = 0.10
        assert fill.fill_price == Decimal("2800.10")

    async def test_slippage_on_short_entry(self, broker_with_slippage):
        """Short entry gets worse fill (lower price)."""
        broker = broker_with_slippage
        await broker.connect()

        order = BracketOrder(
            symbol="/MGC",
            direction=Direction.SHORT,
            quantity=1,
            stop_price=Decimal("2840"),
        )

        fill = await broker.place_bracket_order(order)

        assert fill.fill_price == Decimal("2799.90")


# =============================================================================
# Pyramiding Tests
# =============================================================================


class TestPyramiding:
    """Tests for adding to positions (pyramiding)."""

    async def test_pyramid_updates_average_cost(self, broker):
        """Adding to position recalculates average cost."""
        await broker.connect()

        # First entry at 2800
        await broker.place_bracket_order(
            BracketOrder(
                symbol="/MGC",
                direction=Direction.LONG,
                quantity=2,
                stop_price=Decimal("2760"),
            )
        )

        # Pyramid at 2810
        broker.set_price("/MGC", Decimal("2810"))
        await broker.place_bracket_order(
            BracketOrder(
                symbol="/MGC",
                direction=Direction.LONG,
                quantity=2,
                stop_price=Decimal("2770"),  # Moved up
            )
        )

        pos = await broker.get_position("/MGC")

        assert pos.quantity == 4
        # Average = (2800*2 + 2810*2) / 4 = 2805
        assert pos.average_cost == Decimal("2805")

    async def test_pyramid_updates_stop(self, broker):
        """Pyramiding updates stop order."""
        await broker.connect()

        await broker.place_bracket_order(
            BracketOrder(
                symbol="/MGC",
                direction=Direction.LONG,
                quantity=2,
                stop_price=Decimal("2760"),
            )
        )

        broker.set_price("/MGC", Decimal("2810"))
        await broker.place_bracket_order(
            BracketOrder(
                symbol="/MGC",
                direction=Direction.LONG,
                quantity=2,
                stop_price=Decimal("2770"),  # New stop
            )
        )

        orders = await broker.get_open_orders("/MGC")
        assert orders[0].stop_price == Decimal("2770")


# =============================================================================
# Testing Helpers
# =============================================================================


class TestHelpers:
    """Tests for testing helper methods."""

    async def test_reset(self, broker):
        """Reset clears all state."""
        await broker.connect()

        await broker.place_bracket_order(
            BracketOrder(
                symbol="/MGC",
                direction=Direction.LONG,
                quantity=2,
                stop_price=Decimal("2760"),
            )
        )

        broker.reset()

        positions = await broker.get_positions()
        assert len(positions) == 0

        orders = await broker.get_open_orders()
        assert len(orders) == 0

        history = broker.get_order_history()
        assert len(history) == 0

    async def test_inject_position(self, broker):
        """Inject position directly for testing."""
        await broker.connect()

        broker.inject_position(
            symbol="/MGC",
            quantity=3,
            average_cost=Decimal("2750"),
            stop_price=Decimal("2710"),
        )

        pos = await broker.get_position("/MGC")
        assert pos.quantity == 3
        assert pos.average_cost == Decimal("2750")

        orders = await broker.get_open_orders("/MGC")
        assert orders[0].stop_price == Decimal("2710")

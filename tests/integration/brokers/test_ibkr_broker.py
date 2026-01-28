"""Integration tests for IBKR broker adapter.

These tests require TWS or Gateway to be running.
Run with: pytest tests/integration/brokers/ -v -m ibkr

Note: These tests may place/cancel orders on your paper account.
"""

from decimal import Decimal

import pytest

from src.adapters.brokers.ibkr_broker import IBKRBroker
from src.domain.interfaces.broker import BrokerPosition, OpenOrder, PositionNotFoundError
from src.domain.models.enums import Direction
from src.domain.models.order import BracketOrder


# Skip all tests if IBKR not available
pytestmark = pytest.mark.ibkr


@pytest.fixture
async def broker():
    """Create and connect IBKR broker (paper trading)."""
    broker = IBKRBroker(paper=True, client_id=99)  # Use unique client ID
    try:
        connected = await broker.connect()
        if not connected:
            pytest.skip("Could not connect to IBKR")
        yield broker
    finally:
        await broker.disconnect()


class TestConnection:
    """Tests for IBKR connection."""

    async def test_connects_to_paper(self, broker):
        """Can connect to paper trading."""
        assert broker.is_connected is True
        assert broker.broker_name == "ibkr"

    async def test_disconnect(self, broker):
        """Can disconnect cleanly."""
        await broker.disconnect()
        assert broker.is_connected is False


class TestAccountQueries:
    """Tests for account information queries."""

    async def test_get_account_value(self, broker):
        """Can get account value."""
        value = await broker.get_account_value()
        assert isinstance(value, Decimal)
        assert value > 0

    async def test_get_buying_power(self, broker):
        """Can get buying power."""
        power = await broker.get_buying_power()
        assert isinstance(power, Decimal)
        assert power > 0


class TestPositionQueries:
    """Tests for position queries."""

    async def test_get_positions(self, broker):
        """Can get positions list."""
        positions = await broker.get_positions()
        assert isinstance(positions, list)
        # Each position should be a BrokerPosition
        for pos in positions:
            assert isinstance(pos, BrokerPosition)

    async def test_get_position_nonexistent(self, broker):
        """Getting nonexistent position returns None."""
        pos = await broker.get_position("/NONEXISTENT")
        assert pos is None


class TestOrderQueries:
    """Tests for order queries."""

    async def test_get_open_orders(self, broker):
        """Can get open orders list."""
        orders = await broker.get_open_orders()
        assert isinstance(orders, list)
        for order in orders:
            assert isinstance(order, OpenOrder)


class TestStopModification:
    """Tests for stop order modification.

    Note: These tests only run if there's an existing position with a stop.
    """

    async def test_modify_stop_no_position_raises(self, broker):
        """Modifying stop with no position raises error."""
        with pytest.raises(PositionNotFoundError):
            await broker.modify_stop("/NONEXISTENT", Decimal("100"))


# =============================================================================
# Order Execution Tests (CAUTION: These place real orders!)
# =============================================================================


class TestOrderExecution:
    """Tests for order execution.

    WARNING: These tests place real orders on your paper account!
    They attempt to clean up after themselves, but verify manually.

    Only run these tests deliberately:
        pytest tests/integration/brokers/test_ibkr_broker.py::TestOrderExecution -v -m ibkr
    """

    @pytest.mark.skip(reason="Uncomment to test order placement on paper account")
    async def test_bracket_order_mes(self, broker):
        """Test bracket order on /MES (micro E-mini S&P).

        This test:
        1. Places a bracket order (buy 1 MES)
        2. Verifies the fill
        3. Closes the position
        """
        # Place order
        order = BracketOrder(
            symbol="/MES",
            direction=Direction.LONG,
            quantity=1,
            stop_price=Decimal("5000"),  # Far away stop
        )

        fill = await broker.place_bracket_order(order)

        assert fill.quantity == 1
        assert fill.fill_price > 0

        # Verify position exists
        pos = await broker.get_position("/MES")
        assert pos is not None
        assert pos.quantity == 1

        # Verify stop order exists
        orders = await broker.get_open_orders("/MES")
        stop_orders = [o for o in orders if o.order_type == "STP"]
        assert len(stop_orders) > 0

        # Clean up: close position
        close_fill = await broker.close_position("/MES")
        assert close_fill.quantity == 1

    @pytest.mark.skip(reason="Uncomment to test market order on paper account")
    async def test_market_order_and_close(self, broker):
        """Test simple market order and close."""
        # Buy
        fill = await broker.place_market_order(
            symbol="/MES",
            direction=Direction.LONG,
            quantity=1,
        )

        assert fill.quantity == 1

        # Close
        close_fill = await broker.close_position("/MES")
        assert close_fill.quantity == 1

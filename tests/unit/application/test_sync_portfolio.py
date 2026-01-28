"""Unit tests for SyncPortfolioQuery."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.adapters.brokers.paper_broker import PaperBroker, PaperBrokerConfig
from src.application.queries.sync_portfolio import (
    SyncPortfolioQuery,
    SyncResult,
    sync_portfolio,
)
from src.domain.models.enums import CorrelationGroup, Direction, System
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
) -> Position:
    """Create a test position."""
    pyramid_levels = tuple(
        PyramidLevel(
            level=i + 1,
            entry_price=Decimal("2800") + (i * 10),
            contracts=contracts // 2,  # Split across 2 levels
            n_at_entry=Decimal("20"),
        )
        for i in range(2)
    )

    return Position(
        symbol=symbol,
        direction=direction,
        system=System.S1,
        correlation_group=CorrelationGroup.METALS,
        pyramid_levels=pyramid_levels,
        current_stop=Decimal("2760"),
        initial_entry_price=Decimal("2800"),
        initial_n=make_n_value("20"),
    )


def make_portfolio(*positions: Position) -> Portfolio:
    """Create a portfolio from positions."""
    positions_dict = {pos.symbol: pos for pos in positions}
    return Portfolio(positions=positions_dict)


@pytest.fixture
def broker():
    """Create paper broker for testing."""
    return PaperBroker(
        config=PaperBrokerConfig(slippage_ticks=0),
        prices={
            "/MGC": Decimal("2800"),
            "/MES": Decimal("6000"),
            "/SIL": Decimal("30"),
        },
    )


@pytest.fixture
def query(broker):
    """Create SyncPortfolioQuery."""
    return SyncPortfolioQuery(broker)


class TestEmptySync:
    """Tests for syncing with empty portfolios."""

    async def test_sync_empty_broker_empty_portfolio(self, query, broker):
        """Sync empty broker with empty portfolio."""
        await broker.connect()

        portfolio, result = await query.execute(Portfolio())

        assert result.success is True
        assert result.added_count == 0
        assert result.updated_count == 0
        assert result.removed_count == 0
        assert len(portfolio.positions) == 0

    async def test_sync_broker_positions_to_empty_portfolio(self, query, broker):
        """Sync broker positions to empty portfolio adds them."""
        await broker.connect()

        # Add positions at broker
        broker.inject_position("/MGC", quantity=2, average_cost=Decimal("2800"))
        broker.inject_position("/MES", quantity=-1, average_cost=Decimal("6000"))

        portfolio, result = await query.execute(Portfolio())

        assert result.success is True
        assert result.added_count == 2
        assert len(portfolio.positions) == 2

        # Verify positions created correctly
        mgc = portfolio.get_position("/MGC")
        assert mgc is not None
        assert mgc.direction == Direction.LONG
        assert mgc.total_contracts == 2

        mes = portfolio.get_position("/MES")
        assert mes is not None
        assert mes.direction == Direction.SHORT
        assert mes.total_contracts == 1


class TestPositionSync:
    """Tests for position synchronization."""

    async def test_sync_matching_positions(self, query, broker):
        """Positions that match are unchanged."""
        await broker.connect()

        # Broker has position
        broker.inject_position("/MGC", quantity=4, average_cost=Decimal("2800"))

        # Internal portfolio has matching position
        position = make_position("/MGC", contracts=4)
        portfolio = make_portfolio(position)

        synced_portfolio, result = await query.execute(portfolio)

        assert result.success is True
        # Find the unchanged result
        unchanged = [r for r in result.positions_synced if r.action == "unchanged"]
        assert len(unchanged) == 1
        assert unchanged[0].symbol == "/MGC"

    async def test_sync_detects_quantity_mismatch(self, query, broker):
        """Sync detects when quantities don't match."""
        await broker.connect()

        # Broker has 2 contracts
        broker.inject_position("/MGC", quantity=2, average_cost=Decimal("2800"))

        # Internal has 4 contracts
        position = make_position("/MGC", contracts=4)
        portfolio = make_portfolio(position)

        synced_portfolio, result = await query.execute(portfolio)

        assert result.success is True
        updated = [r for r in result.positions_synced if r.action == "updated"]
        assert len(updated) == 1
        assert "qty" in updated[0].difference

    async def test_sync_detects_direction_mismatch(self, query, broker):
        """Sync detects when directions don't match."""
        await broker.connect()

        # Broker has short position
        broker.inject_position("/MGC", quantity=-2, average_cost=Decimal("2800"))

        # Internal has long position
        position = make_position("/MGC", direction=Direction.LONG, contracts=2)
        portfolio = make_portfolio(position)

        synced_portfolio, result = await query.execute(portfolio)

        assert result.success is True
        updated = [r for r in result.positions_synced if r.action == "updated"]
        assert len(updated) == 1
        assert "direction" in updated[0].difference


class TestClosedPositions:
    """Tests for handling closed positions."""

    async def test_sync_removes_closed_positions(self, query, broker):
        """Positions closed at broker are removed from portfolio."""
        await broker.connect()

        # No positions at broker

        # Internal portfolio has a position
        position = make_position("/MGC")
        portfolio = make_portfolio(position)

        synced_portfolio, result = await query.execute(portfolio)

        assert result.success is True
        assert result.removed_count == 1
        assert len(synced_portfolio.positions) == 0

        removed = [r for r in result.positions_synced if r.action == "removed"]
        assert len(removed) == 1
        assert removed[0].symbol == "/MGC"


class TestCorrelationGroups:
    """Tests for correlation group assignment."""

    async def test_assigns_known_correlation_group(self, query, broker):
        """Assigns correlation group for known symbols."""
        await broker.connect()

        broker.inject_position("/MGC", quantity=2, average_cost=Decimal("2800"))

        portfolio, result = await query.execute()

        mgc = portfolio.get_position("/MGC")
        assert mgc.correlation_group == CorrelationGroup.METALS

    async def test_assigns_equity_group(self, query, broker):
        """Assigns equity correlation group."""
        await broker.connect()

        broker.inject_position("/MES", quantity=1, average_cost=Decimal("6000"))

        portfolio, result = await query.execute()

        mes = portfolio.get_position("/MES")
        assert mes.correlation_group == CorrelationGroup.EQUITY_US


class TestSyncResult:
    """Tests for SyncResult properties."""

    async def test_sync_result_counts(self, query, broker):
        """SyncResult tracks counts correctly."""
        await broker.connect()

        # Add 2 new positions at broker
        broker.inject_position("/MGC", quantity=2, average_cost=Decimal("2800"))
        broker.inject_position("/MES", quantity=1, average_cost=Decimal("6000"))

        # Internal has 1 position that will be removed
        position = make_position("/SIL")
        portfolio = make_portfolio(position)

        synced_portfolio, result = await query.execute(portfolio)

        assert result.added_count == 2
        assert result.removed_count == 1
        assert result.success is True


class TestConvenienceFunction:
    """Tests for sync_portfolio convenience function."""

    async def test_sync_portfolio_function(self, broker):
        """sync_portfolio convenience function works."""
        await broker.connect()

        broker.inject_position("/MGC", quantity=2, average_cost=Decimal("2800"))

        portfolio, result = await sync_portfolio(broker)

        assert result.success is True
        assert len(portfolio.positions) == 1


class TestErrorHandling:
    """Tests for error handling."""

    async def test_sync_handles_broker_error(self, broker):
        """Sync handles broker connection errors gracefully."""
        # Don't connect - broker returns empty positions (not an error for paper broker)
        # This test verifies sync works even with unconnected broker
        query = SyncPortfolioQuery(broker)

        portfolio, result = await query.execute()

        # Paper broker returns empty list when not connected (no error)
        # Real broker would raise - this tests graceful handling
        assert result.success is True
        assert len(portfolio.positions) == 0

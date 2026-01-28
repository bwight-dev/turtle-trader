"""Unit tests for ReconcileAccountQuery."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.adapters.brokers.paper_broker import PaperBroker, PaperBrokerConfig
from src.application.queries.reconcile_account import (
    ReconcileAccountQuery,
    ReconciliationResult,
    reconcile_account,
)
from src.domain.interfaces.broker import BrokerPosition
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
    """Create ReconcileAccountQuery."""
    return ReconcileAccountQuery(broker)


class TestReconciliationMatches:
    """Tests for matching reconciliation."""

    async def test_reconciliation_empty_both(self, query, broker):
        """Empty portfolio and no broker positions match."""
        await broker.connect()

        result = await query.execute(Portfolio())

        assert result.matches is True
        assert result.positions_matched == 0
        assert len(result.position_mismatches) == 0

    async def test_reconciliation_matches(self, query, broker):
        """Matching positions reconcile successfully."""
        await broker.connect()

        # Set up matching position
        broker.inject_position("/MGC", quantity=4, average_cost=Decimal("2800"))

        position = make_position("/MGC", contracts=4)
        portfolio = make_portfolio(position)

        result = await query.execute(portfolio)

        assert result.matches is True
        assert result.positions_matched == 1
        assert len(result.position_mismatches) == 0

    async def test_reconciliation_multiple_positions_match(self, query, broker):
        """Multiple matching positions reconcile successfully."""
        await broker.connect()

        # Set up matching positions
        broker.inject_position("/MGC", quantity=4, average_cost=Decimal("2800"))
        broker.inject_position("/MES", quantity=2, average_cost=Decimal("6000"))

        mgc = make_position("/MGC", contracts=4)
        mes = make_position("/MES", contracts=2)
        portfolio = make_portfolio(mgc, mes)

        result = await query.execute(portfolio)

        assert result.matches is True
        assert result.positions_matched == 2


class TestReconciliationMismatches:
    """Tests for mismatch detection."""

    async def test_reconciliation_detects_mismatch(self, query, broker):
        """Detects quantity mismatch."""
        await broker.connect()

        # Broker has 2 contracts
        broker.inject_position("/MGC", quantity=2, average_cost=Decimal("2800"))

        # Internal has different quantity (8 contracts via pyramid levels)
        position = make_position("/MGC", contracts=8)
        portfolio = make_portfolio(position)

        result = await query.execute(portfolio)

        assert result.matches is False
        assert len(result.position_mismatches) == 1
        assert result.position_mismatches[0].mismatch_type == "quantity"
        assert result.position_mismatches[0].internal_quantity == 8
        assert result.position_mismatches[0].broker_quantity == 2

    async def test_reconciliation_detects_direction_mismatch(self, query, broker):
        """Detects direction mismatch."""
        await broker.connect()

        # Broker has short position
        broker.inject_position("/MGC", quantity=-4, average_cost=Decimal("2800"))

        # Internal has long position
        position = make_position("/MGC", direction=Direction.LONG, contracts=4)
        portfolio = make_portfolio(position)

        result = await query.execute(portfolio)

        assert result.matches is False
        direction_mismatches = [
            m for m in result.position_mismatches if m.mismatch_type == "direction"
        ]
        assert len(direction_mismatches) == 1
        assert direction_mismatches[0].internal_direction == Direction.LONG
        assert direction_mismatches[0].broker_direction == Direction.SHORT

    async def test_reconciliation_detects_missing_at_broker(self, query, broker):
        """Detects position in portfolio but not at broker."""
        await broker.connect()

        # No positions at broker

        # Internal has a position
        position = make_position("/MGC")
        portfolio = make_portfolio(position)

        result = await query.execute(portfolio)

        assert result.matches is False
        assert len(result.position_mismatches) == 1
        assert result.position_mismatches[0].mismatch_type == "missing_at_broker"
        assert result.position_mismatches[0].symbol == "/MGC"

    async def test_reconciliation_detects_missing_internal(self, query, broker):
        """Detects position at broker but not in portfolio."""
        await broker.connect()

        # Broker has position
        broker.inject_position("/MGC", quantity=4, average_cost=Decimal("2800"))

        # Internal portfolio is empty
        portfolio = Portfolio()

        result = await query.execute(portfolio)

        assert result.matches is False
        assert len(result.position_mismatches) == 1
        assert result.position_mismatches[0].mismatch_type == "missing_internal"
        assert result.position_mismatches[0].symbol == "/MGC"
        assert result.position_mismatches[0].broker_quantity == 4


class TestCompareMethod:
    """Tests for the compare() convenience method."""

    async def test_compare_with_provided_positions(self, query, broker):
        """Compare works with pre-fetched broker positions."""
        # Create broker positions directly (not from broker)
        broker_positions = [
            BrokerPosition(
                symbol="/MGC",
                quantity=4,
                average_cost=Decimal("2800"),
                market_value=Decimal("11200"),
                unrealized_pnl=Decimal("0"),
            )
        ]

        position = make_position("/MGC", contracts=4)
        portfolio = make_portfolio(position)

        result = await query.compare(portfolio, broker_positions)

        assert result.matches is True
        assert result.positions_matched == 1

    async def test_compare_detects_mismatch(self, query, broker):
        """Compare detects mismatches with provided positions."""
        broker_positions = [
            BrokerPosition(
                symbol="/MGC",
                quantity=2,  # Different from internal
                average_cost=Decimal("2800"),
                market_value=Decimal("5600"),
                unrealized_pnl=Decimal("0"),
            )
        ]

        position = make_position("/MGC", contracts=4)
        portfolio = make_portfolio(position)

        result = await query.compare(portfolio, broker_positions)

        assert result.matches is False
        assert result.position_mismatches[0].mismatch_type == "quantity"


class TestEquityReconciliation:
    """Tests for account equity reconciliation."""

    async def test_equity_within_tolerance(self, query, broker):
        """Equity within tolerance passes."""
        await broker.connect()
        broker.set_account_value(Decimal("100000"))

        portfolio = Portfolio()

        result = await query.execute(
            portfolio,
            expected_equity=Decimal("100000"),
            equity_tolerance=Decimal("0.01"),
        )

        assert result.matches is True
        assert result.broker_equity == Decimal("100000")
        assert len(result.account_mismatches) == 0

    async def test_equity_exceeds_tolerance(self, query, broker):
        """Equity exceeding tolerance is detected."""
        await broker.connect()
        broker.set_account_value(Decimal("100000"))

        portfolio = Portfolio()

        # Expected 90000, actual 100000 (11% difference)
        result = await query.execute(
            portfolio,
            expected_equity=Decimal("90000"),
            equity_tolerance=Decimal("0.01"),  # 1% tolerance
        )

        assert result.matches is False
        assert len(result.account_mismatches) == 1
        assert result.account_mismatches[0].field == "equity"


class TestReconciliationResult:
    """Tests for ReconciliationResult properties."""

    def test_summary_generation_matching(self):
        """Summary for matching result."""
        result = ReconciliationResult(
            matches=True,
            positions_matched=3,
            broker_equity=Decimal("100000"),
        )

        summary = result.summary()
        assert "All 3 positions match" in summary
        assert "$100,000.00" in summary

    def test_summary_generation_with_mismatches(self):
        """Summary includes mismatch details."""
        from src.application.queries.reconcile_account import PositionMismatch

        result = ReconciliationResult(
            matches=False,
            position_mismatches=[
                PositionMismatch(
                    symbol="/MGC",
                    mismatch_type="quantity",
                    internal_quantity=4,
                    broker_quantity=2,
                    details="Internal has 4, broker has 2",
                )
            ],
        )

        summary = result.summary()
        assert "/MGC" in summary
        assert "quantity" in summary

    def test_has_position_mismatches_property(self):
        """has_position_mismatches property works."""
        from src.application.queries.reconcile_account import PositionMismatch

        result_match = ReconciliationResult(matches=True)
        assert result_match.has_position_mismatches is False

        result_mismatch = ReconciliationResult(
            matches=False,
            position_mismatches=[
                PositionMismatch(symbol="/MGC", mismatch_type="quantity")
            ],
        )
        assert result_mismatch.has_position_mismatches is True


class TestConvenienceFunction:
    """Tests for reconcile_account convenience function."""

    async def test_reconcile_account_function(self, broker):
        """reconcile_account convenience function works."""
        await broker.connect()

        broker.inject_position("/MGC", quantity=4, average_cost=Decimal("2800"))

        position = make_position("/MGC", contracts=4)
        portfolio = make_portfolio(position)

        result = await reconcile_account(broker, portfolio)

        assert result.matches is True
        assert result.positions_matched == 1

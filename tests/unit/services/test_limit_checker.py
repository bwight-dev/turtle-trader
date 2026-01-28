"""Unit tests for position limit checker service."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.domain.models.enums import CorrelationGroup, Direction, System
from src.domain.models.market import NValue
from src.domain.models.portfolio import Portfolio
from src.domain.models.position import Position, PyramidLevel
from src.domain.services.limit_checker import (
    LimitChecker,
    LimitCheckResult,
    LimitViolation,
)


def make_n_value(value: str = "20") -> NValue:
    """Create test NValue."""
    return NValue(value=Decimal(value), calculated_at=datetime.now())


def make_position(
    symbol: str,
    units: int = 1,
    contracts_per_unit: int = 2,
    direction: Direction = Direction.LONG,
    system: System = System.S1,
    correlation_group: CorrelationGroup | None = None,
) -> Position:
    """Create a test position with specified units."""
    pyramid_levels = tuple(
        PyramidLevel(
            level=i + 1,
            entry_price=Decimal("2800") + (i * 10),
            contracts=contracts_per_unit,
            n_at_entry=Decimal("20"),
        )
        for i in range(units)
    )

    return Position(
        symbol=symbol,
        direction=direction,
        system=system,
        correlation_group=correlation_group,
        pyramid_levels=pyramid_levels,
        current_stop=Decimal("2760"),
        initial_entry_price=Decimal("2800"),
        initial_n=make_n_value(),
    )


def make_portfolio(*positions: Position) -> Portfolio:
    """Create a portfolio from positions."""
    positions_dict = {pos.symbol: pos for pos in positions}
    return Portfolio(positions=positions_dict)


@pytest.fixture
def checker():
    """Create a limit checker with default limits."""
    return LimitChecker()


class TestPerMarketLimit:
    """Tests for 4 units per market limit."""

    def test_allows_first_unit(self, checker):
        """Can add first unit to empty market."""
        portfolio = Portfolio()

        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/MGC",
            units_to_add=1,
        )

        assert result.allowed is True
        assert result.violation == LimitViolation.NONE
        assert result.current_market_units == 0

    def test_allows_up_to_4_units(self, checker):
        """Can add units up to max 4 per market."""
        # Start with 3 units
        pos = make_position("/MGC", units=3, correlation_group=CorrelationGroup.METALS)
        portfolio = make_portfolio(pos)

        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/MGC",
            units_to_add=1,
            correlation_group=CorrelationGroup.METALS,
        )

        assert result.allowed is True
        assert result.current_market_units == 3

    def test_blocks_5th_unit(self, checker):
        """Blocks adding 5th unit to a market."""
        # Already at 4 units
        pos = make_position("/MGC", units=4, correlation_group=CorrelationGroup.METALS)
        portfolio = make_portfolio(pos)

        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/MGC",
            units_to_add=1,
            correlation_group=CorrelationGroup.METALS,
        )

        assert result.allowed is False
        assert result.violation == LimitViolation.PER_MARKET
        assert "4 units" in result.reason
        assert result.would_exceed_market is True

    def test_blocks_multiple_units_exceeding_limit(self, checker):
        """Blocks adding multiple units that would exceed limit."""
        # Start with 2 units
        pos = make_position("/MGC", units=2, correlation_group=CorrelationGroup.METALS)
        portfolio = make_portfolio(pos)

        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/MGC",
            units_to_add=3,  # Would go to 5
            correlation_group=CorrelationGroup.METALS,
        )

        assert result.allowed is False
        assert result.violation == LimitViolation.PER_MARKET


class TestCorrelationLimit:
    """Tests for 6 units in correlated markets limit."""

    def test_allows_first_in_group(self, checker):
        """Can add first unit to a correlation group."""
        portfolio = Portfolio()

        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/MGC",
            units_to_add=1,
            correlation_group=CorrelationGroup.METALS,
        )

        assert result.allowed is True
        assert result.current_group_units == 0

    def test_counts_across_correlated_markets(self, checker):
        """Counts units across all markets in same group."""
        # MGC at 4 units, SIL at 2 units = 6 metals
        mgc = make_position("/MGC", units=4, correlation_group=CorrelationGroup.METALS)
        sil = make_position("/SIL", units=2, correlation_group=CorrelationGroup.METALS)
        portfolio = make_portfolio(mgc, sil)

        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/HG",  # New market in metals group
            units_to_add=1,
            correlation_group=CorrelationGroup.METALS,
        )

        assert result.allowed is False
        assert result.violation == LimitViolation.CORRELATED
        assert result.current_group_units == 6
        assert "metals" in result.reason.lower()
        assert result.would_exceed_correlated is True

    def test_allows_different_group(self, checker):
        """Can add to different correlation group even when one is at limit."""
        # Metals at 6 units
        mgc = make_position("/MGC", units=4, correlation_group=CorrelationGroup.METALS)
        sil = make_position("/SIL", units=2, correlation_group=CorrelationGroup.METALS)
        portfolio = make_portfolio(mgc, sil)

        # Can add equities
        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/MES",
            units_to_add=1,
            correlation_group=CorrelationGroup.EQUITY_US,
        )

        assert result.allowed is True

    def test_your_current_portfolio(self, checker):
        """Test with reference portfolio: 10/12 total, metals 6/6."""
        # MGC=4 + SIL=2 = 6 metals, M2K=4 equities = 10 total
        mgc = make_position("/MGC", units=4, correlation_group=CorrelationGroup.METALS)
        sil = make_position("/SIL", units=2, correlation_group=CorrelationGroup.METALS)
        m2k = make_position("/M2K", units=4, correlation_group=CorrelationGroup.EQUITY_US)
        portfolio = make_portfolio(mgc, sil, m2k)

        # Cannot add metals
        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/HG",
            units_to_add=1,
            correlation_group=CorrelationGroup.METALS,
        )
        assert result.allowed is False
        assert result.violation == LimitViolation.CORRELATED

        # Can add equities (4/6)
        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/MES",
            units_to_add=1,
            correlation_group=CorrelationGroup.EQUITY_US,
        )
        assert result.allowed is True


class TestTotalLimit:
    """Tests for 12 units total portfolio limit."""

    def test_allows_up_to_12_units(self, checker):
        """Can add units up to 12 total."""
        # 11 units across different markets
        mgc = make_position("/MGC", units=4, correlation_group=CorrelationGroup.METALS)
        sil = make_position("/SIL", units=2, correlation_group=CorrelationGroup.METALS)
        m2k = make_position("/M2K", units=4, correlation_group=CorrelationGroup.EQUITY_US)
        mes = make_position("/MES", units=1, correlation_group=CorrelationGroup.EQUITY_US)
        portfolio = make_portfolio(mgc, sil, m2k, mes)

        assert portfolio.total_units == 11

        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/ZC",  # Grains
            units_to_add=1,
            correlation_group=CorrelationGroup.GRAINS,
        )

        assert result.allowed is True
        assert result.current_total_units == 11

    def test_blocks_13th_unit(self, checker):
        """Blocks adding unit that would exceed 12 total."""
        # Already at 12 units
        mgc = make_position("/MGC", units=4, correlation_group=CorrelationGroup.METALS)
        sil = make_position("/SIL", units=2, correlation_group=CorrelationGroup.METALS)
        m2k = make_position("/M2K", units=4, correlation_group=CorrelationGroup.EQUITY_US)
        mes = make_position("/MES", units=2, correlation_group=CorrelationGroup.EQUITY_US)
        portfolio = make_portfolio(mgc, sil, m2k, mes)

        assert portfolio.total_units == 12

        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/ZC",
            units_to_add=1,
            correlation_group=CorrelationGroup.GRAINS,
        )

        assert result.allowed is False
        assert result.violation == LimitViolation.TOTAL
        assert "12" in result.reason
        assert result.would_exceed_total is True

    def test_total_limit_checked_before_correlated(self, checker):
        """Total limit is checked before correlation limit."""
        # 12 units total, metals at 4 (under correlated limit)
        mgc = make_position("/MGC", units=4, correlation_group=CorrelationGroup.METALS)
        m2k = make_position("/M2K", units=4, correlation_group=CorrelationGroup.EQUITY_US)
        mes = make_position("/MES", units=4, correlation_group=CorrelationGroup.EQUITY_US)
        portfolio = make_portfolio(mgc, m2k, mes)

        assert portfolio.total_units == 12
        assert portfolio.units_in_group(CorrelationGroup.METALS) == 4

        # Adding metals would violate total (12 -> 13) before correlation (4 -> 5)
        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/SIL",
            units_to_add=1,
            correlation_group=CorrelationGroup.METALS,
        )

        assert result.allowed is False
        assert result.violation == LimitViolation.TOTAL  # Not CORRELATED


class TestCanPyramid:
    """Tests for can_pyramid convenience method."""

    def test_can_pyramid_empty_market(self, checker):
        """Can pyramid into new market."""
        portfolio = Portfolio()

        result = checker.can_pyramid(
            portfolio=portfolio,
            symbol="/MGC",
            correlation_group=CorrelationGroup.METALS,
        )

        assert result.allowed is True
        assert result.units_requested == 1

    def test_cannot_pyramid_at_market_limit(self, checker):
        """Cannot pyramid when at 4 units."""
        pos = make_position("/MGC", units=4, correlation_group=CorrelationGroup.METALS)
        portfolio = make_portfolio(pos)

        result = checker.can_pyramid(
            portfolio=portfolio,
            symbol="/MGC",
            correlation_group=CorrelationGroup.METALS,
        )

        assert result.allowed is False
        assert result.violation == LimitViolation.PER_MARKET


class TestLimitCheckResultProperties:
    """Tests for LimitCheckResult computed properties."""

    def test_units_available_in_market(self, checker):
        """units_available_in_market property."""
        pos = make_position("/MGC", units=2, correlation_group=CorrelationGroup.METALS)
        portfolio = make_portfolio(pos)

        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/MGC",
            units_to_add=1,
            correlation_group=CorrelationGroup.METALS,
        )

        assert result.units_available_in_market == 2  # 4 - 2

    def test_units_available_in_group(self, checker):
        """units_available_in_group property."""
        mgc = make_position("/MGC", units=4, correlation_group=CorrelationGroup.METALS)
        portfolio = make_portfolio(mgc)

        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/SIL",
            units_to_add=1,
            correlation_group=CorrelationGroup.METALS,
        )

        assert result.units_available_in_group == 2  # 6 - 4

    def test_units_available_total(self, checker):
        """units_available_total property."""
        mgc = make_position("/MGC", units=4, correlation_group=CorrelationGroup.METALS)
        m2k = make_position("/M2K", units=4, correlation_group=CorrelationGroup.EQUITY_US)
        portfolio = make_portfolio(mgc, m2k)

        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/ZC",
            units_to_add=1,
            correlation_group=CorrelationGroup.GRAINS,
        )

        assert result.units_available_total == 4  # 12 - 8


class TestPortfolioStatus:
    """Tests for check_portfolio_status method."""

    def test_empty_portfolio_status(self, checker):
        """Status of empty portfolio."""
        portfolio = Portfolio()

        status = checker.check_portfolio_status(portfolio)

        assert status["total"]["current"] == 0
        assert status["total"]["max"] == 12
        assert status["total"]["at_limit"] is False
        assert status["groups"] == {}

    def test_portfolio_status_at_limits(self, checker):
        """Status shows which limits are at capacity."""
        # Metals at 6, equities at 6 = 12 total
        mgc = make_position("/MGC", units=4, correlation_group=CorrelationGroup.METALS)
        sil = make_position("/SIL", units=2, correlation_group=CorrelationGroup.METALS)
        m2k = make_position("/M2K", units=4, correlation_group=CorrelationGroup.EQUITY_US)
        mes = make_position("/MES", units=2, correlation_group=CorrelationGroup.EQUITY_US)
        portfolio = make_portfolio(mgc, sil, m2k, mes)

        status = checker.check_portfolio_status(portfolio)

        assert status["total"]["current"] == 12
        assert status["total"]["at_limit"] is True

        assert status["groups"]["metals"]["current"] == 6
        assert status["groups"]["metals"]["at_limit"] is True

        assert status["groups"]["equity_us"]["current"] == 6
        assert status["groups"]["equity_us"]["at_limit"] is True


class TestCustomLimits:
    """Tests for LimitChecker with custom limits."""

    def test_custom_per_market_limit(self):
        """Can configure custom per-market limit."""
        checker = LimitChecker(max_per_market=2)  # Stricter limit

        pos = make_position("/MGC", units=2)
        portfolio = make_portfolio(pos)

        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/MGC",
            units_to_add=1,
        )

        assert result.allowed is False
        assert result.max_per_market == 2

    def test_custom_total_limit(self):
        """Can configure custom total limit."""
        checker = LimitChecker(max_total=6)  # Stricter limit

        mgc = make_position("/MGC", units=4, correlation_group=CorrelationGroup.METALS)
        m2k = make_position("/M2K", units=2, correlation_group=CorrelationGroup.EQUITY_US)
        portfolio = make_portfolio(mgc, m2k)

        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/ZC",
            units_to_add=1,
        )

        assert result.allowed is False
        assert result.violation == LimitViolation.TOTAL
        assert result.max_total == 6


class TestNoCorrelationGroup:
    """Tests when no correlation group is specified."""

    def test_skips_correlation_check_when_none(self, checker):
        """When no group specified, correlation check is skipped."""
        # Put lots in a group
        mgc = make_position("/MGC", units=4, correlation_group=CorrelationGroup.METALS)
        sil = make_position("/SIL", units=2, correlation_group=CorrelationGroup.METALS)
        portfolio = make_portfolio(mgc, sil)

        # Add position without specifying group
        result = checker.can_add_position(
            portfolio=portfolio,
            symbol="/XYZ",
            units_to_add=1,
            correlation_group=None,  # No group
        )

        # Should be allowed (only checks total limit)
        assert result.allowed is True
        assert result.current_group_units == 0

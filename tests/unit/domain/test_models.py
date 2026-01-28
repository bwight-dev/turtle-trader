"""Unit tests for domain models."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.domain.models import (
    Bar,
    CorrelationGroup,
    Direction,
    DonchianChannel,
    LimitCheckResult,
    NValue,
    Portfolio,
    Position,
    PyramidLevel,
    Signal,
    System,
    Trade,
)


class TestBar:
    """Tests for Bar model."""

    def test_valid_bar(self):
        """Test creating a valid bar."""
        bar = Bar(
            symbol="/MGC",
            date=date.today(),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("95"),
            close=Decimal("102"),
            volume=1000,
        )
        assert bar.symbol == "/MGC"
        assert bar.high >= bar.low

    def test_bar_high_less_than_low_fails(self):
        """Test that high < low raises validation error."""
        with pytest.raises(ValidationError):
            Bar(
                symbol="/MGC",
                date=date.today(),
                open=Decimal("100"),
                high=Decimal("90"),  # Invalid: less than low
                low=Decimal("95"),
                close=Decimal("98"),
            )

    def test_bar_is_frozen(self):
        """Test that Bar is immutable."""
        bar = Bar(
            symbol="/MGC",
            date=date.today(),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("95"),
            close=Decimal("102"),
        )
        with pytest.raises(ValidationError):
            bar.close = Decimal("103")


class TestNValue:
    """Tests for NValue model."""

    def test_nvalue_to_dollars(self):
        """Test converting N to dollar volatility."""
        n = NValue(value=Decimal("20"), calculated_at=datetime.now())
        dollar_risk = n.to_dollars(Decimal("10"))
        assert dollar_risk == Decimal("200")

    def test_nvalue_positive_required(self):
        """Test that N must be positive."""
        with pytest.raises(ValidationError):
            NValue(value=Decimal("0"), calculated_at=datetime.now())


class TestPosition:
    """Tests for Position model."""

    @pytest.fixture
    def base_position(self):
        """Create a base position for testing."""
        n = NValue(value=Decimal("20"), calculated_at=datetime.now(), symbol="/MGC")
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("2800"),
            contracts=2,
            n_at_entry=Decimal("20"),
        )
        return Position(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            correlation_group=CorrelationGroup.METALS,
            pyramid_levels=(level,),
            current_stop=Decimal("2760"),
            initial_entry_price=Decimal("2800"),
            initial_n=n,
        )

    def test_position_total_contracts(self, base_position):
        """Test total contracts calculation."""
        assert base_position.total_contracts == 2
        assert base_position.total_units == 1

    def test_position_next_pyramid_trigger_long(self, base_position):
        """Test next pyramid trigger for long position.

        Rule 11: Pyramid at +½N intervals.
        """
        # ½N = 10, so trigger at 2810
        assert base_position.next_pyramid_trigger == Decimal("2810")

    def test_position_can_pyramid(self, base_position):
        """Test pyramid capacity check."""
        assert base_position.can_pyramid is True

    def test_position_stop_hit_long(self, base_position):
        """Test stop hit detection for long."""
        assert base_position.is_stop_hit(Decimal("2760")) is True  # At stop
        assert base_position.is_stop_hit(Decimal("2750")) is True  # Below stop
        assert base_position.is_stop_hit(Decimal("2800")) is False  # Above stop

    def test_position_add_pyramid(self, base_position):
        """Test adding a pyramid level."""
        new_pos = base_position.add_pyramid(
            entry_price=Decimal("2820"),
            contracts=2,
            n_at_entry=Decimal("20"),
            new_stop=Decimal("2780"),  # 2N below new entry
        )

        assert new_pos.total_units == 2
        assert new_pos.total_contracts == 4
        assert new_pos.current_stop == Decimal("2780")

    def test_position_max_units_enforced(self, base_position):
        """Test that max 4 units is enforced."""
        pos = base_position
        for i in range(3):  # Add 3 more to reach 4
            pos = pos.add_pyramid(
                entry_price=Decimal("2820") + i * 10,
                contracts=2,
                n_at_entry=Decimal("20"),
                new_stop=Decimal("2800"),
            )

        assert pos.total_units == 4
        assert pos.can_pyramid is False

        with pytest.raises(ValueError, match="max 4 units"):
            pos.add_pyramid(
                entry_price=Decimal("2850"),
                contracts=2,
                n_at_entry=Decimal("20"),
                new_stop=Decimal("2810"),
            )


class TestPortfolio:
    """Tests for Portfolio aggregate root."""

    @pytest.fixture
    def sample_position(self):
        """Create a sample position."""
        n = NValue(value=Decimal("20"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("2800"),
            contracts=2,
            n_at_entry=Decimal("20"),
        )
        return Position(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            correlation_group=CorrelationGroup.METALS,
            pyramid_levels=(level,),
            current_stop=Decimal("2760"),
            initial_entry_price=Decimal("2800"),
            initial_n=n,
        )

    def test_empty_portfolio(self):
        """Test empty portfolio."""
        portfolio = Portfolio()
        assert portfolio.total_units == 0
        assert portfolio.total_contracts == 0

    def test_add_position(self, sample_position):
        """Test adding a position."""
        portfolio = Portfolio()
        new_portfolio = portfolio.add_position(sample_position)

        assert new_portfolio.total_units == 1
        assert new_portfolio.has_position("/MGC")

    def test_portfolio_limit_check(self, sample_position):
        """Test portfolio limit checking."""
        portfolio = Portfolio()

        # Can add first position
        allowed, reason = portfolio.can_add_units(
            symbol="/MGC",
            units_to_add=1,
            correlation_group=CorrelationGroup.METALS,
        )
        assert allowed is True

    def test_total_units_limit(self):
        """Test that 12 total units limit is enforced."""
        portfolio = Portfolio()

        # Create positions totaling 11 units across different groups
        # to avoid hitting correlation limit
        symbols_and_groups = [
            ("/MGC", CorrelationGroup.METALS),
            ("/M2K", CorrelationGroup.EQUITY_US),
            ("/MCL", CorrelationGroup.ENERGY),
        ]
        for i, (symbol, group) in enumerate(symbols_and_groups):
            n = NValue(value=Decimal("20"), calculated_at=datetime.now())
            levels = tuple(
                PyramidLevel(
                    level=j + 1,
                    entry_price=Decimal("100"),
                    contracts=1,
                    n_at_entry=Decimal("20"),
                )
                for j in range(4 if i < 2 else 3)  # 4 + 4 + 3 = 11
            )
            pos = Position(
                symbol=symbol,
                direction=Direction.LONG,
                system=System.S1,
                correlation_group=group,
                pyramid_levels=levels,
                current_stop=Decimal("80"),
                initial_entry_price=Decimal("100"),
                initial_n=n,
            )
            portfolio = portfolio.add_position(pos)

        assert portfolio.total_units == 11

        # Can add 1 more
        allowed, _ = portfolio.can_add_units(
            symbol="/MES",
            units_to_add=1,
            correlation_group=CorrelationGroup.EQUITY_US,
        )
        assert allowed is True

        # Cannot add 2 more
        allowed, reason = portfolio.can_add_units(
            symbol="/MES",
            units_to_add=2,
            correlation_group=CorrelationGroup.EQUITY_US,
        )
        assert allowed is False
        assert "12" in reason


class TestTrade:
    """Tests for Trade audit record."""

    def test_trade_is_winner(self):
        """Test winner detection for S1 filter."""
        trade = Trade(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("2800"),
            entry_date=datetime.now(),
            entry_contracts=2,
            n_at_entry=Decimal("20"),
            exit_price=Decimal("2900"),
            exit_date=datetime.now(),
            exit_reason="breakout",
            realized_pnl=Decimal("2000"),
        )

        assert trade.is_winner is True

    def test_trade_is_loser(self):
        """Test loser detection."""
        trade = Trade(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("2800"),
            entry_date=datetime.now(),
            entry_contracts=2,
            n_at_entry=Decimal("20"),
            exit_price=Decimal("2700"),
            exit_date=datetime.now(),
            exit_reason="stop",
            realized_pnl=Decimal("-2000"),
        )

        assert trade.is_winner is False

    def test_r_multiple(self):
        """Test R-multiple calculation."""
        trade = Trade(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("2800"),
            entry_date=datetime.now(),
            entry_contracts=2,
            n_at_entry=Decimal("20"),  # Initial risk = 2 * 20 * 2 = 80
            exit_price=Decimal("2900"),
            exit_date=datetime.now(),
            exit_reason="breakout",
            realized_pnl=Decimal("160"),  # Made 2R
        )

        assert trade.r_multiple == Decimal("2")


class TestSignal:
    """Tests for Signal model."""

    def test_signal_properties(self):
        """Test signal helper properties."""
        signal = Signal(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            breakout_price=Decimal("2850"),
            channel_value=Decimal("2845"),
        )

        assert signal.is_long is True
        assert signal.is_s1 is True

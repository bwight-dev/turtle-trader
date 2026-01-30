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
        """Test that 12 total units limit is enforced (original mode)."""
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
            # Use original mode to test 12 unit limit
            portfolio = portfolio.add_position(pos, use_risk_cap_mode=False)

        assert portfolio.total_units == 11

        # Can add 1 more (original mode)
        allowed, _ = portfolio.can_add_units(
            symbol="/MES",
            units_to_add=1,
            correlation_group=CorrelationGroup.EQUITY_US,
            use_risk_cap_mode=False,
        )
        assert allowed is True

        # Cannot add 2 more (original mode)
        allowed, reason = portfolio.can_add_units(
            symbol="/MES",
            units_to_add=2,
            correlation_group=CorrelationGroup.EQUITY_US,
            use_risk_cap_mode=False,
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


class TestPositionShort:
    """Tests for short positions."""

    @pytest.fixture
    def short_position(self):
        """Create a short position for testing."""
        n = NValue(value=Decimal("20"), calculated_at=datetime.now(), symbol="/MES")
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("4500"),
            contracts=3,
            n_at_entry=Decimal("20"),
        )
        return Position(
            symbol="/MES",
            direction=Direction.SHORT,
            system=System.S2,
            correlation_group=CorrelationGroup.EQUITY_US,
            pyramid_levels=(level,),
            current_stop=Decimal("4540"),  # 2N above entry for short
            initial_entry_price=Decimal("4500"),
            initial_n=n,
        )

    def test_short_position_next_pyramid_trigger(self, short_position):
        """Test next pyramid trigger for short position.

        Rule 11: Pyramid at -½N intervals for shorts.
        """
        # ½N = 10, so trigger at 4490 (below entry)
        assert short_position.next_pyramid_trigger == Decimal("4490")

    def test_short_position_stop_hit(self, short_position):
        """Test stop hit detection for short."""
        assert short_position.is_stop_hit(Decimal("4540")) is True  # At stop
        assert short_position.is_stop_hit(Decimal("4550")) is True  # Above stop
        assert short_position.is_stop_hit(Decimal("4500")) is False  # Below stop

    def test_short_position_unrealized_pnl_profit(self, short_position):
        """Test unrealized P&L for profitable short."""
        # Price dropped, so short is profitable
        pnl = short_position.unrealized_pnl(Decimal("4400"), Decimal("5"))
        # (4500 - 4400) * 3 * 5 = 1500
        assert pnl == Decimal("1500")

    def test_short_position_unrealized_pnl_loss(self, short_position):
        """Test unrealized P&L for losing short."""
        # Price rose, so short is losing
        pnl = short_position.unrealized_pnl(Decimal("4550"), Decimal("5"))
        # (4500 - 4550) * 3 * 5 = -750
        assert pnl == Decimal("-750")

    def test_pyramid_level_stop_price_short(self):
        """Test stop price calculation for short pyramid level."""
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=2,
            n_at_entry=Decimal("5"),
        )
        # Short stop is entry + 2N
        stop = level.stop_price(Direction.SHORT)
        assert stop == Decimal("110")


class TestPositionLong:
    """Additional tests for long positions."""

    def test_long_position_unrealized_pnl_profit(self):
        """Test unrealized P&L for profitable long."""
        n = NValue(value=Decimal("2"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=10,
            n_at_entry=Decimal("2"),
        )
        pos = Position(
            symbol="SPY",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(level,),
            current_stop=Decimal("96"),
            initial_entry_price=Decimal("100"),
            initial_n=n,
        )
        # Price rose, so long is profitable
        pnl = pos.unrealized_pnl(Decimal("105"), Decimal("1"))
        # (105 - 100) * 10 * 1 = 50
        assert pnl == Decimal("50")

    def test_long_position_unrealized_pnl_loss(self):
        """Test unrealized P&L for losing long."""
        n = NValue(value=Decimal("2"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=10,
            n_at_entry=Decimal("2"),
        )
        pos = Position(
            symbol="SPY",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(level,),
            current_stop=Decimal("96"),
            initial_entry_price=Decimal("100"),
            initial_n=n,
        )
        # Price dropped, so long is losing
        pnl = pos.unrealized_pnl(Decimal("97"), Decimal("1"))
        # (97 - 100) * 10 * 1 = -30
        assert pnl == Decimal("-30")

    def test_position_update_stop(self):
        """Test updating position stop."""
        n = NValue(value=Decimal("2"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=10,
            n_at_entry=Decimal("2"),
        )
        pos = Position(
            symbol="SPY",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(level,),
            current_stop=Decimal("96"),
            initial_entry_price=Decimal("100"),
            initial_n=n,
        )
        new_pos = pos.update_stop(Decimal("98"))
        assert new_pos.current_stop == Decimal("98")
        assert pos.current_stop == Decimal("96")  # Original unchanged

    def test_pyramid_level_stop_price_long(self):
        """Test stop price calculation for long pyramid level."""
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=2,
            n_at_entry=Decimal("5"),
        )
        # Long stop is entry - 2N
        stop = level.stop_price(Direction.LONG)
        assert stop == Decimal("90")

    def test_position_average_entry_no_pyramids(self):
        """Test average entry with no pyramids."""
        n = NValue(value=Decimal("2"), calculated_at=datetime.now())
        pos = Position(
            symbol="SPY",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(),  # No pyramid levels
            current_stop=Decimal("96"),
            initial_entry_price=Decimal("100"),
            initial_n=n,
        )
        assert pos.average_entry_price == Decimal("100")

    def test_position_latest_entry_no_pyramids(self):
        """Test latest entry with no pyramids."""
        n = NValue(value=Decimal("2"), calculated_at=datetime.now())
        pos = Position(
            symbol="SPY",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(),
            current_stop=Decimal("96"),
            initial_entry_price=Decimal("100"),
            initial_n=n,
        )
        assert pos.latest_entry_price == Decimal("100")
        assert pos.latest_n_at_entry == Decimal("2")


class TestPortfolioExtended:
    """Extended tests for Portfolio model."""

    def test_get_position_exists(self):
        """Test getting an existing position."""
        n = NValue(value=Decimal("20"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("2800"),
            contracts=2,
            n_at_entry=Decimal("20"),
        )
        pos = Position(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            correlation_group=CorrelationGroup.METALS,
            pyramid_levels=(level,),
            current_stop=Decimal("2760"),
            initial_entry_price=Decimal("2800"),
            initial_n=n,
        )
        portfolio = Portfolio().add_position(pos)

        retrieved = portfolio.get_position("/MGC")
        assert retrieved is not None
        assert retrieved.symbol == "/MGC"

    def test_get_position_not_exists(self):
        """Test getting non-existent position returns None."""
        portfolio = Portfolio()
        assert portfolio.get_position("/MGC") is None

    def test_update_position(self):
        """Test updating an existing position."""
        n = NValue(value=Decimal("20"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("2800"),
            contracts=2,
            n_at_entry=Decimal("20"),
        )
        pos = Position(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(level,),
            current_stop=Decimal("2760"),
            initial_entry_price=Decimal("2800"),
            initial_n=n,
        )
        portfolio = Portfolio().add_position(pos)

        updated_pos = pos.update_stop(Decimal("2780"))
        new_portfolio = portfolio.update_position(updated_pos)

        assert new_portfolio.get_position("/MGC").current_stop == Decimal("2780")

    def test_update_position_not_exists_raises(self):
        """Test updating non-existent position raises error."""
        n = NValue(value=Decimal("20"), calculated_at=datetime.now())
        pos = Position(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(),
            current_stop=Decimal("2760"),
            initial_entry_price=Decimal("2800"),
            initial_n=n,
        )
        portfolio = Portfolio()

        with pytest.raises(ValueError, match="No position"):
            portfolio.update_position(pos)

    def test_close_position(self):
        """Test closing a position."""
        n = NValue(value=Decimal("20"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("2800"),
            contracts=2,
            n_at_entry=Decimal("20"),
        )
        pos = Position(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(level,),
            current_stop=Decimal("2760"),
            initial_entry_price=Decimal("2800"),
            initial_n=n,
        )
        portfolio = Portfolio().add_position(pos)

        new_portfolio, closed = portfolio.close_position("/MGC")
        assert new_portfolio.has_position("/MGC") is False
        assert closed.symbol == "/MGC"

    def test_close_position_not_exists_raises(self):
        """Test closing non-existent position raises error."""
        portfolio = Portfolio()
        with pytest.raises(ValueError, match="No position"):
            portfolio.close_position("/MGC")

    def test_add_duplicate_position_raises(self):
        """Test adding duplicate position raises error."""
        n = NValue(value=Decimal("20"), calculated_at=datetime.now())
        pos = Position(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(),
            current_stop=Decimal("2760"),
            initial_entry_price=Decimal("2800"),
            initial_n=n,
        )
        portfolio = Portfolio().add_position(pos)

        with pytest.raises(ValueError, match="already exists"):
            portfolio.add_position(pos)

    def test_units_in_group(self):
        """Test counting units in a correlation group."""
        n = NValue(value=Decimal("20"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=2,
            n_at_entry=Decimal("20"),
        )
        pos1 = Position(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            correlation_group=CorrelationGroup.METALS,
            pyramid_levels=(level,),
            current_stop=Decimal("80"),
            initial_entry_price=Decimal("100"),
            initial_n=n,
        )
        pos2 = Position(
            symbol="/SIL",
            direction=Direction.LONG,
            system=System.S1,
            correlation_group=CorrelationGroup.METALS,
            pyramid_levels=(level,),
            current_stop=Decimal("80"),
            initial_entry_price=Decimal("100"),
            initial_n=n,
        )
        portfolio = Portfolio().add_position(pos1).add_position(pos2)

        assert portfolio.units_in_group(CorrelationGroup.METALS) == 2
        assert portfolio.units_in_group(CorrelationGroup.EQUITY_US) == 0

    def test_total_unrealized_pnl(self):
        """Test total unrealized P&L calculation."""
        n = NValue(value=Decimal("2"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=10,
            n_at_entry=Decimal("2"),
        )
        pos = Position(
            symbol="SPY",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(level,),
            current_stop=Decimal("96"),
            initial_entry_price=Decimal("100"),
            initial_n=n,
        )
        portfolio = Portfolio().add_position(pos)

        prices = {"SPY": Decimal("110")}
        point_values = {"SPY": Decimal("1")}
        pnl = portfolio.total_unrealized_pnl(prices, point_values)
        # (110 - 100) * 10 * 1 = 100
        assert pnl == Decimal("100")

    def test_total_unrealized_pnl_missing_price(self):
        """Test total P&L skips positions without prices."""
        n = NValue(value=Decimal("2"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=10,
            n_at_entry=Decimal("2"),
        )
        pos = Position(
            symbol="SPY",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(level,),
            current_stop=Decimal("96"),
            initial_entry_price=Decimal("100"),
            initial_n=n,
        )
        portfolio = Portfolio().add_position(pos)

        prices = {}  # No prices
        point_values = {"SPY": Decimal("1")}
        pnl = portfolio.total_unrealized_pnl(prices, point_values)
        assert pnl == Decimal("0")

    def test_can_add_units_correlation_limit(self):
        """Test correlation group limit is enforced."""
        portfolio = Portfolio()

        # Add positions to METALS group up to limit
        n = NValue(value=Decimal("10"), calculated_at=datetime.now())
        for i, symbol in enumerate(["/MGC", "/SIL"]):
            levels = tuple(
                PyramidLevel(
                    level=j + 1,
                    entry_price=Decimal("100"),
                    contracts=1,
                    n_at_entry=Decimal("10"),
                )
                for j in range(3)  # 3 units each = 6 total
            )
            pos = Position(
                symbol=symbol,
                direction=Direction.LONG,
                system=System.S1,
                correlation_group=CorrelationGroup.METALS,
                pyramid_levels=levels,
                current_stop=Decimal("80"),
                initial_entry_price=Decimal("100"),
                initial_n=n,
            )
            portfolio = portfolio.add_position(pos)

        # Now at 6 units in METALS
        assert portfolio.units_in_group(CorrelationGroup.METALS) == 6

        # Cannot add more to METALS
        allowed, reason = portfolio.can_add_units(
            symbol="/GC",
            units_to_add=1,
            correlation_group=CorrelationGroup.METALS,
        )
        assert allowed is False
        assert "metals" in reason.lower()

    def test_portfolio_risk_cap_mode(self):
        """Test risk cap mode skips total unit check."""
        portfolio = Portfolio()

        # Add many positions - in risk cap mode, total unit limit not enforced
        n = NValue(value=Decimal("10"), calculated_at=datetime.now())
        groups = [
            CorrelationGroup.METALS,
            CorrelationGroup.EQUITY_US,
            CorrelationGroup.ENERGY,
            CorrelationGroup.CURRENCIES,
        ]
        for i, group in enumerate(groups):
            levels = tuple(
                PyramidLevel(
                    level=j + 1,
                    entry_price=Decimal("100"),
                    contracts=1,
                    n_at_entry=Decimal("10"),
                )
                for j in range(3)
            )
            pos = Position(
                symbol=f"SYM{i}",
                direction=Direction.LONG,
                system=System.S1,
                correlation_group=group,
                pyramid_levels=levels,
                current_stop=Decimal("80"),
                initial_entry_price=Decimal("100"),
                initial_n=n,
            )
            portfolio = portfolio.add_position(pos, use_risk_cap_mode=True)

        # 12 units total
        assert portfolio.total_units == 12

        # In risk cap mode, can still add (total limit not enforced)
        allowed, reason = portfolio.can_add_units(
            symbol="NEWSYM",
            units_to_add=1,
            correlation_group=CorrelationGroup.RATES,
            use_risk_cap_mode=True,
        )
        assert allowed is True


class TestLimitCheckResult:
    """Tests for LimitCheckResult model."""

    def test_ok_factory(self):
        """Test the ok() factory method."""
        result = LimitCheckResult.ok(
            current_market_units=2,
            current_group_units=4,
            current_total_units=8,
            correlation_group=CorrelationGroup.METALS,
        )
        assert result.allowed is True
        assert result.current_market_units == 2
        assert result.correlation_group == CorrelationGroup.METALS

    def test_blocked_factory(self):
        """Test the blocked() factory method."""
        result = LimitCheckResult.blocked(
            reason="Exceeded market limit",
            limit_violated="market",
            current_market_units=4,
            current_group_units=5,
            current_total_units=10,
            correlation_group=CorrelationGroup.EQUITY_US,
        )
        assert result.allowed is False
        assert result.limit_violated == "market"
        assert result.reason == "Exceeded market limit"

    def test_market_headroom(self):
        """Test market headroom calculation."""
        result = LimitCheckResult(
            allowed=True,
            reason="OK",
            current_market_units=2,
            max_market_units=4,
        )
        assert result.market_headroom == 2

    def test_group_headroom(self):
        """Test group headroom calculation."""
        result = LimitCheckResult(
            allowed=True,
            reason="OK",
            current_group_units=3,
            max_group_units=6,
        )
        assert result.group_headroom == 3

    def test_total_headroom(self):
        """Test total headroom calculation."""
        result = LimitCheckResult(
            allowed=True,
            reason="OK",
            current_total_units=8,
            max_total_units=12,
        )
        assert result.total_headroom == 4

    def test_available_units_minimum(self):
        """Test available units is minimum of all headrooms."""
        result = LimitCheckResult(
            allowed=True,
            reason="OK",
            current_market_units=3,  # headroom = 1
            current_group_units=4,  # headroom = 2
            current_total_units=10,  # headroom = 2
            max_market_units=4,
            max_group_units=6,
            max_total_units=12,
        )
        assert result.available_units == 1  # Constrained by market

    def test_available_units_group_constrained(self):
        """Test available units when group is constraint."""
        result = LimitCheckResult(
            allowed=True,
            reason="OK",
            current_market_units=1,  # headroom = 3
            current_group_units=5,  # headroom = 1
            current_total_units=8,  # headroom = 4
            max_market_units=4,
            max_group_units=6,
            max_total_units=12,
        )
        assert result.available_units == 1  # Constrained by group


class TestDonchianChannel:
    """Tests for DonchianChannel model."""

    def test_donchian_channel_creation(self):
        """Test creating a Donchian channel."""
        channel = DonchianChannel(
            period=20,
            upper=Decimal("2850"),
            lower=Decimal("2700"),
            calculated_at=datetime.now(),
        )
        assert channel.upper == Decimal("2850")
        assert channel.lower == Decimal("2700")
        assert channel.period == 20

    def test_donchian_channel_55_period(self):
        """Test Donchian channel with 55-day period."""
        channel = DonchianChannel(
            period=55,
            upper=Decimal("2900"),
            lower=Decimal("2600"),
            calculated_at=datetime.now(),
        )
        assert channel.period == 55
        assert channel.upper == Decimal("2900")
        assert channel.lower == Decimal("2600")

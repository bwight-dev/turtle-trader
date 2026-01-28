"""Unit tests for Turtle Trading rules."""

from decimal import Decimal

from src.domain import rules


class TestRulesConstants:
    """Test that rule constants are correct."""

    def test_risk_per_trade(self):
        """Test risk is 0.5% (Parker modern rule)."""
        assert rules.RISK_PER_TRADE == Decimal("0.005")

    def test_stop_multiplier(self):
        """Test stop is 2N."""
        assert rules.STOP_MULTIPLIER == Decimal("2")

    def test_pyramid_interval(self):
        """Test pyramid interval is ½N."""
        assert rules.PYRAMID_INTERVAL_MULTIPLIER == Decimal("0.5")

    def test_position_limits(self):
        """Test position limits."""
        assert rules.MAX_UNITS_PER_MARKET == 4
        assert rules.MAX_UNITS_CORRELATED == 6
        assert rules.MAX_UNITS_TOTAL == 12

    def test_entry_periods(self):
        """Test Donchian entry periods."""
        assert rules.S1_ENTRY_PERIOD == 20
        assert rules.S2_ENTRY_PERIOD == 55

    def test_exit_periods(self):
        """Test Donchian exit periods."""
        assert rules.S1_EXIT_PERIOD == 10
        assert rules.S2_EXIT_PERIOD == 20

    def test_drawdown_settings(self):
        """Test drawdown rule settings."""
        assert rules.DRAWDOWN_THRESHOLD == Decimal("0.10")  # 10%
        assert rules.DRAWDOWN_REDUCTION == Decimal("0.20")  # 20%


class TestCalculateStopPrice:
    """Tests for stop price calculation (Rule 10)."""

    def test_stop_long(self):
        """Test stop for long position."""
        stop = rules.calculate_stop_price(
            entry_price=Decimal("2800"),
            n_value=Decimal("20"),
            is_long=True,
        )
        # Stop = 2800 - 2*20 = 2760
        assert stop == Decimal("2760")

    def test_stop_short(self):
        """Test stop for short position."""
        stop = rules.calculate_stop_price(
            entry_price=Decimal("2800"),
            n_value=Decimal("20"),
            is_long=False,
        )
        # Stop = 2800 + 2*20 = 2840
        assert stop == Decimal("2840")


class TestCalculatePyramidTrigger:
    """Tests for pyramid trigger calculation (Rule 11)."""

    def test_pyramid_trigger_long(self):
        """Test pyramid trigger for long position."""
        trigger = rules.calculate_pyramid_trigger(
            last_entry_price=Decimal("2800"),
            n_value=Decimal("20"),
            is_long=True,
        )
        # Trigger = 2800 + 0.5*20 = 2810
        assert trigger == Decimal("2810")

    def test_pyramid_trigger_short(self):
        """Test pyramid trigger for short position."""
        trigger = rules.calculate_pyramid_trigger(
            last_entry_price=Decimal("2800"),
            n_value=Decimal("20"),
            is_long=False,
        )
        # Trigger = 2800 - 0.5*20 = 2790
        assert trigger == Decimal("2790")


class TestCalculateUnitSize:
    """Tests for unit size calculation (Rule 4)."""

    def test_unit_size_rounds_down(self):
        """Test that unit size rounds down."""
        # $100k × 0.005 = $500 risk budget
        # Dollar volatility = 20 × 10 = $200
        # Unit size = 500 / 200 = 2.5, rounds down to 2
        size = rules.calculate_unit_size(
            equity=Decimal("100000"),
            n_value=Decimal("20"),
            point_value=Decimal("10"),
        )
        assert size == 2

    def test_unit_size_exact(self):
        """Test exact unit size calculation."""
        # $100k × 0.005 = $500 risk budget
        # Dollar volatility = 25 × 10 = $250
        # Unit size = 500 / 250 = 2
        size = rules.calculate_unit_size(
            equity=Decimal("100000"),
            n_value=Decimal("25"),
            point_value=Decimal("10"),
        )
        assert size == 2

    def test_unit_size_zero_volatility(self):
        """Test that zero volatility returns 0 contracts."""
        size = rules.calculate_unit_size(
            equity=Decimal("100000"),
            n_value=Decimal("0"),
            point_value=Decimal("10"),
        )
        assert size == 0

    def test_unit_size_custom_risk(self):
        """Test unit size with custom risk percentage."""
        # Original 1% risk
        size = rules.calculate_unit_size(
            equity=Decimal("100000"),
            n_value=Decimal("20"),
            point_value=Decimal("10"),
            risk_pct=Decimal("0.01"),  # 1%
        )
        # $100k × 0.01 = $1000 / 200 = 5
        assert size == 5


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_entry_period_s1(self):
        """Test entry period for S1."""
        assert rules.get_entry_period(is_s1=True) == 20

    def test_get_entry_period_s2(self):
        """Test entry period for S2."""
        assert rules.get_entry_period(is_s1=False) == 55

    def test_get_exit_period_s1(self):
        """Test exit period for S1."""
        assert rules.get_exit_period(is_s1=True) == 10

    def test_get_exit_period_s2(self):
        """Test exit period for S2."""
        assert rules.get_exit_period(is_s1=False) == 20

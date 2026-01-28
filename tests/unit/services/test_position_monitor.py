"""Unit tests for position monitor service."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.domain.models.enums import (
    CorrelationGroup,
    Direction,
    PositionAction,
    System,
)
from src.domain.models.market import DonchianChannel, NValue
from src.domain.models.position import Position, PyramidLevel
from src.domain.services.position_monitor import (
    PositionCheckResult,
    PositionMonitor,
    check_all_positions,
)


def make_n_value(value: str = "20") -> NValue:
    """Create test NValue."""
    return NValue(value=Decimal(value), calculated_at=datetime.now())


def make_position(
    symbol: str = "/MGC",
    direction: Direction = Direction.LONG,
    system: System = System.S1,
    entry_price: str = "2800",
    stop_price: str = "2760",
    n_at_entry: str = "20",
    units: int = 1,
    contracts_per_unit: int = 2,
    correlation_group: CorrelationGroup | None = None,
) -> Position:
    """Create a test position."""
    pyramid_levels = tuple(
        PyramidLevel(
            level=i + 1,
            # Each pyramid at +10 from previous (½N = 10)
            entry_price=Decimal(entry_price) + (i * 10),
            contracts=contracts_per_unit,
            n_at_entry=Decimal(n_at_entry),
        )
        for i in range(units)
    )

    return Position(
        symbol=symbol,
        direction=direction,
        system=system,
        correlation_group=correlation_group,
        pyramid_levels=pyramid_levels,
        current_stop=Decimal(stop_price),
        initial_entry_price=Decimal(entry_price),
        initial_n=make_n_value(n_at_entry),
    )


def make_donchian(period: int, upper: str, lower: str) -> DonchianChannel:
    """Create a test Donchian channel."""
    return DonchianChannel(
        period=period,
        upper=Decimal(upper),
        lower=Decimal(lower),
        calculated_at=datetime.now(),
    )


@pytest.fixture
def monitor():
    """Create position monitor instance."""
    return PositionMonitor()


# =============================================================================
# M16: Stop Hit Detection (Rule 10)
# =============================================================================


class TestStopHitDetection:
    """Tests for 2N hard stop detection (Rule 10)."""

    def test_stop_hit_long(self, monitor):
        """Long stop hit when price <= stop."""
        pos = make_position(
            direction=Direction.LONG,
            entry_price="2800",
            stop_price="2760",  # 2N = 40
        )

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2760"),  # At stop
        )

        assert result.action == PositionAction.EXIT_STOP
        assert result.stop_triggered is True
        assert "2N stop hit" in result.reason
        assert result.is_exit is True

    def test_stop_hit_long_below(self, monitor):
        """Long stop hit when price below stop (gap down)."""
        pos = make_position(
            direction=Direction.LONG,
            stop_price="2760",
        )

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2750"),  # Below stop
        )

        assert result.action == PositionAction.EXIT_STOP
        assert result.stop_triggered is True

    def test_stop_hit_short(self, monitor):
        """Short stop hit when price >= stop."""
        pos = make_position(
            direction=Direction.SHORT,
            entry_price="2800",
            stop_price="2840",  # 2N above entry
        )

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2840"),  # At stop
        )

        assert result.action == PositionAction.EXIT_STOP
        assert result.stop_triggered is True

    def test_stop_hit_short_above(self, monitor):
        """Short stop hit when price above stop (gap up)."""
        pos = make_position(
            direction=Direction.SHORT,
            stop_price="2840",
        )

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2850"),  # Above stop
        )

        assert result.action == PositionAction.EXIT_STOP

    def test_stop_not_hit_long(self, monitor):
        """Long stop not hit when price > stop."""
        pos = make_position(
            direction=Direction.LONG,
            stop_price="2760",
        )

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2770"),  # Above stop
        )

        assert result.action != PositionAction.EXIT_STOP
        assert result.stop_triggered is False

    def test_stop_not_hit_short(self, monitor):
        """Short stop not hit when price < stop."""
        pos = make_position(
            direction=Direction.SHORT,
            stop_price="2840",
        )

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2830"),  # Below stop
        )

        assert result.action != PositionAction.EXIT_STOP
        assert result.stop_triggered is False


# =============================================================================
# M16: Breakout Exit Detection (Rules 13/14)
# =============================================================================


class TestBreakoutExitDetection:
    """Tests for Donchian breakout exit detection (Rules 13/14)."""

    def test_s1_long_exit_on_10day_low(self, monitor):
        """S1 long exits when price touches 10-day low (Rule 13)."""
        pos = make_position(
            direction=Direction.LONG,
            system=System.S1,
            entry_price="2800",
            stop_price="2700",  # Stop below channel low
        )
        exit_channel = make_donchian(period=10, upper="2880", lower="2780")

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2780"),  # At 10-day low
            exit_channel=exit_channel,
        )

        assert result.action == PositionAction.EXIT_BREAKOUT
        assert result.exit_triggered is True
        assert result.exit_channel_value == Decimal("2780")
        assert result.exit_period == 10
        assert "10-day low exit" in result.reason

    def test_s1_long_exit_below_10day_low(self, monitor):
        """S1 long exits when price breaks below 10-day low."""
        pos = make_position(
            direction=Direction.LONG,
            system=System.S1,
            stop_price="2700",
        )
        exit_channel = make_donchian(period=10, upper="2880", lower="2780")

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2770"),  # Below channel low
            exit_channel=exit_channel,
        )

        assert result.action == PositionAction.EXIT_BREAKOUT

    def test_s1_short_exit_on_10day_high(self, monitor):
        """S1 short exits when price touches 10-day high (Rule 13)."""
        pos = make_position(
            direction=Direction.SHORT,
            system=System.S1,
            entry_price="2800",
            stop_price="2900",  # Stop above channel high
        )
        exit_channel = make_donchian(period=10, upper="2820", lower="2700")

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2820"),  # At 10-day high
            exit_channel=exit_channel,
        )

        assert result.action == PositionAction.EXIT_BREAKOUT
        assert result.exit_channel_value == Decimal("2820")
        assert "10-day high exit" in result.reason

    def test_s2_long_exit_on_20day_low(self, monitor):
        """S2 long exits when price touches 20-day low (Rule 14)."""
        pos = make_position(
            direction=Direction.LONG,
            system=System.S2,
            entry_price="2900",
            stop_price="2700",
        )
        exit_channel = make_donchian(period=20, upper="2950", lower="2800")

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2800"),  # At 20-day low
            exit_channel=exit_channel,
        )

        assert result.action == PositionAction.EXIT_BREAKOUT
        assert result.exit_period == 20
        assert "20-day low exit" in result.reason

    def test_s2_short_exit_on_20day_high(self, monitor):
        """S2 short exits when price touches 20-day high (Rule 14)."""
        pos = make_position(
            direction=Direction.SHORT,
            system=System.S2,
            entry_price="2700",
            stop_price="2900",
        )
        exit_channel = make_donchian(period=20, upper="2800", lower="2600")

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2800"),  # At 20-day high
            exit_channel=exit_channel,
        )

        assert result.action == PositionAction.EXIT_BREAKOUT
        assert result.exit_period == 20
        assert "20-day high exit" in result.reason

    def test_no_exit_inside_channel_long(self, monitor):
        """No exit when price is inside channel (long)."""
        pos = make_position(
            direction=Direction.LONG,
            system=System.S1,
            stop_price="2700",
        )
        exit_channel = make_donchian(period=10, upper="2850", lower="2750")

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2800"),  # Inside channel
            exit_channel=exit_channel,
        )

        assert result.action != PositionAction.EXIT_BREAKOUT
        assert result.exit_triggered is False

    def test_no_exit_inside_channel_short(self, monitor):
        """No exit when price is inside channel (short)."""
        pos = make_position(
            direction=Direction.SHORT,
            system=System.S1,
            stop_price="2900",
        )
        exit_channel = make_donchian(period=10, upper="2850", lower="2750")

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2800"),  # Inside channel
            exit_channel=exit_channel,
        )

        assert result.action != PositionAction.EXIT_BREAKOUT
        assert result.exit_triggered is False

    def test_no_exit_check_without_channel(self, monitor):
        """Exit check skipped when no channel provided."""
        pos = make_position(
            direction=Direction.LONG,
            system=System.S1,
            stop_price="2700",
        )

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2780"),  # Would trigger exit if channel existed
            exit_channel=None,
        )

        # Without channel, can't check exit
        assert result.exit_triggered is False


# =============================================================================
# M16: Priority Testing
# =============================================================================


class TestPriorityOrder:
    """Tests for action priority (EXIT_STOP > EXIT_BREAKOUT)."""

    def test_stop_has_priority_over_breakout_exit(self, monitor):
        """When both stop and breakout exit trigger, stop wins."""
        pos = make_position(
            direction=Direction.LONG,
            stop_price="2760",  # Stop at 2760
        )
        # Exit channel low is above the stop
        exit_channel = make_donchian(period=10, upper="2850", lower="2770")

        # Price at 2755 - both stop (<=2760) and exit (<=2770) triggered
        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2755"),
            exit_channel=exit_channel,
        )

        # Stop should take priority
        assert result.action == PositionAction.EXIT_STOP
        assert result.stop_triggered is True

    def test_breakout_checked_when_stop_not_hit(self, monitor):
        """Breakout exit checked when stop isn't hit."""
        pos = make_position(
            direction=Direction.LONG,
            stop_price="2700",  # Stop well below
        )
        exit_channel = make_donchian(period=10, upper="2850", lower="2780")

        # Price at 2780 - stop not hit, but exit triggered
        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2780"),
            exit_channel=exit_channel,
        )

        assert result.action == PositionAction.EXIT_BREAKOUT


# =============================================================================
# M17: Pyramid Detection (Rule 11)
# =============================================================================


class TestPyramidDetection:
    """Tests for pyramid trigger detection (Rule 11)."""

    def test_pyramid_triggered_at_half_n_long(self, monitor):
        """Long pyramid triggers at +½N from last entry (Rule 11)."""
        # Entry at 2800, N=20, so pyramid at 2810 (½N = 10)
        pos = make_position(
            direction=Direction.LONG,
            entry_price="2800",
            n_at_entry="20",
            stop_price="2760",
            units=1,
        )

        # Verify trigger price
        assert pos.next_pyramid_trigger == Decimal("2810")

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2810"),  # At pyramid trigger
        )

        assert result.action == PositionAction.PYRAMID
        assert result.pyramid_triggered is True
        assert "Pyramid triggered" in result.reason
        assert "+½N" in result.reason

    def test_pyramid_triggered_above_half_n_long(self, monitor):
        """Long pyramid triggers above ½N threshold."""
        pos = make_position(
            direction=Direction.LONG,
            entry_price="2800",
            n_at_entry="20",
            stop_price="2760",
            units=1,
        )

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2825"),  # Above trigger (2810)
        )

        assert result.action == PositionAction.PYRAMID

    def test_pyramid_triggered_at_half_n_short(self, monitor):
        """Short pyramid triggers at -½N from last entry."""
        # Short entry at 2800, N=20, so pyramid at 2790 (½N = 10 below)
        pos = make_position(
            direction=Direction.SHORT,
            entry_price="2800",
            n_at_entry="20",
            stop_price="2840",
            units=1,
        )

        # Verify trigger price
        assert pos.next_pyramid_trigger == Decimal("2790")

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2790"),  # At pyramid trigger
        )

        assert result.action == PositionAction.PYRAMID
        assert result.pyramid_triggered is True

    def test_pyramid_triggered_below_half_n_short(self, monitor):
        """Short pyramid triggers below ½N threshold."""
        pos = make_position(
            direction=Direction.SHORT,
            entry_price="2800",
            n_at_entry="20",
            stop_price="2840",
            units=1,
        )

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2785"),  # Below trigger (2790)
        )

        assert result.action == PositionAction.PYRAMID

    def test_pyramid_not_triggered_before_half_n_long(self, monitor):
        """Long pyramid doesn't trigger before ½N."""
        pos = make_position(
            direction=Direction.LONG,
            entry_price="2800",
            n_at_entry="20",
            stop_price="2760",
            units=1,
        )

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2805"),  # Below trigger (2810)
        )

        assert result.action == PositionAction.HOLD
        assert result.pyramid_triggered is False

    def test_pyramid_not_triggered_before_half_n_short(self, monitor):
        """Short pyramid doesn't trigger before ½N."""
        pos = make_position(
            direction=Direction.SHORT,
            entry_price="2800",
            n_at_entry="20",
            stop_price="2840",
            units=1,
        )

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2795"),  # Above trigger (2790)
        )

        assert result.action == PositionAction.HOLD

    def test_no_pyramid_at_max_units(self, monitor):
        """No pyramid when already at max 4 units."""
        pos = make_position(
            direction=Direction.LONG,
            entry_price="2800",
            n_at_entry="20",
            stop_price="2760",
            units=4,  # Already at max
        )

        # Even though price would trigger pyramid...
        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2850"),  # Way above any trigger
        )

        # ...should HOLD because at max units
        assert result.action == PositionAction.HOLD
        assert result.pyramid_triggered is False
        assert result.can_add_unit is False
        assert result.current_units == 4

    def test_pyramid_after_multiple_levels(self, monitor):
        """Pyramid triggers correctly after multiple adds."""
        # Position has 3 units:
        # Level 1: 2800, Level 2: 2810, Level 3: 2820
        # N=20, so next trigger at 2820 + 10 = 2830
        pos = make_position(
            direction=Direction.LONG,
            entry_price="2800",
            n_at_entry="20",
            stop_price="2780",  # Moved up with pyramids
            units=3,
        )

        # Latest entry is at 2820 (level 3)
        assert pos.latest_entry_price == Decimal("2820")
        assert pos.next_pyramid_trigger == Decimal("2830")

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2830"),
        )

        assert result.action == PositionAction.PYRAMID
        assert result.current_units == 3


# =============================================================================
# M17: Full Priority Testing
# =============================================================================


class TestFullPriorityOrder:
    """Tests for complete priority (EXIT_STOP > EXIT_BREAKOUT > PYRAMID > HOLD)."""

    def test_stop_priority_over_pyramid(self, monitor):
        """Stop hit takes priority over pyramid trigger."""
        pos = make_position(
            direction=Direction.LONG,
            entry_price="2800",
            n_at_entry="20",
            stop_price="2760",
            units=1,
        )

        # Price at 2755 triggers both stop (<=2760) and would show movement
        # but stop should win
        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2755"),
        )

        assert result.action == PositionAction.EXIT_STOP

    def test_breakout_priority_over_pyramid(self, monitor):
        """Breakout exit takes priority over pyramid."""
        pos = make_position(
            direction=Direction.LONG,
            entry_price="2800",
            n_at_entry="20",
            stop_price="2700",  # Stop well below
            units=1,
        )
        exit_channel = make_donchian(period=10, upper="2850", lower="2810")

        # Price at 2810 triggers both:
        # - Pyramid (price >= 2810)
        # - Exit (price <= 2810 channel low)
        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2810"),
            exit_channel=exit_channel,
        )

        # Exit should take priority
        assert result.action == PositionAction.EXIT_BREAKOUT

    def test_hold_when_nothing_triggered(self, monitor):
        """HOLD when no conditions met."""
        pos = make_position(
            direction=Direction.LONG,
            entry_price="2800",
            n_at_entry="20",
            stop_price="2760",
            units=1,
        )
        exit_channel = make_donchian(period=10, upper="2900", lower="2750")

        # Price at 2805: above stop (2760), above exit low (2750),
        # below pyramid trigger (2810)
        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2805"),
            exit_channel=exit_channel,
        )

        assert result.action == PositionAction.HOLD
        assert result.requires_action is False


# =============================================================================
# Result Properties
# =============================================================================


class TestPositionCheckResultProperties:
    """Tests for PositionCheckResult properties."""

    def test_requires_action_true_for_exits(self, monitor):
        """requires_action is True for exit actions."""
        pos = make_position(direction=Direction.LONG, stop_price="2760")

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2760"),  # Stop hit
        )

        assert result.requires_action is True

    def test_requires_action_true_for_pyramid(self, monitor):
        """requires_action is True for pyramid action."""
        pos = make_position(
            direction=Direction.LONG,
            entry_price="2800",
            n_at_entry="20",
            stop_price="2760",
            units=1,
        )

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2815"),  # Above pyramid trigger
        )

        assert result.requires_action is True

    def test_requires_action_false_for_hold(self, monitor):
        """requires_action is False for HOLD."""
        pos = make_position(
            direction=Direction.LONG,
            stop_price="2760",
            units=1,
        )

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2800"),  # Neutral
        )

        assert result.requires_action is False

    def test_is_exit_property(self, monitor):
        """is_exit property for exit actions."""
        pos = make_position(direction=Direction.LONG, stop_price="2760")

        stop_result = monitor.check_position(
            position=pos,
            current_price=Decimal("2760"),
        )
        assert stop_result.is_exit is True

        pos_with_low_stop = make_position(
            direction=Direction.LONG, stop_price="2700"
        )
        exit_channel = make_donchian(period=10, upper="2850", lower="2770")
        exit_result = monitor.check_position(
            position=pos_with_low_stop,
            current_price=Decimal("2770"),
            exit_channel=exit_channel,
        )
        assert exit_result.is_exit is True

    def test_is_pyramid_property(self, monitor):
        """is_pyramid property for pyramid action."""
        pos = make_position(
            direction=Direction.LONG,
            entry_price="2800",
            n_at_entry="20",
            stop_price="2760",
            units=1,
        )

        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2815"),
        )

        assert result.is_pyramid is True


# =============================================================================
# Get Exit Period
# =============================================================================


class TestGetExitPeriod:
    """Tests for get_exit_period helper."""

    def test_s1_exit_period(self, monitor):
        """S1 uses 10-day exit."""
        assert monitor.get_exit_period(System.S1) == 10

    def test_s2_exit_period(self, monitor):
        """S2 uses 20-day exit."""
        assert monitor.get_exit_period(System.S2) == 20


# =============================================================================
# Check All Positions
# =============================================================================


class TestCheckAllPositions:
    """Tests for check_all_positions convenience function."""

    def test_filters_to_actionable_results(self):
        """Only returns results requiring action."""
        pos1 = make_position(
            symbol="/MGC",
            direction=Direction.LONG,
            stop_price="2760",  # Will be hit
        )
        pos2 = make_position(
            symbol="/SIL",
            direction=Direction.LONG,
            stop_price="90",
            entry_price="100",
        )

        prices = {
            "/MGC": Decimal("2755"),  # Stop hit
            "/SIL": Decimal("100"),  # Neutral
        }

        results = check_all_positions(
            positions=[pos1, pos2],
            prices=prices,
            exit_channels={},
        )

        assert len(results) == 1
        assert results[0].symbol == "/MGC"

    def test_sorts_by_priority(self):
        """Results sorted: exits first, then pyramids."""
        pos_stop = make_position(
            symbol="/A",
            direction=Direction.LONG,
            stop_price="100",
        )
        pos_pyramid = make_position(
            symbol="/B",
            direction=Direction.LONG,
            entry_price="100",
            n_at_entry="10",
            stop_price="80",
            units=1,
        )
        pos_exit = make_position(
            symbol="/C",
            direction=Direction.LONG,
            stop_price="80",
        )

        prices = {
            "/A": Decimal("95"),  # Stop hit
            "/B": Decimal("110"),  # Pyramid trigger (100 + 5)
            "/C": Decimal("90"),  # Will trigger exit
        }
        exit_channels = {
            "/C": make_donchian(period=10, upper="100", lower="92"),
        }

        results = check_all_positions(
            positions=[pos_pyramid, pos_exit, pos_stop],  # Shuffled order
            prices=prices,
            exit_channels=exit_channels,
        )

        assert len(results) == 3
        assert results[0].action == PositionAction.EXIT_STOP  # First
        assert results[1].action == PositionAction.EXIT_BREAKOUT  # Second
        assert results[2].action == PositionAction.PYRAMID  # Third

    def test_skips_positions_without_prices(self):
        """Positions without prices are skipped."""
        pos = make_position(symbol="/MGC", direction=Direction.LONG)

        results = check_all_positions(
            positions=[pos],
            prices={},  # No price for /MGC
            exit_channels={},
        )

        assert len(results) == 0


# =============================================================================
# Reference Portfolio Tests
# =============================================================================


class TestReferencePortfolio:
    """Tests using the reference portfolio from implementation plan."""

    def test_m2k_stop_check(self, monitor):
        """/M2K stop at $2,648.50 - test stop detection."""
        # From reference: /M2KH26 | 4 | $2,731.10 | $2,648.50 | S1 | $40.44
        pos = make_position(
            symbol="/M2K",
            direction=Direction.LONG,
            system=System.S1,
            entry_price="2731.10",
            stop_price="2648.50",
            n_at_entry="40.44",
            units=4,
        )

        # Current price above stop - should HOLD (max units)
        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2700"),
        )
        assert result.action == PositionAction.HOLD

        # Simulate price at $2,648 - should EXIT_STOP
        result = monitor.check_position(
            position=pos,
            current_price=Decimal("2648"),
        )
        assert result.action == PositionAction.EXIT_STOP

    def test_mgc_at_full_position(self, monitor):
        """/MGC at 4 units - verify no pyramid possible."""
        # From reference: /MGCG26 | 4 | $4,790.25 | $4,770.00 | S2 | $91.42
        pos = make_position(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S2,
            entry_price="4790.25",
            stop_price="4770.00",
            n_at_entry="91.42",
            units=4,
        )

        # Even at high price, can't pyramid (at max)
        result = monitor.check_position(
            position=pos,
            current_price=Decimal("5000"),  # Way up
        )

        assert result.action == PositionAction.HOLD
        assert result.can_add_unit is False

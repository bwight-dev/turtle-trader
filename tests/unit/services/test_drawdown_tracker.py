"""Unit tests for drawdown tracker.

Tests the correct Rule 5 behavior per original Turtle advisor:
- Cascading reductions (0.80^n) for each 10% drawdown level
- Recovery threshold is yearly starting equity (not rolling HWM)
- Annual reset of yearly starting equity
"""

from decimal import Decimal

import pytest

from src.domain.models.equity import EquityState
from src.domain.services.drawdown_tracker import (
    DrawdownTracker,
    calculate_notional_equity,
)


class TestDrawdownTracker:
    """Tests for DrawdownTracker class."""

    def test_initial_state(self):
        """Initial state has all values equal."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("100000"))

        assert tracker.yearly_starting_equity == Decimal("100000")
        assert tracker.actual_equity == Decimal("100000")
        assert tracker.notional_equity == Decimal("100000")
        assert tracker.drawdown_pct == Decimal("0")
        assert tracker.reduction_level == 0
        assert not tracker.is_in_drawdown
        assert not tracker.reduction_applied

    def test_10_pct_drawdown_reduces_notional_by_20_pct(self):
        """Rule 5: 10% drawdown -> 20% notional reduction (notional = 80%)."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))

        # 10% drawdown
        tracker.update_equity(Decimal("900000"))

        assert tracker.actual_equity == Decimal("900000")
        assert tracker.notional_equity == Decimal("800000")  # 1M × 0.80
        assert tracker.reduction_level == 1
        assert tracker.reduction_applied is True

    def test_20_pct_drawdown_cascades_to_64_pct(self):
        """Rule 5: 20% drawdown -> cascading reduction (notional = 64%)."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))

        # 20% drawdown
        tracker.update_equity(Decimal("800000"))

        # Two levels of 20% reduction: 0.80 × 0.80 = 0.64
        assert tracker.actual_equity == Decimal("800000")
        assert tracker.notional_equity == Decimal("640000")  # 1M × 0.64
        assert tracker.reduction_level == 2

    def test_30_pct_drawdown_cascades_to_512_pct(self):
        """Rule 5: 30% drawdown -> three levels (notional = 51.2%)."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))

        # 30% drawdown
        tracker.update_equity(Decimal("700000"))

        # Three levels: 0.80^3 = 0.512
        assert tracker.actual_equity == Decimal("700000")
        assert tracker.notional_equity == Decimal("512000")  # 1M × 0.512
        assert tracker.reduction_level == 3

    def test_cascading_reductions_applied_incrementally(self):
        """Cascading reductions applied as we cross each 10% level."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))

        # First drop to 10% DD
        tracker.update_equity(Decimal("900000"))
        assert tracker.notional_equity == Decimal("800000")  # Level 1
        assert tracker.reduction_level == 1

        # Further drop to 20% DD
        tracker.update_equity(Decimal("800000"))
        # Should cascade from 800k * 0.80 = 640k
        assert tracker.notional_equity == Decimal("640000")  # Level 2
        assert tracker.reduction_level == 2

        # Further drop to 30% DD
        tracker.update_equity(Decimal("700000"))
        # Should cascade from 640k * 0.80 = 512k
        assert tracker.notional_equity == Decimal("512000")  # Level 3
        assert tracker.reduction_level == 3

    def test_drawdown_under_threshold_no_reduction(self):
        """Drawdown under 10% does not trigger reduction.

        When under threshold, notional stays at yearly starting equity
        (no penalty applied). This is correct Rule 5 behavior - you
        don't start reducing until you hit the 10% threshold.
        """
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))

        # 9% drawdown
        tracker.update_equity(Decimal("910000"))

        # Notional stays at yearly start - no reduction triggered yet
        assert tracker.notional_equity == Decimal("1000000")
        assert tracker.reduction_level == 0
        assert tracker.reduction_applied is False

    def test_recovery_to_yearly_start_restores_full_size(self):
        """Rule 5: Recovery to yearly starting equity restores notional."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))

        # Draw down to 80%
        tracker.update_equity(Decimal("800000"))
        assert tracker.notional_equity == Decimal("640000")  # 2 levels

        # Recover to yearly start
        tracker.update_equity(Decimal("1000000"))
        assert tracker.notional_equity == Decimal("1000000")
        assert tracker.reduction_level == 0
        assert tracker.reduction_applied is False

    def test_partial_recovery_does_not_restore(self):
        """Partial recovery doesn't restore notional - must reach yearly start."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))

        # Draw down
        tracker.update_equity(Decimal("900000"))
        assert tracker.notional_equity == Decimal("800000")

        # Partial recovery to 95% (still below yearly start)
        tracker.update_equity(Decimal("950000"))
        # Notional stays at reduced level
        assert tracker.notional_equity == Decimal("800000")
        assert tracker.reduction_level == 1

    def test_new_high_above_yearly_start_restores(self):
        """New high above yearly start restores notional."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))

        # Draw down
        tracker.update_equity(Decimal("900000"))
        assert tracker.notional_equity == Decimal("800000")

        # New high above yearly start
        tracker.update_equity(Decimal("1100000"))
        assert tracker.notional_equity == Decimal("1100000")
        assert tracker.reduction_level == 0

    def test_drawdown_pct_from_yearly_start(self):
        """drawdown_pct calculates from yearly starting equity."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))

        tracker.update_equity(Decimal("850000"))

        assert tracker.drawdown_pct == Decimal("0.15")  # 15%

    def test_is_in_drawdown_property(self):
        """is_in_drawdown reflects threshold breach."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))

        tracker.update_equity(Decimal("910000"))
        assert not tracker.is_in_drawdown  # 9% < 10%

        tracker.update_equity(Decimal("890000"))
        assert tracker.is_in_drawdown  # 11% >= 10%

    def test_reset_year(self):
        """reset_year resets yearly starting equity and all tracking."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))
        tracker.update_equity(Decimal("800000"))

        # Reset for new year with current equity
        tracker.reset_year(Decimal("800000"))

        assert tracker.yearly_starting_equity == Decimal("800000")
        assert tracker.actual_equity == Decimal("800000")
        assert tracker.notional_equity == Decimal("800000")
        assert tracker.reduction_level == 0
        assert not tracker.reduction_applied

    def test_reset_peak_alias(self):
        """reset_peak is alias for reset_year (backwards compatibility)."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))
        tracker.update_equity(Decimal("800000"))

        tracker.reset_peak(Decimal("900000"))

        assert tracker.yearly_starting_equity == Decimal("900000")
        assert tracker.notional_equity == Decimal("900000")
        assert tracker.reduction_level == 0

    def test_peak_equity_alias(self):
        """peak_equity is alias for yearly_starting_equity."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))

        assert tracker.peak_equity == Decimal("1000000")
        assert tracker.peak_equity == tracker.yearly_starting_equity

    def test_custom_thresholds(self):
        """Can use custom threshold and reduction."""
        tracker = DrawdownTracker(
            yearly_starting_equity=Decimal("100000"),
            drawdown_threshold=Decimal("0.05"),  # 5%
            reduction_factor=Decimal("0.25"),  # 25%
        )

        # 6% drawdown (crosses 5% threshold once)
        tracker.update_equity(Decimal("94000"))

        # Notional = 100k × 0.75 = 75k
        assert tracker.notional_equity == Decimal("75000")
        assert tracker.reduction_level == 1

    def test_example_from_turtle_advisor(self):
        """Test the exact example from the Turtle advisor."""
        # Year starts: $1,000,000 (yearly starting equity)
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))

        # Drawdown 10%: Equity = $900,000 -> Trade as if $800,000
        tracker.update_equity(Decimal("900000"))
        assert tracker.notional_equity == Decimal("800000")

        # Drawdown 20%: Equity = $800,000 -> Trade as if $640,000
        tracker.update_equity(Decimal("800000"))
        assert tracker.notional_equity == Decimal("640000")

        # Recovery: When equity returns to $1,000,000 -> Restore full size
        tracker.update_equity(Decimal("1000000"))
        assert tracker.notional_equity == Decimal("1000000")
        assert tracker.reduction_level == 0

    def test_reduction_stays_until_yearly_start_recovery(self):
        """Reduction persists until recovery to yearly start, not just improvement."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))

        # Draw down to 15% (level 1)
        tracker.update_equity(Decimal("850000"))
        assert tracker.notional_equity == Decimal("800000")

        # Improve to 5% DD (still below yearly start)
        tracker.update_equity(Decimal("950000"))
        # Still at level 1 - notional unchanged
        assert tracker.notional_equity == Decimal("800000")
        assert tracker.reduction_level == 1


class TestEquityStateConversion:
    """Tests for EquityState conversion."""

    def test_to_equity_state(self):
        """Convert tracker to EquityState."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("1000000"))
        tracker.update_equity(Decimal("900000"))

        state = tracker.to_equity_state()

        assert isinstance(state, EquityState)
        assert state.actual == Decimal("900000")
        assert state.notional == Decimal("800000")
        assert state.peak == Decimal("1000000")  # yearly_starting_equity

    def test_from_equity_state(self):
        """Create tracker from EquityState."""
        state = EquityState(
            actual=Decimal("900000"),
            notional=Decimal("800000"),
            peak=Decimal("1000000"),
        )

        tracker = DrawdownTracker.from_equity_state(state)

        assert tracker.actual_equity == Decimal("900000")
        assert tracker.notional_equity == Decimal("800000")
        assert tracker.yearly_starting_equity == Decimal("1000000")
        assert tracker.reduction_level == 1

    def test_from_equity_state_multiple_levels(self):
        """Reconstructs multiple reduction levels from state."""
        state = EquityState(
            actual=Decimal("800000"),
            notional=Decimal("640000"),  # 2 levels: 0.80^2 = 0.64
            peak=Decimal("1000000"),
        )

        tracker = DrawdownTracker.from_equity_state(state)

        assert tracker.reduction_level == 2


class TestCalculateNotionalEquity:
    """Tests for pure function calculate_notional_equity."""

    def test_no_drawdown(self):
        """At yearly start, notional = actual."""
        notional = calculate_notional_equity(
            actual_equity=Decimal("1000000"),
            yearly_starting_equity=Decimal("1000000"),
        )

        assert notional == Decimal("1000000")

    def test_above_yearly_start(self):
        """Above yearly start, notional = actual."""
        notional = calculate_notional_equity(
            actual_equity=Decimal("1100000"),
            yearly_starting_equity=Decimal("1000000"),
        )

        assert notional == Decimal("1100000")

    def test_small_drawdown(self):
        """Small drawdown (< 10%), notional = yearly start (no reduction)."""
        notional = calculate_notional_equity(
            actual_equity=Decimal("950000"),
            yearly_starting_equity=Decimal("1000000"),
        )

        # Under threshold: notional = yearly start (no reduction triggered)
        assert notional == Decimal("1000000")

    def test_10_pct_drawdown(self):
        """10% drawdown -> 80% notional."""
        notional = calculate_notional_equity(
            actual_equity=Decimal("900000"),
            yearly_starting_equity=Decimal("1000000"),
        )

        assert notional == Decimal("800000")  # 1M × 0.80

    def test_20_pct_drawdown(self):
        """20% drawdown -> 64% notional (cascading)."""
        notional = calculate_notional_equity(
            actual_equity=Decimal("800000"),
            yearly_starting_equity=Decimal("1000000"),
        )

        assert notional == Decimal("640000")  # 1M × 0.64

    def test_30_pct_drawdown(self):
        """30% drawdown -> 51.2% notional (cascading)."""
        notional = calculate_notional_equity(
            actual_equity=Decimal("700000"),
            yearly_starting_equity=Decimal("1000000"),
        )

        assert notional == Decimal("512000")  # 1M × 0.512


class TestEquityState:
    """Tests for EquityState model."""

    def test_initial_creation(self):
        """Create initial equity state."""
        state = EquityState.initial(Decimal("100000"))

        assert state.actual == Decimal("100000")
        assert state.notional == Decimal("100000")
        assert state.peak == Decimal("100000")

    def test_drawdown_pct(self):
        """drawdown_pct computed correctly."""
        state = EquityState(
            actual=Decimal("85000"),
            notional=Decimal("80000"),
            peak=Decimal("100000"),
        )

        assert state.drawdown_pct == Decimal("0.15")

    def test_is_in_drawdown(self):
        """is_in_drawdown property."""
        at_peak = EquityState.initial(Decimal("100000"))
        assert not at_peak.is_in_drawdown

        in_drawdown = EquityState(
            actual=Decimal("90000"),
            notional=Decimal("80000"),
            peak=Decimal("100000"),
        )
        assert in_drawdown.is_in_drawdown

    def test_reduction_applied(self):
        """reduction_applied property."""
        no_reduction = EquityState(
            actual=Decimal("95000"),
            notional=Decimal("95000"),
            peak=Decimal("100000"),
        )
        assert not no_reduction.reduction_applied

        with_reduction = EquityState(
            actual=Decimal("89000"),
            notional=Decimal("80000"),
            peak=Decimal("100000"),
        )
        assert with_reduction.reduction_applied

    def test_with_equity(self):
        """with_equity creates new state."""
        state = EquityState.initial(Decimal("100000"))

        new_state = state.with_equity(
            new_actual=Decimal("110000"),
            new_notional=Decimal("110000"),
        )

        assert new_state.actual == Decimal("110000")
        assert new_state.notional == Decimal("110000")
        assert new_state.peak == Decimal("110000")  # Updated to new high
        # Original unchanged (immutable)
        assert state.actual == Decimal("100000")

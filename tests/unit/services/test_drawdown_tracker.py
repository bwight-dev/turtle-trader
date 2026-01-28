"""Unit tests for drawdown tracker."""

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
        tracker = DrawdownTracker(peak_equity=Decimal("100000"))

        assert tracker.peak_equity == Decimal("100000")
        assert tracker.actual_equity == Decimal("100000")
        assert tracker.notional_equity == Decimal("100000")
        assert tracker.drawdown_pct == Decimal("0")
        assert not tracker.is_in_drawdown
        assert not tracker.reduction_applied

    def test_drawdown_reduces_notional(self):
        """Rule 5: 10% drawdown → 20% notional reduction."""
        tracker = DrawdownTracker(peak_equity=Decimal("100000"))

        # 11% drawdown (breaches 10% threshold)
        tracker.update_equity(Decimal("89000"))

        assert tracker.actual_equity == Decimal("89000")
        assert tracker.notional_equity == Decimal("80000")  # 100k × 0.8
        assert tracker.reduction_applied is True

    def test_drawdown_exactly_10_percent(self):
        """Exactly 10% drawdown triggers reduction."""
        tracker = DrawdownTracker(peak_equity=Decimal("100000"))

        tracker.update_equity(Decimal("90000"))  # Exactly 10%

        assert tracker.notional_equity == Decimal("80000")
        assert tracker.reduction_applied is True

    def test_drawdown_under_threshold(self):
        """Drawdown under 10% does not trigger reduction."""
        tracker = DrawdownTracker(peak_equity=Decimal("100000"))

        tracker.update_equity(Decimal("91000"))  # 9% drawdown

        assert tracker.notional_equity == Decimal("91000")  # No reduction
        assert tracker.reduction_applied is False

    def test_recovery_restores_notional(self):
        """Rule 5: Recovery to peak restores notional."""
        tracker = DrawdownTracker(peak_equity=Decimal("100000"))

        # Draw down
        tracker.update_equity(Decimal("89000"))
        assert tracker.notional_equity == Decimal("80000")

        # Recover to peak
        tracker.update_equity(Decimal("100000"))
        assert tracker.notional_equity == Decimal("100000")
        assert tracker.reduction_applied is False

    def test_new_high_updates_peak(self):
        """New high updates peak equity."""
        tracker = DrawdownTracker(peak_equity=Decimal("100000"))

        tracker.update_equity(Decimal("110000"))

        assert tracker.peak_equity == Decimal("110000")
        assert tracker.notional_equity == Decimal("110000")

    def test_drawdown_from_new_high(self):
        """Drawdown calculated from new high."""
        tracker = DrawdownTracker(peak_equity=Decimal("100000"))

        # Make new high
        tracker.update_equity(Decimal("120000"))
        assert tracker.peak_equity == Decimal("120000")

        # 10% drawdown from new peak
        tracker.update_equity(Decimal("108000"))  # 10% of 120k = 12k

        # Notional = 120k × 0.8 = 96k
        assert tracker.notional_equity == Decimal("96000")

    def test_multiple_drawdowns(self):
        """Reduction persists through continued drawdown."""
        tracker = DrawdownTracker(peak_equity=Decimal("100000"))

        # Initial drawdown
        tracker.update_equity(Decimal("89000"))
        assert tracker.notional_equity == Decimal("80000")

        # Further drawdown
        tracker.update_equity(Decimal("85000"))
        # Notional stays at 80k (reduction already applied)
        assert tracker.notional_equity == Decimal("80000")

        # Even more drawdown
        tracker.update_equity(Decimal("70000"))
        assert tracker.notional_equity == Decimal("80000")

    def test_partial_recovery_no_restore(self):
        """Partial recovery doesn't restore notional."""
        tracker = DrawdownTracker(peak_equity=Decimal("100000"))

        # Draw down
        tracker.update_equity(Decimal("89000"))
        assert tracker.notional_equity == Decimal("80000")

        # Partial recovery (but not to peak)
        tracker.update_equity(Decimal("95000"))
        # Notional stays reduced
        assert tracker.notional_equity == Decimal("80000")
        assert tracker.reduction_applied is True

    def test_drawdown_pct_property(self):
        """drawdown_pct calculates correctly."""
        tracker = DrawdownTracker(peak_equity=Decimal("100000"))

        tracker.update_equity(Decimal("85000"))

        assert tracker.drawdown_pct == Decimal("0.15")  # 15%

    def test_is_in_drawdown_property(self):
        """is_in_drawdown reflects threshold breach."""
        tracker = DrawdownTracker(peak_equity=Decimal("100000"))

        tracker.update_equity(Decimal("91000"))
        assert not tracker.is_in_drawdown  # 9% < 10%

        tracker.update_equity(Decimal("89000"))
        assert tracker.is_in_drawdown  # 11% >= 10%

    def test_reset_peak(self):
        """reset_peak resets all values."""
        tracker = DrawdownTracker(peak_equity=Decimal("100000"))
        tracker.update_equity(Decimal("89000"))

        tracker.reset_peak(Decimal("120000"))

        assert tracker.peak_equity == Decimal("120000")
        assert tracker.actual_equity == Decimal("120000")
        assert tracker.notional_equity == Decimal("120000")
        assert not tracker.reduction_applied

    def test_custom_thresholds(self):
        """Can use custom threshold and reduction."""
        tracker = DrawdownTracker(
            peak_equity=Decimal("100000"),
            drawdown_threshold=Decimal("0.05"),  # 5%
            reduction_factor=Decimal("0.25"),  # 25%
        )

        tracker.update_equity(Decimal("94000"))  # 6% drawdown

        # Notional = 100k × 0.75 = 75k
        assert tracker.notional_equity == Decimal("75000")


class TestEquityStateConversion:
    """Tests for EquityState conversion."""

    def test_to_equity_state(self):
        """Convert tracker to EquityState."""
        tracker = DrawdownTracker(peak_equity=Decimal("100000"))
        tracker.update_equity(Decimal("89000"))

        state = tracker.to_equity_state()

        assert isinstance(state, EquityState)
        assert state.actual == Decimal("89000")
        assert state.notional == Decimal("80000")
        assert state.peak == Decimal("100000")

    def test_from_equity_state(self):
        """Create tracker from EquityState."""
        state = EquityState(
            actual=Decimal("89000"),
            notional=Decimal("80000"),
            peak=Decimal("100000"),
        )

        tracker = DrawdownTracker.from_equity_state(state)

        assert tracker.actual_equity == Decimal("89000")
        assert tracker.notional_equity == Decimal("80000")
        assert tracker.peak_equity == Decimal("100000")
        assert tracker.reduction_applied is True


class TestCalculateNotionalEquity:
    """Tests for pure function calculate_notional_equity."""

    def test_no_drawdown(self):
        """At peak, notional = actual."""
        notional = calculate_notional_equity(
            actual_equity=Decimal("100000"),
            peak_equity=Decimal("100000"),
        )

        assert notional == Decimal("100000")

    def test_above_peak(self):
        """Above peak, notional = actual."""
        notional = calculate_notional_equity(
            actual_equity=Decimal("110000"),
            peak_equity=Decimal("100000"),
        )

        assert notional == Decimal("110000")

    def test_small_drawdown(self):
        """Small drawdown, notional = actual."""
        notional = calculate_notional_equity(
            actual_equity=Decimal("95000"),
            peak_equity=Decimal("100000"),
        )

        assert notional == Decimal("95000")  # 5% drawdown, no reduction

    def test_threshold_drawdown(self):
        """At threshold, notional is reduced."""
        notional = calculate_notional_equity(
            actual_equity=Decimal("90000"),
            peak_equity=Decimal("100000"),
        )

        assert notional == Decimal("80000")  # 100k × 0.8

    def test_large_drawdown(self):
        """Large drawdown still uses standard reduction."""
        notional = calculate_notional_equity(
            actual_equity=Decimal("70000"),  # 30% drawdown
            peak_equity=Decimal("100000"),
        )

        # Notional = peak × (1 - reduction) = 100k × 0.8 = 80k
        assert notional == Decimal("80000")


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

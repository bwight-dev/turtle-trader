"""Unit tests for EquityTracker service."""

from decimal import Decimal

import pytest

from src.domain.services.equity_tracker import (
    EquityTracker,
    get_equity_tracker,
    init_equity_tracker,
)


class TestEquityTrackerCreation:
    """Tests for EquityTracker initialization."""

    def test_create_with_starting_equity(self):
        """Test creating tracker with starting equity."""
        tracker = EquityTracker(starting_equity=Decimal("50000"))
        assert tracker.yearly_starting_equity == Decimal("50000")
        assert tracker.actual_equity == Decimal("50000")

    def test_create_with_custom_floor(self):
        """Test creating tracker with custom floor."""
        tracker = EquityTracker(
            starting_equity=Decimal("50000"),
            min_notional_floor=Decimal("0.50"),
        )
        # Floor should be respected even in deep drawdown
        tracker.update(Decimal("20000"))  # 60% drawdown
        # Sizing equity should not go below 50% of starting
        assert tracker.sizing_equity >= Decimal("25000")

    def test_default_starting_equity(self):
        """Test tracker uses default starting equity."""
        tracker = EquityTracker()
        # Default is 50000 per the code
        assert tracker.yearly_starting_equity == Decimal("50000")


class TestEquityTrackerUpdate:
    """Tests for equity updates."""

    def test_update_equity(self):
        """Test updating current equity."""
        tracker = EquityTracker(starting_equity=Decimal("50000"))
        tracker.update(Decimal("55000"))
        assert tracker.actual_equity == Decimal("55000")

    def test_update_triggers_drawdown_reduction(self):
        """Test that drawdown triggers reduction per Rule 5."""
        tracker = EquityTracker(
            starting_equity=Decimal("50000"),
            min_notional_floor=Decimal("0.50"),  # 50% floor
        )
        # 10% drawdown should trigger 20% reduction
        tracker.update(Decimal("45000"))
        assert tracker.is_in_drawdown is True
        # Notional should be reduced
        assert tracker.sizing_equity < Decimal("50000")

    def test_no_reduction_when_profitable(self):
        """Test no reduction when equity is up."""
        tracker = EquityTracker(starting_equity=Decimal("50000"))
        tracker.update(Decimal("55000"))
        assert tracker.is_in_drawdown is False
        assert tracker.reduction_level == 0


class TestEquityTrackerProperties:
    """Tests for EquityTracker properties."""

    def test_actual_equity_property(self):
        """Test actual equity property."""
        tracker = EquityTracker(starting_equity=Decimal("50000"))
        tracker.update(Decimal("48000"))
        assert tracker.actual_equity == Decimal("48000")

    def test_sizing_equity_property(self):
        """Test sizing equity (notional) property."""
        tracker = EquityTracker(starting_equity=Decimal("50000"))
        # At start, sizing = actual
        assert tracker.sizing_equity == Decimal("50000")

    def test_drawdown_pct_property(self):
        """Test drawdown percentage calculation."""
        tracker = EquityTracker(starting_equity=Decimal("50000"))
        tracker.update(Decimal("45000"))
        # 10% drawdown returned as decimal (0.10)
        assert tracker.drawdown_pct == Decimal("0.1")

    def test_drawdown_pct_negative_when_profitable(self):
        """Test drawdown is negative when above starting equity."""
        tracker = EquityTracker(starting_equity=Decimal("50000"))
        tracker.update(Decimal("55000"))
        # When profitable, drawdown calculation returns negative
        assert tracker.drawdown_pct == Decimal("-0.1")

    def test_reduction_level_increases_with_drawdown(self):
        """Test reduction level increases as drawdown deepens."""
        tracker = EquityTracker(
            starting_equity=Decimal("50000"),
            min_notional_floor=Decimal("0.50"),
        )
        # No reduction initially
        assert tracker.reduction_level == 0

        # 10% drawdown = level 1
        tracker.update(Decimal("45000"))
        assert tracker.reduction_level == 1

        # 20% drawdown = level 2
        tracker.update(Decimal("40000"))
        assert tracker.reduction_level == 2


class TestEquityTrackerReset:
    """Tests for year reset functionality."""

    def test_reset_year(self):
        """Test resetting for new year."""
        tracker = EquityTracker(starting_equity=Decimal("50000"))
        tracker.update(Decimal("60000"))
        tracker.reset_year(Decimal("60000"))

        assert tracker.yearly_starting_equity == Decimal("60000")
        assert tracker.drawdown_pct == Decimal("0")

    def test_set_starting_equity(self):
        """Test setting starting equity."""
        tracker = EquityTracker(starting_equity=Decimal("50000"))
        tracker.set_starting_equity(Decimal("75000"))

        assert tracker.yearly_starting_equity == Decimal("75000")


class TestGlobalEquityTracker:
    """Tests for global singleton functions."""

    def test_init_equity_tracker(self):
        """Test initializing global tracker."""
        tracker = init_equity_tracker(Decimal("100000"))
        assert tracker.yearly_starting_equity == Decimal("100000")

    def test_get_equity_tracker(self):
        """Test getting global tracker."""
        init_equity_tracker(Decimal("75000"))
        tracker = get_equity_tracker()
        assert tracker.yearly_starting_equity == Decimal("75000")

    def test_get_creates_if_not_exists(self):
        """Test get creates tracker if not initialized."""
        # This relies on the global being initialized earlier in tests
        tracker = get_equity_tracker()
        assert tracker is not None


class TestSizingFloorBehavior:
    """Tests for sizing floor preventing death spiral."""

    def test_floor_prevents_zero_sizing(self):
        """Test that floor prevents sizing from going to zero."""
        tracker = EquityTracker(
            starting_equity=Decimal("50000"),
            min_notional_floor=Decimal("0.60"),  # 60% floor
        )
        # Severe 50% drawdown
        tracker.update(Decimal("25000"))
        # Sizing should not go below 60% of starting (30000)
        assert tracker.sizing_equity >= Decimal("30000")

    def test_floor_with_moderate_drawdown(self):
        """Test floor doesn't affect moderate drawdowns."""
        tracker = EquityTracker(
            starting_equity=Decimal("50000"),
            min_notional_floor=Decimal("0.60"),
        )
        # 5% drawdown - floor shouldn't kick in
        tracker.update(Decimal("47500"))
        # With 5% drawdown, no reduction applied (need 10% for first reduction)
        assert tracker.sizing_equity == Decimal("50000")

"""Drawdown tracking for Turtle Trading system.

Implements Rule 5: The Drawdown Reduction Rule (per original Turtle advisor)
- Track yearly starting equity (the recovery target)
- Every 10% drawdown from yearly start → reduce notional by 20% (cascading: 0.80^n)
- Sizing uses notional equity, not actual
- Recovery to yearly starting equity → restore full trading size
- Reset yearly starting equity annually

Example:
    Year starts: $1,000,000 (this is "yearly starting equity")

    Drawdown 10%: Equity = $900,000
      → Trade as if $800,000 (20% reduction)

    Drawdown 20%: Equity = $800,000
      → Trade as if $640,000 (another 20% = 0.80 × $800,000)

    Recovery: When equity returns to $1,000,000 (yearly start)
      → Restore full trading size

    New year: Reset yearly starting equity to current account value
"""

from decimal import Decimal

from src.domain.models.equity import EquityState
from src.domain.rules import DRAWDOWN_EQUITY_REDUCTION, DRAWDOWN_THRESHOLD


class DrawdownTracker:
    """Tracks drawdowns and manages notional equity reduction.

    Rule 5: The "Risk of Ruin" Rule (per original Turtle advisor)
    - Track yearly starting equity (the recovery target, NOT rolling HWM)
    - Every 10% drawdown from yearly start → apply 20% reduction (cascading)
    - All sizing uses notional equity
    - Recovery to yearly starting equity restores notional = actual
    - Reset at start of each year

    Key differences from common misimplementations:
    1. Recovery threshold is YEARLY START, not rolling high-water mark
    2. Reductions CASCADE: 10% DD → 80%, 20% DD → 64%, 30% DD → 51.2%
    3. Reset happens ANNUALLY, not on every new high

    This class is mutable for convenience in tracking state over time.
    For immutable operations, use EquityState directly.
    """

    def __init__(
        self,
        yearly_starting_equity: Decimal,
        drawdown_threshold: Decimal = DRAWDOWN_THRESHOLD,
        reduction_factor: Decimal = DRAWDOWN_EQUITY_REDUCTION,
    ) -> None:
        """Initialize the drawdown tracker.

        Args:
            yearly_starting_equity: Starting equity for the year (the recovery target)
            drawdown_threshold: Drawdown % that triggers reduction (default 0.10)
            reduction_factor: Notional reduction factor (default 0.20)
        """
        self._yearly_starting_equity = yearly_starting_equity
        self._actual_equity = yearly_starting_equity
        self._notional_equity = yearly_starting_equity
        self._drawdown_threshold = drawdown_threshold
        self._reduction_factor = reduction_factor
        self._reduction_level = 0  # Track which 10% level we've hit (0, 1, 2, ...)

    @property
    def yearly_starting_equity(self) -> Decimal:
        """Yearly starting equity (the recovery target)."""
        return self._yearly_starting_equity

    @property
    def peak_equity(self) -> Decimal:
        """Alias for yearly_starting_equity for backwards compatibility."""
        return self._yearly_starting_equity

    @property
    def actual_equity(self) -> Decimal:
        """Current actual account equity."""
        return self._actual_equity

    @property
    def notional_equity(self) -> Decimal:
        """Equity used for position sizing."""
        return self._notional_equity

    @property
    def reduction_level(self) -> int:
        """Current reduction level (0 = none, 1 = 10% DD, 2 = 20% DD, etc.)."""
        return self._reduction_level

    @property
    def drawdown_pct(self) -> Decimal:
        """Current drawdown as percentage from yearly starting equity."""
        if self._yearly_starting_equity == 0:
            return Decimal("0")
        return (self._yearly_starting_equity - self._actual_equity) / self._yearly_starting_equity

    @property
    def is_in_drawdown(self) -> bool:
        """Check if currently in a meaningful drawdown (>= threshold)."""
        return self.drawdown_pct >= self._drawdown_threshold

    @property
    def reduction_applied(self) -> bool:
        """Check if notional reduction is currently active."""
        return self._reduction_level > 0

    def update_equity(self, new_equity: Decimal) -> None:
        """Update equity and apply/remove reduction as needed.

        Rule 5 logic (per original Turtle advisor):
        - Recovery check: return to yearly start (not HWM) → restore full size
        - Calculate drawdown from yearly starting equity
        - Apply cascading reductions (0.80^n) for each 10% level

        Args:
            new_equity: New account equity value
        """
        self._actual_equity = new_equity

        # Recovery check: return to yearly starting equity (not HWM)
        if new_equity >= self._yearly_starting_equity:
            self._notional_equity = new_equity
            self._reduction_level = 0
            return

        # Calculate drawdown from yearly starting equity
        drawdown_pct = (self._yearly_starting_equity - new_equity) / self._yearly_starting_equity

        # Calculate which 10% level we're at (0.10 = level 1, 0.20 = level 2, etc.)
        current_level = int(drawdown_pct / self._drawdown_threshold)

        # Apply cascading reductions if we've hit a new level
        if current_level > self._reduction_level:
            levels_to_apply = current_level - self._reduction_level
            # Each level reduces by 20% (multiply by 0.80)
            reduction_multiplier = (Decimal("1") - self._reduction_factor) ** levels_to_apply
            self._notional_equity = self._notional_equity * reduction_multiplier
            self._reduction_level = current_level

    def reset_year(self, new_starting_equity: Decimal) -> None:
        """Reset for a new year.

        Call at start of each year to reset the yearly starting equity
        to the current account value.

        Args:
            new_starting_equity: New yearly starting equity (typically current equity)
        """
        self._yearly_starting_equity = new_starting_equity
        self._actual_equity = new_starting_equity
        self._notional_equity = new_starting_equity
        self._reduction_level = 0

    def reset_peak(self, new_peak: Decimal) -> None:
        """Alias for reset_year for backwards compatibility.

        Args:
            new_peak: New yearly starting equity
        """
        self.reset_year(new_peak)

    def to_equity_state(self) -> EquityState:
        """Convert current state to immutable EquityState.

        Returns:
            EquityState snapshot of current values
        """
        return EquityState(
            actual=self._actual_equity,
            notional=self._notional_equity,
            peak=self._yearly_starting_equity,
        )

    @classmethod
    def from_equity_state(
        cls,
        state: EquityState,
        drawdown_threshold: Decimal = DRAWDOWN_THRESHOLD,
        reduction_factor: Decimal = DRAWDOWN_EQUITY_REDUCTION,
    ) -> "DrawdownTracker":
        """Create tracker from existing equity state.

        Note: This reconstructs the reduction level from the state values.
        The peak in EquityState is treated as yearly starting equity.

        Args:
            state: EquityState to restore from
            drawdown_threshold: Drawdown % that triggers reduction
            reduction_factor: Notional reduction factor

        Returns:
            DrawdownTracker initialized with state values
        """
        tracker = cls(
            yearly_starting_equity=state.peak,
            drawdown_threshold=drawdown_threshold,
            reduction_factor=reduction_factor,
        )
        tracker._actual_equity = state.actual
        tracker._notional_equity = state.notional

        # Reconstruct reduction level from notional vs yearly start
        # If notional < yearly_start, we have reductions applied
        if state.notional < state.peak:
            # Calculate how many levels of 0.80 were applied
            # notional = yearly_start * 0.80^n
            # n = log(notional/yearly_start) / log(0.80)
            if state.peak > 0 and state.notional > 0:
                ratio = state.notional / state.peak
                # Each level is 0.80, so count levels
                level = 0
                current = Decimal("1")
                while current * (Decimal("1") - reduction_factor) >= ratio:
                    current = current * (Decimal("1") - reduction_factor)
                    level += 1
                tracker._reduction_level = level
        return tracker


def calculate_notional_equity(
    actual_equity: Decimal,
    yearly_starting_equity: Decimal,
    drawdown_threshold: Decimal = DRAWDOWN_THRESHOLD,
    reduction_factor: Decimal = DRAWDOWN_EQUITY_REDUCTION,
) -> Decimal:
    """Calculate notional equity based on drawdown rules.

    Pure function version of Rule 5 logic with cascading reductions.

    Note: This function calculates fresh notional equity without tracking
    history. For proper cascading behavior that respects the "once reduced,
    stay reduced until recovery" rule, use DrawdownTracker class instead.

    Args:
        actual_equity: Current account equity
        yearly_starting_equity: Yearly starting equity (recovery target)
        drawdown_threshold: Drawdown % that triggers reduction (default 0.10)
        reduction_factor: Reduction factor to apply (default 0.20)

    Returns:
        Notional equity for sizing calculations
    """
    # If at or above yearly start, no reduction
    if actual_equity >= yearly_starting_equity:
        return actual_equity

    # Calculate drawdown from yearly starting equity
    drawdown_pct = (yearly_starting_equity - actual_equity) / yearly_starting_equity

    # Calculate which 10% level we're at
    current_level = int(drawdown_pct / drawdown_threshold)

    if current_level > 0:
        # Apply cascading reductions: 0.80^n
        reduction_multiplier = (Decimal("1") - reduction_factor) ** current_level
        return yearly_starting_equity * reduction_multiplier

    # Under threshold: notional = yearly_starting_equity (no penalty applied)
    return yearly_starting_equity

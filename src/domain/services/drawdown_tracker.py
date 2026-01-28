"""Drawdown tracking for Turtle Trading system.

Implements Rule 5: The Drawdown Reduction Rule
- When equity drops 10% from peak → reduce notional equity by 20%
- Sizing uses notional equity, not actual
- When equity recovers to peak → restore notional = actual
"""

from decimal import Decimal

from src.domain.models.equity import EquityState
from src.domain.rules import DRAWDOWN_EQUITY_REDUCTION, DRAWDOWN_THRESHOLD


class DrawdownTracker:
    """Tracks drawdowns and manages notional equity reduction.

    Rule 5: The "Risk of Ruin" Rule
    - Track peak equity (starting or annual high)
    - When equity drops 10% from peak → reduce notional by 20%
    - All sizing uses notional equity
    - Recovery to peak restores notional = actual

    This class is mutable for convenience in tracking state over time.
    For immutable operations, use EquityState directly.
    """

    def __init__(
        self,
        peak_equity: Decimal,
        drawdown_threshold: Decimal = DRAWDOWN_THRESHOLD,
        reduction_factor: Decimal = DRAWDOWN_EQUITY_REDUCTION,
    ) -> None:
        """Initialize the drawdown tracker.

        Args:
            peak_equity: Starting/peak equity level
            drawdown_threshold: Drawdown % that triggers reduction (default 0.10)
            reduction_factor: Notional reduction factor (default 0.20)
        """
        self._peak_equity = peak_equity
        self._actual_equity = peak_equity
        self._notional_equity = peak_equity
        self._drawdown_threshold = drawdown_threshold
        self._reduction_factor = reduction_factor
        self._reduction_applied = False

    @property
    def peak_equity(self) -> Decimal:
        """High-water mark equity."""
        return self._peak_equity

    @property
    def actual_equity(self) -> Decimal:
        """Current actual account equity."""
        return self._actual_equity

    @property
    def notional_equity(self) -> Decimal:
        """Equity used for position sizing."""
        return self._notional_equity

    @property
    def drawdown_pct(self) -> Decimal:
        """Current drawdown as percentage."""
        if self._peak_equity == 0:
            return Decimal("0")
        return (self._peak_equity - self._actual_equity) / self._peak_equity

    @property
    def is_in_drawdown(self) -> bool:
        """Check if currently in a meaningful drawdown."""
        return self.drawdown_pct >= self._drawdown_threshold

    @property
    def reduction_applied(self) -> bool:
        """Check if notional reduction is currently active."""
        return self._reduction_applied

    def update_equity(self, new_equity: Decimal) -> None:
        """Update equity and apply/remove reduction as needed.

        Rule 5 logic:
        - If equity recovers to peak → restore notional = actual
        - If drawdown exceeds 10% → reduce notional by 20% of PEAK
        - Reduction persists until full recovery to peak
        - Under threshold (no prior reduction), notional = actual

        Args:
            new_equity: New account equity value
        """
        self._actual_equity = new_equity

        # Check for new peak (recovery)
        if new_equity >= self._peak_equity:
            self._peak_equity = new_equity
            self._notional_equity = new_equity
            self._reduction_applied = False
            return

        # If reduction already applied, keep it until full recovery
        if self._reduction_applied:
            # Notional stays at reduced level until recovery to peak
            return

        # Calculate current drawdown from peak
        current_drawdown = (self._peak_equity - new_equity) / self._peak_equity

        # Apply reduction if threshold breached
        if current_drawdown >= self._drawdown_threshold:
            # Reduce notional by reduction factor (e.g., 20%)
            # Notional = Peak × (1 - reduction_factor)
            self._notional_equity = self._peak_equity * (1 - self._reduction_factor)
            self._reduction_applied = True
        else:
            # Under threshold and no prior reduction: notional = actual
            self._notional_equity = new_equity

    def reset_peak(self, new_peak: Decimal) -> None:
        """Reset the peak equity (e.g., at start of new year).

        Args:
            new_peak: New peak equity level
        """
        self._peak_equity = new_peak
        self._actual_equity = new_peak
        self._notional_equity = new_peak
        self._reduction_applied = False

    def to_equity_state(self) -> EquityState:
        """Convert current state to immutable EquityState.

        Returns:
            EquityState snapshot of current values
        """
        return EquityState(
            actual=self._actual_equity,
            notional=self._notional_equity,
            peak=self._peak_equity,
        )

    @classmethod
    def from_equity_state(
        cls,
        state: EquityState,
        drawdown_threshold: Decimal = DRAWDOWN_THRESHOLD,
        reduction_factor: Decimal = DRAWDOWN_EQUITY_REDUCTION,
    ) -> "DrawdownTracker":
        """Create tracker from existing equity state.

        Args:
            state: EquityState to restore from
            drawdown_threshold: Drawdown % that triggers reduction
            reduction_factor: Notional reduction factor

        Returns:
            DrawdownTracker initialized with state values
        """
        tracker = cls(
            peak_equity=state.peak,
            drawdown_threshold=drawdown_threshold,
            reduction_factor=reduction_factor,
        )
        tracker._actual_equity = state.actual
        tracker._notional_equity = state.notional
        tracker._reduction_applied = state.notional < state.actual
        return tracker


def calculate_notional_equity(
    actual_equity: Decimal,
    peak_equity: Decimal,
    drawdown_threshold: Decimal = DRAWDOWN_THRESHOLD,
    reduction_factor: Decimal = DRAWDOWN_EQUITY_REDUCTION,
) -> Decimal:
    """Calculate notional equity based on drawdown rules.

    Pure function version of Rule 5 logic.

    Args:
        actual_equity: Current account equity
        peak_equity: High-water mark equity
        drawdown_threshold: Drawdown % that triggers reduction (default 0.10)
        reduction_factor: Reduction factor to apply (default 0.20)

    Returns:
        Notional equity for sizing calculations
    """
    # If at or above peak, no reduction
    if actual_equity >= peak_equity:
        return actual_equity

    # Calculate drawdown
    drawdown_pct = (peak_equity - actual_equity) / peak_equity

    # Apply reduction if threshold breached
    if drawdown_pct >= drawdown_threshold:
        return peak_equity * (1 - reduction_factor)

    # Otherwise, notional = actual
    return actual_equity

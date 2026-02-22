"""Equity tracking for live trading.

Provides notional equity calculation for position sizing,
matching the backtest behavior exactly.

Uses DrawdownTracker with configurable floor to prevent
the "death spiral" on small accounts.
"""

from decimal import Decimal

from src.domain.services.drawdown_tracker import DrawdownTracker
from src.infrastructure.config import get_settings


class EquityTracker:
    """Tracks equity and provides notional sizing equity.

    This class ensures live trading uses the same sizing logic
    as the backtest:
    - Track yearly starting equity
    - Apply Rule 5 drawdown reductions (10% DD → 20% reduction)
    - Apply configurable floor (default 60% for small accounts)

    Usage:
        tracker = EquityTracker(starting_equity=Decimal("50000"))
        tracker.update(current_equity=Decimal("45000"))
        sizing_equity = tracker.sizing_equity  # Returns notional, not actual
    """

    def __init__(
        self,
        starting_equity: Decimal | None = None,
        min_notional_floor: Decimal | None = None,
    ):
        """Initialize the equity tracker.

        Args:
            starting_equity: Yearly starting equity (uses current if None)
            min_notional_floor: Floor as fraction of starting (uses config if None)
        """
        settings = get_settings()

        # Get floor from config if not specified
        if min_notional_floor is None:
            min_notional_floor = settings.min_notional_floor

        # Default starting equity (will be updated on first broker sync)
        if starting_equity is None:
            starting_equity = Decimal("50000")

        self._drawdown_tracker = DrawdownTracker(
            yearly_starting_equity=starting_equity,
            min_notional_floor=min_notional_floor,
        )

    @property
    def actual_equity(self) -> Decimal:
        """Current actual account equity."""
        return self._drawdown_tracker.actual_equity

    @property
    def sizing_equity(self) -> Decimal:
        """Notional equity for position sizing.

        This is reduced during drawdowns (Rule 5) but never
        below the configured floor.
        """
        return self._drawdown_tracker.notional_equity

    @property
    def yearly_starting_equity(self) -> Decimal:
        """Yearly starting equity (recovery target)."""
        return self._drawdown_tracker.yearly_starting_equity

    @property
    def drawdown_pct(self) -> Decimal:
        """Current drawdown as percentage from yearly start."""
        return self._drawdown_tracker.drawdown_pct

    @property
    def is_in_drawdown(self) -> bool:
        """Check if currently in significant drawdown."""
        return self._drawdown_tracker.is_in_drawdown

    @property
    def reduction_level(self) -> int:
        """Current reduction level (0=none, 1=10% DD, 2=20% DD, etc.)."""
        return self._drawdown_tracker.reduction_level

    def update(self, current_equity: Decimal) -> None:
        """Update with current equity and apply Rule 5.

        Call this after each trade or daily to keep sizing accurate.

        Args:
            current_equity: Current account equity from broker
        """
        self._drawdown_tracker.update_equity(current_equity)

    def reset_year(self, new_starting_equity: Decimal) -> None:
        """Reset for new year (call annually).

        Args:
            new_starting_equity: New yearly starting equity
        """
        self._drawdown_tracker.reset_year(new_starting_equity)

    def set_starting_equity(self, equity: Decimal) -> None:
        """Set starting equity (use on first run or year reset).

        Args:
            equity: Starting equity value
        """
        self._drawdown_tracker.reset_year(equity)


# Singleton instance for live trading
_equity_tracker: EquityTracker | None = None


def get_equity_tracker() -> EquityTracker:
    """Get the global equity tracker instance.

    Returns:
        EquityTracker singleton
    """
    global _equity_tracker
    if _equity_tracker is None:
        _equity_tracker = EquityTracker()
    return _equity_tracker


def init_equity_tracker(starting_equity: Decimal) -> EquityTracker:
    """Initialize the global equity tracker with starting equity.

    Call this once at startup with the broker's account value.

    Args:
        starting_equity: Starting account equity

    Returns:
        Initialized EquityTracker
    """
    global _equity_tracker
    _equity_tracker = EquityTracker(starting_equity=starting_equity)
    return _equity_tracker

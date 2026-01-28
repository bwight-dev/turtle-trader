"""Equity state model for Turtle Trading system.

Tracks the distinction between actual equity and notional equity
as required by Rule 5 (Drawdown Reduction).
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, computed_field


class EquityState(BaseModel):
    """Tracks actual vs notional equity for position sizing.

    Rule 5: When drawdown exceeds 10%, reduce notional equity by 20%.
    All position sizing uses notional equity, not actual.

    This model is immutable - use update methods to get new state.
    """

    model_config = {"frozen": True}

    actual: Decimal = Field(..., description="Current account equity")
    notional: Decimal = Field(..., description="Equity used for sizing calculations")
    peak: Decimal = Field(..., description="High-water mark (starting or annual high)")
    updated_at: datetime = Field(default_factory=datetime.now)

    @computed_field
    @property
    def drawdown_pct(self) -> Decimal:
        """Current drawdown percentage from peak.

        Returns:
            Drawdown as percentage (e.g., 0.10 for 10% drawdown)
        """
        if self.peak == 0:
            return Decimal("0")
        return (self.peak - self.actual) / self.peak

    @computed_field
    @property
    def is_in_drawdown(self) -> bool:
        """Check if currently in a drawdown (actual below peak)."""
        return self.actual < self.peak

    @computed_field
    @property
    def reduction_applied(self) -> bool:
        """Check if notional reduction is currently applied."""
        return self.notional < self.actual

    @classmethod
    def initial(cls, starting_equity: Decimal) -> "EquityState":
        """Create initial equity state.

        Args:
            starting_equity: Starting account equity

        Returns:
            EquityState with all values equal to starting equity
        """
        return cls(
            actual=starting_equity,
            notional=starting_equity,
            peak=starting_equity,
        )

    def with_equity(
        self,
        new_actual: Decimal,
        new_notional: Decimal | None = None,
    ) -> "EquityState":
        """Create new state with updated equity values.

        Args:
            new_actual: New actual equity
            new_notional: New notional equity (default: unchanged)

        Returns:
            New EquityState with updated values
        """
        new_peak = max(self.peak, new_actual)
        return self.model_copy(
            update={
                "actual": new_actual,
                "notional": new_notional if new_notional is not None else self.notional,
                "peak": new_peak,
                "updated_at": datetime.now(),
            }
        )

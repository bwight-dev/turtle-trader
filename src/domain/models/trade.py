"""Trade audit record model for Turtle Trading system."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field

from src.domain.models.enums import Direction, System


class Trade(BaseModel):
    """Audit record of a completed trade.

    A trade is created when a position is closed, recording full lifecycle.
    Used for:
    - S1 filter (was last S1 trade a winner?)
    - Performance tracking
    - Tax records
    """

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    symbol: str
    direction: Direction
    system: System

    # Entry details
    entry_price: Decimal
    entry_date: datetime
    entry_contracts: int = Field(..., gt=0)
    n_at_entry: Decimal

    # Exit details
    exit_price: Decimal
    exit_date: datetime
    exit_reason: str = Field(..., description="stop, breakout, manual, etc.")

    # P&L
    realized_pnl: Decimal
    commission: Decimal = Field(default=Decimal("0"))

    # Pyramid info
    max_units: int = Field(default=1, description="Maximum units held during trade")

    @computed_field
    @property
    def holding_days(self) -> int:
        """Number of days position was held."""
        delta = self.exit_date - self.entry_date
        return delta.days

    @computed_field
    @property
    def net_pnl(self) -> Decimal:
        """Net P&L after commission."""
        return self.realized_pnl - self.commission

    @computed_field
    @property
    def is_winner(self) -> bool:
        """Check if this trade was profitable.

        Used for S1 filter: skip next S1 after winner.
        """
        return self.net_pnl > 0

    @computed_field
    @property
    def r_multiple(self) -> Decimal:
        """R-multiple: P&L expressed in terms of initial risk (2N).

        R = 1 means you made what you risked.
        R = 2 means you made 2x what you risked.
        """
        initial_risk = 2 * self.n_at_entry * self.entry_contracts
        if initial_risk == 0:
            return Decimal("0")
        return self.realized_pnl / initial_risk

    @classmethod
    def from_position_close(
        cls,
        symbol: str,
        direction: Direction,
        system: System,
        entry_price: Decimal,
        entry_date: datetime,
        entry_contracts: int,
        n_at_entry: Decimal,
        exit_price: Decimal,
        exit_date: datetime,
        exit_reason: str,
        point_value: Decimal,
        commission: Decimal = Decimal("0"),
        max_units: int = 1,
    ) -> "Trade":
        """Create a trade record from a closed position.

        Args:
            symbol: Traded symbol
            direction: Trade direction
            system: S1 or S2
            entry_price: Average entry price
            entry_date: When position was opened
            entry_contracts: Total contracts traded
            n_at_entry: N value at initial entry
            exit_price: Exit price
            exit_date: When position was closed
            exit_reason: Why position was closed
            point_value: Dollar value per point move
            commission: Total commission paid
            max_units: Maximum units held

        Returns:
            Trade audit record
        """
        # Calculate realized P&L
        price_diff = exit_price - entry_price
        if direction == Direction.SHORT:
            price_diff = -price_diff

        realized_pnl = price_diff * entry_contracts * point_value

        return cls(
            symbol=symbol,
            direction=direction,
            system=system,
            entry_price=entry_price,
            entry_date=entry_date,
            entry_contracts=entry_contracts,
            n_at_entry=n_at_entry,
            exit_price=exit_price,
            exit_date=exit_date,
            exit_reason=exit_reason,
            realized_pnl=realized_pnl,
            commission=commission,
            max_units=max_units,
        )

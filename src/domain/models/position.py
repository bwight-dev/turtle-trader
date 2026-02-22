"""Position domain models for Turtle Trading system."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field

from src.domain.models.enums import CorrelationGroup, Direction, System
from src.domain.models.market import NValue


class PyramidLevel(BaseModel):
    """A single pyramid level (unit) in a position.

    Each pyramid level represents one unit added at a specific price.
    Rule 11: Add 1 unit at +½N intervals from last entry.
    """

    model_config = {"frozen": True}

    level: int = Field(..., ge=1, le=4, description="Pyramid level (1-4)")
    entry_price: Decimal
    contracts: int = Field(..., gt=0)
    n_at_entry: Decimal = Field(..., description="N value when this level was entered")
    entered_at: datetime = Field(default_factory=datetime.now)

    def stop_price(self, direction: Direction) -> Decimal:
        """Calculate 2N stop for this pyramid level.

        Rule 10: Stop = Entry - 2N (longs) or Entry + 2N (shorts)
        """
        two_n = 2 * self.n_at_entry
        if direction == Direction.LONG:
            return self.entry_price - two_n
        return self.entry_price + two_n


class Position(BaseModel):
    """An open trading position with pyramid levels.

    This is an entity with identity (id) that tracks the full position
    including all pyramid levels, stops, and entry metadata.
    """

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    symbol: str
    direction: Direction
    system: System
    correlation_group: CorrelationGroup | None = None

    # Pyramid levels (units)
    pyramid_levels: tuple[PyramidLevel, ...] = Field(default_factory=tuple)

    # Current stop (updated when pyramiding per Rule 12)
    current_stop: Decimal

    # Entry metadata
    initial_entry_price: Decimal
    initial_n: NValue
    opened_at: datetime = Field(default_factory=datetime.now)

    @computed_field
    @property
    def total_units(self) -> int:
        """Total number of units (pyramid levels)."""
        return len(self.pyramid_levels)

    @computed_field
    @property
    def total_contracts(self) -> int:
        """Total number of contracts across all units."""
        return sum(level.contracts for level in self.pyramid_levels)

    @computed_field
    @property
    def average_entry_price(self) -> Decimal:
        """Volume-weighted average entry price."""
        if not self.pyramid_levels:
            return self.initial_entry_price

        total_value = sum(
            level.entry_price * level.contracts for level in self.pyramid_levels
        )
        return total_value / self.total_contracts

    @computed_field
    @property
    def latest_entry_price(self) -> Decimal:
        """Price of the most recent pyramid entry."""
        if not self.pyramid_levels:
            return self.initial_entry_price
        return self.pyramid_levels[-1].entry_price

    @computed_field
    @property
    def latest_n_at_entry(self) -> Decimal:
        """N value at the most recent entry."""
        if not self.pyramid_levels:
            return self.initial_n.value
        return self.pyramid_levels[-1].n_at_entry

    @property
    def can_pyramid(self) -> bool:
        """Check if position can add another unit (max 4)."""
        return self.total_units < 4

    @property
    def next_pyramid_trigger(self) -> Decimal:
        """Price level that triggers next pyramid add.

        Rule 11: Add at +½N intervals from last entry.
        """
        half_n = self.latest_n_at_entry / 2

        if self.direction == Direction.LONG:
            return self.latest_entry_price + half_n
        return self.latest_entry_price - half_n

    def unrealized_pnl(self, current_price: Decimal, point_value: Decimal) -> Decimal:
        """Calculate unrealized P&L.

        Args:
            current_price: Current market price
            point_value: Dollar value per point move

        Returns:
            Unrealized P&L in dollars
        """
        price_diff = current_price - self.average_entry_price
        if self.direction == Direction.SHORT:
            price_diff = -price_diff

        return price_diff * self.total_contracts * point_value

    def is_stop_hit(self, current_price: Decimal) -> bool:
        """Check if current price has hit the stop.

        Rule 10: 2N hard stop is non-negotiable.
        """
        if self.direction == Direction.LONG:
            return current_price <= self.current_stop
        return current_price >= self.current_stop

    def add_pyramid(
        self,
        entry_price: Decimal,
        contracts: int,
        n_at_entry: Decimal,
        new_stop: Decimal,
    ) -> "Position":
        """Add a pyramid level to this position.

        Rule 12: When pyramiding, move ALL stops to 2N below newest entry.

        Returns:
            New Position with added pyramid level and updated stop.
        """
        if not self.can_pyramid:
            raise ValueError("Position already at max 4 units")

        new_level = PyramidLevel(
            level=self.total_units + 1,
            entry_price=entry_price,
            contracts=contracts,
            n_at_entry=n_at_entry,
        )

        return self.model_copy(
            update={
                "pyramid_levels": (*self.pyramid_levels, new_level),
                "current_stop": new_stop,
            }
        )

    def update_stop(self, new_stop: Decimal) -> "Position":
        """Update the stop price for all units.

        Returns:
            New Position with updated stop.
        """
        return self.model_copy(update={"current_stop": new_stop})

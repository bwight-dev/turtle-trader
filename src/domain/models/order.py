"""Order domain models for Turtle Trading system."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.domain.models.enums import Direction, OrderStatus, OrderType


class BracketOrder(BaseModel):
    """A bracket order with entry and stop-loss.

    In Turtle Trading, every entry has an associated 2N stop.
    """

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    symbol: str
    direction: Direction
    quantity: int = Field(..., gt=0, description="Number of contracts")
    entry_price: Decimal | None = Field(
        default=None, description="Limit price for entry (None = market)"
    )
    stop_price: Decimal = Field(..., description="2N stop-loss price")
    order_type: OrderType = Field(default=OrderType.MARKET)
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def is_long(self) -> bool:
        """Check if this is a long order."""
        return self.direction == Direction.LONG


class OrderFill(BaseModel):
    """Record of an order execution/fill."""

    model_config = {"frozen": True}

    order_id: UUID
    symbol: str
    direction: Direction
    quantity: int = Field(..., gt=0)
    fill_price: Decimal
    commission: Decimal = Field(default=Decimal("0"))
    filled_at: datetime = Field(default_factory=datetime.now)
    broker_order_id: str | None = Field(
        default=None, description="External broker order ID"
    )

    @property
    def total_cost(self) -> Decimal:
        """Calculate total cost including commission."""
        return self.fill_price * self.quantity + self.commission


class StopModification(BaseModel):
    """Record of a stop price modification.

    When pyramiding, all stops are moved to 2N below newest entry (Rule 12).
    """

    model_config = {"frozen": True}

    symbol: str
    old_stop: Decimal
    new_stop: Decimal
    reason: str = Field(..., description="Why the stop was modified")
    modified_at: datetime = Field(default_factory=datetime.now)
    affected_units: int = Field(
        default=1, description="Number of units affected by this modification"
    )

    @property
    def stop_moved_up(self) -> bool:
        """Check if stop was tightened (moved up for longs)."""
        return self.new_stop > self.old_stop

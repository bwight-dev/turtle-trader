"""Alert and position snapshot models for website dashboard."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.domain.models.enums import Direction, System


class AlertType(str, Enum):
    """Types of alerts for the trading dashboard."""

    ENTRY_SIGNAL = "ENTRY_SIGNAL"  # Breakout signal detected
    POSITION_OPENED = "POSITION_OPENED"  # Order filled, position established
    POSITION_CLOSED = "POSITION_CLOSED"  # Position fully exited
    EXIT_STOP = "EXIT_STOP"  # 2N stop hit
    EXIT_BREAKOUT = "EXIT_BREAKOUT"  # Donchian exit triggered
    PYRAMID_TRIGGER = "PYRAMID_TRIGGER"  # Pyramid level reached


class Alert(BaseModel):
    """An alert event for the trading dashboard.

    Alerts are immutable event records stored in the database.
    They capture trading signals, position changes, and exits.
    """

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.now)
    symbol: str
    alert_type: AlertType
    direction: Direction | None = None
    system: System | None = None
    price: Decimal | None = None
    details: dict = Field(default_factory=dict)
    acknowledged: bool = False


class OpenPositionSnapshot(BaseModel):
    """Current state of an open position.

    This is a mutable snapshot that gets upserted when position
    state changes significantly (price move >0.5%, P&L change >$50).
    """

    symbol: str
    direction: Direction
    system: System
    entry_price: Decimal
    entry_date: datetime
    contracts: int
    units: int = 1
    current_price: Decimal | None = None
    stop_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    n_value: Decimal | None = None
    updated_at: datetime = Field(default_factory=datetime.now)

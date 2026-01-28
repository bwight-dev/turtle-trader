"""Market data domain models."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class Bar(BaseModel):
    """OHLCV price bar - immutable value object."""

    model_config = {"frozen": True}

    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = 0

    @field_validator("high")
    @classmethod
    def high_ge_low(cls, v: Decimal, info) -> Decimal:
        """Validate high >= low."""
        if "low" in info.data and v < info.data["low"]:
            raise ValueError("high must be >= low")
        return v

    @field_validator("high")
    @classmethod
    def high_ge_open_close(cls, v: Decimal, info) -> Decimal:
        """Validate high >= open and close."""
        if "open" in info.data and v < info.data["open"]:
            raise ValueError("high must be >= open")
        if "close" in info.data and v < info.data["close"]:
            raise ValueError("high must be >= close")
        return v

    @field_validator("low")
    @classmethod
    def low_le_open_close(cls, v: Decimal, info) -> Decimal:
        """Validate low <= open and close."""
        if "open" in info.data and v > info.data["open"]:
            raise ValueError("low must be <= open")
        if "close" in info.data and v > info.data["close"]:
            raise ValueError("low must be <= close")
        return v


class NValue(BaseModel):
    """N (ATR) value - the volatility measure used for sizing and stops."""

    model_config = {"frozen": True}

    value: Decimal = Field(..., gt=0)
    calculated_at: datetime
    symbol: str | None = None

    def to_dollars(self, point_value: Decimal) -> Decimal:
        """Convert N to dollar volatility.

        Args:
            point_value: Dollar value per point move (e.g., $10 for /MGC)

        Returns:
            Dollar volatility = N × point_value
        """
        return self.value * point_value


class DonchianChannel(BaseModel):
    """Donchian channel values for breakout detection."""

    model_config = {"frozen": True}

    period: int
    upper: Decimal  # Highest high of period
    lower: Decimal  # Lowest low of period
    calculated_at: datetime


class MarketSpec(BaseModel):
    """Market specification - metadata about a tradable instrument."""

    model_config = {"frozen": True}

    symbol: str
    name: str
    exchange: str
    asset_class: str  # futures, stock, forex
    correlation_group: str | None = None
    point_value: Decimal = Decimal("1.0")
    tick_size: Decimal = Decimal("0.01")
    currency: str = "USD"

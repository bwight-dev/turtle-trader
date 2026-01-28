"""Domain enumerations for the Turtle Trading system."""

from enum import Enum, auto


class Direction(str, Enum):
    """Trade direction."""

    LONG = "long"
    SHORT = "short"


class System(str, Enum):
    """Turtle trading system type."""

    S1 = "S1"  # 20-day breakout, 10-day exit
    S2 = "S2"  # 55-day breakout, 20-day exit (failsafe)


class PositionAction(str, Enum):
    """Action determined by Position Monitor."""

    HOLD = "hold"  # No action needed
    PYRAMID = "pyramid"  # Add another unit at +½N
    EXIT_STOP = "exit_stop"  # 2N hard stop hit
    EXIT_BREAKOUT = "exit_breakout"  # Donchian breakout exit (10/20-day)


class CorrelationGroup(str, Enum):
    """Market correlation groups for position limits.

    Rule: Max 6 units in correlated markets.
    """

    METALS = "metals"  # /MGC, /SIL, /HG, etc.
    EQUITY_US = "equity_us"  # /MES, /MNQ, /M2K, /MYM
    EQUITY_INTL = "equity_intl"  # International indices
    ENERGY = "energy"  # /MCL, /MNG, etc.
    GRAINS = "grains"  # /ZC, /ZS, /ZW
    SOFTS = "softs"  # Coffee, cocoa, sugar
    MEATS = "meats"  # Cattle, hogs
    CURRENCIES = "currencies"  # Forex futures
    RATES = "rates"  # Interest rate futures
    CRYPTO = "crypto"  # BTC, ETH futures


class OrderType(str, Enum):
    """Order type for execution."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    """Order execution status."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PARTIAL = "partial"

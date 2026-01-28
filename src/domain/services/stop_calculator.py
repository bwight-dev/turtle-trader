"""Stop price calculations for Turtle Trading system.

Implements Rule 10: 2N Hard Stop
- Longs: Stop = Entry - 2N
- Shorts: Stop = Entry + 2N

Implements Rule 12: Aggressive Stop Adjustment
- When pyramiding, move ALL stops to 2N below newest entry
"""

from dataclasses import dataclass
from decimal import Decimal

from src.domain.models.enums import Direction
from src.domain.models.market import NValue
from src.domain.rules import STOP_MULTIPLIER


@dataclass(frozen=True)
class StopPrice:
    """Result of stop price calculation."""

    price: Decimal
    entry_price: Decimal
    n_value: Decimal
    direction: Direction
    distance: Decimal  # Distance from entry in price terms

    @property
    def distance_in_n(self) -> Decimal:
        """Distance from entry expressed in N units."""
        if self.n_value == 0:
            return Decimal("0")
        return self.distance / self.n_value


def calculate_stop(
    entry_price: Decimal,
    n_value: NValue | Decimal,
    direction: Direction,
    stop_multiplier: Decimal = STOP_MULTIPLIER,
) -> StopPrice:
    """Calculate stop price for a position.

    Rule 10: Stop = Entry ± 2N
    - Longs: Entry - 2N
    - Shorts: Entry + 2N

    Args:
        entry_price: Position entry price
        n_value: N (ATR) value - either NValue object or raw Decimal
        direction: Position direction (LONG or SHORT)
        stop_multiplier: Multiple of N for stop distance (default 2)

    Returns:
        StopPrice with calculated stop and metadata

    Example:
        >>> # Long from 2800, N=20, 2N stop
        >>> stop = calculate_stop(
        ...     entry_price=Decimal("2800"),
        ...     n_value=NValue(value=Decimal("20"), ...),
        ...     direction=Direction.LONG,
        ... )
        >>> stop.price
        Decimal('2760')  # 2800 - 40
    """
    # Extract N value if NValue object
    n = n_value.value if isinstance(n_value, NValue) else n_value

    # Calculate stop distance
    distance = n * stop_multiplier

    # Calculate stop price based on direction
    if direction == Direction.LONG:
        stop_price = entry_price - distance
    else:
        stop_price = entry_price + distance

    return StopPrice(
        price=stop_price,
        entry_price=entry_price,
        n_value=n,
        direction=direction,
        distance=distance,
    )


def calculate_pyramid_stop(
    newest_entry_price: Decimal,
    n_value: NValue | Decimal,
    direction: Direction,
    stop_multiplier: Decimal = STOP_MULTIPLIER,
) -> StopPrice:
    """Calculate new stop price after pyramiding.

    Rule 12: When adding units, move ALL stops to 2N below newest entry.

    Args:
        newest_entry_price: Price of the most recent pyramid entry
        n_value: N value at the newest entry
        direction: Position direction
        stop_multiplier: Multiple of N (default 2)

    Returns:
        StopPrice for all units
    """
    return calculate_stop(
        entry_price=newest_entry_price,
        n_value=n_value,
        direction=direction,
        stop_multiplier=stop_multiplier,
    )


def would_stop_be_hit(
    current_price: Decimal,
    stop_price: Decimal,
    direction: Direction,
) -> bool:
    """Check if a stop would be hit at the current price.

    Args:
        current_price: Current market price
        stop_price: Stop price level
        direction: Position direction

    Returns:
        True if stop would be triggered
    """
    if direction == Direction.LONG:
        return current_price <= stop_price
    return current_price >= stop_price


def calculate_trailing_stop(
    highest_favorable: Decimal,
    n_value: Decimal,
    direction: Direction,
    stop_multiplier: Decimal = STOP_MULTIPLIER,
) -> Decimal:
    """Calculate a trailing stop based on highest favorable price.

    Note: Original Turtle rules don't use trailing stops, but this
    is provided for optional use.

    Args:
        highest_favorable: Highest price (longs) or lowest price (shorts) reached
        n_value: Current N value
        direction: Position direction
        stop_multiplier: Multiple of N (default 2)

    Returns:
        Trailing stop price
    """
    distance = n_value * stop_multiplier

    if direction == Direction.LONG:
        return highest_favorable - distance
    return highest_favorable + distance

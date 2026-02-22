"""Position monitor for Turtle Trading system.

This is the critical module that monitors open positions and determines
what action to take. It implements:

- Rule 10: 2N Hard Stop (non-negotiable)
- Rule 11: Pyramid at +½N intervals (max 4 units)
- Rule 13: S1 Exit on 10-day opposite breakout
- Rule 14: S2 Exit on 20-day opposite breakout

Priority Order (checked in this sequence):
1. EXIT_STOP - 2N stop hit (highest priority, immediate exit)
2. EXIT_BREAKOUT - Donchian exit triggered
3. PYRAMID - Position eligible for pyramid add
4. HOLD - No action needed

The monitor only DETECTS actions - it does not execute them.
Execution is handled by separate handlers in the application layer.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.domain.models.enums import Direction, PositionAction, System
from src.domain.models.market import DonchianChannel
from src.domain.models.position import Position
from src.domain.rules import (
    MAX_UNITS_PER_MARKET,
    S1_EXIT_PERIOD,
    S2_EXIT_PERIOD,
)


@dataclass(frozen=True)
class PositionCheckResult:
    """Result of checking a position's status."""

    position_id: str
    symbol: str
    action: PositionAction
    reason: str
    current_price: Decimal
    checked_at: datetime

    # Stop check details
    stop_price: Decimal | None = None
    stop_triggered: bool = False

    # Exit check details
    exit_channel_value: Decimal | None = None
    exit_period: int | None = None
    exit_triggered: bool = False

    # Pyramid check details
    pyramid_trigger_price: Decimal | None = None
    pyramid_triggered: bool = False
    current_units: int | None = None
    can_add_unit: bool = False

    @property
    def requires_action(self) -> bool:
        """Whether any action is required."""
        return self.action != PositionAction.HOLD

    @property
    def is_exit(self) -> bool:
        """Whether this is any type of exit."""
        return self.action in (PositionAction.EXIT_STOP, PositionAction.EXIT_BREAKOUT)

    @property
    def is_pyramid(self) -> bool:
        """Whether this is a pyramid action."""
        return self.action == PositionAction.PYRAMID


class PositionMonitor:
    """Domain service for monitoring position status.

    The Position Monitor continuously evaluates open positions against
    current market data and determines what action (if any) is needed.

    This service only DETECTS conditions - it does not execute trades.
    Execution is handled by separate handlers (PyramidHandler, ExitHandler)
    in the application layer.
    """

    def __init__(
        self,
        max_units_per_market: int = MAX_UNITS_PER_MARKET,
    ):
        """Initialize monitor with configuration.

        Args:
            max_units_per_market: Maximum pyramid units allowed (default 4)
        """
        self.max_units_per_market = max_units_per_market

    def check_position(
        self,
        position: Position,
        current_price: Decimal,
        exit_channel: DonchianChannel | None = None,
    ) -> PositionCheckResult:
        """Check a position and determine what action is needed.

        Checks are performed in priority order:
        1. Stop hit check (Rule 10)
        2. Breakout exit check (Rule 13/14)
        3. Pyramid trigger check (Rule 11)

        Args:
            position: The position to check
            current_price: Current market price
            exit_channel: Donchian channel for exit (10-day for S1, 20-day for S2)

        Returns:
            PositionCheckResult with action and details
        """
        now = datetime.now()
        base_result = {
            "position_id": str(position.id),
            "symbol": position.symbol,
            "current_price": current_price,
            "checked_at": now,
            "stop_price": position.current_stop,
            "current_units": position.total_units,
            "pyramid_trigger_price": position.next_pyramid_trigger,
            "can_add_unit": position.can_pyramid,
        }

        # Priority 1: Check for stop hit (Rule 10)
        stop_result = self._check_stop(position, current_price)
        if stop_result["triggered"]:
            return PositionCheckResult(
                **base_result,
                action=PositionAction.EXIT_STOP,
                reason=stop_result["reason"],
                stop_triggered=True,
            )

        # Priority 2: Check for breakout exit (Rule 13/14)
        if exit_channel:
            exit_result = self._check_exit(position, current_price, exit_channel)
            if exit_result["triggered"]:
                return PositionCheckResult(
                    **base_result,
                    action=PositionAction.EXIT_BREAKOUT,
                    reason=exit_result["reason"],
                    exit_triggered=True,
                    exit_channel_value=exit_result["channel_value"],
                    exit_period=exit_channel.period,
                )

        # Priority 3: Check for pyramid trigger (Rule 11)
        pyramid_result = self._check_pyramid(position, current_price)
        if pyramid_result["triggered"]:
            return PositionCheckResult(
                **base_result,
                action=PositionAction.PYRAMID,
                reason=pyramid_result["reason"],
                pyramid_triggered=True,
            )

        # No action needed
        return PositionCheckResult(
            **base_result,
            action=PositionAction.HOLD,
            reason="No action required",
        )

    def _check_stop(
        self, position: Position, current_price: Decimal
    ) -> dict[str, bool | str]:
        """Check if 2N hard stop has been hit.

        Rule 10: The 2N stop is non-negotiable.
        - Longs: Exit when price <= stop
        - Shorts: Exit when price >= stop

        Args:
            position: Position to check
            current_price: Current market price

        Returns:
            Dict with triggered status and reason
        """
        if position.direction == Direction.LONG:
            triggered = current_price <= position.current_stop
            direction_text = "at or below"
        else:
            triggered = current_price >= position.current_stop
            direction_text = "at or above"

        return {
            "triggered": triggered,
            "reason": (
                f"2N stop hit: price {current_price} {direction_text} "
                f"stop {position.current_stop}"
                if triggered
                else "Stop not hit"
            ),
        }

    def _check_exit(
        self,
        position: Position,
        current_price: Decimal,
        exit_channel: DonchianChannel,
    ) -> dict[str, bool | str | Decimal]:
        """Check if Donchian breakout exit has triggered.

        Rule 13: S1 exits on 10-day opposite breakout
        Rule 14: S2 exits on 20-day opposite breakout

        For longs: Exit when price touches the channel LOW
        For shorts: Exit when price touches the channel HIGH

        Note: "Touches" means price <= low (longs) or price >= high (shorts)
              per original Turtle rules: "Do not wait for the close"

        Args:
            position: Position to check
            current_price: Current market price
            exit_channel: The appropriate Donchian channel for this system

        Returns:
            Dict with triggered status, reason, and channel value
        """
        if position.direction == Direction.LONG:
            # Long exits when price touches the LOW
            channel_value = exit_channel.lower
            triggered = current_price <= channel_value
            exit_type = "low"
        else:
            # Short exits when price touches the HIGH
            channel_value = exit_channel.upper
            triggered = current_price >= channel_value
            exit_type = "high"

        return {
            "triggered": triggered,
            "channel_value": channel_value,
            "reason": (
                f"{exit_channel.period}-day {exit_type} exit: price {current_price} "
                f"touched {exit_type} {channel_value}"
                if triggered
                else f"Exit not triggered (price {current_price}, "
                f"{exit_type} {channel_value})"
            ),
        }

    def _check_pyramid(
        self, position: Position, current_price: Decimal
    ) -> dict[str, bool | str]:
        """Check if pyramid trigger price has been reached.

        Rule 11: Add 1 unit at +½N intervals from last entry
        - Max 4 units per market
        - Longs: Pyramid when price >= trigger
        - Shorts: Pyramid when price <= trigger

        Args:
            position: Position to check
            current_price: Current market price

        Returns:
            Dict with triggered status and reason
        """
        # Can't pyramid if already at max
        if not position.can_pyramid:
            return {
                "triggered": False,
                "reason": f"At max {self.max_units_per_market} units",
            }

        trigger_price = position.next_pyramid_trigger

        if position.direction == Direction.LONG:
            triggered = current_price >= trigger_price
            direction_text = "above"
        else:
            triggered = current_price <= trigger_price
            direction_text = "below"

        return {
            "triggered": triggered,
            "reason": (
                f"Pyramid triggered: price {current_price} {direction_text} "
                f"trigger {trigger_price} (+½N from last entry)"
                if triggered
                else f"Pyramid not triggered (price {current_price}, "
                f"trigger {trigger_price})"
            ),
        }

    def get_exit_period(self, system: System) -> int:
        """Get the appropriate exit channel period for a system.

        Rule 13: S1 uses 10-day exit
        Rule 14: S2 uses 20-day exit

        Args:
            system: The trading system (S1 or S2)

        Returns:
            Donchian period for exit channel
        """
        return S1_EXIT_PERIOD if system == System.S1 else S2_EXIT_PERIOD


def check_all_positions(
    positions: list[Position],
    prices: dict[str, Decimal],
    exit_channels: dict[str, DonchianChannel],
    monitor: PositionMonitor | None = None,
) -> list[PositionCheckResult]:
    """Check multiple positions and return results requiring action.

    Convenience function for checking a list of positions.

    Args:
        positions: Positions to check
        prices: Current prices by symbol
        exit_channels: Exit Donchian channels by symbol
        monitor: PositionMonitor instance (creates default if None)

    Returns:
        List of PositionCheckResult, filtered to only those requiring action
    """
    if monitor is None:
        monitor = PositionMonitor()

    results = []
    for pos in positions:
        if pos.symbol not in prices:
            continue

        result = monitor.check_position(
            position=pos,
            current_price=prices[pos.symbol],
            exit_channel=exit_channels.get(pos.symbol),
        )

        if result.requires_action:
            results.append(result)

    # Sort by priority: exits first, then pyramids
    priority_order = {
        PositionAction.EXIT_STOP: 0,
        PositionAction.EXIT_BREAKOUT: 1,
        PositionAction.PYRAMID: 2,
        PositionAction.HOLD: 3,
    }
    results.sort(key=lambda r: priority_order[r.action])

    return results

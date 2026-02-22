"""Stop modification command for Turtle Trading system.

This is an application layer command that coordinates:
- Broker stop order modification
- Portfolio position update
- Stop modification logging

Used when pyramiding (Rule 12: move all stops to 2N below newest entry).
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.domain.interfaces.broker import Broker, PositionNotFoundError
from src.domain.models.enums import Direction
from src.domain.models.order import StopModification
from src.domain.models.portfolio import Portfolio
from src.domain.services.stop_calculator import calculate_pyramid_stop


@dataclass
class ModifyStopResult:
    """Result of a stop modification command."""

    success: bool
    symbol: str
    old_stop: Decimal | None = None
    new_stop: Decimal | None = None
    reason: str = ""
    broker_modification: StopModification | None = None
    executed_at: datetime | None = None
    error: str | None = None

    def __post_init__(self):
        if self.executed_at is None:
            self.executed_at = datetime.now()


class ModifyStopCommand:
    """Command to modify stop price for a position.

    This command:
    1. Validates the position exists in portfolio
    2. Calculates the new stop price (if not provided)
    3. Modifies the stop order at the broker
    4. Updates the portfolio position

    Used for:
    - Pyramiding (Rule 12): Move all stops to 2N below newest entry
    - Manual stop adjustments
    """

    def __init__(self, broker: Broker) -> None:
        """Initialize the command.

        Args:
            broker: Broker for stop order modification
        """
        self._broker = broker

    async def execute(
        self,
        portfolio: Portfolio,
        symbol: str,
        new_stop: Decimal,
        reason: str = "Stop modified",
    ) -> tuple[Portfolio, ModifyStopResult]:
        """Execute stop modification.

        Args:
            portfolio: Current portfolio state
            symbol: Symbol to modify stop for
            new_stop: New stop price
            reason: Reason for modification

        Returns:
            Tuple of (updated Portfolio, ModifyStopResult)
        """
        try:
            # Validate position exists
            position = portfolio.get_position(symbol)
            if position is None:
                return portfolio, ModifyStopResult(
                    success=False,
                    symbol=symbol,
                    reason="Position not found in portfolio",
                    error=f"No position for {symbol}",
                )

            old_stop = position.current_stop

            # Modify stop at broker
            broker_mod = await self._broker.modify_stop(
                symbol=symbol,
                new_stop=new_stop,
                quantity=position.total_contracts,
            )

            # Update portfolio position
            updated_position = position.update_stop(new_stop)
            updated_portfolio = portfolio.update_position(updated_position)

            return updated_portfolio, ModifyStopResult(
                success=True,
                symbol=symbol,
                old_stop=old_stop,
                new_stop=new_stop,
                reason=reason,
                broker_modification=broker_mod,
            )

        except PositionNotFoundError:
            return portfolio, ModifyStopResult(
                success=False,
                symbol=symbol,
                reason="Position not found at broker",
                error=f"Broker has no position for {symbol}",
            )
        except Exception as e:
            return portfolio, ModifyStopResult(
                success=False,
                symbol=symbol,
                reason="Stop modification failed",
                error=str(e),
            )

    async def execute_pyramid_stop_update(
        self,
        portfolio: Portfolio,
        symbol: str,
        newest_entry_price: Decimal,
        n_at_entry: Decimal,
    ) -> tuple[Portfolio, ModifyStopResult]:
        """Execute stop modification after pyramiding.

        Rule 12: When pyramiding, move ALL stops to 2N below newest entry.

        Args:
            portfolio: Current portfolio state
            symbol: Symbol that was pyramided
            newest_entry_price: Price of the newest pyramid entry
            n_at_entry: N value at the newest entry

        Returns:
            Tuple of (updated Portfolio, ModifyStopResult)
        """
        position = portfolio.get_position(symbol)
        if position is None:
            return portfolio, ModifyStopResult(
                success=False,
                symbol=symbol,
                reason="Position not found",
                error=f"No position for {symbol}",
            )

        # Calculate new stop based on newest entry
        stop_calc = calculate_pyramid_stop(
            newest_entry_price=newest_entry_price,
            n_value=n_at_entry,
            direction=position.direction,
        )

        return await self.execute(
            portfolio=portfolio,
            symbol=symbol,
            new_stop=stop_calc.price,
            reason=f"Pyramid stop update: 2N from entry {newest_entry_price}",
        )

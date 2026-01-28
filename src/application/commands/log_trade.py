"""Trade logging command for Turtle Trading system.

This is an application layer command that logs trade records
for audit, S1 filter, and performance tracking.

Used for:
- Recording entries (position opened)
- Recording exits (position closed with P&L)
- S1 filter lookups
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.domain.interfaces.repositories import TradeRepository
from src.domain.models.enums import Direction, System
from src.domain.models.order import OrderFill
from src.domain.models.position import Position
from src.domain.models.signal import Signal
from src.domain.models.trade import Trade


@dataclass
class LogTradeResult:
    """Result of a trade logging operation."""

    success: bool
    trade: Trade | None = None
    error: str | None = None


class TradeLogger:
    """Command to log trade audit records.

    This command:
    1. Creates trade records from position/signal/fill data
    2. Persists them to the trade repository
    3. Supports both entry and exit logging

    Trade records are used for:
    - S1 filter (was last S1 trade a winner?)
    - Performance tracking
    - Tax records
    """

    def __init__(
        self,
        trade_repository: TradeRepository,
        market_specs: dict[str, dict] | None = None,
    ) -> None:
        """Initialize the trade logger.

        Args:
            trade_repository: Repository for trade persistence
            market_specs: Optional market specifications (symbol -> {point_value, ...})
        """
        self._repo = trade_repository
        self._market_specs = market_specs or self._default_market_specs()

    def _default_market_specs(self) -> dict[str, dict]:
        """Default market specifications."""
        return {
            "/MGC": {"point_value": Decimal("10")},  # Micro Gold
            "/SIL": {"point_value": Decimal("50")},  # Micro Silver
            "/MES": {"point_value": Decimal("5")},   # Micro E-mini S&P
            "/MNQ": {"point_value": Decimal("2")},   # Micro E-mini Nasdaq
            "/MCL": {"point_value": Decimal("100")}, # Micro Crude Oil
            "/M2K": {"point_value": Decimal("5")},   # Micro Russell
            "/MYM": {"point_value": Decimal("0.50")},# Micro Dow
        }

    def _get_point_value(self, symbol: str) -> Decimal:
        """Get point value for a symbol."""
        if symbol in self._market_specs:
            return self._market_specs[symbol].get("point_value", Decimal("1"))
        return Decimal("1")

    async def log_entry(
        self,
        position: Position,
        signal: Signal,
        fill: OrderFill,
    ) -> LogTradeResult:
        """Log a trade entry (position opened).

        Note: This creates a partial trade record. The full trade
        record is created when the position is closed.

        For now, we don't persist partial entries - we create
        complete trade records only on exit.

        Args:
            position: The opened position
            signal: The signal that triggered entry
            fill: The order fill details

        Returns:
            LogTradeResult (success but no trade persisted for entries)
        """
        # Entry logging is informational - full trade created on exit
        # We could store partial records, but for S1 filter we only
        # need completed trades
        return LogTradeResult(success=True)

    async def log_exit(
        self,
        position: Position,
        exit_price: Decimal,
        exit_reason: str,
        exit_date: datetime | None = None,
        commission: Decimal = Decimal("0"),
    ) -> LogTradeResult:
        """Log a trade exit (position closed).

        Creates a complete trade record with P&L calculation.

        Args:
            position: The closed position
            exit_price: Price at which position was closed
            exit_reason: Why position was closed (stop, breakout, manual)
            exit_date: When position was closed (defaults to now)
            commission: Total commission paid

        Returns:
            LogTradeResult with the created trade
        """
        try:
            exit_date = exit_date or datetime.now()
            point_value = self._get_point_value(position.symbol)

            # Create trade record
            trade = Trade.from_position_close(
                symbol=position.symbol,
                direction=position.direction,
                system=position.system,
                entry_price=position.initial_entry_price,
                entry_date=position.opened_at,
                entry_contracts=position.total_contracts,
                n_at_entry=position.initial_n.value,
                exit_price=exit_price,
                exit_date=exit_date,
                exit_reason=exit_reason,
                point_value=point_value,
                commission=commission,
                max_units=len(position.pyramid_levels),
            )

            # Persist to repository
            await self._repo.save_trade(trade)

            return LogTradeResult(success=True, trade=trade)

        except Exception as e:
            return LogTradeResult(success=False, error=str(e))

    async def log_trade(self, trade: Trade) -> LogTradeResult:
        """Log a pre-constructed trade record.

        Args:
            trade: Complete trade record to persist

        Returns:
            LogTradeResult
        """
        try:
            await self._repo.save_trade(trade)
            return LogTradeResult(success=True, trade=trade)
        except Exception as e:
            return LogTradeResult(success=False, error=str(e))

    async def get_last_s1_trade(self, symbol: str) -> Trade | None:
        """Get the most recent S1 trade for a symbol.

        Used for S1 filter: skip if last S1 was a winner.

        Args:
            symbol: Market symbol

        Returns:
            Most recent S1 trade or None
        """
        return await self._repo.get_last_s1_trade(symbol)

    async def was_last_s1_winner(self, symbol: str) -> bool | None:
        """Check if the last S1 trade was a winner.

        Args:
            symbol: Market symbol

        Returns:
            True if winner, False if loser, None if no S1 history
        """
        trade = await self._repo.get_last_s1_trade(symbol)
        if trade is None:
            return None
        return trade.is_winner


async def log_trade_exit(
    trade_repository: TradeRepository,
    position: Position,
    exit_price: Decimal,
    exit_reason: str,
) -> LogTradeResult:
    """Convenience function to log a trade exit.

    Args:
        trade_repository: Repository for persistence
        position: The closed position
        exit_price: Exit price
        exit_reason: Why position was closed

    Returns:
        LogTradeResult with the created trade
    """
    logger = TradeLogger(trade_repository)
    return await logger.log_exit(position, exit_price, exit_reason)

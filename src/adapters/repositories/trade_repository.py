"""PostgreSQL implementation of TradeRepository."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from src.domain.interfaces.repositories import TradeRepository
from src.domain.models.enums import Direction, System
from src.domain.models.trade import Trade
from src.infrastructure.database import execute, fetch, fetchrow


class PostgresTradeRepository(TradeRepository):
    """PostgreSQL implementation of trade audit persistence.

    Stores trade records for:
    - S1 filter (was last S1 trade a winner?)
    - Performance tracking
    - Tax records
    """

    async def save_trade(self, trade: Trade) -> None:
        """Save a trade audit record."""
        await execute(
            """
            INSERT INTO trades (
                id, symbol, direction, system,
                entry_price, entry_date, entry_contracts, n_at_entry,
                exit_price, exit_date, exit_reason,
                realized_pnl, commission, max_units
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ON CONFLICT (id) DO UPDATE SET
                exit_price = EXCLUDED.exit_price,
                exit_date = EXCLUDED.exit_date,
                exit_reason = EXCLUDED.exit_reason,
                realized_pnl = EXCLUDED.realized_pnl,
                commission = EXCLUDED.commission,
                max_units = EXCLUDED.max_units
            """,
            trade.id,
            trade.symbol,
            trade.direction.value,
            trade.system.value,
            trade.entry_price,
            trade.entry_date,
            trade.entry_contracts,
            trade.n_at_entry,
            trade.exit_price,
            trade.exit_date,
            trade.exit_reason,
            trade.realized_pnl,
            trade.commission,
            trade.max_units,
        )

    async def get_last_s1_trade(self, symbol: str) -> Trade | None:
        """Get the most recent S1 trade for a symbol.

        Used for S1 filter: skip if last S1 was a winner.
        """
        row = await fetchrow(
            """
            SELECT
                id, symbol, direction, system,
                entry_price, entry_date, entry_contracts, n_at_entry,
                exit_price, exit_date, exit_reason,
                realized_pnl, commission, max_units
            FROM trades
            WHERE symbol = $1 AND system = 'S1'
            ORDER BY exit_date DESC
            LIMIT 1
            """,
            symbol,
        )

        if not row:
            return None

        return self._row_to_trade(row)

    async def get_trades_by_symbol(
        self,
        symbol: str,
        limit: int = 100,
    ) -> list[Trade]:
        """Get recent trades for a symbol."""
        rows = await fetch(
            """
            SELECT
                id, symbol, direction, system,
                entry_price, entry_date, entry_contracts, n_at_entry,
                exit_price, exit_date, exit_reason,
                realized_pnl, commission, max_units
            FROM trades
            WHERE symbol = $1
            ORDER BY exit_date DESC
            LIMIT $2
            """,
            symbol,
            limit,
        )

        return [self._row_to_trade(row) for row in rows]

    async def get_last_trade(
        self,
        symbol: str,
        system: System | None = None,
        direction: Direction | None = None,
    ) -> Trade | None:
        """Get the most recent trade matching filters.

        Args:
            symbol: Market symbol
            system: Optional system filter (S1 or S2)
            direction: Optional direction filter (long or short)

        Returns:
            Most recent matching trade or None
        """
        query = """
            SELECT
                id, symbol, direction, system,
                entry_price, entry_date, entry_contracts, n_at_entry,
                exit_price, exit_date, exit_reason,
                realized_pnl, commission, max_units
            FROM trades
            WHERE symbol = $1
        """
        params = [symbol]
        param_idx = 2

        if system:
            query += f" AND system = ${param_idx}"
            params.append(system.value)
            param_idx += 1

        if direction:
            query += f" AND direction = ${param_idx}"
            params.append(direction.value)
            param_idx += 1

        query += " ORDER BY exit_date DESC LIMIT 1"

        row = await fetchrow(query, *params)

        if not row:
            return None

        return self._row_to_trade(row)

    def _row_to_trade(self, row) -> Trade:
        """Convert database row to Trade model."""
        return Trade(
            id=row["id"] if isinstance(row["id"], UUID) else UUID(row["id"]),
            symbol=row["symbol"],
            direction=Direction(row["direction"]),
            system=System(row["system"]),
            entry_price=Decimal(str(row["entry_price"])),
            entry_date=row["entry_date"],
            entry_contracts=row["entry_contracts"],
            n_at_entry=Decimal(str(row["n_at_entry"])),
            exit_price=Decimal(str(row["exit_price"])),
            exit_date=row["exit_date"],
            exit_reason=row["exit_reason"],
            realized_pnl=Decimal(str(row["realized_pnl"])),
            commission=Decimal(str(row["commission"])) if row["commission"] else Decimal("0"),
            max_units=row["max_units"] or 1,
        )

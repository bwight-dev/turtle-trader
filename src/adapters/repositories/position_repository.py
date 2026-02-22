"""PostgreSQL implementation of OpenPositionRepository."""

from datetime import datetime
from decimal import Decimal

from src.domain.interfaces.repositories import OpenPositionRepository
from src.domain.models.alert import OpenPositionSnapshot
from src.domain.models.enums import Direction, System
from src.infrastructure.database import execute, fetch, fetchrow


class PostgresOpenPositionRepository(OpenPositionRepository):
    """PostgreSQL implementation of open position snapshots.

    Stores current state of open positions for dashboard display.
    Uses upsert pattern - one row per symbol.
    """

    async def upsert(self, position: OpenPositionSnapshot) -> None:
        """Insert or update a position snapshot."""
        await execute(
            """
            INSERT INTO open_positions (
                symbol, direction, system, entry_price, entry_date,
                contracts, units, current_price, stop_price,
                unrealized_pnl, n_value, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (symbol) DO UPDATE SET
                direction = EXCLUDED.direction,
                system = EXCLUDED.system,
                entry_price = EXCLUDED.entry_price,
                entry_date = EXCLUDED.entry_date,
                contracts = EXCLUDED.contracts,
                units = EXCLUDED.units,
                current_price = EXCLUDED.current_price,
                stop_price = EXCLUDED.stop_price,
                unrealized_pnl = EXCLUDED.unrealized_pnl,
                n_value = EXCLUDED.n_value,
                updated_at = EXCLUDED.updated_at
            """,
            position.symbol,
            position.direction.value,
            position.system.value,
            position.entry_price,
            position.entry_date,
            position.contracts,
            position.units,
            position.current_price,
            position.stop_price,
            position.unrealized_pnl,
            position.n_value,
            position.updated_at,
        )

    async def get_all(self) -> list[OpenPositionSnapshot]:
        """Get all open position snapshots."""
        rows = await fetch(
            """
            SELECT symbol, direction, system, entry_price, entry_date,
                   contracts, units, current_price, stop_price,
                   unrealized_pnl, n_value, updated_at
            FROM open_positions
            ORDER BY entry_date
            """
        )
        return [self._row_to_snapshot(row) for row in rows]

    async def get(self, symbol: str) -> OpenPositionSnapshot | None:
        """Get snapshot for a specific symbol."""
        row = await fetchrow(
            """
            SELECT symbol, direction, system, entry_price, entry_date,
                   contracts, units, current_price, stop_price,
                   unrealized_pnl, n_value, updated_at
            FROM open_positions
            WHERE symbol = $1
            """,
            symbol,
        )
        return self._row_to_snapshot(row) if row else None

    async def delete(self, symbol: str) -> None:
        """Delete a position snapshot."""
        await execute(
            "DELETE FROM open_positions WHERE symbol = $1",
            symbol,
        )

    def _row_to_snapshot(self, row) -> OpenPositionSnapshot:
        """Convert database row to OpenPositionSnapshot model."""
        return OpenPositionSnapshot(
            symbol=row["symbol"],
            direction=Direction(row["direction"]),
            system=System(row["system"]),
            entry_price=Decimal(str(row["entry_price"])),
            entry_date=row["entry_date"],
            contracts=row["contracts"],
            units=row["units"],
            current_price=Decimal(str(row["current_price"])) if row["current_price"] else None,
            stop_price=Decimal(str(row["stop_price"])) if row["stop_price"] else None,
            unrealized_pnl=Decimal(str(row["unrealized_pnl"])) if row["unrealized_pnl"] else None,
            n_value=Decimal(str(row["n_value"])) if row["n_value"] else None,
            updated_at=row["updated_at"],
        )

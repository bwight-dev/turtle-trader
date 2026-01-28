"""PostgreSQL implementation of NValueRepository."""

from datetime import date, datetime
from decimal import Decimal

from src.domain.interfaces.repositories import NValueRepository
from src.domain.models.market import DonchianChannel, NValue
from src.infrastructure.database import execute, fetch, fetchrow, fetchval


class PostgresNValueRepository(NValueRepository):
    """PostgreSQL implementation of N value persistence.

    Stores N values and Donchian channels in the calculated_indicators table.
    """

    async def save_indicators(
        self,
        symbol: str,
        calc_date: date,
        n_value: NValue,
        donchian_10: DonchianChannel | None = None,
        donchian_20: DonchianChannel | None = None,
        donchian_55: DonchianChannel | None = None,
    ) -> None:
        """Save calculated indicators for a symbol."""
        await execute(
            """
            INSERT INTO calculated_indicators (
                symbol, calc_date, n_value,
                donchian_10_upper, donchian_10_lower,
                donchian_20_upper, donchian_20_lower,
                donchian_55_upper, donchian_55_lower
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (symbol, calc_date) DO UPDATE SET
                n_value = EXCLUDED.n_value,
                donchian_10_upper = EXCLUDED.donchian_10_upper,
                donchian_10_lower = EXCLUDED.donchian_10_lower,
                donchian_20_upper = EXCLUDED.donchian_20_upper,
                donchian_20_lower = EXCLUDED.donchian_20_lower,
                donchian_55_upper = EXCLUDED.donchian_55_upper,
                donchian_55_lower = EXCLUDED.donchian_55_lower,
                created_at = CURRENT_TIMESTAMP
            """,
            symbol,
            calc_date,
            n_value.value,
            donchian_10.upper if donchian_10 else None,
            donchian_10.lower if donchian_10 else None,
            donchian_20.upper if donchian_20 else None,
            donchian_20.lower if donchian_20 else None,
            donchian_55.upper if donchian_55 else None,
            donchian_55.lower if donchian_55 else None,
        )

    async def get_latest_indicators(
        self,
        symbol: str,
    ) -> dict | None:
        """Get the most recent indicators for a symbol."""
        row = await fetchrow(
            """
            SELECT
                calc_date, n_value,
                donchian_10_upper, donchian_10_lower,
                donchian_20_upper, donchian_20_lower,
                donchian_55_upper, donchian_55_lower,
                created_at
            FROM calculated_indicators
            WHERE symbol = $1
            ORDER BY calc_date DESC
            LIMIT 1
            """,
            symbol,
        )

        if not row:
            return None

        result = {
            "calc_date": row["calc_date"],
            "n_value": Decimal(str(row["n_value"])),
            "created_at": row["created_at"],
        }

        # Add Donchian channels if present
        if row["donchian_10_upper"] is not None:
            result["donchian_10"] = DonchianChannel(
                period=10,
                upper=Decimal(str(row["donchian_10_upper"])),
                lower=Decimal(str(row["donchian_10_lower"])),
                calculated_at=row["created_at"],
            )

        if row["donchian_20_upper"] is not None:
            result["donchian_20"] = DonchianChannel(
                period=20,
                upper=Decimal(str(row["donchian_20_upper"])),
                lower=Decimal(str(row["donchian_20_lower"])),
                calculated_at=row["created_at"],
            )

        if row["donchian_55_upper"] is not None:
            result["donchian_55"] = DonchianChannel(
                period=55,
                upper=Decimal(str(row["donchian_55_upper"])),
                lower=Decimal(str(row["donchian_55_lower"])),
                calculated_at=row["created_at"],
            )

        return result

    async def get_previous_n(
        self,
        symbol: str,
        before_date: date,
    ) -> Decimal | None:
        """Get the N value from the day before a given date."""
        value = await fetchval(
            """
            SELECT n_value
            FROM calculated_indicators
            WHERE symbol = $1 AND calc_date < $2
            ORDER BY calc_date DESC
            LIMIT 1
            """,
            symbol,
            before_date,
        )

        return Decimal(str(value)) if value is not None else None

    async def get_n_history(
        self,
        symbol: str,
        days: int = 30,
    ) -> list[tuple[date, Decimal]]:
        """Get historical N values for a symbol."""
        rows = await fetch(
            """
            SELECT calc_date, n_value
            FROM calculated_indicators
            WHERE symbol = $1
            ORDER BY calc_date DESC
            LIMIT $2
            """,
            symbol,
            days,
        )

        # Return oldest first
        return [
            (row["calc_date"], Decimal(str(row["n_value"])))
            for row in reversed(rows)
        ]

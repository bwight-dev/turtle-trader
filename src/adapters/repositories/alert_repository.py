"""PostgreSQL implementation of AlertRepository."""

import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from src.domain.interfaces.repositories import AlertRepository
from src.domain.models.alert import Alert, AlertType
from src.domain.models.enums import Direction, System
from src.infrastructure.database import execute, fetch, fetchrow


class PostgresAlertRepository(AlertRepository):
    """PostgreSQL implementation of alert persistence.

    Stores alerts for dashboard display and audit trail.
    """

    async def save(self, alert: Alert) -> None:
        """Save an alert record."""
        await execute(
            """
            INSERT INTO alerts (
                id, timestamp, symbol, alert_type,
                direction, system, price, details, acknowledged
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (id) DO UPDATE SET
                acknowledged = EXCLUDED.acknowledged
            """,
            alert.id,
            alert.timestamp,
            alert.symbol,
            alert.alert_type.value,
            alert.direction.value if alert.direction else None,
            alert.system.value if alert.system else None,
            alert.price,
            json.dumps(alert.details) if alert.details else None,
            alert.acknowledged,
        )

    async def get_recent(self, limit: int = 50) -> list[Alert]:
        """Get most recent alerts."""
        rows = await fetch(
            """
            SELECT id, timestamp, symbol, alert_type,
                   direction, system, price, details, acknowledged
            FROM alerts
            ORDER BY timestamp DESC
            LIMIT $1
            """,
            limit,
        )
        return [self._row_to_alert(row) for row in rows]

    async def get_by_symbol(self, symbol: str, limit: int = 20) -> list[Alert]:
        """Get alerts for a specific symbol."""
        rows = await fetch(
            """
            SELECT id, timestamp, symbol, alert_type,
                   direction, system, price, details, acknowledged
            FROM alerts
            WHERE symbol = $1
            ORDER BY timestamp DESC
            LIMIT $2
            """,
            symbol,
            limit,
        )
        return [self._row_to_alert(row) for row in rows]

    async def get_unacknowledged(self) -> list[Alert]:
        """Get all unacknowledged alerts."""
        rows = await fetch(
            """
            SELECT id, timestamp, symbol, alert_type,
                   direction, system, price, details, acknowledged
            FROM alerts
            WHERE acknowledged = FALSE
            ORDER BY timestamp DESC
            """
        )
        return [self._row_to_alert(row) for row in rows]

    async def acknowledge(self, alert_id: UUID) -> None:
        """Mark an alert as acknowledged."""
        await execute(
            """
            UPDATE alerts SET acknowledged = TRUE WHERE id = $1
            """,
            alert_id,
        )

    def _row_to_alert(self, row) -> Alert:
        """Convert database row to Alert model."""
        details = row["details"]
        if isinstance(details, str):
            details = json.loads(details)

        return Alert(
            id=row["id"] if isinstance(row["id"], UUID) else UUID(row["id"]),
            timestamp=row["timestamp"],
            symbol=row["symbol"],
            alert_type=AlertType(row["alert_type"]),
            direction=Direction(row["direction"]) if row["direction"] else None,
            system=System(row["system"]) if row["system"] else None,
            price=Decimal(str(row["price"])) if row["price"] else None,
            details=details or {},
            acknowledged=row["acknowledged"],
        )

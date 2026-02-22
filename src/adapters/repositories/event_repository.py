"""PostgreSQL implementation of EventRepository."""

import json
from datetime import datetime
from uuid import UUID

from src.domain.interfaces.repositories import EventRepository
from src.domain.models.event import Event, EventType, OutcomeType
from src.infrastructure.database import execute, fetch


class PostgresEventRepository(EventRepository):
    """PostgreSQL implementation of event persistence.

    Events are immutable audit records capturing every trading
    decision with full context.
    """

    async def save(self, event: Event) -> None:
        """Save an event record.

        Events are immutable - this is always an insert.
        """
        await execute(
            """
            INSERT INTO events (
                id, timestamp, event_type, outcome, outcome_reason,
                run_id, sequence, symbol, context, source, dry_run
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            event.id,
            event.timestamp,
            event.event_type.value,
            event.outcome.value,
            event.outcome_reason,
            event.run_id,
            event.sequence,
            event.symbol,
            json.dumps(event.context, default=_json_serialize),
            event.source,
            event.dry_run,
        )

    async def get_by_run_id(self, run_id: UUID) -> list[Event]:
        """Get all events for a specific run."""
        rows = await fetch(
            """
            SELECT id, timestamp, event_type, outcome, outcome_reason,
                   run_id, sequence, symbol, context, source, dry_run
            FROM events
            WHERE run_id = $1
            ORDER BY sequence
            """,
            run_id,
        )
        return [_row_to_event(row) for row in rows]

    async def get_by_symbol(
        self,
        symbol: str,
        limit: int = 100,
        event_types: list[EventType] | None = None,
    ) -> list[Event]:
        """Get events for a specific symbol."""
        if event_types:
            type_values = [et.value for et in event_types]
            rows = await fetch(
                """
                SELECT id, timestamp, event_type, outcome, outcome_reason,
                       run_id, sequence, symbol, context, source, dry_run
                FROM events
                WHERE symbol = $1
                  AND event_type = ANY($2)
                ORDER BY timestamp DESC
                LIMIT $3
                """,
                symbol,
                type_values,
                limit,
            )
        else:
            rows = await fetch(
                """
                SELECT id, timestamp, event_type, outcome, outcome_reason,
                       run_id, sequence, symbol, context, source, dry_run
                FROM events
                WHERE symbol = $1
                ORDER BY timestamp DESC
                LIMIT $2
                """,
                symbol,
                limit,
            )
        return [_row_to_event(row) for row in rows]

    async def get_recent(
        self,
        limit: int = 100,
        source: str | None = None,
        event_types: list[EventType] | None = None,
        outcomes: list[OutcomeType] | None = None,
    ) -> list[Event]:
        """Get recent events with optional filters."""
        # Build dynamic query based on filters
        conditions = []
        params: list = []
        param_idx = 1

        if source:
            conditions.append(f"source = ${param_idx}")
            params.append(source)
            param_idx += 1

        if event_types:
            conditions.append(f"event_type = ANY(${param_idx})")
            params.append([et.value for et in event_types])
            param_idx += 1

        if outcomes:
            conditions.append(f"outcome = ANY(${param_idx})")
            params.append([o.value for o in outcomes])
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        params.append(limit)
        query = f"""
            SELECT id, timestamp, event_type, outcome, outcome_reason,
                   run_id, sequence, symbol, context, source, dry_run
            FROM events
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ${param_idx}
        """

        rows = await fetch(query, *params)
        return [_row_to_event(row) for row in rows]

    async def get_by_date_range(
        self,
        start: datetime,
        end: datetime,
        symbol: str | None = None,
        event_types: list[EventType] | None = None,
    ) -> list[Event]:
        """Get events within a date range."""
        conditions = ["timestamp >= $1", "timestamp <= $2"]
        params: list = [start, end]
        param_idx = 3

        if symbol:
            conditions.append(f"symbol = ${param_idx}")
            params.append(symbol)
            param_idx += 1

        if event_types:
            conditions.append(f"event_type = ANY(${param_idx})")
            params.append([et.value for et in event_types])
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}"

        query = f"""
            SELECT id, timestamp, event_type, outcome, outcome_reason,
                   run_id, sequence, symbol, context, source, dry_run
            FROM events
            {where_clause}
            ORDER BY timestamp
        """

        rows = await fetch(query, *params)
        return [_row_to_event(row) for row in rows]

    async def get_non_hold_events(
        self,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Get events where something happened (not HOLD)."""
        if since:
            rows = await fetch(
                """
                SELECT id, timestamp, event_type, outcome, outcome_reason,
                       run_id, sequence, symbol, context, source, dry_run
                FROM events
                WHERE outcome != 'hold'
                  AND timestamp >= $1
                ORDER BY timestamp DESC
                LIMIT $2
                """,
                since,
                limit,
            )
        else:
            rows = await fetch(
                """
                SELECT id, timestamp, event_type, outcome, outcome_reason,
                       run_id, sequence, symbol, context, source, dry_run
                FROM events
                WHERE outcome != 'hold'
                ORDER BY timestamp DESC
                LIMIT $1
                """,
                limit,
            )
        return [_row_to_event(row) for row in rows]


def _row_to_event(row) -> Event:
    """Convert database row to Event model."""
    context = row["context"]
    if isinstance(context, str):
        context = json.loads(context)

    return Event(
        id=row["id"] if isinstance(row["id"], UUID) else UUID(row["id"]),
        timestamp=row["timestamp"],
        event_type=EventType(row["event_type"]),
        outcome=OutcomeType(row["outcome"]),
        outcome_reason=row["outcome_reason"],
        run_id=row["run_id"] if isinstance(row["run_id"], UUID) else UUID(row["run_id"]),
        sequence=row["sequence"],
        symbol=row["symbol"],
        context=context or {},
        source=row["source"],
        dry_run=row["dry_run"],
    )


def _json_serialize(obj):
    """JSON serializer for objects not serializable by default."""
    from decimal import Decimal
    from datetime import date, datetime

    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

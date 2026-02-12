"""PostgreSQL implementation of RunRepository."""

import json
from datetime import date, datetime
from uuid import UUID

from src.domain.interfaces.repositories import RunRepository
from src.domain.models.run import Run, RunStatus, TaskType
from src.infrastructure.database import execute, fetch, fetchrow


class PostgresRunRepository(RunRepository):
    """PostgreSQL implementation of run event logging.

    Stores run events for dashboard display and debugging.
    """

    async def save(self, run: Run) -> None:
        """Insert or update a run record."""
        await execute(
            """
            INSERT INTO runs (
                id, started_at, completed_at, task_type,
                symbols_checked, signals_found, actions_needed,
                errors_count, status, summary, details
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (id) DO UPDATE SET
                completed_at = EXCLUDED.completed_at,
                symbols_checked = EXCLUDED.symbols_checked,
                signals_found = EXCLUDED.signals_found,
                actions_needed = EXCLUDED.actions_needed,
                errors_count = EXCLUDED.errors_count,
                status = EXCLUDED.status,
                summary = EXCLUDED.summary,
                details = EXCLUDED.details
            """,
            run.id,
            run.started_at,
            run.completed_at,
            run.task_type.value,
            run.symbols_checked,
            run.signals_found,
            run.actions_needed,
            run.errors_count,
            run.status.value,
            run.summary,
            json.dumps(run.details),
        )

    async def get_by_id(self, run_id: UUID) -> Run | None:
        """Get a single run by ID with full details."""
        row = await fetchrow(
            """
            SELECT id, started_at, completed_at, task_type,
                   symbols_checked, signals_found, actions_needed,
                   errors_count, status, summary, details
            FROM runs
            WHERE id = $1
            """,
            run_id,
        )
        if row is None:
            return None
        return self._row_to_run(row)

    async def get_recent(
        self,
        task_type: TaskType | None = None,
        limit: int = 50,
    ) -> list[Run]:
        """Get recent runs, optionally filtered by task type."""
        if task_type is not None:
            rows = await fetch(
                """
                SELECT id, started_at, completed_at, task_type,
                       symbols_checked, signals_found, actions_needed,
                       errors_count, status, summary, details
                FROM runs
                WHERE task_type = $1
                ORDER BY started_at DESC
                LIMIT $2
                """,
                task_type.value,
                limit,
            )
        else:
            rows = await fetch(
                """
                SELECT id, started_at, completed_at, task_type,
                       symbols_checked, signals_found, actions_needed,
                       errors_count, status, summary, details
                FROM runs
                ORDER BY started_at DESC
                LIMIT $1
                """,
                limit,
            )
        return [self._row_to_run(row) for row in rows]

    async def get_by_date(
        self,
        target_date: date,
        task_type: TaskType | None = None,
    ) -> list[Run]:
        """Get all runs for a specific date."""
        if task_type is not None:
            rows = await fetch(
                """
                SELECT id, started_at, completed_at, task_type,
                       symbols_checked, signals_found, actions_needed,
                       errors_count, status, summary, details
                FROM runs
                WHERE started_at::date = $1
                AND task_type = $2
                ORDER BY started_at DESC
                """,
                target_date,
                task_type.value,
            )
        else:
            rows = await fetch(
                """
                SELECT id, started_at, completed_at, task_type,
                       symbols_checked, signals_found, actions_needed,
                       errors_count, status, summary, details
                FROM runs
                WHERE started_at::date = $1
                ORDER BY started_at DESC
                """,
                target_date,
            )
        return [self._row_to_run(row) for row in rows]

    def _row_to_run(self, row) -> Run:
        """Convert database row to Run model."""
        details = row["details"]
        if isinstance(details, str):
            details = json.loads(details)

        return Run(
            id=row["id"] if isinstance(row["id"], UUID) else UUID(row["id"]),
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            task_type=TaskType(row["task_type"]),
            symbols_checked=row["symbols_checked"],
            signals_found=row["signals_found"],
            actions_needed=row["actions_needed"],
            errors_count=row["errors_count"],
            status=RunStatus(row["status"]),
            summary=row["summary"],
            details=details or {},
        )

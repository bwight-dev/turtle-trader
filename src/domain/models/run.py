"""Run event models for execution logging."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """Types of scheduled tasks."""

    SCANNER = "scanner"  # Daily market scanner
    MONITOR = "monitor"  # Position monitor


class RunStatus(str, Enum):
    """Status of a task execution."""

    RUNNING = "running"  # Currently executing
    SUCCESS = "success"  # Completed without errors
    PARTIAL = "partial"  # Completed but some symbols had errors
    FAILED = "failed"  # Critical failure, run aborted


class Run(BaseModel):
    """A single execution of a scheduled task.

    Captures what happened during each scanner or monitor run,
    including summary metrics and detailed per-symbol/position data.
    """

    id: UUID = Field(default_factory=uuid4)
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None

    task_type: TaskType

    # Summary metrics (for list view)
    symbols_checked: int = 0
    signals_found: int = 0
    actions_needed: int = 0
    errors_count: int = 0
    status: RunStatus = RunStatus.RUNNING
    summary: str | None = None

    # Full execution detail (for drill-down view)
    # Scanner: {"symbols": [...], "market_date": "2026-02-12"}
    # Monitor: {"positions": [...], "ibkr_connected": true}
    details: dict = Field(default_factory=dict)

    @property
    def duration_ms(self) -> int | None:
        """Duration of the run in milliseconds."""
        if self.completed_at is None:
            return None
        delta = self.completed_at - self.started_at
        return int(delta.total_seconds() * 1000)

    @property
    def outcome(self) -> str:
        """Human-readable outcome for dashboard display."""
        if self.status == RunStatus.FAILED:
            return "error"
        if self.actions_needed > 0:
            return "action_needed"
        if self.signals_found > 0:
            return "signals_found"
        return "all_clear"

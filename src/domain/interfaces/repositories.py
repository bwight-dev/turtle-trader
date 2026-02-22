"""Repository interfaces (ports) for data persistence."""

from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from src.domain.models.alert import Alert, OpenPositionSnapshot
from src.domain.models.enums import Direction, System
from src.domain.models.event import Event, EventType, OutcomeType
from src.domain.models.market import DonchianChannel, NValue
from src.domain.models.run import Run, TaskType


class NValueRepository(ABC):
    """Repository interface for N value persistence.

    N values are persisted to support:
    - Incremental N calculation (using previous day's N)
    - Historical analysis
    - Continuity across bot restarts
    """

    @abstractmethod
    async def save_indicators(
        self,
        symbol: str,
        calc_date: date,
        n_value: NValue,
        donchian_10: DonchianChannel | None = None,
        donchian_20: DonchianChannel | None = None,
        donchian_55: DonchianChannel | None = None,
    ) -> None:
        """Save calculated indicators for a symbol.

        Args:
            symbol: The internal symbol (e.g., '/MGC')
            calc_date: The date these values were calculated for
            n_value: The N (ATR) value
            donchian_10: 10-day Donchian channel (S1 exit)
            donchian_20: 20-day Donchian channel (S1 entry/S2 exit)
            donchian_55: 55-day Donchian channel (S2 entry)
        """
        ...

    @abstractmethod
    async def get_latest_indicators(
        self,
        symbol: str,
    ) -> dict | None:
        """Get the most recent indicators for a symbol.

        Args:
            symbol: The internal symbol

        Returns:
            Dict with n_value, donchian_10, etc. or None if not found
        """
        ...

    @abstractmethod
    async def get_previous_n(
        self,
        symbol: str,
        before_date: date,
    ) -> Decimal | None:
        """Get the N value from the day before a given date.

        Used for incremental N calculation with Wilder's smoothing.

        Args:
            symbol: The internal symbol
            before_date: Get N from the day before this date

        Returns:
            Previous N value or None if not found
        """
        ...

    @abstractmethod
    async def get_n_history(
        self,
        symbol: str,
        days: int = 30,
    ) -> list[tuple[date, Decimal]]:
        """Get historical N values for a symbol.

        Args:
            symbol: The internal symbol
            days: Number of days of history

        Returns:
            List of (date, n_value) tuples, oldest first
        """
        ...


class TradeRepository(ABC):
    """Repository interface for trade audit records.

    Trades are persisted for:
    - S1 filter (was last S1 trade a winner?)
    - Performance tracking
    - Tax records
    """

    @abstractmethod
    async def save_trade(self, trade: "Trade") -> None:  # noqa: F821
        """Save a trade audit record."""
        ...

    @abstractmethod
    async def get_last_s1_trade(self, symbol: str) -> "Trade | None":  # noqa: F821
        """Get the most recent S1 trade for a symbol.

        Used for S1 filter: skip if last S1 was a winner.
        """
        ...

    @abstractmethod
    async def get_trades_by_symbol(
        self,
        symbol: str,
        limit: int = 100,
    ) -> list["Trade"]:  # noqa: F821
        """Get recent trades for a symbol."""
        ...


class AlertRepository(ABC):
    """Repository interface for alert persistence.

    Alerts are immutable event records used for:
    - Dashboard notifications
    - Historical analysis
    - Audit trail
    """

    @abstractmethod
    async def save(self, alert: Alert) -> None:
        """Save an alert record."""
        ...

    @abstractmethod
    async def has_signal_today(
        self,
        symbol: str,
        direction: Direction,
        system: System,
    ) -> bool:
        """Check if an ENTRY_SIGNAL already exists today for this combination.

        Used to prevent duplicate signals when scanning hourly.

        Args:
            symbol: Market symbol
            direction: Trade direction (LONG/SHORT)
            system: Trading system (S1/S2)

        Returns:
            True if signal already exists today, False otherwise
        """
        ...

    @abstractmethod
    async def get_recent(self, limit: int = 50) -> list[Alert]:
        """Get most recent alerts."""
        ...

    @abstractmethod
    async def get_by_symbol(self, symbol: str, limit: int = 20) -> list[Alert]:
        """Get alerts for a specific symbol."""
        ...

    @abstractmethod
    async def get_unacknowledged(self) -> list[Alert]:
        """Get all unacknowledged alerts."""
        ...

    @abstractmethod
    async def acknowledge(self, alert_id: UUID) -> None:
        """Mark an alert as acknowledged."""
        ...


class OpenPositionRepository(ABC):
    """Repository interface for open position snapshots.

    Snapshots track current state of open positions for
    dashboard display. Upserted on significant changes.
    """

    @abstractmethod
    async def upsert(self, position: OpenPositionSnapshot) -> None:
        """Insert or update a position snapshot."""
        ...

    @abstractmethod
    async def get_all(self) -> list[OpenPositionSnapshot]:
        """Get all open position snapshots."""
        ...

    @abstractmethod
    async def get(self, symbol: str) -> OpenPositionSnapshot | None:
        """Get snapshot for a specific symbol."""
        ...

    @abstractmethod
    async def delete(self, symbol: str) -> None:
        """Delete a position snapshot (when position closes)."""
        ...


class RunRepository(ABC):
    """Repository interface for run event logging.

    Runs track each execution of scanner and monitor tasks,
    capturing what was checked and what decisions were made.
    """

    @abstractmethod
    async def save(self, run: Run) -> None:
        """Insert or update a run record.

        Uses upsert to allow updating a run after completion.
        """
        ...

    @abstractmethod
    async def get_by_id(self, run_id: UUID) -> Run | None:
        """Get a single run by ID with full details."""
        ...

    @abstractmethod
    async def get_recent(
        self,
        task_type: TaskType | None = None,
        limit: int = 50,
    ) -> list[Run]:
        """Get recent runs, optionally filtered by task type.

        Args:
            task_type: Filter to specific task type, or None for all
            limit: Maximum number of runs to return

        Returns:
            List of runs, newest first
        """
        ...

    @abstractmethod
    async def get_by_date(
        self,
        target_date: date,
        task_type: TaskType | None = None,
    ) -> list[Run]:
        """Get all runs for a specific date.

        Args:
            target_date: The date to query
            task_type: Filter to specific task type, or None for all

        Returns:
            List of runs for that date, newest first
        """
        ...


class EventRepository(ABC):
    """Repository interface for event streaming persistence.

    Events are immutable audit records capturing every trading
    decision with full context. Used for:
    - Complete audit trail
    - Calculation replay
    - Debugging
    - Performance analysis

    See docs/plans/2026-02-12-event-streaming-design.md for full design.
    """

    @abstractmethod
    async def save(self, event: Event) -> None:
        """Save an event record.

        Events are immutable - this is always an insert.
        """
        ...

    @abstractmethod
    async def get_by_run_id(self, run_id: UUID) -> list[Event]:
        """Get all events for a specific run.

        Returns events in sequence order.
        """
        ...

    @abstractmethod
    async def get_by_symbol(
        self,
        symbol: str,
        limit: int = 100,
        event_types: list[EventType] | None = None,
    ) -> list[Event]:
        """Get events for a specific symbol.

        Args:
            symbol: Market symbol
            limit: Maximum events to return
            event_types: Filter to specific event types, or None for all

        Returns:
            Events newest first
        """
        ...

    @abstractmethod
    async def get_recent(
        self,
        limit: int = 100,
        source: str | None = None,
        event_types: list[EventType] | None = None,
        outcomes: list[OutcomeType] | None = None,
    ) -> list[Event]:
        """Get recent events with optional filters.

        Args:
            limit: Maximum events to return
            source: Filter to "scanner" or "monitor", or None for all
            event_types: Filter to specific event types, or None for all
            outcomes: Filter to specific outcomes, or None for all

        Returns:
            Events newest first
        """
        ...

    @abstractmethod
    async def get_by_date_range(
        self,
        start: datetime,
        end: datetime,
        symbol: str | None = None,
        event_types: list[EventType] | None = None,
    ) -> list[Event]:
        """Get events within a date range.

        Args:
            start: Start of range (inclusive)
            end: End of range (inclusive)
            symbol: Filter to specific symbol, or None for all
            event_types: Filter to specific event types, or None for all

        Returns:
            Events in chronological order
        """
        ...

    @abstractmethod
    async def get_non_hold_events(
        self,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Get events where something happened (not HOLD).

        Useful for reviewing trading activity without the noise
        of routine position checks.

        Args:
            since: Only events after this time, or None for all
            limit: Maximum events to return

        Returns:
            Events newest first, excluding HOLD outcomes
        """
        ...

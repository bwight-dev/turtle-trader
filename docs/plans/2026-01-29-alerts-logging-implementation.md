# Alerts Logging Implementation Plan

**Status:** ✅ Complete (2026-01-29) - All 13 tasks implemented

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add database logging for alerts and open positions to enable website dashboard polling.

**Architecture:** Two new tables (`alerts`, `open_positions`) with repository pattern matching existing codebase. AlertLogger command orchestrates writes. Integration via monitoring loop and daily scanner.

**Tech Stack:** Python 3.12+, Pydantic v2, asyncpg, Neon PostgreSQL

---

## Task 1: Create AlertType Enum and Alert Model

**Files:**
- Create: `src/domain/models/alert.py`
- Test: `tests/unit/domain/test_alert_models.py`

**Step 1: Write the failing test**

Create `tests/unit/domain/test_alert_models.py`:

```python
"""Unit tests for Alert and OpenPositionSnapshot models."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import pytest

from src.domain.models.alert import Alert, AlertType, OpenPositionSnapshot
from src.domain.models.enums import Direction, System


class TestAlertType:
    """Tests for AlertType enum."""

    def test_alert_type_values(self):
        """Verify all expected alert types exist."""
        assert AlertType.ENTRY_SIGNAL == "ENTRY_SIGNAL"
        assert AlertType.POSITION_OPENED == "POSITION_OPENED"
        assert AlertType.POSITION_CLOSED == "POSITION_CLOSED"
        assert AlertType.EXIT_STOP == "EXIT_STOP"
        assert AlertType.EXIT_BREAKOUT == "EXIT_BREAKOUT"
        assert AlertType.PYRAMID_TRIGGER == "PYRAMID_TRIGGER"

    def test_alert_type_is_string_enum(self):
        """AlertType should be usable as string."""
        assert str(AlertType.ENTRY_SIGNAL) == "ENTRY_SIGNAL"


class TestAlert:
    """Tests for Alert model."""

    def test_create_alert_minimal(self):
        """Create alert with minimal required fields."""
        alert = Alert(
            symbol="SPY",
            alert_type=AlertType.ENTRY_SIGNAL,
        )
        assert alert.symbol == "SPY"
        assert alert.alert_type == AlertType.ENTRY_SIGNAL
        assert isinstance(alert.id, UUID)
        assert isinstance(alert.timestamp, datetime)
        assert alert.acknowledged is False

    def test_create_alert_full(self):
        """Create alert with all fields."""
        alert = Alert(
            symbol="SPY",
            alert_type=AlertType.EXIT_STOP,
            direction=Direction.LONG,
            system=System.S1,
            price=Decimal("450.25"),
            details={"reason": "2N stop hit", "pnl": -1075.00},
        )
        assert alert.direction == Direction.LONG
        assert alert.system == System.S1
        assert alert.price == Decimal("450.25")
        assert alert.details["reason"] == "2N stop hit"


class TestOpenPositionSnapshot:
    """Tests for OpenPositionSnapshot model."""

    def test_create_snapshot_minimal(self):
        """Create snapshot with minimal required fields."""
        snapshot = OpenPositionSnapshot(
            symbol="EFA",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("101.56"),
            entry_date=datetime(2026, 1, 29, 10, 30),
            contracts=134,
        )
        assert snapshot.symbol == "EFA"
        assert snapshot.units == 1  # default
        assert snapshot.current_price is None
        assert isinstance(snapshot.updated_at, datetime)

    def test_create_snapshot_full(self):
        """Create snapshot with all fields."""
        snapshot = OpenPositionSnapshot(
            symbol="EFA",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("101.56"),
            entry_date=datetime(2026, 1, 29, 10, 30),
            contracts=134,
            units=2,
            current_price=Decimal("101.67"),
            stop_price=Decimal("99.73"),
            unrealized_pnl=Decimal("15.08"),
            n_value=Decimal("0.93"),
        )
        assert snapshot.units == 2
        assert snapshot.current_price == Decimal("101.67")
        assert snapshot.stop_price == Decimal("99.73")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/domain/test_alert_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.domain.models.alert'"

**Step 3: Write minimal implementation**

Create `src/domain/models/alert.py`:

```python
"""Alert and position snapshot models for website dashboard."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.domain.models.enums import Direction, System


class AlertType(str, Enum):
    """Types of alerts for the trading dashboard."""

    ENTRY_SIGNAL = "ENTRY_SIGNAL"  # Breakout signal detected
    POSITION_OPENED = "POSITION_OPENED"  # Order filled, position established
    POSITION_CLOSED = "POSITION_CLOSED"  # Position fully exited
    EXIT_STOP = "EXIT_STOP"  # 2N stop hit
    EXIT_BREAKOUT = "EXIT_BREAKOUT"  # Donchian exit triggered
    PYRAMID_TRIGGER = "PYRAMID_TRIGGER"  # Pyramid level reached


class Alert(BaseModel):
    """An alert event for the trading dashboard.

    Alerts are immutable event records stored in the database.
    They capture trading signals, position changes, and exits.
    """

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.now)
    symbol: str
    alert_type: AlertType
    direction: Direction | None = None
    system: System | None = None
    price: Decimal | None = None
    details: dict = Field(default_factory=dict)
    acknowledged: bool = False


class OpenPositionSnapshot(BaseModel):
    """Current state of an open position.

    This is a mutable snapshot that gets upserted when position
    state changes significantly (price move >0.5%, P&L change >$50).
    """

    symbol: str
    direction: Direction
    system: System
    entry_price: Decimal
    entry_date: datetime
    contracts: int
    units: int = 1
    current_price: Decimal | None = None
    stop_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    n_value: Decimal | None = None
    updated_at: datetime = Field(default_factory=datetime.now)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/domain/test_alert_models.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add src/domain/models/alert.py tests/unit/domain/test_alert_models.py
git commit -m "feat: add Alert and OpenPositionSnapshot models"
```

---

## Task 2: Add Repository Interfaces

**Files:**
- Modify: `src/domain/interfaces/repositories.py`
- Test: `tests/unit/domain/test_alert_models.py` (add interface tests)

**Step 1: Write the failing test**

Add to `tests/unit/domain/test_alert_models.py`:

```python
from abc import ABC
from src.domain.interfaces.repositories import AlertRepository, OpenPositionRepository


class TestRepositoryInterfaces:
    """Tests for repository interfaces."""

    def test_alert_repository_is_abstract(self):
        """AlertRepository should be abstract."""
        assert issubclass(AlertRepository, ABC)

    def test_open_position_repository_is_abstract(self):
        """OpenPositionRepository should be abstract."""
        assert issubclass(OpenPositionRepository, ABC)

    def test_alert_repository_has_required_methods(self):
        """AlertRepository should define required abstract methods."""
        methods = ['save', 'get_recent', 'get_by_symbol', 'get_unacknowledged', 'acknowledge']
        for method in methods:
            assert hasattr(AlertRepository, method)

    def test_open_position_repository_has_required_methods(self):
        """OpenPositionRepository should define required abstract methods."""
        methods = ['upsert', 'get_all', 'get', 'delete']
        for method in methods:
            assert hasattr(OpenPositionRepository, method)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/domain/test_alert_models.py::TestRepositoryInterfaces -v`
Expected: FAIL with "ImportError: cannot import name 'AlertRepository'"

**Step 3: Write minimal implementation**

Add to `src/domain/interfaces/repositories.py` (after existing classes):

```python
from uuid import UUID
from src.domain.models.alert import Alert, OpenPositionSnapshot


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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/domain/test_alert_models.py -v`
Expected: PASS (10 tests)

**Step 5: Commit**

```bash
git add src/domain/interfaces/repositories.py tests/unit/domain/test_alert_models.py
git commit -m "feat: add AlertRepository and OpenPositionRepository interfaces"
```

---

## Task 3: Create Database Migration

**Files:**
- Create: `src/infrastructure/migrations/005_create_alerts_tables.sql`

**Step 1: Write the migration**

Create `src/infrastructure/migrations/005_create_alerts_tables.sql`:

```sql
-- Migration: 005_create_alerts_tables
-- Description: Create alerts and open_positions tables for dashboard
-- Created: 2026-01-29

-- Alerts table: immutable event log
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    symbol VARCHAR(20) NOT NULL,
    alert_type VARCHAR(30) NOT NULL,
    direction VARCHAR(10),
    system VARCHAR(5),
    price DECIMAL(14,6),
    details JSONB,
    acknowledged BOOLEAN DEFAULT FALSE
);

-- Index for recent alerts query
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp
    ON alerts(timestamp DESC);

-- Index for symbol-specific alerts
CREATE INDEX IF NOT EXISTS idx_alerts_symbol
    ON alerts(symbol, timestamp DESC);

-- Partial index for unacknowledged alerts (notification badge)
CREATE INDEX IF NOT EXISTS idx_alerts_unacknowledged
    ON alerts(acknowledged) WHERE acknowledged = FALSE;

-- Open positions table: current state snapshot
CREATE TABLE IF NOT EXISTS open_positions (
    symbol VARCHAR(20) PRIMARY KEY,
    direction VARCHAR(10) NOT NULL,
    system VARCHAR(5) NOT NULL,
    entry_price DECIMAL(14,6) NOT NULL,
    entry_date TIMESTAMPTZ NOT NULL,
    contracts INTEGER NOT NULL,
    units INTEGER NOT NULL DEFAULT 1,
    current_price DECIMAL(14,6),
    stop_price DECIMAL(14,6),
    unrealized_pnl DECIMAL(14,2),
    n_value DECIMAL(12,6),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Record this migration
INSERT INTO schema_migrations (version) VALUES ('005_create_alerts_tables')
ON CONFLICT (version) DO NOTHING;
```

**Step 2: Run the migration**

Run: `cd /Users/bradwight/Development/Projects/Personal/turtle-trading-bot-alerts && source .venv/bin/activate && python scripts/setup_db.py`
Expected: "Applying 005_create_alerts_tables..."

**Step 3: Verify tables exist**

Run: `python -c "import asyncio; from src.infrastructure.database import fetch; print(asyncio.run(fetch(\"SELECT table_name FROM information_schema.tables WHERE table_name IN ('alerts', 'open_positions')\")))"`
Expected: Two rows showing 'alerts' and 'open_positions'

**Step 4: Commit**

```bash
git add src/infrastructure/migrations/005_create_alerts_tables.sql
git commit -m "feat: add database migration for alerts and open_positions tables"
```

---

## Task 4: Implement PostgresAlertRepository

**Files:**
- Create: `src/adapters/repositories/alert_repository.py`
- Test: `tests/unit/adapters/test_alert_repository.py`

**Step 1: Write the failing test**

Create `tests/unit/adapters/test_alert_repository.py`:

```python
"""Unit tests for PostgresAlertRepository."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.domain.models.alert import Alert, AlertType
from src.domain.models.enums import Direction, System


class InMemoryAlertRepository:
    """In-memory alert repository for testing."""

    def __init__(self):
        self.alerts: dict[str, Alert] = {}

    async def save(self, alert: Alert) -> None:
        self.alerts[str(alert.id)] = alert

    async def get_recent(self, limit: int = 50) -> list[Alert]:
        sorted_alerts = sorted(
            self.alerts.values(),
            key=lambda a: a.timestamp,
            reverse=True,
        )
        return sorted_alerts[:limit]

    async def get_by_symbol(self, symbol: str, limit: int = 20) -> list[Alert]:
        symbol_alerts = [a for a in self.alerts.values() if a.symbol == symbol]
        symbol_alerts.sort(key=lambda a: a.timestamp, reverse=True)
        return symbol_alerts[:limit]

    async def get_unacknowledged(self) -> list[Alert]:
        return [a for a in self.alerts.values() if not a.acknowledged]

    async def acknowledge(self, alert_id) -> None:
        key = str(alert_id)
        if key in self.alerts:
            alert = self.alerts[key]
            self.alerts[key] = Alert(
                id=alert.id,
                timestamp=alert.timestamp,
                symbol=alert.symbol,
                alert_type=alert.alert_type,
                direction=alert.direction,
                system=alert.system,
                price=alert.price,
                details=alert.details,
                acknowledged=True,
            )


@pytest.fixture
def repo():
    """Create in-memory alert repository."""
    return InMemoryAlertRepository()


def make_alert(
    symbol: str = "SPY",
    alert_type: AlertType = AlertType.ENTRY_SIGNAL,
    **kwargs,
) -> Alert:
    """Create a test alert."""
    return Alert(symbol=symbol, alert_type=alert_type, **kwargs)


class TestAlertRepository:
    """Tests for alert repository operations."""

    @pytest.mark.asyncio
    async def test_save_and_get_recent(self, repo):
        """Save an alert and retrieve it."""
        alert = make_alert()
        await repo.save(alert)

        recent = await repo.get_recent(limit=10)
        assert len(recent) == 1
        assert recent[0].id == alert.id

    @pytest.mark.asyncio
    async def test_get_by_symbol(self, repo):
        """Get alerts filtered by symbol."""
        await repo.save(make_alert(symbol="SPY"))
        await repo.save(make_alert(symbol="QQQ"))
        await repo.save(make_alert(symbol="SPY"))

        spy_alerts = await repo.get_by_symbol("SPY")
        assert len(spy_alerts) == 2
        assert all(a.symbol == "SPY" for a in spy_alerts)

    @pytest.mark.asyncio
    async def test_get_unacknowledged(self, repo):
        """Get only unacknowledged alerts."""
        alert1 = make_alert()
        alert2 = make_alert()
        await repo.save(alert1)
        await repo.save(alert2)
        await repo.acknowledge(alert1.id)

        unacked = await repo.get_unacknowledged()
        assert len(unacked) == 1
        assert unacked[0].id == alert2.id

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, repo):
        """Acknowledge an alert."""
        alert = make_alert()
        await repo.save(alert)
        await repo.acknowledge(alert.id)

        recent = await repo.get_recent()
        assert recent[0].acknowledged is True

    @pytest.mark.asyncio
    async def test_recent_ordered_by_timestamp(self, repo):
        """Recent alerts should be ordered newest first."""
        alert1 = Alert(
            symbol="A",
            alert_type=AlertType.ENTRY_SIGNAL,
            timestamp=datetime(2026, 1, 1, 10, 0),
        )
        alert2 = Alert(
            symbol="B",
            alert_type=AlertType.ENTRY_SIGNAL,
            timestamp=datetime(2026, 1, 1, 12, 0),
        )
        await repo.save(alert1)
        await repo.save(alert2)

        recent = await repo.get_recent()
        assert recent[0].symbol == "B"  # newer
        assert recent[1].symbol == "A"  # older
```

**Step 2: Run test to verify it passes with in-memory implementation**

Run: `pytest tests/unit/adapters/test_alert_repository.py -v`
Expected: PASS (5 tests with in-memory repo)

**Step 3: Write PostgreSQL implementation**

Create `src/adapters/repositories/alert_repository.py`:

```python
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
```

**Step 4: Run tests again**

Run: `pytest tests/unit/adapters/test_alert_repository.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add src/adapters/repositories/alert_repository.py tests/unit/adapters/test_alert_repository.py
git commit -m "feat: implement PostgresAlertRepository"
```

---

## Task 5: Implement PostgresOpenPositionRepository

**Files:**
- Create: `src/adapters/repositories/position_repository.py`
- Test: `tests/unit/adapters/test_position_repository.py`

**Step 1: Write the failing test**

Create `tests/unit/adapters/test_position_repository.py`:

```python
"""Unit tests for PostgresOpenPositionRepository."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.domain.models.alert import OpenPositionSnapshot
from src.domain.models.enums import Direction, System


class InMemoryOpenPositionRepository:
    """In-memory position repository for testing."""

    def __init__(self):
        self.positions: dict[str, OpenPositionSnapshot] = {}

    async def upsert(self, position: OpenPositionSnapshot) -> None:
        self.positions[position.symbol] = position

    async def get_all(self) -> list[OpenPositionSnapshot]:
        return list(self.positions.values())

    async def get(self, symbol: str) -> OpenPositionSnapshot | None:
        return self.positions.get(symbol)

    async def delete(self, symbol: str) -> None:
        self.positions.pop(symbol, None)


@pytest.fixture
def repo():
    """Create in-memory position repository."""
    return InMemoryOpenPositionRepository()


def make_snapshot(symbol: str = "EFA", **kwargs) -> OpenPositionSnapshot:
    """Create a test position snapshot."""
    defaults = {
        "direction": Direction.LONG,
        "system": System.S1,
        "entry_price": Decimal("101.56"),
        "entry_date": datetime(2026, 1, 29, 10, 30),
        "contracts": 134,
    }
    defaults.update(kwargs)
    return OpenPositionSnapshot(symbol=symbol, **defaults)


class TestOpenPositionRepository:
    """Tests for open position repository operations."""

    @pytest.mark.asyncio
    async def test_upsert_and_get(self, repo):
        """Upsert a position and retrieve it."""
        snapshot = make_snapshot()
        await repo.upsert(snapshot)

        result = await repo.get("EFA")
        assert result is not None
        assert result.symbol == "EFA"
        assert result.contracts == 134

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, repo):
        """Upsert should update existing position."""
        await repo.upsert(make_snapshot(current_price=Decimal("101.00")))
        await repo.upsert(make_snapshot(current_price=Decimal("102.00")))

        result = await repo.get("EFA")
        assert result.current_price == Decimal("102.00")

    @pytest.mark.asyncio
    async def test_get_all(self, repo):
        """Get all open positions."""
        await repo.upsert(make_snapshot(symbol="EFA"))
        await repo.upsert(make_snapshot(symbol="SPY"))

        all_positions = await repo.get_all()
        assert len(all_positions) == 2
        symbols = {p.symbol for p in all_positions}
        assert symbols == {"EFA", "SPY"}

    @pytest.mark.asyncio
    async def test_delete(self, repo):
        """Delete a position."""
        await repo.upsert(make_snapshot())
        await repo.delete("EFA")

        result = await repo.get("EFA")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, repo):
        """Get returns None for nonexistent symbol."""
        result = await repo.get("NOTEXIST")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_no_error(self, repo):
        """Delete nonexistent symbol should not error."""
        await repo.delete("NOTEXIST")  # Should not raise
```

**Step 2: Run test to verify it passes with in-memory implementation**

Run: `pytest tests/unit/adapters/test_position_repository.py -v`
Expected: PASS (6 tests)

**Step 3: Write PostgreSQL implementation**

Create `src/adapters/repositories/position_repository.py`:

```python
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
```

**Step 4: Run tests again**

Run: `pytest tests/unit/adapters/test_position_repository.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add src/adapters/repositories/position_repository.py tests/unit/adapters/test_position_repository.py
git commit -m "feat: implement PostgresOpenPositionRepository"
```

---

## Task 6: Implement AlertLogger Command

**Files:**
- Create: `src/application/commands/log_alert.py`
- Test: `tests/unit/application/test_log_alert.py`

**Step 1: Write the failing test**

Create `tests/unit/application/test_log_alert.py`:

```python
"""Unit tests for AlertLogger command."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.application.commands.log_alert import AlertLogger
from src.domain.models.alert import Alert, AlertType, OpenPositionSnapshot
from src.domain.models.enums import Direction, System


class InMemoryAlertRepository:
    """In-memory alert repository for testing."""

    def __init__(self):
        self.alerts: list[Alert] = []

    async def save(self, alert: Alert) -> None:
        self.alerts.append(alert)

    async def get_recent(self, limit: int = 50) -> list[Alert]:
        return self.alerts[-limit:]

    async def get_by_symbol(self, symbol: str, limit: int = 20) -> list[Alert]:
        return [a for a in self.alerts if a.symbol == symbol][-limit:]

    async def get_unacknowledged(self) -> list[Alert]:
        return [a for a in self.alerts if not a.acknowledged]

    async def acknowledge(self, alert_id) -> None:
        pass


class InMemoryOpenPositionRepository:
    """In-memory position repository for testing."""

    def __init__(self):
        self.positions: dict[str, OpenPositionSnapshot] = {}

    async def upsert(self, position: OpenPositionSnapshot) -> None:
        self.positions[position.symbol] = position

    async def get_all(self) -> list[OpenPositionSnapshot]:
        return list(self.positions.values())

    async def get(self, symbol: str) -> OpenPositionSnapshot | None:
        return self.positions.get(symbol)

    async def delete(self, symbol: str) -> None:
        self.positions.pop(symbol, None)


@pytest.fixture
def alert_repo():
    return InMemoryAlertRepository()


@pytest.fixture
def position_repo():
    return InMemoryOpenPositionRepository()


@pytest.fixture
def logger(alert_repo, position_repo):
    return AlertLogger(alert_repo, position_repo)


class TestAlertLoggerSignals:
    """Tests for signal logging."""

    @pytest.mark.asyncio
    async def test_log_signal_creates_alert(self, logger, alert_repo):
        """log_signal should create an ENTRY_SIGNAL alert."""
        alert = await logger.log_signal(
            symbol="SPY",
            direction=Direction.LONG,
            system=System.S1,
            price=Decimal("450.00"),
            details={"breakout_level": 449.50},
        )

        assert alert.alert_type == AlertType.ENTRY_SIGNAL
        assert alert.symbol == "SPY"
        assert alert.direction == Direction.LONG
        assert len(alert_repo.alerts) == 1


class TestAlertLoggerPositions:
    """Tests for position logging."""

    @pytest.mark.asyncio
    async def test_log_position_opened_creates_alert_and_position(
        self, logger, alert_repo, position_repo
    ):
        """log_position_opened should create alert AND position snapshot."""
        alert = await logger.log_position_opened(
            symbol="EFA",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("101.56"),
            contracts=134,
            stop_price=Decimal("99.73"),
            n_value=Decimal("0.93"),
        )

        assert alert.alert_type == AlertType.POSITION_OPENED
        assert len(alert_repo.alerts) == 1

        position = await position_repo.get("EFA")
        assert position is not None
        assert position.contracts == 134
        assert position.stop_price == Decimal("99.73")


class TestAlertLoggerExits:
    """Tests for exit logging."""

    @pytest.mark.asyncio
    async def test_log_exit_creates_alert_and_deletes_position(
        self, logger, alert_repo, position_repo
    ):
        """log_exit should create alert AND delete position snapshot."""
        # First create a position
        await logger.log_position_opened(
            symbol="EFA",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("101.56"),
            contracts=134,
            stop_price=Decimal("99.73"),
            n_value=Decimal("0.93"),
        )

        # Now close it
        alert = await logger.log_exit(
            symbol="EFA",
            alert_type=AlertType.EXIT_STOP,
            exit_price=Decimal("99.70"),
            details={"reason": "2N stop hit", "pnl": -249.24},
        )

        assert alert.alert_type == AlertType.EXIT_STOP
        assert len(alert_repo.alerts) == 2  # POSITION_OPENED + EXIT_STOP

        position = await position_repo.get("EFA")
        assert position is None  # deleted


class TestAlertLoggerPyramids:
    """Tests for pyramid logging."""

    @pytest.mark.asyncio
    async def test_log_pyramid_creates_alert_and_updates_position(
        self, logger, alert_repo, position_repo
    ):
        """log_pyramid should create alert AND update position."""
        # First create a position
        await logger.log_position_opened(
            symbol="SPY",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("450.00"),
            contracts=100,
            stop_price=Decimal("440.00"),
            n_value=Decimal("5.00"),
        )

        # Now pyramid
        alert = await logger.log_pyramid(
            symbol="SPY",
            trigger_price=Decimal("452.50"),
            new_units=2,
            new_stop=Decimal("442.50"),
            new_contracts=200,
        )

        assert alert.alert_type == AlertType.PYRAMID_TRIGGER
        assert len(alert_repo.alerts) == 2

        position = await position_repo.get("SPY")
        assert position.units == 2
        assert position.stop_price == Decimal("442.50")
        assert position.contracts == 200


class TestAlertLoggerPositionUpdate:
    """Tests for position snapshot updates."""

    @pytest.mark.asyncio
    async def test_update_position_upserts_snapshot(self, logger, position_repo):
        """update_position should upsert the snapshot."""
        snapshot = OpenPositionSnapshot(
            symbol="EFA",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("101.56"),
            entry_date=datetime(2026, 1, 29, 10, 30),
            contracts=134,
            current_price=Decimal("102.00"),
            unrealized_pnl=Decimal("58.96"),
        )

        await logger.update_position(snapshot)

        position = await position_repo.get("EFA")
        assert position.current_price == Decimal("102.00")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/application/test_log_alert.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.application.commands.log_alert'"

**Step 3: Write minimal implementation**

Create `src/application/commands/log_alert.py`:

```python
"""Alert logging command for Turtle Trading system.

This command logs alerts and manages open position snapshots
for the website dashboard.
"""

from datetime import datetime
from decimal import Decimal

from src.domain.interfaces.repositories import AlertRepository, OpenPositionRepository
from src.domain.models.alert import Alert, AlertType, OpenPositionSnapshot
from src.domain.models.enums import Direction, System


class AlertLogger:
    """Command to log alerts and manage position snapshots.

    This command:
    1. Creates alert records for trading events
    2. Manages open_positions table for dashboard display
    3. Coordinates alert + position writes for consistency
    """

    def __init__(
        self,
        alert_repo: AlertRepository,
        position_repo: OpenPositionRepository,
    ) -> None:
        """Initialize the alert logger.

        Args:
            alert_repo: Repository for alert persistence
            position_repo: Repository for position snapshots
        """
        self._alert_repo = alert_repo
        self._position_repo = position_repo

    async def log_signal(
        self,
        symbol: str,
        direction: Direction,
        system: System,
        price: Decimal,
        details: dict | None = None,
    ) -> Alert:
        """Log an entry signal detection.

        Args:
            symbol: Market symbol
            direction: Trade direction
            system: S1 or S2
            price: Signal price
            details: Additional signal details

        Returns:
            Created Alert
        """
        alert = Alert(
            symbol=symbol,
            alert_type=AlertType.ENTRY_SIGNAL,
            direction=direction,
            system=system,
            price=price,
            details=details or {},
        )
        await self._alert_repo.save(alert)
        return alert

    async def log_position_opened(
        self,
        symbol: str,
        direction: Direction,
        system: System,
        entry_price: Decimal,
        contracts: int,
        stop_price: Decimal,
        n_value: Decimal,
    ) -> Alert:
        """Log a position being opened.

        Creates both an alert and an open_positions snapshot.

        Args:
            symbol: Market symbol
            direction: Trade direction
            system: S1 or S2
            entry_price: Entry fill price
            contracts: Number of contracts/shares
            stop_price: Initial stop price
            n_value: N (ATR) at entry

        Returns:
            Created Alert
        """
        now = datetime.now()

        # Create alert
        alert = Alert(
            symbol=symbol,
            alert_type=AlertType.POSITION_OPENED,
            direction=direction,
            system=system,
            price=entry_price,
            details={
                "contracts": contracts,
                "stop_price": float(stop_price),
                "n_value": float(n_value),
            },
        )
        await self._alert_repo.save(alert)

        # Create position snapshot
        snapshot = OpenPositionSnapshot(
            symbol=symbol,
            direction=direction,
            system=system,
            entry_price=entry_price,
            entry_date=now,
            contracts=contracts,
            units=1,
            current_price=entry_price,
            stop_price=stop_price,
            unrealized_pnl=Decimal("0"),
            n_value=n_value,
            updated_at=now,
        )
        await self._position_repo.upsert(snapshot)

        return alert

    async def log_exit(
        self,
        symbol: str,
        alert_type: AlertType,
        exit_price: Decimal,
        details: dict | None = None,
    ) -> Alert:
        """Log a position exit.

        Creates alert and deletes position snapshot.

        Args:
            symbol: Market symbol
            alert_type: EXIT_STOP or EXIT_BREAKOUT
            exit_price: Exit fill price
            details: Additional details (reason, pnl, etc.)

        Returns:
            Created Alert
        """
        alert = Alert(
            symbol=symbol,
            alert_type=alert_type,
            price=exit_price,
            details=details or {},
        )
        await self._alert_repo.save(alert)

        # Delete position snapshot
        await self._position_repo.delete(symbol)

        return alert

    async def log_pyramid(
        self,
        symbol: str,
        trigger_price: Decimal,
        new_units: int,
        new_stop: Decimal,
        new_contracts: int,
    ) -> Alert:
        """Log a pyramid being added.

        Creates alert and updates position snapshot.

        Args:
            symbol: Market symbol
            trigger_price: Price that triggered pyramid
            new_units: Total units after pyramid
            new_stop: New stop price after pyramid
            new_contracts: Total contracts after pyramid

        Returns:
            Created Alert
        """
        alert = Alert(
            symbol=symbol,
            alert_type=AlertType.PYRAMID_TRIGGER,
            price=trigger_price,
            details={
                "new_units": new_units,
                "new_stop": float(new_stop),
                "new_contracts": new_contracts,
            },
        )
        await self._alert_repo.save(alert)

        # Update position snapshot
        existing = await self._position_repo.get(symbol)
        if existing:
            updated = OpenPositionSnapshot(
                symbol=existing.symbol,
                direction=existing.direction,
                system=existing.system,
                entry_price=existing.entry_price,
                entry_date=existing.entry_date,
                contracts=new_contracts,
                units=new_units,
                current_price=trigger_price,
                stop_price=new_stop,
                unrealized_pnl=existing.unrealized_pnl,
                n_value=existing.n_value,
                updated_at=datetime.now(),
            )
            await self._position_repo.upsert(updated)

        return alert

    async def update_position(self, snapshot: OpenPositionSnapshot) -> None:
        """Update position snapshot without creating alert.

        Used for significant price/P&L changes between actions.

        Args:
            snapshot: Updated position snapshot
        """
        await self._position_repo.upsert(snapshot)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/application/test_log_alert.py -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add src/application/commands/log_alert.py tests/unit/application/test_log_alert.py
git commit -m "feat: implement AlertLogger command"
```

---

## Task 7: Add Significant Change Detection

**Files:**
- Modify: `src/application/commands/log_alert.py`
- Test: `tests/unit/application/test_log_alert.py` (add tests)

**Step 1: Write the failing test**

Add to `tests/unit/application/test_log_alert.py`:

```python
from src.application.commands.log_alert import is_significant_change


class TestSignificantChange:
    """Tests for significant change detection."""

    def test_price_change_above_threshold_is_significant(self):
        """Price change >0.5% should be significant."""
        snapshot = OpenPositionSnapshot(
            symbol="SPY",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("450.00"),
            entry_date=datetime(2026, 1, 29),
            contracts=100,
            current_price=Decimal("450.00"),
            unrealized_pnl=Decimal("0"),
        )

        # 0.6% price change
        assert is_significant_change(
            snapshot,
            new_price=Decimal("452.70"),
            new_pnl=Decimal("270.00"),
        ) is True

    def test_price_change_below_threshold_not_significant(self):
        """Price change <0.5% should not be significant."""
        snapshot = OpenPositionSnapshot(
            symbol="SPY",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("450.00"),
            entry_date=datetime(2026, 1, 29),
            contracts=100,
            current_price=Decimal("450.00"),
            unrealized_pnl=Decimal("0"),
        )

        # 0.2% price change
        assert is_significant_change(
            snapshot,
            new_price=Decimal("450.90"),
            new_pnl=Decimal("90.00"),
        ) is False

    def test_pnl_change_above_threshold_is_significant(self):
        """P&L change >$50 should be significant."""
        snapshot = OpenPositionSnapshot(
            symbol="SPY",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("450.00"),
            entry_date=datetime(2026, 1, 29),
            contracts=100,
            current_price=Decimal("450.00"),
            unrealized_pnl=Decimal("0"),
        )

        # Small price change but $60 P&L change
        assert is_significant_change(
            snapshot,
            new_price=Decimal("450.20"),
            new_pnl=Decimal("60.00"),
        ) is True

    def test_stop_change_is_significant(self):
        """Stop price change should be significant."""
        snapshot = OpenPositionSnapshot(
            symbol="SPY",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("450.00"),
            entry_date=datetime(2026, 1, 29),
            contracts=100,
            current_price=Decimal("450.00"),
            stop_price=Decimal("440.00"),
            unrealized_pnl=Decimal("0"),
        )

        # Small price/pnl change but stop changed
        assert is_significant_change(
            snapshot,
            new_price=Decimal("450.10"),
            new_pnl=Decimal("10.00"),
            new_stop=Decimal("442.50"),
        ) is True

    def test_no_change_not_significant(self):
        """No meaningful change should not be significant."""
        snapshot = OpenPositionSnapshot(
            symbol="SPY",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("450.00"),
            entry_date=datetime(2026, 1, 29),
            contracts=100,
            current_price=Decimal("450.00"),
            stop_price=Decimal("440.00"),
            unrealized_pnl=Decimal("0"),
        )

        assert is_significant_change(
            snapshot,
            new_price=Decimal("450.10"),
            new_pnl=Decimal("10.00"),
            new_stop=Decimal("440.00"),
        ) is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/application/test_log_alert.py::TestSignificantChange -v`
Expected: FAIL with "ImportError: cannot import name 'is_significant_change'"

**Step 3: Write minimal implementation**

Add to `src/application/commands/log_alert.py` (before AlertLogger class):

```python
# Thresholds for significant change detection
PRICE_CHANGE_THRESHOLD = Decimal("0.005")  # 0.5%
PNL_CHANGE_THRESHOLD = Decimal("50")  # $50


def is_significant_change(
    current: OpenPositionSnapshot,
    new_price: Decimal,
    new_pnl: Decimal,
    new_stop: Decimal | None = None,
) -> bool:
    """Determine if position change warrants a DB write.

    A change is significant if any of these conditions are met:
    - Price moved more than 0.5%
    - P&L changed by more than $50
    - Stop price changed (pyramid happened)

    Args:
        current: Current position snapshot
        new_price: New current price
        new_pnl: New unrealized P&L
        new_stop: New stop price (if changed)

    Returns:
        True if change is significant and should be persisted
    """
    # Price moved more than 0.5%
    if current.current_price:
        price_change = abs(new_price - current.current_price) / current.current_price
        if price_change > PRICE_CHANGE_THRESHOLD:
            return True

    # P&L changed by more than $50
    if current.unrealized_pnl is not None:
        if abs(new_pnl - current.unrealized_pnl) > PNL_CHANGE_THRESHOLD:
            return True

    # Stop price changed (pyramid happened)
    if new_stop and current.stop_price:
        if new_stop != current.stop_price:
            return True

    return False
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/application/test_log_alert.py -v`
Expected: PASS (12 tests)

**Step 5: Commit**

```bash
git add src/application/commands/log_alert.py tests/unit/application/test_log_alert.py
git commit -m "feat: add significant change detection for position updates"
```

---

## Task 8: Integrate AlertLogger into MonitoringLoop

**Files:**
- Modify: `src/application/workflows/monitoring_loop.py`
- Test: Update `tests/unit/workflows/test_monitoring_loop.py`

**Step 1: Understand current implementation**

Read `src/application/workflows/monitoring_loop.py` to understand where to add logging.

Key integration points:
- `__init__`: Add `alert_repo` and `position_repo` parameters
- `_execute_exit`: Log EXIT_STOP or EXIT_BREAKOUT alert
- `_execute_pyramid`: Log PYRAMID_TRIGGER alert
- `_check_single_position`: Update position snapshot on significant change

**Step 2: Write the test for alert logging on exit**

Add to `tests/unit/workflows/test_monitoring_loop.py`:

```python
# Add these imports
from src.domain.models.alert import Alert, AlertType, OpenPositionSnapshot
from src.domain.interfaces.repositories import AlertRepository, OpenPositionRepository


class InMemoryAlertRepository:
    """In-memory alert repository for testing."""

    def __init__(self):
        self.alerts: list[Alert] = []

    async def save(self, alert: Alert) -> None:
        self.alerts.append(alert)

    async def get_recent(self, limit: int = 50) -> list[Alert]:
        return self.alerts[-limit:]

    async def get_by_symbol(self, symbol: str, limit: int = 20) -> list[Alert]:
        return [a for a in self.alerts if a.symbol == symbol][-limit:]

    async def get_unacknowledged(self) -> list[Alert]:
        return [a for a in self.alerts if not a.acknowledged]

    async def acknowledge(self, alert_id) -> None:
        pass


class InMemoryOpenPositionRepository:
    """In-memory position repository for testing."""

    def __init__(self):
        self.positions: dict[str, OpenPositionSnapshot] = {}

    async def upsert(self, position: OpenPositionSnapshot) -> None:
        self.positions[position.symbol] = position

    async def get_all(self) -> list[OpenPositionSnapshot]:
        return list(self.positions.values())

    async def get(self, symbol: str) -> OpenPositionSnapshot | None:
        return self.positions.get(symbol)

    async def delete(self, symbol: str) -> None:
        self.positions.pop(symbol, None)


class TestMonitoringLoopAlertLogging:
    """Tests for alert logging in monitoring loop."""

    @pytest.mark.asyncio
    async def test_exit_stop_logs_alert(self):
        """Exit stop should log an EXIT_STOP alert."""
        alert_repo = InMemoryAlertRepository()
        position_repo = InMemoryOpenPositionRepository()

        loop = MonitoringLoop(
            broker=MockBroker(),
            data_feed=MockDataFeed(),
            trade_repo=InMemoryTradeRepository(),
            alert_repo=alert_repo,
            position_repo=position_repo,
        )

        # Set up position that will trigger stop
        # ... test implementation

        # Verify alert was logged
        assert len(alert_repo.alerts) == 1
        assert alert_repo.alerts[0].alert_type == AlertType.EXIT_STOP
```

**Step 3: Modify MonitoringLoop implementation**

Update `src/application/workflows/monitoring_loop.py`:

1. Add imports:
```python
from src.application.commands.log_alert import AlertLogger, is_significant_change
from src.domain.interfaces.repositories import AlertRepository, OpenPositionRepository
from src.domain.models.alert import AlertType, OpenPositionSnapshot
```

2. Update `__init__`:
```python
def __init__(
    self,
    broker: Broker | None = None,
    data_feed: DataFeed | None = None,
    n_repo: NValueRepository | None = None,
    trade_repo: TradeRepository | None = None,
    alert_repo: AlertRepository | None = None,
    position_repo: OpenPositionRepository | None = None,
    check_interval_seconds: float = 60.0,
):
    # ... existing code ...
    self._alert_repo = alert_repo
    self._position_repo = position_repo
    self._alert_logger = (
        AlertLogger(alert_repo, position_repo)
        if alert_repo and position_repo
        else None
    )
```

3. Update `_execute_exit` to log alert:
```python
async def _execute_exit(self, position, check_result):
    # ... existing broker close code ...

    # Log alert
    if self._alert_logger:
        alert_type = (
            AlertType.EXIT_STOP
            if check_result.action == PositionAction.EXIT_STOP
            else AlertType.EXIT_BREAKOUT
        )
        await self._alert_logger.log_exit(
            symbol=position.symbol,
            alert_type=alert_type,
            exit_price=fill.fill_price,
            details={
                "reason": check_result.reason,
                "pnl": float(fill.realized_pnl) if hasattr(fill, 'realized_pnl') else None,
            },
        )
```

4. Update `_execute_pyramid` to log alert:
```python
async def _execute_pyramid(self, position, check_result):
    # ... existing pyramid code ...

    # Log alert
    if self._alert_logger:
        await self._alert_logger.log_pyramid(
            symbol=position.symbol,
            trigger_price=check_result.current_price,
            new_units=position.unit_count + 1,
            new_stop=new_stop,
            new_contracts=new_total_contracts,
        )
```

**Step 4: Run tests**

Run: `pytest tests/unit/workflows/test_monitoring_loop.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/application/workflows/monitoring_loop.py tests/unit/workflows/test_monitoring_loop.py
git commit -m "feat: integrate AlertLogger into MonitoringLoop"
```

---

## Task 9: Integrate Alert Logging into Daily Scanner

**Files:**
- Modify: `scripts/daily_run.py`

**Step 1: Update daily_run.py to log signals**

Add alert logging when signals are detected:

```python
# Add imports at top
from src.adapters.repositories.alert_repository import PostgresAlertRepository
from src.adapters.repositories.position_repository import PostgresOpenPositionRepository
from src.application.commands.log_alert import AlertLogger
from src.domain.models.enums import Direction, System


async def main(symbols: list[str] | None = None):
    """Run the daily market scanner."""
    universe = symbols or DEFAULT_UNIVERSE

    print("=" * 60)
    print(f"TURTLE TRADING SIGNAL SCANNER - {date.today()}")
    print("=" * 60)
    print(f"\nScanning {len(universe)} markets...")
    print()

    # Initialize repositories and logger
    alert_repo = PostgresAlertRepository()
    position_repo = PostgresOpenPositionRepository()
    alert_logger = AlertLogger(alert_repo, position_repo)

    # Initialize detector
    detector = SignalDetector()

    # Scan all symbols
    results = []
    for symbol in universe:
        print(f"  Scanning {symbol}...", end=" ", flush=True)
        result = await scan_symbol(symbol, detector)
        results.append(result)

        if result["error"]:
            print(f"ERROR: {result['error']}")
        elif result["signals"]:
            print(f"SIGNAL DETECTED!")
            # Log each signal to database
            for sig in result["signals"]:
                await alert_logger.log_signal(
                    symbol=symbol,
                    direction=Direction(sig["direction"]),
                    system=System(sig["system"]),
                    price=Decimal(str(sig["price"])),
                    details={
                        "signal_type": sig["type"],
                        "channel_value": sig["channel"],
                        "n_value": result["n_value"],
                    },
                )
        else:
            print("no signal")

    # ... rest of existing code ...
```

**Step 2: Test manually**

Run: `python scripts/daily_run.py --symbols SPY`
Expected: Signals (if any) logged to alerts table

**Step 3: Verify in database**

Run: `python -c "import asyncio; from src.infrastructure.database import fetch; print(asyncio.run(fetch('SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 5')))"`

**Step 4: Commit**

```bash
git add scripts/daily_run.py
git commit -m "feat: integrate alert logging into daily scanner"
```

---

## Task 10: Create Backfill Script for Current Position

**Files:**
- Create: `scripts/backfill_position.py`

**Step 1: Create the backfill script**

Create `scripts/backfill_position.py`:

```python
#!/usr/bin/env python3
"""Backfill current EFA position into open_positions table.

One-time script to populate the database with the existing position.

Usage:
    python scripts/backfill_position.py
"""

import asyncio
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.repositories.alert_repository import PostgresAlertRepository
from src.adapters.repositories.position_repository import PostgresOpenPositionRepository
from src.application.commands.log_alert import AlertLogger
from src.domain.models.enums import Direction, System


async def backfill_efa_position():
    """Backfill the current EFA position."""
    alert_repo = PostgresAlertRepository()
    position_repo = PostgresOpenPositionRepository()
    alert_logger = AlertLogger(alert_repo, position_repo)

    # Current EFA position details (from IBKR)
    symbol = "EFA"
    direction = Direction.LONG
    system = System.S1
    entry_price = Decimal("101.56")
    contracts = 134
    stop_price = Decimal("99.73")  # 2N below entry
    n_value = Decimal("0.93")

    print(f"Backfilling {symbol} position...")
    print(f"  Direction: {direction.value}")
    print(f"  System: {system.value}")
    print(f"  Entry: ${entry_price}")
    print(f"  Contracts: {contracts}")
    print(f"  Stop: ${stop_price}")
    print(f"  N: {n_value}")

    # Check if position already exists
    existing = await position_repo.get(symbol)
    if existing:
        print(f"\nPosition already exists in database. Skipping.")
        return

    # Log position opened (creates alert + position snapshot)
    alert = await alert_logger.log_position_opened(
        symbol=symbol,
        direction=direction,
        system=system,
        entry_price=entry_price,
        contracts=contracts,
        stop_price=stop_price,
        n_value=n_value,
    )

    print(f"\nPosition backfilled successfully!")
    print(f"  Alert ID: {alert.id}")

    # Verify
    position = await position_repo.get(symbol)
    print(f"\nVerification:")
    print(f"  Symbol: {position.symbol}")
    print(f"  Contracts: {position.contracts}")
    print(f"  Stop: ${position.stop_price}")


if __name__ == "__main__":
    asyncio.run(backfill_efa_position())
```

**Step 2: Run the backfill**

Run: `python scripts/backfill_position.py`
Expected: Position inserted into open_positions table

**Step 3: Verify in database**

Run: `python -c "import asyncio; from src.infrastructure.database import fetch; print(asyncio.run(fetch('SELECT * FROM open_positions')))"`

**Step 4: Commit**

```bash
git add scripts/backfill_position.py
git commit -m "feat: add backfill script for current EFA position"
```

---

## Task 11: Update Monitor Script to Use Alert Logging

**Files:**
- Modify: `scripts/monitor_positions.py`

**Step 1: Update monitor script**

Add alert repository initialization and pass to MonitoringLoop:

```python
# Add imports
from src.adapters.repositories.alert_repository import PostgresAlertRepository
from src.adapters.repositories.position_repository import PostgresOpenPositionRepository


async def run_monitor(...):
    # ... existing setup ...

    # Initialize alert repositories
    alert_repo = PostgresAlertRepository()
    position_repo = PostgresOpenPositionRepository()

    # Create monitoring loop with alert logging
    loop = MonitoringLoop(
        broker=broker,
        data_feed=data_feed,
        n_repo=n_repo,
        trade_repo=trade_repo,
        alert_repo=alert_repo,
        position_repo=position_repo,
        check_interval_seconds=60.0,
    )

    # ... rest of existing code ...
```

**Step 2: Test the monitor**

Run: `python scripts/monitor_positions.py --once`
Expected: Position status printed, snapshot updated in database

**Step 3: Verify position snapshot updated**

Run: `python -c "import asyncio; from src.infrastructure.database import fetch; print(asyncio.run(fetch('SELECT symbol, current_price, unrealized_pnl, updated_at FROM open_positions')))"`

**Step 4: Commit**

```bash
git add scripts/monitor_positions.py
git commit -m "feat: integrate alert logging into position monitor"
```

---

## Task 12: Final Integration Test

**Files:**
- Create: `tests/integration/test_alert_logging.py`

**Step 1: Write integration test**

Create `tests/integration/test_alert_logging.py`:

```python
"""Integration tests for alert logging flow."""

import asyncio
from datetime import datetime
from decimal import Decimal

import pytest

from src.adapters.repositories.alert_repository import PostgresAlertRepository
from src.adapters.repositories.position_repository import PostgresOpenPositionRepository
from src.application.commands.log_alert import AlertLogger
from src.domain.models.alert import AlertType
from src.domain.models.enums import Direction, System
from src.infrastructure.database import execute


@pytest.fixture
async def cleanup_test_data():
    """Clean up test data before and after tests."""
    await execute("DELETE FROM alerts WHERE symbol = 'TEST'")
    await execute("DELETE FROM open_positions WHERE symbol = 'TEST'")
    yield
    await execute("DELETE FROM alerts WHERE symbol = 'TEST'")
    await execute("DELETE FROM open_positions WHERE symbol = 'TEST'")


@pytest.mark.asyncio
async def test_full_position_lifecycle(cleanup_test_data):
    """Test complete position lifecycle: signal -> open -> pyramid -> exit."""
    alert_repo = PostgresAlertRepository()
    position_repo = PostgresOpenPositionRepository()
    logger = AlertLogger(alert_repo, position_repo)

    # 1. Signal detected
    signal_alert = await logger.log_signal(
        symbol="TEST",
        direction=Direction.LONG,
        system=System.S1,
        price=Decimal("100.00"),
        details={"breakout_level": 99.50},
    )
    assert signal_alert.alert_type == AlertType.ENTRY_SIGNAL

    # 2. Position opened
    open_alert = await logger.log_position_opened(
        symbol="TEST",
        direction=Direction.LONG,
        system=System.S1,
        entry_price=Decimal("100.25"),
        contracts=100,
        stop_price=Decimal("95.25"),
        n_value=Decimal("2.50"),
    )
    assert open_alert.alert_type == AlertType.POSITION_OPENED

    position = await position_repo.get("TEST")
    assert position is not None
    assert position.contracts == 100

    # 3. Pyramid added
    pyramid_alert = await logger.log_pyramid(
        symbol="TEST",
        trigger_price=Decimal("101.50"),
        new_units=2,
        new_stop=Decimal("96.50"),
        new_contracts=200,
    )
    assert pyramid_alert.alert_type == AlertType.PYRAMID_TRIGGER

    position = await position_repo.get("TEST")
    assert position.units == 2
    assert position.contracts == 200

    # 4. Position closed
    exit_alert = await logger.log_exit(
        symbol="TEST",
        alert_type=AlertType.EXIT_STOP,
        exit_price=Decimal("96.50"),
        details={"reason": "2N stop hit", "pnl": -750.00},
    )
    assert exit_alert.alert_type == AlertType.EXIT_STOP

    position = await position_repo.get("TEST")
    assert position is None  # deleted

    # Verify all alerts were recorded
    alerts = await alert_repo.get_by_symbol("TEST")
    assert len(alerts) == 4
    alert_types = {a.alert_type for a in alerts}
    assert alert_types == {
        AlertType.ENTRY_SIGNAL,
        AlertType.POSITION_OPENED,
        AlertType.PYRAMID_TRIGGER,
        AlertType.EXIT_STOP,
    }
```

**Step 2: Run integration test**

Run: `pytest tests/integration/test_alert_logging.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/integration/test_alert_logging.py
git commit -m "test: add integration test for alert logging lifecycle"
```

---

## Task 13: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add alerts documentation**

Add to CLAUDE.md under "Database" section:

```markdown
### Dashboard Tables

Two additional tables support the website dashboard:

**`alerts`** - Immutable event log for trading signals and actions:
- ENTRY_SIGNAL, POSITION_OPENED, EXIT_STOP, EXIT_BREAKOUT, PYRAMID_TRIGGER

**`open_positions`** - Current state of open positions (upserted on changes)

Query examples:
```sql
-- All open positions for dashboard
SELECT * FROM open_positions ORDER BY entry_date;

-- Recent alerts (last 24h)
SELECT * FROM alerts WHERE timestamp > NOW() - INTERVAL '24 hours' ORDER BY timestamp DESC;

-- Unacknowledged count for notification badge
SELECT COUNT(*) FROM alerts WHERE acknowledged = FALSE;
```
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add alerts and open_positions documentation to CLAUDE.md"
```

---

## Summary

**Total Tasks:** 13
**Estimated Tests:** ~30 new tests
**New Files:** 8
**Modified Files:** 5

### Execution Order

1. Alert models (domain)
2. Repository interfaces (domain)
3. Database migration (infrastructure)
4. Alert repository (adapter)
5. Position repository (adapter)
6. AlertLogger command (application)
7. Significant change detection (application)
8. MonitoringLoop integration (workflow)
9. Daily scanner integration (script)
10. Backfill script (script)
11. Monitor script integration (script)
12. Integration test
13. Documentation update

### Verification Checklist

After all tasks complete:

- [ ] `pytest tests/unit/` passes (all new + existing tests)
- [ ] `pytest tests/integration/test_alert_logging.py` passes
- [ ] `python scripts/backfill_position.py` runs successfully
- [ ] `python scripts/daily_run.py` logs signals to database
- [ ] `python scripts/monitor_positions.py --once` updates position snapshot
- [ ] Database has `alerts` and `open_positions` tables with data

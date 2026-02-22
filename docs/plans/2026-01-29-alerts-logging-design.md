# Alerts & Position Logging for Website Dashboard

**Date:** 2026-01-29
**Branch:** `feature/alerts-logging`
**Status:** ✅ Implemented (2026-01-29)

## Overview

Add database logging for alerts and open positions to support a website dashboard. The dashboard will poll the Neon PostgreSQL database to display real-time position status and historical alerts.

### Requirements

- **Real-time monitoring**: Current positions, P&L, stop levels
- **Historical review**: Past signals, exits, pyramids
- **Alert types**: Trading actions + position updates (not system events)
- **Website**: Polling-based (Vercel + Neon free tiers compatible)
- **Efficiency**: Write to DB only on meaningful changes

## Database Schema

### `alerts` table (immutable event log)

```sql
CREATE TABLE alerts (
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

CREATE INDEX idx_alerts_timestamp ON alerts(timestamp DESC);
CREATE INDEX idx_alerts_symbol ON alerts(symbol, timestamp DESC);
CREATE INDEX idx_alerts_unacknowledged ON alerts(acknowledged) WHERE acknowledged = FALSE;
```

**Alert types:**
- `ENTRY_SIGNAL` - Breakout signal detected by scanner
- `POSITION_OPENED` - Order filled, position established
- `POSITION_CLOSED` - Position fully exited (with final P&L)
- `EXIT_STOP` - 2N stop hit
- `EXIT_BREAKOUT` - Donchian exit triggered
- `PYRAMID_TRIGGER` - Pyramid level reached

### `open_positions` table (current state snapshot)

```sql
CREATE TABLE open_positions (
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
```

- One row per open position (upserted on changes)
- Row deleted when position closes
- Simple query: `SELECT * FROM open_positions`

## Integration Points

### 1. Daily Scanner (`scripts/daily_run.py`)

When signal detected:
```python
await alert_logger.log_signal(
    symbol="SPY",
    direction=Direction.LONG,
    system=System.S1,
    price=Decimal("450.00"),
    details={
        "breakout_level": 449.50,
        "n_value": 5.25,
        "dc20_high": 449.50,
    }
)
```

### 2. Position Entry (order fill)

```python
await alert_logger.log_position_opened(
    symbol="SPY",
    direction=Direction.LONG,
    system=System.S1,
    entry_price=Decimal("450.25"),
    contracts=100,
    stop_price=Decimal("439.75"),
    n_value=Decimal("5.25"),
)
# Also upserts open_positions row
```

### 3. Monitor Loop (`monitoring_loop.py`)

On action required:
```python
# EXIT_STOP or EXIT_BREAKOUT
await alert_logger.log_exit(
    symbol="SPY",
    alert_type=AlertType.EXIT_STOP,
    exit_price=Decimal("439.50"),
    details={"reason": "2N stop hit", "pnl": -1075.00}
)
# Deletes from open_positions

# PYRAMID_TRIGGER
await alert_logger.log_pyramid(
    symbol="SPY",
    trigger_price=Decimal("452.88"),
    new_units=2,
    new_stop=Decimal("442.38"),
)
# Updates open_positions
```

On significant change (no action):
```python
# Only update open_positions if:
# - Price moved > 0.5%
# - P&L changed > $50
# - Stop price changed
await position_repo.upsert(updated_snapshot)
```

## Domain Models

### `src/domain/models/alert.py`

```python
from enum import Enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class AlertType(str, Enum):
    ENTRY_SIGNAL = "ENTRY_SIGNAL"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"
    EXIT_STOP = "EXIT_STOP"
    EXIT_BREAKOUT = "EXIT_BREAKOUT"
    PYRAMID_TRIGGER = "PYRAMID_TRIGGER"

class Alert(BaseModel):
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

## Repository Interfaces

### `src/domain/interfaces/repositories.py` (additions)

```python
class AlertRepository(ABC):
    @abstractmethod
    async def save(self, alert: Alert) -> None: ...

    @abstractmethod
    async def get_recent(self, limit: int = 50) -> list[Alert]: ...

    @abstractmethod
    async def get_by_symbol(self, symbol: str, limit: int = 20) -> list[Alert]: ...

    @abstractmethod
    async def get_unacknowledged(self) -> list[Alert]: ...

    @abstractmethod
    async def acknowledge(self, alert_id: UUID) -> None: ...

class OpenPositionRepository(ABC):
    @abstractmethod
    async def upsert(self, position: OpenPositionSnapshot) -> None: ...

    @abstractmethod
    async def get_all(self) -> list[OpenPositionSnapshot]: ...

    @abstractmethod
    async def get(self, symbol: str) -> OpenPositionSnapshot | None: ...

    @abstractmethod
    async def delete(self, symbol: str) -> None: ...
```

## AlertLogger Command

### `src/application/commands/log_alert.py`

```python
class AlertLogger:
    def __init__(
        self,
        alert_repo: AlertRepository,
        position_repo: OpenPositionRepository,
    ): ...

    async def log_signal(self, symbol, direction, system, price, details) -> Alert: ...

    async def log_position_opened(self, symbol, direction, system,
                                   entry_price, contracts, stop_price, n_value) -> Alert: ...

    async def log_exit(self, symbol, alert_type, exit_price, details) -> Alert: ...

    async def log_pyramid(self, symbol, trigger_price, new_units, new_stop) -> Alert: ...

    async def update_position(self, snapshot: OpenPositionSnapshot) -> None: ...
```

## Significant Change Detection

```python
def is_significant_change(
    current: OpenPositionSnapshot,
    new_price: Decimal,
    new_pnl: Decimal,
    new_stop: Decimal | None = None,
) -> bool:
    """Determine if position change warrants a DB write."""

    # Price moved more than 0.5%
    if current.current_price:
        price_change = abs(new_price - current.current_price) / current.current_price
        if price_change > Decimal("0.005"):
            return True

    # P&L changed by more than $50
    if current.unrealized_pnl:
        if abs(new_pnl - current.unrealized_pnl) > Decimal("50"):
            return True

    # Stop price changed (pyramid happened)
    if new_stop and new_stop != current.stop_price:
        return True

    return False
```

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/domain/models/alert.py` | Create | Alert and OpenPositionSnapshot models |
| `src/domain/interfaces/repositories.py` | Modify | Add AlertRepository, OpenPositionRepository ABCs |
| `src/application/commands/log_alert.py` | Create | AlertLogger command |
| `src/adapters/repositories/postgres_alert_repo.py` | Create | Postgres implementation |
| `src/adapters/repositories/postgres_position_repo.py` | Create | Postgres implementation |
| `src/infrastructure/migrations/005_create_alerts_tables.sql` | Create | DB migration |
| `src/application/workflows/monitoring_loop.py` | Modify | Add alert/position logging |
| `scripts/daily_run.py` | Modify | Log entry signals |
| `scripts/backfill_position.py` | Create | One-time: insert current EFA position |

## Testing Strategy

### Unit Tests (~23 tests)

**AlertLogger tests** (`tests/unit/application/commands/test_log_alert.py`):
- `test_log_signal_creates_alert`
- `test_log_position_opened_creates_alert_and_position`
- `test_log_exit_creates_alert_and_deletes_position`
- `test_log_pyramid_creates_alert_and_updates_position`
- ~10 tests total

**Repository tests** (`tests/unit/adapters/repositories/`):
- `test_alert_repo_save_and_retrieve`
- `test_alert_repo_get_unacknowledged`
- `test_position_repo_upsert`
- `test_position_repo_delete`
- ~8 tests total

**Significant change tests**:
- `test_price_change_above_threshold`
- `test_price_change_below_threshold`
- `test_pnl_change_triggers_update`
- `test_stop_change_triggers_update`
- ~5 tests total

### Integration Test

- Full flow: scanner detects signal → alert in DB → position opened → monitor updates → exit logged

## Migration Plan

1. Run migration to create tables
2. Run backfill script to insert current EFA position
3. Deploy updated monitor loop
4. Verify alerts appearing in database
5. Website can begin polling

## Estimated Writes Per Day

With 1-5 positions during market hours:
- Alerts: 0-10 (only on signals/actions)
- Position updates: 5-20 (significant moves)
- Well within Neon free tier (no concerns)

## Website Query Examples

```sql
-- Dashboard: all open positions
SELECT * FROM open_positions ORDER BY entry_date;

-- Recent alerts (last 24 hours)
SELECT * FROM alerts
WHERE timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;

-- Unacknowledged alerts (for notification badge)
SELECT COUNT(*) FROM alerts WHERE acknowledged = FALSE;

-- Alerts for specific symbol
SELECT * FROM alerts
WHERE symbol = 'SPY'
ORDER BY timestamp DESC
LIMIT 20;
```

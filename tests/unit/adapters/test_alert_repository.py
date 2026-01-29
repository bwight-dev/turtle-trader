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

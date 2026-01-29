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
        assert AlertType.ENTRY_SIGNAL.value == "ENTRY_SIGNAL"
        # Also works in string comparisons
        assert AlertType.ENTRY_SIGNAL == "ENTRY_SIGNAL"


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

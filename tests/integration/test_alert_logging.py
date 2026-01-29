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
from src.infrastructure.database import close_pool, execute


@pytest.fixture(autouse=True)
async def cleanup_pool():
    """Clean up pool after each test."""
    yield
    await close_pool()


async def cleanup_test_symbol():
    """Clean up test data."""
    await execute("DELETE FROM alerts WHERE symbol = 'TEST'")
    await execute("DELETE FROM open_positions WHERE symbol = 'TEST'")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_position_lifecycle():
    """Test complete position lifecycle: signal -> open -> pyramid -> exit."""
    await cleanup_test_symbol()

    alert_repo = PostgresAlertRepository()
    position_repo = PostgresOpenPositionRepository()
    logger = AlertLogger(alert_repo, position_repo)

    try:
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
    finally:
        await cleanup_test_symbol()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_alert_acknowledge():
    """Test acknowledging alerts."""
    await cleanup_test_symbol()

    alert_repo = PostgresAlertRepository()
    position_repo = PostgresOpenPositionRepository()
    logger = AlertLogger(alert_repo, position_repo)

    try:
        # Create alert
        alert = await logger.log_signal(
            symbol="TEST",
            direction=Direction.LONG,
            system=System.S1,
            price=Decimal("100.00"),
        )

        # Should be unacknowledged
        unacked = await alert_repo.get_unacknowledged()
        assert any(a.id == alert.id for a in unacked)

        # Acknowledge it
        await alert_repo.acknowledge(alert.id)

        # Should no longer be unacknowledged
        unacked = await alert_repo.get_unacknowledged()
        assert not any(a.id == alert.id for a in unacked)
    finally:
        await cleanup_test_symbol()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_recent_alerts_ordered():
    """Test that recent alerts are ordered newest first."""
    await cleanup_test_symbol()

    alert_repo = PostgresAlertRepository()
    position_repo = PostgresOpenPositionRepository()
    logger = AlertLogger(alert_repo, position_repo)

    try:
        # Create multiple alerts
        for i in range(3):
            await logger.log_signal(
                symbol="TEST",
                direction=Direction.LONG,
                system=System.S1,
                price=Decimal(f"{100 + i}"),
            )
            await asyncio.sleep(0.01)  # Small delay to ensure different timestamps

        # Get recent
        alerts = await alert_repo.get_by_symbol("TEST")
        assert len(alerts) == 3

        # Should be newest first (highest price was created last)
        prices = [float(a.price) for a in alerts]
        assert prices == sorted(prices, reverse=True)
    finally:
        await cleanup_test_symbol()

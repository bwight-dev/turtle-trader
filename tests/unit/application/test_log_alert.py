"""Unit tests for AlertLogger command."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.application.commands.log_alert import AlertLogger, is_significant_change
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

        # 0.2% price change, $20 P&L change (both below thresholds)
        assert is_significant_change(
            snapshot,
            new_price=Decimal("450.90"),
            new_pnl=Decimal("20.00"),
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

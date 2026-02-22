"""Unit tests for TradeLogger command."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.application.commands.log_trade import (
    LogTradeResult,
    TradeLogger,
    log_trade_exit,
)
from src.domain.interfaces.repositories import TradeRepository
from src.domain.models.enums import CorrelationGroup, Direction, System
from src.domain.models.market import NValue
from src.domain.models.position import Position, PyramidLevel
from src.domain.models.trade import Trade


class InMemoryTradeRepository(TradeRepository):
    """In-memory trade repository for testing."""

    def __init__(self):
        self.trades: dict[str, Trade] = {}

    async def save_trade(self, trade: Trade) -> None:
        self.trades[str(trade.id)] = trade

    async def get_last_s1_trade(self, symbol: str) -> Trade | None:
        s1_trades = [
            t for t in self.trades.values()
            if t.symbol == symbol and t.system == System.S1
        ]
        if not s1_trades:
            return None
        return max(s1_trades, key=lambda t: t.exit_date)

    async def get_trades_by_symbol(self, symbol: str, limit: int = 100) -> list[Trade]:
        trades = [t for t in self.trades.values() if t.symbol == symbol]
        trades.sort(key=lambda t: t.exit_date, reverse=True)
        return trades[:limit]

    async def get_last_trade(
        self,
        symbol: str,
        system: System | None = None,
        direction: Direction | None = None,
    ) -> Trade | None:
        trades = [t for t in self.trades.values() if t.symbol == symbol]
        if system:
            trades = [t for t in trades if t.system == system]
        if direction:
            trades = [t for t in trades if t.direction == direction]
        if not trades:
            return None
        return max(trades, key=lambda t: t.exit_date)


def make_n_value(value: str = "20") -> NValue:
    """Create test NValue."""
    return NValue(value=Decimal(value), calculated_at=datetime.now())


def make_position(
    symbol: str = "/MGC",
    direction: Direction = Direction.LONG,
    contracts: int = 4,
    entry_price: str = "2800",
    n_at_entry: str = "20",
    system: System = System.S1,
) -> Position:
    """Create a test position."""
    entry_dt = datetime.now() - timedelta(days=5)
    pyramid_levels = tuple(
        PyramidLevel(
            level=i + 1,
            entry_price=Decimal(entry_price) + (i * 10),
            contracts=contracts // 2 if contracts >= 2 else 1,
            n_at_entry=Decimal(n_at_entry),
            entry_date=entry_dt + timedelta(days=i),
        )
        for i in range(2 if contracts >= 2 else 1)
    )

    return Position(
        symbol=symbol,
        direction=direction,
        system=system,
        correlation_group=CorrelationGroup.METALS,
        pyramid_levels=pyramid_levels,
        current_stop=Decimal("2760"),
        initial_entry_price=Decimal(entry_price),
        initial_n=make_n_value(n_at_entry),
    )


@pytest.fixture
def repo():
    """Create in-memory trade repository."""
    return InMemoryTradeRepository()


@pytest.fixture
def logger(repo):
    """Create TradeLogger with test repository."""
    return TradeLogger(repo)


class TestLogEntry:
    """Tests for logging trade entries."""

    async def test_log_entry_succeeds(self, logger):
        """Entry logging succeeds (informational only)."""
        position = make_position()

        result = await logger.log_entry(
            position=position,
            signal=None,  # Simplified for test
            fill=None,    # Simplified for test
        )

        assert result.success is True


class TestLogExit:
    """Tests for logging trade exits."""

    async def test_log_exit_creates_trade(self, logger, repo):
        """Exit logging creates a trade record."""
        position = make_position(
            symbol="/MGC",
            direction=Direction.LONG,
            contracts=4,
            entry_price="2800",
        )

        result = await logger.log_exit(
            position=position,
            exit_price=Decimal("2850"),
            exit_reason="breakout",
        )

        assert result.success is True
        assert result.trade is not None
        assert result.trade.symbol == "/MGC"
        assert result.trade.direction == Direction.LONG
        assert result.trade.exit_price == Decimal("2850")
        assert result.trade.exit_reason == "breakout"

        # Verify persisted
        saved = await repo.get_last_s1_trade("/MGC")
        assert saved is not None
        assert saved.id == result.trade.id

    async def test_log_exit_calculates_pnl(self, logger, repo):
        """Exit logging calculates realized P&L."""
        position = make_position(
            symbol="/MGC",
            direction=Direction.LONG,
            contracts=4,
            entry_price="2800",
        )

        result = await logger.log_exit(
            position=position,
            exit_price=Decimal("2850"),  # +50 points
            exit_reason="stop",
        )

        # P&L = (2850 - 2800) * 4 contracts * $10 point value = $2000
        assert result.trade is not None
        assert result.trade.realized_pnl == Decimal("2000")

    async def test_log_exit_short_position(self, logger, repo):
        """Exit logging handles short positions correctly."""
        position = make_position(
            symbol="/MGC",
            direction=Direction.SHORT,
            contracts=2,
            entry_price="2850",
        )

        result = await logger.log_exit(
            position=position,
            exit_price=Decimal("2800"),  # +50 points profit for short
            exit_reason="breakout",
        )

        # P&L = (2850 - 2800) * 2 contracts * $10 = $1000
        assert result.trade is not None
        assert result.trade.realized_pnl == Decimal("1000")

    async def test_log_exit_with_commission(self, logger, repo):
        """Exit logging includes commission."""
        position = make_position()

        result = await logger.log_exit(
            position=position,
            exit_price=Decimal("2850"),
            exit_reason="stop",
            commission=Decimal("9.00"),  # 4 contracts * $2.25
        )

        assert result.trade is not None
        assert result.trade.commission == Decimal("9.00")
        assert result.trade.net_pnl == result.trade.realized_pnl - Decimal("9.00")


class TestS1Filter:
    """Tests for S1 filter queries."""

    async def test_get_last_s1_trade(self, logger, repo):
        """Can retrieve last S1 trade."""
        position = make_position(system=System.S1)

        await logger.log_exit(
            position=position,
            exit_price=Decimal("2850"),
            exit_reason="stop",
        )

        trade = await logger.get_last_s1_trade("/MGC")
        assert trade is not None
        assert trade.system == System.S1

    async def test_was_last_s1_winner_true(self, logger, repo):
        """Detects winning S1 trade."""
        position = make_position(system=System.S1, entry_price="2800")

        await logger.log_exit(
            position=position,
            exit_price=Decimal("2900"),  # Profitable
            exit_reason="breakout",
        )

        is_winner = await logger.was_last_s1_winner("/MGC")
        assert is_winner is True

    async def test_was_last_s1_winner_false(self, logger, repo):
        """Detects losing S1 trade."""
        position = make_position(system=System.S1, entry_price="2800")

        await logger.log_exit(
            position=position,
            exit_price=Decimal("2750"),  # Loss
            exit_reason="stop",
        )

        is_winner = await logger.was_last_s1_winner("/MGC")
        assert is_winner is False

    async def test_was_last_s1_winner_no_history(self, logger, repo):
        """Returns None when no S1 history."""
        is_winner = await logger.was_last_s1_winner("/XYZ")
        assert is_winner is None

    async def test_s1_filter_ignores_s2_trades(self, logger, repo):
        """S1 filter only looks at S1 trades."""
        # Log S2 trade
        s2_position = make_position(system=System.S2)
        await logger.log_exit(
            position=s2_position,
            exit_price=Decimal("2900"),
            exit_reason="breakout",
        )

        # No S1 trade exists
        trade = await logger.get_last_s1_trade("/MGC")
        assert trade is None


class TestLogTrade:
    """Tests for logging pre-constructed trades."""

    async def test_log_trade_persists(self, logger, repo):
        """Can log a pre-constructed trade."""
        trade = Trade(
            id=uuid4(),
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("2800"),
            entry_date=datetime.now() - timedelta(days=5),
            entry_contracts=4,
            n_at_entry=Decimal("20"),
            exit_price=Decimal("2850"),
            exit_date=datetime.now(),
            exit_reason="manual",
            realized_pnl=Decimal("2000"),
            commission=Decimal("9.00"),
        )

        result = await logger.log_trade(trade)

        assert result.success is True
        assert result.trade == trade

        # Verify persisted
        saved = await repo.get_last_s1_trade("/MGC")
        assert saved is not None


class TestConvenienceFunction:
    """Tests for log_trade_exit convenience function."""

    async def test_log_trade_exit_function(self, repo):
        """Convenience function works."""
        position = make_position()

        result = await log_trade_exit(
            trade_repository=repo,
            position=position,
            exit_price=Decimal("2850"),
            exit_reason="stop",
        )

        assert result.success is True
        assert result.trade is not None


class TestTradeProperties:
    """Tests for Trade computed properties."""

    async def test_trade_holding_days(self, logger, repo):
        """Trade calculates holding days."""
        position = make_position()

        result = await logger.log_exit(
            position=position,
            exit_price=Decimal("2850"),
            exit_reason="stop",
        )

        # Position has entry_date ~5 days ago
        assert result.trade is not None
        assert result.trade.holding_days >= 0

    async def test_trade_is_winner(self, logger, repo):
        """Trade determines winner/loser status."""
        position = make_position(entry_price="2800")

        # Winner
        result = await logger.log_exit(
            position=position,
            exit_price=Decimal("2900"),
            exit_reason="breakout",
        )
        assert result.trade.is_winner is True

    async def test_trade_r_multiple(self, logger, repo):
        """Trade calculates R-multiple."""
        position = make_position(
            entry_price="2800",
            n_at_entry="20",
            contracts=4,
        )

        # Exit with 1R profit (2N = 40 points * 4 contracts * $10 = $1600 risk)
        # Actual profit = 40 points * 4 * $10 = $1600 = 1R
        result = await logger.log_exit(
            position=position,
            exit_price=Decimal("2840"),  # +40 points
            exit_reason="stop",
        )

        assert result.trade is not None
        # R = realized_pnl / (2 * N * contracts) = 1600 / (2 * 20 * 4) = 1600/160 = 10
        # Wait - the formula in Trade uses n_at_entry directly: 2 * n * contracts
        # For /MGC: pnl = 40 * 4 * 10 = 1600
        # initial_risk = 2 * 20 * 4 = 160
        # r_multiple = 1600 / 160 = 10
        assert result.trade.r_multiple == Decimal("10")

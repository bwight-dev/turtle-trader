"""Unit tests for S1 filter service."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.domain.models.enums import Direction, System
from src.domain.models.signal import Signal
from src.domain.models.trade import Trade
from src.domain.services.s1_filter import S1Filter


@pytest.fixture
def mock_repo():
    """Create mock trade repository."""
    return AsyncMock()


@pytest.fixture
def s1_filter(mock_repo):
    """Create S1Filter with mock repository."""
    return S1Filter(mock_repo)


@pytest.fixture
def s1_long_signal():
    """Create sample S1 long signal."""
    return Signal(
        symbol="/MGC",
        direction=Direction.LONG,
        system=System.S1,
        breakout_price=Decimal("2860"),
        channel_value=Decimal("2850"),
    )


@pytest.fixture
def s2_long_signal():
    """Create sample S2 long signal."""
    return Signal(
        symbol="/MGC",
        direction=Direction.LONG,
        system=System.S2,
        breakout_price=Decimal("2910"),
        channel_value=Decimal("2900"),
    )


@pytest.fixture
def winning_trade():
    """Create a winning S1 trade."""
    return Trade(
        symbol="/MGC",
        direction=Direction.LONG,
        system=System.S1,
        entry_price=Decimal("2800"),
        entry_date=datetime(2026, 1, 1, 10, 0),
        entry_contracts=1,
        n_at_entry=Decimal("50"),
        exit_price=Decimal("2900"),  # $100 profit
        exit_date=datetime(2026, 1, 15, 14, 0),
        exit_reason="breakout",
        realized_pnl=Decimal("1000"),  # Assuming $10/point
        commission=Decimal("5"),
    )


@pytest.fixture
def losing_trade():
    """Create a losing S1 trade."""
    return Trade(
        symbol="/MGC",
        direction=Direction.LONG,
        system=System.S1,
        entry_price=Decimal("2800"),
        entry_date=datetime(2026, 1, 1, 10, 0),
        entry_contracts=1,
        n_at_entry=Decimal("50"),
        exit_price=Decimal("2700"),  # $100 loss
        exit_date=datetime(2026, 1, 5, 14, 0),
        exit_reason="stop",
        realized_pnl=Decimal("-1000"),
        commission=Decimal("5"),
    )


class TestS1FilterWithS1Signal:
    """Tests for S1 signal filtering (Rule 7)."""

    async def test_skip_after_winner(self, s1_filter, mock_repo, s1_long_signal, winning_trade):
        """Rule 7: Skip S1 after previous S1 was a winner."""
        mock_repo.get_last_s1_trade.return_value = winning_trade

        result = await s1_filter.should_take_signal(s1_long_signal)

        assert result.take_signal is False
        assert result.last_s1_was_winner is True
        assert "Rule 7" in result.reason
        assert "winner" in result.reason.lower()

    async def test_take_after_loser(self, s1_filter, mock_repo, s1_long_signal, losing_trade):
        """Take S1 signal after previous S1 was a loser."""
        mock_repo.get_last_s1_trade.return_value = losing_trade

        result = await s1_filter.should_take_signal(s1_long_signal)

        assert result.take_signal is True
        assert result.last_s1_was_winner is False
        assert "loser" in result.reason.lower()

    async def test_take_with_no_history(self, s1_filter, mock_repo, s1_long_signal):
        """Take S1 signal when no trade history exists."""
        mock_repo.get_last_s1_trade.return_value = None

        result = await s1_filter.should_take_signal(s1_long_signal)

        assert result.take_signal is True
        assert result.last_s1_was_winner is None
        assert "no s1 trade history" in result.reason.lower()

    async def test_filter_result_includes_signal(self, s1_filter, mock_repo, s1_long_signal):
        """FilterResult should include the evaluated signal."""
        mock_repo.get_last_s1_trade.return_value = None

        result = await s1_filter.should_take_signal(s1_long_signal)

        assert result.signal == s1_long_signal


class TestS2FilterNever:
    """Tests for S2 signals (Rule 9: always take)."""

    async def test_s2_never_filtered_after_winner(self, s1_filter, mock_repo, s2_long_signal, winning_trade):
        """Rule 9: S2 signals always taken, even after S1 winner."""
        mock_repo.get_last_s1_trade.return_value = winning_trade

        result = await s1_filter.should_take_signal(s2_long_signal)

        assert result.take_signal is True
        assert "failsafe" in result.reason.lower()
        # Should NOT call trade repo for S2 signals
        mock_repo.get_last_s1_trade.assert_not_called()

    async def test_s2_never_filtered_after_loser(self, s1_filter, mock_repo, s2_long_signal, losing_trade):
        """Rule 9: S2 signals always taken, even after S1 loser."""
        mock_repo.get_last_s1_trade.return_value = losing_trade

        result = await s1_filter.should_take_signal(s2_long_signal)

        assert result.take_signal is True
        mock_repo.get_last_s1_trade.assert_not_called()

    async def test_s2_taken_with_no_history(self, s1_filter, mock_repo, s2_long_signal):
        """Rule 9: S2 signals taken when no history exists."""
        mock_repo.get_last_s1_trade.return_value = None

        result = await s1_filter.should_take_signal(s2_long_signal)

        assert result.take_signal is True
        mock_repo.get_last_s1_trade.assert_not_called()


class TestCheckSymbol:
    """Tests for check_symbol status query."""

    async def test_check_symbol_no_history(self, s1_filter, mock_repo):
        """Check status when no S1 history."""
        mock_repo.get_last_s1_trade.return_value = None

        status = await s1_filter.check_symbol("/MGC")

        assert status["symbol"] == "/MGC"
        assert status["has_s1_history"] is False
        assert status["would_filter_s1"] is False

    async def test_check_symbol_would_filter(self, s1_filter, mock_repo, winning_trade):
        """Check status when last S1 was winner (would filter)."""
        mock_repo.get_last_s1_trade.return_value = winning_trade

        status = await s1_filter.check_symbol("/MGC")

        assert status["has_s1_history"] is True
        assert status["would_filter_s1"] is True
        assert status["last_s1_was_winner"] is True
        assert "skip" in status["reason"].lower()

    async def test_check_symbol_would_not_filter(self, s1_filter, mock_repo, losing_trade):
        """Check status when last S1 was loser (would not filter)."""
        mock_repo.get_last_s1_trade.return_value = losing_trade

        status = await s1_filter.check_symbol("/MGC")

        assert status["has_s1_history"] is True
        assert status["would_filter_s1"] is False
        assert status["last_s1_was_winner"] is False
        assert "take" in status["reason"].lower()


class TestShortSignals:
    """Tests for short direction signals."""

    async def test_s1_short_after_short_winner(self, s1_filter, mock_repo):
        """Skip S1 short after previous S1 short was winner."""
        short_signal = Signal(
            symbol="/MGC",
            direction=Direction.SHORT,
            system=System.S1,
            breakout_price=Decimal("2690"),
            channel_value=Decimal("2700"),
        )

        winning_short = Trade(
            symbol="/MGC",
            direction=Direction.SHORT,
            system=System.S1,
            entry_price=Decimal("2700"),
            entry_date=datetime(2026, 1, 1, 10, 0),
            entry_contracts=1,
            n_at_entry=Decimal("50"),
            exit_price=Decimal("2600"),  # Profitable short
            exit_date=datetime(2026, 1, 10, 14, 0),
            exit_reason="breakout",
            realized_pnl=Decimal("1000"),
        )

        mock_repo.get_last_s1_trade.return_value = winning_short

        result = await s1_filter.should_take_signal(short_signal)

        assert result.take_signal is False
        assert result.last_s1_was_winner is True

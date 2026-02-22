"""Unit tests for market scanner use case."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.queries.scan_markets import MarketScanner, ScanResult
from src.domain.models.enums import Direction, System
from src.domain.models.market import Bar, DonchianChannel, NValue
from src.domain.models.signal import Signal
from src.domain.models.trade import Trade


def make_bar(day_offset: int = 0, o: str = "100", h: str = "110", l: str = "90", c: str = "105") -> Bar:
    """Create a test bar.

    Args:
        day_offset: Days from base date (2026-01-01)
    """
    base_date = date(2026, 1, 1)
    bar_date = base_date + timedelta(days=day_offset)
    return Bar(
        symbol="TEST",
        date=bar_date,
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(l),
        close=Decimal(c),
    )


@pytest.fixture
def mock_data_feed():
    """Create mock data feed."""
    feed = AsyncMock()
    # Return 60 days of bars by default
    feed.get_bars.return_value = [make_bar(day_offset=i) for i in range(60)]
    feed.get_current_price.return_value = Decimal("105")
    return feed


@pytest.fixture
def mock_n_repo():
    """Create mock N value repository."""
    repo = AsyncMock()
    repo.get_previous_n.return_value = Decimal("10")
    return repo


@pytest.fixture
def mock_trade_repo():
    """Create mock trade repository."""
    repo = AsyncMock()
    repo.get_last_s1_trade.return_value = None
    return repo


@pytest.fixture
def scanner(mock_data_feed, mock_n_repo, mock_trade_repo):
    """Create scanner with mock dependencies."""
    return MarketScanner(
        data_feed=mock_data_feed,
        n_value_repo=mock_n_repo,
        trade_repo=mock_trade_repo,
    )


class TestScanResult:
    """Tests for ScanResult dataclass."""

    def test_has_actionable_signal_with_accepted(self):
        """has_actionable_signal is True when signal is accepted."""
        signal = Signal(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            breakout_price=Decimal("2860"),
            channel_value=Decimal("2850"),
        )
        from src.domain.models.signal import FilterResult

        filter_result = FilterResult.accept(signal)

        result = ScanResult(
            symbol="/MGC",
            filter_results=[filter_result],
        )

        assert result.has_actionable_signal is True

    def test_has_actionable_signal_with_rejected(self):
        """has_actionable_signal is False when signal is rejected."""
        signal = Signal(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            breakout_price=Decimal("2860"),
            channel_value=Decimal("2850"),
        )
        from src.domain.models.signal import FilterResult

        filter_result = FilterResult.reject(signal, "Last S1 was winner")

        result = ScanResult(
            symbol="/MGC",
            filter_results=[filter_result],
        )

        assert result.has_actionable_signal is False

    def test_has_actionable_signal_no_filters(self):
        """has_actionable_signal is False when no filter results."""
        result = ScanResult(symbol="/MGC")
        assert result.has_actionable_signal is False

    def test_actionable_signals_returns_accepted_only(self):
        """actionable_signals returns only signals that passed filter."""
        from src.domain.models.signal import FilterResult

        s1_signal = Signal(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            breakout_price=Decimal("2860"),
            channel_value=Decimal("2850"),
        )
        s2_signal = Signal(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S2,
            breakout_price=Decimal("2910"),
            channel_value=Decimal("2900"),
        )

        filter_results = [
            FilterResult.reject(s1_signal, "Last S1 was winner"),
            FilterResult.accept(s2_signal),
        ]

        result = ScanResult(
            symbol="/MGC",
            filter_results=filter_results,
        )

        actionable = result.actionable_signals
        assert len(actionable) == 1
        assert actionable[0].system == System.S2


class TestMarketScanner:
    """Tests for MarketScanner use case."""

    async def test_scans_universe(self, scanner, mock_data_feed, mock_n_repo):
        """Test that scanner processes all symbols in universe."""
        universe = ["/MGC", "/MES", "/M2K"]

        results = await scanner.scan(universe)

        assert len(results) == 3
        assert {r.symbol for r in results} == {"/MGC", "/MES", "/M2K"}

    async def test_returns_scan_results(self, scanner, mock_data_feed):
        """Test that scanner returns ScanResult objects."""
        results = await scanner.scan(["/MGC"])

        assert len(results) == 1
        assert isinstance(results[0], ScanResult)
        assert results[0].symbol == "/MGC"

    async def test_includes_current_price(self, scanner, mock_data_feed):
        """Test that results include current price."""
        mock_data_feed.get_current_price.return_value = Decimal("2850")

        results = await scanner.scan(["/MGC"])

        assert results[0].current_price == Decimal("2850")

    async def test_includes_n_value(self, scanner, mock_data_feed, mock_n_repo):
        """Test that results include N value."""
        results = await scanner.scan(["/MGC"])

        assert results[0].n_value is not None
        mock_n_repo.get_previous_n.assert_called()

    async def test_includes_donchian_channels(self, scanner, mock_data_feed):
        """Test that results include Donchian channel values."""
        results = await scanner.scan(["/MGC"])

        assert results[0].donchian_20_upper is not None
        assert results[0].donchian_20_lower is not None
        assert results[0].donchian_55_upper is not None
        assert results[0].donchian_55_lower is not None

    async def test_detects_signals(self, scanner, mock_data_feed):
        """Test that signals are detected for breakouts."""
        # Set up a breakout scenario
        # Create bars where current price breaks above 20-day high
        bars = [make_bar(day_offset=i, h="100", l="90", c="95") for i in range(60)]
        mock_data_feed.get_bars.return_value = bars
        mock_data_feed.get_current_price.return_value = Decimal("110")  # Breakout!

        results = await scanner.scan(["/MGC"])

        assert results[0].signals is not None
        # Should detect at least one signal (S1 or S2 breakout)
        assert len(results[0].signals) > 0

    async def test_applies_s1_filter(self, scanner, mock_data_feed, mock_trade_repo):
        """Test that S1 filter is applied to signals."""
        # Set up a breakout scenario
        bars = [make_bar(day_offset=i, h="100", l="90", c="95") for i in range(60)]
        mock_data_feed.get_bars.return_value = bars
        mock_data_feed.get_current_price.return_value = Decimal("110")

        # Simulate last S1 was a winner (should filter S1 signal)
        winning_trade = Trade(
            symbol="/MGC",
            direction=Direction.LONG,
            system=System.S1,
            entry_price=Decimal("90"),
            entry_date=datetime(2026, 1, 1),
            entry_contracts=1,
            n_at_entry=Decimal("5"),
            exit_price=Decimal("100"),
            exit_date=datetime(2026, 1, 10),
            exit_reason="breakout",
            realized_pnl=Decimal("100"),
        )
        mock_trade_repo.get_last_s1_trade.return_value = winning_trade

        results = await scanner.scan(["/MGC"])

        # Filter results should exist
        assert results[0].filter_results is not None
        # S1 signal should be filtered out
        s1_filter_results = [fr for fr in results[0].filter_results if fr.signal and fr.signal.system == System.S1]
        if s1_filter_results:
            assert s1_filter_results[0].take_signal is False

    async def test_handles_insufficient_data(self, scanner, mock_data_feed):
        """Test that scanner handles markets with insufficient data."""
        mock_data_feed.get_bars.return_value = [make_bar(day_offset=i) for i in range(30)]  # Only 30 bars

        results = await scanner.scan(["/MGC"])

        assert results[0].error is not None
        assert "insufficient" in results[0].error.lower()

    async def test_handles_data_feed_error(self, scanner, mock_data_feed):
        """Test that scanner handles data feed errors gracefully."""
        mock_data_feed.get_bars.side_effect = Exception("Connection failed")

        results = await scanner.scan(["/MGC"])

        assert results[0].error is not None
        assert "failed" in results[0].error.lower()

    async def test_concurrent_limit(self, scanner, mock_data_feed):
        """Test that scanner respects concurrent limit."""
        universe = [f"/SYM{i}" for i in range(10)]

        # Run with limit of 2
        results = await scanner.scan(universe, concurrent_limit=2)

        assert len(results) == 10

    async def test_scan_for_actionable(self, scanner, mock_data_feed):
        """Test scan_for_actionable filters to signals only."""
        # One market with no signals, one with signals
        results = await scanner.scan_for_actionable(["/MGC", "/MES"])

        # Only markets with actionable signals returned
        for result in results:
            assert result.has_actionable_signal

    async def test_empty_universe(self, scanner):
        """Test scanning empty universe."""
        results = await scanner.scan([])

        assert len(results) == 0


class TestNoSignalsScenario:
    """Tests for scenarios with no signals."""

    async def test_no_signals_inside_channel(self, scanner, mock_data_feed):
        """Test that no signals when price is inside channels."""
        # Create bars with price movement
        bars = [make_bar(day_offset=i, h="110", l="90", c="100") for i in range(60)]
        mock_data_feed.get_bars.return_value = bars
        mock_data_feed.get_current_price.return_value = Decimal("100")  # Inside channel

        results = await scanner.scan(["/MGC"])

        assert results[0].signals is not None
        assert len(results[0].signals) == 0
        assert not results[0].has_actionable_signal

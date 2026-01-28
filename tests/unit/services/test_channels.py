"""Unit tests for Donchian channel calculations."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.domain.models.market import Bar
from src.domain.services.channels import (
    calculate_all_channels,
    calculate_channel_series,
    calculate_donchian,
    is_breakout_long,
    is_breakout_short,
    is_exit_long,
    is_exit_short,
)


def load_fixture_bars() -> list[Bar]:
    """Load MGC bars from test fixture."""
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "mgc_bars.json"
    with open(fixture_path) as f:
        data = json.load(f)

    return [
        Bar(
            symbol=item["symbol"],
            date=date.fromisoformat(item["date"]),
            open=Decimal(item["open"]),
            high=Decimal(item["high"]),
            low=Decimal(item["low"]),
            close=Decimal(item["close"]),
            volume=item["volume"],
        )
        for item in data
    ]


@pytest.fixture
def mgc_bars():
    """Load MGC fixture data."""
    return load_fixture_bars()


@pytest.fixture
def simple_bars():
    """Create simple bars with known highs/lows."""
    return [
        Bar(symbol="TEST", date=date(2026, 1, i + 1),
            open=Decimal("100"), high=Decimal(str(100 + i)),
            low=Decimal(str(90 - i)), close=Decimal("100"))
        for i in range(25)
    ]


class TestCalculateDonchian:
    """Tests for Donchian channel calculation."""

    def test_donchian_requires_minimum_bars(self):
        """Test that calculation requires minimum bars."""
        bars = load_fixture_bars()[:5]

        with pytest.raises(ValueError, match="Need at least 20 bars"):
            calculate_donchian(bars, period=20)

    def test_donchian_20_basic(self, mgc_bars):
        """Test basic 20-day Donchian calculation."""
        dc = calculate_donchian(mgc_bars, period=20)

        assert dc.period == 20
        assert dc.upper > dc.lower
        assert dc.upper > 0
        assert dc.lower > 0

    def test_donchian_uses_last_n_bars(self, simple_bars):
        """Test that Donchian uses last N bars."""
        dc = calculate_donchian(simple_bars, period=10)

        # Last 10 bars: i = 15..24
        # High of bar i = 100 + i, so max = 100 + 24 = 124
        # Low of bar i = 90 - i, so min = 90 - 24 = 66
        assert dc.upper == Decimal("124")
        assert dc.lower == Decimal("66")

    def test_donchian_10_period(self, mgc_bars):
        """Test 10-day Donchian for S1 exit."""
        dc = calculate_donchian(mgc_bars, period=10)

        assert dc.period == 10
        assert dc.upper > dc.lower


class TestCalculateAllChannels:
    """Tests for calculating all channels at once."""

    def test_all_channels_returns_three(self, mgc_bars):
        """Test that all three channels are returned."""
        channels = calculate_all_channels(mgc_bars)

        assert "dc_10" in channels
        assert "dc_20" in channels
        assert "dc_55" in channels

    def test_all_channels_periods_correct(self, mgc_bars):
        """Test that channel periods are correct."""
        channels = calculate_all_channels(mgc_bars)

        assert channels["dc_10"].period == 10
        assert channels["dc_20"].period == 20
        assert channels["dc_55"].period == 55

    def test_all_channels_requires_55_bars(self):
        """Test that 55 bars are required."""
        bars = load_fixture_bars()[:30]

        with pytest.raises(ValueError, match="Need at least 55 bars"):
            calculate_all_channels(bars)


class TestBreakoutDetection:
    """Tests for breakout detection."""

    def test_breakout_long_above_upper(self, mgc_bars):
        """Test long breakout detection."""
        dc = calculate_donchian(mgc_bars, period=20)

        # Price above upper = breakout
        assert is_breakout_long(dc.upper + 1, dc) is True

        # Price at upper = no breakout (must be above)
        assert is_breakout_long(dc.upper, dc) is False

        # Price below upper = no breakout
        assert is_breakout_long(dc.upper - 1, dc) is False

    def test_breakout_short_below_lower(self, mgc_bars):
        """Test short breakout detection."""
        dc = calculate_donchian(mgc_bars, period=20)

        # Price below lower = breakout
        assert is_breakout_short(dc.lower - 1, dc) is True

        # Price at lower = no breakout
        assert is_breakout_short(dc.lower, dc) is False

        # Price above lower = no breakout
        assert is_breakout_short(dc.lower + 1, dc) is False


class TestExitDetection:
    """Tests for exit signal detection."""

    def test_exit_long_at_lower(self, mgc_bars):
        """Test long exit at channel lower."""
        dc = calculate_donchian(mgc_bars, period=10)

        # Price at or below lower = exit
        assert is_exit_long(dc.lower, dc) is True
        assert is_exit_long(dc.lower - 1, dc) is True

        # Price above lower = hold
        assert is_exit_long(dc.lower + 1, dc) is False

    def test_exit_short_at_upper(self, mgc_bars):
        """Test short exit at channel upper."""
        dc = calculate_donchian(mgc_bars, period=10)

        # Price at or above upper = exit
        assert is_exit_short(dc.upper, dc) is True
        assert is_exit_short(dc.upper + 1, dc) is True

        # Price below upper = hold
        assert is_exit_short(dc.upper - 1, dc) is False


class TestChannelSeries:
    """Tests for channel series calculation."""

    def test_series_length(self, mgc_bars):
        """Test that series returns correct number of values."""
        series = calculate_channel_series(mgc_bars, period=20)

        # Should have one channel per bar starting from position 20
        expected_length = len(mgc_bars) - 20 + 1
        assert len(series) == expected_length

    def test_series_last_matches_single(self, mgc_bars):
        """Test that last series value matches single calculation."""
        series = calculate_channel_series(mgc_bars, period=20)
        single = calculate_donchian(mgc_bars, period=20)

        assert series[-1].upper == single.upper
        assert series[-1].lower == single.lower

    def test_series_all_valid(self, mgc_bars):
        """Test that all channel values are valid."""
        series = calculate_channel_series(mgc_bars, period=20)

        for dc in series:
            assert dc.upper > dc.lower
            assert dc.upper > 0
            assert dc.lower > 0

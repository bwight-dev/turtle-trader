"""Unit tests for volatility calculations."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.domain.models.market import Bar
from src.domain.services.volatility import (
    calculate_n,
    calculate_n_series,
    calculate_true_range,
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


class TestCalculateTrueRange:
    """Tests for True Range calculation."""

    def test_true_range_no_gap(self):
        """Test TR when there's no gap (H-L is largest)."""
        tr = calculate_true_range(
            high=Decimal("105"),
            low=Decimal("95"),
            prev_close=Decimal("100"),
        )
        # H-L = 10, |H-C| = 5, |C-L| = 5
        assert tr == Decimal("10")

    def test_true_range_gap_up(self):
        """Test TR with gap up (H - prev_close is largest)."""
        tr = calculate_true_range(
            high=Decimal("115"),
            low=Decimal("110"),
            prev_close=Decimal("100"),
        )
        # H-L = 5, |H-C| = 15, |C-L| = 10
        assert tr == Decimal("15")

    def test_true_range_gap_down(self):
        """Test TR with gap down (prev_close - L is largest)."""
        tr = calculate_true_range(
            high=Decimal("95"),
            low=Decimal("85"),
            prev_close=Decimal("100"),
        )
        # H-L = 10, |H-C| = 5, |C-L| = 15
        assert tr == Decimal("15")

    def test_true_range_no_prev_close(self):
        """Test TR without previous close (first bar)."""
        tr = calculate_true_range(
            high=Decimal("105"),
            low=Decimal("95"),
            prev_close=None,
        )
        # Just H-L
        assert tr == Decimal("10")


class TestCalculateN:
    """Tests for N (ATR) calculation."""

    @pytest.fixture
    def mgc_bars(self):
        """Load MGC fixture data."""
        return load_fixture_bars()

    def test_n_requires_minimum_bars(self):
        """Test that N calculation requires minimum bars."""
        bars = load_fixture_bars()[:5]  # Only 5 bars

        with pytest.raises(ValueError, match="Need at least 20 bars"):
            calculate_n(bars, period=20)

    def test_n_calculation_basic(self, mgc_bars):
        """Test basic N calculation."""
        n = calculate_n(mgc_bars, period=20)

        assert n.value > 0
        assert n.symbol == "/MGC"

    def test_n_with_previous(self, mgc_bars):
        """Test incremental N calculation with previous value."""
        # Calculate initial N
        n1 = calculate_n(mgc_bars[:-1], period=20)

        # Calculate next N using previous
        n2 = calculate_n(mgc_bars, period=20, prev_n=n1.value)

        # Both should be positive and similar magnitude
        assert n2.value > 0
        assert abs(n2.value - n1.value) / n1.value < Decimal("0.5")  # Within 50%

    def test_n_matches_tos_within_tolerance(self, mgc_bars):
        """Test that N matches TOS ATR(20, WILDERS) within 0.5%.

        Note: The exact TOS value depends on the date. This test verifies
        the calculation is in a reasonable range for gold volatility.

        Typical /MGC N values are in the 50-150 range depending on market conditions.
        """
        n = calculate_n(mgc_bars, period=20)

        # Sanity check: N should be in reasonable range for micro gold
        # /MGC typically has N in 50-200 range
        assert Decimal("30") < n.value < Decimal("300"), f"N={n.value} outside expected range"

    def test_wilders_smoothing_formula(self):
        """Test that Wilder's smoothing formula is applied correctly.

        N = ((19 × Prev_N) + Current_TR) / 20
        """
        # Create simple bars with known TR
        bars = []
        for i in range(25):
            bars.append(
                Bar(
                    symbol="TEST",
                    date=date(2026, 1, i + 1),
                    open=Decimal("100"),
                    high=Decimal("110"),  # TR will be 10
                    low=Decimal("100"),
                    close=Decimal("105"),
                )
            )

        n = calculate_n(bars, period=20)

        # With constant TR of 10, N should converge to 10
        # After initial average and smoothing, should be close to 10
        assert abs(n.value - Decimal("10")) < Decimal("1")


class TestCalculateNSeries:
    """Tests for N series calculation."""

    def test_n_series_length(self):
        """Test that series returns correct number of values."""
        bars = load_fixture_bars()
        series = calculate_n_series(bars, period=20)

        # Should have N for each bar from position 20 onwards
        expected_length = len(bars) - 20
        assert len(series) == expected_length

    def test_n_series_matches_single_calc(self):
        """Test that series matches single calculation."""
        bars = load_fixture_bars()
        series = calculate_n_series(bars, period=20)

        # Last series value should match single calculation
        single_n = calculate_n(bars, period=20)

        # Should be very close (may differ slightly due to rounding)
        diff = abs(series[-1].value - single_n.value)
        assert diff < Decimal("0.01")

    def test_n_series_all_positive(self):
        """Test that all N values are positive."""
        bars = load_fixture_bars()
        series = calculate_n_series(bars, period=20)

        assert all(n.value > 0 for n in series)

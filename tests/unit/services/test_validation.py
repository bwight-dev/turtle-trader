"""Unit tests for data validation services."""

from datetime import date
from decimal import Decimal

import pytest

from src.domain.models.market import Bar
from src.domain.services.validation import (
    compare_bars,
    filter_valid_bars,
    validate_bar,
    validate_bars,
)


def make_valid_bar(
    o: str = "100",
    h: str = "105",
    l: str = "95",  # noqa: E741
    c: str = "102",
    dt: date = date(2026, 1, 1),
) -> Bar:
    """Helper to create valid test bars."""
    return Bar(
        symbol="TEST",
        date=dt,
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(l),
        close=Decimal(c),
    )


class TestValidateBar:
    """Tests for single bar validation.

    Note: Pydantic already validates OHLC relationships when creating Bar objects,
    so validate_bar is mainly for additional checks and data quality assurance.
    """

    def test_valid_bar(self):
        """Test that a valid bar passes."""
        bar = make_valid_bar()
        valid, reason = validate_bar(bar)
        assert valid is True
        assert reason == "OK"

    def test_bar_with_low_volume(self):
        """Test bar with zero volume is still valid."""
        bar = make_valid_bar()
        valid, reason = validate_bar(bar)
        assert valid is True

    def test_bar_with_high_equals_low(self):
        """Test bar where high equals low (doji)."""
        bar = Bar(
            symbol="TEST",
            date=date(2026, 1, 1),
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("100"),
            close=Decimal("100"),
        )
        valid, reason = validate_bar(bar)
        assert valid is True

    def test_multiple_valid_bars(self):
        """Test validation of multiple valid bars."""
        bars = [make_valid_bar(dt=date(2026, 1, i + 1)) for i in range(5)]
        for bar in bars:
            valid, _ = validate_bar(bar)
            assert valid is True


class TestValidateBars:
    """Tests for batch bar validation."""

    def test_all_valid(self):
        """Test batch with all valid bars."""
        bars = [make_valid_bar(dt=date(2026, 1, i + 1)) for i in range(5)]
        valid, errors = validate_bars(bars)
        assert valid is True
        assert len(errors) == 0

    def test_empty_list(self):
        """Test validation of empty list."""
        valid, errors = validate_bars([])
        assert valid is True
        assert len(errors) == 0


class TestCompareBars:
    """Tests for cross-source bar comparison."""

    def test_matching_bars(self):
        """Test bars with matching close prices."""
        bar1 = make_valid_bar(c="100.00")
        bar2 = make_valid_bar(c="100.50")  # 0.5% deviation
        consistent, reason = compare_bars(bar1, bar2, max_deviation_pct=Decimal("2.0"))
        assert consistent is True
        assert "within tolerance" in reason.lower()

    def test_divergent_bars(self):
        """Test bars with divergent close prices."""
        bar1 = make_valid_bar(c="100.00", h="110", l="90")
        bar2 = make_valid_bar(c="105.00", h="110", l="90")  # 5% deviation
        consistent, reason = compare_bars(bar1, bar2, max_deviation_pct=Decimal("2.0"))
        assert consistent is False
        assert "deviation" in reason.lower()

    def test_exact_match(self):
        """Test bars with exactly matching prices."""
        bar1 = make_valid_bar()
        bar2 = make_valid_bar()
        consistent, reason = compare_bars(bar1, bar2)
        assert consistent is True

    def test_date_mismatch(self):
        """Test bars with different dates."""
        bar1 = make_valid_bar(dt=date(2026, 1, 1))
        bar2 = make_valid_bar(dt=date(2026, 1, 2))
        consistent, reason = compare_bars(bar1, bar2)
        assert consistent is False
        assert "Dates" in reason

    def test_small_deviation_allowed(self):
        """Test that small deviations are allowed."""
        bar1 = make_valid_bar(o="1000", c="1000.00", h="1100", l="900")
        bar2 = make_valid_bar(o="1000", c="1015.00", h="1100", l="900")  # 1.5% deviation
        consistent, _ = compare_bars(bar1, bar2, max_deviation_pct=Decimal("2.0"))
        assert consistent is True


class TestFilterValidBars:
    """Tests for filtering bars.

    Since Pydantic prevents invalid bars from being created,
    filter_valid_bars will always return all input bars.
    """

    def test_filter_all_valid(self):
        """Test that valid bars are preserved."""
        bars = [make_valid_bar(dt=date(2026, 1, i + 1)) for i in range(5)]
        valid_bars = filter_valid_bars(bars)
        assert len(valid_bars) == 5

    def test_filter_empty_list(self):
        """Test filtering empty list."""
        valid_bars = filter_valid_bars([])
        assert len(valid_bars) == 0

    def test_filter_preserves_order(self):
        """Test that filtering preserves bar order."""
        bars = [make_valid_bar(dt=date(2026, 1, i + 1)) for i in range(5)]
        valid_bars = filter_valid_bars(bars)
        for i, bar in enumerate(valid_bars):
            assert bar.date == date(2026, 1, i + 1)

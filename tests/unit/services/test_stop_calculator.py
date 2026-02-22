"""Unit tests for stop price calculator."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.domain.models.enums import Direction
from src.domain.models.market import NValue
from src.domain.services.stop_calculator import (
    StopPrice,
    calculate_pyramid_stop,
    calculate_stop,
    calculate_trailing_stop,
    would_stop_be_hit,
)


def make_n_value(value: str) -> NValue:
    """Create test NValue."""
    return NValue(value=Decimal(value), calculated_at=datetime.now())


class TestCalculateStop:
    """Tests for calculate_stop function."""

    def test_stop_calculation_long(self):
        """Rule 10: Long stop = Entry - 2N."""
        stop = calculate_stop(
            entry_price=Decimal("2800"),
            n_value=make_n_value("20"),
            direction=Direction.LONG,
        )

        assert stop.price == Decimal("2760")  # 2800 - 40
        assert stop.distance == Decimal("40")
        assert stop.direction == Direction.LONG

    def test_stop_calculation_short(self):
        """Rule 10: Short stop = Entry + 2N."""
        stop = calculate_stop(
            entry_price=Decimal("2800"),
            n_value=make_n_value("20"),
            direction=Direction.SHORT,
        )

        assert stop.price == Decimal("2840")  # 2800 + 40
        assert stop.distance == Decimal("40")
        assert stop.direction == Direction.SHORT

    def test_stop_with_decimal_n(self):
        """Can use raw Decimal instead of NValue."""
        stop = calculate_stop(
            entry_price=Decimal("2800"),
            n_value=Decimal("20"),  # Raw Decimal
            direction=Direction.LONG,
        )

        assert stop.price == Decimal("2760")

    def test_stop_custom_multiplier(self):
        """Can use custom stop multiplier."""
        # 3N stop instead of 2N
        stop = calculate_stop(
            entry_price=Decimal("2800"),
            n_value=make_n_value("20"),
            direction=Direction.LONG,
            stop_multiplier=Decimal("3"),
        )

        assert stop.price == Decimal("2740")  # 2800 - 60
        assert stop.distance == Decimal("60")

    def test_stop_distance_in_n(self):
        """StopPrice.distance_in_n property."""
        stop = calculate_stop(
            entry_price=Decimal("2800"),
            n_value=make_n_value("20"),
            direction=Direction.LONG,
        )

        assert stop.distance_in_n == Decimal("2")  # 40 / 20


class TestCalculatePyramidStop:
    """Tests for calculate_pyramid_stop function."""

    def test_pyramid_stop_long(self):
        """Rule 12: All stops move to 2N below newest entry."""
        stop = calculate_pyramid_stop(
            newest_entry_price=Decimal("2820"),  # Pyramided at 2820
            n_value=make_n_value("20"),
            direction=Direction.LONG,
        )

        assert stop.price == Decimal("2780")  # 2820 - 40

    def test_pyramid_stop_short(self):
        """Rule 12: Short stops move above newest entry."""
        stop = calculate_pyramid_stop(
            newest_entry_price=Decimal("2780"),  # Pyramided at 2780
            n_value=make_n_value("20"),
            direction=Direction.SHORT,
        )

        assert stop.price == Decimal("2820")  # 2780 + 40


class TestWouldStopBeHit:
    """Tests for would_stop_be_hit function."""

    def test_long_stop_hit(self):
        """Long stop hit when price <= stop."""
        # Stop at 2760, price at 2750
        assert would_stop_be_hit(
            current_price=Decimal("2750"),
            stop_price=Decimal("2760"),
            direction=Direction.LONG,
        ) is True

    def test_long_stop_exact(self):
        """Long stop hit at exact price."""
        assert would_stop_be_hit(
            current_price=Decimal("2760"),
            stop_price=Decimal("2760"),
            direction=Direction.LONG,
        ) is True

    def test_long_stop_not_hit(self):
        """Long stop not hit when price > stop."""
        assert would_stop_be_hit(
            current_price=Decimal("2770"),
            stop_price=Decimal("2760"),
            direction=Direction.LONG,
        ) is False

    def test_short_stop_hit(self):
        """Short stop hit when price >= stop."""
        # Stop at 2840, price at 2850
        assert would_stop_be_hit(
            current_price=Decimal("2850"),
            stop_price=Decimal("2840"),
            direction=Direction.SHORT,
        ) is True

    def test_short_stop_exact(self):
        """Short stop hit at exact price."""
        assert would_stop_be_hit(
            current_price=Decimal("2840"),
            stop_price=Decimal("2840"),
            direction=Direction.SHORT,
        ) is True

    def test_short_stop_not_hit(self):
        """Short stop not hit when price < stop."""
        assert would_stop_be_hit(
            current_price=Decimal("2830"),
            stop_price=Decimal("2840"),
            direction=Direction.SHORT,
        ) is False


class TestCalculateTrailingStop:
    """Tests for calculate_trailing_stop function."""

    def test_trailing_stop_long(self):
        """Trailing stop follows highest price for longs."""
        stop = calculate_trailing_stop(
            highest_favorable=Decimal("2900"),  # Peaked at 2900
            n_value=Decimal("20"),
            direction=Direction.LONG,
        )

        assert stop == Decimal("2860")  # 2900 - 40

    def test_trailing_stop_short(self):
        """Trailing stop follows lowest price for shorts."""
        stop = calculate_trailing_stop(
            highest_favorable=Decimal("2700"),  # Bottomed at 2700
            n_value=Decimal("20"),
            direction=Direction.SHORT,
        )

        assert stop == Decimal("2740")  # 2700 + 40


class TestStopScenarios:
    """Tests for realistic stop scenarios."""

    def test_pyramid_tightens_stop(self):
        """Pyramiding tightens the stop for all units."""
        # Initial entry at 2800, stop at 2760
        initial_stop = calculate_stop(
            entry_price=Decimal("2800"),
            n_value=Decimal("20"),
            direction=Direction.LONG,
        )
        assert initial_stop.price == Decimal("2760")

        # Pyramid at 2820, new stop for ALL units at 2780
        pyramid_stop = calculate_pyramid_stop(
            newest_entry_price=Decimal("2820"),
            n_value=Decimal("20"),
            direction=Direction.LONG,
        )
        assert pyramid_stop.price == Decimal("2780")

        # Stop moved up by 20 (half N)
        assert pyramid_stop.price > initial_stop.price

    def test_stop_protects_profit(self):
        """After pyramiding, stop protects some profit on early units."""
        # Entry at 2800, first pyramid at 2810 (half N)
        # After pyramid, stop at 2810 - 40 = 2770
        # First unit is now protected: entered at 2800, stop at 2770
        # Risk reduced from 40 to 30 points

        stop = calculate_pyramid_stop(
            newest_entry_price=Decimal("2810"),
            n_value=Decimal("20"),
            direction=Direction.LONG,
        )

        initial_entry = Decimal("2800")
        risk_on_first_unit = initial_entry - stop.price

        assert risk_on_first_unit == Decimal("30")  # Not 40 anymore

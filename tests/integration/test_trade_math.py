"""Integration tests for trade math accuracy.

These tests verify that all trading calculations are accurate and correct
per the original Turtle Trading rules:

- Rule 4: Unit sizing = (Risk × Equity) / (N × PointValue)
- Rule 5: Drawdown reductions (10% DD → 20% reduction, cascading)
- Rule 10: Stop price = Entry ± 2N
- Rule 11: Pyramid at ½N intervals
- Rule 12: Move all stops to 2N below newest entry

All calculations are verified with specific numerical examples.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from src.domain.models.enums import Direction, System
from src.domain.models.equity import EquityState
from src.domain.models.market import NValue
from src.domain.models.position import Position, PyramidLevel
from src.domain.services.drawdown_tracker import DrawdownTracker, calculate_notional_equity
from src.domain.services.sizing import (
    UnitSize,
    calculate_contracts_for_risk,
    calculate_unit_size,
    scale_position_size,
)
from src.domain.services.stop_calculator import (
    calculate_pyramid_stop,
    calculate_stop,
    calculate_trailing_stop,
    would_stop_be_hit,
)


class TestUnitSizingMath:
    """Tests for Rule 4: Unit size calculation accuracy."""

    def test_standard_unit_size_calculation(self):
        """Verify standard unit size calculation.

        Example from rules:
        - Equity: $100,000
        - Risk: 0.5% ($500)
        - N (ATR): $20
        - Point Value: $10
        - Dollar Volatility: $20 × $10 = $200
        - Unit Size: $500 / $200 = 2.5 → 2 contracts (truncate)
        """
        size = calculate_unit_size(
            equity=Decimal("100000"),
            n_value=Decimal("20"),
            point_value=Decimal("10"),
            risk_pct=Decimal("0.005"),
        )

        assert size.risk_amount == Decimal("500")  # 100000 × 0.005
        assert size.dollar_volatility == Decimal("200")  # 20 × 10
        assert size.raw_size == Decimal("2.5")  # 500 / 200
        assert size.contracts == 2  # Truncated

    def test_small_account_truncation(self):
        """Verify small accounts truncate to 0 when unit < 1.

        This is critical - per Curtis Faith, never round up.
        - Equity: $10,000
        - Risk: 0.5% ($50)
        - Dollar Volatility: $200
        - Unit Size: $50 / $200 = 0.25 → 0 contracts
        """
        size = calculate_unit_size(
            equity=Decimal("10000"),
            n_value=Decimal("20"),
            point_value=Decimal("10"),
            risk_pct=Decimal("0.005"),
        )

        assert size.raw_size == Decimal("0.25")
        assert size.contracts == 0  # Must be 0, not 1
        assert size.is_valid is False

    def test_large_account_sizing(self):
        """Verify large account sizing.

        - Equity: $1,000,000
        - Risk: 0.5% ($5,000)
        - N: $50
        - Point Value: $25
        - Dollar Volatility: $50 × $25 = $1,250
        - Unit Size: $5,000 / $1,250 = 4 contracts
        """
        size = calculate_unit_size(
            equity=Decimal("1000000"),
            n_value=Decimal("50"),
            point_value=Decimal("25"),
            risk_pct=Decimal("0.005"),
        )

        assert size.risk_amount == Decimal("5000")
        assert size.dollar_volatility == Decimal("1250")
        assert size.contracts == 4

    def test_nvalue_object_handling(self):
        """Verify NValue object is handled correctly."""
        n_value = NValue(
            value=Decimal("20"),
            calculated_at=datetime.now(),
            symbol="/MGC",
        )

        size = calculate_unit_size(
            equity=Decimal("100000"),
            n_value=n_value,  # Pass object, not raw Decimal
            point_value=Decimal("10"),
        )

        assert size.contracts == 2

    def test_zero_volatility_protection(self):
        """Verify zero volatility returns 0 contracts."""
        size = calculate_unit_size(
            equity=Decimal("100000"),
            n_value=Decimal("0"),
            point_value=Decimal("10"),
        )

        assert size.contracts == 0
        assert size.dollar_volatility == Decimal("0")

    def test_calculate_contracts_for_risk(self):
        """Test direct risk budget to contracts calculation."""
        contracts = calculate_contracts_for_risk(
            risk_budget=Decimal("1000"),
            n_value=Decimal("20"),
            point_value=Decimal("10"),
        )

        # $1000 / ($20 × $10) = 5 contracts
        assert contracts == 5

    def test_scale_position_size(self):
        """Test position scaling for drawdown."""
        size = UnitSize(
            contracts=4,
            risk_amount=Decimal("500"),
            dollar_volatility=Decimal("125"),
            raw_size=Decimal("4.0"),
        )

        # 20% reduction
        scaled = scale_position_size(size, Decimal("0.8"))
        assert scaled == 3  # 4 × 0.8 = 3.2 → 3


class TestStopCalculationMath:
    """Tests for Rule 10/12: Stop price calculation accuracy."""

    def test_long_stop_calculation(self):
        """Verify long stop = Entry - 2N.

        - Entry: $100
        - N: $5
        - Stop: $100 - (2 × $5) = $90
        """
        stop = calculate_stop(
            entry_price=Decimal("100"),
            n_value=Decimal("5"),
            direction=Direction.LONG,
        )

        assert stop.price == Decimal("90")
        assert stop.distance == Decimal("10")  # 2N
        assert stop.distance_in_n == Decimal("2")

    def test_short_stop_calculation(self):
        """Verify short stop = Entry + 2N.

        - Entry: $100
        - N: $5
        - Stop: $100 + (2 × $5) = $110
        """
        stop = calculate_stop(
            entry_price=Decimal("100"),
            n_value=Decimal("5"),
            direction=Direction.SHORT,
        )

        assert stop.price == Decimal("110")
        assert stop.distance == Decimal("10")

    def test_pyramid_stop_calculation(self):
        """Verify Rule 12: Pyramid stop moves all stops.

        - Original entry: $100, stop at $90
        - Pyramid entry: $105, N=$5
        - New stop for ALL: $105 - (2 × $5) = $95
        """
        stop = calculate_pyramid_stop(
            newest_entry_price=Decimal("105"),
            n_value=Decimal("5"),
            direction=Direction.LONG,
        )

        assert stop.price == Decimal("95")

    def test_stop_hit_detection_long(self):
        """Verify stop hit detection for longs."""
        stop_price = Decimal("90")

        # At stop
        assert would_stop_be_hit(Decimal("90"), stop_price, Direction.LONG) is True
        # Below stop
        assert would_stop_be_hit(Decimal("85"), stop_price, Direction.LONG) is True
        # Above stop
        assert would_stop_be_hit(Decimal("95"), stop_price, Direction.LONG) is False

    def test_stop_hit_detection_short(self):
        """Verify stop hit detection for shorts."""
        stop_price = Decimal("110")

        # At stop
        assert would_stop_be_hit(Decimal("110"), stop_price, Direction.SHORT) is True
        # Above stop
        assert would_stop_be_hit(Decimal("115"), stop_price, Direction.SHORT) is True
        # Below stop
        assert would_stop_be_hit(Decimal("105"), stop_price, Direction.SHORT) is False

    def test_trailing_stop_long(self):
        """Test trailing stop calculation for longs."""
        trailing = calculate_trailing_stop(
            highest_favorable=Decimal("120"),  # Highest price reached
            n_value=Decimal("5"),
            direction=Direction.LONG,
        )

        # 120 - (2 × 5) = 110
        assert trailing == Decimal("110")

    def test_trailing_stop_short(self):
        """Test trailing stop calculation for shorts."""
        trailing = calculate_trailing_stop(
            highest_favorable=Decimal("80"),  # Lowest price reached
            n_value=Decimal("5"),
            direction=Direction.SHORT,
        )

        # 80 + (2 × 5) = 90
        assert trailing == Decimal("90")


class TestDrawdownMath:
    """Tests for Rule 5: Drawdown reduction accuracy."""

    def test_10_percent_drawdown_reduction(self):
        """Verify 10% drawdown → 20% notional reduction.

        - Starting equity: $100,000
        - 10% drawdown → equity: $90,000
        - Notional: $100,000 × 0.80 = $80,000
        """
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("100000"))
        tracker.update_equity(Decimal("90000"))

        assert tracker.notional_equity == Decimal("80000")
        assert tracker.reduction_level == 1

    def test_20_percent_drawdown_cascading(self):
        """Verify 20% drawdown cascades (0.80 × 0.80 = 0.64).

        - Starting: $100,000
        - 20% drawdown → equity: $80,000
        - Notional: $100,000 × 0.64 = $64,000
        """
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("100000"))
        tracker.update_equity(Decimal("80000"))

        assert tracker.notional_equity == Decimal("64000")
        assert tracker.reduction_level == 2

    def test_30_percent_drawdown_triple_cascade(self):
        """Verify 30% drawdown triple cascades (0.80^3 = 0.512).

        - Starting: $100,000
        - 30% drawdown → equity: $70,000
        - Notional: $100,000 × 0.512 = $51,200
        """
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("100000"))
        tracker.update_equity(Decimal("70000"))

        assert tracker.notional_equity == Decimal("51200")
        assert tracker.reduction_level == 3

    def test_recovery_restores_full_sizing(self):
        """Verify recovery to yearly start restores full sizing."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("100000"))

        # Go into drawdown
        tracker.update_equity(Decimal("90000"))
        assert tracker.reduction_level == 1
        assert tracker.notional_equity == Decimal("80000")

        # Recover to yearly start
        tracker.update_equity(Decimal("100000"))
        assert tracker.reduction_level == 0
        assert tracker.notional_equity == Decimal("100000")

    def test_floor_prevents_death_spiral(self):
        """Verify floor prevents notional from going too low.

        With 60% floor:
        - Starting: $100,000
        - 50% drawdown → equity: $50,000
        - Calculated notional: $100,000 × 0.80^5 = $32,768
        - Floor: $100,000 × 0.60 = $60,000
        - Actual notional: $60,000 (floor applied)
        """
        tracker = DrawdownTracker(
            yearly_starting_equity=Decimal("100000"),
            min_notional_floor=Decimal("0.60"),
        )
        tracker.update_equity(Decimal("50000"))

        # Should be floored at 60%
        assert tracker.notional_equity >= Decimal("60000")

    def test_pure_function_notional_calculation(self):
        """Test pure function for notional equity."""
        notional = calculate_notional_equity(
            actual_equity=Decimal("90000"),
            yearly_starting_equity=Decimal("100000"),
        )

        # 10% drawdown → 80% of yearly start
        assert notional == Decimal("80000")

    def test_drawdown_pct_calculation(self):
        """Verify drawdown percentage calculation."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("100000"))
        tracker.update_equity(Decimal("85000"))

        # 15% drawdown
        assert tracker.drawdown_pct == Decimal("0.15")

    def test_year_reset(self):
        """Verify yearly reset clears reductions."""
        tracker = DrawdownTracker(yearly_starting_equity=Decimal("100000"))
        tracker.update_equity(Decimal("80000"))

        # In drawdown
        assert tracker.reduction_level > 0

        # Reset for new year at current equity
        tracker.reset_year(Decimal("80000"))

        # Fresh start
        assert tracker.yearly_starting_equity == Decimal("80000")
        assert tracker.reduction_level == 0
        assert tracker.notional_equity == Decimal("80000")


class TestPyramidMath:
    """Tests for Rule 11/12: Pyramid trigger and stop math."""

    def test_pyramid_trigger_long(self):
        """Verify pyramid trigger at +½N for longs.

        - Entry: $100
        - N: $4
        - ½N: $2
        - Trigger: $102
        """
        n_value = NValue(value=Decimal("4"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=2,
            n_at_entry=Decimal("4"),
        )
        pos = Position(
            symbol="TEST",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(level,),
            current_stop=Decimal("92"),  # 100 - 2×4
            initial_entry_price=Decimal("100"),
            initial_n=n_value,
        )

        assert pos.next_pyramid_trigger == Decimal("102")  # 100 + 2

    def test_pyramid_trigger_short(self):
        """Verify pyramid trigger at -½N for shorts.

        - Entry: $100
        - N: $4
        - ½N: $2
        - Trigger: $98
        """
        n_value = NValue(value=Decimal("4"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=2,
            n_at_entry=Decimal("4"),
        )
        pos = Position(
            symbol="TEST",
            direction=Direction.SHORT,
            system=System.S1,
            pyramid_levels=(level,),
            current_stop=Decimal("108"),  # 100 + 2×4
            initial_entry_price=Decimal("100"),
            initial_n=n_value,
        )

        assert pos.next_pyramid_trigger == Decimal("98")  # 100 - 2

    def test_pyramid_stop_adjustment(self):
        """Verify Rule 12: All stops move to 2N below newest entry.

        - Original entry: $100, stop at $92
        - Pyramid at: $102, N=$4
        - New stop for ALL: $102 - 8 = $94
        """
        n_value = NValue(value=Decimal("4"), calculated_at=datetime.now())
        level1 = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=2,
            n_at_entry=Decimal("4"),
        )
        pos = Position(
            symbol="TEST",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(level1,),
            current_stop=Decimal("92"),
            initial_entry_price=Decimal("100"),
            initial_n=n_value,
        )

        # Add pyramid at $102
        new_pos = pos.add_pyramid(
            entry_price=Decimal("102"),
            contracts=2,
            n_at_entry=Decimal("4"),
            new_stop=Decimal("94"),  # 102 - 8
        )

        assert new_pos.total_units == 2
        assert new_pos.current_stop == Decimal("94")

    def test_full_pyramid_sequence(self):
        """Test complete 4-unit pyramid sequence with correct math."""
        n_value = NValue(value=Decimal("4"), calculated_at=datetime.now())
        level1 = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=2,
            n_at_entry=Decimal("4"),
        )
        pos = Position(
            symbol="TEST",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(level1,),
            current_stop=Decimal("92"),  # 100 - 8
            initial_entry_price=Decimal("100"),
            initial_n=n_value,
        )

        # Expected sequence:
        # Entry 1: $100, trigger at $102, stop at $92
        # Entry 2: $102, trigger at $104, stop at $94
        # Entry 3: $104, trigger at $106, stop at $96
        # Entry 4: $106, trigger N/A, stop at $98

        entries = [
            (Decimal("102"), Decimal("94")),
            (Decimal("104"), Decimal("96")),
            (Decimal("106"), Decimal("98")),
        ]

        for entry_price, new_stop in entries:
            pos = pos.add_pyramid(
                entry_price=entry_price,
                contracts=2,
                n_at_entry=Decimal("4"),
                new_stop=new_stop,
            )

        assert pos.total_units == 4
        assert pos.total_contracts == 8
        assert pos.current_stop == Decimal("98")
        assert pos.can_pyramid is False  # Max 4 units


class TestPnLCalculations:
    """Tests for P&L calculation accuracy."""

    def test_long_profit_calculation(self):
        """Verify long P&L calculation.

        - Entry: $100
        - Current: $110
        - Contracts: 10
        - Point Value: $5
        - P&L: ($110 - $100) × 10 × $5 = $500
        """
        n_value = NValue(value=Decimal("2"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=10,
            n_at_entry=Decimal("2"),
        )
        pos = Position(
            symbol="TEST",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(level,),
            current_stop=Decimal("96"),
            initial_entry_price=Decimal("100"),
            initial_n=n_value,
        )

        pnl = pos.unrealized_pnl(Decimal("110"), Decimal("5"))
        assert pnl == Decimal("500")

    def test_long_loss_calculation(self):
        """Verify long loss calculation.

        - Entry: $100
        - Current: $95
        - Contracts: 10
        - Point Value: $5
        - P&L: ($95 - $100) × 10 × $5 = -$250
        """
        n_value = NValue(value=Decimal("2"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=10,
            n_at_entry=Decimal("2"),
        )
        pos = Position(
            symbol="TEST",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=(level,),
            current_stop=Decimal("96"),
            initial_entry_price=Decimal("100"),
            initial_n=n_value,
        )

        pnl = pos.unrealized_pnl(Decimal("95"), Decimal("5"))
        assert pnl == Decimal("-250")

    def test_short_profit_calculation(self):
        """Verify short profit calculation.

        - Entry: $100
        - Current: $90 (price down = short profit)
        - Contracts: 10
        - Point Value: $5
        - P&L: ($100 - $90) × 10 × $5 = $500
        """
        n_value = NValue(value=Decimal("2"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=10,
            n_at_entry=Decimal("2"),
        )
        pos = Position(
            symbol="TEST",
            direction=Direction.SHORT,
            system=System.S1,
            pyramid_levels=(level,),
            current_stop=Decimal("104"),
            initial_entry_price=Decimal("100"),
            initial_n=n_value,
        )

        pnl = pos.unrealized_pnl(Decimal("90"), Decimal("5"))
        assert pnl == Decimal("500")

    def test_short_loss_calculation(self):
        """Verify short loss calculation.

        - Entry: $100
        - Current: $105 (price up = short loss)
        - Contracts: 10
        - Point Value: $5
        - P&L: ($100 - $105) × 10 × $5 = -$250
        """
        n_value = NValue(value=Decimal("2"), calculated_at=datetime.now())
        level = PyramidLevel(
            level=1,
            entry_price=Decimal("100"),
            contracts=10,
            n_at_entry=Decimal("2"),
        )
        pos = Position(
            symbol="TEST",
            direction=Direction.SHORT,
            system=System.S1,
            pyramid_levels=(level,),
            current_stop=Decimal("104"),
            initial_entry_price=Decimal("100"),
            initial_n=n_value,
        )

        pnl = pos.unrealized_pnl(Decimal("105"), Decimal("5"))
        assert pnl == Decimal("-250")

    def test_pyramided_position_average_entry(self):
        """Verify volume-weighted average entry for pyramids.

        - Level 1: 2 contracts @ $100
        - Level 2: 2 contracts @ $102
        - Level 3: 2 contracts @ $104
        - Total: 6 contracts
        - Average: (2×100 + 2×102 + 2×104) / 6 = $102
        """
        n_value = NValue(value=Decimal("4"), calculated_at=datetime.now())
        levels = (
            PyramidLevel(level=1, entry_price=Decimal("100"), contracts=2, n_at_entry=Decimal("4")),
            PyramidLevel(level=2, entry_price=Decimal("102"), contracts=2, n_at_entry=Decimal("4")),
            PyramidLevel(level=3, entry_price=Decimal("104"), contracts=2, n_at_entry=Decimal("4")),
        )
        pos = Position(
            symbol="TEST",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=levels,
            current_stop=Decimal("96"),
            initial_entry_price=Decimal("100"),
            initial_n=n_value,
        )

        assert pos.total_contracts == 6
        assert pos.average_entry_price == Decimal("102")


class TestIntegratedTradingScenario:
    """End-to-end test of a complete trading scenario."""

    def test_complete_trade_lifecycle(self):
        """Test a complete trade from entry through pyramid to exit.

        Scenario:
        - $100,000 account
        - Enter long at $100, N=$4
        - Pyramid at $102, $104, $106
        - Exit at stop ($98)

        Expected:
        - 4 units with 2 contracts each = 8 total contracts
        - Average entry: ($100 + $102 + $104 + $106) / 4 = $103
        - Exit at $98, loss: ($98 - $103) × 8 × $1 = -$40
        """
        # Calculate unit size
        size = calculate_unit_size(
            equity=Decimal("100000"),
            n_value=Decimal("4"),
            point_value=Decimal("100"),  # $100 per point
            risk_pct=Decimal("0.005"),
        )

        # Risk: $500, Dollar Vol: $400, Size: 1.25 → 1 contract per unit
        assert size.contracts == 1

        # Build position with pyramids
        n_value = NValue(value=Decimal("4"), calculated_at=datetime.now())
        levels = tuple(
            PyramidLevel(
                level=i + 1,
                entry_price=Decimal("100") + Decimal(i * 2),
                contracts=1,
                n_at_entry=Decimal("4"),
            )
            for i in range(4)
        )
        pos = Position(
            symbol="TEST",
            direction=Direction.LONG,
            system=System.S1,
            pyramid_levels=levels,
            current_stop=Decimal("98"),  # 106 - 8
            initial_entry_price=Decimal("100"),
            initial_n=n_value,
        )

        # Verify position state
        assert pos.total_units == 4
        assert pos.total_contracts == 4
        assert pos.average_entry_price == Decimal("103")  # (100+102+104+106)/4
        assert pos.current_stop == Decimal("98")

        # Verify stop is hit at $98
        assert pos.is_stop_hit(Decimal("98")) is True
        assert pos.is_stop_hit(Decimal("99")) is False

        # Calculate P&L at exit
        pnl = pos.unrealized_pnl(Decimal("98"), Decimal("100"))
        # (98 - 103) × 4 × 100 = -$2000
        assert pnl == Decimal("-2000")

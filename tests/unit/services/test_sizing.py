"""Unit tests for position sizing service."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.domain.models.market import NValue
from src.domain.services.sizing import (
    UnitSize,
    calculate_contracts_for_risk,
    calculate_unit_size,
    scale_position_size,
)


def make_n_value(value: str) -> NValue:
    """Create test NValue."""
    return NValue(value=Decimal(value), calculated_at=datetime.now())


class TestCalculateUnitSize:
    """Tests for calculate_unit_size function."""

    def test_unit_size_basic(self):
        """Rule 4: Basic unit size calculation."""
        # $100k equity, N=20, $10/point, 0.5% risk
        # Risk budget = $100,000 × 0.005 = $500
        # Dollar volatility = 20 × $10 = $200
        # Unit size = $500 / $200 = 2.5 → 2 contracts
        size = calculate_unit_size(
            equity=Decimal("100000"),
            n_value=make_n_value("20"),
            point_value=Decimal("10"),
            risk_pct=Decimal("0.005"),
        )

        assert size.contracts == 2
        assert size.risk_amount == Decimal("500")
        assert size.dollar_volatility == Decimal("200")
        assert size.raw_size == Decimal("2.5")

    def test_unit_size_rounds_down(self):
        """Unit size always rounds down (conservative)."""
        # Setup for 2.9 raw size
        size = calculate_unit_size(
            equity=Decimal("116000"),  # 116k × 0.005 = 580
            n_value=make_n_value("20"),  # 20 × 10 = 200
            point_value=Decimal("10"),  # 580 / 200 = 2.9
        )

        assert size.contracts == 2  # Not 3
        assert size.raw_size == Decimal("2.9")

    def test_unit_size_with_decimal_n(self):
        """Can use raw Decimal instead of NValue."""
        size = calculate_unit_size(
            equity=Decimal("100000"),
            n_value=Decimal("20"),  # Raw Decimal
            point_value=Decimal("10"),
        )

        assert size.contracts == 2

    def test_unit_size_zero_volatility(self):
        """Handle zero volatility gracefully."""
        size = calculate_unit_size(
            equity=Decimal("100000"),
            n_value=Decimal("0"),  # Raw Decimal to test edge case
            point_value=Decimal("10"),
        )

        assert size.contracts == 0
        assert not size.is_valid

    def test_unit_size_small_account(self):
        """Small account may not afford minimum."""
        # $10k equity, N=50, $10/point
        # Risk = 10k × 0.005 = $50
        # Vol = 50 × 10 = $500
        # Size = 50 / 500 = 0.1 → 0 contracts
        size = calculate_unit_size(
            equity=Decimal("10000"),
            n_value=make_n_value("50"),
            point_value=Decimal("10"),
        )

        assert size.contracts == 0
        assert not size.is_valid

    def test_unit_size_large_account(self):
        """Large account can afford more contracts."""
        # $1M equity, N=20, $10/point
        # Risk = 1M × 0.005 = $5000
        # Vol = 20 × 10 = $200
        # Size = 5000 / 200 = 25 contracts
        size = calculate_unit_size(
            equity=Decimal("1000000"),
            n_value=make_n_value("20"),
            point_value=Decimal("10"),
        )

        assert size.contracts == 25

    def test_unit_size_high_point_value(self):
        """High point value reduces position size."""
        # $100k, N=20, $100/point (like ES)
        # Risk = $500, Vol = $2000
        # Size = 500 / 2000 = 0.25 → 0 contracts
        size = calculate_unit_size(
            equity=Decimal("100000"),
            n_value=make_n_value("20"),
            point_value=Decimal("100"),
        )

        assert size.contracts == 0

    def test_unit_size_is_valid(self):
        """UnitSize.is_valid property works."""
        valid = UnitSize(
            contracts=2,
            risk_amount=Decimal("500"),
            dollar_volatility=Decimal("200"),
            raw_size=Decimal("2.5"),
        )
        assert valid.is_valid is True

        invalid = UnitSize(
            contracts=0,
            risk_amount=Decimal("50"),
            dollar_volatility=Decimal("500"),
            raw_size=Decimal("0.1"),
        )
        assert invalid.is_valid is False


class TestCalculateContractsForRisk:
    """Tests for calculate_contracts_for_risk function."""

    def test_contracts_for_specific_risk(self):
        """Calculate contracts for specific risk budget."""
        contracts = calculate_contracts_for_risk(
            risk_budget=Decimal("500"),
            n_value=Decimal("20"),
            point_value=Decimal("10"),
        )

        assert contracts == 2

    def test_contracts_zero_volatility(self):
        """Handle zero volatility."""
        contracts = calculate_contracts_for_risk(
            risk_budget=Decimal("500"),
            n_value=Decimal("0"),
            point_value=Decimal("10"),
        )

        assert contracts == 0


class TestScalePositionSize:
    """Tests for scale_position_size function."""

    def test_scale_down(self):
        """Scale position down by factor."""
        size = UnitSize(
            contracts=10,
            risk_amount=Decimal("5000"),
            dollar_volatility=Decimal("500"),
            raw_size=Decimal("10"),
        )

        scaled = scale_position_size(size, Decimal("0.8"))

        assert scaled == 8

    def test_scale_rounds_down(self):
        """Scaling rounds down."""
        size = UnitSize(
            contracts=10,
            risk_amount=Decimal("5000"),
            dollar_volatility=Decimal("500"),
            raw_size=Decimal("10"),
        )

        scaled = scale_position_size(size, Decimal("0.75"))

        assert scaled == 7  # 10 × 0.75 = 7.5 → 7


class TestDrawdownSizingIntegration:
    """Tests for sizing during drawdown."""

    def test_sizing_uses_notional_not_actual(self):
        """Sizing must use notional equity during drawdown."""
        # During drawdown: actual=$89k, notional=$80k (per Rule 5)
        # Should size based on $80k notional
        size = calculate_unit_size(
            equity=Decimal("80000"),  # Use notional!
            n_value=make_n_value("20"),
            point_value=Decimal("10"),
        )

        # $80k × 0.005 / 200 = 2 contracts
        assert size.contracts == 2

        # If using actual $89k, would be 2.225 → still 2, but different risk
        size_wrong = calculate_unit_size(
            equity=Decimal("89000"),  # Wrong - using actual
            n_value=make_n_value("20"),
            point_value=Decimal("10"),
        )

        # Both round to 2, but risk amounts differ
        assert size_wrong.risk_amount == Decimal("445")
        assert size.risk_amount == Decimal("400")

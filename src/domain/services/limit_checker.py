"""Position limit checker for Turtle Trading system.

Supports TWO modes for position limits:

1. ORIGINAL MODE (unit count limits):
   - Max 4 units per market
   - Max 6 units in correlated markets
   - Max 12 units total portfolio
   - Designed for ~20 market universe (original 1983 Turtles)

2. MODERN MODE (total risk cap - Rule 17):
   - Max 4 units per market (unchanged)
   - Max 6 units in correlated markets (unchanged)
   - Max 20% total portfolio risk (instead of 12 units)
   - Designed for 228+ market universe (Jerry Parker approach)
   - Per Parker: "Each position must be inconsequential"

Use `use_risk_cap_mode=True` for 228+ markets (default).
Use `use_risk_cap_mode=False` for historical validation with ~20 markets.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from src.domain.models.enums import CorrelationGroup
from src.domain.models.portfolio import Portfolio
from src.domain.rules import (
    MAX_TOTAL_RISK,
    MAX_UNITS_CORRELATED,
    MAX_UNITS_PER_MARKET,
    MAX_UNITS_TOTAL,
    RISK_PER_TRADE,
    USE_RISK_CAP_MODE,
)


class LimitViolation(str, Enum):
    """Type of limit violation."""

    NONE = "none"
    PER_MARKET = "per_market"  # Would exceed 4 units in single market
    CORRELATED = "correlated"  # Would exceed 6 units in correlated group
    TOTAL = "total"  # Would exceed 12 units total (original mode)
    RISK_CAP = "risk_cap"  # Would exceed 20% total risk (modern mode)


@dataclass(frozen=True)
class LimitCheckResult:
    """Result of a position limit check."""

    allowed: bool
    violation: LimitViolation
    reason: str
    symbol: str
    units_requested: int
    current_market_units: int
    current_group_units: int
    current_total_units: int
    max_per_market: int
    max_correlated: int
    max_total: int
    # Risk cap fields (modern mode)
    current_total_risk: Decimal = Decimal("0")
    max_total_risk: Decimal = Decimal("0.20")
    risk_per_unit: Decimal = Decimal("0.005")
    use_risk_cap_mode: bool = True

    @property
    def would_exceed_market(self) -> bool:
        """Check if this would exceed per-market limit."""
        return self.violation == LimitViolation.PER_MARKET

    @property
    def would_exceed_correlated(self) -> bool:
        """Check if this would exceed correlated group limit."""
        return self.violation == LimitViolation.CORRELATED

    @property
    def would_exceed_total(self) -> bool:
        """Check if this would exceed total portfolio limit (original mode)."""
        return self.violation == LimitViolation.TOTAL

    @property
    def would_exceed_risk_cap(self) -> bool:
        """Check if this would exceed total risk cap (modern mode)."""
        return self.violation == LimitViolation.RISK_CAP

    @property
    def units_available_in_market(self) -> int:
        """How many more units can be added in this market."""
        return max(0, self.max_per_market - self.current_market_units)

    @property
    def units_available_in_group(self) -> int:
        """How many more units can be added in this correlation group."""
        return max(0, self.max_correlated - self.current_group_units)

    @property
    def units_available_total(self) -> int:
        """How many more units can be added to portfolio.

        In risk cap mode, this is based on remaining risk budget.
        In original mode, this is based on unit count.
        """
        if self.use_risk_cap_mode:
            remaining_risk = self.max_total_risk - self.current_total_risk
            if self.risk_per_unit > 0:
                return max(0, int(remaining_risk / self.risk_per_unit))
            return 0
        return max(0, self.max_total - self.current_total_units)


class LimitChecker:
    """Domain service for checking position limits.

    Supports TWO modes:

    ORIGINAL MODE (use_risk_cap_mode=False):
    - Max 4 units per individual market
    - Max 6 units across correlated markets (e.g., all metals)
    - Max 12 units in the entire portfolio
    - Best for: Historical validation with ~20 markets

    MODERN MODE (use_risk_cap_mode=True, default):
    - Max 4 units per individual market (unchanged)
    - Max 6 units across correlated markets (unchanged)
    - Max 20% total portfolio risk (instead of 12 units)
    - Best for: 228+ market universe (Jerry Parker approach)

    Per Jerry Parker: When trading 300+ markets, each position must be
    "inconsequential" - meaning if any single position has a big drawdown,
    it doesn't devastate your portfolio.
    """

    def __init__(
        self,
        max_per_market: int = MAX_UNITS_PER_MARKET,
        max_correlated: int = MAX_UNITS_CORRELATED,
        max_total: int = MAX_UNITS_TOTAL,
        max_total_risk: Decimal = MAX_TOTAL_RISK,
        risk_per_unit: Decimal = RISK_PER_TRADE,
        use_risk_cap_mode: bool = USE_RISK_CAP_MODE,
    ):
        """Initialize limit checker with configured limits.

        Args:
            max_per_market: Max units per market (default 4)
            max_correlated: Max units in correlated markets (default 6)
            max_total: Max total portfolio units - original mode (default 12)
            max_total_risk: Max total risk as % of equity - modern mode (default 0.20)
            risk_per_unit: Risk per unit as decimal - modern mode (default 0.005)
            use_risk_cap_mode: If True, use risk cap; if False, use unit count (default True)
        """
        self.max_per_market = max_per_market
        self.max_correlated = max_correlated
        self.max_total = max_total
        self.max_total_risk = max_total_risk
        self.risk_per_unit = risk_per_unit
        self.use_risk_cap_mode = use_risk_cap_mode

    def can_add_position(
        self,
        portfolio: Portfolio,
        symbol: str,
        units_to_add: int,
        correlation_group: CorrelationGroup | None = None,
    ) -> LimitCheckResult:
        """Check if units can be added while respecting all limits.

        Checks limits in this order (most restrictive first):
        1. Total portfolio limit:
           - Original mode: 12 units
           - Modern mode: 20% total risk
        2. Correlation group limit (6 units)
        3. Per-market limit (4 units)

        Args:
            portfolio: Current portfolio state
            symbol: Symbol to add units for
            units_to_add: Number of units to add
            correlation_group: Correlation group of the symbol

        Returns:
            LimitCheckResult with detailed information
        """
        # Get current counts
        current_market_units = 0
        if portfolio.has_position(symbol):
            current_market_units = portfolio.get_position(symbol).total_units

        current_group_units = 0
        if correlation_group:
            current_group_units = portfolio.units_in_group(correlation_group)

        current_total_units = portfolio.total_units

        # Calculate current total risk (for modern mode)
        current_total_risk = current_total_units * self.risk_per_unit
        new_total_risk = (current_total_units + units_to_add) * self.risk_per_unit

        # Check limits in order (most restrictive first)
        violation = LimitViolation.NONE
        reason = "OK"

        # 1. Check total limit (mode-dependent)
        if self.use_risk_cap_mode:
            # MODERN MODE: Check total risk cap (Rule 17 - Portfolio Heat Cap)
            if new_total_risk > self.max_total_risk:
                violation = LimitViolation.RISK_CAP
                reason = (
                    f"Would exceed {self.max_total_risk:.1%} total risk cap "
                    f"({current_total_risk:.1%} current + {units_to_add * self.risk_per_unit:.1%} requested = "
                    f"{new_total_risk:.1%})"
                )
        else:
            # ORIGINAL MODE: Check unit count limit
            if current_total_units + units_to_add > self.max_total:
                violation = LimitViolation.TOTAL
                reason = (
                    f"Would exceed {self.max_total} total units "
                    f"({current_total_units} current + {units_to_add} requested = "
                    f"{current_total_units + units_to_add})"
                )

        # 2. Check correlation limit (only if group specified, applies to both modes)
        if violation == LimitViolation.NONE:
            if correlation_group and current_group_units + units_to_add > self.max_correlated:
                violation = LimitViolation.CORRELATED
                reason = (
                    f"Would exceed {self.max_correlated} units in {correlation_group.value} "
                    f"({current_group_units} current + {units_to_add} requested = "
                    f"{current_group_units + units_to_add})"
                )

        # 3. Check per-market limit (applies to both modes)
        if violation == LimitViolation.NONE:
            if current_market_units + units_to_add > self.max_per_market:
                violation = LimitViolation.PER_MARKET
                reason = (
                    f"Would exceed {self.max_per_market} units in {symbol} "
                    f"({current_market_units} current + {units_to_add} requested = "
                    f"{current_market_units + units_to_add})"
                )

        return LimitCheckResult(
            allowed=(violation == LimitViolation.NONE),
            violation=violation,
            reason=reason,
            symbol=symbol,
            units_requested=units_to_add,
            current_market_units=current_market_units,
            current_group_units=current_group_units,
            current_total_units=current_total_units,
            max_per_market=self.max_per_market,
            max_correlated=self.max_correlated,
            max_total=self.max_total,
            current_total_risk=current_total_risk,
            max_total_risk=self.max_total_risk,
            risk_per_unit=self.risk_per_unit,
            use_risk_cap_mode=self.use_risk_cap_mode,
        )

    def can_pyramid(
        self,
        portfolio: Portfolio,
        symbol: str,
        correlation_group: CorrelationGroup | None = None,
    ) -> LimitCheckResult:
        """Check if a position can add one more pyramid unit.

        Convenience method for pyramid operations (always adds 1 unit).

        Args:
            portfolio: Current portfolio state
            symbol: Symbol to pyramid
            correlation_group: Correlation group of the symbol

        Returns:
            LimitCheckResult for adding 1 unit
        """
        return self.can_add_position(
            portfolio=portfolio,
            symbol=symbol,
            units_to_add=1,
            correlation_group=correlation_group,
        )

    def check_portfolio_status(
        self, portfolio: Portfolio
    ) -> dict[str, dict]:
        """Get current portfolio status against limits.

        Returns:
            Dict with status for each limit type:
            {
                "mode": "risk_cap" or "unit_count",
                "total": {
                    "current_units": 10,
                    "max_units": 12,  # original mode
                    "current_risk": 0.05,
                    "max_risk": 0.20,  # modern mode
                    "at_limit": False,
                },
                "groups": {
                    "metals": {"current": 6, "max": 6, "at_limit": True},
                    ...
                }
            }
        """
        # Calculate group totals
        group_totals: dict[CorrelationGroup, int] = {}
        for pos in portfolio.positions.values():
            if pos.correlation_group:
                if pos.correlation_group not in group_totals:
                    group_totals[pos.correlation_group] = 0
                group_totals[pos.correlation_group] += pos.total_units

        # Build status
        groups_status = {}
        for group, count in group_totals.items():
            groups_status[group.value] = {
                "current": count,
                "max": self.max_correlated,
                "at_limit": count >= self.max_correlated,
            }

        # Calculate risk
        current_risk = portfolio.total_units * self.risk_per_unit

        # Determine if at limit based on mode
        if self.use_risk_cap_mode:
            at_limit = current_risk >= self.max_total_risk
        else:
            at_limit = portfolio.total_units >= self.max_total

        return {
            "mode": "risk_cap" if self.use_risk_cap_mode else "unit_count",
            "total": {
                "current_units": portfolio.total_units,
                "max_units": self.max_total,
                "current_risk": float(current_risk),
                "max_risk": float(self.max_total_risk),
                "at_limit": at_limit,
            },
            "groups": groups_status,
        }

"""Position limit checker for Turtle Trading system.

Enforces the Turtle position limits:
- Rule: Max 4 units per market
- Rule: Max 6 units in correlated markets
- Rule: Max 12 units total portfolio
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, auto

from src.domain.models.enums import CorrelationGroup
from src.domain.models.portfolio import Portfolio
from src.domain.rules import (
    MAX_UNITS_CORRELATED,
    MAX_UNITS_PER_MARKET,
    MAX_UNITS_TOTAL,
)


class LimitViolation(str, Enum):
    """Type of limit violation."""

    NONE = "none"
    PER_MARKET = "per_market"  # Would exceed 4 units in single market
    CORRELATED = "correlated"  # Would exceed 6 units in correlated group
    TOTAL = "total"  # Would exceed 12 units total


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
        """Check if this would exceed total portfolio limit."""
        return self.violation == LimitViolation.TOTAL

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
        """How many more units can be added to portfolio."""
        return max(0, self.max_total - self.current_total_units)


class LimitChecker:
    """Domain service for checking position limits.

    The Turtle Trading system uses unit-based limits:
    - Max 4 units per individual market
    - Max 6 units across correlated markets (e.g., all metals)
    - Max 12 units in the entire portfolio

    Modern trend followers like Parker use volatility-based "heat" caps,
    but we implement the original unit-count rules for clarity.
    """

    def __init__(
        self,
        max_per_market: int = MAX_UNITS_PER_MARKET,
        max_correlated: int = MAX_UNITS_CORRELATED,
        max_total: int = MAX_UNITS_TOTAL,
    ):
        """Initialize limit checker with configured limits.

        Args:
            max_per_market: Max units per market (default 4)
            max_correlated: Max units in correlated markets (default 6)
            max_total: Max total portfolio units (default 12)
        """
        self.max_per_market = max_per_market
        self.max_correlated = max_correlated
        self.max_total = max_total

    def can_add_position(
        self,
        portfolio: Portfolio,
        symbol: str,
        units_to_add: int,
        correlation_group: CorrelationGroup | None = None,
    ) -> LimitCheckResult:
        """Check if units can be added while respecting all limits.

        Checks limits in this order (most restrictive first):
        1. Total portfolio limit (12 units)
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

        # Check limits in order (most restrictive first)
        violation = LimitViolation.NONE
        reason = "OK"

        # 1. Check total limit
        if current_total_units + units_to_add > self.max_total:
            violation = LimitViolation.TOTAL
            reason = (
                f"Would exceed {self.max_total} total units "
                f"({current_total_units} current + {units_to_add} requested = "
                f"{current_total_units + units_to_add})"
            )

        # 2. Check correlation limit (only if group specified)
        elif correlation_group and current_group_units + units_to_add > self.max_correlated:
            violation = LimitViolation.CORRELATED
            reason = (
                f"Would exceed {self.max_correlated} units in {correlation_group.value} "
                f"({current_group_units} current + {units_to_add} requested = "
                f"{current_group_units + units_to_add})"
            )

        # 3. Check per-market limit
        elif current_market_units + units_to_add > self.max_per_market:
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
    ) -> dict[str, dict[str, int | bool]]:
        """Get current portfolio status against limits.

        Returns:
            Dict with status for each limit type:
            {
                "total": {"current": 10, "max": 12, "at_limit": False},
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

        return {
            "total": {
                "current": portfolio.total_units,
                "max": self.max_total,
                "at_limit": portfolio.total_units >= self.max_total,
            },
            "groups": groups_status,
        }

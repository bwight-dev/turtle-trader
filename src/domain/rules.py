"""Turtle Trading rules configuration.

This module defines the core rules as constants, making them
explicit and testable. All rules are sourced from:
- The Original Turtle Trading Rules (Faith)
- Way of the Turtle (Faith)
- The Complete TurtleTrader (Covel)
- Jerry Parker/RCM interview transcripts
"""

from decimal import Decimal
from typing import Final

# =============================================================================
# VOLATILITY & POSITION SIZING (Rules 3-5)
# =============================================================================

# N (ATR) calculation period - 20-day Wilder's smoothing
N_PERIOD: Final[int] = 20

# Risk per trade (Rule 4)
# Original (1983): 1.0% for ~20 markets
# Modern (Parker): 0.5% for 300+ markets
RISK_PER_TRADE: Final[Decimal] = Decimal("0.005")  # 0.5%

# Drawdown reduction (Rule 5)
# When equity drops 10% from peak, reduce notional by 20%
DRAWDOWN_THRESHOLD: Final[Decimal] = Decimal("0.10")  # 10%
DRAWDOWN_REDUCTION: Final[Decimal] = Decimal("0.20")  # 20%
DRAWDOWN_EQUITY_REDUCTION: Final[Decimal] = DRAWDOWN_REDUCTION  # Alias


# =============================================================================
# ENTRY RULES (Rules 6-9)
# =============================================================================

# System 1: 20-day breakout
S1_ENTRY_PERIOD: Final[int] = 20

# System 2: 55-day breakout (failsafe)
S2_ENTRY_PERIOD: Final[int] = 55


# =============================================================================
# EXIT RULES (Rules 10, 13, 14)
# =============================================================================

# Hard stop: 2N from entry (non-negotiable)
STOP_MULTIPLIER: Final[Decimal] = Decimal("2")

# System 1: 10-day opposite breakout
S1_EXIT_PERIOD: Final[int] = 10

# System 2: 20-day opposite breakout
S2_EXIT_PERIOD: Final[int] = 20


# =============================================================================
# PYRAMIDING (Rules 11, 12)
# =============================================================================

# Add 1 unit at +½N intervals from last entry
PYRAMID_INTERVAL_MULTIPLIER: Final[Decimal] = Decimal("0.5")

# Maximum units per market
MAX_UNITS_PER_MARKET: Final[int] = 4


# =============================================================================
# POSITION LIMITS
# =============================================================================

# Maximum units in correlated markets
MAX_UNITS_CORRELATED: Final[int] = 6

# Maximum total portfolio units
MAX_UNITS_TOTAL: Final[int] = 12


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def calculate_stop_price(
    entry_price: Decimal,
    n_value: Decimal,
    is_long: bool,
) -> Decimal:
    """Calculate 2N stop price.

    Rule 10: Stop = Entry ± 2N

    Args:
        entry_price: Entry price
        n_value: Current N (ATR) value
        is_long: True for long positions

    Returns:
        Stop price
    """
    two_n = STOP_MULTIPLIER * n_value
    if is_long:
        return entry_price - two_n
    return entry_price + two_n


def calculate_pyramid_trigger(
    last_entry_price: Decimal,
    n_value: Decimal,
    is_long: bool,
) -> Decimal:
    """Calculate next pyramid trigger price.

    Rule 11: Add at +½N from last entry

    Args:
        last_entry_price: Most recent entry price
        n_value: N value at last entry
        is_long: True for long positions

    Returns:
        Price that triggers pyramid add
    """
    half_n = PYRAMID_INTERVAL_MULTIPLIER * n_value
    if is_long:
        return last_entry_price + half_n
    return last_entry_price - half_n


def calculate_unit_size(
    equity: Decimal,
    n_value: Decimal,
    point_value: Decimal,
    risk_pct: Decimal = RISK_PER_TRADE,
) -> int:
    """Calculate unit size in contracts.

    Rule 4: Unit = (Risk% × Equity) / Dollar_Volatility

    Args:
        equity: Account equity (use notional during drawdown)
        n_value: Current N (ATR) value
        point_value: Dollar value per point move
        risk_pct: Risk percentage per trade (default 0.5%)

    Returns:
        Number of contracts (rounded down)
    """
    risk_budget = equity * risk_pct
    dollar_volatility = n_value * point_value

    if dollar_volatility <= 0:
        return 0

    return int(risk_budget / dollar_volatility)


def get_entry_period(is_s1: bool) -> int:
    """Get the Donchian entry period for a system."""
    return S1_ENTRY_PERIOD if is_s1 else S2_ENTRY_PERIOD


def get_exit_period(is_s1: bool) -> int:
    """Get the Donchian exit period for a system."""
    return S1_EXIT_PERIOD if is_s1 else S2_EXIT_PERIOD

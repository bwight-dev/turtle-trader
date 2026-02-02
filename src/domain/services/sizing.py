"""Position sizing calculations for Turtle Trading system.

Implements Rule 4: Unit Size Calculation
Unit = (Risk Factor × Equity) / Dollar Volatility

Where:
- Risk Factor = 0.5% (Parker modern for 300+ markets)
- Dollar Volatility = N × Dollars Per Point
"""

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from src.domain.models.market import NValue
from src.domain.rules import RISK_PER_TRADE


@dataclass(frozen=True)
class UnitSize:
    """Result of unit size calculation."""

    contracts: Decimal  # May be fractional for ETFs, whole for futures
    risk_amount: Decimal
    dollar_volatility: Decimal
    raw_size: Decimal  # Before rounding (same as contracts when fractional)

    @property
    def is_valid(self) -> bool:
        """Check if unit size is valid (at least minimum tradeable amount)."""
        return self.contracts >= Decimal("0.001")


def calculate_unit_size(
    equity: Decimal,
    n_value: NValue | Decimal,
    point_value: Decimal,
    risk_pct: Decimal = RISK_PER_TRADE,
    min_contracts: int = 1,
    allow_fractional: bool = False,
) -> UnitSize:
    """Calculate position unit size.

    Rule 4: Unit = (Risk × Equity) / (N × PointValue)

    Args:
        equity: Account equity to use for sizing (use notional during drawdown)
        n_value: N (ATR) value - either NValue object or raw Decimal
        point_value: Dollar value per point move
        risk_pct: Risk per trade as decimal (default 0.005 = 0.5%)
        min_contracts: Minimum contracts (default 1)
        allow_fractional: If True, return exact fractional shares (for ETFs).
                         If False, round down to whole contracts (for futures).

    Returns:
        UnitSize with calculated contracts and metadata

    Example:
        >>> # $100k equity, N=20, $10/point, 0.5% risk
        >>> # Risk budget = $100,000 × 0.005 = $500
        >>> # Dollar volatility = 20 × $10 = $200
        >>> # Unit size = $500 / $200 = 2.5 → 2 contracts (futures)
        >>> size = calculate_unit_size(
        ...     equity=Decimal("100000"),
        ...     n_value=NValue(value=Decimal("20"), ...),
        ...     point_value=Decimal("10"),
        ... )
        >>> size.contracts
        Decimal('2')

        >>> # With fractional shares (ETFs): 2.5 shares exactly
        >>> size = calculate_unit_size(..., allow_fractional=True)
        >>> size.contracts
        Decimal('2.5')
    """
    # Extract N value if NValue object
    n = n_value.value if isinstance(n_value, NValue) else n_value

    # Calculate risk budget
    risk_amount = equity * risk_pct

    # Calculate dollar volatility (risk per contract)
    dollar_volatility = n * point_value

    # Handle edge case of zero volatility
    if dollar_volatility <= 0:
        return UnitSize(
            contracts=Decimal("0"),
            risk_amount=risk_amount,
            dollar_volatility=Decimal("0"),
            raw_size=Decimal("0"),
        )

    # Calculate raw unit size
    raw_size = risk_amount / dollar_volatility

    if allow_fractional:
        # ETFs: Use exact fractional shares for precise risk management
        # This is the key benefit of ETFs over futures - no granularity problem
        # Round to 6 decimal places to avoid floating point issues
        contracts = raw_size.quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    else:
        # Futures: Round DOWN (conservative) to whole contracts
        # Never risk more than intended
        #
        # IMPORTANT: Per Curtis Faith (Way of the Turtle), always TRUNCATE to zero
        # if the calculated size is less than 1 contract. Never round up.
        # "If the math resulted in 0.8 or 0.5 contracts, truncating results in zero."
        # Rounding up would violate the risk rules by risking more than the
        # percent-risk limit allows (e.g., risking 3% instead of 0.5%).
        #
        # This means small accounts will be unable to trade some markets -
        # that's intentional. It preserves the risk discipline.
        contracts = Decimal(int(raw_size.quantize(Decimal("1"), rounding=ROUND_DOWN)))

    # NOTE: We intentionally do NOT bump to min_contracts if raw_size < 1.
    # The min_contracts parameter is only used when contracts >= 1 already.
    # If raw_size < 1, the trade should be skipped (contracts = 0).

    return UnitSize(
        contracts=contracts,
        risk_amount=risk_amount,
        dollar_volatility=dollar_volatility,
        raw_size=raw_size,
    )


def calculate_contracts_for_risk(
    risk_budget: Decimal,
    n_value: Decimal,
    point_value: Decimal,
    allow_fractional: bool = False,
) -> Decimal:
    """Calculate contracts for a specific risk budget.

    Useful for pyramiding where risk per add may differ.

    Args:
        risk_budget: Maximum dollar risk
        n_value: Current N (ATR) value
        point_value: Dollar value per point
        allow_fractional: If True, return exact fractional shares (for ETFs)

    Returns:
        Number of contracts (Decimal - may be fractional for ETFs)
    """
    dollar_volatility = n_value * point_value

    if dollar_volatility <= 0:
        return Decimal("0")

    raw_size = risk_budget / dollar_volatility

    if allow_fractional:
        return raw_size.quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    else:
        return Decimal(int(raw_size.quantize(Decimal("1"), rounding=ROUND_DOWN)))


def scale_position_size(
    base_size: UnitSize,
    scale_factor: Decimal,
    allow_fractional: bool = False,
) -> Decimal:
    """Scale a position size by a factor.

    Useful for position reduction during drawdown.

    Args:
        base_size: Original calculated size
        scale_factor: Factor to multiply by (e.g., 0.8 for 20% reduction)
        allow_fractional: If True, return exact fractional shares (for ETFs)

    Returns:
        Scaled number of contracts (Decimal - may be fractional for ETFs)
    """
    scaled = base_size.raw_size * scale_factor

    if allow_fractional:
        return scaled.quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    else:
        return Decimal(int(scaled.quantize(Decimal("1"), rounding=ROUND_DOWN)))

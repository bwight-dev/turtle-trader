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

    contracts: int
    risk_amount: Decimal
    dollar_volatility: Decimal
    raw_size: Decimal  # Before rounding

    @property
    def is_valid(self) -> bool:
        """Check if unit size is valid (at least 1 contract)."""
        return self.contracts >= 1


def calculate_unit_size(
    equity: Decimal,
    n_value: NValue | Decimal,
    point_value: Decimal,
    risk_pct: Decimal = RISK_PER_TRADE,
    min_contracts: int = 1,
) -> UnitSize:
    """Calculate position unit size.

    Rule 4: Unit = (Risk × Equity) / (N × PointValue)

    Args:
        equity: Account equity to use for sizing (use notional during drawdown)
        n_value: N (ATR) value - either NValue object or raw Decimal
        point_value: Dollar value per point move
        risk_pct: Risk per trade as decimal (default 0.005 = 0.5%)
        min_contracts: Minimum contracts (default 1)

    Returns:
        UnitSize with calculated contracts and metadata

    Example:
        >>> # $100k equity, N=20, $10/point, 0.5% risk
        >>> # Risk budget = $100,000 × 0.005 = $500
        >>> # Dollar volatility = 20 × $10 = $200
        >>> # Unit size = $500 / $200 = 2.5 → 2 contracts
        >>> size = calculate_unit_size(
        ...     equity=Decimal("100000"),
        ...     n_value=NValue(value=Decimal("20"), ...),
        ...     point_value=Decimal("10"),
        ... )
        >>> size.contracts
        2
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
            contracts=0,
            risk_amount=risk_amount,
            dollar_volatility=Decimal("0"),
            raw_size=Decimal("0"),
        )

    # Calculate raw unit size
    raw_size = risk_amount / dollar_volatility

    # Round DOWN (conservative) to whole contracts
    # Never risk more than intended
    contracts = int(raw_size.quantize(Decimal("1"), rounding=ROUND_DOWN))

    # Apply minimum
    if contracts < min_contracts and raw_size >= Decimal("0.5"):
        # Only bump to min if we're at least halfway there
        contracts = min_contracts

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
) -> int:
    """Calculate contracts for a specific risk budget.

    Useful for pyramiding where risk per add may differ.

    Args:
        risk_budget: Maximum dollar risk
        n_value: Current N (ATR) value
        point_value: Dollar value per point

    Returns:
        Number of contracts (rounded down)
    """
    dollar_volatility = n_value * point_value

    if dollar_volatility <= 0:
        return 0

    raw_size = risk_budget / dollar_volatility
    return int(raw_size.quantize(Decimal("1"), rounding=ROUND_DOWN))


def scale_position_size(
    base_size: UnitSize,
    scale_factor: Decimal,
) -> int:
    """Scale a position size by a factor.

    Useful for position reduction during drawdown.

    Args:
        base_size: Original calculated size
        scale_factor: Factor to multiply by (e.g., 0.8 for 20% reduction)

    Returns:
        Scaled number of contracts (rounded down)
    """
    scaled = base_size.raw_size * scale_factor
    return int(scaled.quantize(Decimal("1"), rounding=ROUND_DOWN))

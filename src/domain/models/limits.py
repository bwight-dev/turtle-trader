"""Position limit models for Turtle Trading system."""

from pydantic import BaseModel, Field

from src.domain.models.enums import CorrelationGroup


class LimitCheckResult(BaseModel):
    """Result of checking position limits.

    Turtle position limits:
    - 4 units per market
    - 6 units in correlated markets
    - 12 units total
    """

    model_config = {"frozen": True}

    allowed: bool
    reason: str

    # Current state
    current_market_units: int = Field(default=0, ge=0)
    current_group_units: int = Field(default=0, ge=0)
    current_total_units: int = Field(default=0, ge=0)

    # Limits
    max_market_units: int = Field(default=4, ge=1)
    max_group_units: int = Field(default=6, ge=1)
    max_total_units: int = Field(default=12, ge=1)

    # Which limit would be violated
    limit_violated: str | None = Field(
        default=None, description="Which limit would be violated"
    )
    correlation_group: CorrelationGroup | None = Field(
        default=None, description="Correlation group being checked"
    )

    @property
    def market_headroom(self) -> int:
        """How many more units can be added to this market."""
        return self.max_market_units - self.current_market_units

    @property
    def group_headroom(self) -> int:
        """How many more units can be added to this correlation group."""
        return self.max_group_units - self.current_group_units

    @property
    def total_headroom(self) -> int:
        """How many more units can be added to the portfolio."""
        return self.max_total_units - self.current_total_units

    @property
    def available_units(self) -> int:
        """Maximum units that can be added given all constraints."""
        return min(self.market_headroom, self.group_headroom, self.total_headroom)

    @classmethod
    def ok(
        cls,
        current_market_units: int,
        current_group_units: int,
        current_total_units: int,
        correlation_group: CorrelationGroup | None = None,
    ) -> "LimitCheckResult":
        """Create a passing limit check result."""
        return cls(
            allowed=True,
            reason="Within all position limits",
            current_market_units=current_market_units,
            current_group_units=current_group_units,
            current_total_units=current_total_units,
            correlation_group=correlation_group,
        )

    @classmethod
    def blocked(
        cls,
        reason: str,
        limit_violated: str,
        current_market_units: int,
        current_group_units: int,
        current_total_units: int,
        correlation_group: CorrelationGroup | None = None,
    ) -> "LimitCheckResult":
        """Create a failing limit check result."""
        return cls(
            allowed=False,
            reason=reason,
            limit_violated=limit_violated,
            current_market_units=current_market_units,
            current_group_units=current_group_units,
            current_total_units=current_total_units,
            correlation_group=correlation_group,
        )

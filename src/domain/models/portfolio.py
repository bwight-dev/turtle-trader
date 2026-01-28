"""Portfolio aggregate root for Turtle Trading system."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, computed_field

from src.domain.models.enums import CorrelationGroup
from src.domain.models.position import Position


class Portfolio(BaseModel):
    """Portfolio aggregate root - manages all open positions.

    This is the aggregate root that enforces position limits:
    - Rule: Max 4 units per market
    - Rule: Max 6 units in correlated markets
    - Rule: Max 12 units total
    """

    model_config = {"frozen": True}

    positions: dict[str, Position] = Field(
        default_factory=dict,
        description="Open positions keyed by symbol",
    )
    updated_at: datetime = Field(default_factory=datetime.now)

    @computed_field
    @property
    def total_units(self) -> int:
        """Total units across all positions."""
        return sum(pos.total_units for pos in self.positions.values())

    @computed_field
    @property
    def total_contracts(self) -> int:
        """Total contracts across all positions."""
        return sum(pos.total_contracts for pos in self.positions.values())

    def units_in_group(self, group: CorrelationGroup) -> int:
        """Count units in a correlation group."""
        return sum(
            pos.total_units
            for pos in self.positions.values()
            if pos.correlation_group == group
        )

    def get_position(self, symbol: str) -> Position | None:
        """Get position by symbol."""
        return self.positions.get(symbol)

    def has_position(self, symbol: str) -> bool:
        """Check if portfolio has a position in this symbol."""
        return symbol in self.positions

    def can_add_units(
        self,
        symbol: str,
        units_to_add: int,
        correlation_group: CorrelationGroup | None = None,
        max_per_market: int = 4,
        max_correlated: int = 6,
        max_total: int = 12,
    ) -> tuple[bool, str]:
        """Check if units can be added while respecting limits.

        Args:
            symbol: Symbol to add units for
            units_to_add: Number of units to add
            correlation_group: Correlation group of the symbol
            max_per_market: Max units per market (default 4)
            max_correlated: Max units in correlated markets (default 6)
            max_total: Max total portfolio units (default 12)

        Returns:
            Tuple of (allowed, reason)
        """
        # Check per-market limit
        current_market_units = 0
        if symbol in self.positions:
            current_market_units = self.positions[symbol].total_units

        if current_market_units + units_to_add > max_per_market:
            return False, f"Would exceed {max_per_market} units in {symbol}"

        # Check correlation limit
        if correlation_group:
            current_group_units = self.units_in_group(correlation_group)
            if current_group_units + units_to_add > max_correlated:
                return False, f"Would exceed {max_correlated} units in {correlation_group.value}"

        # Check total limit
        if self.total_units + units_to_add > max_total:
            return False, f"Would exceed {max_total} total units"

        return True, "OK"

    def add_position(self, position: Position) -> "Portfolio":
        """Add a new position to the portfolio.

        Validates limits before adding.

        Returns:
            New Portfolio with added position.

        Raises:
            ValueError: If position would violate limits.
        """
        allowed, reason = self.can_add_units(
            symbol=position.symbol,
            units_to_add=position.total_units,
            correlation_group=position.correlation_group,
        )

        if not allowed:
            raise ValueError(f"Cannot add position: {reason}")

        if position.symbol in self.positions:
            raise ValueError(f"Position in {position.symbol} already exists")

        new_positions = dict(self.positions)
        new_positions[position.symbol] = position

        return self.model_copy(
            update={"positions": new_positions, "updated_at": datetime.now()}
        )

    def update_position(self, position: Position) -> "Portfolio":
        """Update an existing position.

        Returns:
            New Portfolio with updated position.

        Raises:
            ValueError: If position doesn't exist.
        """
        if position.symbol not in self.positions:
            raise ValueError(f"No position in {position.symbol}")

        new_positions = dict(self.positions)
        new_positions[position.symbol] = position

        return self.model_copy(
            update={"positions": new_positions, "updated_at": datetime.now()}
        )

    def close_position(self, symbol: str) -> tuple["Portfolio", Position]:
        """Close and remove a position.

        Returns:
            Tuple of (new Portfolio, closed Position)

        Raises:
            ValueError: If position doesn't exist.
        """
        if symbol not in self.positions:
            raise ValueError(f"No position in {symbol}")

        closed = self.positions[symbol]
        new_positions = {k: v for k, v in self.positions.items() if k != symbol}

        new_portfolio = self.model_copy(
            update={"positions": new_positions, "updated_at": datetime.now()}
        )

        return new_portfolio, closed

    def total_unrealized_pnl(
        self, prices: dict[str, Decimal], point_values: dict[str, Decimal]
    ) -> Decimal:
        """Calculate total unrealized P&L.

        Args:
            prices: Current prices by symbol
            point_values: Point values by symbol

        Returns:
            Total unrealized P&L in dollars.
        """
        total = Decimal("0")
        for symbol, pos in self.positions.items():
            if symbol in prices and symbol in point_values:
                total += pos.unrealized_pnl(prices[symbol], point_values[symbol])
        return total

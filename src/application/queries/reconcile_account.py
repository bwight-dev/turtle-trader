"""Account reconciliation query for Turtle Trading system.

This is an application layer query that compares the internal
portfolio state with actual broker positions and account values.

Used for:
- Pre-trade validation
- End-of-day reconciliation
- Detecting manual trades or broker discrepancies
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from src.domain.interfaces.broker import Broker, BrokerPosition
from src.domain.models.enums import Direction
from src.domain.models.portfolio import Portfolio


@dataclass
class PositionMismatch:
    """Details of a position mismatch between internal and broker."""

    symbol: str
    mismatch_type: str  # "missing_at_broker", "missing_internal", "quantity", "direction"
    internal_quantity: int | None = None
    broker_quantity: int | None = None
    internal_direction: Direction | None = None
    broker_direction: Direction | None = None
    details: str = ""


@dataclass
class AccountMismatch:
    """Details of an account-level mismatch."""

    field: str  # "equity", "buying_power", etc.
    expected: Decimal | None = None
    actual: Decimal | None = None
    difference: Decimal | None = None
    details: str = ""


@dataclass
class ReconciliationResult:
    """Result of account reconciliation."""

    matches: bool
    reconciled_at: datetime = field(default_factory=datetime.now)
    position_mismatches: list[PositionMismatch] = field(default_factory=list)
    account_mismatches: list[AccountMismatch] = field(default_factory=list)
    positions_matched: int = 0
    broker_equity: Decimal | None = None
    broker_buying_power: Decimal | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def has_position_mismatches(self) -> bool:
        """Check if there are any position mismatches."""
        return len(self.position_mismatches) > 0

    @property
    def has_account_mismatches(self) -> bool:
        """Check if there are any account-level mismatches."""
        return len(self.account_mismatches) > 0

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [f"Reconciliation at {self.reconciled_at.isoformat()}"]

        if self.matches:
            lines.append(f"✓ All {self.positions_matched} positions match")
        else:
            if self.position_mismatches:
                lines.append(f"✗ {len(self.position_mismatches)} position mismatches:")
                for m in self.position_mismatches:
                    lines.append(f"  - {m.symbol}: {m.mismatch_type} - {m.details}")

            if self.account_mismatches:
                lines.append(f"✗ {len(self.account_mismatches)} account mismatches:")
                for m in self.account_mismatches:
                    lines.append(f"  - {m.field}: {m.details}")

        if self.broker_equity:
            lines.append(f"Broker equity: ${self.broker_equity:,.2f}")
        if self.broker_buying_power:
            lines.append(f"Buying power: ${self.broker_buying_power:,.2f}")

        return "\n".join(lines)


class ReconcileAccountQuery:
    """Query to reconcile portfolio with broker state.

    This query compares internal portfolio state with actual broker
    positions and reports any discrepancies. Unlike SyncPortfolioQuery,
    it does NOT modify the portfolio - it only reports differences.

    Use cases:
    - Pre-trade validation (ensure we're in sync before placing orders)
    - End-of-day reconciliation
    - Alert on unexpected broker-side changes
    """

    def __init__(self, broker: Broker) -> None:
        """Initialize the query.

        Args:
            broker: Broker for position and account queries
        """
        self._broker = broker

    async def execute(
        self,
        portfolio: Portfolio,
        expected_equity: Decimal | None = None,
        equity_tolerance: Decimal = Decimal("0.01"),  # 1% tolerance
    ) -> ReconciliationResult:
        """Execute account reconciliation.

        Args:
            portfolio: Internal portfolio state to compare
            expected_equity: Optional expected account equity to verify
            equity_tolerance: Tolerance for equity comparison (default 1%)

        Returns:
            ReconciliationResult with match status and any discrepancies
        """
        position_mismatches: list[PositionMismatch] = []
        account_mismatches: list[AccountMismatch] = []
        errors: list[str] = []
        positions_matched = 0

        # Get broker positions
        try:
            broker_positions = await self._broker.get_positions()
        except Exception as e:
            return ReconciliationResult(
                matches=False,
                errors=[f"Failed to get broker positions: {e}"],
            )

        # Create lookup for broker positions
        broker_by_symbol = {pos.symbol: pos for pos in broker_positions}

        # Check each internal position against broker
        for symbol, internal_pos in portfolio.positions.items():
            broker_pos = broker_by_symbol.get(symbol)

            if broker_pos is None:
                # Position exists internally but not at broker
                position_mismatches.append(
                    PositionMismatch(
                        symbol=symbol,
                        mismatch_type="missing_at_broker",
                        internal_quantity=internal_pos.total_contracts,
                        internal_direction=internal_pos.direction,
                        details=f"Internal has {internal_pos.total_contracts} {internal_pos.direction.value}, broker has none",
                    )
                )
            else:
                # Compare quantities and direction
                mismatches = self._compare_position(internal_pos, broker_pos)
                if mismatches:
                    position_mismatches.extend(mismatches)
                else:
                    positions_matched += 1

        # Check for broker positions not in internal portfolio
        for symbol, broker_pos in broker_by_symbol.items():
            if symbol not in portfolio.positions:
                broker_direction = (
                    Direction.LONG if broker_pos.quantity > 0 else Direction.SHORT
                )
                position_mismatches.append(
                    PositionMismatch(
                        symbol=symbol,
                        mismatch_type="missing_internal",
                        broker_quantity=broker_pos.abs_quantity,
                        broker_direction=broker_direction,
                        details=f"Broker has {broker_pos.abs_quantity} {broker_direction.value}, not tracked internally",
                    )
                )

        # Get account values
        broker_equity = None
        broker_buying_power = None
        try:
            broker_equity = await self._broker.get_account_value()
            broker_buying_power = await self._broker.get_buying_power()
        except Exception as e:
            errors.append(f"Failed to get account values: {e}")

        # Check equity if expected value provided
        if expected_equity is not None and broker_equity is not None:
            equity_diff = abs(broker_equity - expected_equity)
            tolerance_amount = expected_equity * equity_tolerance
            if equity_diff > tolerance_amount:
                account_mismatches.append(
                    AccountMismatch(
                        field="equity",
                        expected=expected_equity,
                        actual=broker_equity,
                        difference=broker_equity - expected_equity,
                        details=f"Equity differs by ${equity_diff:,.2f} (>{equity_tolerance * 100}% tolerance)",
                    )
                )

        # Determine overall match status
        matches = len(position_mismatches) == 0 and len(account_mismatches) == 0

        return ReconciliationResult(
            matches=matches,
            position_mismatches=position_mismatches,
            account_mismatches=account_mismatches,
            positions_matched=positions_matched,
            broker_equity=broker_equity,
            broker_buying_power=broker_buying_power,
            errors=errors,
        )

    def _compare_position(
        self,
        internal_pos,
        broker_pos: BrokerPosition,
    ) -> list[PositionMismatch]:
        """Compare internal position with broker position.

        Returns list of mismatches (empty if they match).
        """
        mismatches = []
        symbol = broker_pos.symbol

        # Check quantity
        if internal_pos.total_contracts != broker_pos.abs_quantity:
            mismatches.append(
                PositionMismatch(
                    symbol=symbol,
                    mismatch_type="quantity",
                    internal_quantity=internal_pos.total_contracts,
                    broker_quantity=broker_pos.abs_quantity,
                    details=f"Internal has {internal_pos.total_contracts}, broker has {broker_pos.abs_quantity}",
                )
            )

        # Check direction
        internal_long = internal_pos.direction == Direction.LONG
        broker_long = broker_pos.quantity > 0
        if internal_long != broker_long:
            internal_dir = Direction.LONG if internal_long else Direction.SHORT
            broker_dir = Direction.LONG if broker_long else Direction.SHORT
            mismatches.append(
                PositionMismatch(
                    symbol=symbol,
                    mismatch_type="direction",
                    internal_direction=internal_dir,
                    broker_direction=broker_dir,
                    details=f"Internal is {internal_dir.value}, broker is {broker_dir.value}",
                )
            )

        return mismatches

    async def compare(
        self,
        portfolio: Portfolio,
        broker_positions: list[BrokerPosition] | None = None,
    ) -> ReconciliationResult:
        """Compare portfolio with broker positions (for testing).

        This is a convenience method that allows passing broker positions
        directly without querying the broker.

        Args:
            portfolio: Internal portfolio state
            broker_positions: Optional pre-fetched broker positions

        Returns:
            ReconciliationResult with match status
        """
        if broker_positions is None:
            return await self.execute(portfolio)

        # Use provided positions instead of querying
        position_mismatches: list[PositionMismatch] = []
        positions_matched = 0

        broker_by_symbol = {pos.symbol: pos for pos in broker_positions}

        # Check internal positions
        for symbol, internal_pos in portfolio.positions.items():
            broker_pos = broker_by_symbol.get(symbol)

            if broker_pos is None:
                position_mismatches.append(
                    PositionMismatch(
                        symbol=symbol,
                        mismatch_type="missing_at_broker",
                        internal_quantity=internal_pos.total_contracts,
                        internal_direction=internal_pos.direction,
                        details=f"Internal has {internal_pos.total_contracts}, broker has none",
                    )
                )
            else:
                mismatches = self._compare_position(internal_pos, broker_pos)
                if mismatches:
                    position_mismatches.extend(mismatches)
                else:
                    positions_matched += 1

        # Check broker positions not tracked
        for symbol, broker_pos in broker_by_symbol.items():
            if symbol not in portfolio.positions:
                broker_direction = (
                    Direction.LONG if broker_pos.quantity > 0 else Direction.SHORT
                )
                position_mismatches.append(
                    PositionMismatch(
                        symbol=symbol,
                        mismatch_type="missing_internal",
                        broker_quantity=broker_pos.abs_quantity,
                        broker_direction=broker_direction,
                        details=f"Broker has {broker_pos.abs_quantity}, not tracked internally",
                    )
                )

        matches = len(position_mismatches) == 0

        return ReconciliationResult(
            matches=matches,
            position_mismatches=position_mismatches,
            positions_matched=positions_matched,
        )


async def reconcile_account(
    broker: Broker,
    portfolio: Portfolio,
    expected_equity: Decimal | None = None,
) -> ReconciliationResult:
    """Convenience function to reconcile account.

    Args:
        broker: Broker for queries
        portfolio: Internal portfolio state
        expected_equity: Optional expected equity to verify

    Returns:
        ReconciliationResult with match status
    """
    query = ReconcileAccountQuery(broker)
    return await query.execute(portfolio, expected_equity)

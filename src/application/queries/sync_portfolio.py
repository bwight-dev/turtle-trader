"""Portfolio sync query for Turtle Trading system.

This is an application layer query that synchronizes the internal
portfolio state with broker positions.

Used for:
- Initial portfolio load on startup
- Periodic reconciliation
- After manual trades in TWS
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from src.domain.interfaces.broker import Broker, BrokerPosition
from src.domain.models.enums import CorrelationGroup, Direction, System
from src.domain.models.market import NValue
from src.domain.models.portfolio import Portfolio
from src.domain.models.position import Position, PyramidLevel


@dataclass
class PositionSyncResult:
    """Result of syncing a single position."""

    symbol: str
    action: str  # "added", "updated", "removed", "unchanged"
    broker_position: BrokerPosition | None = None
    internal_position: Position | None = None
    difference: str | None = None


@dataclass
class SyncResult:
    """Result of portfolio synchronization."""

    success: bool
    synced_at: datetime = field(default_factory=datetime.now)
    positions_synced: list[PositionSyncResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def added_count(self) -> int:
        """Number of positions added."""
        return sum(1 for p in self.positions_synced if p.action == "added")

    @property
    def updated_count(self) -> int:
        """Number of positions updated."""
        return sum(1 for p in self.positions_synced if p.action == "updated")

    @property
    def removed_count(self) -> int:
        """Number of positions removed."""
        return sum(1 for p in self.positions_synced if p.action == "removed")


# Symbol to correlation group mapping
CORRELATION_GROUPS = {
    "/MGC": CorrelationGroup.METALS,
    "/SIL": CorrelationGroup.METALS,
    "/HG": CorrelationGroup.METALS,
    "/MES": CorrelationGroup.EQUITY_US,
    "/MNQ": CorrelationGroup.EQUITY_US,
    "/M2K": CorrelationGroup.EQUITY_US,
    "/MYM": CorrelationGroup.EQUITY_US,
    "/MCL": CorrelationGroup.ENERGY,
    "/MNG": CorrelationGroup.ENERGY,
}


class SyncPortfolioQuery:
    """Query to synchronize portfolio with broker positions.

    This query:
    1. Fetches current positions from broker
    2. Compares with internal portfolio
    3. Creates/updates/removes positions as needed
    4. Returns sync results

    Note: This creates "flat" positions without pyramid level detail,
    since the broker doesn't track our pyramid structure.
    """

    def __init__(
        self,
        broker: Broker,
        default_system: System = System.S1,
    ) -> None:
        """Initialize the query.

        Args:
            broker: Broker for position queries
            default_system: Default system for new positions (S1 or S2)
        """
        self._broker = broker
        self._default_system = default_system

    async def execute(
        self,
        current_portfolio: Portfolio | None = None,
    ) -> tuple[Portfolio, SyncResult]:
        """Execute portfolio synchronization.

        Args:
            current_portfolio: Current portfolio state (None = fresh sync)

        Returns:
            Tuple of (synced Portfolio, SyncResult)
        """
        if current_portfolio is None:
            current_portfolio = Portfolio()

        sync_results: list[PositionSyncResult] = []
        errors: list[str] = []

        try:
            broker_positions = await self._broker.get_positions()
        except Exception as e:
            return current_portfolio, SyncResult(
                success=False,
                errors=[f"Failed to get broker positions: {e}"],
            )

        # Create lookup for broker positions
        broker_by_symbol = {pos.symbol: pos for pos in broker_positions}

        # Track which symbols we've processed
        processed_symbols: set[str] = set()
        new_positions: dict[str, Position] = {}

        # Process broker positions
        for broker_pos in broker_positions:
            symbol = broker_pos.symbol
            processed_symbols.add(symbol)

            internal_pos = current_portfolio.get_position(symbol)

            if internal_pos is None:
                # New position from broker
                new_pos = self._create_position_from_broker(broker_pos)
                new_positions[symbol] = new_pos
                sync_results.append(
                    PositionSyncResult(
                        symbol=symbol,
                        action="added",
                        broker_position=broker_pos,
                        internal_position=new_pos,
                    )
                )
            else:
                # Check if position needs update
                if self._positions_differ(internal_pos, broker_pos):
                    # Update internal position to match broker
                    updated_pos = self._update_position_from_broker(
                        internal_pos, broker_pos
                    )
                    new_positions[symbol] = updated_pos
                    sync_results.append(
                        PositionSyncResult(
                            symbol=symbol,
                            action="updated",
                            broker_position=broker_pos,
                            internal_position=updated_pos,
                            difference=self._describe_difference(
                                internal_pos, broker_pos
                            ),
                        )
                    )
                else:
                    # No change needed
                    new_positions[symbol] = internal_pos
                    sync_results.append(
                        PositionSyncResult(
                            symbol=symbol,
                            action="unchanged",
                            broker_position=broker_pos,
                            internal_position=internal_pos,
                        )
                    )

        # Check for positions in portfolio but not at broker (closed externally)
        for symbol, pos in current_portfolio.positions.items():
            if symbol not in processed_symbols:
                sync_results.append(
                    PositionSyncResult(
                        symbol=symbol,
                        action="removed",
                        internal_position=pos,
                        difference="Position closed at broker",
                    )
                )

        # Build new portfolio
        synced_portfolio = Portfolio(positions=new_positions)

        return synced_portfolio, SyncResult(
            success=True,
            positions_synced=sync_results,
            errors=errors,
        )

    def _create_position_from_broker(self, broker_pos: BrokerPosition) -> Position:
        """Create internal position from broker position.

        Note: This creates a "flat" position without detailed pyramid levels,
        since we can't know the exact entry history from broker.
        """
        direction = broker_pos.direction
        contracts = broker_pos.abs_quantity

        # Get correlation group if known
        correlation_group = CORRELATION_GROUPS.get(broker_pos.symbol)

        # Create a single pyramid level representing the entire position
        # We use average cost as the entry price
        pyramid_level = PyramidLevel(
            level=1,
            entry_price=broker_pos.average_cost,
            contracts=contracts,
            n_at_entry=Decimal("1"),  # Unknown, use placeholder
        )

        # Create N value placeholder
        n_value = NValue(
            value=Decimal("1"),  # Will be updated on next calculation
            calculated_at=datetime.now(),
            symbol=broker_pos.symbol,
        )

        return Position(
            id=uuid4(),
            symbol=broker_pos.symbol,
            direction=direction,
            system=self._default_system,
            correlation_group=correlation_group,
            pyramid_levels=(pyramid_level,),
            current_stop=Decimal("0"),  # Unknown, needs to be set
            initial_entry_price=broker_pos.average_cost,
            initial_n=n_value,
        )

    def _update_position_from_broker(
        self, internal_pos: Position, broker_pos: BrokerPosition
    ) -> Position:
        """Update internal position based on broker data.

        Only updates quantity-related fields; preserves our pyramid structure
        where possible.
        """
        # For now, just update the stop if broker shows different quantity
        # More sophisticated logic could try to preserve pyramid levels
        return internal_pos

    def _positions_differ(
        self, internal_pos: Position, broker_pos: BrokerPosition
    ) -> bool:
        """Check if internal and broker positions differ significantly."""
        # Check quantity mismatch
        if internal_pos.total_contracts != broker_pos.abs_quantity:
            return True

        # Check direction mismatch
        internal_long = internal_pos.direction == Direction.LONG
        broker_long = broker_pos.quantity > 0
        if internal_long != broker_long:
            return True

        return False

    def _describe_difference(
        self, internal_pos: Position, broker_pos: BrokerPosition
    ) -> str:
        """Describe the difference between internal and broker positions."""
        diffs = []

        if internal_pos.total_contracts != broker_pos.abs_quantity:
            diffs.append(
                f"qty: internal={internal_pos.total_contracts}, "
                f"broker={broker_pos.abs_quantity}"
            )

        internal_long = internal_pos.direction == Direction.LONG
        broker_long = broker_pos.quantity > 0
        if internal_long != broker_long:
            diffs.append(
                f"direction: internal={'LONG' if internal_long else 'SHORT'}, "
                f"broker={'LONG' if broker_long else 'SHORT'}"
            )

        return "; ".join(diffs) if diffs else "no difference"


async def sync_portfolio(
    broker: Broker,
    current_portfolio: Portfolio | None = None,
) -> tuple[Portfolio, SyncResult]:
    """Convenience function to sync portfolio.

    Args:
        broker: Broker for position queries
        current_portfolio: Current portfolio state

    Returns:
        Tuple of (synced Portfolio, SyncResult)
    """
    query = SyncPortfolioQuery(broker)
    return await query.execute(current_portfolio)

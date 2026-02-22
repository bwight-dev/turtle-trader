"""Paper broker implementation for simulated trading.

The PaperBroker simulates order execution without connecting to a real broker.
Useful for:
- Unit testing
- Strategy backtesting
- Development without TWS running
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from src.domain.interfaces.broker import (
    Broker,
    BrokerPosition,
    InsufficientFundsError,
    OpenOrder,
    OrderRejectedError,
    PositionNotFoundError,
)
from src.domain.models.enums import Direction
from src.domain.models.order import BracketOrder, OrderFill, StopModification


@dataclass
class SimulatedPosition:
    """Internal position tracking for paper broker."""

    symbol: str
    quantity: int  # Positive = long, negative = short
    average_cost: Decimal
    stop_price: Decimal | None = None
    stop_order_id: str | None = None
    realized_pnl: Decimal = Decimal("0")

    def to_broker_position(self, current_price: Decimal) -> BrokerPosition:
        """Convert to BrokerPosition for external use."""
        market_value = current_price * abs(self.quantity)
        cost_basis = self.average_cost * abs(self.quantity)

        if self.quantity > 0:  # Long
            unrealized_pnl = market_value - cost_basis
        else:  # Short
            unrealized_pnl = cost_basis - market_value

        return BrokerPosition(
            symbol=self.symbol,
            quantity=self.quantity,
            average_cost=self.average_cost,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=self.realized_pnl,
        )


@dataclass
class PaperBrokerConfig:
    """Configuration for paper broker simulation."""

    initial_equity: Decimal = Decimal("100000")
    commission_per_contract: Decimal = Decimal("2.25")  # Typical futures commission
    slippage_ticks: int = 1  # Simulate 1 tick slippage on market orders
    tick_size: Decimal = Decimal("0.10")  # Default tick size


class PaperBroker(Broker):
    """Simulated broker for testing and development.

    Features:
    - Tracks positions and orders in memory
    - Simulates fills with configurable slippage
    - Applies realistic commissions
    - Enforces buying power limits
    """

    def __init__(
        self,
        config: PaperBrokerConfig | None = None,
        prices: dict[str, Decimal] | None = None,
    ):
        """Initialize paper broker.

        Args:
            config: Broker configuration (uses defaults if None)
            prices: Initial price dictionary for simulating fills
        """
        self.config = config or PaperBrokerConfig()
        self._connected = False
        self._equity = self.config.initial_equity
        self._positions: dict[str, SimulatedPosition] = {}
        self._open_orders: dict[str, OpenOrder] = {}  # order_id -> OpenOrder
        self._prices: dict[str, Decimal] = prices or {}
        self._order_history: list[OrderFill] = []

    # ==========================================================================
    # Connection Management
    # ==========================================================================

    @property
    def is_connected(self) -> bool:
        """Check if broker is connected (always true for paper)."""
        return self._connected

    @property
    def broker_name(self) -> str:
        """Return broker name."""
        return "paper"

    async def connect(self) -> bool:
        """Connect to paper broker (always succeeds)."""
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """Disconnect from paper broker."""
        self._connected = False

    # ==========================================================================
    # Price Management (for simulation)
    # ==========================================================================

    def set_price(self, symbol: str, price: Decimal) -> None:
        """Set the current price for a symbol.

        Used by tests to control fill prices.
        """
        self._prices[symbol] = price

    def get_price(self, symbol: str) -> Decimal:
        """Get current price for a symbol."""
        if symbol not in self._prices:
            raise ValueError(f"No price set for {symbol}")
        return self._prices[symbol]

    # ==========================================================================
    # Order Execution
    # ==========================================================================

    async def place_bracket_order(self, order: BracketOrder) -> OrderFill:
        """Place a bracket order with entry and stop-loss.

        Simulates immediate fill at current price plus slippage.
        Creates a stop order that will be tracked.
        """
        # Get fill price with slippage
        base_price = order.entry_price or self._prices.get(order.symbol)
        if base_price is None:
            raise OrderRejectedError(f"No price available for {order.symbol}", order)

        fill_price = self._apply_slippage(base_price, order.direction, is_entry=True)

        # Calculate commission
        commission = self.config.commission_per_contract * order.quantity

        # Check buying power
        order_cost = fill_price * order.quantity + commission
        if order_cost > self._equity:
            raise InsufficientFundsError(
                f"Order cost {order_cost} exceeds equity {self._equity}"
            )

        # Create or update position
        await self._update_position(
            symbol=order.symbol,
            quantity=order.quantity if order.is_long else -order.quantity,
            fill_price=fill_price,
            stop_price=order.stop_price,
        )

        # Deduct commission from equity
        self._equity -= commission

        # Create fill record
        fill = OrderFill(
            order_id=order.id,
            symbol=order.symbol,
            direction=order.direction,
            quantity=order.quantity,
            fill_price=fill_price,
            commission=commission,
            broker_order_id=str(uuid4())[:8],
        )

        self._order_history.append(fill)
        return fill

    async def place_market_order(
        self,
        symbol: str,
        direction: Direction,
        quantity: int,
    ) -> OrderFill:
        """Place a simple market order."""
        base_price = self._prices.get(symbol)
        if base_price is None:
            raise OrderRejectedError(f"No price available for {symbol}")

        fill_price = self._apply_slippage(base_price, direction, is_entry=True)
        commission = self.config.commission_per_contract * quantity

        # Update position
        qty = quantity if direction == Direction.LONG else -quantity
        await self._update_position(symbol, qty, fill_price, stop_price=None)

        self._equity -= commission

        fill = OrderFill(
            order_id=uuid4(),
            symbol=symbol,
            direction=direction,
            quantity=quantity,
            fill_price=fill_price,
            commission=commission,
            broker_order_id=str(uuid4())[:8],
        )

        self._order_history.append(fill)
        return fill

    async def close_position(
        self,
        symbol: str,
        quantity: int | None = None,
    ) -> OrderFill:
        """Close an existing position."""
        if symbol not in self._positions:
            raise PositionNotFoundError(symbol)

        pos = self._positions[symbol]
        close_qty = quantity or abs(pos.quantity)

        # Determine exit direction (opposite of position)
        exit_direction = Direction.SHORT if pos.quantity > 0 else Direction.LONG

        base_price = self._prices.get(symbol)
        if base_price is None:
            raise OrderRejectedError(f"No price available for {symbol}")

        fill_price = self._apply_slippage(base_price, exit_direction, is_entry=False)
        commission = self.config.commission_per_contract * close_qty

        # Calculate P&L
        if pos.quantity > 0:  # Long position
            pnl = (fill_price - pos.average_cost) * close_qty
        else:  # Short position
            pnl = (pos.average_cost - fill_price) * close_qty

        # Update position
        pos.realized_pnl += pnl
        if close_qty >= abs(pos.quantity):
            # Full close - remove position and stop
            if pos.stop_order_id and pos.stop_order_id in self._open_orders:
                del self._open_orders[pos.stop_order_id]
            del self._positions[symbol]
            self._equity += pnl
        else:
            # Partial close
            if pos.quantity > 0:
                pos.quantity -= close_qty
            else:
                pos.quantity += close_qty
            self._equity += pnl

        self._equity -= commission

        fill = OrderFill(
            order_id=uuid4(),
            symbol=symbol,
            direction=exit_direction,
            quantity=close_qty,
            fill_price=fill_price,
            commission=commission,
            broker_order_id=str(uuid4())[:8],
        )

        self._order_history.append(fill)
        return fill

    # ==========================================================================
    # Stop Management
    # ==========================================================================

    async def modify_stop(
        self,
        symbol: str,
        new_stop: Decimal,
        quantity: int | None = None,
    ) -> StopModification:
        """Modify the stop price for a position."""
        if symbol not in self._positions:
            raise PositionNotFoundError(symbol)

        pos = self._positions[symbol]
        old_stop = pos.stop_price or Decimal("0")

        # Update stop price
        pos.stop_price = new_stop

        # Update stop order if exists
        if pos.stop_order_id and pos.stop_order_id in self._open_orders:
            order = self._open_orders[pos.stop_order_id]
            # Replace with updated order
            self._open_orders[pos.stop_order_id] = OpenOrder(
                order_id=order.order_id,
                symbol=order.symbol,
                direction=order.direction,
                quantity=quantity or order.quantity,
                order_type="STP",
                stop_price=new_stop,
                status="Submitted",
            )

        return StopModification(
            symbol=symbol,
            old_stop=old_stop,
            new_stop=new_stop,
            reason="Stop modified via paper broker",
            affected_units=1,
        )

    async def cancel_stop(self, symbol: str) -> bool:
        """Cancel the stop order for a position."""
        if symbol not in self._positions:
            return False

        pos = self._positions[symbol]
        if pos.stop_order_id and pos.stop_order_id in self._open_orders:
            del self._open_orders[pos.stop_order_id]
            pos.stop_order_id = None
            pos.stop_price = None
            return True

        return False

    # ==========================================================================
    # Position & Order Queries
    # ==========================================================================

    async def get_positions(self) -> list[BrokerPosition]:
        """Get all current positions."""
        positions = []
        for symbol, pos in self._positions.items():
            price = self._prices.get(symbol, pos.average_cost)
            positions.append(pos.to_broker_position(price))
        return positions

    async def get_position(self, symbol: str) -> BrokerPosition | None:
        """Get position for a specific symbol."""
        if symbol not in self._positions:
            return None
        pos = self._positions[symbol]
        price = self._prices.get(symbol, pos.average_cost)
        return pos.to_broker_position(price)

    async def get_open_orders(self, symbol: str | None = None) -> list[OpenOrder]:
        """Get open orders, optionally filtered by symbol."""
        if symbol is None:
            return list(self._open_orders.values())
        return [o for o in self._open_orders.values() if o.symbol == symbol]

    # ==========================================================================
    # Account Information
    # ==========================================================================

    async def get_account_value(self) -> Decimal:
        """Get current account equity."""
        # Add unrealized P&L to equity
        total = self._equity
        for symbol, pos in self._positions.items():
            price = self._prices.get(symbol, pos.average_cost)
            broker_pos = pos.to_broker_position(price)
            total += broker_pos.unrealized_pnl
        return total

    async def get_buying_power(self) -> Decimal:
        """Get available buying power."""
        # For simplicity, use equity minus margin used
        return self._equity

    # ==========================================================================
    # Internal Helpers
    # ==========================================================================

    def _apply_slippage(
        self, price: Decimal, direction: Direction, is_entry: bool
    ) -> Decimal:
        """Apply slippage to a price based on direction.

        Entries get worse fills, exits get worse fills too.
        """
        slippage = self.config.tick_size * self.config.slippage_ticks

        if is_entry:
            # Buying costs more, selling gets less
            if direction == Direction.LONG:
                return price + slippage
            return price - slippage
        else:
            # Exits: selling gets less, covering costs more
            if direction == Direction.LONG:  # Selling to close long
                return price - slippage
            return price + slippage  # Buying to close short

    async def _update_position(
        self,
        symbol: str,
        quantity: int,
        fill_price: Decimal,
        stop_price: Decimal | None,
    ) -> None:
        """Update or create a position after a fill."""
        if symbol in self._positions:
            pos = self._positions[symbol]
            old_qty = pos.quantity
            new_qty = old_qty + quantity

            if new_qty == 0:
                # Position closed
                del self._positions[symbol]
                # Clean up stop order
                if pos.stop_order_id and pos.stop_order_id in self._open_orders:
                    del self._open_orders[pos.stop_order_id]
            elif (old_qty > 0 and quantity > 0) or (old_qty < 0 and quantity < 0):
                # Adding to position - recalculate average cost
                total_cost = pos.average_cost * abs(old_qty) + fill_price * abs(quantity)
                pos.quantity = new_qty
                pos.average_cost = total_cost / abs(new_qty)
                if stop_price:
                    pos.stop_price = stop_price
                    # Remove old stop order and create new one
                    if pos.stop_order_id and pos.stop_order_id in self._open_orders:
                        del self._open_orders[pos.stop_order_id]
                    self._create_stop_order(pos)
            else:
                # Reducing position
                pos.quantity = new_qty
                # Keep existing stop if still have position
        else:
            # New position
            pos = SimulatedPosition(
                symbol=symbol,
                quantity=quantity,
                average_cost=fill_price,
                stop_price=stop_price,
            )
            self._positions[symbol] = pos
            if stop_price:
                self._create_stop_order(pos)

    def _create_stop_order(self, pos: SimulatedPosition) -> None:
        """Create a stop order for a position."""
        if pos.stop_price is None:
            return

        order_id = str(uuid4())[:8]
        pos.stop_order_id = order_id

        # Stop direction is opposite of position
        stop_direction = Direction.SHORT if pos.quantity > 0 else Direction.LONG

        self._open_orders[order_id] = OpenOrder(
            order_id=order_id,
            symbol=pos.symbol,
            direction=stop_direction,
            quantity=abs(pos.quantity),
            order_type="STP",
            stop_price=pos.stop_price,
            status="Submitted",
        )

    # ==========================================================================
    # Testing Helpers
    # ==========================================================================

    def reset(self) -> None:
        """Reset broker to initial state (for testing)."""
        self._equity = self.config.initial_equity
        self._positions.clear()
        self._open_orders.clear()
        self._order_history.clear()

    def set_account_value(self, equity: Decimal) -> None:
        """Set the account equity directly (for testing)."""
        self._equity = equity

    def get_order_history(self) -> list[OrderFill]:
        """Get all order fills (for testing)."""
        return list(self._order_history)

    def inject_position(
        self,
        symbol: str,
        quantity: int,
        average_cost: Decimal,
        stop_price: Decimal | None = None,
    ) -> None:
        """Inject a position directly (for testing).

        Useful for setting up test scenarios without going through
        order execution.
        """
        pos = SimulatedPosition(
            symbol=symbol,
            quantity=quantity,
            average_cost=average_cost,
            stop_price=stop_price,
        )
        self._positions[symbol] = pos
        if stop_price:
            self._create_stop_order(pos)

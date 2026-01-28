"""Broker interface (port) - defines how to execute trades."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.domain.models.enums import Direction
from src.domain.models.order import BracketOrder, OrderFill, StopModification


@dataclass(frozen=True)
class BrokerPosition:
    """A position as reported by the broker.

    This is the broker's view of a position, which may differ from
    our internal Position model (e.g., broker doesn't track pyramid levels).
    """

    symbol: str
    quantity: int  # Positive for long, negative for short
    average_cost: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal = Decimal("0")

    @property
    def direction(self) -> Direction:
        """Infer direction from quantity."""
        return Direction.LONG if self.quantity > 0 else Direction.SHORT

    @property
    def abs_quantity(self) -> int:
        """Absolute quantity (always positive)."""
        return abs(self.quantity)


@dataclass(frozen=True)
class OpenOrder:
    """An open order at the broker (typically a stop order)."""

    order_id: str
    symbol: str
    direction: Direction
    quantity: int
    order_type: str  # "STP", "LMT", "MKT"
    stop_price: Decimal | None = None
    limit_price: Decimal | None = None
    status: str = "Submitted"
    parent_id: str | None = None  # For bracket orders


class Broker(ABC):
    """Abstract interface for trade execution.

    This is a port in Clean Architecture - defines what the domain needs
    for executing trades without specifying broker implementation details.

    Implementations include:
    - PaperBroker: Simulated execution for testing
    - IBKRBroker: Real execution via Interactive Brokers
    """

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if broker connection is active."""
        ...

    @property
    @abstractmethod
    def broker_name(self) -> str:
        """Return the broker name (e.g., 'paper', 'ibkr')."""
        ...

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the broker.

        Returns:
            True if connection successful, False otherwise.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the broker."""
        ...

    # ==========================================================================
    # Order Execution
    # ==========================================================================

    @abstractmethod
    async def place_bracket_order(self, order: BracketOrder) -> OrderFill:
        """Place a bracket order (entry + stop-loss).

        This is the primary order type for Turtle Trading:
        - Entry order (market or limit)
        - Attached stop-loss at 2N

        Args:
            order: The bracket order to place

        Returns:
            OrderFill with execution details

        Raises:
            BrokerError: If order placement fails
        """
        ...

    @abstractmethod
    async def place_market_order(
        self,
        symbol: str,
        direction: Direction,
        quantity: int,
    ) -> OrderFill:
        """Place a simple market order.

        Used for exits (stop-outs, breakout exits) where we just
        want to get out at market.

        Args:
            symbol: The symbol to trade
            direction: BUY or SELL
            quantity: Number of contracts

        Returns:
            OrderFill with execution details
        """
        ...

    @abstractmethod
    async def close_position(
        self,
        symbol: str,
        quantity: int | None = None,
    ) -> OrderFill:
        """Close an existing position.

        Args:
            symbol: Symbol to close
            quantity: Number of contracts to close (None = close all)

        Returns:
            OrderFill with execution details
        """
        ...

    # ==========================================================================
    # Stop Management
    # ==========================================================================

    @abstractmethod
    async def modify_stop(
        self,
        symbol: str,
        new_stop: Decimal,
        quantity: int | None = None,
    ) -> StopModification:
        """Modify the stop price for a position.

        Rule 12: When pyramiding, move ALL stops to 2N below newest entry.

        Args:
            symbol: Symbol to modify stop for
            new_stop: New stop price
            quantity: Number of contracts (None = all contracts)

        Returns:
            StopModification with old and new stop prices
        """
        ...

    @abstractmethod
    async def cancel_stop(self, symbol: str) -> bool:
        """Cancel the stop order for a position.

        Args:
            symbol: Symbol to cancel stop for

        Returns:
            True if cancellation successful
        """
        ...

    # ==========================================================================
    # Position & Order Queries
    # ==========================================================================

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        """Get all current positions from the broker.

        Returns:
            List of BrokerPosition objects
        """
        ...

    @abstractmethod
    async def get_position(self, symbol: str) -> BrokerPosition | None:
        """Get position for a specific symbol.

        Args:
            symbol: Symbol to look up

        Returns:
            BrokerPosition or None if no position
        """
        ...

    @abstractmethod
    async def get_open_orders(self, symbol: str | None = None) -> list[OpenOrder]:
        """Get open orders, optionally filtered by symbol.

        Args:
            symbol: Filter to this symbol (None = all orders)

        Returns:
            List of OpenOrder objects
        """
        ...

    # ==========================================================================
    # Account Information
    # ==========================================================================

    @abstractmethod
    async def get_account_value(self) -> Decimal:
        """Get current account equity/value.

        Returns:
            Account equity in dollars
        """
        ...

    @abstractmethod
    async def get_buying_power(self) -> Decimal:
        """Get available buying power.

        Returns:
            Available buying power in dollars
        """
        ...


class BrokerError(Exception):
    """Base exception for broker-related errors."""

    pass


class OrderRejectedError(BrokerError):
    """Order was rejected by the broker."""

    def __init__(self, reason: str, order: BracketOrder | None = None):
        self.reason = reason
        self.order = order
        super().__init__(f"Order rejected: {reason}")


class InsufficientFundsError(BrokerError):
    """Insufficient funds/buying power for the order."""

    pass


class PositionNotFoundError(BrokerError):
    """Position not found for the requested operation."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        super().__init__(f"No position found for {symbol}")


class ConnectionError(BrokerError):
    """Failed to connect to the broker."""

    pass

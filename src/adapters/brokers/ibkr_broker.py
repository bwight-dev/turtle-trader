"""Interactive Brokers broker adapter using ib_insync.

Implements the Broker interface for real order execution via IBKR TWS/Gateway.
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from ib_insync import IB, Contract, Future, LimitOrder, MarketOrder, Order, StopOrder

from src.domain.interfaces.broker import (
    Broker,
    BrokerError,
    BrokerPosition,
    ConnectionError,
    InsufficientFundsError,
    OpenOrder,
    OrderRejectedError,
    PositionNotFoundError,
)
from src.domain.models.enums import Direction
from src.domain.models.order import BracketOrder, OrderFill, StopModification
from src.infrastructure.config import get_settings


class IBKRBroker(Broker):
    """IBKR broker implementation using ib_insync.

    This adapter handles real order execution via TWS or Gateway.
    It implements the Broker interface from the domain layer.

    Features:
    - Bracket orders with parent/child linking
    - Stop order management
    - Position tracking
    - Account queries
    """

    # Symbol mapping: internal symbol -> (exchange, local_symbol_prefix)
    SYMBOL_MAP = {
        "/MGC": ("COMEX", "MGC"),
        "/SIL": ("COMEX", "SIL"),
        "/HG": ("COMEX", "HG"),
        "/M2K": ("CME", "M2K"),
        "/MES": ("CME", "MES"),
        "/MNQ": ("CME", "MNQ"),
        "/MYM": ("CME", "MYM"),
        "/MCL": ("NYMEX", "MCL"),
        "/MNG": ("NYMEX", "MNG"),
    }

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        client_id: int | None = None,
        paper: bool = True,
    ):
        """Initialize IBKR broker.

        Args:
            host: TWS/Gateway host
            port: TWS/Gateway port (7497 paper, 7496 live)
            client_id: Client ID for this connection
            paper: If True, use paper trading port by default
        """
        settings = get_settings()
        self._host = host or settings.ibkr_host

        # Determine port: explicit override, or based on paper/live
        if port is not None:
            self._port = port
        elif paper:
            self._port = 7497  # Paper trading
        else:
            self._port = 7496  # Live trading

        self._client_id = client_id or settings.ibkr_client_id
        self._ib = IB()
        self._connected = False
        self._account_id = settings.ibkr_account_id
        self._contract_cache: dict[str, Contract] = {}

        # Track our stop orders by symbol
        self._stop_orders: dict[str, int] = {}  # symbol -> order_id

    # ==========================================================================
    # Connection Management
    # ==========================================================================

    @property
    def is_connected(self) -> bool:
        """Check if connected to TWS/Gateway."""
        return self._connected and self._ib.isConnected()

    @property
    def broker_name(self) -> str:
        """Return broker name."""
        return "ibkr"

    async def connect(self) -> bool:
        """Connect to TWS/Gateway."""
        if self.is_connected:
            return True

        try:
            await self._ib.connectAsync(
                host=self._host,
                port=self._port,
                clientId=self._client_id,
                timeout=get_settings().ibkr_connection_timeout,
            )
            self._connected = True

            # Get account ID if not set
            if not self._account_id:
                accounts = self._ib.managedAccounts()
                if accounts:
                    self._account_id = accounts[0]

            return True
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to connect to IBKR: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from TWS/Gateway."""
        if self._ib.isConnected():
            self._ib.disconnect()
        self._connected = False
        self._contract_cache.clear()
        self._stop_orders.clear()

    # ==========================================================================
    # Contract Resolution
    # ==========================================================================

    async def _get_contract(self, symbol: str) -> Contract:
        """Get a qualified contract for the symbol.

        Args:
            symbol: Internal symbol (e.g., '/MGC')

        Returns:
            Qualified ib_insync Contract
        """
        if symbol in self._contract_cache:
            return self._contract_cache[symbol]

        if symbol not in self.SYMBOL_MAP:
            raise ValueError(f"Unknown symbol: {symbol}")

        exchange, local_prefix = self.SYMBOL_MAP[symbol]

        # Create futures contract
        contract = Future(
            symbol=local_prefix,
            exchange=exchange,
            currency="USD",
        )

        # Qualify it to get the front month
        contracts = await self._ib.qualifyContractsAsync(contract)
        if not contracts:
            details = await self._ib.reqContractDetailsAsync(contract)
            if not details:
                raise ValueError(f"No contracts found for {symbol}")
            details.sort(key=lambda d: d.contract.lastTradeDateOrContractMonth)
            contract = details[0].contract
        else:
            contract = contracts[0]

        self._contract_cache[symbol] = contract
        return contract

    # ==========================================================================
    # Order Execution
    # ==========================================================================

    async def place_bracket_order(self, order: BracketOrder) -> OrderFill:
        """Place a bracket order with entry and stop-loss.

        Uses IBKR's bracket order functionality to link orders.
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to IBKR")

        contract = await self._get_contract(order.symbol)

        # Determine action
        action = "BUY" if order.is_long else "SELL"
        opposite_action = "SELL" if order.is_long else "BUY"

        # Create parent order (entry)
        if order.entry_price:
            parent = LimitOrder(
                action=action,
                totalQuantity=order.quantity,
                lmtPrice=float(order.entry_price),
                transmit=False,  # Don't transmit until child is ready
            )
        else:
            parent = MarketOrder(
                action=action,
                totalQuantity=order.quantity,
                transmit=False,
            )

        # Place parent order to get order ID
        parent_trade = self._ib.placeOrder(contract, parent)
        parent_id = parent_trade.order.orderId

        # Create stop order (child)
        stop = StopOrder(
            action=opposite_action,
            totalQuantity=order.quantity,
            stopPrice=float(order.stop_price),
            parentId=parent_id,
            transmit=True,  # Transmit both now
        )

        # Place stop order
        stop_trade = self._ib.placeOrder(contract, stop)

        # Transmit the parent order
        parent.transmit = True
        self._ib.placeOrder(contract, parent)

        # Wait for fill
        try:
            await asyncio.wait_for(
                self._wait_for_fill(parent_trade),
                timeout=get_settings().ibkr_request_timeout,
            )
        except asyncio.TimeoutError:
            raise OrderRejectedError("Order fill timeout", order)

        if parent_trade.orderStatus.status == "Filled":
            # Track stop order
            self._stop_orders[order.symbol] = stop_trade.order.orderId

            return OrderFill(
                order_id=order.id,
                symbol=order.symbol,
                direction=order.direction,
                quantity=int(parent_trade.orderStatus.filled),
                fill_price=Decimal(str(parent_trade.orderStatus.avgFillPrice)),
                commission=Decimal(str(parent_trade.orderStatus.commission or 0)),
                broker_order_id=str(parent_id),
            )
        else:
            raise OrderRejectedError(
                f"Order not filled: {parent_trade.orderStatus.status}", order
            )

    async def place_market_order(
        self,
        symbol: str,
        direction: Direction,
        quantity: int,
    ) -> OrderFill:
        """Place a simple market order."""
        if not self.is_connected:
            raise ConnectionError("Not connected to IBKR")

        contract = await self._get_contract(symbol)
        action = "BUY" if direction == Direction.LONG else "SELL"

        order = MarketOrder(action=action, totalQuantity=quantity)
        trade = self._ib.placeOrder(contract, order)

        try:
            await asyncio.wait_for(
                self._wait_for_fill(trade),
                timeout=get_settings().ibkr_request_timeout,
            )
        except asyncio.TimeoutError:
            raise BrokerError(f"Market order fill timeout for {symbol}")

        if trade.orderStatus.status == "Filled":
            return OrderFill(
                order_id=uuid4(),
                symbol=symbol,
                direction=direction,
                quantity=int(trade.orderStatus.filled),
                fill_price=Decimal(str(trade.orderStatus.avgFillPrice)),
                commission=Decimal(str(trade.orderStatus.commission or 0)),
                broker_order_id=str(trade.order.orderId),
            )
        else:
            raise BrokerError(f"Market order not filled: {trade.orderStatus.status}")

    async def close_position(
        self,
        symbol: str,
        quantity: int | None = None,
    ) -> OrderFill:
        """Close an existing position."""
        if not self.is_connected:
            raise ConnectionError("Not connected to IBKR")

        # Get current position
        position = await self.get_position(symbol)
        if position is None:
            raise PositionNotFoundError(symbol)

        close_qty = quantity or position.abs_quantity

        # Close direction is opposite of position
        close_direction = Direction.SHORT if position.quantity > 0 else Direction.LONG

        # Cancel any existing stop order for this position
        if symbol in self._stop_orders:
            try:
                await self.cancel_stop(symbol)
            except Exception:
                pass  # Ignore cancel errors

        return await self.place_market_order(symbol, close_direction, close_qty)

    async def _wait_for_fill(self, trade) -> None:
        """Wait for a trade to be filled or cancelled."""
        while trade.orderStatus.status not in ("Filled", "Cancelled", "Inactive"):
            await asyncio.sleep(0.1)
            self._ib.sleep(0)  # Process events

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
        if not self.is_connected:
            raise ConnectionError("Not connected to IBKR")

        position = await self.get_position(symbol)
        if position is None:
            raise PositionNotFoundError(symbol)

        # Get existing stop order
        if symbol not in self._stop_orders:
            raise BrokerError(f"No stop order tracked for {symbol}")

        stop_order_id = self._stop_orders[symbol]
        contract = await self._get_contract(symbol)

        # Get current order to find old stop price
        open_orders = self._ib.openOrders()
        old_stop = Decimal("0")
        existing_order = None

        for order in open_orders:
            if order.orderId == stop_order_id:
                old_stop = Decimal(str(order.auxPrice))
                existing_order = order
                break

        if existing_order is None:
            raise BrokerError(f"Stop order {stop_order_id} not found")

        # Modify the stop order
        existing_order.auxPrice = float(new_stop)
        if quantity:
            existing_order.totalQuantity = quantity

        self._ib.placeOrder(contract, existing_order)

        return StopModification(
            symbol=symbol,
            old_stop=old_stop,
            new_stop=new_stop,
            reason="Stop modified via IBKR",
            affected_units=1,
        )

    async def cancel_stop(self, symbol: str) -> bool:
        """Cancel the stop order for a position."""
        if not self.is_connected:
            return False

        if symbol not in self._stop_orders:
            return False

        stop_order_id = self._stop_orders[symbol]

        # Find and cancel the order
        for trade in self._ib.openTrades():
            if trade.order.orderId == stop_order_id:
                self._ib.cancelOrder(trade.order)
                del self._stop_orders[symbol]
                return True

        return False

    # ==========================================================================
    # Position & Order Queries
    # ==========================================================================

    async def get_positions(self) -> list[BrokerPosition]:
        """Get all current positions from IBKR."""
        if not self.is_connected:
            raise ConnectionError("Not connected to IBKR")

        positions = self._ib.positions()
        result = []

        for pos in positions:
            if pos.position != 0:
                symbol = self._to_internal_symbol(pos.contract)
                if symbol:
                    result.append(
                        BrokerPosition(
                            symbol=symbol,
                            quantity=int(pos.position),
                            average_cost=Decimal(str(pos.avgCost)),
                            market_value=Decimal(str(pos.marketValue or 0)),
                            unrealized_pnl=Decimal(str(pos.unrealizedPNL or 0)),
                            realized_pnl=Decimal(str(pos.realizedPNL or 0)),
                        )
                    )

        return result

    async def get_position(self, symbol: str) -> BrokerPosition | None:
        """Get position for a specific symbol."""
        positions = await self.get_positions()
        for pos in positions:
            if pos.symbol == symbol:
                return pos
        return None

    async def get_open_orders(self, symbol: str | None = None) -> list[OpenOrder]:
        """Get open orders from IBKR."""
        if not self.is_connected:
            raise ConnectionError("Not connected to IBKR")

        orders = self._ib.openOrders()
        result = []

        for order in orders:
            order_symbol = self._to_internal_symbol(order.contract)
            if symbol and order_symbol != symbol:
                continue

            direction = Direction.LONG if order.action == "BUY" else Direction.SHORT

            # Determine order type
            order_type = "MKT"
            stop_price = None
            limit_price = None

            if hasattr(order, "orderType"):
                if order.orderType == "STP":
                    order_type = "STP"
                    stop_price = Decimal(str(order.auxPrice)) if order.auxPrice else None
                elif order.orderType == "LMT":
                    order_type = "LMT"
                    limit_price = Decimal(str(order.lmtPrice)) if order.lmtPrice else None

            result.append(
                OpenOrder(
                    order_id=str(order.orderId),
                    symbol=order_symbol or "",
                    direction=direction,
                    quantity=int(order.totalQuantity),
                    order_type=order_type,
                    stop_price=stop_price,
                    limit_price=limit_price,
                    status=order.status if hasattr(order, "status") else "Unknown",
                    parent_id=str(order.parentId) if order.parentId else None,
                )
            )

        return result

    # ==========================================================================
    # Account Information
    # ==========================================================================

    async def get_account_value(self) -> Decimal:
        """Get current account equity."""
        if not self.is_connected:
            raise ConnectionError("Not connected to IBKR")

        summary = await self._ib.accountSummaryAsync()

        for item in summary:
            if item.tag == "NetLiquidation" and item.currency == "USD":
                return Decimal(str(item.value))

        raise BrokerError("Could not get account value")

    async def get_buying_power(self) -> Decimal:
        """Get available buying power."""
        if not self.is_connected:
            raise ConnectionError("Not connected to IBKR")

        summary = await self._ib.accountSummaryAsync()

        for item in summary:
            if item.tag == "AvailableFunds" and item.currency == "USD":
                return Decimal(str(item.value))

        raise BrokerError("Could not get buying power")

    # ==========================================================================
    # Helpers
    # ==========================================================================

    def _to_internal_symbol(self, contract: Contract) -> str | None:
        """Convert IBKR contract to internal symbol."""
        if not contract:
            return None

        # Reverse lookup in symbol map
        for internal, (exchange, prefix) in self.SYMBOL_MAP.items():
            if contract.symbol == prefix:
                return internal

        return None

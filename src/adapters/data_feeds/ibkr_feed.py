"""Interactive Brokers data feed adapter using ib_insync."""

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal

from ib_insync import IB, Contract, Future, util

from src.domain.interfaces.data_feed import DataFeed
from src.domain.models.market import Bar
from src.infrastructure.config import get_settings


class IBKRDataFeed(DataFeed):
    """IBKR data feed implementation using ib_insync.

    This is an adapter in Clean Architecture - implements the DataFeed port
    using Interactive Brokers TWS/Gateway API.
    """

    # Symbol mapping: internal symbol -> (exchange, local_symbol_prefix)
    SYMBOL_MAP = {
        "/MGC": ("COMEX", "MGC"),
        "/SIL": ("COMEX", "SIL"),
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
    ):
        """Initialize IBKR feed with connection settings.

        Args:
            host: TWS/Gateway host (defaults to settings)
            port: TWS/Gateway port (defaults to settings)
            client_id: Client ID for this connection (defaults to settings)
        """
        settings = get_settings()
        self._host = host or settings.ibkr_host
        self._port = port or settings.ibkr_port
        self._client_id = client_id or settings.ibkr_client_id
        self._ib = IB()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to TWS/Gateway."""
        return self._connected and self._ib.isConnected()

    @property
    def source_name(self) -> str:
        """Return data source name."""
        return "ibkr"

    async def connect(self) -> bool:
        """Connect to TWS/Gateway.

        Returns:
            True if connection successful.
        """
        if self.is_connected:
            return True

        try:
            # ib_insync uses nest_asyncio internally
            await self._ib.connectAsync(
                host=self._host,
                port=self._port,
                clientId=self._client_id,
                timeout=get_settings().ibkr_connection_timeout,
            )
            self._connected = True
            return True
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to connect to IBKR: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from TWS/Gateway."""
        if self._ib.isConnected():
            self._ib.disconnect()
        self._connected = False

    async def _get_front_month_contract(self, symbol: str) -> Contract:
        """Get the front month futures contract for internal symbol.

        Args:
            symbol: Internal symbol (e.g., '/MGC')

        Returns:
            Qualified ib_insync Contract object for front month
        """
        if symbol not in self.SYMBOL_MAP:
            raise ValueError(f"Unknown symbol: {symbol}")

        exchange, local_prefix = self.SYMBOL_MAP[symbol]

        # Create an unqualified futures contract
        contract = Future(
            symbol=local_prefix,
            exchange=exchange,
            currency="USD",
        )

        # Get all available contracts
        contracts = await self._ib.qualifyContractsAsync(contract)
        if not contracts:
            # Try requesting contract details to find available expirations
            details = await self._ib.reqContractDetailsAsync(contract)
            if not details:
                raise ValueError(f"No contracts found for {symbol}")

            # Sort by expiration and pick the front month
            details.sort(key=lambda d: d.contract.lastTradeDateOrContractMonth)
            return details[0].contract

        # If we got multiple contracts, pick the first one (front month)
        return contracts[0]

    async def get_bars(
        self,
        symbol: str,
        days: int = 20,
        end_date: date | None = None,
    ) -> list[Bar]:
        """Fetch historical OHLCV bars from IBKR.

        Args:
            symbol: Internal symbol (e.g., '/MGC')
            days: Number of days of history
            end_date: End date (defaults to today)

        Returns:
            List of Bar objects, oldest first.
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to IBKR")

        contract = await self._get_front_month_contract(symbol)

        # Calculate end datetime
        end_dt = datetime.combine(end_date or date.today(), datetime.max.time())

        # Request historical data
        bars = await self._ib.reqHistoricalDataAsync(
            contract,
            endDateTime=end_dt,
            durationStr=f"{days} D",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=get_settings().ibkr_use_rth,
            formatDate=1,
        )

        # Convert to domain Bar objects
        result = []
        for bar in bars:
            result.append(
                Bar(
                    symbol=symbol,
                    date=bar.date.date() if isinstance(bar.date, datetime) else bar.date,
                    open=Decimal(str(bar.open)),
                    high=Decimal(str(bar.high)),
                    low=Decimal(str(bar.low)),
                    close=Decimal(str(bar.close)),
                    volume=int(bar.volume),
                )
            )

        return result

    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current/last price from IBKR.

        Args:
            symbol: Internal symbol

        Returns:
            Current price as Decimal.
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to IBKR")

        contract = await self._get_front_month_contract(symbol)

        # Request market data snapshot
        ticker = await self._ib.reqTickersAsync(contract)
        if not ticker:
            raise ValueError(f"No ticker data for {symbol}")

        # Use last price, or close if no last
        price = ticker[0].last or ticker[0].close
        if price is None or price <= 0:
            raise ValueError(f"Invalid price for {symbol}")

        return Decimal(str(price))

    async def get_account_summary(self) -> dict[str, Decimal]:
        """Get account summary from IBKR.

        Returns:
            Dict with account values like NetLiquidation, AvailableFunds, etc.
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to IBKR")

        # Request account summary
        summary = await self._ib.accountSummaryAsync()

        result = {}
        for item in summary:
            if item.currency == "USD" or item.currency == "":
                try:
                    # Try to convert to Decimal, skip if not numeric
                    value = str(item.value).strip()
                    if value and value not in ("", "N/A", "-"):
                        result[item.tag] = Decimal(value)
                except Exception:
                    # Skip non-numeric values silently
                    pass

        return result

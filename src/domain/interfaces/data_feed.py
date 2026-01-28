"""Data feed interface (port) - defines how to fetch market data."""

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.models.market import Bar


class DataFeed(ABC):
    """Abstract interface for market data feeds.

    This is a port in Clean Architecture - defines what the domain needs
    without specifying implementation details.
    """

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the feed is currently connected."""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the name of this data source (e.g., 'ibkr', 'yahoo')."""
        ...

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the data source.

        Returns:
            True if connection successful, False otherwise.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the data source."""
        ...

    @abstractmethod
    async def get_bars(
        self,
        symbol: str,
        days: int = 20,
        end_date: date | None = None,
    ) -> list["Bar"]:
        """Fetch historical OHLCV bars for a symbol.

        Args:
            symbol: The internal symbol (e.g., '/MGC')
            days: Number of days of history to fetch
            end_date: End date for the data (defaults to today)

        Returns:
            List of Bar objects, oldest first.
        """
        ...

    @abstractmethod
    async def get_current_price(self, symbol: str) -> Decimal:
        """Get the current/last price for a symbol.

        Args:
            symbol: The internal symbol (e.g., '/MGC')

        Returns:
            The current price as a Decimal.
        """
        ...

    @abstractmethod
    async def get_account_summary(self) -> dict[str, Decimal]:
        """Get account summary information.

        Returns:
            Dict with keys like 'NetLiquidation', 'AvailableFunds', etc.
        """
        ...

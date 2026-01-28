"""Repository interfaces (ports) for data persistence."""

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

from src.domain.models.market import DonchianChannel, NValue


class NValueRepository(ABC):
    """Repository interface for N value persistence.

    N values are persisted to support:
    - Incremental N calculation (using previous day's N)
    - Historical analysis
    - Continuity across bot restarts
    """

    @abstractmethod
    async def save_indicators(
        self,
        symbol: str,
        calc_date: date,
        n_value: NValue,
        donchian_10: DonchianChannel | None = None,
        donchian_20: DonchianChannel | None = None,
        donchian_55: DonchianChannel | None = None,
    ) -> None:
        """Save calculated indicators for a symbol.

        Args:
            symbol: The internal symbol (e.g., '/MGC')
            calc_date: The date these values were calculated for
            n_value: The N (ATR) value
            donchian_10: 10-day Donchian channel (S1 exit)
            donchian_20: 20-day Donchian channel (S1 entry/S2 exit)
            donchian_55: 55-day Donchian channel (S2 entry)
        """
        ...

    @abstractmethod
    async def get_latest_indicators(
        self,
        symbol: str,
    ) -> dict | None:
        """Get the most recent indicators for a symbol.

        Args:
            symbol: The internal symbol

        Returns:
            Dict with n_value, donchian_10, etc. or None if not found
        """
        ...

    @abstractmethod
    async def get_previous_n(
        self,
        symbol: str,
        before_date: date,
    ) -> Decimal | None:
        """Get the N value from the day before a given date.

        Used for incremental N calculation with Wilder's smoothing.

        Args:
            symbol: The internal symbol
            before_date: Get N from the day before this date

        Returns:
            Previous N value or None if not found
        """
        ...

    @abstractmethod
    async def get_n_history(
        self,
        symbol: str,
        days: int = 30,
    ) -> list[tuple[date, Decimal]]:
        """Get historical N values for a symbol.

        Args:
            symbol: The internal symbol
            days: Number of days of history

        Returns:
            List of (date, n_value) tuples, oldest first
        """
        ...


class TradeRepository(ABC):
    """Repository interface for trade audit records.

    Trades are persisted for:
    - S1 filter (was last S1 trade a winner?)
    - Performance tracking
    - Tax records
    """

    @abstractmethod
    async def save_trade(self, trade: "Trade") -> None:  # noqa: F821
        """Save a trade audit record."""
        ...

    @abstractmethod
    async def get_last_s1_trade(self, symbol: str) -> "Trade | None":  # noqa: F821
        """Get the most recent S1 trade for a symbol.

        Used for S1 filter: skip if last S1 was a winner.
        """
        ...

    @abstractmethod
    async def get_trades_by_symbol(
        self,
        symbol: str,
        limit: int = 100,
    ) -> list["Trade"]:  # noqa: F821
        """Get recent trades for a symbol."""
        ...

"""Composite data feed with automatic failover."""

from datetime import date
from decimal import Decimal

from src.adapters.data_feeds.ibkr_feed import IBKRDataFeed
from src.adapters.data_feeds.yahoo_feed import YahooDataFeed
from src.domain.interfaces.data_feed import DataFeed
from src.domain.models.market import Bar
from src.domain.services.validation import filter_valid_bars, validate_bars
from src.infrastructure.config import get_settings
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class CompositeDataFeed(DataFeed):
    """Composite data feed with automatic failover.

    Uses IBKR as primary source and Yahoo Finance as backup.
    Automatically falls back to Yahoo when:
    - IBKR connection fails
    - IBKR returns no data
    - IBKR data fails validation
    """

    def __init__(
        self,
        ibkr_feed: IBKRDataFeed | None = None,
        yahoo_feed: YahooDataFeed | None = None,
        enable_fallback: bool | None = None,
    ):
        """Initialize composite feed.

        Args:
            ibkr_feed: IBKR feed instance (created if not provided)
            yahoo_feed: Yahoo feed instance (created if not provided)
            enable_fallback: Whether to enable Yahoo fallback (defaults to settings)
        """
        settings = get_settings()

        self._ibkr = ibkr_feed or IBKRDataFeed()
        self._yahoo = yahoo_feed or YahooDataFeed()
        self._enable_fallback = (
            enable_fallback if enable_fallback is not None else settings.data_enable_fallback
        )

        self._last_source: str | None = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if at least one feed is connected."""
        return self._connected and (self._ibkr.is_connected or self._yahoo.is_connected)

    @property
    def source_name(self) -> str:
        """Return the name of the last used data source."""
        return self._last_source or "composite"

    @property
    def last_source(self) -> str | None:
        """Return the source used for the last data request."""
        return self._last_source

    async def connect(self) -> bool:
        """Connect to data sources.

        Attempts IBKR first, then Yahoo as fallback.

        Returns:
            True if at least one connection succeeds.
        """
        ibkr_connected = False
        yahoo_connected = False

        # Try IBKR first
        try:
            ibkr_connected = await self._ibkr.connect()
            if ibkr_connected:
                logger.info("Connected to IBKR (primary)")
        except Exception as e:
            logger.warning(f"IBKR connection failed: {e}")

        # Connect Yahoo as backup
        if self._enable_fallback:
            try:
                yahoo_connected = await self._yahoo.connect()
                if yahoo_connected:
                    logger.info("Connected to Yahoo (backup)")
            except Exception as e:
                logger.warning(f"Yahoo connection failed: {e}")

        self._connected = ibkr_connected or yahoo_connected
        return self._connected

    async def disconnect(self) -> None:
        """Disconnect from all data sources."""
        try:
            await self._ibkr.disconnect()
        except Exception:
            pass

        try:
            await self._yahoo.disconnect()
        except Exception:
            pass

        self._connected = False

    async def get_bars(
        self,
        symbol: str,
        days: int = 20,
        end_date: date | None = None,
    ) -> list[Bar]:
        """Fetch historical bars with automatic failover.

        Tries IBKR first, falls back to Yahoo on failure.

        Args:
            symbol: Internal symbol (e.g., '/MGC')
            days: Number of days of history
            end_date: End date (defaults to today)

        Returns:
            List of Bar objects, oldest first.

        Raises:
            ConnectionError: If no data source is available
            ValueError: If no valid data could be retrieved
        """
        if not self._connected:
            raise ConnectionError("Not connected to any data source")

        errors: list[str] = []

        # Try IBKR first
        if self._ibkr.is_connected:
            try:
                bars = await self._ibkr.get_bars(symbol, days, end_date)

                # Validate bars
                valid, validation_errors = validate_bars(bars)
                if valid and len(bars) > 0:
                    self._last_source = "ibkr"
                    logger.debug(f"Got {len(bars)} bars from IBKR for {symbol}")
                    return bars
                elif len(bars) == 0:
                    errors.append("IBKR returned no bars")
                else:
                    errors.append(f"IBKR validation failed: {validation_errors}")
                    # Try to use valid bars only
                    valid_bars = filter_valid_bars(bars)
                    if len(valid_bars) >= days * 0.8:  # Accept if 80%+ valid
                        self._last_source = "ibkr"
                        return valid_bars

            except Exception as e:
                errors.append(f"IBKR error: {e}")
                logger.warning(f"IBKR get_bars failed for {symbol}: {e}")

        # Fallback to Yahoo
        if self._enable_fallback and self._yahoo.is_connected:
            try:
                bars = await self._yahoo.get_bars(symbol, days, end_date)

                valid, validation_errors = validate_bars(bars)
                if valid and len(bars) > 0:
                    self._last_source = "yahoo"
                    logger.info(f"Got {len(bars)} bars from Yahoo (fallback) for {symbol}")
                    return bars
                elif len(bars) == 0:
                    errors.append("Yahoo returned no bars")
                else:
                    errors.append(f"Yahoo validation failed: {validation_errors}")
                    valid_bars = filter_valid_bars(bars)
                    if len(valid_bars) >= days * 0.5:  # Accept if 50%+ valid for backup
                        self._last_source = "yahoo"
                        return valid_bars

            except Exception as e:
                errors.append(f"Yahoo error: {e}")
                logger.warning(f"Yahoo get_bars failed for {symbol}: {e}")

        # All sources failed
        raise ValueError(f"No data for {symbol}: {'; '.join(errors)}")

    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current price with automatic failover.

        Args:
            symbol: Internal symbol

        Returns:
            Current price as Decimal.
        """
        if not self._connected:
            raise ConnectionError("Not connected to any data source")

        errors: list[str] = []

        # Try IBKR first
        if self._ibkr.is_connected:
            try:
                price = await self._ibkr.get_current_price(symbol)
                if price > 0:
                    self._last_source = "ibkr"
                    return price
            except Exception as e:
                errors.append(f"IBKR error: {e}")

        # Fallback to Yahoo
        if self._enable_fallback and self._yahoo.is_connected:
            try:
                price = await self._yahoo.get_current_price(symbol)
                if price > 0:
                    self._last_source = "yahoo"
                    logger.info(f"Got price from Yahoo (fallback) for {symbol}")
                    return price
            except Exception as e:
                errors.append(f"Yahoo error: {e}")

        raise ValueError(f"No price for {symbol}: {'; '.join(errors)}")

    async def get_account_summary(self) -> dict[str, Decimal]:
        """Get account summary from IBKR only.

        Yahoo doesn't provide account information.

        Returns:
            Account summary dict, or empty if IBKR unavailable.
        """
        if self._ibkr.is_connected:
            try:
                summary = await self._ibkr.get_account_summary()
                self._last_source = "ibkr"
                return summary
            except Exception as e:
                logger.warning(f"IBKR account summary failed: {e}")

        return {}

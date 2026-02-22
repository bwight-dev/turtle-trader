"""Yahoo Finance data feed adapter for backup data source."""

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal

import yfinance as yf

from src.adapters.mappers.symbol_mapper import SymbolMapper
from src.domain.interfaces.data_feed import DataFeed
from src.domain.models.market import Bar
from src.infrastructure.config import get_settings


class YahooDataFeed(DataFeed):
    """Yahoo Finance data feed implementation.

    This is a backup data source when IBKR is unavailable.
    Note: Yahoo doesn't provide real-time data for futures, only delayed.

    Important limitations:
    - Futures data may be delayed 15+ minutes
    - Micro contracts may have limited or no data
    - Volume data may be inaccurate
    - No account information (get_account_summary returns empty)
    """

    def __init__(self):
        """Initialize Yahoo Finance feed."""
        self._mapper = SymbolMapper()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Yahoo is always 'connected' as it's a REST API."""
        return self._connected

    @property
    def source_name(self) -> str:
        """Return data source name."""
        return "yahoo"

    async def connect(self) -> bool:
        """'Connect' to Yahoo - just marks as ready.

        Returns:
            Always True (Yahoo is stateless).
        """
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """'Disconnect' from Yahoo - marks as not ready."""
        self._connected = False

    async def get_bars(
        self,
        symbol: str,
        days: int = 20,
        end_date: date | None = None,
    ) -> list[Bar]:
        """Fetch historical OHLCV bars from Yahoo Finance.

        Args:
            symbol: Internal symbol (e.g., '/MGC')
            days: Number of days of history
            end_date: End date (defaults to today)

        Returns:
            List of Bar objects, oldest first.
        """
        if not self._connected:
            raise ConnectionError("Not connected to Yahoo")

        # Convert symbol
        try:
            yahoo_symbol = self._mapper.to_yahoo(symbol)
        except ValueError:
            raise ValueError(f"Cannot map symbol {symbol} to Yahoo")

        # Calculate date range
        end = end_date or date.today()
        # Add buffer days for weekends/holidays
        start = end - timedelta(days=int(days * 1.5) + 10)

        # Run yfinance in thread pool (it's synchronous)
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            lambda: self._fetch_yahoo_data(yahoo_symbol, start, end),
        )

        if df is None or df.empty:
            # Try fallback to full-size contract
            fallback = self._mapper.get_yahoo_fallback(symbol)
            if fallback and fallback != yahoo_symbol:
                df = await loop.run_in_executor(
                    None,
                    lambda: self._fetch_yahoo_data(fallback, start, end),
                )

        if df is None or df.empty:
            raise ValueError(f"No data from Yahoo for {symbol}")

        # Convert to Bar objects
        bars: list[Bar] = []
        for idx, row in df.iterrows():
            try:
                bar = Bar(
                    symbol=symbol,
                    date=idx.date() if hasattr(idx, "date") else idx,
                    open=Decimal(str(round(row["Open"], 6))),
                    high=Decimal(str(round(row["High"], 6))),
                    low=Decimal(str(round(row["Low"], 6))),
                    close=Decimal(str(round(row["Close"], 6))),
                    volume=int(row["Volume"]) if row["Volume"] > 0 else 0,
                )
                bars.append(bar)
            except Exception:
                # Skip invalid bars
                continue

        # Return only requested number of days
        return bars[-days:] if len(bars) > days else bars

    def _fetch_yahoo_data(self, yahoo_symbol: str, start: date, end: date):
        """Synchronous Yahoo Finance fetch."""
        settings = get_settings()

        ticker = yf.Ticker(yahoo_symbol)
        df = ticker.history(
            start=start,
            end=end + timedelta(days=1),  # end is exclusive
            auto_adjust=settings.yahoo_auto_adjust,
        )
        return df

    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current/last price from Yahoo.

        Note: Yahoo futures data is delayed 15+ minutes.

        Args:
            symbol: Internal symbol

        Returns:
            Current price as Decimal.
        """
        if not self._connected:
            raise ConnectionError("Not connected to Yahoo")

        try:
            yahoo_symbol = self._mapper.to_yahoo(symbol)
        except ValueError:
            raise ValueError(f"Cannot map symbol {symbol} to Yahoo")

        loop = asyncio.get_event_loop()
        price = await loop.run_in_executor(
            None,
            lambda: self._fetch_current_price(yahoo_symbol),
        )

        if price is None:
            # Try fallback
            fallback = self._mapper.get_yahoo_fallback(symbol)
            if fallback:
                price = await loop.run_in_executor(
                    None,
                    lambda: self._fetch_current_price(fallback),
                )

        if price is None:
            raise ValueError(f"No price from Yahoo for {symbol}")

        return price

    def _fetch_current_price(self, yahoo_symbol: str) -> Decimal | None:
        """Synchronous current price fetch."""
        try:
            ticker = yf.Ticker(yahoo_symbol)
            info = ticker.fast_info

            # Try different price fields
            price = (
                getattr(info, "last_price", None)
                or getattr(info, "previous_close", None)
                or getattr(info, "regular_market_price", None)
            )

            if price and price > 0:
                return Decimal(str(round(price, 6)))
        except Exception:
            pass
        return None

    async def get_account_summary(self) -> dict[str, Decimal]:
        """Get account summary - not available from Yahoo.

        Returns:
            Empty dict (Yahoo doesn't provide account info).
        """
        # Yahoo doesn't provide account information
        return {}

"""Market scanner use case for detecting trading signals.

This is an application layer use case that coordinates domain services
and adapters to scan a universe of markets for trading opportunities.
"""

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from src.domain.interfaces.data_feed import DataFeed
from src.domain.interfaces.repositories import NValueRepository, TradeRepository
from src.domain.models.enums import System
from src.domain.models.market import DonchianChannel
from src.domain.models.signal import FilterResult, Signal
from src.domain.services.channels import calculate_all_channels
from src.domain.services.s1_filter import S1Filter
from src.domain.services.signal_detector import SignalDetector
from src.domain.services.volatility import calculate_n


@dataclass
class ScanResult:
    """Result of scanning a single market."""

    symbol: str
    current_price: Decimal | None = None
    n_value: Decimal | None = None
    donchian_20_upper: Decimal | None = None
    donchian_20_lower: Decimal | None = None
    donchian_55_upper: Decimal | None = None
    donchian_55_lower: Decimal | None = None
    signals: list[Signal] | None = None
    filter_results: list[FilterResult] | None = None
    error: str | None = None
    scanned_at: datetime = None

    def __post_init__(self):
        if self.scanned_at is None:
            self.scanned_at = datetime.now()

    @property
    def has_actionable_signal(self) -> bool:
        """Check if there's an actionable (unfiltered) signal."""
        if not self.filter_results:
            return False
        return any(fr.take_signal for fr in self.filter_results)

    @property
    def actionable_signals(self) -> list[Signal]:
        """Get signals that passed filtering."""
        if not self.filter_results:
            return []
        return [fr.signal for fr in self.filter_results if fr.take_signal and fr.signal]


class MarketScanner:
    """Scans a universe of markets for trading signals.

    Coordinates:
    - Data feed for price/bar data
    - N calculator for volatility
    - Donchian calculator for channels
    - Signal detector for breakouts
    - S1 filter for signal filtering

    This is an application layer use case, not domain logic.
    """

    def __init__(
        self,
        data_feed: DataFeed,
        n_value_repo: NValueRepository,
        trade_repo: TradeRepository,
    ) -> None:
        """Initialize the scanner.

        Args:
            data_feed: Data feed for market data
            n_value_repo: Repository for N value persistence
            trade_repo: Repository for trade history (S1 filter)
        """
        self._data_feed = data_feed
        self._n_value_repo = n_value_repo
        self._trade_repo = trade_repo
        self._signal_detector = SignalDetector()
        self._s1_filter = S1Filter(trade_repo)

    async def scan(
        self,
        universe: list[str],
        concurrent_limit: int = 5,
    ) -> list[ScanResult]:
        """Scan a universe of markets for signals.

        Args:
            universe: List of symbols to scan (e.g., ['/MGC', '/MES', '/M2K'])
            concurrent_limit: Max concurrent requests (default 5)

        Returns:
            List of ScanResult for each market
        """
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrent_limit)

        async def scan_with_limit(symbol: str) -> ScanResult:
            async with semaphore:
                return await self._scan_single(symbol)

        # Scan all markets concurrently (with limit)
        tasks = [scan_with_limit(symbol) for symbol in universe]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        scan_results = []
        for symbol, result in zip(universe, results):
            if isinstance(result, Exception):
                scan_results.append(ScanResult(symbol=symbol, error=str(result)))
            else:
                scan_results.append(result)

        return scan_results

    async def _scan_single(self, symbol: str) -> ScanResult:
        """Scan a single market for signals.

        Args:
            symbol: Market symbol to scan

        Returns:
            ScanResult with signal information or error
        """
        try:
            # Get historical bars for calculations (need 55+ for Donchian)
            bars = await self._data_feed.get_bars(symbol, days=60)

            if len(bars) < 55:
                return ScanResult(
                    symbol=symbol,
                    error=f"Insufficient data: {len(bars)} bars (need 55+)",
                )

            # Get current price
            current_price = await self._data_feed.get_current_price(symbol)

            # Try to get previous N for Wilder's smoothing
            prev_n = await self._n_value_repo.get_previous_n(symbol, date.today())

            # Calculate N (ATR with Wilder's smoothing)
            n_value = calculate_n(bars[-20:], period=20, prev_n=prev_n)

            # Calculate Donchian channels (exclude current bar for breakout detection)
            channels = calculate_all_channels(bars, exclude_current=True)

            dc_20 = channels.get("dc_20")
            dc_55 = channels.get("dc_55")

            if not dc_20 or not dc_55:
                return ScanResult(
                    symbol=symbol,
                    current_price=current_price,
                    n_value=n_value.value,
                    error="Could not calculate Donchian channels",
                )

            # Detect signals
            signals = self._signal_detector.detect_all_signals(
                symbol=symbol,
                current_price=current_price,
                donchian_20=dc_20,
                donchian_55=dc_55,
            )

            # Apply S1 filter to each signal
            filter_results = []
            for signal in signals:
                filter_result = await self._s1_filter.should_take_signal(signal)
                filter_results.append(filter_result)

            return ScanResult(
                symbol=symbol,
                current_price=current_price,
                n_value=n_value.value,
                donchian_20_upper=dc_20.upper,
                donchian_20_lower=dc_20.lower,
                donchian_55_upper=dc_55.upper,
                donchian_55_lower=dc_55.lower,
                signals=signals,
                filter_results=filter_results,
            )

        except Exception as e:
            return ScanResult(
                symbol=symbol,
                error=f"Scan failed: {str(e)}",
            )

    async def scan_for_actionable(
        self,
        universe: list[str],
    ) -> list[ScanResult]:
        """Scan universe and return only markets with actionable signals.

        Convenience method that filters to only results with unfiltered signals.

        Args:
            universe: List of symbols to scan

        Returns:
            List of ScanResult that have actionable signals
        """
        all_results = await self.scan(universe)
        return [r for r in all_results if r.has_actionable_signal]


async def create_scanner(
    data_feed: DataFeed,
    n_value_repo: NValueRepository,
    trade_repo: TradeRepository,
) -> MarketScanner:
    """Factory function to create a configured MarketScanner.

    Args:
        data_feed: Data feed for market data
        n_value_repo: Repository for N value persistence
        trade_repo: Repository for trade history

    Returns:
        Configured MarketScanner instance
    """
    return MarketScanner(
        data_feed=data_feed,
        n_value_repo=n_value_repo,
        trade_repo=trade_repo,
    )

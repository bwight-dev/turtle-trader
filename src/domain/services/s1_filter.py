"""S1 Filter implementation for Turtle Trading system.

Implements Rule 7: Skip S1 signals if last S1 trade was a winner.
S2 signals (Rule 9) are NEVER filtered - they are the failsafe.
"""

from src.domain.interfaces.repositories import TradeRepository
from src.domain.models.enums import System
from src.domain.models.signal import FilterResult, Signal


class S1Filter:
    """Filter S1 signals based on previous trade outcome.

    Rule 7: Skip S1 if last S1 was a winner (to avoid whipsaws).
    Rule 9: Always take S2 signals (failsafe).

    The filter uses trade history to determine whether to take a signal.
    This prevents over-trading in choppy markets while ensuring major
    trends are never missed (via the S2 failsafe).
    """

    def __init__(self, trade_repository: TradeRepository) -> None:
        """Initialize the filter with a trade repository.

        Args:
            trade_repository: Repository for accessing trade history
        """
        self._trade_repo = trade_repository

    async def should_take_signal(
        self,
        signal: Signal,
    ) -> FilterResult:
        """Determine whether to take a trading signal.

        Args:
            signal: The signal to evaluate

        Returns:
            FilterResult with decision and explanation
        """
        # Rule 9: S2 signals are NEVER filtered (failsafe)
        if signal.system == System.S2:
            return FilterResult.accept(
                signal=signal,
                reason="S2 failsafe: always take 55-day breakout signals",
            )

        # Rule 7: Check last S1 trade outcome
        last_s1_trade = await self._trade_repo.get_last_s1_trade(signal.symbol)

        # No S1 history - take the signal
        if last_s1_trade is None:
            return FilterResult(
                take_signal=True,
                reason="No S1 trade history for this symbol - take signal",
                last_s1_was_winner=None,
                signal=signal,
            )

        # Last S1 was a winner - SKIP this signal
        if last_s1_trade.is_winner:
            return FilterResult(
                take_signal=False,
                reason=f"Rule 7: Last S1 trade was a winner (R={last_s1_trade.r_multiple:.2f}) - skip this signal",
                last_s1_was_winner=True,
                signal=signal,
            )

        # Last S1 was a loser - TAKE this signal
        return FilterResult(
            take_signal=True,
            reason=f"Last S1 trade was a loser (R={last_s1_trade.r_multiple:.2f}) - take signal",
            last_s1_was_winner=False,
            signal=signal,
        )

    async def check_symbol(self, symbol: str) -> dict:
        """Check the S1 filter status for a symbol.

        Returns current filter state without evaluating a specific signal.
        Useful for dashboards and monitoring.

        Args:
            symbol: Market symbol to check

        Returns:
            Dict with filter status information
        """
        last_s1_trade = await self._trade_repo.get_last_s1_trade(symbol)

        if last_s1_trade is None:
            return {
                "symbol": symbol,
                "has_s1_history": False,
                "would_filter_s1": False,
                "last_s1_trade": None,
                "reason": "No S1 trade history",
            }

        would_filter = last_s1_trade.is_winner

        return {
            "symbol": symbol,
            "has_s1_history": True,
            "would_filter_s1": would_filter,
            "last_s1_was_winner": last_s1_trade.is_winner,
            "last_s1_r_multiple": float(last_s1_trade.r_multiple),
            "last_s1_exit_date": last_s1_trade.exit_date.isoformat(),
            "reason": "Would skip S1 (last was winner)" if would_filter else "Would take S1 (last was loser)",
        }

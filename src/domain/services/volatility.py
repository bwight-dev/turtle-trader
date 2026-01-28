"""Volatility calculations for Turtle Trading system.

Implements N (ATR with Wilder's smoothing) as described in:
- The Original Turtle Trading Rules (Faith)
- Rule 3: Calculate N (The Volatility Measure)

N = ((19 × Previous_N) + Current_TR) / 20

This is equivalent to TOS ATR(20, WILDERS).
"""

from datetime import datetime
from decimal import Decimal

from src.domain.models.market import Bar, NValue
from src.domain.rules import N_PERIOD


def calculate_true_range(
    high: Decimal,
    low: Decimal,
    prev_close: Decimal | None = None,
) -> Decimal:
    """Calculate True Range for a single bar.

    TR = Max(H - L, |H - PDC|, |PDC - L|)

    Where PDC = Previous Day's Close.
    If no previous close (first bar), TR = H - L.

    Args:
        high: Current bar high
        low: Current bar low
        prev_close: Previous bar close (optional)

    Returns:
        True Range value
    """
    # Basic range
    hl_range = high - low

    if prev_close is None:
        return hl_range

    # True range considers gaps
    high_close = abs(high - prev_close)
    low_close = abs(prev_close - low)

    return max(hl_range, high_close, low_close)


def calculate_n(
    bars: list[Bar],
    period: int = N_PERIOD,
    prev_n: Decimal | None = None,
) -> NValue:
    """Calculate N (ATR with Wilder's smoothing).

    Wilder's smoothing formula:
    N = ((period - 1) × Previous_N + Current_TR) / period

    For the first calculation (no prev_n), uses simple average of first
    `period` true ranges.

    Args:
        bars: List of Bar objects, oldest first
        period: Smoothing period (default 20)
        prev_n: Previous N value for incremental calculation

    Returns:
        NValue with calculated N

    Raises:
        ValueError: If insufficient bars for calculation
    """
    if len(bars) < 2:
        raise ValueError(f"Need at least 2 bars, got {len(bars)}")

    # Calculate true ranges for all bars
    true_ranges: list[Decimal] = []

    for i, bar in enumerate(bars):
        prev_close = bars[i - 1].close if i > 0 else None
        tr = calculate_true_range(bar.high, bar.low, prev_close)
        true_ranges.append(tr)

    # If we have a previous N, use Wilder's smoothing for just the last TR
    if prev_n is not None:
        current_tr = true_ranges[-1]
        n_value = ((period - 1) * prev_n + current_tr) / period
        return NValue(
            value=n_value,
            calculated_at=datetime.now(),
            symbol=bars[-1].symbol if bars else None,
        )

    # Initial calculation: need at least `period` bars
    if len(true_ranges) < period:
        raise ValueError(f"Need at least {period} bars for initial N, got {len(true_ranges)}")

    # First N is simple average of first `period` TRs
    # Start from index 1 since first TR (index 0) has no prev_close
    initial_trs = true_ranges[1 : period + 1]
    n_value = sum(initial_trs) / len(initial_trs)

    # Then apply Wilder's smoothing for remaining bars
    for tr in true_ranges[period + 1 :]:
        n_value = ((period - 1) * n_value + tr) / period

    return NValue(
        value=n_value,
        calculated_at=datetime.now(),
        symbol=bars[-1].symbol if bars else None,
    )


def calculate_n_series(
    bars: list[Bar],
    period: int = N_PERIOD,
) -> list[NValue]:
    """Calculate N values for each bar in the series.

    Returns N values starting from bar `period` (first calculable N).

    Args:
        bars: List of Bar objects, oldest first
        period: Smoothing period (default 20)

    Returns:
        List of NValue objects, one per bar starting from position `period`
    """
    if len(bars) < period + 1:
        raise ValueError(f"Need at least {period + 1} bars, got {len(bars)}")

    # Calculate all true ranges
    true_ranges: list[Decimal] = []
    for i, bar in enumerate(bars):
        prev_close = bars[i - 1].close if i > 0 else None
        tr = calculate_true_range(bar.high, bar.low, prev_close)
        true_ranges.append(tr)

    results: list[NValue] = []

    # First N is simple average of TRs 1 through period (skip index 0)
    initial_trs = true_ranges[1 : period + 1]
    n_value = sum(initial_trs) / len(initial_trs)

    results.append(
        NValue(
            value=n_value,
            calculated_at=datetime.now(),
            symbol=bars[period].symbol,
        )
    )

    # Wilder's smoothing for remaining bars
    for i in range(period + 1, len(bars)):
        n_value = ((period - 1) * n_value + true_ranges[i]) / period
        results.append(
            NValue(
                value=n_value,
                calculated_at=datetime.now(),
                symbol=bars[i].symbol,
            )
        )

    return results

"""Donchian Channel calculations for Turtle Trading system.

Donchian Channels are used for:
- Entry signals (breakouts above/below channel)
- Exit signals (opposite channel touch)

Entry periods:
- S1: 20-day (Rule 6)
- S2: 55-day (Rule 8)

Exit periods:
- S1: 10-day (Rule 13)
- S2: 20-day (Rule 14)
"""

from datetime import datetime
from decimal import Decimal

from src.domain.models.market import Bar, DonchianChannel
from src.domain.rules import S1_ENTRY_PERIOD, S1_EXIT_PERIOD, S2_ENTRY_PERIOD, S2_EXIT_PERIOD


def calculate_donchian(
    bars: list[Bar],
    period: int,
) -> DonchianChannel:
    """Calculate Donchian Channel for a given period.

    Upper = Highest High of period
    Lower = Lowest Low of period

    Args:
        bars: List of Bar objects, oldest first
        period: Lookback period (10, 20, or 55 typically)

    Returns:
        DonchianChannel with upper and lower values

    Raises:
        ValueError: If insufficient bars for calculation
    """
    if len(bars) < period:
        raise ValueError(f"Need at least {period} bars, got {len(bars)}")

    # Use last `period` bars
    lookback_bars = bars[-period:]

    upper = max(bar.high for bar in lookback_bars)
    lower = min(bar.low for bar in lookback_bars)

    return DonchianChannel(
        period=period,
        upper=upper,
        lower=lower,
        calculated_at=datetime.now(),
    )


def calculate_all_channels(
    bars: list[Bar],
) -> dict[str, DonchianChannel]:
    """Calculate all Donchian channels needed for Turtle Trading.

    Returns channels for:
    - 10-day (S1 exit)
    - 20-day (S1 entry, S2 exit)
    - 55-day (S2 entry)

    Args:
        bars: List of Bar objects, oldest first (need at least 55)

    Returns:
        Dict with keys 'dc_10', 'dc_20', 'dc_55'

    Raises:
        ValueError: If insufficient bars
    """
    min_required = max(S1_EXIT_PERIOD, S1_ENTRY_PERIOD, S2_ENTRY_PERIOD)
    if len(bars) < min_required:
        raise ValueError(f"Need at least {min_required} bars, got {len(bars)}")

    return {
        "dc_10": calculate_donchian(bars, S1_EXIT_PERIOD),
        "dc_20": calculate_donchian(bars, S1_ENTRY_PERIOD),
        "dc_55": calculate_donchian(bars, S2_ENTRY_PERIOD),
    }


def is_breakout_long(
    current_price: Decimal,
    channel: DonchianChannel,
) -> bool:
    """Check if price breaks above the channel upper.

    Rule 6 (S1): Price > 20-day high
    Rule 8 (S2): Price > 55-day high

    Args:
        current_price: Current market price
        channel: Donchian channel to check against

    Returns:
        True if price is above channel upper
    """
    return current_price > channel.upper


def is_breakout_short(
    current_price: Decimal,
    channel: DonchianChannel,
) -> bool:
    """Check if price breaks below the channel lower.

    Rule 6 (S1): Price < 20-day low
    Rule 8 (S2): Price < 55-day low

    Args:
        current_price: Current market price
        channel: Donchian channel to check against

    Returns:
        True if price is below channel lower
    """
    return current_price < channel.lower


def is_exit_long(
    current_price: Decimal,
    channel: DonchianChannel,
) -> bool:
    """Check if long position should exit via channel touch.

    Rule 13 (S1): Price touches 10-day low
    Rule 14 (S2): Price touches 20-day low

    Args:
        current_price: Current market price
        channel: Exit channel (10-day for S1, 20-day for S2)

    Returns:
        True if price has touched/breached channel lower
    """
    return current_price <= channel.lower


def is_exit_short(
    current_price: Decimal,
    channel: DonchianChannel,
) -> bool:
    """Check if short position should exit via channel touch.

    Rule 13 (S1): Price touches 10-day high
    Rule 14 (S2): Price touches 20-day high

    Args:
        current_price: Current market price
        channel: Exit channel (10-day for S1, 20-day for S2)

    Returns:
        True if price has touched/breached channel upper
    """
    return current_price >= channel.upper


def calculate_channel_series(
    bars: list[Bar],
    period: int,
) -> list[DonchianChannel]:
    """Calculate Donchian channels for each bar in the series.

    Returns channels starting from bar `period` (first calculable).

    Args:
        bars: List of Bar objects, oldest first
        period: Lookback period

    Returns:
        List of DonchianChannel objects
    """
    if len(bars) < period:
        raise ValueError(f"Need at least {period} bars, got {len(bars)}")

    results: list[DonchianChannel] = []

    for i in range(period, len(bars) + 1):
        lookback = bars[i - period : i]
        channel = DonchianChannel(
            period=period,
            upper=max(bar.high for bar in lookback),
            lower=min(bar.low for bar in lookback),
            calculated_at=datetime.now(),
        )
        results.append(channel)

    return results

"""Signal detection for Turtle Trading system.

Implements Rules 6-9:
- Rule 6: S1 Entry - 20-day breakout
- Rule 7: S1 Filter (handled separately by S1Filter service)
- Rule 8: S2 Entry - 55-day breakout
- Rule 9: Failsafe - S2 always taken
"""

from datetime import datetime
from decimal import Decimal

from src.domain.models.enums import Direction, System
from src.domain.models.market import DonchianChannel
from src.domain.models.signal import Signal


class SignalDetector:
    """Detects entry signals based on Donchian channel breakouts.

    This is pure domain logic with no external dependencies.
    Uses Donchian channels to identify S1 (20-day) and S2 (55-day) breakouts.
    """

    def detect_s1_signal(
        self,
        symbol: str,
        current_price: Decimal,
        donchian_20: DonchianChannel,
    ) -> Signal | None:
        """Detect System 1 (20-day) breakout signal.

        Rule 6: Enter 1 unit when price breaks 20-day high/low.

        Args:
            symbol: Market symbol (e.g., '/MGC')
            current_price: Current market price
            donchian_20: 20-day Donchian channel

        Returns:
            Signal if breakout detected, None otherwise
        """
        # Long breakout: price > 20-day high
        if current_price > donchian_20.upper:
            return Signal(
                symbol=symbol,
                direction=Direction.LONG,
                system=System.S1,
                breakout_price=current_price,
                channel_value=donchian_20.upper,
                detected_at=datetime.now(),
            )

        # Short breakout: price < 20-day low
        if current_price < donchian_20.lower:
            return Signal(
                symbol=symbol,
                direction=Direction.SHORT,
                system=System.S1,
                breakout_price=current_price,
                channel_value=donchian_20.lower,
                detected_at=datetime.now(),
            )

        return None

    def detect_s2_signal(
        self,
        symbol: str,
        current_price: Decimal,
        donchian_55: DonchianChannel,
    ) -> Signal | None:
        """Detect System 2 (55-day) breakout signal.

        Rule 8 & 9: Enter 1 unit when price breaks 55-day high/low.
        S2 is the failsafe - always take this signal.

        Args:
            symbol: Market symbol (e.g., '/MGC')
            current_price: Current market price
            donchian_55: 55-day Donchian channel

        Returns:
            Signal if breakout detected, None otherwise
        """
        # Long breakout: price > 55-day high
        if current_price > donchian_55.upper:
            return Signal(
                symbol=symbol,
                direction=Direction.LONG,
                system=System.S2,
                breakout_price=current_price,
                channel_value=donchian_55.upper,
                detected_at=datetime.now(),
            )

        # Short breakout: price < 55-day low
        if current_price < donchian_55.lower:
            return Signal(
                symbol=symbol,
                direction=Direction.SHORT,
                system=System.S2,
                breakout_price=current_price,
                channel_value=donchian_55.lower,
                detected_at=datetime.now(),
            )

        return None

    def detect_all_signals(
        self,
        symbol: str,
        current_price: Decimal,
        donchian_20: DonchianChannel,
        donchian_55: DonchianChannel,
    ) -> list[Signal]:
        """Detect all possible signals for a market.

        Returns signals in priority order (S1 first, then S2).
        A market can have both S1 and S2 signals if price breaks both channels.

        Args:
            symbol: Market symbol
            current_price: Current market price
            donchian_20: 20-day Donchian channel
            donchian_55: 55-day Donchian channel

        Returns:
            List of detected signals (may be empty)
        """
        signals = []

        s1_signal = self.detect_s1_signal(symbol, current_price, donchian_20)
        if s1_signal:
            signals.append(s1_signal)

        s2_signal = self.detect_s2_signal(symbol, current_price, donchian_55)
        if s2_signal:
            signals.append(s2_signal)

        return signals

    def is_inside_channel(
        self,
        current_price: Decimal,
        donchian: DonchianChannel,
    ) -> bool:
        """Check if price is inside a Donchian channel.

        Args:
            current_price: Current market price
            donchian: Donchian channel to check

        Returns:
            True if price is between upper and lower bounds
        """
        return donchian.lower <= current_price <= donchian.upper

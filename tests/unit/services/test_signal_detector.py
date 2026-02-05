"""Unit tests for signal detection service."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.domain.models.enums import Direction, System
from src.domain.models.market import DonchianChannel
from src.domain.services.signal_detector import SignalDetector


@pytest.fixture
def detector():
    """Create signal detector instance."""
    return SignalDetector()


@pytest.fixture
def donchian_20():
    """Create sample 20-day Donchian channel."""
    return DonchianChannel(
        period=20,
        upper=Decimal("2850"),
        lower=Decimal("2700"),
        calculated_at=datetime.now(),
    )


@pytest.fixture
def donchian_55():
    """Create sample 55-day Donchian channel."""
    return DonchianChannel(
        period=55,
        upper=Decimal("2900"),
        lower=Decimal("2600"),
        calculated_at=datetime.now(),
    )


class TestS1SignalDetection:
    """Tests for System 1 (20-day) breakout detection."""

    def test_s1_long_breakout(self, detector, donchian_20):
        """Rule 6: Price > 20-day high generates long signal."""
        signal = detector.detect_s1_signal(
            symbol="/MGC",
            current_price=Decimal("2860"),  # Above 2850 upper
            donchian_20=donchian_20,
        )

        assert signal is not None
        assert signal.symbol == "/MGC"
        assert signal.direction == Direction.LONG
        assert signal.system == System.S1
        assert signal.breakout_price == Decimal("2860")
        assert signal.channel_value == Decimal("2850")

    def test_s1_short_breakout(self, detector, donchian_20):
        """Rule 6: Price < 20-day low generates short signal."""
        signal = detector.detect_s1_signal(
            symbol="/MGC",
            current_price=Decimal("2690"),  # Below 2700 lower
            donchian_20=donchian_20,
        )

        assert signal is not None
        assert signal.direction == Direction.SHORT
        assert signal.system == System.S1
        assert signal.breakout_price == Decimal("2690")
        assert signal.channel_value == Decimal("2700")

    def test_no_signal_inside_channel(self, detector, donchian_20):
        """No signal when price is inside the channel."""
        signal = detector.detect_s1_signal(
            symbol="/MGC",
            current_price=Decimal("2775"),  # Between 2700 and 2850
            donchian_20=donchian_20,
        )

        assert signal is None

    def test_no_signal_at_channel_boundary(self, detector, donchian_20):
        """No signal when price equals channel boundary (not through)."""
        # At upper boundary
        signal = detector.detect_s1_signal(
            symbol="/MGC",
            current_price=Decimal("2850"),  # Exactly at upper
            donchian_20=donchian_20,
        )
        assert signal is None

        # At lower boundary
        signal = detector.detect_s1_signal(
            symbol="/MGC",
            current_price=Decimal("2700"),  # Exactly at lower
            donchian_20=donchian_20,
        )
        assert signal is None

    def test_s1_signal_is_s1_system(self, detector, donchian_20):
        """S1 signals have is_s1 property True."""
        signal = detector.detect_s1_signal(
            symbol="/MGC",
            current_price=Decimal("2860"),
            donchian_20=donchian_20,
        )

        assert signal.is_s1 is True


class TestS2SignalDetection:
    """Tests for System 2 (55-day) breakout detection."""

    def test_s2_long_breakout(self, detector, donchian_55):
        """Rule 8: Price > 55-day high generates long signal."""
        signal = detector.detect_s2_signal(
            symbol="/MGC",
            current_price=Decimal("2910"),  # Above 2900 upper
            donchian_55=donchian_55,
        )

        assert signal is not None
        assert signal.direction == Direction.LONG
        assert signal.system == System.S2
        assert signal.breakout_price == Decimal("2910")
        assert signal.channel_value == Decimal("2900")

    def test_s2_short_breakout(self, detector, donchian_55):
        """Rule 8: Price < 55-day low generates short signal."""
        signal = detector.detect_s2_signal(
            symbol="/MGC",
            current_price=Decimal("2590"),  # Below 2600 lower
            donchian_55=donchian_55,
        )

        assert signal is not None
        assert signal.direction == Direction.SHORT
        assert signal.system == System.S2
        assert signal.channel_value == Decimal("2600")

    def test_no_signal_inside_channel(self, detector, donchian_55):
        """No signal when price is inside the 55-day channel."""
        signal = detector.detect_s2_signal(
            symbol="/MGC",
            current_price=Decimal("2750"),  # Between 2600 and 2900
            donchian_55=donchian_55,
        )

        assert signal is None

    def test_s2_signal_is_not_s1(self, detector, donchian_55):
        """S2 signals have is_s1 property False."""
        signal = detector.detect_s2_signal(
            symbol="/MGC",
            current_price=Decimal("2910"),
            donchian_55=donchian_55,
        )

        assert signal.is_s1 is False


class TestDetectAllSignals:
    """Tests for detecting all signals at once."""

    def test_both_breakouts_s1_takes_priority(self, detector, donchian_20, donchian_55):
        """When price breaks both channels in same direction, S1 takes priority.

        S2 is suppressed when S1 triggers in the same direction to avoid
        redundant entries.
        """
        # Price above both 20-day (2850) and 55-day (2900) highs
        signals = detector.detect_all_signals(
            symbol="/MGC",
            current_price=Decimal("2950"),
            donchian_20=donchian_20,
            donchian_55=donchian_55,
        )

        # Only S1 returned - S2 suppressed (same direction = redundant)
        assert len(signals) == 1
        assert signals[0].system == System.S1

    def test_only_s1_breakout(self, detector, donchian_20, donchian_55):
        """When price only breaks 20-day, return only S1 signal."""
        # Price above 20-day (2850) but below 55-day (2900)
        signals = detector.detect_all_signals(
            symbol="/MGC",
            current_price=Decimal("2870"),
            donchian_20=donchian_20,
            donchian_55=donchian_55,
        )

        assert len(signals) == 1
        assert signals[0].system == System.S1

    def test_only_s2_breakout(self, detector):
        """When 55-day is tighter than 20-day, only S2 triggers.

        This is an edge case where channels overlap in unusual ways.
        """
        # 20-day channel is wider than 55-day (unusual but possible)
        wide_20 = DonchianChannel(
            period=20,
            upper=Decimal("3000"),
            lower=Decimal("2500"),
            calculated_at=datetime.now(),
        )
        tight_55 = DonchianChannel(
            period=55,
            upper=Decimal("2800"),
            lower=Decimal("2600"),
            calculated_at=datetime.now(),
        )

        # Price breaks 55-day (2800) but not 20-day (3000)
        signals = detector.detect_all_signals(
            symbol="/MGC",
            current_price=Decimal("2850"),
            donchian_20=wide_20,
            donchian_55=tight_55,
        )

        assert len(signals) == 1
        assert signals[0].system == System.S2

    def test_no_breakouts_returns_empty(self, detector, donchian_20, donchian_55):
        """When price is inside all channels, return empty list."""
        signals = detector.detect_all_signals(
            symbol="/MGC",
            current_price=Decimal("2750"),  # Inside both channels
            donchian_20=donchian_20,
            donchian_55=donchian_55,
        )

        assert len(signals) == 0

    def test_short_breakouts_s1_takes_priority(self, detector, donchian_20, donchian_55):
        """Test short signals - S1 takes priority over S2."""
        # Price below both 20-day (2700) and 55-day (2600) lows
        signals = detector.detect_all_signals(
            symbol="/MGC",
            current_price=Decimal("2550"),
            donchian_20=donchian_20,
            donchian_55=donchian_55,
        )

        # Only S1 SHORT returned - S2 suppressed (same direction)
        assert len(signals) == 1
        assert signals[0].direction == Direction.SHORT
        assert signals[0].system == System.S1


class TestIsInsideChannel:
    """Tests for the is_inside_channel helper."""

    def test_price_inside(self, detector, donchian_20):
        """Price between bounds is inside."""
        assert detector.is_inside_channel(Decimal("2775"), donchian_20) is True

    def test_price_at_upper_is_inside(self, detector, donchian_20):
        """Price at upper bound is considered inside."""
        assert detector.is_inside_channel(Decimal("2850"), donchian_20) is True

    def test_price_at_lower_is_inside(self, detector, donchian_20):
        """Price at lower bound is considered inside."""
        assert detector.is_inside_channel(Decimal("2700"), donchian_20) is True

    def test_price_above_is_outside(self, detector, donchian_20):
        """Price above upper bound is outside."""
        assert detector.is_inside_channel(Decimal("2860"), donchian_20) is False

    def test_price_below_is_outside(self, detector, donchian_20):
        """Price below lower bound is outside."""
        assert detector.is_inside_channel(Decimal("2690"), donchian_20) is False


class TestSignalProperties:
    """Tests for Signal model properties."""

    def test_is_long_property(self, detector, donchian_20):
        """Test is_long property on signals."""
        long_signal = detector.detect_s1_signal(
            symbol="/MGC",
            current_price=Decimal("2860"),
            donchian_20=donchian_20,
        )
        assert long_signal.is_long is True

        short_signal = detector.detect_s1_signal(
            symbol="/MGC",
            current_price=Decimal("2690"),
            donchian_20=donchian_20,
        )
        assert short_signal.is_long is False

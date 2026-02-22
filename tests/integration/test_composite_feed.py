"""Integration tests for composite data feed with failover."""

import pytest

from src.adapters.data_feeds.composite_feed import CompositeDataFeed
from src.adapters.data_feeds.ibkr_feed import IBKRDataFeed
from src.adapters.data_feeds.yahoo_feed import YahooDataFeed


@pytest.fixture
async def composite_feed():
    """Create and connect composite feed."""
    # Use unique client ID for tests
    ibkr = IBKRDataFeed(client_id=94)
    yahoo = YahooDataFeed()
    feed = CompositeDataFeed(ibkr_feed=ibkr, yahoo_feed=yahoo)
    await feed.connect()
    yield feed
    await feed.disconnect()


@pytest.fixture
async def yahoo_only_feed():
    """Create composite feed with Yahoo only (IBKR disabled)."""
    # Invalid port to simulate IBKR unavailable
    ibkr = IBKRDataFeed(port=9999)
    yahoo = YahooDataFeed()
    feed = CompositeDataFeed(ibkr_feed=ibkr, yahoo_feed=yahoo, enable_fallback=True)
    # Only connect Yahoo
    await yahoo.connect()
    feed._connected = True
    yield feed
    await feed.disconnect()


@pytest.mark.integration
async def test_composite_connects():
    """Test composite feed connection."""
    ibkr = IBKRDataFeed(client_id=93)
    feed = CompositeDataFeed(ibkr_feed=ibkr)
    connected = await feed.connect()
    assert connected is True
    await feed.disconnect()


@pytest.mark.integration
async def test_uses_ibkr_when_available(composite_feed):
    """Test that IBKR is used as primary source."""
    bars = await composite_feed.get_bars("/MGC", days=10)

    assert len(bars) >= 5
    assert composite_feed.last_source == "ibkr"


@pytest.mark.integration
async def test_falls_back_to_yahoo(yahoo_only_feed):
    """Test fallback to Yahoo when IBKR unavailable."""
    # Use full-size contract for better Yahoo data
    bars = await yahoo_only_feed.get_bars("/GC", days=10)

    assert len(bars) >= 5
    assert yahoo_only_feed.last_source == "yahoo"


@pytest.mark.integration
async def test_account_summary_from_ibkr(composite_feed):
    """Test account summary comes from IBKR."""
    summary = await composite_feed.get_account_summary()

    # Should have data from IBKR
    assert "NetLiquidation" in summary


@pytest.mark.integration
async def test_account_summary_empty_without_ibkr(yahoo_only_feed):
    """Test account summary is empty without IBKR."""
    summary = await yahoo_only_feed.get_account_summary()

    # Yahoo doesn't provide account info
    assert summary == {}


@pytest.mark.integration
async def test_current_price_with_failover(composite_feed):
    """Test current price retrieval."""
    price = await composite_feed.get_current_price("/MGC")

    # Gold should be > $1000
    assert price > 1000


@pytest.mark.integration
@pytest.mark.ibkr
async def test_validates_data(composite_feed):
    """Test that data is validated."""
    # Should return valid bars
    bars = await composite_feed.get_bars("/MGC", days=20)

    # All bars should pass validation
    for bar in bars:
        assert bar.high >= bar.low
        assert bar.high >= bar.open
        assert bar.high >= bar.close
        assert bar.low <= bar.open
        assert bar.low <= bar.close

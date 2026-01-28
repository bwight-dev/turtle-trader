"""Integration tests for Yahoo Finance data feed."""

import pytest

from src.adapters.data_feeds.yahoo_feed import YahooDataFeed


@pytest.fixture
async def feed():
    """Create and connect Yahoo feed."""
    feed = YahooDataFeed()
    await feed.connect()
    yield feed
    await feed.disconnect()


@pytest.mark.integration
async def test_yahoo_connects():
    """Test that Yahoo feed can connect."""
    feed = YahooDataFeed()
    connected = await feed.connect()
    assert connected is True
    assert feed.is_connected is True
    await feed.disconnect()


@pytest.mark.integration
async def test_yahoo_source_name():
    """Test source name is 'yahoo'."""
    feed = YahooDataFeed()
    assert feed.source_name == "yahoo"


@pytest.mark.integration
async def test_yahoo_get_bars_gc(feed):
    """Test fetching gold futures bars."""
    # Use /GC (full size) which has better data on Yahoo
    bars = await feed.get_bars("/GC", days=10)

    assert len(bars) >= 5  # May have fewer due to holidays
    assert all(b.high >= b.low for b in bars)
    assert all(b.symbol == "/GC" for b in bars)


@pytest.mark.integration
async def test_yahoo_get_bars_es(feed):
    """Test fetching S&P futures bars."""
    bars = await feed.get_bars("/ES", days=10)

    assert len(bars) >= 5
    assert all(b.high >= b.low for b in bars)


@pytest.mark.integration
async def test_yahoo_get_current_price_gc(feed):
    """Test fetching gold current price."""
    price = await feed.get_current_price("/GC")

    # Gold should be > $1000
    assert price > 1000


@pytest.mark.integration
async def test_yahoo_account_summary_empty(feed):
    """Test that account summary returns empty dict."""
    summary = await feed.get_account_summary()
    assert summary == {}


@pytest.mark.integration
async def test_yahoo_micro_fallback(feed):
    """Test that micro contracts fall back to full-size."""
    # /MGC should fall back to GC=F
    bars = await feed.get_bars("/MGC", days=10)

    # Should get data (may be from fallback)
    assert len(bars) >= 5

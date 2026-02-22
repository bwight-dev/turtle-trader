"""Integration tests for IBKR data feed."""

import pytest

from src.adapters.data_feeds.ibkr_feed import IBKRDataFeed


@pytest.fixture
async def feed():
    """Create and connect IBKR feed."""
    feed = IBKRDataFeed(client_id=98)  # Use unique client ID for tests
    try:
        await feed.connect()
        yield feed
    finally:
        await feed.disconnect()


@pytest.mark.ibkr
@pytest.mark.integration
async def test_ibkr_connects():
    """Test that we can connect to IBKR."""
    feed = IBKRDataFeed(client_id=97)
    try:
        connected = await feed.connect()
        assert connected
        assert feed.is_connected
    finally:
        await feed.disconnect()


@pytest.mark.ibkr
@pytest.mark.integration
async def test_ibkr_account_summary(feed):
    """Test account summary retrieval."""
    summary = await feed.get_account_summary()
    assert "NetLiquidation" in summary
    assert summary["NetLiquidation"] > 0


@pytest.mark.ibkr
@pytest.mark.integration
async def test_ibkr_get_bars(feed):
    """Test historical bar retrieval."""
    bars = await feed.get_bars("/MGC", days=5)
    assert len(bars) >= 3
    assert all(b.high >= b.low for b in bars)
    assert all(b.symbol == "/MGC" for b in bars)


@pytest.mark.ibkr
@pytest.mark.integration
async def test_ibkr_source_name():
    """Test source name property."""
    feed = IBKRDataFeed()
    assert feed.source_name == "ibkr"

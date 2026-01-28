#!/usr/bin/env python3
"""Test Interactive Brokers TWS connection."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.data_feeds.ibkr_feed import IBKRDataFeed
from src.infrastructure.config import get_settings


async def test_connection() -> bool:
    """Test basic IBKR connectivity."""
    settings = get_settings()
    print(f"Connecting to IBKR at {settings.ibkr_host}:{settings.ibkr_port}...")

    feed = IBKRDataFeed()

    try:
        connected = await feed.connect()
        if not connected:
            print("✗ Connection failed")
            return False

        print("✓ Connected to IBKR")
        print(f"  Account: {settings.ibkr_account_id}")

        return True
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False
    finally:
        await feed.disconnect()


async def test_account_summary(feed: IBKRDataFeed) -> bool:
    """Test account summary retrieval."""
    print("\nTesting account summary...")

    try:
        summary = await feed.get_account_summary()

        if "NetLiquidation" not in summary:
            print("✗ NetLiquidation not in summary")
            return False

        print("✓ Account summary retrieved:")
        for key in ["NetLiquidation", "AvailableFunds", "BuyingPower", "TotalCashValue"]:
            if key in summary:
                print(f"    {key}: ${summary[key]:,.2f}")

        return True
    except Exception as e:
        print(f"✗ Account summary error: {e}")
        return False


async def test_market_data(feed: IBKRDataFeed) -> bool:
    """Test market data retrieval."""
    print("\nTesting market data for /MGC...")

    try:
        bars = await feed.get_bars("/MGC", days=5)

        if not bars:
            print("✗ No bars returned")
            return False

        print(f"✓ Retrieved {len(bars)} bars:")
        for bar in bars[-3:]:  # Show last 3
            print(f"    {bar.date}: O={bar.open} H={bar.high} L={bar.low} C={bar.close}")

        return True
    except Exception as e:
        print(f"✗ Market data error: {e}")
        return False


async def main() -> None:
    """Run all IBKR tests."""
    feed = IBKRDataFeed()

    try:
        # Test connection
        print("=" * 50)
        print("IBKR Connection Test")
        print("=" * 50)

        connected = await feed.connect()
        if not connected:
            print("\n✗ Could not connect to IBKR")
            print("  Make sure TWS/Gateway is running and API is enabled")
            sys.exit(1)

        print("✓ Connected to IBKR")

        # Test account summary
        account_ok = await test_account_summary(feed)

        # Test market data
        data_ok = await test_market_data(feed)

        # Summary
        print("\n" + "=" * 50)
        if account_ok and data_ok:
            print("All IBKR tests passed!")
        else:
            print("Some tests failed")
            sys.exit(1)

    finally:
        await feed.disconnect()
        print("\nDisconnected from IBKR")


if __name__ == "__main__":
    asyncio.run(main())

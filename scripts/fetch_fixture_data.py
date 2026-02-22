#!/usr/bin/env python3
"""Fetch real market data for test fixtures."""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.data_feeds.ibkr_feed import IBKRDataFeed


async def main():
    """Fetch MGC data and save as JSON fixture."""
    feed = IBKRDataFeed(client_id=95)

    try:
        await feed.connect()
        print("Connected to IBKR")

        # Fetch 65 days of data (need 55+ for S2 Donchian calculation)
        bars = await feed.get_bars("/MGC", days=65)
        print(f"Fetched {len(bars)} bars")

        # Convert to JSON-serializable format
        data = []
        for bar in bars:
            data.append({
                "symbol": bar.symbol,
                "date": bar.date.isoformat(),
                "open": str(bar.open),
                "high": str(bar.high),
                "low": str(bar.low),
                "close": str(bar.close),
                "volume": bar.volume,
            })

        # Save to fixtures
        fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"
        fixtures_dir.mkdir(exist_ok=True)

        output_file = fixtures_dir / "mgc_bars.json"
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        print(f"Saved {len(data)} bars to {output_file}")

        # Print last few bars for reference
        print("\nLast 5 bars:")
        for bar in bars[-5:]:
            print(f"  {bar.date}: O={bar.open} H={bar.high} L={bar.low} C={bar.close}")

    finally:
        await feed.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""Test Neon PostgreSQL connection."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.database import close_pool, fetch, fetchval


async def test_connection() -> bool:
    """Test basic database connectivity."""
    print("Testing Neon PostgreSQL connection...")

    try:
        # Test basic query
        result = await fetchval("SELECT 1")
        assert result == 1, f"Expected 1, got {result}"
        print("✓ Basic connectivity: OK")

        # Test version
        version = await fetchval("SELECT version()")
        print(f"✓ PostgreSQL version: {version[:50]}...")

        return True
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False


async def test_markets_table() -> bool:
    """Test that markets table exists and has data."""
    print("\nTesting markets table...")

    try:
        # Check table exists
        exists = await fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'markets'
            )
        """)
        assert exists, "Markets table does not exist"
        print("✓ Markets table exists")

        # Check row count
        count = await fetchval("SELECT COUNT(*) FROM markets")
        print(f"✓ Markets table has {count} rows")

        # Sample data
        markets = await fetch("SELECT symbol, name, correlation_group FROM markets LIMIT 5")
        print("✓ Sample markets:")
        for m in markets:
            print(f"    {m['symbol']}: {m['name']} ({m['correlation_group']})")

        return True
    except Exception as e:
        print(f"✗ Markets table test failed: {e}")
        return False


async def main() -> None:
    """Run all tests."""
    try:
        conn_ok = await test_connection()
        table_ok = await test_markets_table()

        print("\n" + "=" * 50)
        if conn_ok and table_ok:
            print("Connected to Neon successfully")
            print("All tests passed!")
        else:
            print("Some tests failed")
            sys.exit(1)
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())

"""Integration tests for Neon PostgreSQL connection."""

import pytest

from src.infrastructure.database import close_pool, fetch, fetchval, get_pool


@pytest.fixture(autouse=True)
async def cleanup():
    """Clean up pool after tests."""
    yield
    await close_pool()


@pytest.mark.integration
async def test_neon_connection():
    """Test basic Neon connectivity."""
    pool = await get_pool()
    result = await pool.fetchval("SELECT 1")
    assert result == 1


@pytest.mark.integration
async def test_markets_table_exists():
    """Test that markets table exists."""
    exists = await fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'markets')"
    )
    assert exists is True


@pytest.mark.integration
async def test_markets_has_data():
    """Test that markets table has seeded data."""
    count = await fetchval("SELECT COUNT(*) FROM markets")
    assert count > 0


@pytest.mark.integration
async def test_markets_schema():
    """Test that markets table has expected columns."""
    columns = await fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'markets'
        ORDER BY ordinal_position
    """)

    column_names = {row["column_name"] for row in columns}
    expected = {"id", "symbol", "name", "exchange", "asset_class", "correlation_group",
                "point_value", "tick_size", "currency", "is_active", "created_at", "updated_at"}

    assert expected.issubset(column_names)

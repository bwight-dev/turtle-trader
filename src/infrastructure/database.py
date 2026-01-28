"""Neon PostgreSQL database connection pool."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from asyncpg import Pool

from src.infrastructure.config import get_settings

_pool: Pool | None = None
_pool_lock = asyncio.Lock()


async def get_pool() -> Pool:
    """Get or create the database connection pool."""
    global _pool

    if _pool is not None:
        return _pool

    async with _pool_lock:
        # Double-check after acquiring lock
        if _pool is not None:
            return _pool

        settings = get_settings()
        _pool = await asyncpg.create_pool(
            str(settings.database_url),
            min_size=1,
            max_size=settings.database_pool_size,
            command_timeout=60,
        )
        return _pool


async def close_pool() -> None:
    """Close the database connection pool."""
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Get a connection from the pool as a context manager."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def execute(query: str, *args) -> str:
    """Execute a query and return status."""
    async with get_connection() as conn:
        return await conn.execute(query, *args)


async def fetch(query: str, *args) -> list[asyncpg.Record]:
    """Execute a query and return all rows."""
    async with get_connection() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args) -> asyncpg.Record | None:
    """Execute a query and return a single row."""
    async with get_connection() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args):
    """Execute a query and return a single value."""
    async with get_connection() as conn:
        return await conn.fetchval(query, *args)

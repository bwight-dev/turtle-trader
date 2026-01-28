#!/usr/bin/env python3
"""Database setup script - runs migrations against Neon PostgreSQL."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.database import close_pool, get_connection


async def run_migrations() -> None:
    """Run all pending migrations."""
    migrations_dir = Path(__file__).parent.parent / "src" / "infrastructure" / "migrations"

    # Get list of migration files sorted by name
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        print("No migration files found.")
        return

    async with get_connection() as conn:
        # Ensure schema_migrations table exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(50) PRIMARY KEY,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Get already applied migrations
        applied = await conn.fetch("SELECT version FROM schema_migrations")
        applied_versions = {row["version"] for row in applied}

        for migration_file in migration_files:
            version = migration_file.stem  # e.g., "001_create_markets_table"

            if version in applied_versions:
                print(f"Skipping {version} (already applied)")
                continue

            print(f"Applying {version}...")
            sql = migration_file.read_text()

            # Run the migration in a transaction
            async with conn.transaction():
                await conn.execute(sql)

            print(f"Applied {version}")

    print("All migrations complete.")


async def main() -> None:
    """Run database setup."""
    try:
        print("Connecting to Neon PostgreSQL...")
        await run_migrations()
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())

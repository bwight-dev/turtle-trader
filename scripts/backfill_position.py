#!/usr/bin/env python3
"""Backfill current EFA position into open_positions table.

One-time script to populate the database with the existing position.

Usage:
    python scripts/backfill_position.py
"""

import asyncio
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.repositories.alert_repository import PostgresAlertRepository
from src.adapters.repositories.position_repository import PostgresOpenPositionRepository
from src.application.commands.log_alert import AlertLogger
from src.domain.models.enums import Direction, System


async def backfill_efa_position():
    """Backfill the current EFA position."""
    alert_repo = PostgresAlertRepository()
    position_repo = PostgresOpenPositionRepository()
    alert_logger = AlertLogger(alert_repo, position_repo)

    # Current EFA position details (from IBKR)
    symbol = "EFA"
    direction = Direction.LONG
    system = System.S1
    entry_price = Decimal("101.56")
    contracts = 134
    stop_price = Decimal("99.73")  # 2N below entry
    n_value = Decimal("0.93")

    print(f"Backfilling {symbol} position...")
    print(f"  Direction: {direction.value}")
    print(f"  System: {system.value}")
    print(f"  Entry: ${entry_price}")
    print(f"  Contracts: {contracts}")
    print(f"  Stop: ${stop_price}")
    print(f"  N: {n_value}")

    # Check if position already exists
    existing = await position_repo.get(symbol)
    if existing:
        print(f"\nPosition already exists in database. Skipping.")
        return

    # Log position opened (creates alert + position snapshot)
    alert = await alert_logger.log_position_opened(
        symbol=symbol,
        direction=direction,
        system=system,
        entry_price=entry_price,
        contracts=contracts,
        stop_price=stop_price,
        n_value=n_value,
    )

    print(f"\nPosition backfilled successfully!")
    print(f"  Alert ID: {alert.id}")

    # Verify
    position = await position_repo.get(symbol)
    print(f"\nVerification:")
    print(f"  Symbol: {position.symbol}")
    print(f"  Contracts: {position.contracts}")
    print(f"  Stop: ${position.stop_price}")


if __name__ == "__main__":
    asyncio.run(backfill_efa_position())

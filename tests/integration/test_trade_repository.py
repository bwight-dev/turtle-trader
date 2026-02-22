"""Integration tests for trade repository."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.adapters.repositories.trade_repository import PostgresTradeRepository
from src.domain.models.enums import Direction, System
from src.domain.models.trade import Trade
from src.infrastructure.database import close_pool, execute


@pytest.fixture
async def repo():
    """Create repository instance."""
    return PostgresTradeRepository()


@pytest.fixture(autouse=True)
async def cleanup():
    """Clean up test data after each test."""
    yield
    # Clean up test data
    await execute("DELETE FROM trades WHERE symbol LIKE 'TEST%'")
    await close_pool()


def make_trade(
    symbol: str = "TEST_MGC",
    direction: Direction = Direction.LONG,
    system: System = System.S1,
    entry_price: str = "2800",
    exit_price: str = "2900",
    realized_pnl: str = "1000",
    exit_reason: str = "breakout",
    exit_date: datetime = None,
) -> Trade:
    """Helper to create test trades."""
    return Trade(
        id=uuid4(),
        symbol=symbol,
        direction=direction,
        system=system,
        entry_price=Decimal(entry_price),
        entry_date=datetime(2026, 1, 1, 10, 0),
        entry_contracts=1,
        n_at_entry=Decimal("50"),
        exit_price=Decimal(exit_price),
        exit_date=exit_date or datetime(2026, 1, 10, 14, 0),
        exit_reason=exit_reason,
        realized_pnl=Decimal(realized_pnl),
        commission=Decimal("5"),
        max_units=1,
    )


@pytest.mark.integration
async def test_save_and_retrieve_trade(repo):
    """Test saving and retrieving a trade."""
    trade = make_trade()

    await repo.save_trade(trade)

    trades = await repo.get_trades_by_symbol("TEST_MGC")

    assert len(trades) == 1
    assert trades[0].symbol == "TEST_MGC"
    assert trades[0].direction == Direction.LONG
    assert trades[0].system == System.S1
    assert trades[0].entry_price == Decimal("2800")
    assert trades[0].exit_price == Decimal("2900")
    assert trades[0].realized_pnl == Decimal("1000")


@pytest.mark.integration
async def test_get_last_s1_trade(repo):
    """Test getting the most recent S1 trade."""
    # Save older S1 trade
    older_s1 = make_trade(
        realized_pnl="-500",
        exit_date=datetime(2026, 1, 5, 14, 0),
    )
    await repo.save_trade(older_s1)

    # Save newer S1 trade (winner)
    newer_s1 = make_trade(
        realized_pnl="1000",
        exit_date=datetime(2026, 1, 10, 14, 0),
    )
    await repo.save_trade(newer_s1)

    # Save S2 trade (should be ignored)
    s2_trade = make_trade(
        system=System.S2,
        exit_date=datetime(2026, 1, 15, 14, 0),
    )
    await repo.save_trade(s2_trade)

    last_s1 = await repo.get_last_s1_trade("TEST_MGC")

    assert last_s1 is not None
    assert last_s1.system == System.S1
    assert last_s1.realized_pnl == Decimal("1000")  # The newer S1
    assert last_s1.is_winner is True


@pytest.mark.integration
async def test_get_last_s1_trade_not_found(repo):
    """Test getting S1 trade when none exists."""
    last_s1 = await repo.get_last_s1_trade("TEST_NONEXISTENT")

    assert last_s1 is None


@pytest.mark.integration
async def test_get_last_s1_trade_only_s2_exists(repo):
    """Test getting S1 trade when only S2 trades exist."""
    s2_trade = make_trade(system=System.S2)
    await repo.save_trade(s2_trade)

    last_s1 = await repo.get_last_s1_trade("TEST_MGC")

    assert last_s1 is None


@pytest.mark.integration
async def test_get_trades_by_symbol_ordered(repo):
    """Test that trades are returned in chronological order (newest first)."""
    for i in range(5):
        trade = make_trade(
            realized_pnl=str(100 * i),
            exit_date=datetime(2026, 1, 1 + i, 14, 0),
        )
        await repo.save_trade(trade)

    trades = await repo.get_trades_by_symbol("TEST_MGC")

    assert len(trades) == 5
    # Should be newest first (Jan 5, Jan 4, Jan 3, Jan 2, Jan 1)
    assert trades[0].exit_date.day == 5
    assert trades[4].exit_date.day == 1


@pytest.mark.integration
async def test_get_trades_by_symbol_limit(repo):
    """Test limiting number of returned trades."""
    for i in range(10):
        trade = make_trade(
            exit_date=datetime(2026, 1, 1 + i, 14, 0),
        )
        await repo.save_trade(trade)

    trades = await repo.get_trades_by_symbol("TEST_MGC", limit=5)

    assert len(trades) == 5


@pytest.mark.integration
async def test_multiple_symbols(repo):
    """Test trades for multiple symbols stay separate."""
    mgc_trade = make_trade(symbol="TEST_MGC")
    mes_trade = make_trade(symbol="TEST_MES", realized_pnl="2000")

    await repo.save_trade(mgc_trade)
    await repo.save_trade(mes_trade)

    mgc_trades = await repo.get_trades_by_symbol("TEST_MGC")
    mes_trades = await repo.get_trades_by_symbol("TEST_MES")

    assert len(mgc_trades) == 1
    assert len(mes_trades) == 1
    assert mgc_trades[0].realized_pnl == Decimal("1000")
    assert mes_trades[0].realized_pnl == Decimal("2000")


@pytest.mark.integration
async def test_get_last_trade_with_filters(repo):
    """Test get_last_trade with system and direction filters."""
    # Save trades with different systems and directions
    s1_long = make_trade(system=System.S1, direction=Direction.LONG, exit_date=datetime(2026, 1, 1))
    s1_short = make_trade(system=System.S1, direction=Direction.SHORT, exit_date=datetime(2026, 1, 2))
    s2_long = make_trade(system=System.S2, direction=Direction.LONG, exit_date=datetime(2026, 1, 3))

    await repo.save_trade(s1_long)
    await repo.save_trade(s1_short)
    await repo.save_trade(s2_long)

    # Filter by system
    last_s1 = await repo.get_last_trade("TEST_MGC", system=System.S1)
    assert last_s1.system == System.S1
    assert last_s1.direction == Direction.SHORT  # Most recent S1

    # Filter by direction
    last_long = await repo.get_last_trade("TEST_MGC", direction=Direction.LONG)
    assert last_long.direction == Direction.LONG
    assert last_long.system == System.S2  # Most recent long

    # Filter by both
    last_s1_long = await repo.get_last_trade("TEST_MGC", system=System.S1, direction=Direction.LONG)
    assert last_s1_long.system == System.S1
    assert last_s1_long.direction == Direction.LONG


@pytest.mark.integration
async def test_trade_computed_fields(repo):
    """Test that computed fields work after retrieval."""
    trade = Trade(
        symbol="TEST_MGC",
        direction=Direction.LONG,
        system=System.S1,
        entry_price=Decimal("2800"),
        entry_date=datetime(2026, 1, 1, 10, 0),
        entry_contracts=2,
        n_at_entry=Decimal("50"),
        exit_price=Decimal("2900"),
        exit_date=datetime(2026, 1, 11, 14, 0),  # 10 days later
        exit_reason="breakout",
        realized_pnl=Decimal("2000"),
        commission=Decimal("10"),
    )

    await repo.save_trade(trade)

    retrieved = (await repo.get_trades_by_symbol("TEST_MGC"))[0]

    assert retrieved.holding_days == 10
    assert retrieved.net_pnl == Decimal("1990")  # 2000 - 10
    assert retrieved.is_winner is True
    # R = 2000 / (2 * 50 * 2) = 2000 / 200 = 10
    assert retrieved.r_multiple == Decimal("10")


@pytest.mark.integration
async def test_losing_trade_is_winner_false(repo):
    """Test that losing trades have is_winner = False."""
    trade = make_trade(
        exit_price="2700",  # Lost $100
        realized_pnl="-1000",
    )

    await repo.save_trade(trade)

    retrieved = (await repo.get_trades_by_symbol("TEST_MGC"))[0]

    assert retrieved.is_winner is False
    assert retrieved.r_multiple < 0

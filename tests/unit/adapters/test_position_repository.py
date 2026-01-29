"""Unit tests for PostgresOpenPositionRepository."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.domain.models.alert import OpenPositionSnapshot
from src.domain.models.enums import Direction, System


class InMemoryOpenPositionRepository:
    """In-memory position repository for testing."""

    def __init__(self):
        self.positions: dict[str, OpenPositionSnapshot] = {}

    async def upsert(self, position: OpenPositionSnapshot) -> None:
        self.positions[position.symbol] = position

    async def get_all(self) -> list[OpenPositionSnapshot]:
        return list(self.positions.values())

    async def get(self, symbol: str) -> OpenPositionSnapshot | None:
        return self.positions.get(symbol)

    async def delete(self, symbol: str) -> None:
        self.positions.pop(symbol, None)


@pytest.fixture
def repo():
    """Create in-memory position repository."""
    return InMemoryOpenPositionRepository()


def make_snapshot(symbol: str = "EFA", **kwargs) -> OpenPositionSnapshot:
    """Create a test position snapshot."""
    defaults = {
        "direction": Direction.LONG,
        "system": System.S1,
        "entry_price": Decimal("101.56"),
        "entry_date": datetime(2026, 1, 29, 10, 30),
        "contracts": 134,
    }
    defaults.update(kwargs)
    return OpenPositionSnapshot(symbol=symbol, **defaults)


class TestOpenPositionRepository:
    """Tests for open position repository operations."""

    @pytest.mark.asyncio
    async def test_upsert_and_get(self, repo):
        """Upsert a position and retrieve it."""
        snapshot = make_snapshot()
        await repo.upsert(snapshot)

        result = await repo.get("EFA")
        assert result is not None
        assert result.symbol == "EFA"
        assert result.contracts == 134

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, repo):
        """Upsert should update existing position."""
        await repo.upsert(make_snapshot(current_price=Decimal("101.00")))
        await repo.upsert(make_snapshot(current_price=Decimal("102.00")))

        result = await repo.get("EFA")
        assert result.current_price == Decimal("102.00")

    @pytest.mark.asyncio
    async def test_get_all(self, repo):
        """Get all open positions."""
        await repo.upsert(make_snapshot(symbol="EFA"))
        await repo.upsert(make_snapshot(symbol="SPY"))

        all_positions = await repo.get_all()
        assert len(all_positions) == 2
        symbols = {p.symbol for p in all_positions}
        assert symbols == {"EFA", "SPY"}

    @pytest.mark.asyncio
    async def test_delete(self, repo):
        """Delete a position."""
        await repo.upsert(make_snapshot())
        await repo.delete("EFA")

        result = await repo.get("EFA")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, repo):
        """Get returns None for nonexistent symbol."""
        result = await repo.get("NOTEXIST")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_no_error(self, repo):
        """Delete nonexistent symbol should not error."""
        await repo.delete("NOTEXIST")  # Should not raise

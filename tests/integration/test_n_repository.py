"""Integration tests for N value repository."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from src.adapters.repositories.n_repository import PostgresNValueRepository
from src.domain.models.market import DonchianChannel, NValue
from src.infrastructure.database import close_pool, execute


@pytest.fixture
async def repo():
    """Create repository instance."""
    return PostgresNValueRepository()


@pytest.fixture(autouse=True)
async def cleanup():
    """Clean up test data after each test."""
    yield
    # Clean up test data
    await execute("DELETE FROM calculated_indicators WHERE symbol LIKE 'TEST%'")
    await close_pool()


@pytest.mark.integration
async def test_save_and_retrieve_n(repo):
    """Test saving and retrieving N value."""
    n_value = NValue(
        value=Decimal("91.42"),
        calculated_at=datetime.now(),
        symbol="TEST_MGC",
    )

    await repo.save_indicators(
        symbol="TEST_MGC",
        calc_date=date(2026, 1, 22),
        n_value=n_value,
    )

    indicators = await repo.get_latest_indicators("TEST_MGC")

    assert indicators is not None
    assert indicators["n_value"] == Decimal("91.42")
    assert indicators["calc_date"] == date(2026, 1, 22)


@pytest.mark.integration
async def test_save_with_donchian_channels(repo):
    """Test saving N value with Donchian channels."""
    n_value = NValue(value=Decimal("20.00"), calculated_at=datetime.now())
    dc_10 = DonchianChannel(period=10, upper=Decimal("2850"), lower=Decimal("2750"), calculated_at=datetime.now())
    dc_20 = DonchianChannel(period=20, upper=Decimal("2900"), lower=Decimal("2700"), calculated_at=datetime.now())
    dc_55 = DonchianChannel(period=55, upper=Decimal("3000"), lower=Decimal("2600"), calculated_at=datetime.now())

    await repo.save_indicators(
        symbol="TEST_MGC",
        calc_date=date(2026, 1, 22),
        n_value=n_value,
        donchian_10=dc_10,
        donchian_20=dc_20,
        donchian_55=dc_55,
    )

    indicators = await repo.get_latest_indicators("TEST_MGC")

    assert indicators is not None
    assert "donchian_10" in indicators
    assert indicators["donchian_10"].upper == Decimal("2850")
    assert indicators["donchian_20"].period == 20
    assert indicators["donchian_55"].lower == Decimal("2600")


@pytest.mark.integration
async def test_get_previous_n(repo):
    """Test getting previous N for incremental calculation."""
    # Save N for two consecutive days
    await repo.save_indicators(
        symbol="TEST_MGC",
        calc_date=date(2026, 1, 21),
        n_value=NValue(value=Decimal("90.00"), calculated_at=datetime.now()),
    )
    await repo.save_indicators(
        symbol="TEST_MGC",
        calc_date=date(2026, 1, 22),
        n_value=NValue(value=Decimal("91.42"), calculated_at=datetime.now()),
    )

    # Get previous N before Jan 22
    prev_n = await repo.get_previous_n("TEST_MGC", date(2026, 1, 22))
    assert prev_n == Decimal("90.00")

    # Get previous N before Jan 23
    prev_n = await repo.get_previous_n("TEST_MGC", date(2026, 1, 23))
    assert prev_n == Decimal("91.42")


@pytest.mark.integration
async def test_get_previous_n_not_found(repo):
    """Test getting previous N when no history exists."""
    prev_n = await repo.get_previous_n("TEST_NONEXISTENT", date(2026, 1, 22))
    assert prev_n is None


@pytest.mark.integration
async def test_get_n_history(repo):
    """Test getting N value history."""
    # Save N for multiple days
    for i in range(5):
        await repo.save_indicators(
            symbol="TEST_MGC",
            calc_date=date(2026, 1, 18 + i),
            n_value=NValue(value=Decimal(str(90 + i)), calculated_at=datetime.now()),
        )

    history = await repo.get_n_history("TEST_MGC", days=10)

    assert len(history) == 5
    # Should be oldest first
    assert history[0] == (date(2026, 1, 18), Decimal("90"))
    assert history[4] == (date(2026, 1, 22), Decimal("94"))


@pytest.mark.integration
async def test_upsert_overwrites(repo):
    """Test that saving same date updates existing record."""
    # Save initial value
    await repo.save_indicators(
        symbol="TEST_MGC",
        calc_date=date(2026, 1, 22),
        n_value=NValue(value=Decimal("90.00"), calculated_at=datetime.now()),
    )

    # Save updated value for same date
    await repo.save_indicators(
        symbol="TEST_MGC",
        calc_date=date(2026, 1, 22),
        n_value=NValue(value=Decimal("95.00"), calculated_at=datetime.now()),
    )

    indicators = await repo.get_latest_indicators("TEST_MGC")
    assert indicators["n_value"] == Decimal("95.00")


@pytest.mark.integration
async def test_multiple_symbols(repo):
    """Test storing indicators for multiple symbols."""
    await repo.save_indicators(
        symbol="TEST_MGC",
        calc_date=date(2026, 1, 22),
        n_value=NValue(value=Decimal("91.42"), calculated_at=datetime.now()),
    )
    await repo.save_indicators(
        symbol="TEST_MES",
        calc_date=date(2026, 1, 22),
        n_value=NValue(value=Decimal("45.00"), calculated_at=datetime.now()),
    )

    mgc = await repo.get_latest_indicators("TEST_MGC")
    mes = await repo.get_latest_indicators("TEST_MES")

    assert mgc["n_value"] == Decimal("91.42")
    assert mes["n_value"] == Decimal("45.00")

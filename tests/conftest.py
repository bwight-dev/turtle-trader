"""Pytest configuration and fixtures for all tests."""

import os
from decimal import Decimal

import pytest


# Set up required environment variables before any imports
# This ensures Settings can be instantiated without a real database
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables before tests run."""
    # Set a dummy DATABASE_URL for tests that don't need a real database
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/testdb"

    yield

    # Cleanup (optional)


# Also set it at module load time for imports that happen before fixtures
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/testdb"


@pytest.fixture
def sample_equity():
    """Sample equity value for testing."""
    return Decimal("50000")


@pytest.fixture
def sample_n_value():
    """Sample N (ATR) value for testing."""
    return Decimal("2.50")


@pytest.fixture
def sample_price():
    """Sample price for testing."""
    return Decimal("100.00")

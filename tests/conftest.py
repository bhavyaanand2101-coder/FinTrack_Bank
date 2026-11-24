"""
FinTrack - Test Configuration and Pytest Fixtures
File: tests/conftest.py
"""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import os
from decimal import Decimal
import pytest

from config.settings import settings
from database_layer.db import close_connection_pool, get_connection_pool, get_db_connection
from database_layer.postgres import execute_update, transaction

# Test database URL
TEST_DB_URI = "postgresql://bhavya@localhost:5432/fintrack_test"
TEST_MONGO_DB = "fintrack_test_db"


def pytest_configure(config):
    """Override configuration to ensure tests run against isolated test databases."""
    settings.POSTGRES_URI = TEST_DB_URI
    settings.MONGO_DB_NAME = TEST_MONGO_DB
    close_connection_pool()


def pytest_unconfigure(config):
    """Clean up pool connections upon test suite completion."""
    close_connection_pool()


@pytest.fixture(autouse=True)
def reset_db_state():
    """Ensure clean connection pool and isolated rate-limit state before each test."""
    from security import _RATE_LIMITS, _RATE_LIMIT_LOCK
    with _RATE_LIMIT_LOCK:
        _RATE_LIMITS.clear()
    yield
    # Any post-test cleanup if necessary


@pytest.fixture
def db_conn():
    """Yield a connection to the isolated test database."""
    with get_db_connection() as conn:
        yield conn

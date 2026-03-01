"""
Shared pytest fixtures for Colorado CareAssist test suite.

Provides mock database connections, environment variables,
and common test helpers so unit tests never hit real services.
"""

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# Stub out heavy optional dependencies that aren't installed
# in the test environment. Tests import specific modules
# (e.g. services.auth_service) instead of the services package
# which eagerly loads everything via __init__.py.
# ============================================================

_STUB_MODULES = [
    "gspread",
    "google.ads",
    "google.analytics",
    "google.analytics.data_v1beta",
    "google.cloud",
    "google.cloud.vision",
    "google.cloud.vision_v1",
    "google.oauth2.service_account",
    "flask",
    "flask_cors",
    "flask_login",
    "flask_sqlalchemy",
    "anthropic",
    "openai",
    "retell",
    "retell.lib",
    "retell.lib.webhook_auth",
    "dotenv",
    "brevo_python",
    "brevo_python.rest",
    "sentry_sdk",
    "playwright",
    "playwright.async_api",
    "PIL",
    "pdfplumber",
    "pytesseract",
    "cv2",
    "pytz",
]

for _mod in _STUB_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()


# ============================================================
# Environment fixtures
# ============================================================

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Set safe default environment variables for all tests."""
    defaults = {
        "DATABASE_URL": "postgresql://test@localhost:5432/test_careassist",
        "GOOGLE_CLIENT_ID": "test-client-id",
        "GOOGLE_CLIENT_SECRET": "test-client-secret",
        "GOOGLE_REDIRECT_URI": "http://localhost:8765/auth/callback",
        "APP_SECRET_KEY": "test-secret-key-for-unit-tests-only",
        "ALLOWED_DOMAINS": "coloradocareassist.com,test.com",
        "ENVIRONMENT": "test",
        "PORTAL_SECRET": "test-portal-secret",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "GIGI_API_TOKEN": "test-gigi-token",
        "GIGI_LLM_PROVIDER": "anthropic",
        "GIGI_LLM_MODEL": "claude-haiku-4-5-20251001",
    }
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)


# ============================================================
# Database fixtures
# ============================================================

@pytest.fixture
def mock_db_connection():
    """Mock psycopg2 connection that records queries without touching a real DB."""
    conn = MagicMock()
    cursor = MagicMock()

    # cursor context manager
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)

    # conn.cursor() returns the mock cursor
    conn.cursor.return_value = cursor

    # context manager support
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    return conn, cursor


@pytest.fixture
def mock_psycopg2(mock_db_connection):
    """Patch psycopg2.connect to return the mock connection."""
    conn, cursor = mock_db_connection
    with patch("psycopg2.connect", return_value=conn) as mock_connect:
        yield mock_connect, conn, cursor


# ============================================================
# Time fixtures
# ============================================================

@pytest.fixture
def weekday_morning():
    """A Monday at 7:30 AM."""
    return datetime(2026, 3, 2, 7, 30, 0)  # Monday


@pytest.fixture
def weekday_business_hours():
    """A Tuesday at 10:00 AM."""
    return datetime(2026, 3, 3, 10, 0, 0)  # Tuesday


@pytest.fixture
def weekday_evening():
    """A Wednesday at 7:00 PM."""
    return datetime(2026, 3, 4, 19, 0, 0)  # Wednesday


@pytest.fixture
def weekend():
    """A Saturday at noon."""
    return datetime(2026, 3, 7, 12, 0, 0)  # Saturday


@pytest.fixture
def late_night():
    """A Thursday at 11:30 PM."""
    return datetime(2026, 3, 5, 23, 30, 0)  # Thursday

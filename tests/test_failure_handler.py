"""
Unit tests for gigi/failure_handler.py

Covers:
- Failure type/severity/action enums
- Tool failure classification (critical vs non-critical)
- Low confidence action selection by bracket
- Meltdown detection threshold logic
- safe_tool_call wrapper
- Conflicting instructions handling
- Missing context handling
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from gigi.failure_handler import (
    FailureAction,
    FailureHandler,
    FailureSeverity,
    FailureType,
    safe_tool_call,
)


# ============================================================
# Enum tests
# ============================================================

class TestFailureEnums:
    def test_failure_types_count(self):
        """Should have exactly 10 failure types matching the protocol."""
        assert len(FailureType) == 10

    def test_severity_levels(self):
        assert FailureSeverity.INFO.value == "info"
        assert FailureSeverity.WARNING.value == "warning"
        assert FailureSeverity.ERROR.value == "error"
        assert FailureSeverity.CRITICAL.value == "critical"

    def test_action_types(self):
        assert FailureAction.CONTINUE.value == "continue"
        assert FailureAction.DEGRADE.value == "degrade"
        assert FailureAction.ASK_USER.value == "ask_user"
        assert FailureAction.ESCALATE.value == "escalate"
        assert FailureAction.ABORT.value == "abort"


# ============================================================
# Handler construction
# ============================================================

def _make_handler(mock_psycopg2):
    """Create a FailureHandler with mocked DB."""
    mock_connect, conn, cursor = mock_psycopg2
    handler = FailureHandler.__new__(FailureHandler)
    handler.database_url = "postgresql://test@localhost/test"
    handler.recent_failures = []
    handler.meltdown_threshold = 3
    handler.meltdown_window = timedelta(minutes=5)
    return handler


# ============================================================
# Tool failure classification tests
# ============================================================

class TestToolFailureClassification:
    """handle_tool_failure should classify tools as critical or non-critical."""

    def test_wellsky_is_critical(self, mock_psycopg2):
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-failure-id",)
        # Mock detect_meltdown to avoid DB call
        handler.detect_meltdown = MagicMock(return_value=False)

        action, msg = handler.handle_tool_failure(
            tool_name="wellsky",
            error=ConnectionError("API timeout"),
        )

        assert action == FailureAction.ESCALATE
        assert "not responding" in msg

    def test_ringcentral_is_critical(self, mock_psycopg2):
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-failure-id",)
        handler.detect_meltdown = MagicMock(return_value=False)

        action, msg = handler.handle_tool_failure(
            tool_name="ringcentral",
            error=TimeoutError("Connection reset"),
        )

        assert action == FailureAction.ESCALATE

    def test_non_critical_tool_degrades(self, mock_psycopg2):
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-failure-id",)
        handler.detect_meltdown = MagicMock(return_value=False)

        action, msg = handler.handle_tool_failure(
            tool_name="weather_api",
            error=ConnectionError("DNS error"),
        )

        assert action == FailureAction.DEGRADE
        assert "limited functionality" in msg


# ============================================================
# Low confidence action selection tests
# ============================================================

class TestLowConfidenceActions:
    """handle_low_confidence should select actions by confidence bracket."""

    def test_very_low_confidence_aborts(self, mock_psycopg2):
        """Confidence < 0.3 should abort."""
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-failure-id",)

        action, msg = handler.handle_low_confidence(
            action="book a flight",
            confidence=0.2,
        )

        assert action == FailureAction.ABORT
        assert "not confident enough" in msg

    def test_medium_low_confidence_asks_user(self, mock_psycopg2):
        """Confidence 0.3-0.6 should ask user."""
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-failure-id",)

        action, msg = handler.handle_low_confidence(
            action="send an email",
            confidence=0.45,
        )

        assert action == FailureAction.ASK_USER
        assert "45%" in msg

    def test_marginal_confidence_continues(self, mock_psycopg2):
        """Confidence >= 0.6 should continue with warning."""
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-failure-id",)

        action, msg = handler.handle_low_confidence(
            action="schedule a meeting",
            confidence=0.7,
        )

        assert action == FailureAction.CONTINUE
        assert "70%" in msg

    def test_boundary_0_3(self, mock_psycopg2):
        """Exactly 0.3 should ask user (not abort)."""
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-failure-id",)

        action, _ = handler.handle_low_confidence(
            action="test boundary",
            confidence=0.3,
        )

        assert action == FailureAction.ASK_USER

    def test_boundary_0_6(self, mock_psycopg2):
        """Exactly 0.6 should continue (not ask)."""
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-failure-id",)

        action, _ = handler.handle_low_confidence(
            action="test boundary",
            confidence=0.6,
        )

        assert action == FailureAction.CONTINUE


# ============================================================
# Meltdown detection tests
# ============================================================

class TestMeltdownDetection:
    """detect_meltdown should trigger at 3 failures in 5 minutes."""

    def test_no_meltdown_below_threshold(self, mock_psycopg2):
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = (2,)  # 2 failures — below threshold

        result = handler.detect_meltdown()
        assert result is False

    def test_meltdown_at_threshold(self, mock_psycopg2):
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = (3,)  # Exactly at threshold

        result = handler.detect_meltdown()
        assert result is True

    def test_meltdown_above_threshold(self, mock_psycopg2):
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = (10,)  # Well above

        result = handler.detect_meltdown()
        assert result is True

    def test_meltdown_fallback_on_db_error(self, mock_psycopg2):
        """When DB fails, should fall back to in-memory tracking."""
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2

        # Make the DB query fail
        conn.cursor.side_effect = Exception("DB down")

        # Add 3 recent failures in-memory
        now = datetime.now()
        handler.recent_failures = [
            now - timedelta(minutes=1),
            now - timedelta(minutes=2),
            now - timedelta(minutes=3),
        ]

        result = handler.detect_meltdown()
        assert result is True

    def test_meltdown_fallback_clears_old(self, mock_psycopg2):
        """In-memory fallback should clear failures outside the window."""
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        conn.cursor.side_effect = Exception("DB down")

        # Old failures outside the 5-minute window
        old = datetime.now() - timedelta(minutes=10)
        handler.recent_failures = [old, old, old]

        result = handler.detect_meltdown()
        assert result is False


# ============================================================
# Conflicting instructions tests
# ============================================================

class TestConflictingInstructions:
    def test_returns_ask_user(self, mock_psycopg2):
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-failure-id",)

        action, msg = handler.handle_conflicting_instructions(
            instruction1="Always book direct flights",
            instruction2="Book cheapest option (has layover)",
        )

        assert action == FailureAction.ASK_USER
        assert "conflicting" in msg.lower()
        assert "direct flights" in msg
        assert "cheapest" in msg


# ============================================================
# Missing context tests
# ============================================================

class TestMissingContext:
    def test_returns_ask_user_with_needed_info(self, mock_psycopg2):
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-failure-id",)

        action, msg = handler.handle_missing_context(
            action="schedule caregiver visit",
            missing_info=["client name", "preferred time"],
        )

        assert action == FailureAction.ASK_USER
        assert "client name" in msg
        assert "preferred time" in msg


# ============================================================
# safe_tool_call wrapper tests
# ============================================================

class TestSafeToolCall:
    def test_success_path(self, mock_psycopg2):
        handler = _make_handler(mock_psycopg2)

        def add(a, b):
            return a + b

        success, result, error_msg = safe_tool_call(handler, "add_tool", add, 2, 3)

        assert success is True
        assert result == 5
        assert error_msg is None

    def test_failure_path(self, mock_psycopg2):
        handler = _make_handler(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-failure-id",)
        handler.detect_meltdown = MagicMock(return_value=False)

        def fail():
            raise ValueError("Something broke")

        success, result, error_msg = safe_tool_call(handler, "broken_tool", fail)

        assert success is False
        assert result is None
        assert error_msg is not None

"""
Unit tests for gigi/mode_detector.py

Covers:
- Time-based mode inference (weekday/weekend, time of day)
- Context-based mode detection from keywords
- Mode command parsing
- Behavior config for all 8 modes
"""

from datetime import datetime, time, timedelta
from unittest.mock import patch

import pytest

from gigi.mode_detector import (
    ModeDetector,
    ModeSource,
    OperatingMode,
    parse_mode_command,
)


# ============================================================
# Time-based inference tests
# ============================================================

class TestTimeBasedModeInference:
    """_infer_mode_from_time should select mode based on time and day."""

    def _make_detector(self):
        """Create a ModeDetector without DB."""
        detector = ModeDetector.__new__(ModeDetector)
        detector.database_url = "postgresql://test@localhost/test"
        return detector

    def test_weekday_early_morning_is_focus(self):
        detector = self._make_detector()
        # Monday 7:30 AM
        with patch("gigi.mode_detector.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 2, 7, 30)
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            result = detector._infer_mode_from_time()
        assert result.mode == OperatingMode.FOCUS
        assert result.source == ModeSource.TIME_BASED
        assert result.confidence == 0.7

    def test_weekday_business_hours_is_execution(self):
        detector = self._make_detector()
        with patch("gigi.mode_detector.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 3, 10, 0)
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            result = detector._infer_mode_from_time()
        assert result.mode == OperatingMode.EXECUTION
        assert result.confidence == 0.8

    def test_weekday_evening_is_decision(self):
        detector = self._make_detector()
        with patch("gigi.mode_detector.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 4, 19, 0)
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            result = detector._infer_mode_from_time()
        assert result.mode == OperatingMode.DECISION
        assert result.confidence == 0.6

    def test_late_night_is_off_grid(self):
        detector = self._make_detector()
        with patch("gigi.mode_detector.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 5, 23, 30)
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            result = detector._infer_mode_from_time()
        assert result.mode == OperatingMode.OFF_GRID
        assert result.confidence == 0.7

    def test_weekend_is_review(self):
        detector = self._make_detector()
        with patch("gigi.mode_detector.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 7, 12, 0)  # Saturday
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            result = detector._infer_mode_from_time()
        assert result.mode == OperatingMode.REVIEW
        assert result.confidence == 0.6

    def test_sunday_is_also_review(self):
        detector = self._make_detector()
        with patch("gigi.mode_detector.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 8, 14, 0)  # Sunday
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            result = detector._infer_mode_from_time()
        assert result.mode == OperatingMode.REVIEW

    def test_early_morning_boundary_6am(self):
        detector = self._make_detector()
        with patch("gigi.mode_detector.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 2, 6, 0)  # Exactly 6 AM Monday
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            result = detector._infer_mode_from_time()
        assert result.mode == OperatingMode.FOCUS

    def test_before_6am_is_off_grid(self):
        detector = self._make_detector()
        with patch("gigi.mode_detector.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 2, 5, 59)  # 5:59 AM Monday
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            result = detector._infer_mode_from_time()
        assert result.mode == OperatingMode.OFF_GRID


# ============================================================
# Context-based detection tests
# ============================================================

class TestContextDetection:
    def _make_detector(self):
        detector = ModeDetector.__new__(ModeDetector)
        detector.database_url = "postgresql://test@localhost/test"
        return detector

    def test_crisis_keywords(self):
        detector = self._make_detector()
        crisis_texts = [
            "This is an emergency!",
            "URGENT: server is down",
            "Crisis in the office",
            "Critical patient situation",
            "Need this ASAP",
            "Server is down immediately",
        ]
        for text in crisis_texts:
            mode, confidence = detector.detect_mode_from_context(text)
            assert mode == OperatingMode.CRISIS, f"Failed for: {text}"
            assert confidence == 0.9

    def test_travel_keywords(self):
        detector = self._make_detector()
        mode, conf = detector.detect_mode_from_context("I'm at the airport heading to NYC")
        assert mode == OperatingMode.TRAVEL
        assert conf == 0.7

    def test_off_grid_keywords(self):
        detector = self._make_detector()
        mode, conf = detector.detect_mode_from_context("Going on vacation next week")
        assert mode == OperatingMode.OFF_GRID
        assert conf == 0.8

    def test_focus_keywords(self):
        detector = self._make_detector()
        mode, conf = detector.detect_mode_from_context("I need to focus on this report")
        assert mode == OperatingMode.FOCUS
        assert conf == 0.7

    def test_review_keywords(self):
        detector = self._make_detector()
        mode, conf = detector.detect_mode_from_context("Let's do a monthly review")
        assert mode == OperatingMode.REVIEW
        assert conf == 0.6

    def test_no_signal(self):
        detector = self._make_detector()
        mode, conf = detector.detect_mode_from_context("What's for lunch?")
        assert mode is None
        assert conf == 0.0

    def test_case_insensitive(self):
        detector = self._make_detector()
        mode, _ = detector.detect_mode_from_context("EMERGENCY SITUATION")
        assert mode == OperatingMode.CRISIS


# ============================================================
# Behavior config tests
# ============================================================

class TestBehaviorConfig:
    def _make_detector(self):
        detector = ModeDetector.__new__(ModeDetector)
        detector.database_url = "postgresql://test@localhost/test"
        return detector

    def test_all_modes_have_config(self):
        """Every OperatingMode should have a behavior config."""
        detector = self._make_detector()
        for mode in OperatingMode:
            config = detector.get_mode_behavior_config(mode)
            assert "interrupt_threshold" in config, f"{mode.value} missing interrupt_threshold"
            assert "response_style" in config, f"{mode.value} missing response_style"
            assert "response_delay" in config, f"{mode.value} missing response_delay"
            assert "auto_actions" in config, f"{mode.value} missing auto_actions"
            assert "escalation_rules" in config, f"{mode.value} missing escalation_rules"
            assert "tone" in config, f"{mode.value} missing tone"

    def test_crisis_has_immediate_response(self):
        detector = self._make_detector()
        config = detector.get_mode_behavior_config(OperatingMode.CRISIS)
        assert config["response_delay"] == "immediate"
        assert config["interrupt_threshold"] == "none"

    def test_off_grid_holds_messages(self):
        detector = self._make_detector()
        config = detector.get_mode_behavior_config(OperatingMode.OFF_GRID)
        assert config["response_delay"] == "hold"
        assert config["interrupt_threshold"] == "crisis_only"

    def test_focus_batches_responses(self):
        detector = self._make_detector()
        config = detector.get_mode_behavior_config(OperatingMode.FOCUS)
        assert config["response_delay"] == "batch"


# ============================================================
# Mode command parsing tests
# ============================================================

class TestModeCommandParsing:
    def test_focus_command(self):
        result = parse_mode_command("Set mode to focus")
        assert result is not None
        mode, expires = result
        assert mode == OperatingMode.FOCUS

    def test_crisis_command(self):
        result = parse_mode_command("I'm in crisis mode")
        assert result is not None
        mode, _ = result
        assert mode == OperatingMode.CRISIS

    def test_off_grid_variants(self):
        for text in ["Going off-grid", "off grid for a bit", "offgrid time"]:
            result = parse_mode_command(text)
            assert result is not None, f"Failed for: {text}"
            mode, _ = result
            assert mode == OperatingMode.OFF_GRID

    def test_travel_with_duration(self):
        result = parse_mode_command("Switch to travel mode until Friday")
        assert result is not None
        mode, expires = result
        assert mode == OperatingMode.TRAVEL
        assert expires is not None  # Should set a 24h expiration

    def test_no_command_returns_none(self):
        result = parse_mode_command("What's the weather like?")
        assert result is None

    def test_execution_command(self):
        result = parse_mode_command("Back to execution mode")
        assert result is not None
        mode, _ = result
        assert mode == OperatingMode.EXECUTION

    def test_case_insensitive(self):
        result = parse_mode_command("CRISIS MODE NOW")
        assert result is not None
        mode, _ = result
        assert mode == OperatingMode.CRISIS

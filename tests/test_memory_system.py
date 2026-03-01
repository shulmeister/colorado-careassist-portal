"""
Unit tests for gigi/memory_system.py

Covers:
- Confidence clamping per memory type
- Max confidence by type
- Conflict detection logic
- Memory dataclass construction
- Enum values
"""

import pytest

from gigi.memory_system import (
    ImpactLevel,
    MemorySource,
    MemoryStatus,
    MemorySystem,
    MemoryType,
)


# ============================================================
# Enum value tests
# ============================================================

class TestMemoryEnums:
    """Verify enum values match what the DB stores."""

    def test_memory_types(self):
        assert MemoryType.EXPLICIT_INSTRUCTION.value == "explicit_instruction"
        assert MemoryType.CORRECTION.value == "correction"
        assert MemoryType.CONFIRMED_PATTERN.value == "confirmed_pattern"
        assert MemoryType.INFERRED_PATTERN.value == "inferred_pattern"
        assert MemoryType.SINGLE_INFERENCE.value == "single_inference"
        assert MemoryType.TEMPORARY.value == "temporary"
        assert MemoryType.FACT.value == "fact"

    def test_memory_status(self):
        assert MemoryStatus.ACTIVE.value == "active"
        assert MemoryStatus.INACTIVE.value == "inactive"
        assert MemoryStatus.ARCHIVED.value == "archived"

    def test_impact_levels(self):
        assert ImpactLevel.HIGH.value == "high"
        assert ImpactLevel.MEDIUM.value == "medium"
        assert ImpactLevel.LOW.value == "low"


# ============================================================
# Confidence clamping tests
# ============================================================

class TestConfidenceClamping:
    """Test that create_memory clamps confidence per type rules."""

    def _make_system(self, mock_psycopg2):
        """Create a MemorySystem with mocked DB."""
        mock_connect, conn, cursor = mock_psycopg2
        # Bypass schema init
        MemorySystem._schema_initialized = True
        system = MemorySystem.__new__(MemorySystem)
        system.database_url = "postgresql://test@localhost/test"
        return system

    def test_explicit_instruction_always_1(self, mock_psycopg2):
        """EXPLICIT_INSTRUCTION should always be clamped to 1.0."""
        system = self._make_system(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-uuid-123",)

        system.create_memory(
            content="Test instruction",
            memory_type=MemoryType.EXPLICIT_INSTRUCTION,
            source=MemorySource.EXPLICIT,
            confidence=0.5,  # Should be overridden to 1.0
            category="test",
            impact_level=ImpactLevel.HIGH,
        )

        # Check the INSERT call's confidence parameter
        insert_call = cursor.execute.call_args_list[-2]  # -2 because -1 is the audit log
        args = insert_call[0][1]  # positional args tuple
        confidence_arg = args[2]  # (type, content, confidence, ...)
        assert confidence_arg == 1.0

    def test_fact_always_1(self, mock_psycopg2):
        """FACT (legacy) should always be clamped to 1.0."""
        system = self._make_system(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-uuid-456",)

        system.create_memory(
            content="Legacy fact",
            memory_type=MemoryType.FACT,
            source=MemorySource.EXPLICIT,
            confidence=0.3,
            category="test",
            impact_level=ImpactLevel.LOW,
        )

        insert_call = cursor.execute.call_args_list[-2]
        args = insert_call[0][1]
        assert args[2] == 1.0

    def test_correction_capped_at_0_9(self, mock_psycopg2):
        """CORRECTION should be capped at 0.9."""
        system = self._make_system(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-uuid",)

        system.create_memory(
            content="Correction test",
            memory_type=MemoryType.CORRECTION,
            source=MemorySource.CORRECTION,
            confidence=0.95,  # Should be capped to 0.9
            category="test",
            impact_level=ImpactLevel.MEDIUM,
        )

        insert_call = cursor.execute.call_args_list[-2]
        args = insert_call[0][1]
        assert args[2] == 0.9

    def test_inferred_pattern_capped_at_0_7(self, mock_psycopg2):
        """INFERRED_PATTERN should be capped at 0.7."""
        system = self._make_system(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-uuid",)

        system.create_memory(
            content="Pattern test",
            memory_type=MemoryType.INFERRED_PATTERN,
            source=MemorySource.PATTERN,
            confidence=0.9,
            category="test",
            impact_level=ImpactLevel.LOW,
        )

        insert_call = cursor.execute.call_args_list[-2]
        args = insert_call[0][1]
        assert args[2] == 0.7

    def test_single_inference_capped_at_0_5(self, mock_psycopg2):
        """SINGLE_INFERENCE should be capped at 0.5."""
        system = self._make_system(mock_psycopg2)
        mock_connect, conn, cursor = mock_psycopg2
        cursor.fetchone.return_value = ("fake-uuid",)

        system.create_memory(
            content="Inference test",
            memory_type=MemoryType.SINGLE_INFERENCE,
            source=MemorySource.INFERENCE,
            confidence=0.8,
            category="test",
            impact_level=ImpactLevel.LOW,
        )

        insert_call = cursor.execute.call_args_list[-2]
        args = insert_call[0][1]
        assert args[2] == 0.5


# ============================================================
# Max confidence lookup tests
# ============================================================

class TestMaxConfidence:
    def _make_system(self):
        MemorySystem._schema_initialized = True
        system = MemorySystem.__new__(MemorySystem)
        system.database_url = "postgresql://test@localhost/test"
        return system

    def test_max_confidence_values(self):
        system = self._make_system()
        assert system._get_max_confidence(MemoryType.EXPLICIT_INSTRUCTION) == 1.0
        assert system._get_max_confidence(MemoryType.FACT) == 1.0
        assert system._get_max_confidence(MemoryType.CORRECTION) == 0.9
        assert system._get_max_confidence(MemoryType.CONFIRMED_PATTERN) == 0.9
        assert system._get_max_confidence(MemoryType.INFERRED_PATTERN) == 0.7
        assert system._get_max_confidence(MemoryType.SINGLE_INFERENCE) == 0.5
        assert system._get_max_confidence(MemoryType.TEMPORARY) == 0.5


# ============================================================
# Conflict detection tests
# ============================================================

class TestConflictDetection:
    def _make_system(self):
        MemorySystem._schema_initialized = True
        system = MemorySystem.__new__(MemorySystem)
        system.database_url = "postgresql://test@localhost/test"
        return system

    def test_always_never_conflict(self):
        system = self._make_system()
        assert system._might_conflict(
            "Always book direct flights",
            "Never book direct flights"
        ) is True

    def test_prefer_avoid_conflict(self):
        system = self._make_system()
        assert system._might_conflict(
            "Prefer United Airlines",
            "Avoid United Airlines"
        ) is True

    def test_yes_no_conflict(self):
        system = self._make_system()
        assert system._might_conflict(
            "Yes to morning meetings",
            "No morning meetings"
        ) is True

    def test_include_exclude_conflict(self):
        system = self._make_system()
        assert system._might_conflict(
            "Include allergies in care plan",
            "Exclude allergies from care plan"
        ) is True

    def test_no_conflict(self):
        system = self._make_system()
        assert system._might_conflict(
            "Client prefers morning shifts",
            "Caregiver available on weekends"
        ) is False

    def test_case_insensitive(self):
        system = self._make_system()
        assert system._might_conflict(
            "ALWAYS use formal greetings",
            "NEVER use formal greetings"
        ) is True

"""
Unit tests for gigi/conversation_store.py

Covers:
- Token estimation
- Leading non-user message stripping
- Cross-channel summary formatting
"""

import pytest

from gigi.conversation_store import CHARS_PER_TOKEN, ConversationStore


# ============================================================
# Token estimation tests
# ============================================================

class TestTokenEstimation:
    def _make_store(self):
        """Create a ConversationStore without DB init."""
        ConversationStore._table_ensured = True
        store = ConversationStore.__new__(ConversationStore)
        store.database_url = "postgresql://test@localhost/test"
        return store

    def test_empty_messages(self):
        store = self._make_store()
        assert store.estimate_tokens([]) == 0

    def test_single_message(self):
        store = self._make_store()
        # 20 chars / 4 chars_per_token = 5 tokens
        messages = [{"content": "Hello, how are you?!"}]  # 20 chars
        result = store.estimate_tokens(messages)
        assert result == 20 // CHARS_PER_TOKEN

    def test_multiple_messages(self):
        store = self._make_store()
        messages = [
            {"content": "Hi"},        # 2 chars
            {"content": "How are you"},  # 11 chars
        ]
        result = store.estimate_tokens(messages)
        assert result == 13 // CHARS_PER_TOKEN

    def test_missing_content_key(self):
        store = self._make_store()
        messages = [{"role": "user"}]  # no content key
        assert store.estimate_tokens(messages) == 0

    def test_chars_per_token_constant(self):
        """CHARS_PER_TOKEN should be 4."""
        assert CHARS_PER_TOKEN == 4

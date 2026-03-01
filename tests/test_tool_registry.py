"""
Unit tests for gigi/tool_registry.py

Covers:
- No duplicate tool names in CANONICAL_TOOLS
- Channel filtering correctness (SMS, voice, telegram, dm)
- Tool count expectations per channel
- Every tool has required schema fields
- SMS_EXCLUDE and VOICE_EXCLUDE sets
"""

import pytest

from gigi.tool_registry import (
    CANONICAL_TOOLS,
    SMS_EXCLUDE,
    VOICE_EXCLUDE,
    get_tools,
)


# ============================================================
# CANONICAL_TOOLS integrity tests
# ============================================================

class TestCanonicalTools:
    def test_no_duplicate_names(self):
        """Every tool name must be unique."""
        names = [t["name"] for t in CANONICAL_TOOLS]
        duplicates = [n for n in names if names.count(n) > 1]
        assert duplicates == [], f"Duplicate tool names: {set(duplicates)}"

    def test_all_tools_have_required_fields(self):
        """Every tool must have name, description, and input_schema."""
        for tool in CANONICAL_TOOLS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool {tool['name']} missing 'description'"
            assert "input_schema" in tool, f"Tool {tool['name']} missing 'input_schema'"

    def test_all_input_schemas_have_type(self):
        """Every input_schema must have a 'type' field."""
        for tool in CANONICAL_TOOLS:
            schema = tool["input_schema"]
            assert "type" in schema, f"Tool {tool['name']} input_schema missing 'type'"
            assert schema["type"] == "object", f"Tool {tool['name']} input_schema type should be 'object'"

    def test_all_input_schemas_have_properties(self):
        """Every input_schema must have a 'properties' field."""
        for tool in CANONICAL_TOOLS:
            schema = tool["input_schema"]
            assert "properties" in schema, f"Tool {tool['name']} input_schema missing 'properties'"

    def test_required_is_list(self):
        """Every input_schema 'required' field must be a list."""
        for tool in CANONICAL_TOOLS:
            schema = tool["input_schema"]
            if "required" in schema:
                assert isinstance(schema["required"], list), \
                    f"Tool {tool['name']} 'required' should be a list"

    def test_tool_names_are_snake_case(self):
        """Tool names should follow snake_case convention."""
        for tool in CANONICAL_TOOLS:
            name = tool["name"]
            assert name == name.lower(), f"Tool name '{name}' is not lowercase"
            assert " " not in name, f"Tool name '{name}' contains spaces"

    def test_minimum_tool_count(self):
        """Should have at least 80 canonical tools."""
        assert len(CANONICAL_TOOLS) >= 80, \
            f"Expected 80+ tools, got {len(CANONICAL_TOOLS)}"


# ============================================================
# Channel filtering tests
# ============================================================

class TestChannelFiltering:
    def test_telegram_gets_all_tools(self):
        """Telegram channel should get all canonical tools."""
        tools = get_tools("telegram")
        assert len(tools) == len(CANONICAL_TOOLS)

    def test_dm_gets_all_tools(self):
        """DM channel should get all canonical tools."""
        tools = get_tools("dm")
        assert len(tools) == len(CANONICAL_TOOLS)

    def test_sms_excludes_correct_tools(self):
        """SMS channel should exclude the SMS_EXCLUDE set."""
        sms_tools = get_tools("sms")
        sms_names = {t["name"] for t in sms_tools}

        # No excluded tool should be in SMS
        for excluded in SMS_EXCLUDE:
            assert excluded not in sms_names, \
                f"Excluded tool '{excluded}' found in SMS tools"

        # SMS should have fewer tools than full set
        assert len(sms_tools) < len(CANONICAL_TOOLS)
        assert len(sms_tools) == len(CANONICAL_TOOLS) - len(
            SMS_EXCLUDE & {t["name"] for t in CANONICAL_TOOLS}
        )

    def test_voice_excludes_correct_tools(self):
        """Voice channel should exclude the VOICE_EXCLUDE set."""
        voice_tools = get_tools("voice")
        voice_names = {t["name"] for t in voice_tools}

        for excluded in VOICE_EXCLUDE:
            assert excluded not in voice_names, \
                f"Excluded tool '{excluded}' found in voice tools"

    def test_unknown_channel_gets_all_tools(self):
        """Unknown channel should default to all tools."""
        tools = get_tools("unknown_channel")
        assert len(tools) == len(CANONICAL_TOOLS)

    def test_sms_exclude_tools_exist_in_canonical(self):
        """All SMS_EXCLUDE names should reference actual tools."""
        canonical_names = {t["name"] for t in CANONICAL_TOOLS}
        for excluded in SMS_EXCLUDE:
            assert excluded in canonical_names, \
                f"SMS_EXCLUDE references non-existent tool: '{excluded}'"

    def test_voice_exclude_tools_exist_in_canonical(self):
        """All VOICE_EXCLUDE names should reference actual tools."""
        canonical_names = {t["name"] for t in CANONICAL_TOOLS}
        for excluded in VOICE_EXCLUDE:
            assert excluded in canonical_names, \
                f"VOICE_EXCLUDE references non-existent tool: '{excluded}'"

    def test_get_tools_returns_copies(self):
        """get_tools should return a new list (not mutate CANONICAL_TOOLS)."""
        tools1 = get_tools("telegram")
        tools2 = get_tools("telegram")
        assert tools1 is not tools2
        assert tools1 is not CANONICAL_TOOLS

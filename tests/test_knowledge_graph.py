"""
Unit tests for gigi/knowledge_graph.py

Covers:
- _parse_list_param (JSON string/list parsing)
- update_knowledge_graph action routing and validation
- query_knowledge_graph action routing and validation
- _entity_to_dict conversion
"""

import json

import pytest

from gigi.knowledge_graph import _parse_list_param, _entity_to_dict


# ============================================================
# _parse_list_param tests
# ============================================================

class TestParseListParam:
    """Test the parameter parsing that handles Gemini's JSON string quirk."""

    def test_already_a_list_of_dicts(self):
        """Lists of dicts should pass through unchanged."""
        data = [{"name": "Alice", "entityType": "person"}]
        assert _parse_list_param(data) == data

    def test_json_string_of_list(self):
        """JSON string containing a list should be parsed."""
        data = '[{"name": "Bob", "entityType": "person"}]'
        result = _parse_list_param(data)
        assert isinstance(result, list)
        assert result[0]["name"] == "Bob"

    def test_list_of_json_strings(self):
        """List containing JSON string items should parse each item."""
        data = ['{"name": "Charlie", "entityType": "org"}']
        result = _parse_list_param(data)
        assert isinstance(result, list)
        assert result[0]["name"] == "Charlie"

    def test_non_list_json_string_returns_none(self):
        """JSON string that's not a list should return None."""
        assert _parse_list_param('{"not": "a list"}') is None

    def test_invalid_json_string_returns_none(self):
        """Invalid JSON string should return None."""
        assert _parse_list_param("not json at all") is None

    def test_none_returns_none(self):
        """None input should return None."""
        assert _parse_list_param(None) is None

    def test_empty_list(self):
        """Empty list should pass through."""
        assert _parse_list_param([]) == []

    def test_empty_json_list_string(self):
        """Empty JSON list string should parse to empty list."""
        assert _parse_list_param("[]") == []

    def test_nested_json_strings(self):
        """JSON string containing list of JSON strings should parse recursively."""
        inner = json.dumps({"name": "Nested", "entityType": "test"})
        outer = json.dumps([inner])
        result = _parse_list_param(outer)
        assert result[0]["name"] == "Nested"

    def test_mixed_list(self):
        """List with mix of dicts and strings should parse strings."""
        data = [
            {"name": "Direct"},
            json.dumps({"name": "Stringified"}),
        ]
        result = _parse_list_param(data)
        assert result[0]["name"] == "Direct"
        assert result[1]["name"] == "Stringified"

    def test_non_parseable_strings_kept_as_is(self):
        """Non-JSON strings in a list should be kept as-is."""
        data = ["just a name"]
        result = _parse_list_param(data)
        assert result == ["just a name"]


# ============================================================
# _entity_to_dict tests
# ============================================================

class TestEntityToDict:
    def test_basic_conversion(self):
        row = ("Alice Smith", "person", ["client since 2025", "prefers mornings"])
        result = _entity_to_dict(row)
        assert result["name"] == "Alice Smith"
        assert result["entityType"] == "person"
        assert len(result["observations"]) == 2

    def test_null_observations(self):
        row = ("Org Corp", "organization", None)
        result = _entity_to_dict(row)
        assert result["observations"] == []

    def test_empty_observations(self):
        row = ("Place", "location", [])
        result = _entity_to_dict(row)
        assert result["observations"] == []


# ============================================================
# Async API action routing tests
# ============================================================

class TestUpdateKnowledgeGraph:
    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self):
        from gigi.knowledge_graph import update_knowledge_graph
        result = await update_knowledge_graph(action="bad_action")
        assert "error" in result
        assert "Unknown action" in result["error"]

    @pytest.mark.asyncio
    async def test_add_entities_requires_entities(self):
        from gigi.knowledge_graph import update_knowledge_graph
        result = await update_knowledge_graph(action="add_entities", entities=None)
        assert "error" in result
        assert "entities required" in result["error"]

    @pytest.mark.asyncio
    async def test_add_relations_requires_relations(self):
        from gigi.knowledge_graph import update_knowledge_graph
        result = await update_knowledge_graph(action="add_relations", relations=None)
        assert "error" in result
        assert "relations required" in result["error"]

    @pytest.mark.asyncio
    async def test_add_observations_requires_observations(self):
        from gigi.knowledge_graph import update_knowledge_graph
        result = await update_knowledge_graph(action="add_observations", observations=None)
        assert "error" in result
        assert "observations required" in result["error"]

    @pytest.mark.asyncio
    async def test_delete_entities_requires_names(self):
        from gigi.knowledge_graph import update_knowledge_graph
        result = await update_knowledge_graph(action="delete_entities", entity_names=None)
        assert "error" in result
        assert "entity_names required" in result["error"]

    @pytest.mark.asyncio
    async def test_delete_relations_requires_relations(self):
        from gigi.knowledge_graph import update_knowledge_graph
        result = await update_knowledge_graph(action="delete_relations", relations=None)
        assert "error" in result
        assert "relations required" in result["error"]

    @pytest.mark.asyncio
    async def test_delete_observations_requires_deletions(self):
        from gigi.knowledge_graph import update_knowledge_graph
        result = await update_knowledge_graph(action="delete_observations", deletions=None)
        assert "error" in result
        assert "deletions required" in result["error"]

    @pytest.mark.asyncio
    async def test_action_whitespace_handled(self):
        from gigi.knowledge_graph import update_knowledge_graph
        result = await update_knowledge_graph(action="  ADD_ENTITIES  ", entities=None)
        assert "error" in result
        assert "entities required" in result["error"]


class TestQueryKnowledgeGraph:
    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self):
        from gigi.knowledge_graph import query_knowledge_graph
        result = await query_knowledge_graph(action="bad_action")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_requires_query(self):
        from gigi.knowledge_graph import query_knowledge_graph
        result = await query_knowledge_graph(action="search", query=None)
        assert "error" in result
        assert "query required" in result["error"]

    @pytest.mark.asyncio
    async def test_open_nodes_requires_names(self):
        from gigi.knowledge_graph import query_knowledge_graph
        result = await query_knowledge_graph(action="open_nodes", names=None)
        assert "error" in result
        assert "names required" in result["error"]

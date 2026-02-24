"""
Knowledge Graph for Gigi — PostgreSQL-backed entity-relation graph.

Stores structured knowledge about people, organizations, places, and
their connections. Complements the flat memory system (gigi_memories)
with relationship-aware queries.

Tables: gigi_kg_entities, gigi_kg_relations
All functions are ASYNC. All functions return dicts.
"""

import json
import logging
import os
from typing import Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger("gigi.knowledge_graph")

DB_URL = os.getenv("DATABASE_URL", "postgresql://careassist:careassist2026@localhost:5432/careassist")


def _conn():
    """Get a database connection."""
    return psycopg2.connect(DB_URL)


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def _create_entities(entities: list[dict]) -> list[dict]:
    """Create entities, skipping duplicates. Returns newly created."""
    conn = _conn()
    created = []
    try:
        cur = conn.cursor()
        for e in entities:
            name = e.get("name", "").strip()
            entity_type = e.get("entityType", "").strip()
            observations = e.get("observations", [])
            if not name or not entity_type:
                continue
            try:
                cur.execute("""
                    INSERT INTO gigi_kg_entities (name, entity_type, observations)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO NOTHING
                    RETURNING name
                """, (name, entity_type, observations))
                row = cur.fetchone()
                if row:
                    created.append({"name": name, "entityType": entity_type, "observations": observations})
            except Exception as ex:
                logger.warning(f"Failed to create entity '{name}': {ex}")
                conn.rollback()
                continue
        conn.commit()
    finally:
        conn.close()
    return created


def _create_relations(relations: list[dict]) -> list[dict]:
    """Create relations, skipping duplicates. Returns newly created."""
    conn = _conn()
    created = []
    try:
        cur = conn.cursor()
        for r in relations:
            from_e = r.get("from", "").strip()
            to_e = r.get("to", "").strip()
            rel_type = r.get("relationType", "").strip()
            if not from_e or not to_e or not rel_type:
                continue
            try:
                cur.execute("""
                    INSERT INTO gigi_kg_relations (from_entity, to_entity, relation_type)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (from_entity, to_entity, relation_type) DO NOTHING
                    RETURNING id
                """, (from_e, to_e, rel_type))
                row = cur.fetchone()
                if row:
                    created.append({"from": from_e, "to": to_e, "relationType": rel_type})
            except psycopg2.errors.ForeignKeyViolation:
                logger.warning(f"Relation skipped — entity not found: {from_e} -> {to_e}")
                conn.rollback()
                continue
            except Exception as ex:
                logger.warning(f"Failed to create relation: {ex}")
                conn.rollback()
                continue
        conn.commit()
    finally:
        conn.close()
    return created


def _add_observations(observations: list[dict]) -> list[dict]:
    """Add observations to existing entities. Returns what was added."""
    conn = _conn()
    results = []
    try:
        cur = conn.cursor()
        for o in observations:
            entity_name = o.get("entityName", "").strip()
            contents = o.get("contents", [])
            if not entity_name or not contents:
                continue
            # Get current observations
            cur.execute("SELECT observations FROM gigi_kg_entities WHERE name = %s", (entity_name,))
            row = cur.fetchone()
            if not row:
                results.append({"entityName": entity_name, "error": "entity not found"})
                continue
            existing = set(row[0] or [])
            new_obs = [c for c in contents if c not in existing]
            if new_obs:
                cur.execute("""
                    UPDATE gigi_kg_entities
                    SET observations = observations || %s, updated_at = NOW()
                    WHERE name = %s
                """, (new_obs, entity_name))
            results.append({"entityName": entity_name, "addedObservations": new_obs})
        conn.commit()
    finally:
        conn.close()
    return results


def _delete_entities(entity_names: list[str]) -> int:
    """Delete entities and their cascading relations. Returns count deleted."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM gigi_kg_entities WHERE name = ANY(%s)", (entity_names,))
        count = cur.rowcount
        conn.commit()
        return count
    finally:
        conn.close()


def _delete_relations(relations: list[dict]) -> int:
    """Delete specific relations. Returns count deleted."""
    conn = _conn()
    count = 0
    try:
        cur = conn.cursor()
        for r in relations:
            cur.execute("""
                DELETE FROM gigi_kg_relations
                WHERE from_entity = %s AND to_entity = %s AND relation_type = %s
            """, (r.get("from", ""), r.get("to", ""), r.get("relationType", "")))
            count += cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return count


def _delete_observations(deletions: list[dict]) -> list[dict]:
    """Remove specific observations from entities."""
    conn = _conn()
    results = []
    try:
        cur = conn.cursor()
        for d in deletions:
            entity_name = d.get("entityName", "").strip()
            obs_to_remove = d.get("observations", [])
            if not entity_name or not obs_to_remove:
                continue
            cur.execute("SELECT observations FROM gigi_kg_entities WHERE name = %s", (entity_name,))
            row = cur.fetchone()
            if not row:
                continue
            current = row[0] or []
            updated = [o for o in current if o not in obs_to_remove]
            cur.execute("""
                UPDATE gigi_kg_entities SET observations = %s, updated_at = NOW()
                WHERE name = %s
            """, (updated, entity_name))
            results.append({"entityName": entity_name, "removed": len(current) - len(updated)})
        conn.commit()
    finally:
        conn.close()
    return results


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def _entity_to_dict(row) -> dict:
    """Convert a DB row (name, entity_type, observations) to dict."""
    return {"name": row[0], "entityType": row[1], "observations": row[2] or []}


def _search_nodes(query: str) -> dict:
    """Search entities by name, type, or observation content."""
    conn = _conn()
    try:
        cur = conn.cursor()
        q = f"%{query.lower()}%"
        cur.execute("""
            SELECT name, entity_type, observations FROM gigi_kg_entities
            WHERE lower(name) LIKE %s
               OR lower(entity_type) LIKE %s
               OR EXISTS (SELECT 1 FROM unnest(observations) obs WHERE lower(obs) LIKE %s)
            ORDER BY name
            LIMIT 50
        """, (q, q, q))
        entities = [_entity_to_dict(r) for r in cur.fetchall()]

        entity_names = {e["name"] for e in entities}
        if entity_names:
            cur.execute("""
                SELECT from_entity, to_entity, relation_type FROM gigi_kg_relations
                WHERE from_entity = ANY(%s) AND to_entity = ANY(%s)
            """, (list(entity_names), list(entity_names)))
            relations = [{"from": r[0], "to": r[1], "relationType": r[2]} for r in cur.fetchall()]
        else:
            relations = []

        return {"entities": entities, "relations": relations}
    finally:
        conn.close()


def _open_nodes(names: list[str]) -> dict:
    """Get specific entities and relations between them."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT name, entity_type, observations FROM gigi_kg_entities
            WHERE name = ANY(%s)
            ORDER BY name
        """, (names,))
        entities = [_entity_to_dict(r) for r in cur.fetchall()]

        entity_names = {e["name"] for e in entities}
        if entity_names:
            # Get relations where either end is one of our entities
            cur.execute("""
                SELECT from_entity, to_entity, relation_type FROM gigi_kg_relations
                WHERE from_entity = ANY(%s) OR to_entity = ANY(%s)
            """, (list(entity_names), list(entity_names)))
            relations = [{"from": r[0], "to": r[1], "relationType": r[2]} for r in cur.fetchall()]
        else:
            relations = []

        return {"entities": entities, "relations": relations}
    finally:
        conn.close()


def _read_graph() -> dict:
    """Read the full knowledge graph."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name, entity_type, observations FROM gigi_kg_entities ORDER BY name")
        entities = [_entity_to_dict(r) for r in cur.fetchall()]

        cur.execute("SELECT from_entity, to_entity, relation_type FROM gigi_kg_relations ORDER BY from_entity")
        relations = [{"from": r[0], "to": r[1], "relationType": r[2]} for r in cur.fetchall()]

        return {"entities": entities, "relations": relations, "entity_count": len(entities), "relation_count": len(relations)}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public async API (called from execute_tool)
# ---------------------------------------------------------------------------

import asyncio


def _parse_list_param(value):
    """Parse a parameter that may be a JSON string or already a list.

    Handles four cases:
    1. value is a JSON string of a list → parse outer, then parse any string items
    2. value is a list of JSON strings (some LLMs serialize sub-objects) → parse each item
    3. value is already a list of dicts → return as-is
    4. value is a JSON string that is not a list → return None
    """
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                return None
            value = parsed  # fall through to item-by-item parsing below
        except (json.JSONDecodeError, ValueError):
            return None
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, str):
                try:
                    result.append(json.loads(item))
                except (json.JSONDecodeError, ValueError):
                    result.append(item)  # keep as-is; will fail with a clearer error downstream
            else:
                result.append(item)
        return result
    return value


async def update_knowledge_graph(
    action: str,
    entities: Optional[list] = None,
    relations: Optional[list] = None,
    observations: Optional[list] = None,
    entity_names: Optional[list] = None,
    deletions: Optional[list] = None,
) -> dict:
    """Write to the knowledge graph. Returns result dict."""
    action = (action or "").strip().lower()

    # Gemini passes array params as JSON strings — parse them back to lists
    entities = _parse_list_param(entities)
    relations = _parse_list_param(relations)
    observations = _parse_list_param(observations)
    entity_names = _parse_list_param(entity_names)
    deletions = _parse_list_param(deletions)

    if action == "add_entities":
        if not entities:
            return {"error": "entities required for add_entities"}
        result = await asyncio.to_thread(_create_entities, entities)
        return {"action": action, "created": result, "count": len(result)}

    elif action == "add_relations":
        if not relations:
            return {"error": "relations required for add_relations"}
        result = await asyncio.to_thread(_create_relations, relations)
        return {"action": action, "created": result, "count": len(result)}

    elif action == "add_observations":
        if not observations:
            return {"error": "observations required for add_observations"}
        result = await asyncio.to_thread(_add_observations, observations)
        return {"action": action, "results": result}

    elif action == "delete_entities":
        if not entity_names:
            return {"error": "entity_names required for delete_entities"}
        count = await asyncio.to_thread(_delete_entities, entity_names)
        return {"action": action, "deleted": count}

    elif action == "delete_relations":
        if not relations:
            return {"error": "relations required for delete_relations"}
        count = await asyncio.to_thread(_delete_relations, relations)
        return {"action": action, "deleted": count}

    elif action == "delete_observations":
        if not deletions:
            return {"error": "deletions required for delete_observations"}
        result = await asyncio.to_thread(_delete_observations, deletions)
        return {"action": action, "results": result}

    else:
        return {"error": f"Unknown action: {action}. Use: add_entities, add_relations, add_observations, delete_entities, delete_relations, delete_observations"}


async def query_knowledge_graph(
    action: str,
    query: Optional[str] = None,
    names: Optional[list] = None,
) -> dict:
    """Read from the knowledge graph. Returns result dict."""
    action = (action or "").strip().lower()
    names = _parse_list_param(names)

    if action == "search":
        if not query:
            return {"error": "query required for search"}
        result = await asyncio.to_thread(_search_nodes, query)
        return {"action": action, "query": query, **result}

    elif action == "open_nodes":
        if not names:
            return {"error": "names required for open_nodes"}
        result = await asyncio.to_thread(_open_nodes, names)
        return {"action": action, **result}

    elif action == "read_graph":
        result = await asyncio.to_thread(_read_graph)
        return {"action": action, **result}

    else:
        return {"error": f"Unknown action: {action}. Use: search, open_nodes, read_graph"}

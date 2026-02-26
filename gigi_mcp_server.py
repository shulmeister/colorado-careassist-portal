"""
Gigi MCP Server — FastMCP server exposing Gigi's live data to Claude Code.

Gives Claude Code direct access to:
  - WellSky clients & caregivers (cached + live)
  - Gigi's memory (save, recall, list)
  - Recent conversations (all channels)
  - SMS shadow drafts
  - Knowledge graph
  - Failure log
  - Read-only SQL on the careassist DB
  - Gigi service status

Run via stdio (spawned by Claude Code):
  python3.11 /path/to/gigi_mcp_server.py

Secrets sourced from ~/.config/careassist/resolved-secrets.env
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

import psycopg2
import psycopg2.extras
from fastmcp import FastMCP


# ── Load secrets ──────────────────────────────────────────────────────────────
def _load_secrets():
    secrets_file = os.path.expanduser("~/.config/careassist/resolved-secrets.env")
    if os.path.exists(secrets_file):
        with open(secrets_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

_load_secrets()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://careassist:careassist2026@localhost:5432/careassist",
)

# ── DB helper ─────────────────────────────────────────────────────────────────
def _db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def _query(sql: str, params=None) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]


def _execute(sql: str, params=None):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()


# ── FastMCP server ────────────────────────────────────────────────────────────
mcp = FastMCP(
    name="gigi",
    instructions=(
        "Live access to Gigi's data: WellSky clients/caregivers/shifts, "
        "Gigi's memory, conversations, SMS drafts, knowledge graph, failure log, "
        "and read-only SQL on the careassist database."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# CLIENTS & CAREGIVERS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool
def gigi_get_clients(search: str = "", limit: int = 20) -> str:
    """
    Search Gigi's cached WellSky client list.
    Returns name, phone, status, location, wellsky_id, primary_caregiver.
    Use search='' to list most-recent clients.
    """
    if search:
        rows = _query(
            """
            SELECT name, phone, status, location, address, primary_caregiver, wellsky_id, updated_at
            FROM gigi_clients
            WHERE name ILIKE %s OR phone ILIKE %s OR location ILIKE %s
            ORDER BY name
            LIMIT %s
            """,
            (f"%{search}%", f"%{search}%", f"%{search}%", limit),
        )
    else:
        rows = _query(
            """
            SELECT name, phone, status, location, address, primary_caregiver, wellsky_id, updated_at
            FROM gigi_clients
            ORDER BY updated_at DESC NULLS LAST
            LIMIT %s
            """,
            (limit,),
        )
    return json.dumps(rows, default=str)


@mcp.tool
def gigi_get_caregivers(search: str = "", limit: int = 20) -> str:
    """
    Search Gigi's cached WellSky caregiver list.
    Use search to filter by name, phone, or status.
    """
    rows = _query(
        """
        SELECT *
        FROM gigi_caregivers
        WHERE (%s = '' OR name ILIKE %s OR phone ILIKE %s OR status ILIKE %s)
        ORDER BY name
        LIMIT %s
        """,
        (search, f"%{search}%", f"%{search}%", f"%{search}%", limit),
    )
    return json.dumps(rows, default=str)


@mcp.tool
def gigi_get_shifts(
    date: str = "",
    caregiver_name: str = "",
    client_name: str = "",
    limit: int = 30,
) -> str:
    """
    Query Gigi's shift cache. date format: YYYY-MM-DD (defaults to today).
    Filter by caregiver_name or client_name (partial match).
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    rows = _query(
        """
        SELECT *
        FROM gigi_shifts
        WHERE (date::date = %s OR %s = '')
          AND (%s = '' OR caregiver_name ILIKE %s)
          AND (%s = '' OR client_name ILIKE %s)
        ORDER BY date, start_time
        LIMIT %s
        """,
        (
            target_date, target_date,
            caregiver_name, f"%{caregiver_name}%",
            client_name, f"%{client_name}%",
            limit,
        ),
    )
    return json.dumps(rows, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# MEMORY
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool
def gigi_recall(query: str, limit: int = 15) -> str:
    """
    Search Gigi's memory for content matching the query (full-text ILIKE search).
    Returns type, content, confidence, category, source, created_at.
    """
    rows = _query(
        """
        SELECT type, content, confidence, category, source, status, impact_level,
               reinforcement_count, created_at
        FROM gigi_memories
        WHERE status = 'active'
          AND (content ILIKE %s OR category ILIKE %s)
        ORDER BY confidence DESC, reinforcement_count DESC
        LIMIT %s
        """,
        (f"%{query}%", f"%{query}%", limit),
    )
    return json.dumps(rows, default=str)


@mcp.tool
def gigi_list_memories(
    memory_type: str = "",
    category: str = "",
    limit: int = 30,
) -> str:
    """
    List Gigi's active memories. Filter by type (EXPLICIT/CORRECTION/PATTERN/INFERENCE)
    or category. Shows top memories by confidence.
    """
    rows = _query(
        """
        SELECT type, content, confidence, category, source, impact_level,
               reinforcement_count, created_at
        FROM gigi_memories
        WHERE status = 'active'
          AND (%s = '' OR type = %s)
          AND (%s = '' OR category ILIKE %s)
        ORDER BY confidence DESC, reinforcement_count DESC
        LIMIT %s
        """,
        (memory_type, memory_type, category, f"%{category}%", limit),
    )
    return json.dumps(rows, default=str)


@mcp.tool
def gigi_save_memory(
    content: str,
    memory_type: str = "EXPLICIT",
    category: str = "",
    confidence: float = 0.9,
) -> str:
    """
    Save a new memory to Gigi's memory system.
    memory_type: EXPLICIT | CORRECTION | PATTERN | INFERENCE
    confidence: 0.0–1.0
    """
    _execute(
        """
        INSERT INTO gigi_memories (type, content, category, confidence, source, status)
        VALUES (%s, %s, %s, %s, 'claude_code', 'active')
        """,
        (memory_type.upper(), content, category or None, confidence),
    )
    return json.dumps({"saved": True, "content": content, "type": memory_type})


# ─────────────────────────────────────────────────────────────────────────────
# CONVERSATIONS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool
def gigi_get_conversations(
    channel: str = "",
    user_id: str = "",
    hours_back: int = 24,
    limit: int = 50,
) -> str:
    """
    Get recent Gigi conversations.
    channel: sms | telegram | voice | dm | team_chat | ask_gigi (or '' for all)
    user_id: phone number or chat ID (or '' for all)
    hours_back: how far back to look (default 24h)
    Returns role (user/assistant), content, channel, user_id, timestamp.
    """
    since = datetime.now() - timedelta(hours=hours_back)
    rows = _query(
        """
        SELECT user_id, channel, role, content, created_at
        FROM gigi_conversations
        WHERE created_at >= %s
          AND (%s = '' OR channel = %s)
          AND (%s = '' OR user_id ILIKE %s)
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (since, channel, channel, user_id, f"%{user_id}%", limit),
    )
    return json.dumps(rows, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# SMS SHADOW DRAFTS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool
def gigi_get_sms_drafts(paired: Optional[bool] = None, limit: int = 20) -> str:
    """
    Get Gigi's SMS shadow drafts (what she would have sent vs. what Jason sent).
    paired=True: show matched pairs | paired=False: unmatched | None: all
    Useful for reviewing learning pipeline accuracy.
    """
    if paired is None:
        rows = _query(
            """
            SELECT from_name, from_phone, inbound_text, draft_reply, actual_reply,
                   actual_reply_by, paired, inbound_time
            FROM gigi_sms_drafts
            ORDER BY inbound_time DESC
            LIMIT %s
            """,
            (limit,),
        )
    else:
        rows = _query(
            """
            SELECT from_name, from_phone, inbound_text, draft_reply, actual_reply,
                   actual_reply_by, paired, inbound_time
            FROM gigi_sms_drafts
            WHERE paired = %s
            ORDER BY inbound_time DESC
            LIMIT %s
            """,
            (paired, limit),
        )
    return json.dumps(rows, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE GRAPH
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool
def gigi_kg_search(query: str = "", entity_type: str = "", limit: int = 20) -> str:
    """
    Search Gigi's knowledge graph entities.
    entity_type: client | caregiver | prospect | location | organization (or '' for all)
    Returns entity name, type, and observations.
    """
    rows = _query(
        """
        SELECT name, entity_type, observations, updated_at
        FROM gigi_kg_entities
        WHERE (%s = '' OR name ILIKE %s OR %s = ANY(observations))
          AND (%s = '' OR entity_type = %s)
        ORDER BY updated_at DESC
        LIMIT %s
        """,
        (query, f"%{query}%", query, entity_type, entity_type, limit),
    )
    return json.dumps(rows, default=str)


@mcp.tool
def gigi_kg_relations(entity_name: str, limit: int = 20) -> str:
    """
    Get all knowledge graph relations for a specific entity (by name).
    Shows what Gigi knows about connections between people, places, orgs.
    """
    rows = _query(
        """
        SELECT r.from_entity, r.relation_type, r.to_entity, r.context, r.created_at
        FROM gigi_kg_relations r
        WHERE r.from_entity ILIKE %s OR r.to_entity ILIKE %s
        ORDER BY r.created_at DESC
        LIMIT %s
        """,
        (f"%{entity_name}%", f"%{entity_name}%", limit),
    )
    return json.dumps(rows, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# FAILURES
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool
def gigi_get_failures(
    tool_name: str = "",
    resolved: Optional[bool] = False,
    hours_back: int = 48,
    limit: int = 20,
) -> str:
    """
    Get Gigi's recent failure log.
    tool_name: filter by specific tool (or '' for all)
    resolved=False: only open failures | True: resolved | None: all
    """
    since = datetime.now() - timedelta(hours=hours_back)
    if resolved is None:
        rows = _query(
            """
            SELECT type, severity, tool_name, message, action_taken, resolved, occurred_at
            FROM gigi_failure_log
            WHERE occurred_at >= %s
              AND (%s = '' OR tool_name ILIKE %s)
            ORDER BY occurred_at DESC
            LIMIT %s
            """,
            (since, tool_name, f"%{tool_name}%", limit),
        )
    else:
        rows = _query(
            """
            SELECT type, severity, tool_name, message, action_taken, resolved, occurred_at
            FROM gigi_failure_log
            WHERE occurred_at >= %s
              AND resolved = %s
              AND (%s = '' OR tool_name ILIKE %s)
            ORDER BY occurred_at DESC
            LIMIT %s
            """,
            (since, resolved, tool_name, f"%{tool_name}%", limit),
        )
    return json.dumps(rows, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# READ-ONLY SQL
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool
def gigi_query_db(sql: str, limit_rows: int = 100) -> str:
    """
    Run a read-only SELECT query against the careassist PostgreSQL database.
    Only SELECT statements are allowed — any other statement will be rejected.
    Results capped at limit_rows (max 500).

    Key tables: gigi_clients, gigi_caregivers, gigi_shifts, gigi_memories,
    gigi_conversations, gigi_sms_drafts, gigi_kg_entities, gigi_kg_relations,
    gigi_failure_log, contacts, deals, wellsky_clients, wellsky_caregivers.
    """
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT"):
        return json.dumps({"error": "Only SELECT statements are allowed."})

    cap = min(limit_rows, 500)
    # Wrap in LIMIT if not already limited
    wrapped = sql.rstrip().rstrip(";")
    if "LIMIT" not in stripped:
        wrapped = f"{wrapped} LIMIT {cap}"

    try:
        rows = _query(wrapped)
        return json.dumps(rows, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# SERVICE STATUS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool
def gigi_service_status() -> str:
    """
    Live status of all Gigi-related services: ports, recent errors, DB stats,
    current mode, and recent failure counts.
    """
    import urllib.request

    status = {}

    # Port checks
    ports = {
        "gigi_prod": 8767,
        "gigi_staging": 8768,
        "portal_prod": 8765,
        "portal_staging": 8766,
    }
    for name, port in ports.items():
        try:
            req = urllib.request.urlopen(f"http://localhost:{port}/gigi/health", timeout=2)
            status[name] = f"up ({req.status})"
        except Exception as e:
            status[name] = f"down ({e})"

    # DB stats
    try:
        mem_count = _query("SELECT COUNT(*) as n FROM gigi_memories WHERE status='active'")[0]["n"]
        conv_count_24h = _query(
            "SELECT COUNT(*) as n FROM gigi_conversations WHERE created_at > NOW() - INTERVAL '24 hours'"
        )[0]["n"]
        failure_count_24h = _query(
            "SELECT COUNT(*) as n FROM gigi_failure_log WHERE occurred_at > NOW() - INTERVAL '24 hours' AND resolved = false"
        )[0]["n"]
        draft_count = _query("SELECT COUNT(*) as n FROM gigi_sms_drafts WHERE paired = false")[0]["n"]

        status["db"] = {
            "active_memories": int(mem_count),
            "conversations_24h": int(conv_count_24h),
            "open_failures_24h": int(failure_count_24h),
            "unpaired_sms_drafts": int(draft_count),
        }
    except Exception as e:
        status["db"] = f"error: {e}"

    # Current mode
    try:
        mode_rows = _query(
            "SELECT mode, set_at FROM gigi_mode_state WHERE active = true ORDER BY set_at DESC LIMIT 1"
        )
        status["current_mode"] = mode_rows[0] if mode_rows else "unknown"
    except Exception:
        status["current_mode"] = "unknown"

    return json.dumps(status, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# LEARNING PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool
def gigi_learning_stats() -> str:
    """
    Stats from Gigi's shadow mode learning pipeline.
    Shows how many SMS drafts have been paired, corrections generated, accuracy trend.
    """
    try:
        rows = _query(
            """
            SELECT
                COUNT(*) FILTER (WHERE paired = true) AS paired,
                COUNT(*) FILTER (WHERE paired = false) AS unpaired,
                COUNT(*) FILTER (WHERE actual_reply IS NOT NULL AND actual_reply != draft_reply) AS corrections,
                COUNT(*) FILTER (WHERE actual_reply IS NOT NULL AND actual_reply = draft_reply) AS matches,
                MIN(inbound_time) AS oldest,
                MAX(inbound_time) AS newest
            FROM gigi_sms_drafts
            """
        )
        return json.dumps(rows[0], default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run()

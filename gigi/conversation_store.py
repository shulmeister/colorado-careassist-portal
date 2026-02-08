"""
Shared conversation store for cross-channel persistence.

Replaces per-handler in-memory dicts and JSON files with PostgreSQL,
enabling conversation continuity across Telegram, SMS, DM, and Team Chat.
"""

import os
import logging
from typing import List, Dict, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")

# Rough estimate: ~4 chars per token for context window management
CHARS_PER_TOKEN = 4


class ConversationStore:
    """PostgreSQL-backed conversation store with cross-channel awareness."""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or DATABASE_URL
        self._ensure_table()

    def _get_connection(self):
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is not installed")
        return psycopg2.connect(self.database_url)

    def _ensure_table(self):
        """Create the gigi_conversations table if it doesn't exist."""
        try:
            conn = self._get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS gigi_conversations (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            channel TEXT NOT NULL,
                            role TEXT NOT NULL,
                            content TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_gigi_conv_user_channel
                        ON gigi_conversations(user_id, channel, created_at DESC)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_gigi_conv_user_recent
                        ON gigi_conversations(user_id, created_at DESC)
                    """)
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to ensure gigi_conversations table: %s", e)

    def append(self, user_id: str, channel: str, role: str, content: str):
        """Append a message to the conversation store."""
        try:
            conn = self._get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO gigi_conversations (user_id, channel, role, content) "
                        "VALUES (%s, %s, %s, %s)",
                        (user_id, channel, role, content)
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to append conversation message: %s", e)

    def get_recent(self, user_id: str, channel: Optional[str] = None,
                   limit: int = 20, timeout_minutes: Optional[int] = None) -> List[Dict]:
        """Get recent messages for a user, optionally filtered by channel.

        Args:
            user_id: The user identifier
            channel: Optional channel filter (telegram, sms, dm, team_chat)
            limit: Maximum number of messages to return
            timeout_minutes: If set, only return messages within this time window

        Returns:
            List of {role, content} dicts, oldest first. Leading non-user
            messages are stripped for LLM API compatibility.
        """
        try:
            conn = self._get_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    conditions = ["user_id = %s"]
                    params: list = [user_id]

                    if channel:
                        conditions.append("channel = %s")
                        params.append(channel)

                    if timeout_minutes:
                        conditions.append(
                            "created_at >= NOW() - make_interval(mins => %s)"
                        )
                        params.append(timeout_minutes)

                    where = " AND ".join(conditions)
                    params.append(limit)

                    cur.execute(
                        f"SELECT role, content "
                        f"FROM gigi_conversations "
                        f"WHERE {where} "
                        f"ORDER BY created_at DESC "
                        f"LIMIT %s",
                        params
                    )
                    rows = [dict(r) for r in cur.fetchall()]
                    rows.reverse()  # chronological order

                    # Strip leading non-user messages (prevents LLM API errors)
                    while rows and rows[0]["role"] != "user":
                        rows.pop(0)

                    return rows
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to get recent conversations: %s", e)
            return []

    def get_cross_channel_summary(self, user_id: str, exclude_channel: str,
                                  limit: int = 5, hours: int = 4) -> Optional[str]:
        """Get a brief summary of recent messages from OTHER channels.

        Injected into system prompt so Gigi has cross-channel awareness.

        Returns:
            A formatted string, or None if no recent cross-channel activity.
        """
        try:
            conn = self._get_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT role, content, channel, created_at "
                        "FROM gigi_conversations "
                        "WHERE user_id = %s AND channel != %s "
                        "AND created_at >= NOW() - make_interval(hours => %s) "
                        "ORDER BY created_at DESC "
                        "LIMIT %s",
                        (user_id, exclude_channel, hours, limit)
                    )
                    rows = [dict(r) for r in cur.fetchall()]

                if not rows:
                    return None

                rows.reverse()
                lines = []
                for r in rows:
                    ts = r["created_at"]
                    time_str = ts.strftime("%-I:%M %p") if hasattr(ts, "strftime") else str(ts)
                    # Truncate long messages for the summary
                    snippet = r["content"][:150]
                    if len(r["content"]) > 150:
                        snippet += "..."
                    lines.append(f"- [{r['channel']}@{time_str}] {r['role']}: {snippet}")

                return "\n## Recent Activity on Other Channels:\n" + "\n".join(lines)
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to get cross-channel summary: %s", e)
            return None

    def estimate_tokens(self, messages: List[Dict]) -> int:
        """Estimate token count for a list of messages."""
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return total_chars // CHARS_PER_TOKEN

    def clear_channel(self, user_id: str, channel: str):
        """Clear all messages for a user on a specific channel."""
        try:
            conn = self._get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM gigi_conversations "
                        "WHERE user_id = %s AND channel = %s",
                        (user_id, channel)
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to clear channel conversations: %s", e)

    def prune_old(self, max_age_hours: int = 72):
        """Delete messages older than max_age_hours. Called by memory decay cron."""
        try:
            conn = self._get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM gigi_conversations "
                        "WHERE created_at < NOW() - make_interval(hours => %s)",
                        (max_age_hours,)
                    )
                    deleted = cur.rowcount
                conn.commit()
                if deleted:
                    logger.info("Pruned %d old conversation messages", deleted)
                return deleted
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to prune old conversations: %s", e)
            return 0

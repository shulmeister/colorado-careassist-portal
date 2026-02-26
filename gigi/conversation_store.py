"""
Shared conversation store for cross-channel persistence.

Replaces per-handler in-memory dicts and JSON files with PostgreSQL,
enabling conversation continuity across Telegram, SMS, DM, and Team Chat.
"""

import logging
import os
from typing import Dict, List, Optional

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

    _table_ensured = False

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or DATABASE_URL
        self._ensure_table()

    def _get_connection(self):
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is not installed")
        return psycopg2.connect(self.database_url)

    def _ensure_table(self):
        """Create the gigi_conversations table if it doesn't exist. Runs only once per process."""
        if ConversationStore._table_ensured:
            return
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
                ConversationStore._table_ensured = True
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

    def prune_old(self, max_age_hours: int = 168):
        """Delete messages older than max_age_hours (default 7 days). Called by memory decay cron.

        Before deleting, summarizes each day's conversations for long-term retention.
        """
        try:
            conn = self._get_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Find distinct user/channel/date combos that are about to be pruned
                    cur.execute(
                        "SELECT DISTINCT user_id, channel, created_at::date AS conv_date "
                        "FROM gigi_conversations "
                        "WHERE created_at < NOW() - make_interval(hours => %s)",
                        (max_age_hours,)
                    )
                    to_summarize = [dict(r) for r in cur.fetchall()]

                # Summarize each day before deletion
                for item in to_summarize:
                    try:
                        self.summarize_day(item["user_id"], item["channel"], item["conv_date"])
                    except Exception as e:
                        logger.warning("Failed to summarize %s/%s/%s: %s",
                                       item["user_id"], item["channel"], item["conv_date"], e)

                # Now delete the old messages
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM gigi_conversations "
                        "WHERE created_at < NOW() - make_interval(hours => %s)",
                        (max_age_hours,)
                    )
                    deleted = cur.rowcount
                conn.commit()
                if deleted:
                    logger.info("Pruned %d old conversation messages (after summarizing)", deleted)

                # Also prune old summaries (keep 90 days)
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM gigi_conversation_summaries "
                        "WHERE summary_date < CURRENT_DATE - 90"
                    )
                    pruned_summaries = cur.rowcount
                conn.commit()
                if pruned_summaries:
                    logger.info("Pruned %d old conversation summaries (>90 days)", pruned_summaries)

                return deleted
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to prune old conversations: %s", e)
            return 0

    def summarize_day(self, user_id: str, channel: str, conv_date):
        """Summarize a day's conversations into 3-5 bullets using Haiku.

        Stored in gigi_conversation_summaries for long-term context.
        Skips if summary already exists for this user/channel/date.
        """
        try:
            conn = self._get_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Check if summary already exists
                    cur.execute(
                        "SELECT id FROM gigi_conversation_summaries "
                        "WHERE user_id = %s AND channel = %s AND summary_date = %s",
                        (user_id, channel, conv_date)
                    )
                    if cur.fetchone():
                        return  # Already summarized

                    # Fetch all messages for this day
                    cur.execute(
                        "SELECT role, content, created_at "
                        "FROM gigi_conversations "
                        "WHERE user_id = %s AND channel = %s AND created_at::date = %s "
                        "ORDER BY created_at",
                        (user_id, channel, conv_date)
                    )
                    messages = [dict(r) for r in cur.fetchall()]

                if not messages:
                    return

                # Build conversation text for summarization
                conv_text = ""
                for m in messages:
                    ts = m["created_at"]
                    time_str = ts.strftime("%-I:%M %p") if hasattr(ts, "strftime") else ""
                    conv_text += f"[{time_str}] {m['role']}: {m['content']}\n"

                # Truncate to avoid huge API calls
                if len(conv_text) > 8000:
                    conv_text = conv_text[:8000] + "\n... (truncated)"

                # Use Haiku to summarize
                summary = self._call_haiku_for_summary(conv_text, channel, conv_date)
                if not summary:
                    # Fallback: just note the count
                    summary = f"{len(messages)} messages exchanged."

                # Extract basic topics from summary
                topics = []
                for keyword in summary.lower().split():
                    if len(keyword) > 5 and keyword.isalpha():
                        topics.append(keyword)
                topics = list(set(topics))[:5]

                # Insert summary
                conn2 = self._get_connection()
                try:
                    with conn2.cursor() as cur:
                        cur.execute(
                            "INSERT INTO gigi_conversation_summaries "
                            "(user_id, channel, summary_date, summary, message_count, topics) "
                            "VALUES (%s, %s, %s, %s, %s, %s) "
                            "ON CONFLICT (user_id, channel, summary_date) DO NOTHING",
                            (user_id, channel, conv_date, summary, len(messages), topics)
                        )
                    conn2.commit()
                    logger.info("Summarized %s/%s/%s: %d messages", user_id, channel, conv_date, len(messages))
                finally:
                    conn2.close()
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to summarize day %s/%s/%s: %s", user_id, channel, conv_date, e)

    def _call_haiku_for_summary(self, conv_text: str, channel: str, conv_date) -> Optional[str]:
        """Call Claude Haiku to produce a conversation summary."""
        try:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                return None
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Summarize this {channel} conversation from {conv_date} into 3-5 bullet points. "
                        f"Focus on: decisions made, requests, action items, key topics discussed. "
                        f"Be concise (1 line per bullet). Do NOT include greetings or pleasantries.\n\n"
                        f"{conv_text}"
                    )
                }]
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.warning("Haiku summarization failed: %s", e)
            return None

    def get_long_term_context(self, user_id: str, days: int = 30) -> Optional[str]:
        """Get conversation summaries from recent days for long-term context injection.

        Returns a formatted string of recent daily summaries across all channels.
        """
        try:
            conn = self._get_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT channel, summary_date, summary "
                        "FROM gigi_conversation_summaries "
                        "WHERE user_id = %s AND summary_date >= CURRENT_DATE - %s "
                        "ORDER BY summary_date DESC",
                        (user_id, days)
                    )
                    rows = [dict(r) for r in cur.fetchall()]

                if not rows:
                    return None

                lines = []
                for r in rows:
                    date_str = r["summary_date"].strftime("%b %d") if hasattr(r["summary_date"], "strftime") else str(r["summary_date"])
                    # Compact format: one line per day per channel
                    summary_oneline = r["summary"].replace("\n", " ").strip()
                    if len(summary_oneline) > 200:
                        summary_oneline = summary_oneline[:200] + "..."
                    lines.append(f"- [{date_str}, {r['channel']}] {summary_oneline}")

                return "\n## Conversation History (Recent Days):\n" + "\n".join(lines)
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to get long-term context: %s", e)
            return None

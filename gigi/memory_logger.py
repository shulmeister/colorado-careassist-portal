"""
Daily memory logger for Gigi AI Chief of Staff.

Generates a daily markdown journal summarizing operations:
- Memory activity (created, reinforced, archived)
- Tool usage counts and failure details
- Patterns detected

Runs as a daily cron job at 11:59 PM MT.
"""

import os
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")


class MemoryLogger:
    """Generates daily markdown logs summarizing Gigi's operations."""

    def __init__(self, database_url: Optional[str] = None, log_dir: Optional[str] = None):
        self.database_url = database_url or DATABASE_URL
        self.log_dir = Path(log_dir) if log_dir else Path.home() / ".gigi-memory"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _get_connection(self):
        """Get a PostgreSQL connection."""
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is not installed")
        return psycopg2.connect(self.database_url)

    def _query(self, sql: str, params: tuple = ()) -> List[Dict]:
        """Execute a query and return results as list of dicts."""
        try:
            conn = self._get_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, params)
                    return [dict(row) for row in cur.fetchall()]
            finally:
                conn.close()
        except Exception as e:
            logger.error("Database query failed: %s", e)
            return []

    def _get_memory_activity(self, target_date: date) -> Dict:
        """Get memory creation/reinforcement/archival counts for the day."""
        next_day = target_date + timedelta(days=1)

        # Count memories created today
        created = self._query(
            "SELECT COUNT(*) AS cnt FROM gigi_memories "
            "WHERE created_at >= %s AND created_at < %s",
            (target_date, next_day),
        )
        created_count = created[0]["cnt"] if created else 0

        # Count memories reinforced today (but not created today)
        reinforced = self._query(
            "SELECT COUNT(*) AS cnt FROM gigi_memories "
            "WHERE last_reinforced_at >= %s AND last_reinforced_at < %s "
            "AND (created_at < %s OR created_at IS NULL)",
            (target_date, next_day, target_date),
        )
        reinforced_count = reinforced[0]["cnt"] if reinforced else 0

        # Count archived from audit log
        archived = self._query(
            "SELECT COUNT(*) AS cnt FROM gigi_memory_audit_log "
            "WHERE event_type = 'archived' "
            "AND created_at >= %s AND created_at < %s",
            (target_date, next_day),
        )
        archived_count = archived[0]["cnt"] if archived else 0

        # Active memory stats
        active_stats = self._query(
            "SELECT COUNT(*) AS total, "
            "COALESCE(ROUND(AVG(confidence)::numeric, 0), 0) AS avg_confidence "
            "FROM gigi_memories WHERE status = 'active'"
        )
        if active_stats:
            active_total = active_stats[0]["total"]
            avg_confidence = int(active_stats[0]["avg_confidence"])
        else:
            active_total = 0
            avg_confidence = 0

        return {
            "created": created_count,
            "reinforced": reinforced_count,
            "archived": archived_count,
            "active_total": active_total,
            "avg_confidence": avg_confidence,
        }

    def _get_tool_usage(self, target_date: date) -> List[Dict]:
        """Get tool usage counts and failure counts from failure_log for the day."""
        next_day = target_date + timedelta(days=1)

        # gigi_failure_log only contains failures, so total_calls = failure count
        rows = self._query(
            "SELECT tool_name, "
            "COUNT(*) AS total_calls, "
            "SUM(CASE WHEN resolved = false THEN 1 ELSE 0 END) AS unresolved_count "
            "FROM gigi_failure_log "
            "WHERE occurred_at >= %s AND occurred_at < %s "
            "AND tool_name IS NOT NULL "
            "GROUP BY tool_name "
            "ORDER BY total_calls DESC",
            (target_date, next_day),
        )
        return rows

    def _get_failures(self, target_date: date) -> List[Dict]:
        """Get failure details from failure_log for the day."""
        next_day = target_date + timedelta(days=1)

        rows = self._query(
            "SELECT tool_name, message, occurred_at "
            "FROM gigi_failure_log "
            "WHERE occurred_at >= %s AND occurred_at < %s "
            "ORDER BY occurred_at",
            (target_date, next_day),
        )
        return rows

    def generate_daily_log(self, target_date: Optional[date] = None) -> str:
        """Generate the daily markdown log and save it to disk.

        Args:
            target_date: The date to generate the log for. Defaults to today.

        Returns:
            The file path of the saved log.
        """
        if target_date is None:
            target_date = date.today()

        # Gather data
        memory = self._get_memory_activity(target_date)
        tool_usage = self._get_tool_usage(target_date)
        failures = self._get_failures(target_date)

        # Format the date header
        day_name = target_date.strftime("%A")
        date_display = target_date.strftime("%B %-d, %Y")
        header = f"# Gigi Daily Log — {date_display} ({day_name})"

        # Build Memory Activity section
        lines = [header, ""]
        lines.append("## Memory Activity")
        lines.append(f"- Created: {memory['created']} new memories")
        lines.append(f"- Reinforced: {memory['reinforced']} existing memories")
        lines.append(f"- Archived: {memory['archived']} memories")
        lines.append(
            f"- Active total: {memory['active_total']} "
            f"(avg confidence: {memory['avg_confidence']}%)"
        )
        lines.append("")

        # Build Tool Usage section
        lines.append("## Tool Usage (from failure_log)")
        if tool_usage:
            for row in tool_usage:
                name = row["tool_name"]
                total = row["total_calls"]
                unresolved = row["unresolved_count"]
                lines.append(f"- {name}: {total} logged ({unresolved} unresolved)")
        else:
            lines.append("- No tool calls recorded today")
        lines.append("")

        # Build Failures section
        total_failures = len(failures)
        lines.append("## Failures")
        if total_failures > 0:
            lines.append(f"- {total_failures} failure{'s' if total_failures != 1 else ''} total")
            for f in failures:
                ts = f["occurred_at"]
                if hasattr(ts, "strftime"):
                    time_str = ts.strftime("%-I:%M %p")
                else:
                    time_str = str(ts)
                error = f.get("message") or "unknown error"
                lines.append(f"- {f['tool_name']}: {error} at {time_str}")
        else:
            lines.append("- 0 failures today")
        lines.append("")

        # Patterns section (placeholder — can be extended later)
        lines.append("## Patterns Detected")
        lines.append("- None today")
        lines.append("")

        # Footer
        now = datetime.now()
        time_str = now.strftime("%-I:%M %p")
        lines.append("---")
        lines.append(f"*Generated at {time_str} MT by Gigi Self-Monitor*")
        lines.append("")

        # Write file
        filename = f"{target_date.isoformat()}.md"
        filepath = self.log_dir / filename
        filepath.write_text("\n".join(lines), encoding="utf-8")

        logger.info("Daily log written to %s", filepath)
        return str(filepath)

    def search_logs(self, query: str, days_back: int = 30) -> List[Dict]:
        """Search past log files for a keyword.

        Args:
            query: The search string (case-insensitive).
            days_back: How many days back to search (default 30).

        Returns:
            List of dicts with keys: date, file, matches (list of matching lines).
        """
        results = []
        today = date.today()
        query_lower = query.lower()

        for i in range(days_back):
            check_date = today - timedelta(days=i)
            filepath = self.log_dir / f"{check_date.isoformat()}.md"

            if not filepath.exists():
                continue

            try:
                content = filepath.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning("Could not read %s: %s", filepath, e)
                continue

            matching_lines = []
            for line in content.splitlines():
                if query_lower in line.lower():
                    matching_lines.append(line)

            if matching_lines:
                results.append({
                    "date": check_date.isoformat(),
                    "file": str(filepath),
                    "matches": matching_lines,
                })

        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ml = MemoryLogger()
    path = ml.generate_daily_log()
    print(f"Log saved to: {path}")

"""
Gigi Self-Monitor - Weekly Self-Audit System

Analyzes Gigi's own operational metrics and generates a report.
Designed to run weekly (e.g., Sunday night).

Metrics collected:
- Failure rate (from gigi_failure_log)
- Memory health (from gigi_memories)
- Shift coverage (from cached_appointments)
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")


class SelfMonitor:
    """Weekly self-audit for Gigi's operational health."""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or DATABASE_URL
        if not self.database_url:
            raise ValueError("DATABASE_URL not set")

        # Fix for Mac Mini (Local) PostgreSQL URLs
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)

    def _get_connection(self):
        """Get database connection."""
        if psycopg2 is None:
            raise ImportError("psycopg2 is required but not installed")
        return psycopg2.connect(self.database_url)

    def _collect_failures(self, conn, since: datetime) -> Dict:
        """Collect failure metrics from gigi_failure_log."""
        result = {"total": 0, "by_tool": {}}

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Total failures in period
                cur.execute(
                    "SELECT COUNT(*) as total FROM gigi_failure_log WHERE occurred_at >= %s",
                    (since,)
                )
                row = cur.fetchone()
                result["total"] = row["total"] if row else 0

                # Top failing tools (top 3)
                cur.execute("""
                    SELECT tool_name, COUNT(*) as count
                    FROM gigi_failure_log
                    WHERE occurred_at >= %s AND tool_name IS NOT NULL
                    GROUP BY tool_name
                    ORDER BY count DESC
                    LIMIT 3
                """, (since,))
                for row in cur.fetchall():
                    result["by_tool"][row["tool_name"]] = row["count"]

        except Exception as e:
            logger.error(f"Error collecting failure metrics: {e}")

        return result

    def _collect_memory_stats(self, conn, since: datetime) -> Dict:
        """Collect memory metrics from gigi_memories."""
        result = {
            "active": 0,
            "archived": 0,
            "avg_confidence": 0.0,
            "by_category": {},
            "created_this_week": 0,
            "low_confidence": 0,
            "high_confidence": 0,
        }

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Active and archived counts
                cur.execute("""
                    SELECT status, COUNT(*) as count
                    FROM gigi_memories
                    WHERE status IN ('active', 'archived')
                    GROUP BY status
                """)
                for row in cur.fetchall():
                    if row["status"] == "active":
                        result["active"] = row["count"]
                    elif row["status"] == "archived":
                        result["archived"] = row["count"]

                # Average confidence of active memories
                cur.execute("""
                    SELECT AVG(confidence) as avg_conf
                    FROM gigi_memories
                    WHERE status = 'active'
                """)
                row = cur.fetchone()
                if row and row["avg_conf"] is not None:
                    result["avg_confidence"] = round(float(row["avg_conf"]), 3)

                # Count by category (active only)
                cur.execute("""
                    SELECT category, COUNT(*) as count
                    FROM gigi_memories
                    WHERE status = 'active' AND category IS NOT NULL
                    GROUP BY category
                    ORDER BY count DESC
                """)
                for row in cur.fetchall():
                    result["by_category"][row["category"]] = row["count"]

                # Memories created this week
                cur.execute(
                    "SELECT COUNT(*) as count FROM gigi_memories WHERE created_at >= %s",
                    (since,)
                )
                row = cur.fetchone()
                result["created_this_week"] = row["count"] if row else 0

                # Low confidence (< 0.4) active memories - may be decaying away
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM gigi_memories
                    WHERE status = 'active' AND confidence < 0.4
                """)
                row = cur.fetchone()
                result["low_confidence"] = row["count"] if row else 0

                # High confidence (> 0.8) active memories - reliable
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM gigi_memories
                    WHERE status = 'active' AND confidence > 0.8
                """)
                row = cur.fetchone()
                result["high_confidence"] = row["count"] if row else 0

        except Exception as e:
            logger.error(f"Error collecting memory metrics: {e}")

        return result

    def _collect_shift_stats(self, conn, since: datetime, until: datetime) -> Dict:
        """Collect shift coverage metrics from cached_appointments."""
        result = {"total": 0, "open": 0, "fill_rate": 0.0}

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Total shifts this week
                cur.execute("""
                    SELECT COUNT(*) as total
                    FROM cached_appointments
                    WHERE scheduled_start >= %s AND scheduled_start < %s
                """, (since, until))
                row = cur.fetchone()
                result["total"] = row["total"] if row else 0

                # Open shifts (no practitioner assigned)
                cur.execute("""
                    SELECT COUNT(*) as open_count
                    FROM cached_appointments
                    WHERE scheduled_start >= %s AND scheduled_start < %s
                      AND practitioner_id IS NULL
                """, (since, until))
                row = cur.fetchone()
                result["open"] = row["open_count"] if row else 0

                # Calculate fill rate
                if result["total"] > 0:
                    filled = result["total"] - result["open"]
                    result["fill_rate"] = round((filled / result["total"]) * 100, 1)

        except Exception as e:
            logger.error(f"Error collecting shift metrics: {e}")

        return result

    def run_audit(self) -> Dict:
        """
        Run the full weekly self-audit.

        Returns:
            Dict with period, failures, memory, and shifts sections.
        """
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        week_end = now

        result = {
            "period": f"{week_ago.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}",
            "failures": {"total": 0, "by_tool": {}},
            "memory": {
                "active": 0, "archived": 0, "avg_confidence": 0.0,
                "by_category": {}, "created_this_week": 0,
                "low_confidence": 0, "high_confidence": 0,
            },
            "shifts": {"total": 0, "open": 0, "fill_rate": 0.0},
        }

        conn = None
        try:
            conn = self._get_connection()
            result["failures"] = self._collect_failures(conn, week_ago)
            result["memory"] = self._collect_memory_stats(conn, week_ago)
            result["shifts"] = self._collect_shift_stats(conn, week_ago, week_end)
        except Exception as e:
            logger.error(f"Self-audit failed: {e}")
        finally:
            if conn:
                conn.close()

        return result

    def get_briefing_section(self) -> Optional[str]:
        """
        Generate a formatted text block for the weekly audit report.

        Returns:
            Formatted string, or None if no meaningful data.
        """
        audit = self.run_audit()

        # Check if we have any meaningful data at all
        mem = audit["memory"]
        fail = audit["failures"]
        shifts = audit["shifts"]

        has_data = (mem["active"] > 0 or fail["total"] > 0 or shifts["total"] > 0)
        if not has_data:
            return None

        # Format date range for header
        period = audit["period"]
        try:
            start_dt = datetime.strptime(period.split(" to ")[0], "%Y-%m-%d")
            end_dt = datetime.strptime(period.split(" to ")[1], "%Y-%m-%d")
            header_dates = f"{start_dt.strftime('%b %-d')}-{end_dt.strftime('%-d')}"
        except (ValueError, IndexError):
            header_dates = period

        lines = [f"WEEKLY SELF-AUDIT ({header_dates})"]

        # Memory line
        confidence_pct = round(mem["avg_confidence"] * 100)
        lines.append(
            f"  Memory: {mem['active']} active (avg {confidence_pct}% confidence), "
            f"{mem['created_this_week']} created this week"
        )

        # Failures line
        if fail["total"] > 0:
            top_tools = ", ".join(
                f"{tool} x{count}" for tool, count in fail["by_tool"].items()
            )
            fail_detail = f" (top: {top_tools})" if top_tools else ""
            lines.append(f"  Failures: {fail['total']} total{fail_detail}")
        else:
            lines.append("  Failures: 0 this week")

        # Shifts line
        if shifts["total"] > 0:
            lines.append(
                f"  Shifts: {shifts['total']} this week, "
                f"{shifts['fill_rate']}% filled ({shifts['open']} open)"
            )

        return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    monitor = SelfMonitor()

    print("Running weekly self-audit...\n")
    audit = monitor.run_audit()

    print(f"Period: {audit['period']}")
    print(f"\nFailures: {audit['failures']['total']} total")
    for tool, count in audit["failures"]["by_tool"].items():
        print(f"  - {tool}: {count}")

    mem = audit["memory"]
    print(f"\nMemory: {mem['active']} active, {mem['archived']} archived")
    print(f"  Avg confidence: {mem['avg_confidence']:.2f}")
    print(f"  Created this week: {mem['created_this_week']}")
    print(f"  Low confidence (<0.4): {mem['low_confidence']}")
    print(f"  High confidence (>0.8): {mem['high_confidence']}")
    for cat, count in mem["by_category"].items():
        print(f"  - {cat}: {count}")

    shifts = audit["shifts"]
    print(f"\nShifts: {shifts['total']} total, {shifts['open']} open, {shifts['fill_rate']}% filled")

    print("\n--- Briefing Section ---")
    section = monitor.get_briefing_section()
    if section:
        print(section)
    else:
        print("(no data)")

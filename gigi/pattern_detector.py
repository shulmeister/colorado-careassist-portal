"""
Gigi Pattern Detector

Analyzes various data sources for repeating friction and anomalies.

Checks:
- Repeated tool failures (same tool failing 3+ times in 7 days)
- Open shift trends (unfilled shifts in the next 7 days)
- Memory conflicts (memories with unresolved conflicts)
- High failure rate (>10 failures in last 24 hours)
- Memory drift (active memories with confidence < 0.4)
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


class PatternDetector:
    """Detects repeating friction and anomalies across Gigi's data sources."""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or DATABASE_URL
        # Normalize postgres:// to postgresql:// for psycopg2
        if self.database_url and self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)

    def _get_connection(self):
        """Get a database connection."""
        if not psycopg2:
            raise RuntimeError("psycopg2 is not installed")
        return psycopg2.connect(self.database_url)

    def detect_patterns(self) -> List[Dict]:
        """
        Run all pattern detections and return a list of detected patterns.
        Uses a single DB connection for all checks to avoid connection waste.

        Each pattern dict contains:
            type: str - pattern identifier
            severity: "high" | "medium" | "low"
            description: str - human-readable explanation
            count: int - number of occurrences
            recommendation: str - suggested action
        """
        patterns = []
        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            patterns.extend(self._check_repeated_tool_failures(cur))
            patterns.extend(self._check_open_shift_trend(cur))
            patterns.extend(self._check_memory_conflicts(cur))
            patterns.extend(self._check_high_failure_rate(cur))
            patterns.extend(self._check_memory_drift(cur))

            cur.close()
        except Exception as e:
            logger.error(f"Pattern detection DB error: {e}")
        finally:
            if conn:
                conn.close()

        # Sort by severity: high first, then medium, then low
        severity_order = {"high": 0, "medium": 1, "low": 2}
        patterns.sort(key=lambda p: severity_order.get(p["severity"], 3))

        return patterns

    def _check_repeated_tool_failures(self, cur) -> List[Dict]:
        """Check gigi_failure_log for same tool failing 3+ times in last 7 days."""
        patterns = []
        try:
            cur.execute("""
                SELECT tool_name, COUNT(*) as fail_count
                FROM gigi_failure_log
                WHERE occurred_at > NOW() - INTERVAL '7 days'
                  AND tool_name IS NOT NULL
                GROUP BY tool_name
                HAVING COUNT(*) >= 3
                ORDER BY fail_count DESC
            """)
            rows = cur.fetchall()

            for row in rows:
                tool = row["tool_name"]
                count = row["fail_count"]
                patterns.append({
                    "type": "repeated_tool_failure",
                    "severity": "high" if count >= 5 else "medium",
                    "description": f"{tool} failed {count} times this week",
                    "count": count,
                    "recommendation": f"Check {tool} API status and connectivity",
                })

        except Exception as e:
            logger.debug(f"Skipping repeated_tool_failure check: {e}")

        return patterns

    def _check_open_shift_trend(self, cur) -> List[Dict]:
        """Check cached_appointments for unfilled shifts in next 7 days."""
        patterns = []
        try:
            cur.execute("""
                SELECT COUNT(*) as open_count
                FROM cached_appointments
                WHERE scheduled_start >= NOW()
                  AND scheduled_start < NOW() + INTERVAL '7 days'
                  AND (practitioner_id IS NULL OR practitioner_id = '')
            """)
            row = cur.fetchone()

            if row and row["open_count"] > 0:
                count = row["open_count"]
                patterns.append({
                    "type": "open_shift_trend",
                    "severity": "high" if count >= 5 else "medium",
                    "description": f"{count} open shift{'s' if count != 1 else ''} in next 7 days need coverage",
                    "count": count,
                    "recommendation": "Review open shifts and reach out to available caregivers",
                })

        except Exception as e:
            logger.debug(f"Skipping open_shift_trend check: {e}")

        return patterns

    def _check_memory_conflicts(self, cur) -> List[Dict]:
        """Check gigi_memories for entries with unresolved conflicts."""
        patterns = []
        try:
            cur.execute("""
                SELECT COUNT(*) as conflict_count
                FROM gigi_memories
                WHERE status = 'active'
                  AND conflicts_with IS NOT NULL
                  AND array_length(conflicts_with, 1) > 0
            """)
            row = cur.fetchone()

            if row and row["conflict_count"] > 0:
                count = row["conflict_count"]
                patterns.append({
                    "type": "memory_conflicts",
                    "severity": "medium",
                    "description": f"{count} memor{'ies' if count != 1 else 'y'} with unresolved conflicts",
                    "count": count,
                    "recommendation": "Review conflicting memories and resolve or archive stale ones",
                })

        except Exception as e:
            logger.debug(f"Skipping memory_conflicts check: {e}")

        return patterns

    def _check_high_failure_rate(self, cur) -> List[Dict]:
        """Check if total failures in last 24 hours exceed threshold."""
        patterns = []
        try:
            cur.execute("""
                SELECT COUNT(*) as total_failures
                FROM gigi_failure_log
                WHERE occurred_at > NOW() - INTERVAL '24 hours'
            """)
            row = cur.fetchone()

            if row and row["total_failures"] > 10:
                count = row["total_failures"]
                patterns.append({
                    "type": "high_failure_rate",
                    "severity": "high",
                    "description": f"{count} failures in the last 24 hours (threshold: 10)",
                    "count": count,
                    "recommendation": "Investigate failure log for root cause — possible systemic issue",
                })

        except Exception as e:
            logger.debug(f"Skipping high_failure_rate check: {e}")

        return patterns

    def _check_memory_drift(self, cur) -> List[Dict]:
        """Check for active memories with low confidence that may need attention."""
        patterns = []
        try:
            cur.execute("""
                SELECT COUNT(*) as drift_count
                FROM gigi_memories
                WHERE status = 'active'
                  AND confidence < 0.4
            """)
            row = cur.fetchone()

            if row and row["drift_count"] > 0:
                count = row["drift_count"]
                patterns.append({
                    "type": "memory_drift",
                    "severity": "low",
                    "description": f"{count} active memor{'ies' if count != 1 else 'y'} drifting below 0.4 confidence",
                    "count": count,
                    "recommendation": "Review low-confidence memories — reinforce or archive them",
                })

        except Exception as e:
            logger.debug(f"Skipping memory_drift check: {e}")

        return patterns

    def get_briefing_section(self) -> Optional[str]:
        """
        Format detected patterns into a readable text block.

        Returns:
            A formatted string section, or None if no patterns were found.
        """
        try:
            patterns = self.detect_patterns()
        except Exception as e:
            logger.error(f"Pattern detection failed: {e}")
            return None

        if not patterns:
            return None

        severity_icons = {
            "high": "\u26a0",      # warning sign
            "medium": "\u2139",    # info
            "low": "\U0001f50d",   # magnifying glass
        }

        lines = ["PATTERNS DETECTED"]
        for p in patterns:
            icon = severity_icons.get(p["severity"], "-")
            label = p["severity"].upper()
            lines.append(f"  {icon} {label}: {p['description']} \u2014 {p['recommendation']}")

        return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    detector = PatternDetector()

    print("Running pattern detection...\n")
    patterns = detector.detect_patterns()

    if patterns:
        for p in patterns:
            print(f"  [{p['severity'].upper()}] {p['type']}: {p['description']}")
            print(f"    Count: {p['count']}")
            print(f"    Recommendation: {p['recommendation']}")
            print()
    else:
        print("  No patterns detected.")

    print("\n--- Briefing Section ---")
    section = detector.get_briefing_section()
    if section:
        print(section)
    else:
        print("(no section to include)")

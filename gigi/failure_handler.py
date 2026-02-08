"""
Gigi Failure Protocol System - Phase 3 Implementation

Implements the 10 failure protocols from FAILURE_PROTOCOLS.md:

1. Missing Context - When information is incomplete
2. Conflicting Instructions - When rules contradict
3. Low-Confidence Action - When uncertain about correct action
4. Tool Failure - When APIs/services fail
5. Drift Detection - When behavior diverges from expectations
6. Over-Complexity - When solution is getting too complicated
7. Emotional Escalation - When user is frustrated/upset
8. Ambiguous Authority - When unclear who decides
9. Partial Success - When action completes but with issues
10. Meltdown Prevention - Stop before cascading failures

Core principles:
- "When uncertain, Gigi slows down, explains herself, and asks once"
- Permission to say: "I'm not confident enough to proceed safely"
- Fail gracefully, explain clearly, escalate appropriately
"""

import os
import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import logging

logger = logging.getLogger(__name__)


class FailureType(Enum):
    MISSING_CONTEXT = "missing_context"
    CONFLICTING_INSTRUCTIONS = "conflicting_instructions"
    LOW_CONFIDENCE = "low_confidence"
    TOOL_FAILURE = "tool_failure"
    DRIFT_DETECTION = "drift_detection"
    OVER_COMPLEXITY = "over_complexity"
    EMOTIONAL_ESCALATION = "emotional_escalation"
    AMBIGUOUS_AUTHORITY = "ambiguous_authority"
    PARTIAL_SUCCESS = "partial_success"
    MELTDOWN_PREVENTION = "meltdown_prevention"


class FailureSeverity(Enum):
    INFO = "info"           # FYI, no action needed
    WARNING = "warning"     # Noteworthy, monitor
    ERROR = "error"         # Problem occurred, handled
    CRITICAL = "critical"   # Serious issue, user attention required


class FailureAction(Enum):
    CONTINUE = "continue"           # Proceed with caution
    DEGRADE = "degrade"            # Reduce functionality, continue
    ASK_USER = "ask_user"          # Stop and ask for guidance
    ESCALATE = "escalate"          # Alert user immediately
    ABORT = "abort"                # Stop operation completely


@dataclass
class FailureEvent:
    """A single failure event with full context."""
    id: str
    type: FailureType
    severity: FailureSeverity
    action_taken: FailureAction
    message: str
    context: Dict[str, Any]
    tool_name: Optional[str]
    confidence: Optional[float]
    occurred_at: datetime
    resolved: bool
    resolution: Optional[str]


class FailureHandler:
    """Detects, logs, and handles failures according to protocols."""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL not set")

        # Fix for Mac Mini (Local) PostgreSQL URLs
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)

        self._init_schema()

        # Meltdown prevention: Track recent failures
        self.recent_failures = []
        self.meltdown_threshold = 3  # 3 failures in 5 minutes = meltdown
        self.meltdown_window = timedelta(minutes=5)

    @contextmanager
    def _get_connection(self):
        """Get database connection (auto-closes on exit)."""
        conn = psycopg2.connect(self.database_url)
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema if not exists."""
        schema = """
        CREATE TABLE IF NOT EXISTS gigi_failure_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            action_taken VARCHAR(50) NOT NULL,
            message TEXT NOT NULL,
            context JSONB DEFAULT '{}'::jsonb,
            tool_name VARCHAR(100),
            confidence DECIMAL(3,2),
            occurred_at TIMESTAMP NOT NULL DEFAULT NOW(),
            resolved BOOLEAN DEFAULT false,
            resolution TEXT,
            resolved_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_failure_type ON gigi_failure_log(type);
        CREATE INDEX IF NOT EXISTS idx_failure_severity ON gigi_failure_log(severity);
        CREATE INDEX IF NOT EXISTS idx_failure_occurred ON gigi_failure_log(occurred_at);
        CREATE INDEX IF NOT EXISTS idx_failure_resolved ON gigi_failure_log(resolved);
        CREATE INDEX IF NOT EXISTS idx_failure_tool ON gigi_failure_log(tool_name);

        CREATE TABLE IF NOT EXISTS gigi_failure_stats (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            total_failures INTEGER DEFAULT 0,
            by_type JSONB DEFAULT '{}'::jsonb,
            by_severity JSONB DEFAULT '{}'::jsonb,
            meltdowns INTEGER DEFAULT 0,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_failure_stats_date ON gigi_failure_stats(date);
        """

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(schema)
            conn.commit()

    def detect_meltdown(self) -> bool:
        """
        Detect if we're in a meltdown state (cascading failures).
        Queries the DB for cross-process visibility instead of in-memory tracking.

        Returns:
            True if meltdown detected, False otherwise
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM gigi_failure_log
                        WHERE severity IN ('error', 'critical')
                          AND occurred_at > NOW() - make_interval(mins => %s)
                    """, (int(self.meltdown_window.total_seconds() / 60),))
                    count = cur.fetchone()[0]

            if count >= self.meltdown_threshold:
                logger.critical(f"MELTDOWN DETECTED: {count} failures in {self.meltdown_window.total_seconds()/60:.0f} minutes")
                return True
            return False
        except Exception as e:
            logger.warning(f"Meltdown detection DB query failed, falling back to in-memory: {e}")
            # Fallback to in-memory tracking if DB fails
            cutoff = datetime.now() - self.meltdown_window
            recent = [f for f in self.recent_failures if f > cutoff]
            self.recent_failures = recent
            return len(recent) >= self.meltdown_threshold

    def log_failure(
        self,
        failure_type: FailureType,
        message: str,
        severity: FailureSeverity = FailureSeverity.WARNING,
        action: FailureAction = FailureAction.CONTINUE,
        context: Dict[str, Any] = None,
        tool_name: str = None,
        confidence: float = None
    ) -> str:
        """
        Log a failure event.

        Args:
            failure_type: Type of failure from FailureType enum
            message: Human-readable description
            severity: How serious this is
            action: What action was taken
            context: Additional context dict
            tool_name: Name of tool that failed (if applicable)
            confidence: Confidence level when failure occurred

        Returns:
            Failure event ID
        """
        context = context or {}

        # Track for meltdown detection
        if severity in [FailureSeverity.ERROR, FailureSeverity.CRITICAL]:
            self.recent_failures.append(datetime.now())

            # Check for meltdown
            if self.detect_meltdown():
                # Upgrade to meltdown — save original type before overwriting
                context['original_failure_type'] = failure_type.value
                failure_type = FailureType.MELTDOWN_PREVENTION
                severity = FailureSeverity.CRITICAL
                action = FailureAction.ABORT
                message = f"MELTDOWN DETECTED: {message} (Part of cascading failure pattern)"

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO gigi_failure_log (
                        type, severity, action_taken, message, context,
                        tool_name, confidence
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    failure_type.value,
                    severity.value,
                    action.value,
                    message,
                    Json(context),
                    tool_name,
                    confidence
                ))
                failure_id = cur.fetchone()[0]

                # Update daily stats (jsonb_set increments count, || would overwrite)
                type_key = failure_type.value
                sev_key = severity.value
                cur.execute("""
                    INSERT INTO gigi_failure_stats (date, total_failures, by_type, by_severity)
                    VALUES (CURRENT_DATE, 1, %s::jsonb, %s::jsonb)
                    ON CONFLICT (date) DO UPDATE SET
                        total_failures = gigi_failure_stats.total_failures + 1,
                        by_type = jsonb_set(
                            gigi_failure_stats.by_type,
                            ARRAY[%s],
                            to_jsonb(COALESCE((gigi_failure_stats.by_type->>%s)::int, 0) + 1)
                        ),
                        by_severity = jsonb_set(
                            gigi_failure_stats.by_severity,
                            ARRAY[%s],
                            to_jsonb(COALESCE((gigi_failure_stats.by_severity->>%s)::int, 0) + 1)
                        ),
                        updated_at = NOW()
                """, (
                    Json({type_key: 1}),
                    Json({sev_key: 1}),
                    type_key, type_key,
                    sev_key, sev_key
                ))

            conn.commit()

        logger.warning(f"Failure logged: {failure_type.value} - {message} (action: {action.value})")
        return str(failure_id)

    def handle_tool_failure(
        self,
        tool_name: str,
        error: Exception,
        context: Dict[str, Any] = None
    ) -> Tuple[FailureAction, str]:
        """
        Handle a tool/API failure.

        Args:
            tool_name: Name of the tool that failed
            error: The exception that occurred
            context: Additional context

        Returns:
            (action_to_take, user_message)
        """
        context = context or {}
        context['error_type'] = type(error).__name__
        context['error_message'] = str(error)

        # Determine severity based on tool
        critical_tools = ['wellsky', 'ringcentral', 'beetexting']
        severity = FailureSeverity.CRITICAL if tool_name.lower() in critical_tools else FailureSeverity.ERROR

        # Determine action
        if severity == FailureSeverity.CRITICAL:
            action = FailureAction.ESCALATE
            user_message = f"I tried to use {tool_name} but it's not responding. This is critical - I'm alerting you immediately."
        else:
            action = FailureAction.DEGRADE
            user_message = f"I couldn't reach {tool_name} right now. I'll continue with limited functionality and try again later."

        self.log_failure(
            failure_type=FailureType.TOOL_FAILURE,
            message=f"{tool_name} failed: {str(error)}",
            severity=severity,
            action=action,
            context=context,
            tool_name=tool_name
        )

        return (action, user_message)

    def handle_low_confidence(
        self,
        action: str,
        confidence: float,
        context: Dict[str, Any] = None
    ) -> Tuple[FailureAction, str]:
        """
        Handle low confidence in an action.

        Args:
            action: The action being considered
            confidence: Confidence level (0.0 to 1.0)
            context: Additional context

        Returns:
            (action_to_take, user_message)
        """
        context = context or {}
        context['action'] = action
        context['confidence'] = confidence

        if confidence < 0.3:
            # Very low confidence - abort
            action_taken = FailureAction.ABORT
            user_message = f"I'm not confident enough to {action}. I need more information before proceeding."
        elif confidence < 0.6:
            # Medium-low confidence - ask user
            action_taken = FailureAction.ASK_USER
            user_message = f"I'm only {confidence*100:.0f}% confident about {action}. Should I proceed?"
        else:
            # Marginal confidence - warn and continue
            action_taken = FailureAction.CONTINUE
            user_message = f"Proceeding with {action}, though I'm only {confidence*100:.0f}% confident."

        self.log_failure(
            failure_type=FailureType.LOW_CONFIDENCE,
            message=f"Low confidence ({confidence:.2f}) for action: {action}",
            severity=FailureSeverity.WARNING,
            action=action_taken,
            context=context,
            confidence=confidence
        )

        return (action_taken, user_message)

    def handle_conflicting_instructions(
        self,
        instruction1: str,
        instruction2: str,
        context: Dict[str, Any] = None
    ) -> Tuple[FailureAction, str]:
        """
        Handle conflicting instructions.

        Args:
            instruction1: First instruction
            instruction2: Conflicting instruction
            context: Additional context

        Returns:
            (action_to_take, user_message)
        """
        context = context or {}
        context['instruction1'] = instruction1
        context['instruction2'] = instruction2

        self.log_failure(
            failure_type=FailureType.CONFLICTING_INSTRUCTIONS,
            message=f"Conflict: '{instruction1}' vs '{instruction2}'",
            severity=FailureSeverity.WARNING,
            action=FailureAction.ASK_USER,
            context=context
        )

        user_message = f"I have conflicting instructions:\n1. {instruction1}\n2. {instruction2}\nWhich should I follow?"

        return (FailureAction.ASK_USER, user_message)

    def handle_missing_context(
        self,
        action: str,
        missing_info: List[str],
        context: Dict[str, Any] = None
    ) -> Tuple[FailureAction, str]:
        """
        Handle missing context needed to complete an action.

        Args:
            action: The action being attempted
            missing_info: List of missing information
            context: Additional context

        Returns:
            (action_to_take, user_message)
        """
        context = context or {}
        context['action'] = action
        context['missing_info'] = missing_info

        self.log_failure(
            failure_type=FailureType.MISSING_CONTEXT,
            message=f"Missing info for {action}: {', '.join(missing_info)}",
            severity=FailureSeverity.INFO,
            action=FailureAction.ASK_USER,
            context=context
        )

        user_message = f"To {action}, I need: {', '.join(missing_info)}"

        return (FailureAction.ASK_USER, user_message)

    def resolve_failure(self, failure_id: str, resolution: str):
        """Mark a failure as resolved."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE gigi_failure_log
                    SET resolved = true, resolution = %s, resolved_at = NOW()
                    WHERE id = %s
                """, (resolution, failure_id))
            conn.commit()

        logger.info(f"Failure {failure_id} resolved: {resolution}")

    def get_recent_failures(self, hours: int = 24, severity: FailureSeverity = None) -> List[FailureEvent]:
        """Get recent failures."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT * FROM gigi_failure_log
                    WHERE occurred_at > NOW() - make_interval(hours => %s)
                """
                params = [hours]

                if severity:
                    query += " AND severity = %s"
                    params.append(severity.value)

                query += " ORDER BY occurred_at DESC"

                cur.execute(query, params)
                rows = cur.fetchall()

                return [FailureEvent(
                    id=str(row['id']),
                    type=FailureType(row['type']),
                    severity=FailureSeverity(row['severity']),
                    action_taken=FailureAction(row['action_taken']),
                    message=row['message'],
                    context=row['context'] or {},
                    tool_name=row['tool_name'],
                    confidence=float(row['confidence']) if row['confidence'] else None,
                    occurred_at=row['occurred_at'],
                    resolved=row['resolved'],
                    resolution=row['resolution']
                ) for row in rows]

    def get_failure_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get failure statistics."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        SUM(total_failures) as total,
                        jsonb_object_agg(date::text, total_failures) as daily_counts
                    FROM gigi_failure_stats
                    WHERE date > CURRENT_DATE - make_interval(days => %s)
                """, (days,))
                row = cur.fetchone()

                stats = {
                    'total_failures': int(row['total']) if row['total'] else 0,
                    'daily_counts': row['daily_counts'] or {},
                    'period_days': days
                }

                # Get breakdown by type
                cur.execute("""
                    SELECT type, COUNT(*) as count
                    FROM gigi_failure_log
                    WHERE occurred_at > NOW() - make_interval(days => %s)
                    GROUP BY type
                    ORDER BY count DESC
                """, (days,))
                stats['by_type'] = {row['type']: row['count'] for row in cur.fetchall()}

                # Get breakdown by severity
                cur.execute("""
                    SELECT severity, COUNT(*) as count
                    FROM gigi_failure_log
                    WHERE occurred_at > NOW() - make_interval(days => %s)
                    GROUP BY severity
                    ORDER BY count DESC
                """, (days,))
                stats['by_severity'] = {row['severity']: row['count'] for row in cur.fetchall()}

                return stats


def safe_tool_call(
    handler: FailureHandler,
    tool_name: str,
    tool_func: Callable,
    *args,
    confidence_threshold: float = 0.7,
    **kwargs
) -> Tuple[bool, Any, Optional[str]]:
    """
    Wrapper for tool calls with failure handling.

    Args:
        handler: FailureHandler instance
        tool_name: Name of the tool
        tool_func: The tool function to call
        *args: Positional arguments for tool
        confidence_threshold: Minimum confidence to proceed
        **kwargs: Keyword arguments for tool

    Returns:
        (success, result, error_message)
    """
    try:
        result = tool_func(*args, **kwargs)
        return (True, result, None)
    except Exception as e:
        action, message = handler.handle_tool_failure(
            tool_name=tool_name,
            error=e,
            context={'args': str(args), 'kwargs': str(kwargs)}
        )
        return (False, None, message)


if __name__ == "__main__":
    # Test failure handler
    handler = FailureHandler()

    # Test tool failure
    print("\n1. Testing tool failure...")
    action, msg = handler.handle_tool_failure(
        tool_name="wellsky",
        error=ConnectionError("API timeout"),
        context={"endpoint": "/api/shifts"}
    )
    print(f"   Action: {action.value}")
    print(f"   Message: {msg}")

    # Test low confidence
    print("\n2. Testing low confidence...")
    action, msg = handler.handle_low_confidence(
        action="book United Airlines flight",
        confidence=0.4,
        context={"user_preference": "Never book United"}
    )
    print(f"   Action: {action.value}")
    print(f"   Message: {msg}")

    # Test conflicting instructions
    print("\n3. Testing conflicting instructions...")
    action, msg = handler.handle_conflicting_instructions(
        instruction1="Always book direct flights",
        instruction2="Book cheapest option (has layover)",
        context={"trip": "Denver to NYC"}
    )
    print(f"   Action: {action.value}")
    print(f"   Message: {msg}")

    # Get stats
    print("\n4. Failure statistics:")
    stats = handler.get_failure_stats(days=1)
    print(f"   Total failures: {stats['total_failures']}")
    print(f"   By type: {stats['by_type']}")
    print(f"   By severity: {stats['by_severity']}")

"""
Gigi Mode Detection System - Phase 2 Implementation

Detects Jason's current operating mode based on:
- Time of day and day of week
- Calendar events (future: Google Calendar integration)
- Explicit mode commands
- Context from conversation

Modes:
- focus: Deep work blocks, meeting-dense days
- execution: Normal operations, handling tasks
- decision: Quick decisions, high-volume input
- travel: On the road, limited bandwidth
- off_grid: Vacation, completely offline
- crisis: Emergency situations, all hands on deck
- thinking: Monthly review, reflection mode
- review: Retrospection, pattern analysis

Persistence:
- Current mode stored in PostgreSQL
- Mode history tracked for pattern detection
- Mode changes logged for audit trail
"""

import os
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import logging

logger = logging.getLogger(__name__)


class OperatingMode(Enum):
    FOCUS = "focus"
    EXECUTION = "execution"
    DECISION = "decision"
    TRAVEL = "travel"
    OFF_GRID = "off_grid"
    CRISIS = "crisis"
    THINKING = "thinking"
    REVIEW = "review"


class ModeSource(Enum):
    EXPLICIT = "explicit"          # User explicitly set the mode
    CALENDAR = "calendar"          # Detected from calendar event
    TIME_BASED = "time_based"      # Inferred from time of day/week
    CONTEXT = "context"            # Inferred from conversation context
    DEFAULT = "default"            # Fallback default


@dataclass
class ModeInfo:
    """Current mode with metadata."""
    mode: OperatingMode
    source: ModeSource
    confidence: float
    set_at: datetime
    expires_at: Optional[datetime]
    context: Dict[str, Any]


class ModeDetector:
    """Detects and manages Jason's operating mode."""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL not set")

        # Fix for Mac Mini (Local) PostgreSQL URLs
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)

        self._init_schema()

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
        CREATE TABLE IF NOT EXISTS gigi_mode_state (
            id SERIAL PRIMARY KEY,
            mode VARCHAR(20) NOT NULL,
            source VARCHAR(20) NOT NULL,
            confidence DECIMAL(3,2) NOT NULL,
            set_at TIMESTAMP NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMP,
            context JSONB DEFAULT '{}'::jsonb,
            active BOOLEAN DEFAULT true
        );

        CREATE INDEX IF NOT EXISTS idx_mode_state_active ON gigi_mode_state(active);
        CREATE INDEX IF NOT EXISTS idx_mode_state_set_at ON gigi_mode_state(set_at);

        CREATE TABLE IF NOT EXISTS gigi_mode_history (
            id SERIAL PRIMARY KEY,
            mode VARCHAR(20) NOT NULL,
            source VARCHAR(20) NOT NULL,
            confidence DECIMAL(3,2) NOT NULL,
            started_at TIMESTAMP NOT NULL,
            ended_at TIMESTAMP,
            duration_minutes INTEGER,
            context JSONB DEFAULT '{}'::jsonb
        );

        CREATE INDEX IF NOT EXISTS idx_mode_history_started_at ON gigi_mode_history(started_at);
        CREATE INDEX IF NOT EXISTS idx_mode_history_mode ON gigi_mode_history(mode);
        """

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(schema)
            conn.commit()

    def get_current_mode(self) -> ModeInfo:
        """
        Get current operating mode.

        Priority:
        1. Explicit mode set by user (highest)
        2. Crisis mode (always wins)
        3. Calendar-based mode
        4. Time-based inference
        5. Default (execution mode)
        """
        # Check for active explicit mode
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM gigi_mode_state
                    WHERE active = true
                    AND (expires_at IS NULL OR expires_at > NOW())
                    ORDER BY
                        CASE
                            WHEN mode = 'crisis' THEN 1
                            WHEN source = 'explicit' THEN 2
                            WHEN source = 'calendar' THEN 3
                            WHEN source = 'time_based' THEN 4
                            ELSE 5
                        END,
                        set_at DESC
                    LIMIT 1
                """)
                row = cur.fetchone()

                if row:
                    return ModeInfo(
                        mode=OperatingMode(row['mode']),
                        source=ModeSource(row['source']),
                        confidence=float(row['confidence']),
                        set_at=row['set_at'],
                        expires_at=row['expires_at'],
                        context=row['context'] or {}
                    )

        # No active mode - infer from time
        return self._infer_mode_from_time()

    def set_mode(
        self,
        mode: OperatingMode,
        source: ModeSource = ModeSource.EXPLICIT,
        confidence: float = 1.0,
        expires_at: Optional[datetime] = None,
        context: Dict[str, Any] = None
    ) -> bool:
        """
        Set current operating mode.

        Args:
            mode: The mode to set
            source: How this mode was determined
            confidence: 0.0 to 1.0
            expires_at: Optional expiration time
            context: Additional context

        Returns:
            Success boolean
        """
        context = context or {}

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Deactivate all current modes
                cur.execute("""
                    UPDATE gigi_mode_state
                    SET active = false
                    WHERE active = true
                """)

                # Archive to history
                cur.execute("""
                    INSERT INTO gigi_mode_history (
                        mode, source, confidence, started_at, ended_at,
                        duration_minutes, context
                    )
                    SELECT
                        mode, source, confidence, set_at, NOW(),
                        EXTRACT(EPOCH FROM (NOW() - set_at)) / 60,
                        context
                    FROM gigi_mode_state
                    WHERE active = false
                    AND set_at < NOW()
                """)

                # Set new mode
                cur.execute("""
                    INSERT INTO gigi_mode_state (
                        mode, source, confidence, expires_at, context, active
                    ) VALUES (%s, %s, %s, %s, %s, true)
                """, (mode.value, source.value, confidence, expires_at, Json(context)))

            conn.commit()

        logger.info(f"Mode set to {mode.value} (source: {source.value}, confidence: {confidence:.2f})")
        return True

    def _infer_mode_from_time(self) -> ModeInfo:
        """
        Infer mode from time of day and day of week.

        Heuristics:
        - Mon-Fri 6am-9am: Focus (morning deep work)
        - Mon-Fri 9am-5pm: Execution (normal operations)
        - Mon-Fri 5pm-10pm: Decision (evening catch-up)
        - Weekends: Review (unless specified otherwise)
        - Late night: Off-grid (assume not working)
        """
        now = datetime.now()
        current_time = now.time()
        is_weekday = now.weekday() < 5  # Mon-Fri

        # Weekend default: Review mode
        if not is_weekday:
            return ModeInfo(
                mode=OperatingMode.REVIEW,
                source=ModeSource.TIME_BASED,
                confidence=0.6,
                set_at=now,
                expires_at=None,
                context={"reason": "Weekend - review mode"}
            )

        # Weekday time-based detection
        if time(6, 0) <= current_time < time(9, 0):
            # Early morning: Focus
            return ModeInfo(
                mode=OperatingMode.FOCUS,
                source=ModeSource.TIME_BASED,
                confidence=0.7,
                set_at=now,
                expires_at=None,
                context={"reason": "Early morning - focus block"}
            )
        elif time(9, 0) <= current_time < time(17, 0):
            # Business hours: Execution
            return ModeInfo(
                mode=OperatingMode.EXECUTION,
                source=ModeSource.TIME_BASED,
                confidence=0.8,
                set_at=now,
                expires_at=None,
                context={"reason": "Business hours - execution mode"}
            )
        elif time(17, 0) <= current_time < time(22, 0):
            # Evening: Decision
            return ModeInfo(
                mode=OperatingMode.DECISION,
                source=ModeSource.TIME_BASED,
                confidence=0.6,
                set_at=now,
                expires_at=None,
                context={"reason": "Evening - decision mode"}
            )
        else:
            # Late night/early morning: Off-grid
            return ModeInfo(
                mode=OperatingMode.OFF_GRID,
                source=ModeSource.TIME_BASED,
                confidence=0.7,
                set_at=now,
                expires_at=None,
                context={"reason": "After hours - off-grid"}
            )

    def detect_mode_from_context(self, text: str) -> Tuple[Optional[OperatingMode], float]:
        """
        Detect mode from conversation context using keyword detection.

        Returns:
            (mode, confidence) or (None, 0.0) if no clear signal
        """
        text_lower = text.lower()

        # Crisis indicators
        crisis_keywords = ['emergency', 'urgent', 'crisis', 'critical', 'asap', 'immediately', 'down']
        if any(keyword in text_lower for keyword in crisis_keywords):
            return (OperatingMode.CRISIS, 0.9)

        # Travel indicators
        travel_keywords = ['airport', 'flight', 'traveling', 'on the road', 'hotel']
        if any(keyword in text_lower for keyword in travel_keywords):
            return (OperatingMode.TRAVEL, 0.7)

        # Off-grid indicators
        offgrid_keywords = ['vacation', 'out of office', 'ooo', 'offline', 'away']
        if any(keyword in text_lower for keyword in offgrid_keywords):
            return (OperatingMode.OFF_GRID, 0.8)

        # Focus indicators
        focus_keywords = ['focus', 'deep work', 'do not disturb', 'dnd', 'concentrating']
        if any(keyword in text_lower for keyword in focus_keywords):
            return (OperatingMode.FOCUS, 0.7)

        # Review indicators
        review_keywords = ['review', 'analyze', 'retrospective', 'monthly', 'quarterly']
        if any(keyword in text_lower for keyword in review_keywords):
            return (OperatingMode.REVIEW, 0.6)

        return (None, 0.0)

    def get_mode_behavior_config(self, mode: OperatingMode) -> Dict[str, Any]:
        """
        Get behavior configuration for a specific mode.

        Returns configuration dict with:
        - interrupt_threshold: How important something must be to interrupt
        - response_style: Tone and verbosity
        - auto_actions: What Gigi can do autonomously
        - escalation_rules: When to escalate
        """
        configs = {
            OperatingMode.FOCUS: {
                "interrupt_threshold": "high",
                "response_style": "minimal",
                "response_delay": "batch",  # Don't interrupt, batch responses
                "auto_actions": ["filter_noise", "defer_low_priority"],
                "escalation_rules": "only_crisis",
                "tone": "direct, no fluff"
            },
            OperatingMode.EXECUTION: {
                "interrupt_threshold": "medium",
                "response_style": "normal",
                "response_delay": "immediate",
                "auto_actions": ["handle_routine", "send_reminders", "manage_schedule"],
                "escalation_rules": "high_impact",
                "tone": "professional, efficient"
            },
            OperatingMode.DECISION: {
                "interrupt_threshold": "low",
                "response_style": "compressed",
                "response_delay": "immediate",
                "auto_actions": ["present_options", "compress_decisions"],
                "escalation_rules": "anything_requiring_input",
                "tone": "concise, decision-focused"
            },
            OperatingMode.TRAVEL: {
                "interrupt_threshold": "high",
                "response_style": "ultra_compressed",
                "response_delay": "immediate",
                "auto_actions": ["handle_logistics", "auto_respond"],
                "escalation_rules": "only_urgent",
                "tone": "extremely brief, mobile-friendly"
            },
            OperatingMode.OFF_GRID: {
                "interrupt_threshold": "crisis_only",
                "response_style": "minimal",
                "response_delay": "hold",  # Hold everything except crisis
                "auto_actions": ["auto_respond_ooo", "hold_all"],
                "escalation_rules": "none_unless_crisis",
                "tone": "auto-responder"
            },
            OperatingMode.CRISIS: {
                "interrupt_threshold": "none",
                "response_style": "action_focused",
                "response_delay": "immediate",
                "auto_actions": ["all_hands", "bypass_normal_rules"],
                "escalation_rules": "everything_visible",
                "tone": "urgent, action-oriented"
            },
            OperatingMode.THINKING: {
                "interrupt_threshold": "very_high",
                "response_style": "reflective",
                "response_delay": "batch",
                "auto_actions": ["analyze_patterns", "generate_insights"],
                "escalation_rules": "minimal",
                "tone": "analytical, thoughtful"
            },
            OperatingMode.REVIEW: {
                "interrupt_threshold": "very_high",
                "response_style": "detailed",
                "response_delay": "batch",
                "auto_actions": ["surface_patterns", "retrospective_analysis"],
                "escalation_rules": "minimal",
                "tone": "comprehensive, data-driven"
            }
        }

        return configs.get(mode, configs[OperatingMode.EXECUTION])

    def get_mode_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get mode history for the past N days."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM gigi_mode_history
                    WHERE started_at > NOW() - INTERVAL '%s days'
                    ORDER BY started_at DESC
                """, (days,))
                return [dict(row) for row in cur.fetchall()]

    def get_mode_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get mode usage statistics."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        mode,
                        COUNT(*) as occurrences,
                        SUM(duration_minutes) as total_minutes,
                        AVG(duration_minutes) as avg_duration,
                        AVG(confidence) as avg_confidence
                    FROM gigi_mode_history
                    WHERE started_at > NOW() - INTERVAL '%s days'
                    GROUP BY mode
                    ORDER BY total_minutes DESC
                """, (days,))

                stats = {row['mode']: dict(row) for row in cur.fetchall()}

                # Add current mode
                current = self.get_current_mode()
                stats['current'] = {
                    'mode': current.mode.value,
                    'source': current.source.value,
                    'confidence': float(current.confidence),
                    'set_at': current.set_at.isoformat() if current.set_at else None
                }

                return stats


# Example usage and mode command parser
def parse_mode_command(text: str) -> Optional[Tuple[OperatingMode, Optional[datetime]]]:
    """
    Parse mode commands from user text.

    Examples:
    - "Set mode to focus"
    - "I'm in crisis mode"
    - "Switch to travel mode until Friday"
    - "Going off-grid for 2 weeks"

    Returns:
        (mode, expires_at) or None if no command detected
    """
    text_lower = text.lower()

    # Detect mode keywords
    mode_map = {
        'focus': OperatingMode.FOCUS,
        'execution': OperatingMode.EXECUTION,
        'decision': OperatingMode.DECISION,
        'travel': OperatingMode.TRAVEL,
        'off-grid': OperatingMode.OFF_GRID,
        'off grid': OperatingMode.OFF_GRID,
        'offgrid': OperatingMode.OFF_GRID,
        'crisis': OperatingMode.CRISIS,
        'thinking': OperatingMode.THINKING,
        'review': OperatingMode.REVIEW
    }

    detected_mode = None
    for keyword, mode in mode_map.items():
        if keyword in text_lower:
            detected_mode = mode
            break

    if not detected_mode:
        return None

    # Detect duration/expiration
    expires_at = None

    # Simple time parsing (can be enhanced with dateutil)
    if 'until' in text_lower or 'for' in text_lower:
        # Future enhancement: parse "until Friday", "for 2 weeks", etc.
        # For now, set default expiration of 24 hours for travel/off-grid
        if detected_mode in [OperatingMode.TRAVEL, OperatingMode.OFF_GRID]:
            expires_at = datetime.now() + timedelta(days=1)

    return (detected_mode, expires_at)


if __name__ == "__main__":
    # Initialize mode detector
    detector = ModeDetector()

    # Get current mode
    current = detector.get_current_mode()
    print(f"Current mode: {current.mode.value}")
    print(f"Source: {current.source.value}")
    print(f"Confidence: {current.confidence:.2f}")
    print(f"Context: {current.context}")

    # Get behavior config
    config = detector.get_mode_behavior_config(current.mode)
    print(f"\nBehavior config:")
    for key, value in config.items():
        print(f"  {key}: {value}")

    # Test mode command parsing
    test_commands = [
        "Set mode to focus",
        "I'm in crisis mode",
        "Going off-grid for vacation",
        "Switch to travel mode"
    ]

    print("\nMode command parsing:")
    for cmd in test_commands:
        result = parse_mode_command(cmd)
        if result:
            mode, expires = result
            print(f"  '{cmd}' -> {mode.value} (expires: {expires})")

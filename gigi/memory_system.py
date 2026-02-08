"""
Gigi Memory System - Phase 1 Implementation

This is the foundation layer. Everything else depends on this.

Memory Types:
- explicit_instruction: Direct statements from Jason (confidence 1.0)
- correction: Jason correcting Gigi's behavior (confidence 0.9)
- confirmed_pattern: Repeated behavior Jason reinforced (confidence 0.7-0.9)
- inferred_pattern: Gigi detecting patterns (confidence 0.5-0.7)
- single_inference: One-time observations (confidence 0.3-0.5)
- temporary: Thinking mode insights (48hr decay)
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import logging

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    EXPLICIT_INSTRUCTION = "explicit_instruction"
    CORRECTION = "correction"
    CONFIRMED_PATTERN = "confirmed_pattern"
    INFERRED_PATTERN = "inferred_pattern"
    SINGLE_INFERENCE = "single_inference"
    TEMPORARY = "temporary"


class MemoryStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class MemorySource(Enum):
    EXPLICIT = "explicit"
    CORRECTION = "correction"
    PATTERN = "pattern"
    INFERENCE = "inference"


class ImpactLevel(Enum):
    HIGH = "high"      # Money, reputation, legal
    MEDIUM = "medium"  # Scheduling, communication
    LOW = "low"        # Preferences, formatting


@dataclass
class Memory:
    """A single memory with metadata."""
    id: str
    type: MemoryType
    content: str
    confidence: float
    source: MemorySource
    created_at: datetime
    last_confirmed_at: Optional[datetime]
    last_reinforced_at: Optional[datetime]
    reinforcement_count: int
    conflicts_with: List[str]
    status: MemoryStatus
    category: str
    impact_level: ImpactLevel
    metadata: Dict[str, Any]


class MemorySystem:
    """Manages Gigi's memory with decay, confidence, and conflict detection."""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL not set")

        # Fix for Mac Mini (Local) PostgreSQL URLs (postgres:// -> postgresql://)
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)

        self._init_schema()

    def _get_connection(self):
        """Get database connection."""
        return psycopg2.connect(self.database_url)

    def _init_schema(self):
        """Initialize database schema if not exists."""
        schema = """
        CREATE TABLE IF NOT EXISTS gigi_memories (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            confidence DECIMAL(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
            source VARCHAR(50) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            last_confirmed_at TIMESTAMP,
            last_reinforced_at TIMESTAMP,
            reinforcement_count INTEGER DEFAULT 0,
            conflicts_with UUID[],
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            category VARCHAR(50),
            impact_level VARCHAR(20),
            metadata JSONB DEFAULT '{}'::jsonb
        );

        CREATE INDEX IF NOT EXISTS idx_memories_type ON gigi_memories(type);
        CREATE INDEX IF NOT EXISTS idx_memories_status ON gigi_memories(status);
        CREATE INDEX IF NOT EXISTS idx_memories_confidence ON gigi_memories(confidence);
        CREATE INDEX IF NOT EXISTS idx_memories_category ON gigi_memories(category);

        CREATE TABLE IF NOT EXISTS gigi_memory_audit_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            memory_id UUID REFERENCES gigi_memories(id),
            event_type VARCHAR(50) NOT NULL,
            old_confidence DECIMAL(3,2),
            new_confidence DECIMAL(3,2),
            reason TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_audit_memory_id ON gigi_memory_audit_log(memory_id);
        CREATE INDEX IF NOT EXISTS idx_audit_created_at ON gigi_memory_audit_log(created_at);
        """

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(schema)
            conn.commit()

    def create_memory(
        self,
        content: str,
        memory_type: MemoryType,
        source: MemorySource,
        confidence: float,
        category: str,
        impact_level: ImpactLevel,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Create a new memory.

        Args:
            content: The actual preference/rule/pattern
            memory_type: Type of memory
            source: How this memory was created
            confidence: 0.0 to 1.0
            category: communication, scheduling, money, etc.
            impact_level: high, medium, low
            metadata: Additional context

        Returns:
            Memory ID
        """
        metadata = metadata or {}

        # Validate confidence ranges per type
        if memory_type == MemoryType.EXPLICIT_INSTRUCTION:
            confidence = 1.0
        elif memory_type == MemoryType.CORRECTION:
            confidence = min(confidence, 0.9)
        elif memory_type == MemoryType.CONFIRMED_PATTERN:
            confidence = min(confidence, 0.9)
        elif memory_type == MemoryType.INFERRED_PATTERN:
            confidence = min(confidence, 0.7)
        elif memory_type == MemoryType.SINGLE_INFERENCE:
            confidence = min(confidence, 0.5)

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO gigi_memories (
                        type, content, confidence, source, category, impact_level, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    memory_type.value,
                    content,
                    confidence,
                    source.value,
                    category,
                    impact_level.value,
                    Json(metadata)
                ))
                memory_id = cur.fetchone()[0]

                # Log creation
                self._log_event(
                    cur,
                    memory_id,
                    "created",
                    None,
                    confidence,
                    f"New {memory_type.value} memory"
                )

            conn.commit()

        logger.info(f"Created memory {memory_id}: {content[:50]}... (confidence: {confidence})")
        return str(memory_id)

    def get_memory(self, memory_id: str) -> Optional[Memory]:
        """Retrieve a specific memory by ID."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM gigi_memories WHERE id = %s",
                    (memory_id,)
                )
                row = cur.fetchone()

                if not row:
                    return None

                return Memory(
                    id=str(row['id']),
                    type=MemoryType(row['type']),
                    content=row['content'],
                    confidence=float(row['confidence']),
                    source=MemorySource(row['source']),
                    created_at=row['created_at'],
                    last_confirmed_at=row['last_confirmed_at'],
                    last_reinforced_at=row['last_reinforced_at'],
                    reinforcement_count=row['reinforcement_count'],
                    conflicts_with=[str(c) for c in (row['conflicts_with'] or [])],
                    status=MemoryStatus(row['status']),
                    category=row['category'],
                    impact_level=ImpactLevel(row['impact_level']),
                    metadata=row['metadata'] or {}
                )

    def query_memories(
        self,
        category: Optional[str] = None,
        status: Optional[MemoryStatus] = None,
        min_confidence: float = 0.0,
        memory_type: Optional[MemoryType] = None,
        limit: int = 100
    ) -> List[Memory]:
        """Query memories with filters."""
        conditions = ["1=1"]
        params = []

        if category:
            conditions.append("category = %s")
            params.append(category)

        if status:
            conditions.append("status = %s")
            params.append(status.value)

        if min_confidence > 0:
            conditions.append("confidence >= %s")
            params.append(min_confidence)

        if memory_type:
            conditions.append("type = %s")
            params.append(memory_type.value)

        query = f"""
            SELECT * FROM gigi_memories
            WHERE {' AND '.join(conditions)}
            ORDER BY confidence DESC, created_at DESC
            LIMIT %s
        """
        params.append(limit)

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

                return [Memory(
                    id=str(row['id']),
                    type=MemoryType(row['type']),
                    content=row['content'],
                    confidence=float(row['confidence']),
                    source=MemorySource(row['source']),
                    created_at=row['created_at'],
                    last_confirmed_at=row['last_confirmed_at'],
                    last_reinforced_at=row['last_reinforced_at'],
                    reinforcement_count=row['reinforcement_count'],
                    conflicts_with=[str(c) for c in (row['conflicts_with'] or [])],
                    status=MemoryStatus(row['status']),
                    category=row['category'],
                    impact_level=ImpactLevel(row['impact_level']),
                    metadata=row['metadata'] or {}
                ) for row in rows]

    def reinforce_memory(self, memory_id: str) -> bool:
        """
        Reinforce a memory (pattern was confirmed/repeated).
        Increases confidence by 10-20% (capped by type max).
        """
        memory = self.get_memory(memory_id)
        if not memory:
            return False

        # Calculate new confidence
        boost = 0.15  # 15% boost
        new_confidence = min(memory.confidence + boost, self._get_max_confidence(memory.type))

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE gigi_memories
                    SET confidence = %s,
                        last_reinforced_at = NOW(),
                        reinforcement_count = reinforcement_count + 1
                    WHERE id = %s
                """, (new_confidence, memory_id))

                self._log_event(
                    cur,
                    memory_id,
                    "reinforced",
                    memory.confidence,
                    new_confidence,
                    "Pattern confirmed/repeated"
                )

            conn.commit()

        logger.info(f"Reinforced memory {memory_id}: {memory.confidence:.2f} → {new_confidence:.2f}")
        return True

    def decay_memories(self):
        """
        Run decay process on all active memories.
        Should be run daily via cron job.
        """
        decay_rates = {
            MemoryType.EXPLICIT_INSTRUCTION: 0.0,      # Never decays
            MemoryType.CORRECTION: 0.05 / 30,          # 5% per month (~0.0017/day)
            MemoryType.CONFIRMED_PATTERN: 0.10 / 30,   # 10% per month (~0.0033/day)
            MemoryType.INFERRED_PATTERN: 0.20 / 30,    # 20% per month (~0.0067/day)
            MemoryType.SINGLE_INFERENCE: 0.30 / 30,    # 30% per month (~0.01/day) — was 50%/week (too aggressive)
            MemoryType.TEMPORARY: 0.50,                 # 50% per day
        }

        inactive_thresholds = {
            MemoryType.EXPLICIT_INSTRUCTION: 0.0,  # Never inactive
            MemoryType.CORRECTION: 0.3,
            MemoryType.CONFIRMED_PATTERN: 0.3,
            MemoryType.INFERRED_PATTERN: 0.2,
            MemoryType.SINGLE_INFERENCE: 0.15,     # Was 0.3 — too aggressive (killed memories in 3 days)
            MemoryType.TEMPORARY: 0.0,  # Archives after 48hrs
        }

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get all active memories
                cur.execute("SELECT * FROM gigi_memories WHERE status = 'active'")
                memories = cur.fetchall()

                for memory in memories:
                    memory_type = MemoryType(memory['type'])
                    old_confidence = float(memory['confidence'])
                    decay_rate = decay_rates.get(memory_type, 0.0)

                    # Apply decay
                    new_confidence = max(0.0, old_confidence - decay_rate)

                    # Check if should become inactive
                    threshold = inactive_thresholds.get(memory_type, 0.0)
                    new_status = 'inactive' if new_confidence < threshold else 'active'

                    # Handle temporary memories (archive after 48hrs)
                    if memory_type == MemoryType.TEMPORARY:
                        created_at = memory['created_at']
                        if datetime.now() - created_at > timedelta(hours=48):
                            new_status = 'archived'

                    # Update if changed
                    if new_confidence != old_confidence or new_status != memory['status']:
                        cur.execute("""
                            UPDATE gigi_memories
                            SET confidence = %s, status = %s
                            WHERE id = %s
                        """, (new_confidence, new_status, memory['id']))

                        self._log_event(
                            cur,
                            str(memory['id']),
                            "decayed",
                            old_confidence,
                            new_confidence,
                            f"Status: {memory['status']} → {new_status}"
                        )

            conn.commit()

        logger.info("Memory decay completed")

    def detect_conflicts(self, new_content: str, category: str) -> List[Memory]:
        """
        Detect potential conflicts with existing memories.
        Returns list of potentially conflicting memories.
        """
        # Simple keyword-based conflict detection
        # TODO: Implement semantic similarity for better detection
        memories = self.query_memories(category=category, status=MemoryStatus.ACTIVE)

        conflicts = []
        for memory in memories:
            # Check for direct contradictions
            # This is a simplified version - could use NLP for better detection
            if self._might_conflict(new_content, memory.content):
                conflicts.append(memory)

        return conflicts

    def _might_conflict(self, content1: str, content2: str) -> bool:
        """Simple conflict detection based on keywords."""
        # Look for opposing terms
        opposites = [
            ('always', 'never'),
            ('prefer', 'avoid'),
            ('yes', 'no'),
            ('include', 'exclude')
        ]

        content1_lower = content1.lower()
        content2_lower = content2.lower()

        for word1, word2 in opposites:
            if (word1 in content1_lower and word2 in content2_lower) or \
               (word2 in content1_lower and word1 in content2_lower):
                return True

        return False

    def _get_max_confidence(self, memory_type: MemoryType) -> float:
        """Get maximum confidence allowed for memory type."""
        max_confidence = {
            MemoryType.EXPLICIT_INSTRUCTION: 1.0,
            MemoryType.CORRECTION: 0.9,
            MemoryType.CONFIRMED_PATTERN: 0.9,
            MemoryType.INFERRED_PATTERN: 0.7,
            MemoryType.SINGLE_INFERENCE: 0.5,
            MemoryType.TEMPORARY: 0.5,
        }
        return max_confidence.get(memory_type, 1.0)

    def _log_event(
        self,
        cursor,
        memory_id: str,
        event_type: str,
        old_confidence: Optional[float],
        new_confidence: Optional[float],
        reason: str
    ):
        """Log memory event to audit log."""
        cursor.execute("""
            INSERT INTO gigi_memory_audit_log (
                memory_id, event_type, old_confidence, new_confidence, reason
            ) VALUES (%s, %s, %s, %s, %s)
        """, (memory_id, event_type, old_confidence, new_confidence, reason))

    def get_audit_log(self, memory_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get audit log for a specific memory."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM gigi_memory_audit_log
                    WHERE memory_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (memory_id, limit))
                return [dict(row) for row in cur.fetchall()]


# Example usage
if __name__ == "__main__":
    # Initialize memory system
    memory_system = MemorySystem()

    # Create an explicit instruction
    memory_id = memory_system.create_memory(
        content="Never book United Airlines flights",
        memory_type=MemoryType.EXPLICIT_INSTRUCTION,
        source=MemorySource.EXPLICIT,
        confidence=1.0,
        category="travel",
        impact_level=ImpactLevel.HIGH,
        metadata={"reason": "Jason hates United"}
    )

    print(f"Created memory: {memory_id}")

    # Query memories
    travel_memories = memory_system.query_memories(category="travel", min_confidence=0.7)
    for memory in travel_memories:
        print(f"- {memory.content} (confidence: {memory.confidence})")

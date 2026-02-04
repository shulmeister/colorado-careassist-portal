#!/usr/bin/env python3
"""
Migration script to create Gigi memory tables in production database.

Usage:
    python migrate_memory.py
"""

import os
import sys
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    sys.exit(1)

# Fix for Mac Mini (Local) PostgreSQL URLs (postgres:// -> postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

MIGRATION_SQL = """
-- Gigi Memory System Tables

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

CREATE INDEX IF NOT EXISTS idx_gigi_memories_type ON gigi_memories(type);
CREATE INDEX IF NOT EXISTS idx_gigi_memories_status ON gigi_memories(status);
CREATE INDEX IF NOT EXISTS idx_gigi_memories_confidence ON gigi_memories(confidence);
CREATE INDEX IF NOT EXISTS idx_gigi_memories_category ON gigi_memories(category);
CREATE INDEX IF NOT EXISTS idx_gigi_memories_created_at ON gigi_memories(created_at);

CREATE TABLE IF NOT EXISTS gigi_memory_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID REFERENCES gigi_memories(id),
    event_type VARCHAR(50) NOT NULL,
    old_confidence DECIMAL(3,2),
    new_confidence DECIMAL(3,2),
    reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gigi_audit_memory_id ON gigi_memory_audit_log(memory_id);
CREATE INDEX IF NOT EXISTS idx_gigi_audit_created_at ON gigi_memory_audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_gigi_audit_event_type ON gigi_memory_audit_log(event_type);
"""

def run_migration():
    """Run migration to create memory tables."""
    print("=" * 60)
    print("GIGI MEMORY SYSTEM MIGRATION")
    print("=" * 60)
    print(f"\nConnecting to database...")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        print("Creating memory tables...")
        cur.execute(MIGRATION_SQL)

        # Verify tables were created
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name LIKE 'gigi_%'
            ORDER BY table_name
        """)
        tables = cur.fetchall()

        conn.commit()

        print("\n✓ Migration successful!")
        print("\nTables created:")
        for table in tables:
            print(f"  - {table[0]}")

        # Count existing memories
        cur.execute("SELECT COUNT(*) FROM gigi_memories")
        count = cur.fetchone()[0]
        print(f"\nExisting memories: {count}")

        cur.close()
        conn.close()

        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()

#!/usr/bin/env python3
"""
Migration script for Attio-inspired CRM enhancements.

Phase 1: Relationship Graph + Time-in-Stage
Phase 2: Unified Activity Timeline
Phase 3: AI Enrichment fields

Run with: python scripts/migrate_attio_enhancements.py
"""

import os
import sys
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect
from database import db_manager

def get_dialect():
    """Get the database dialect (sqlite or postgresql)"""
    return db_manager.engine.dialect.name

def column_exists(conn, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    dialect = get_dialect()
    if dialect == "sqlite":
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return any(row[1] == column_name for row in rows)
    else:
        query = text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=:table AND column_name=:column"
        )
        row = conn.execute(query, {"table": table_name, "column": column_name}).fetchone()
        return row is not None

def table_exists(conn, table_name: str) -> bool:
    """Check if a table exists"""
    dialect = get_dialect()
    if dialect == "sqlite":
        result = conn.execute(text(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
        )).fetchone()
        return result is not None
    else:
        result = conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_name=:table"
        ), {"table": table_name}).fetchone()
        return result is not None

def add_column_safe(conn, table_name: str, column_def: str):
    """Add a column if it doesn't exist"""
    column_name = column_def.split()[0]
    if not column_exists(conn, table_name, column_name):
        dialect = get_dialect()
        if dialect == "sqlite":
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_def}"))
        else:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_def}"))
        print(f"  ✓ Added column {table_name}.{column_name}")
    else:
        print(f"  - Column {table_name}.{column_name} already exists")

def migrate_phase1_relationship_graph(conn):
    """Phase 1: Create relationship tables and add stage tracking"""
    print("\n=== Phase 1: Relationship Graph & Time-in-Stage ===\n")

    dialect = get_dialect()

    # 1. Create deal_contacts table
    if not table_exists(conn, "deal_contacts"):
        if dialect == "sqlite":
            conn.execute(text("""
                CREATE TABLE deal_contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deal_id INTEGER NOT NULL,
                    contact_id INTEGER NOT NULL,
                    role VARCHAR(100),
                    is_primary BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE,
                    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
                    UNIQUE(deal_id, contact_id)
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE deal_contacts (
                    id SERIAL PRIMARY KEY,
                    deal_id INTEGER NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
                    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                    role VARCHAR(100),
                    is_primary BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(deal_id, contact_id)
                )
            """))
        conn.execute(text("CREATE INDEX idx_deal_contacts_deal ON deal_contacts(deal_id)"))
        conn.execute(text("CREATE INDEX idx_deal_contacts_contact ON deal_contacts(contact_id)"))
        print("  ✓ Created deal_contacts table")
    else:
        print("  - deal_contacts table already exists")

    # 2. Create deal_stage_history table
    if not table_exists(conn, "deal_stage_history"):
        if dialect == "sqlite":
            conn.execute(text("""
                CREATE TABLE deal_stage_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deal_id INTEGER NOT NULL,
                    from_stage VARCHAR(100),
                    to_stage VARCHAR(100) NOT NULL,
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    changed_by VARCHAR(255),
                    duration_seconds INTEGER,
                    FOREIGN KEY (deal_id) REFERENCES deals(id) ON DELETE CASCADE
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE deal_stage_history (
                    id SERIAL PRIMARY KEY,
                    deal_id INTEGER NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
                    from_stage VARCHAR(100),
                    to_stage VARCHAR(100) NOT NULL,
                    changed_at TIMESTAMP DEFAULT NOW(),
                    changed_by VARCHAR(255),
                    duration_seconds INTEGER
                )
            """))
        conn.execute(text("CREATE INDEX idx_deal_stage_history_deal ON deal_stage_history(deal_id)"))
        conn.execute(text("CREATE INDEX idx_deal_stage_history_changed ON deal_stage_history(changed_at)"))
        print("  ✓ Created deal_stage_history table")
    else:
        print("  - deal_stage_history table already exists")

    # 3. Add stage_entered_at to deals
    add_column_safe(conn, "deals", "stage_entered_at TIMESTAMP")

    # 4. Initialize stage_entered_at from updated_at for existing deals
    result = conn.execute(text(
        "UPDATE deals SET stage_entered_at = updated_at WHERE stage_entered_at IS NULL AND stage IS NOT NULL"
    ))
    if result.rowcount > 0:
        print(f"  ✓ Initialized stage_entered_at for {result.rowcount} existing deals")

def migrate_phase1_deal_contacts(conn):
    """Migrate existing contact_ids JSON to deal_contacts table"""
    print("\n=== Migrating Deal Contacts ===\n")

    # Get deals with contact_ids
    deals = conn.execute(text(
        "SELECT id, contact_ids FROM deals WHERE contact_ids IS NOT NULL AND contact_ids != ''"
    )).fetchall()

    migrated = 0
    for deal in deals:
        deal_id = deal[0]
        contact_ids_json = deal[1]

        try:
            contact_ids = json.loads(contact_ids_json)
            if not isinstance(contact_ids, list):
                continue

            for i, contact_id in enumerate(contact_ids):
                # Check if already migrated
                existing = conn.execute(text(
                    "SELECT id FROM deal_contacts WHERE deal_id = :deal_id AND contact_id = :contact_id"
                ), {"deal_id": deal_id, "contact_id": contact_id}).fetchone()

                if not existing:
                    # First contact becomes primary
                    is_primary = (i == 0)
                    conn.execute(text(
                        "INSERT INTO deal_contacts (deal_id, contact_id, is_primary) VALUES (:deal_id, :contact_id, :is_primary)"
                    ), {"deal_id": deal_id, "contact_id": contact_id, "is_primary": is_primary})
                    migrated += 1
        except json.JSONDecodeError:
            continue

    if migrated > 0:
        print(f"  ✓ Migrated {migrated} deal-contact relationships")
    else:
        print("  - No deal contacts to migrate")

def migrate_phase2_activity_timeline(conn):
    """Phase 2: Add unified timeline fields to activity_logs"""
    print("\n=== Phase 2: Unified Activity Timeline ===\n")

    # Add new columns to activity_logs
    add_column_safe(conn, "activity_logs", "title VARCHAR(255)")
    add_column_safe(conn, "activity_logs", "direction VARCHAR(20)")
    add_column_safe(conn, "activity_logs", "duration_seconds INTEGER")
    add_column_safe(conn, "activity_logs", "participants TEXT")
    add_column_safe(conn, "activity_logs", "content TEXT")
    add_column_safe(conn, "activity_logs", "attachments TEXT")
    add_column_safe(conn, "activity_logs", "external_id VARCHAR(255)")
    add_column_safe(conn, "activity_logs", "external_url TEXT")
    add_column_safe(conn, "activity_logs", "occurred_at TIMESTAMP")

    # Initialize occurred_at from created_at
    result = conn.execute(text(
        "UPDATE activity_logs SET occurred_at = created_at WHERE occurred_at IS NULL"
    ))
    if result.rowcount > 0:
        print(f"  ✓ Initialized occurred_at for {result.rowcount} existing activities")

    # Create index on occurred_at if not exists
    try:
        conn.execute(text("CREATE INDEX idx_activity_logs_occurred ON activity_logs(occurred_at)"))
        print("  ✓ Created index on activity_logs.occurred_at")
    except:
        print("  - Index on occurred_at already exists")

    # Create index on external_id if not exists
    try:
        conn.execute(text("CREATE INDEX idx_activity_logs_external ON activity_logs(external_id)"))
        print("  ✓ Created index on activity_logs.external_id")
    except:
        print("  - Index on external_id already exists")

def migrate_phase3_enrichment(conn):
    """Phase 3: Add AI enrichment fields to referral_sources"""
    print("\n=== Phase 3: AI Enrichment Fields ===\n")

    # Add enrichment columns to referral_sources
    add_column_safe(conn, "referral_sources", "employee_count VARCHAR(50)")
    add_column_safe(conn, "referral_sources", "industry VARCHAR(100)")
    add_column_safe(conn, "referral_sources", "enriched_at TIMESTAMP")
    add_column_safe(conn, "referral_sources", "enrichment_confidence FLOAT")

def run_migration():
    """Run all migrations"""
    print("=" * 60)
    print("Attio-Inspired CRM Enhancement Migration")
    print("=" * 60)
    print(f"\nDatabase: {get_dialect()}")
    print(f"Time: {datetime.now().isoformat()}")

    with db_manager.engine.connect() as conn:
        # Phase 1
        migrate_phase1_relationship_graph(conn)
        migrate_phase1_deal_contacts(conn)

        # Phase 2
        migrate_phase2_activity_timeline(conn)

        # Phase 3
        migrate_phase3_enrichment(conn)

        conn.commit()

    print("\n" + "=" * 60)
    print("Migration completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    run_migration()

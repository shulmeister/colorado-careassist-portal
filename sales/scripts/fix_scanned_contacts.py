#!/usr/bin/env python3
"""
Fix scanned contacts that have NULL last_activity field
This makes them visible in dashboard with active filters
"""

import os
import sys
from sqlalchemy import create_engine, text

# Get database URL
db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

engine = create_engine(db_url)

with engine.connect() as conn:
    # Update contacts where last_activity is NULL but last_seen is set
    # This fixes contacts from business card scans
    result = conn.execute(text("""
        UPDATE contacts
        SET last_activity = last_seen
        WHERE last_activity IS NULL
        AND last_seen IS NOT NULL
        AND account_manager IN ('jen@coloradocareassist.com', 'cosprings@coloradocareassist.com', 'jacob@coloradocareassist.com')
        AND source = 'Auto-Scan Business Card'
    """))

    conn.commit()

    print(f"✅ Updated {result.rowcount} contacts")
    print(f"   Set last_activity = last_seen for scanned business cards")

    # Verify the fix
    result = conn.execute(text("""
        SELECT account_manager, COUNT(*) as count
        FROM contacts
        WHERE account_manager IN ('jen@coloradocareassist.com', 'cosprings@coloradocareassist.com', 'jacob@coloradocareassist.com')
        AND source = 'Auto-Scan Business Card'
        GROUP BY account_manager
        ORDER BY count DESC
    """)).fetchall()

    print(f"\n=== SCANNED BUSINESS CARD CONTACTS ===")
    for row in result:
        print(f"{row[0]}: {row[1]} contacts")

    # Show sample of Jen's contacts
    result = conn.execute(text("""
        SELECT id, name, company, created_at, last_activity
        FROM contacts
        WHERE account_manager = 'jen@coloradocareassist.com'
        AND source = 'Auto-Scan Business Card'
        ORDER BY created_at DESC
        LIMIT 5
    """)).fetchall()

    print(f"\n=== SAMPLE JEN'S CONTACTS ===")
    for row in result:
        print(f"ID: {row[0]}, Name: {row[1]}, Company: {row[2]}")
        print(f"  Created: {row[3]}, Last Activity: {row[4]}\n")

print("\n✅ Done! Scanned contacts should now appear in dashboard.")

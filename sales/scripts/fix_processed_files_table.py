#!/usr/bin/env python3
"""
Fix processed_drive_files table to handle renamed business card folders.

Old folder_type: business_cards
New folder_types: business_cards_jacob, business_cards_jen, business_cards_cosprings

Strategy: Update old "business_cards" entries to "business_cards_jacob" since that was the original Jacob folder.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db import get_db
from sqlalchemy import text

def main():
    db = next(get_db())

    # Check current state
    print("Current folder_types in database:")
    result = db.execute(text("""
        SELECT folder_type, COUNT(*) as count
        FROM processed_drive_files
        GROUP BY folder_type
        ORDER BY count DESC
    """)).fetchall()

    for row in result:
        print(f"  {row[0]}: {row[1]} files")

    # Count old business_cards entries
    old_count = db.execute(text("""
        SELECT COUNT(*) FROM processed_drive_files
        WHERE folder_type = 'business_cards'
    """)).scalar()

    print(f"\nFound {old_count} entries with old 'business_cards' folder_type")

    if old_count > 0:
        print("\nUpdating old 'business_cards' entries to 'business_cards_jacob'...")
        db.execute(text("""
            UPDATE processed_drive_files
            SET folder_type = 'business_cards_jacob'
            WHERE folder_type = 'business_cards'
        """))
        db.commit()
        print(f"✓ Updated {old_count} records")
    else:
        print("\nNo old entries to update. Database is already clean.")

    # Show final state
    print("\nFinal folder_types in database:")
    result = db.execute(text("""
        SELECT folder_type, COUNT(*) as count
        FROM processed_drive_files
        GROUP BY folder_type
        ORDER BY count DESC
    """)).fetchall()

    for row in result:
        print(f"  {row[0]}: {row[1]} files")

    print("\n✓ Database fix complete!")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Sync data from Google Sheets to database"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Run the sync from Google Sheets"""
    try:
        from migrate_data import GoogleSheetsMigrator
        
        print("=" * 60)
        print("Syncing Data from Google Sheets")
        print("=" * 60)
        
        migrator = GoogleSheetsMigrator()
        result = migrator.migrate_all_data()
        
        if result["success"]:
            print(f"\n✅ Sync successful!")
            print(f"   📊 New visits added: {result['visits_migrated']}")
            print(f"   ⏰ New time entries added: {result['time_entries_migrated']}")
            return 0
        else:
            print(f"\n❌ Sync failed: {result.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        print(f"\n❌ Error during sync: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

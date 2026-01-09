#!/usr/bin/env python3
"""Debug script to test sync and see what's happening"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

def main():
    try:
        from migrate_data import GoogleSheetsMigrator
        from database import db_manager
        from models import Visit
        from sqlalchemy.orm import sessionmaker
        
        print("=" * 60)
        print("DEBUG: Testing Google Sheets Sync")
        print("=" * 60)
        
        # Check current database count
        Session = sessionmaker(bind=db_manager.engine)
        db = Session()
        current_count = db.query(Visit).count()
        print(f"\nCurrent visits in database: {current_count}")
        
        # Test migration
        print("\n" + "=" * 60)
        print("Running migration...")
        print("=" * 60)
        
        migrator = GoogleSheetsMigrator()
        result = migrator.migrate_all_data()
        
        print(f"\nMigration result: {result}")
        
        # Check new count
        db = Session()
        new_count = db.query(Visit).count()
        print(f"\nNew visits in database: {new_count}")
        print(f"Difference: {new_count - current_count}")
        
        # Show some sample visits from database
        print("\n" + "=" * 60)
        print("Sample visits from database (last 5):")
        print("=" * 60)
        recent = db.query(Visit).order_by(Visit.created_at.desc()).limit(5).all()
        for v in recent:
            print(f"  Date: {v.visit_date}, Business: {v.business_name}, Stop: {v.stop_number}")
        
        db.close()
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

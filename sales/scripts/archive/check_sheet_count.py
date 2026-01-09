#!/usr/bin/env python3
"""Check row counts in Google Sheet vs database"""

import os
from dotenv import load_dotenv
from migrate_data import GoogleSheetsMigrator
from sqlalchemy.orm import sessionmaker
from database import db_manager
from models import Visit

load_dotenv()

def check_counts():
    """Compare Google Sheet row count with database count"""
    print("=" * 60)
    print("GOOGLE SHEET vs DATABASE COUNT CHECK")
    print("=" * 60)
    
    # Check database
    SessionLocal = sessionmaker(bind=db_manager.engine)
    db = SessionLocal()
    db_count = db.query(Visit).count()
    print(f"\n📊 Database visit count: {db_count}")
    
    # Check Google Sheet
    try:
        migrator = GoogleSheetsMigrator()
        spreadsheet = migrator.client.open_by_key(migrator.sheet_id)
        
        # Find visits worksheet
        worksheets = spreadsheet.worksheets()
        visits_worksheet = None
        
        possible_names = ['visits', 'tracker', 'visit tracker', 'sales tracker - visits', 'sales tracker']
        for ws in worksheets:
            ws_name_lower = ws.title.lower()
            if ws_name_lower in [name.lower() for name in possible_names] or 'visit' in ws_name_lower:
                visits_worksheet = ws
                break
        
        if not visits_worksheet and worksheets:
            visits_worksheet = worksheets[0]
        
        if visits_worksheet:
            all_values = visits_worksheet.get_all_values()
            sheet_total_rows = len(all_values)
            sheet_data_rows = len(all_values) - 1  # Excluding header
            
            print(f"📄 Google Sheet: '{visits_worksheet.title}'")
            print(f"   Total rows: {sheet_total_rows} (including header)")
            print(f"   Data rows: {sheet_data_rows}")
            
            difference = db_count - sheet_data_rows
            print(f"\n📈 Difference: {difference} ({'+' if difference > 0 else ''}{difference} visits)")
            
            if abs(difference) > 10:
                print(f"\n⚠️  Significant difference detected!")
                print(f"   Database has {db_count} visits")
                print(f"   Sheet has {sheet_data_rows} data rows")
        else:
            print("\n❌ Could not find visits worksheet")
            
    except Exception as e:
        print(f"\n❌ Error checking Google Sheet: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_counts()

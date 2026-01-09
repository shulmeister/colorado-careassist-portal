#!/usr/bin/env python3
"""Test script to diagnose Google Sheets connection and daily visits updates"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_environment():
    """Check if required environment variables are set"""
    print("=" * 60)
    print("Testing Environment Variables")
    print("=" * 60)
    
    sheet_id = os.getenv("SHEET_ID")
    service_account_key = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
    
    if sheet_id:
        print(f"✓ SHEET_ID is set: {sheet_id}")
    else:
        print("✗ SHEET_ID is not set")
        return False
    
    if service_account_key:
        print("✓ GOOGLE_SERVICE_ACCOUNT_KEY is set")
        # Try to parse it as JSON
        try:
            import json
            json.loads(service_account_key)
            print("✓ GOOGLE_SERVICE_ACCOUNT_KEY is valid JSON")
        except json.JSONDecodeError as e:
            print(f"✗ GOOGLE_SERVICE_ACCOUNT_KEY is not valid JSON: {e}")
            return False
    else:
        print("✗ GOOGLE_SERVICE_ACCOUNT_KEY is not set")
        return False
    
    return True

def check_database_counts():
    """Check current database counts"""
    print("\n" + "=" * 60)
    print("Database Counts")
    print("=" * 60)
    
    try:
        from database import db_manager
        from models import Visit, TimeEntry
        from sqlalchemy.orm import sessionmaker
        
        Session = sessionmaker(bind=db_manager.engine)
        db = Session()
        
        visit_count = db.query(Visit).count()
        time_entry_count = db.query(TimeEntry).count()
        
        print(f"✓ Visits in database: {visit_count}")
        print(f"✓ Time entries in database: {time_entry_count}")
        
        # Get most recent visit
        most_recent = db.query(Visit).order_by(Visit.created_at.desc()).first()
        if most_recent:
            print(f"✓ Most recent visit: {most_recent.business_name} on {most_recent.visit_date}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"✗ Error checking database: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_connection():
    """Test Google Sheets connection"""
    print("\n" + "=" * 60)
    print("Testing Google Sheets Connection")
    print("=" * 60)
    
    try:
        from google_sheets import GoogleSheetsManager
        
        manager = GoogleSheetsManager()
        print("✓ GoogleSheetsManager initialized successfully")
        
        # Test connection
        if manager.test_connection():
            print("✓ Connection test passed")
        else:
            print("✗ Connection test failed")
            return False
        
        # Get worksheets
        spreadsheet = manager.client.open_by_key(manager.sheet_id)
        worksheets = spreadsheet.worksheets()
        print(f"✓ Found {len(worksheets)} worksheets:")
        for ws in worksheets:
            print(f"  - {ws.title}")
        
        # Check Visits worksheet
        try:
            visits_worksheet = None
            for ws in worksheets:
                if ws.title.lower() in ['visits', 'tracker', 'visit tracker']:
                    visits_worksheet = ws
                    break
            
            if visits_worksheet:
                print(f"\n✓ Visits worksheet found: {visits_worksheet.title}")
                
                # Get header row
                headers = visits_worksheet.row_values(1)
                print(f"  Headers: {headers}")
                
                # Get row count
                all_values = visits_worksheet.get_all_values()
                total_rows = len(all_values) - 1  # Exclude header
                print(f"  Total visit rows in sheet: {total_rows}")
                
                # Get a few sample rows
                rows = all_values[1:4] if len(all_values) > 1 else []
                if rows:
                    print(f"  Sample rows:")
                    for i, row in enumerate(rows, start=2):
                        print(f"    Row {i}: {row[:6]}")  # Show first 6 columns
            else:
                print("\n✗ No Visits worksheet found")
                
        except Exception as e:
            print(f"\n✗ Error checking Visits worksheet: {e}")
        
        # Check Daily Summary worksheet
        try:
            daily_summary = spreadsheet.worksheet("Daily Summary")
            print(f"\n✓ Daily Summary worksheet found")
            
            # Get header row
            headers = daily_summary.row_values(1)
            print(f"  Headers: {headers}")
            
            # Get row count
            all_values = daily_summary.get_all_values()
            total_rows = len(all_values) - 1  # Exclude header
            print(f"  Total rows in Daily Summary: {total_rows}")
            
            # Get a few sample rows
            rows = all_values[1:4] if len(all_values) > 1 else []
            if rows:
                print(f"  Sample rows:")
                for i, row in enumerate(rows, start=2):
                    print(f"    Row {i}: {row}")
            else:
                print("  No data rows found yet")
                
            return True
        except Exception as e:
            print(f"\n✗ Daily Summary worksheet not found or error: {e}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing connection: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\nGoogle Sheets Connection Diagnostic Tool\n")
    
    # Test environment
    if not test_environment():
        print("\n❌ Environment check failed. Please set required environment variables.")
        sys.exit(1)
    
    # Check database counts
    check_database_counts()
    
    # Test connection
    if not test_connection():
        print("\n❌ Connection test failed.")
        sys.exit(1)
    
    print("\n✅ Connection test passed!")
    print("\n💡 To sync data from Google Sheets, run: python3 sync_from_sheets.py")

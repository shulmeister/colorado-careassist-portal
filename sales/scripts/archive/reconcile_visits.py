#!/usr/bin/env python3
"""
Reconcile database visits with Google Sheet.
Makes database exactly match the sheet - removes visits not in sheet, adds missing ones.
Google Sheet is the source of truth.
"""

import os
import sys
from dotenv import load_dotenv
from migrate_data import GoogleSheetsMigrator
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, and_
from database import db_manager
from models import Visit
from datetime import datetime
import re

load_dotenv()

def normalize_business_name(name):
    """Normalize business name for comparison"""
    if not name:
        return ""
    normalized = (name or "").lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized

def get_sheet_visits_key(visit_data):
    """Get normalized key for a visit from sheet data"""
    date = visit_data.get('date')
    business = normalize_business_name(visit_data.get('business_name', ''))
    stop = visit_data.get('stop_number', 1)
    return f"{date.isoformat() if date else 'NODATE'}|{business}|{stop}"

def get_db_visit_key(visit):
    """Get normalized key for a database visit"""
    date = visit.visit_date.date() if visit.visit_date else None
    business = normalize_business_name(visit.business_name or '')
    stop = visit.stop_number or 1
    return f"{date.isoformat() if date else 'NODATE'}|{business}|{stop}"

def parse_visit_row(row, row_index=None, all_rows=None, migrator=None):
    """Parse a row from Google Sheet into visit data - with intelligence enhancement"""
    visit_date = None
    stop_number = None
    business_name = ""
    address = ""
    city = ""
    notes = ""
    
    # Stop (column 0)
    if len(row) >= 1 and row[0]:
        try:
            stop_number = int(float(row[0]))
        except:
            stop_number = 1
    
    # Business Name (column 1)
    if len(row) >= 2:
        business_name = (row[1] or "Unknown Facility").strip()
    
    # Location/Address (column 2)
    if len(row) >= 3:
        address = (row[2] or "").strip()[:500]
    
    # City (column 3)
    if len(row) >= 4:
        city = (row[3] or "").strip()[:500]
    
    # Notes (column 4)
    if len(row) >= 5:
        notes = (row[4] or "").strip()[:1000]
    
    # ENHANCE business name and city using intelligence (if migrator provided)
    if migrator:
        business_name = migrator._enhance_business_name(business_name, address, notes)
        city = migrator._enhance_city(city, address, notes)
    
    # Date (column 5) - IMPORTANT: Don't default to today if date is missing
    if len(row) >= 6 and row[5] and row[5].strip() and row[5].strip() != "—":
        date_str = row[5].strip()
        try:
            if ' ' in date_str:
                visit_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            else:
                visit_date = datetime.strptime(date_str, '%Y-%m-%d')
        except:
            try:
                visit_date = datetime.strptime(date_str, '%m/%d/%Y')
            except:
                try:
                    visit_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                except:
                    visit_date = None  # Don't default to today
    else:
        visit_date = None  # Don't default to today
    
    # Try to infer missing date if migrator provided
    if not visit_date and migrator and row_index is not None and all_rows:
        visit_date = migrator._get_date_from_daily_summary(row_index, all_rows)
        if not visit_date:
            visit_date = migrator._infer_missing_date(row_index, all_rows)
    
    # Final fallback (only if still no date)
    if not visit_date:
        visit_date = datetime.now()
    
    return {
        'stop_number': stop_number or 1,
        'business_name': business_name,
        'address': address,
        'city': city,
        'notes': notes,
        'date': visit_date.date() if visit_date else datetime.now().date(),
        'datetime': visit_date or datetime.now()
    }

def reconcile_visits(dry_run=True):
    """Reconcile database visits with Google Sheet"""
    print("=" * 60)
    print("RECONCILE DATABASE WITH GOOGLE SHEET")
    print("=" * 60)
    print("\nGoogle Sheet is the source of truth.")
    print("Database will be updated to match exactly.\n")
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
    else:
        print("⚠️  LIVE MODE - Database will be updated!")
    
    SessionLocal = sessionmaker(bind=db_manager.engine)
    db = SessionLocal()
    
    try:
        # Get all visits from Google Sheet
        print("\n📄 Reading Google Sheet...")
        migrator = GoogleSheetsMigrator()
        spreadsheet = migrator.client.open_by_key(migrator.sheet_id)
        
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
        
        if not visits_worksheet:
            print("\n❌ Could not find visits worksheet")
            return
        
        all_values = visits_worksheet.get_all_values()
        data_rows = all_values[1:] if len(all_values) > 1 else []
        
        print(f"   Found {len(data_rows)} data rows in sheet")
        
        # Parse all visits from sheet - deduplicate (unique by date + business + stop)
        sheet_visits = {}
        for row_index, row in enumerate(data_rows, start=1):  # Start at 1 (after header)
            if not row or len(row) < 3:
                continue
            try:
                visit_data = parse_visit_row(row, row_index=row_index + 1, all_rows=data_rows, migrator=migrator)
                key = get_sheet_visits_key(visit_data)
                if key not in sheet_visits:  # Keep first occurrence of duplicates
                    sheet_visits[key] = visit_data
            except Exception as e:
                print(f"   Warning: Failed to parse row {row_index + 1}: {e}")
                continue
        
        print(f"   Parsed {len(sheet_visits)} unique visits from sheet (deduplicated from {len(data_rows)} rows)")
        
        # Get all visits from database
        print("\n📊 Reading database...")
        db_visits = db.query(Visit).all()
        db_visits_map = {}
        db_visits_by_id = {}
        for visit in db_visits:
            key = get_db_visit_key(visit)
            if key not in db_visits_map:
                db_visits_map[key] = []
            db_visits_map[key].append(visit)
            db_visits_by_id[visit.id] = visit
        
        print(f"   Found {len(db_visits)} visits in database")
        print(f"   {len(db_visits_map)} unique visit keys")
        
        # Find visits to add (in sheet but not in DB)
        visits_to_add = []
        matched_db_visit_ids = set()
        
        for key, visit_data in sheet_visits.items():
            if key in db_visits_map and len(db_visits_map[key]) > 0:
                # Found matching visit - mark as matched (keep first one)
                matched_visit = db_visits_map[key].pop(0)
                matched_db_visit_ids.add(matched_visit.id)
                # If there are duplicates in DB with same key, they'll be removed
            else:
                # No match in DB - need to add
                visits_to_add.append(visit_data)
        
        # Find visits to remove (in DB but not in sheet, or duplicates)
        visits_to_remove = []
        for visit in db_visits:
            if visit.id not in matched_db_visit_ids:
                visits_to_remove.append(visit)
        
        print("\n" + "=" * 60)
        print("RECONCILIATION SUMMARY")
        print("=" * 60)
        print(f"📄 Google Sheet: {len(data_rows)} rows → {len(sheet_visits)} unique visits")
        print(f"📊 Database visits: {len(db_visits)}")
        print(f"➕ Visits to add: {len(visits_to_add)}")
        print(f"➖ Visits to remove: {len(visits_to_remove)}")
        print(f"✅ Expected final count: {len(sheet_visits)}")
        
        if visits_to_add:
            print(f"\n➕ Will add these {len(visits_to_add)} visits:")
            for v in visits_to_add[:5]:
                print(f"   {v['business_name']} on {v['date']} (Stop {v['stop_number']})")
            if len(visits_to_add) > 5:
                print(f"   ... and {len(visits_to_add) - 5} more")
        
        if visits_to_remove:
            print(f"\n➖ Will remove these {len(visits_to_remove)} visits:")
            for v in visits_to_remove[:5]:
                print(f"   ID {v.id}: {v.business_name} on {v.visit_date}")
            if len(visits_to_remove) > 5:
                print(f"   ... and {len(visits_to_remove) - 5} more")
        
        if not dry_run:
            # Remove visits not in sheet
            for visit in visits_to_remove:
                db.delete(visit)
            
            # Add visits from sheet
            for visit_data in visits_to_add:
                visit = Visit(
                    stop_number=visit_data['stop_number'],
                    business_name=visit_data['business_name'],
                    address=visit_data['address'],
                    city=visit_data['city'],
                    notes=visit_data['notes'],
                    visit_date=visit_data['datetime']
                )
                db.add(visit)
            
            db.commit()
            
            # Verify final count
            final_count = db.query(Visit).count()
            print(f"\n✅ Reconciliation complete!")
            print(f"✅ Database now has {final_count} visits")
            print(f"✅ Sheet has {len(sheet_visits)} unique visits")
            if final_count == len(sheet_visits):
                print(f"✅ Perfect match!")
        else:
            print("\n💡 This was a DRY RUN. Run with --live to apply changes.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        if not dry_run:
            db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    dry_run = "--live" not in sys.argv
    force = "--force" in sys.argv
    
    if not dry_run and not force:
        try:
            response = input("\n⚠️  WARNING: This will modify the database to match Google Sheet!\nAre you sure? Type 'yes' to continue: ")
            if response.lower() != 'yes':
                print("Aborted.")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("\n⚠️  Non-interactive mode detected. Use --force to skip confirmation.")
            sys.exit(1)
    
    reconcile_visits(dry_run=dry_run)

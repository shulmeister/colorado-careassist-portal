#!/usr/bin/env python3
"""
Comprehensive CSV import script for Sales Tracker
Imports visits, financial data, and dashboard statistics
"""

import csv
import os
import sys
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import sessionmaker
from database import db_manager
from models import Visit, TimeEntry, FinancialEntry, SalesBonus, Contact, ActivityNote
from dotenv import load_dotenv

load_dotenv()

def clean_currency(value):
    """Clean currency values and convert to float"""
    if not value or value == '' or value == '-':
        return 0.0
    # Remove $, commas, and convert to float
    cleaned = str(value).replace('$', '').replace(',', '').replace('(', '-').replace(')', '')
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def parse_date(date_str):
    """Parse various date formats"""
    if not date_str or date_str == '':
        return None
    
    # Handle different date formats
    formats = [
        '%m/%d/%Y',
        '%m/%d/%Y %H:%M:%S',
        '%Y-%m-%d',
        '%Y-%m-%d %H:%M:%S',
        '%m/%d/%Y %H:%M:%S',
        '%Y-%m-%d %H:%M:%S'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    
    print(f"Warning: Could not parse date: {date_str}")
    return None

def import_visits_csv(csv_file_path):
    """Import visits from CSV"""
    print(f"Importing visits from {csv_file_path}...")
    
    SessionLocal = sessionmaker(bind=db_manager.engine)
    db = SessionLocal()
    
    imported_count = 0
    skipped_count = 0
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            header = next(csv_reader)  # Skip header
            
            for row_num, row in enumerate(csv_reader, 2):
                if not row or len(row) < 6:
                    skipped_count += 1
                    continue
                
                try:
                    # Parse row data
                    stop = row[0] if len(row) > 0 else None
                    business_name = row[1] if len(row) > 1 and row[1] else None
                    location = row[2] if len(row) > 2 else None
                    city = row[3] if len(row) > 3 else None
                    notes = row[4] if len(row) > 4 else None
                    date_str = row[5] if len(row) > 5 else None
                    facility_type = row[6] if len(row) > 6 else None
                    follow_up = row[7] if len(row) > 7 else None
                    lead = row[8] if len(row) > 8 else None
                    client = row[9] if len(row) > 9 else None
                    
                    # Parse date
                    visit_date = parse_date(date_str)
                    if not visit_date:
                        skipped_count += 1
                        continue
                    
                    # Create visit record
                    visit = Visit(
                        business_name=business_name,
                        location=location,
                        city=city,
                        notes=notes,
                        visit_date=visit_date,
                        facility_type=facility_type,
                        follow_up_needed=follow_up,
                        is_lead=lead == 'Yes' if lead else False,
                        is_client=client == 'Yes' if client else False
                    )
                    
                    db.add(visit)
                    imported_count += 1
                    
                except Exception as e:
                    print(f"Error importing row {row_num}: {e}")
                    skipped_count += 1
                    continue
        
        db.commit()
        print(f"✅ Visits imported: {imported_count}, skipped: {skipped_count}")
        
    except Exception as e:
        print(f"❌ Error importing visits: {e}")
        db.rollback()
    finally:
        db.close()

def import_financial_csv(csv_file_path):
    """Import financial data from daily summary CSV"""
    print(f"Importing financial data from {csv_file_path}...")
    
    SessionLocal = sessionmaker(bind=db_manager.engine)
    db = SessionLocal()
    
    imported_count = 0
    skipped_count = 0
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            header = next(csv_reader)  # Skip header
            
            for row_num, row in enumerate(csv_reader, 2):
                if not row or len(row) < 7:
                    skipped_count += 1
                    continue
                
                try:
                    # Parse row data
                    date_str = row[0] if len(row) > 0 else None
                    hours_worked = clean_currency(row[1]) if len(row) > 1 else 0
                    hour_total = clean_currency(row[2]) if len(row) > 2 else 0
                    miles_driven = clean_currency(row[3]) if len(row) > 3 else 0
                    mileage_cost = clean_currency(row[4]) if len(row) > 4 else 0
                    gas_treats = clean_currency(row[5]) if len(row) > 5 else 0
                    total_cost = clean_currency(row[6]) if len(row) > 6 else 0
                    
                    # Parse date
                    entry_date = parse_date(date_str)
                    if not entry_date:
                        skipped_count += 1
                        continue
                    
                    # Create financial entry (costs only, no revenue)
                    financial_entry = FinancialEntry(
                        date=entry_date,
                        hours_worked=hours_worked,
                        hourly_rate=20.0,  # Default rate
                        miles_driven=miles_driven,
                        mileage_rate=0.7,  # Default rate
                        gas_treats_cost=gas_treats,
                        total_cost=total_cost,
                        revenue=0.0,  # No revenue - this is cost tracking only
                        description=f"Daily work costs - {hours_worked} hours, {miles_driven} miles"
                    )
                    
                    db.add(financial_entry)
                    imported_count += 1
                    
                except Exception as e:
                    print(f"Error importing financial row {row_num}: {e}")
                    skipped_count += 1
                    continue
        
        db.commit()
        print(f"✅ Financial entries imported: {imported_count}, skipped: {skipped_count}")
        
    except Exception as e:
        print(f"❌ Error importing financial data: {e}")
        db.rollback()
    finally:
        db.close()

def import_time_entries_from_financial(csv_file_path):
    """Import time entries from financial CSV"""
    print(f"Importing time entries from {csv_file_path}...")
    
    SessionLocal = sessionmaker(bind=db_manager.engine)
    db = SessionLocal()
    
    imported_count = 0
    skipped_count = 0
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            header = next(csv_reader)  # Skip header
            
            for row_num, row in enumerate(csv_reader, 2):
                if not row or len(row) < 3:
                    skipped_count += 1
                    continue
                
                try:
                    # Parse row data
                    date_str = row[0] if len(row) > 0 else None
                    hours_worked = clean_currency(row[1]) if len(row) > 1 else 0
                    
                    # Skip if no hours worked
                    if hours_worked <= 0:
                        skipped_count += 1
                        continue
                    
                    # Parse date
                    entry_date = parse_date(date_str)
                    if not entry_date:
                        skipped_count += 1
                        continue
                    
                    # Create time entry
                    time_entry = TimeEntry(
                        date=entry_date,
                        hours_worked=hours_worked,
                        hourly_rate=20.0,  # Default rate
                        description=f"Daily work - {hours_worked} hours"
                    )
                    
                    db.add(time_entry)
                    imported_count += 1
                    
                except Exception as e:
                    print(f"Error importing time row {row_num}: {e}")
                    skipped_count += 1
                    continue
        
        db.commit()
        print(f"✅ Time entries imported: {imported_count}, skipped: {skipped_count}")
        
    except Exception as e:
        print(f"❌ Error importing time entries: {e}")
        db.rollback()
    finally:
        db.close()

def import_sales_bonuses_csv(csv_file_path):
    """Import sales bonuses from closed sales CSV"""
    print(f"Importing sales bonuses from {csv_file_path}...")
    
    SessionLocal = sessionmaker(bind=db_manager.engine)
    db = SessionLocal()
    
    imported_count = 0
    skipped_count = 0
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            header = next(csv_reader)  # Skip header
            
            for row_num, row in enumerate(csv_reader, 2):
                if not row or len(row) < 5:
                    skipped_count += 1
                    continue
                
                try:
                    # Parse row data
                    client_name = row[0] if len(row) > 0 and row[0] else None
                    start_date_str = row[1] if len(row) > 1 else None
                    wellsky = row[2] if len(row) > 2 else None
                    status = row[3] if len(row) > 3 else None
                    commission_str = row[4] if len(row) > 4 else None
                    
                    # Skip empty rows or summary rows
                    if not client_name or client_name in ['', 'Commission', 'Actual Commission', 'Overpaid', 'Underpaid', 'Total Commission since July']:
                        skipped_count += 1
                        continue
                    
                    # Parse commission amount
                    commission_amount = clean_currency(commission_str) if commission_str else 0
                    
                    # Parse start date
                    start_date = None
                    if start_date_str and start_date_str not in ['', 'NA', 'Unknown']:
                        start_date = parse_date(start_date_str)
                    
                    # Create sales bonus entry
                    sales_bonus = SalesBonus(
                        client_name=client_name,
                        start_date=start_date,
                        commission_amount=commission_amount,
                        status=status,
                        wellsky_client=wellsky == 'Yes',
                        notes=f"Status: {status}, Wellsky: {wellsky}"
                    )
                    
                    db.add(sales_bonus)
                    imported_count += 1
                    
                except Exception as e:
                    print(f"Error importing sales bonus row {row_num}: {e}")
                    skipped_count += 1
                    continue
        
        db.commit()
        print(f"✅ Sales bonuses imported: {imported_count}, skipped: {skipped_count}")
        
    except Exception as e:
        print(f"❌ Error importing sales bonuses: {e}")
        db.rollback()
    finally:
        db.close()

def import_activity_notes_csv(csv_file_path):
    """Import activity notes from CSV"""
    print(f"Importing activity notes from {csv_file_path}...")
    
    SessionLocal = sessionmaker(bind=db_manager.engine)
    db = SessionLocal()
    
    imported_count = 0
    skipped_count = 0
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            header = next(csv_reader)  # Skip header
            
            for row_num, row in enumerate(csv_reader, 2):
                if not row or len(row) < 2:
                    skipped_count += 1
                    continue
                
                try:
                    # Parse row data
                    date_str = row[0] if len(row) > 0 else None
                    notes = row[1] if len(row) > 1 else None
                    
                    # Skip empty rows
                    if not date_str or not notes:
                        skipped_count += 1
                        continue
                    
                    # Parse date
                    entry_date = parse_date(date_str)
                    if not entry_date:
                        skipped_count += 1
                        continue
                    
                    # Create activity note
                    activity_note = ActivityNote(
                        date=entry_date,
                        notes=notes,
                        category="Daily Activity"
                    )
                    
                    db.add(activity_note)
                    imported_count += 1
                    
                except Exception as e:
                    print(f"Error importing activity note row {row_num}: {e}")
                    skipped_count += 1
                    continue
        
        db.commit()
        print(f"✅ Activity notes imported: {imported_count}, skipped: {skipped_count}")
        
    except Exception as e:
        print(f"❌ Error importing activity notes: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    """Main import function"""
    print("🚀 Starting comprehensive CSV import...")
    
    # File paths
    visits_file = "/Users/jasonshulman/Desktop/Sales Tracker - Visits.csv"
    financial_file = "/Users/jasonshulman/Desktop/Sales Tracker - Daily Summary.csv"
    sales_file = "/Users/jasonshulman/Desktop/Sales Tracker - Closed Sales.csv"
    activity_file = "/Users/jasonshulman/Desktop/Sales Tracker - Activity Notes.csv"
    
    # Check if files exist
    files_to_check = [
        (visits_file, "Visits"),
        (financial_file, "Financial"),
        (sales_file, "Sales Bonuses"),
        (activity_file, "Activity Notes")
    ]
    
    for file_path, file_type in files_to_check:
        if not os.path.exists(file_path):
            print(f"❌ {file_type} file not found: {file_path}")
            return
    
    try:
        # Import data in order
        import_visits_csv(visits_file)
        import_financial_csv(financial_file)
        import_time_entries_from_financial(financial_file)
        import_sales_bonuses_csv(sales_file)
        import_activity_notes_csv(activity_file)
        
        print("\n🎉 Import completed successfully!")
        print("\nNext steps:")
        print("1. Deploy this script to Heroku")
        print("2. Run it to populate your database")
        print("3. Refresh your dashboard to see the data")
        
    except Exception as e:
        print(f"❌ Import failed: {e}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""One-time script to populate notes from CSV column D"""
import csv
import io
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Lead

def decode_csv_content(csv_bytes):
    encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252', 'iso-8859-1']
    for encoding in encodings:
        try:
            return csv_bytes.decode(encoding)
        except:
            continue
    return csv_bytes.decode('utf-8', errors='replace')

if __name__ == "__main__":
    csv_path = "/Users/jasonshulman/Desktop/Caregiver Leads - COS CG candidates.csv"
    
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        sys.exit(1)
    
    with app.app_context():
        # Step 1: Clear all notes
        print("Step 1: Clearing all notes...")
        leads = Lead.query.all()
        for lead in leads:
            lead.notes = ''
        db.session.commit()
        print(f"✅ Cleared notes for {len(leads)} leads")
        
        # Step 2: Read CSV and update notes
        print("\nStep 2: Reading CSV and updating notes...")
        with open(csv_path, 'rb') as f:
            csv_bytes = f.read()
        
        csv_content = decode_csv_content(csv_bytes)
        sample = csv_content[:1024]
        delimiter = '\t' if '\t' in sample else ','
        
        reader = csv.DictReader(io.StringIO(csv_content), delimiter=delimiter)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        
        if len(fieldnames) < 4:
            print(f"❌ Error: CSV needs at least 4 columns, found {len(fieldnames)}")
            sys.exit(1)
        
        notes_col = fieldnames[3]  # Column D
        name_col = fieldnames[0]
        email_col = fieldnames[1] if len(fieldnames) > 1 else None
        phone_col = fieldnames[2] if len(fieldnames) > 2 else None
        
        print(f"Using columns - Name: {name_col}, Email: {email_col}, Phone: {phone_col}, Notes: {notes_col}")
        
        updated = 0
        not_found = 0
        skipped = 0
        
        for row in reader:
            name = row.get(name_col, '').strip()
            email = row.get(email_col, '').strip() if email_col else ''
            phone = row.get(phone_col, '').strip() if phone_col else ''
            notes = row.get(notes_col, '').strip()
            
            if not name and not email and not phone:
                continue
            
            if not notes:
                skipped += 1
                continue
            
            if phone.startswith('p:'):
                phone = phone[2:].strip()
            
            lead = None
            if email:
                lead = Lead.query.filter_by(email=email).first()
            if not lead and phone:
                lead = Lead.query.filter_by(phone=phone).first()
            if not lead and name:
                lead = Lead.query.filter(db.func.lower(Lead.name) == name.lower()).first()
            
            if lead:
                lead.notes = notes
                updated += 1
                if updated % 20 == 0:
                    print(f"  Updated {updated} leads...")
            else:
                not_found += 1
        
        db.session.commit()
        print(f"\n✅ Complete!")
        print(f"   Updated: {updated} leads")
        print(f"   Not found: {not_found} leads")
        print(f"   Skipped (no notes): {skipped} rows")



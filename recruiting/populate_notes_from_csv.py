import os
import sys
import csv
import io

# Add the current directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Lead

def decode_csv_content(csv_bytes):
    """Try to decode CSV content with different encodings"""
    encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            return csv_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    
    # If all encodings fail, try with error handling
    try:
        return csv_bytes.decode('utf-8', errors='replace')
    except:
        return csv_bytes.decode('latin-1', errors='replace')

def process_csv_for_notes(csv_file_path):
    """Process CSV file and update notes from column D"""
    with app.app_context():
        # Step 1: Clear all notes
        print("Step 1: Clearing all notes...")
        leads = Lead.query.all()
        cleared_count = 0
        for lead in leads:
            lead.notes = ''
            cleared_count += 1
        db.session.commit()
        print(f"✅ Cleared notes for {cleared_count} leads")
        
        # Step 2: Read CSV and update notes
        print("\nStep 2: Reading CSV and updating notes...")
        with open(csv_file_path, 'rb') as f:
            csv_bytes = f.read()
        
        csv_content = decode_csv_content(csv_bytes)
        
        # Try to detect delimiter
        sample = csv_content[:1024]
        delimiter = '\t' if '\t' in sample else ','
        
        reader = csv.DictReader(io.StringIO(csv_content), delimiter=delimiter)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        
        print(f"CSV Columns found: {fieldnames[:10]}...")
        
        # Column D is the 4th column (index 3)
        if len(fieldnames) < 4:
            print(f"❌ Error: CSV doesn't have at least 4 columns. Found: {len(fieldnames)}")
            return
        
        notes_column = fieldnames[3]
        print(f"Using notes column (D): {notes_column}")
        
        # Find name/email/phone columns
        name_col = fieldnames[0] if len(fieldnames) >= 1 else None
        email_col = fieldnames[1] if len(fieldnames) >= 2 else None
        phone_col = fieldnames[2] if len(fieldnames) >= 3 else None
        
        # Try to find by name if headers exist
        for col in fieldnames:
            col_lower = col.lower().strip()
            if 'email' in col_lower and not email_col:
                email_col = col
            elif 'phone' in col_lower and not phone_col:
                phone_col = col
        
        # If no email/phone found by name, use positions
        if not email_col and len(fieldnames) >= 2:
            email_col = fieldnames[1]
        if not phone_col and len(fieldnames) >= 3:
            phone_col = fieldnames[2]
        
        print(f"Using columns - Name: {name_col}, Email: {email_col}, Phone: {phone_col}, Notes: {notes_column}")
        
        updated_count = 0
        not_found_count = 0
        skipped_no_notes = 0
        
        for row in reader:
            # Skip empty rows
            name = row.get(name_col, '').strip() if name_col else ''
            email = row.get(email_col, '').strip() if email_col else ''
            phone = row.get(phone_col, '').strip() if phone_col else ''
            
            # Skip if no identifying information
            if not name and not email and not phone:
                continue
            
            notes = row.get(notes_column, '').strip()
            
            # Skip if no notes (leave blank in database)
            if not notes:
                skipped_no_notes += 1
                continue
            
            # Clean phone number (remove p: prefix if present)
            if phone and phone.startswith('p:'):
                phone = phone[2:].strip()
            
            # Find matching lead
            lead = None
            
            # First try by email (most reliable)
            if email:
                lead = Lead.query.filter_by(email=email).first()
            
            # Then try by phone
            if not lead and phone:
                lead = Lead.query.filter_by(phone=phone).first()
            
            # Finally try by name (case-insensitive)
            if not lead and name:
                lead = Lead.query.filter(
                    db.func.lower(Lead.name) == name.lower()
                ).first()
            
            if lead:
                lead.notes = notes
                updated_count += 1
                if updated_count % 10 == 0:
                    print(f"  Updated {updated_count} leads...")
            else:
                not_found_count += 1
                if not_found_count <= 10:  # Only print first 10 not found
                    print(f"  ⚠️  Not found: {name or email or phone}")
        
        db.session.commit()
        
        print(f"\n✅ Notes update complete!")
        print(f"   - Updated: {updated_count} leads")
        print(f"   - Not found: {not_found_count} leads")
        print(f"   - Skipped (no notes): {skipped_no_notes} rows")

if __name__ == "__main__":
    csv_path = "/Users/jasonshulman/Desktop/Caregiver Leads - COS CG candidates.csv"
    if not os.path.exists(csv_path):
        print(f"❌ Error: CSV file not found at {csv_path}")
        sys.exit(1)
    
    process_csv_for_notes(csv_path)


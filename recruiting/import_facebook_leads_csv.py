#!/usr/bin/env python3
"""Import Facebook leads from CSV file"""
from app import app, db, Lead
import csv
import sys
from datetime import datetime

def clean_phone(phone):
    """Clean phone number format"""
    if not phone:
        return None

    phone = str(phone).strip()
    phone = phone.replace('(', '').replace(')', '').replace('-', '').replace(' ', '')

    # Add +1 if it doesn't start with +
    if phone and not phone.startswith('+'):
        if len(phone) == 10:
            phone = '+1' + phone
        elif len(phone) == 11 and phone.startswith('1'):
            phone = '+' + phone

    return phone if phone else None

def parse_date(date_str):
    """Parse date from CSV format: 11/24/2025 4:53am"""
    if not date_str:
        return datetime.now()

    try:
        # Try parsing the CSV format
        return datetime.strptime(date_str, '%m/%d/%Y %I:%M%p')
    except:
        try:
            # Try alternate format
            return datetime.strptime(date_str, '%m/%d/%Y %H:%M')
        except:
            return datetime.now()

def import_csv_leads(csv_file_path):
    """Import leads from CSV file"""
    with app.app_context():
        added = 0
        skipped = 0
        errors = 0

        with open(csv_file_path, 'r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                try:
                    name = row.get('Name', '').strip()
                    email = row.get('Email', '').strip()
                    phone = clean_phone(row.get('Phone', ''))
                    created_date = parse_date(row.get('Created', ''))
                    source = row.get('Source', 'Facebook')
                    stage = row.get('Stage', 'Intake')

                    if not name or not phone:
                        print(f"Skipping lead with missing name or phone: {name or email}")
                        skipped += 1
                        continue

                    # Check if lead already exists by phone
                    existing = Lead.query.filter_by(phone=phone).first()
                    if existing:
                        print(f"Skipping duplicate lead: {name} ({phone})")
                        skipped += 1
                        continue

                    # Create new lead
                    lead = Lead(
                        name=name,
                        email=email if email else 'noemail@example.com',
                        phone=phone,
                        source='facebook_ads',
                        facebook_lead_id=None,
                        status='new',
                        priority='medium',
                        notes=f"Stage: {stage}. Imported from CSV on {datetime.now().strftime('%Y-%m-%d')}"
                    )

                    db.session.add(lead)
                    added += 1

                    if added <= 10:
                        print(f"Added: {name} ({phone}) - {email}")

                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        print(f"Error processing row: {e}")
                        print(f"Row data: {row}")

        db.session.commit()
        print(f"\n=== IMPORT COMPLETE ===")
        print(f"✓ Added: {added} leads")
        print(f"⊘ Skipped: {skipped} duplicates")
        print(f"✗ Errors: {errors}")
        return added

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_facebook_leads_csv.py <csv_file_path>")
        sys.exit(1)

    csv_file = sys.argv[1]
    imported = import_csv_leads(csv_file)
    print(f"\nTotal imported: {imported}")

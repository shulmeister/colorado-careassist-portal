#!/usr/bin/env python3
"""
Import Wealth Leads from CSV
"""

import sys
import os
import csv
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from ~/.gigi-env
env_file = Path.home() / '.gigi-env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                if line.startswith('export '):
                    line = line[7:]
                key, value = line.split('=', 1)
                value = value.strip('"').strip("'")
                os.environ[key] = value

from database import db_manager
from models import Contact, ReferralSource

def import_wealth_leads(csv_path: str, dry_run=False):
    """Import wealth leads from CSV."""

    print("=" * 70)
    print("IMPORT WEALTH LEADS")
    print("=" * 70)
    print(f"\nTime: {datetime.now().isoformat()}")
    print(f"CSV: {csv_path}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

    with db_manager.SessionLocal() as db:
        added_contacts = 0
        updated_contacts = 0
        added_companies = 0
        skipped = 0

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                first_name = row.get('Firstname', '').strip()
                last_name = row.get('Lastname', '').strip()
                email = row.get('Email', '').strip()
                firm = row.get('Firm', '').strip()
                county = row.get('County', '').strip()
                coi_type = row.get('COI_TYPE', '').strip()
                specialization = row.get('Key_Specialization', '').strip()
                address = row.get('Office_Address', '').strip()

                if not first_name or not last_name or not email:
                    print(f"⚠️  Skipping incomplete row: {first_name} {last_name}")
                    skipped += 1
                    continue

                # Find or create company
                company_id = None
                if firm:
                    existing_company = db.query(ReferralSource).filter(
                        ReferralSource.name.ilike(f"%{firm}%")
                    ).first()

                    if existing_company:
                        company_id = existing_company.id
                    else:
                        if not dry_run:
                            new_company = ReferralSource(
                                name=firm,
                                organization=firm,
                                address=address,
                                location=county,
                                source_type='Professional Services',
                                status='prospect',
                                notes=f"{coi_type} - {specialization}".strip(' -'),
                                created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow()
                            )
                            db.add(new_company)
                            db.flush()
                            company_id = new_company.id
                            added_companies += 1
                            print(f"  + Company: {firm} ({county})")

                # Find or create contact
                existing_contact = db.query(Contact).filter(
                    Contact.email == email
                ).first()

                if existing_contact:
                    # Update existing
                    if not dry_run:
                        existing_contact.first_name = first_name
                        existing_contact.last_name = last_name
                        existing_contact.name = f"{first_name} {last_name}"
                        existing_contact.company = firm
                        existing_contact.company_id = company_id
                        existing_contact.title = coi_type
                        existing_contact.address = address
                        existing_contact.notes = f"{specialization}\nCounty: {county}"
                        existing_contact.updated_at = datetime.utcnow()
                        existing_contact.last_activity = datetime.utcnow()
                        db.add(existing_contact)
                    updated_contacts += 1
                    print(f"✓ Updated: {first_name} {last_name} - {firm}")
                else:
                    # Create new
                    if not dry_run:
                        new_contact = Contact(
                            first_name=first_name,
                            last_name=last_name,
                            name=f"{first_name} {last_name}",
                            email=email,
                            company=firm,
                            company_id=company_id,
                            title=coi_type,
                            address=address,
                            notes=f"{specialization}\nCounty: {county}",
                            status='cold',
                            source='Wealth Leads CSV Import',
                            account_manager='jacob@coloradocareassist.com',
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                            last_activity=datetime.utcnow()
                        )
                        db.add(new_contact)
                    added_contacts += 1
                    print(f"+ Added: {first_name} {last_name} - {firm}")

        if not dry_run:
            db.commit()
            print(f"\n✅ Committed changes to database")

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"New contacts added: {added_contacts}")
        print(f"Existing contacts updated: {updated_contacts}")
        print(f"New companies added: {added_companies}")
        print(f"Skipped (incomplete): {skipped}")
        print("=" * 70)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Import wealth leads from CSV')
    parser.add_argument('--csv', type=str, required=True, help='Path to CSV file')
    parser.add_argument('--dry-run', action='store_true', help='Preview without modifying database')
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"ERROR: CSV file not found: {args.csv}")
        sys.exit(1)

    import_wealth_leads(args.csv, dry_run=args.dry_run)

#!/usr/bin/env python3
"""
Import Companies from Maryssa's Sales Tracker (Visits CSV)
"""

import sys
import os
import csv
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db_manager
from models import ReferralSource


def normalize_company_name(name: str) -> str:
    """Normalize company name for comparison."""
    if not name:
        return ""
    return name.strip().lower()


def import_from_csv(csv_path: str, dry_run=False):
    """Import companies from CSV file."""

    print("=" * 70)
    print("IMPORT COMPANIES FROM VISITS CSV")
    print("=" * 70)
    print(f"\nTime: {datetime.now().isoformat()}")
    print(f"CSV: {csv_path}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

    # Read CSV file
    companies_from_csv = set()

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            business_name = row.get('Business Name', '').strip()
            if business_name and len(business_name) > 2:
                companies_from_csv.add(business_name)

    print(f"Unique companies in CSV: {len(companies_from_csv)}\n")

    # Connect to database
    with db_manager.SessionLocal() as db:
        # Get existing companies
        existing = db.query(ReferralSource).all()
        existing_names = {normalize_company_name(c.name): c for c in existing}

        print(f"Existing companies in database: {len(existing_names)}\n")

        added = 0
        skipped = 0

        for company_name in sorted(companies_from_csv):
            normalized = normalize_company_name(company_name)

            if normalized in existing_names:
                skipped += 1
                continue

            print(f"+ {company_name}")

            if not dry_run:
                new_company = ReferralSource(
                    name=company_name,
                    source_type='referral',
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(new_company)
                added += 1

        if not dry_run and added > 0:
            db.commit()
            print(f"\n✅ Committed {added} new companies to database")

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Companies in CSV: {len(companies_from_csv)}")
        print(f"Already in database: {skipped}")
        print(f"New companies added: {added}")
        print(f"Final total: {len(existing_names) + added}")
        print("=" * 70)


if __name__ == '__main__':
    import argparse
    import glob

    parser = argparse.ArgumentParser(description='Import companies from Visits CSV')
    parser.add_argument('--csv', type=str, help='Path to CSV file')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without modifying database')
    args = parser.parse_args()

    # Find CSV file
    csv_path = args.csv
    if not csv_path:
        # Try to find it on Desktop
        pattern = str(Path.home() / 'Desktop' / '*Visits*.csv')
        matches = glob.glob(pattern)
        if matches:
            csv_path = matches[0]
            print(f"Found CSV: {csv_path}\n")
        else:
            print("ERROR: No CSV file specified and none found on Desktop")
            print("Usage: python import_from_visits_csv.py --csv <path>")
            sys.exit(1)

    if not os.path.exists(csv_path):
        print(f"ERROR: CSV file not found: {csv_path}")
        sys.exit(1)

    import_from_csv(csv_path, dry_run=args.dry_run)

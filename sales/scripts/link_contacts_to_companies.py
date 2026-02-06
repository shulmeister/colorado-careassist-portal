#!/usr/bin/env python3
"""
Auto-link Contacts to Companies

Finds contacts with company names but no company_id, then links them
to matching companies in referral_sources table.
"""

import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
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
from sqlalchemy import func


def link_contacts_to_companies(dry_run=False):
    """Auto-link contacts to companies based on company name."""

    print("=" * 70)
    print("AUTO-LINK CONTACTS TO COMPANIES")
    print("=" * 70)
    print(f"\nTime: {datetime.now().isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

    with db_manager.SessionLocal() as db:
        # Get contacts with company name but no company_id
        unlinked = db.query(Contact).filter(
            Contact.company.isnot(None),
            Contact.company != '',
            Contact.company_id.is_(None)
        ).all()

        print(f"Found {len(unlinked)} contacts with company name but no link\n")

        # Get all companies for matching
        all_companies = db.query(ReferralSource).all()
        company_map = {}

        # Create normalized name map
        for company in all_companies:
            if company.name:
                normalized = company.name.strip().lower()
                company_map[normalized] = company

        linked = 0
        no_match = 0
        already_linked = 0

        for contact in unlinked:
            company_name = contact.company.strip()
            normalized = company_name.lower()

            # Try exact match first
            if normalized in company_map:
                company = company_map[normalized]
                print(f"✓ {contact.name or contact.email} → {company.name}")

                if not dry_run:
                    contact.company_id = company.id
                    contact.updated_at = datetime.utcnow()
                    db.add(contact)

                linked += 1
            else:
                # Try partial match (company name contains or is contained in)
                matched = False
                for comp_name, company in company_map.items():
                    # Check if one contains the other
                    if (len(normalized) > 5 and normalized in comp_name) or \
                       (len(comp_name) > 5 and comp_name in normalized):
                        print(f"≈ {contact.name or contact.email} → {company.name} (partial match)")

                        if not dry_run:
                            contact.company_id = company.id
                            contact.updated_at = datetime.utcnow()
                            db.add(contact)

                        linked += 1
                        matched = True
                        break

                if not matched:
                    print(f"✗ {contact.name or contact.email} - No match for '{company_name}'")
                    no_match += 1

        if not dry_run and linked > 0:
            db.commit()
            print(f"\n✅ Committed {linked} contact-company links")

        # Get updated stats
        total_contacts = db.query(Contact).count()
        linked_contacts = db.query(Contact).filter(
            Contact.company_id.isnot(None)
        ).count()

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total contacts: {total_contacts}")
        print(f"Contacts linked to companies: {linked_contacts} ({linked_contacts*100//total_contacts}%)")
        print(f"New links created: {linked}")
        print(f"No matching company found: {no_match}")
        print("=" * 70)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Auto-link contacts to companies')
    parser.add_argument('--dry-run', action='store_true', help='Preview without modifying database')
    args = parser.parse_args()

    link_contacts_to_companies(dry_run=args.dry_run)

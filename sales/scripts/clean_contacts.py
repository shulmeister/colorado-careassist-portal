#!/usr/bin/env python3
"""
CRM Data Cleanup Script
- Remove duplicate contacts
- Fill in missing names from 'name' field
- Link contacts to companies by email domain
- Sync contacts to Brevo
"""

import os
import sys
import re
import logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models import Contact, ReferralSource
from sqlalchemy import func
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BREVO_API_KEY = os.getenv("BREVO_API_KEY")


def remove_duplicates(db):
    """Remove duplicate contacts, keeping the one with most data"""
    print("\n=== REMOVING DUPLICATES ===")

    # Find duplicate emails
    dupes = db.query(Contact.email, func.count(Contact.id)).filter(
        Contact.email != None, Contact.email != ''
    ).group_by(Contact.email).having(func.count(Contact.id) > 1).all()

    removed = 0
    for email, count in dupes:
        contacts = db.query(Contact).filter(Contact.email == email).order_by(Contact.id).all()

        # Score each contact by data completeness
        def score(c):
            s = 0
            if c.first_name: s += 1
            if c.last_name: s += 1
            if c.phone: s += 1
            if c.company_id: s += 2  # Company link is valuable
            if c.title: s += 1
            return s

        # Sort by score descending, keep the best one
        contacts.sort(key=score, reverse=True)
        keeper = contacts[0]

        for c in contacts[1:]:
            print(f"  Removing duplicate: {c.email} (ID {c.id}, keeping ID {keeper.id})")
            db.delete(c)
            removed += 1

    db.commit()
    print(f"Removed {removed} duplicate contacts")
    return removed


def fill_missing_names(db):
    """Fill in first/last names from 'name' field if available"""
    print("\n=== FILLING MISSING NAMES ===")

    # Get contacts with missing first or last name but have full name
    contacts = db.query(Contact).filter(
        (Contact.name != None) & (Contact.name != ''),
        ((Contact.first_name == None) | (Contact.first_name == '') |
         (Contact.last_name == None) | (Contact.last_name == ''))
    ).all()

    updated = 0
    for c in contacts:
        if not c.name:
            continue

        # Parse name
        parts = c.name.strip().split()
        if len(parts) >= 2:
            first = parts[0]
            last = ' '.join(parts[1:])
        elif len(parts) == 1:
            first = parts[0]
            last = ''
        else:
            continue

        changed = False
        if not c.first_name and first:
            c.first_name = first
            changed = True
        if not c.last_name and last:
            c.last_name = last
            changed = True

        if changed:
            print(f"  Updated: {c.email} -> {c.first_name} {c.last_name}")
            updated += 1

    db.commit()
    print(f"Updated {updated} contact names")
    return updated


def link_contacts_to_companies(db):
    """Link contacts to companies based on email domain"""
    print("\n=== LINKING CONTACTS TO COMPANIES ===")

    # Get contacts without company but with email
    orphans = db.query(Contact).filter(
        Contact.company_id == None,
        Contact.email != None,
        Contact.email != ''
    ).all()

    # Build domain -> company map from existing data
    domain_map = {}
    linked_contacts = db.query(Contact).filter(
        Contact.company_id != None,
        Contact.email != None
    ).all()

    for c in linked_contacts:
        if '@' in c.email:
            domain = c.email.split('@')[1].lower()
            # Skip common personal email domains
            if domain not in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
                             'icloud.com', 'aol.com', 'comcast.net', 'msn.com']:
                if domain not in domain_map:
                    domain_map[domain] = c.company_id

    print(f"  Built domain map with {len(domain_map)} corporate domains")

    # Also try to match by company name in email domain
    companies = db.query(ReferralSource).all()
    for company in companies:
        if company.name:
            # Create domain-like pattern from company name
            name_pattern = company.name.lower().replace(' ', '').replace(',', '').replace('.', '')
            name_pattern = re.sub(r'[^a-z0-9]', '', name_pattern)
            if len(name_pattern) > 3:
                domain_map[name_pattern] = company.id

    linked = 0
    for c in orphans:
        if '@' not in c.email:
            continue

        domain = c.email.split('@')[1].lower()

        # Direct domain match
        if domain in domain_map:
            c.company_id = domain_map[domain]
            print(f"  Linked: {c.email} -> company ID {c.company_id}")
            linked += 1
            continue

        # Try partial match on domain name
        domain_name = domain.split('.')[0]
        for pattern, company_id in domain_map.items():
            if domain_name in pattern or pattern in domain_name:
                c.company_id = company_id
                print(f"  Linked (fuzzy): {c.email} -> company ID {c.company_id}")
                linked += 1
                break

    db.commit()
    print(f"Linked {linked} contacts to companies")
    return linked


def sync_to_brevo(db):
    """Sync all contacts with email to Brevo"""
    print("\n=== SYNCING TO BREVO ===")

    if not BREVO_API_KEY:
        print("  No Brevo API key configured")
        return 0

    # Get all contacts with email
    contacts = db.query(Contact).filter(
        Contact.email != None,
        Contact.email != ''
    ).all()

    synced = 0
    errors = 0

    for c in contacts:
        # Skip invalid emails
        if not c.email or '@' not in c.email:
            continue

        # Get company name if linked
        company_name = ""
        if c.company_id:
            company = db.query(ReferralSource).filter(ReferralSource.id == c.company_id).first()
            if company:
                company_name = company.name or ""

        # Prepare Brevo contact data
        payload = {
            "email": c.email.lower().strip(),
            "attributes": {
                "FIRSTNAME": c.first_name or "",
                "LASTNAME": c.last_name or "",
                "COMPANY": company_name,
                "SMS": c.phone or ""
            },
            "updateEnabled": True
        }

        try:
            resp = requests.post(
                "https://api.brevo.com/v3/contacts",
                headers={
                    "api-key": BREVO_API_KEY,
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=10
            )

            if resp.status_code in [200, 201, 204]:
                synced += 1
            elif resp.status_code == 400 and "duplicate" in resp.text.lower():
                # Already exists, try update
                synced += 1
            else:
                if errors < 5:  # Only log first 5 errors
                    print(f"  Error syncing {c.email}: {resp.status_code} - {resp.text[:100]}")
                errors += 1

        except Exception as e:
            if errors < 5:
                print(f"  Error syncing {c.email}: {e}")
            errors += 1

    print(f"Synced {synced} contacts to Brevo ({errors} errors)")
    return synced


def main():
    print("=" * 60)
    print("CRM DATA CLEANUP")
    print("=" * 60)

    db = next(get_db())

    # Step 1: Remove duplicates
    removed = remove_duplicates(db)

    # Step 2: Fill missing names
    names_fixed = fill_missing_names(db)

    # Step 3: Link contacts to companies
    linked = link_contacts_to_companies(db)

    # Step 4: Sync to Brevo
    synced = sync_to_brevo(db)

    # Final summary
    print("\n" + "=" * 60)
    print("CLEANUP SUMMARY")
    print("=" * 60)
    print(f"Duplicates removed: {removed}")
    print(f"Names filled in: {names_fixed}")
    print(f"Contacts linked to companies: {linked}")
    print(f"Contacts synced to Brevo: {synced}")

    # Re-audit
    print("\n--- POST-CLEANUP STATS ---")
    total = db.query(Contact).count()
    missing_company = db.query(Contact).filter(Contact.company_id == None).count()
    missing_email = db.query(Contact).filter(
        (Contact.email == None) | (Contact.email == '')
    ).count()

    print(f"Total contacts: {total}")
    print(f"Still missing company: {missing_company}")
    print(f"Still missing email: {missing_email}")

    db.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Enrich Company Data from Email Domains

For contacts with email but no company:
1. Extract domain from email
2. Use Gemini AI to identify the company
3. Link to existing company or create new one
"""

import sys
import os
import re
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
import google.generativeai as genai

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Skip these generic domains
SKIP_DOMAINS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
    'icloud.com', 'me.com', 'mac.com', 'msn.com', 'live.com',
    'comcast.net', 'att.net', 'verizon.net', 'cox.net', 'earthlink.net'
}


def extract_domain(email):
    """Extract domain from email address."""
    if not email or '@' not in email:
        return None
    domain = email.split('@')[1].lower().strip()
    return domain if domain not in SKIP_DOMAINS else None


def identify_company_from_domain(domain):
    """Use Gemini AI to identify company from email domain."""
    if not GEMINI_API_KEY:
        return None

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')

    prompt = f"""What is the company name for the email domain "{domain}"?

This is likely a:
- Healthcare facility (hospital, nursing home, assisted living)
- Medical practice or clinic
- Home health agency
- Senior care organization
- Professional services firm (law, accounting, financial)
- Corporate business

Return ONLY the official company name, nothing else. If you cannot identify a specific company, return "UNKNOWN".

Examples:
- "uchealth.org" → "UCHealth"
- "sclhealth.org" → "SCL Health"
- "davita.com" → "DaVita"
- "commonspirit.org" → "CommonSpirit Health"
- "hollandhart.com" → "Holland & Hart"
"""

    try:
        response = model.generate_content(prompt)
        company_name = response.text.strip()

        if company_name and company_name.upper() != "UNKNOWN":
            return company_name
    except Exception as e:
        print(f"  Error querying Gemini for {domain}: {e}")

    return None


def enrich_companies(dry_run=False, limit=None):
    """Enrich contacts with company data from email domains."""

    print("=" * 70)
    print("ENRICH COMPANIES FROM EMAIL DOMAINS")
    print("=" * 70)
    print(f"\nTime: {datetime.now().isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    if limit:
        print(f"Limit: {limit} contacts")
    print()

    with db_manager.SessionLocal() as db:
        # Get contacts with email but no company (NULL or empty string)
        query = db.query(Contact).filter(
            Contact.email.isnot(None),
            Contact.email != ''
        ).filter(
            (Contact.company.is_(None)) | (Contact.company == '')
        )

        if limit:
            contacts = query.limit(limit).all()
        else:
            contacts = query.all()

        print(f"Found {len(contacts)} contacts with email but no company\n")

        # Get all existing companies for matching
        all_companies = db.query(ReferralSource).all()
        company_map = {c.name.strip().lower(): c for c in all_companies if c.name}

        enriched = 0
        skipped = 0
        created_companies = 0

        for i, contact in enumerate(contacts, 1):
            email = contact.email.strip().lower()
            domain = extract_domain(email)

            if not domain:
                print(f"[{i}/{len(contacts)}] ⊘ {email} - Generic domain, skipping")
                skipped += 1
                continue

            print(f"[{i}/{len(contacts)}] Processing {email} ({domain})...")

            # Try to identify company from domain
            company_name = identify_company_from_domain(domain)

            if not company_name:
                print(f"  ⚠️  Could not identify company from domain")
                skipped += 1
                continue

            print(f"  ✓ Found: {company_name}")

            # Check if company exists
            normalized = company_name.strip().lower()
            company_id = None

            if normalized in company_map:
                company = company_map[normalized]
                company_id = company.id
                print(f"  → Linking to existing company (ID: {company_id})")
            else:
                # Create new company
                if not dry_run:
                    new_company = ReferralSource(
                        name=company_name,
                        organization=company_name,
                        source_type='Healthcare Facility',
                        status='prospect',
                        notes=f"Auto-discovered from email domain: {domain}",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(new_company)
                    db.flush()
                    company_id = new_company.id
                    company_map[normalized] = new_company
                    created_companies += 1
                    print(f"  + Created new company (ID: {company_id})")

            # Update contact
            if not dry_run and company_id:
                contact.company = company_name
                contact.company_id = company_id
                contact.updated_at = datetime.utcnow()
                db.add(contact)

            enriched += 1

        if not dry_run and enriched > 0:
            db.commit()
            print(f"\n✅ Committed {enriched} enriched contacts")

        # Get updated stats
        total_contacts = db.query(Contact).count()
        has_company = db.query(Contact).filter(
            Contact.company.isnot(None),
            Contact.company != ''
        ).count()
        linked = db.query(Contact).filter(
            Contact.company_id.isnot(None)
        ).count()

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Contacts processed: {len(contacts)}")
        print(f"Successfully enriched: {enriched}")
        print(f"New companies created: {created_companies}")
        print(f"Skipped (generic email/unknown): {skipped}")
        print(f"\nDatabase totals:")
        print(f"  Total contacts: {total_contacts}")
        print(f"  With company name: {has_company} ({has_company*100//total_contacts}%)")
        print(f"  Linked to company: {linked} ({linked*100//total_contacts}%)")
        print("=" * 70)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Enrich company data from email domains')
    parser.add_argument('--dry-run', action='store_true', help='Preview without modifying database')
    parser.add_argument('--limit', type=int, help='Limit number of contacts to process')
    args = parser.parse_args()

    enrich_companies(dry_run=args.dry_run, limit=args.limit)

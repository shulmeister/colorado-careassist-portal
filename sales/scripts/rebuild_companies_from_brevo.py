#!/usr/bin/env python3
"""
Rebuild Companies from Brevo

Fetches all companies from Brevo (2184+), filters out personal emails and non-companies,
then imports clean company data into referral_sources table.

Usage:
    python scripts/rebuild_companies_from_brevo.py [--dry-run]
"""

import sys
import os
import re
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db_manager
from models import ReferralSource
from brevo_service import BrevoService


def is_valid_company_name(name: str) -> bool:
    """
    Check if a company name looks like a real company (not a person or personal email).

    Returns True if it's likely a real company, False if it's likely a person or junk.
    """
    if not name or not name.strip():
        return False

    name = name.strip()
    name_lower = name.lower()

    # Filter out obvious email addresses as company names
    if '@' in name:
        return False

    # Filter out names that are just numbers or very short
    if len(name) < 3:
        return False

    # Filter out names that look like email usernames (e.g., "john.doe", "user123")
    if re.match(r'^[a-z]+\.[a-z]+$', name_lower):  # john.doe
        return False
    if re.match(r'^[a-z]+\d+$', name_lower):  # user123
        return False

    # Company indicators (positive signals)
    company_indicators = [
        'hospital', 'hospice', 'health', 'care', 'center', 'clinic',
        'medical', 'nursing', 'living', 'senior', 'home', 'services',
        'llc', 'inc', 'corp', 'corporation', 'company', 'co.', 'ltd',
        'facility', 'rehab', 'therapy', 'pharmacy', 'group', 'associates',
        'partners', 'foundation', 'institute', 'agency', 'ministries',
        'church', 'school', 'university', 'college', 'district',
        'department', 'office', 'center', 'society', 'association',
        'community', 'network', 'systems', 'solutions', 'technologies',
        'consulting', 'advisors', 'management', 'enterprises'
    ]

    for indicator in company_indicators:
        if indicator in name_lower:
            return True

    # Person name patterns (negative signals)
    # Check if it looks like "FirstName LastName" (2 capitalized words, no company words)
    words = name.split()
    if len(words) == 2:
        # Both words are capitalized, short, and no numbers
        if all(w[0].isupper() and len(w) < 15 and not any(c.isdigit() for c in w) for w in words):
            # Could be a person name - reject unless it has company indicators
            return False

    # If 1 word and short, likely not a company (unless has company indicator above)
    if len(words) == 1 and len(name) < 10:
        return False

    # Filter out common first names as company names
    common_first_names = [
        'john', 'james', 'robert', 'michael', 'william', 'david', 'richard',
        'joseph', 'thomas', 'charles', 'mary', 'patricia', 'jennifer',
        'linda', 'barbara', 'elizabeth', 'susan', 'jessica', 'sarah',
        'karen', 'nancy', 'lisa', 'betty', 'margaret', 'sandra', 'ashley'
    ]
    if name_lower in common_first_names:
        return False

    # If it passes all filters and doesn't match person patterns, accept it
    return True


def normalize_company_name(name: str) -> str:
    """Normalize company name for deduplication."""
    if not name:
        return ""
    name = name.strip()
    # Remove common suffixes for matching
    for suffix in [' LLC', ' Inc', ' Corp', ' Corporation', ' Co', ' Company',
                   ', LLC', ', Inc.', ', Corp.', ' - Colorado', ' of Colorado']:
        name = re.sub(re.escape(suffix) + r'$', '', name, flags=re.IGNORECASE)
    return name.strip()


def fetch_all_brevo_companies() -> List[Dict[str, Any]]:
    """
    Fetch all CRM companies from Brevo (paginated).
    """
    brevo = BrevoService()
    if not brevo.enabled:
        print("ERROR: Brevo API not configured. Set BREVO_API_KEY.")
        return []

    print("\n📡 Fetching CRM companies from Brevo...")

    import requests
    all_companies = []
    page = 1
    page_size = 50

    while True:
        try:
            response = requests.get(
                f"{brevo.base_url}/companies",
                headers=brevo._get_headers(),
                params={"limit": page_size, "page": page}
            )

            if response.status_code != 200:
                print(f"ERROR: Brevo API returned {response.status_code}")
                break

            data = response.json()
            companies = data.get('items', [])

            if not companies:
                break

            all_companies.extend(companies)

            # Check pagination info
            pager = data.get('pager', {})
            total = pager.get('total', 0)
            max_page = pager.get('max', 1)

            print(f"  Page {page}/{max_page}: {len(companies)} companies (total: {len(all_companies)}/{total})")

            # Stop if we've fetched all pages
            if page >= max_page:
                break

            page += 1

        except Exception as e:
            print(f"ERROR fetching companies: {e}")
            import traceback
            traceback.print_exc()
            break

    print(f"\n✅ Fetched {len(all_companies)} total CRM companies from Brevo")
    return all_companies


def rebuild_companies(dry_run: bool = False):
    """
    Main function to rebuild companies from Brevo.
    """
    print("=" * 70)
    print("REBUILD COMPANIES FROM BREVO")
    print("=" * 70)
    print(f"\nTime: {datetime.now().isoformat()}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will modify database)'}")
    print()

    # Fetch all companies from Brevo
    brevo_companies = fetch_all_brevo_companies()
    if not brevo_companies:
        print("\n❌ No companies fetched. Exiting.")
        return

    # Filter companies
    print("\n🔍 Filtering companies...")
    valid_companies = []
    filtered_out = []

    for company in brevo_companies:
        # Extract name from attributes (Brevo CRM structure)
        attrs = company.get('attributes', {})
        name = attrs.get('name', '').strip()

        if is_valid_company_name(name):
            valid_companies.append(company)
        else:
            filtered_out.append(name if name else "(empty name)")

    print(f"\n✅ Valid companies: {len(valid_companies)}")
    print(f"❌ Filtered out: {len(filtered_out)}")

    # Show sample of filtered out names
    if filtered_out:
        print("\nSample of filtered names (personal/junk):")
        for name in filtered_out[:20]:
            print(f"  - {name}")
        if len(filtered_out) > 20:
            print(f"  ... and {len(filtered_out) - 20} more")

    if dry_run:
        print("\n🏁 DRY RUN COMPLETE - No changes made to database")
        print(f"\nWould import {len(valid_companies)} companies if run without --dry-run")
        return

    # Import to database
    print(f"\n📥 Importing {len(valid_companies)} companies to database...")

    with db_manager.SessionLocal() as db:
        # Get existing companies for deduplication
        existing_companies = db.query(ReferralSource).all()
        existing_names = {normalize_company_name(c.name).lower(): c for c in existing_companies}

        created = 0
        updated = 0
        skipped = 0

        for brevo_company in valid_companies:
            # Brevo CRM companies have attributes nested
            attrs = brevo_company.get('attributes', {})
            name = attrs.get('name', '').strip()

            if not name:
                continue

            normalized = normalize_company_name(name).lower()

            # Extract attributes from Brevo CRM company
            email = attrs.get('email')
            phone = attrs.get('phone')
            address = attrs.get('address')
            website = attrs.get('website')
            location = attrs.get('location')
            county = attrs.get('county')
            source_type = attrs.get('source_type', 'referral')
            notes = attrs.get('notes')

            # Check if company already exists
            if normalized in existing_names:
                # Update existing company
                company = existing_names[normalized]

                # Update fields if Brevo has more data
                updated_fields = []
                if email and not company.email:
                    company.email = email
                    updated_fields.append('email')
                if phone and not company.phone:
                    company.phone = phone
                    updated_fields.append('phone')
                if address and not company.address:
                    company.address = address
                    updated_fields.append('address')
                if website and not company.website:
                    company.website = website
                    updated_fields.append('website')
                if location and not company.location:
                    company.location = location
                    updated_fields.append('location')
                if county and not company.county:
                    company.county = county
                    updated_fields.append('county')
                if notes and not company.notes:
                    company.notes = notes
                    updated_fields.append('notes')

                if updated_fields:
                    company.updated_at = datetime.utcnow()
                    db.add(company)
                    updated += 1
                    print(f"  📝 Updated: {name} ({', '.join(updated_fields)})")
                else:
                    skipped += 1
            else:
                # Create new company
                company = ReferralSource(
                    name=name,
                    email=email,
                    phone=phone,
                    address=address,
                    website=website,
                    location=location,
                    county=county,
                    source_type=source_type or 'referral',
                    notes=notes,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(company)
                created += 1
                print(f"  ✨ Created: {name}")

        # Commit all changes
        try:
            db.commit()
            print(f"\n✅ Database updated successfully!")
        except Exception as e:
            db.rollback()
            print(f"\n❌ Error committing to database: {e}")
            return

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total Brevo companies fetched: {len(brevo_companies)}")
    print(f"Valid companies: {len(valid_companies)}")
    print(f"Filtered out (personal/junk): {len(filtered_out)}")
    print(f"\nDatabase changes:")
    print(f"  ✨ Created: {created}")
    print(f"  📝 Updated: {updated}")
    print(f"  ⏭️  Skipped (already exists): {skipped}")
    print("=" * 70)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Rebuild companies from Brevo')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run without making changes to database')
    args = parser.parse_args()

    rebuild_companies(dry_run=args.dry_run)

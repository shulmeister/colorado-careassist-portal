#!/usr/bin/env python3
"""
Populate Company Locations

Extracts location data from company names and populates the location field.
This allows the deduplication script to properly distinguish between
companies with the same name but different locations.
"""

import sys
import os
import re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db_manager
from models import ReferralSource

# Colorado cities to look for (ordered by specificity - longer names first)
COLORADO_CITIES = [
    "Colorado Springs",
    "Fort Collins",
    "Castle Rock",
    "Grand Junction",
    "Highlands Ranch",
    "Cherry Hills Village",
    "Denver",
    "Boulder",
    "Aurora",
    "Lakewood",
    "Arvada",
    "Westminster",
    "Thornton",
    "Centennial",
    "Littleton",
    "Broomfield",
    "Longmont",
    "Loveland",
    "Pueblo",
    "Greeley",
    "Parker",
    "Commerce City",
    "Northglenn",
    "Brighton",
    "Englewood",
    "Wheat Ridge",
    "Golden",
    "Louisville",
    "Lafayette",
    "Superior",
    "Erie",
    "Johnstown",
    "Windsor",
    "Firestone",
    "Frederick"
]

# Other common location indicators
OTHER_LOCATIONS = [
    "Colorado",
    "CO",
]


def extract_location(company_name: str) -> str:
    """
    Extract location from company name.

    Examples:
    - "Encompass Health Rehabilitation Hospital of Littleton" -> "Littleton"
    - "Advanced Health Aurora" -> "Aurora"
    - "City of Boulder Housing" -> "Boulder"
    - "Colorado Springs Orthopaedic Group" -> "Colorado Springs"
    """
    if not company_name:
        return ""

    # Check for Colorado cities (longest first to catch "Colorado Springs" before "Colorado")
    for city in COLORADO_CITIES:
        # Case-insensitive search
        pattern = r'\b' + re.escape(city) + r'\b'
        if re.search(pattern, company_name, re.IGNORECASE):
            return city

    # Check for state indicators
    for location in OTHER_LOCATIONS:
        pattern = r'\b' + re.escape(location) + r'\b'
        if re.search(pattern, company_name, re.IGNORECASE):
            # If just "Colorado" or "CO", return it
            # But skip if it's part of "Colorado Springs" etc (already checked above)
            return location

    return ""


def populate_locations(dry_run=False):
    """Populate location field for companies based on their names."""

    print("=" * 70)
    print("POPULATE COMPANY LOCATIONS")
    print("=" * 70)
    print(f"\nTime: {datetime.now().isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

    with db_manager.SessionLocal() as db:
        # Get all companies
        companies = db.query(ReferralSource).all()

        print(f"Total companies: {len(companies)}\n")

        updated = 0
        already_had_location = 0
        no_location_found = 0

        for company in companies:
            # Skip if already has location
            if company.location:
                already_had_location += 1
                continue

            # Try to extract location from name
            location = extract_location(company.name)

            if location:
                print(f"✓ {company.name}")
                print(f"  → Location: {location}")

                if not dry_run:
                    company.location = location
                    company.updated_at = datetime.utcnow()
                    db.add(company)

                updated += 1
            else:
                no_location_found += 1

        if not dry_run and updated > 0:
            db.commit()
            print(f"\n✅ Committed changes to database")

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total companies: {len(companies)}")
        print(f"Already had location: {already_had_location}")
        print(f"Location extracted: {updated}")
        print(f"No location found: {no_location_found}")
        print("=" * 70)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Populate company locations from names')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without modifying database')
    args = parser.parse_args()

    populate_locations(dry_run=args.dry_run)

#!/usr/bin/env python3
"""
Migrate Gigi Data to PostgreSQL Database

One-time migration script to move data from contacts_cache.json to the database.
Run this once after deploying the database models.

Usage:
    python gigi/migrate_to_db.py

    # On Heroku:
    heroku run python gigi/migrate_to_db.py -a careassist-unified
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    print("=" * 60)
    print("GIGI DATA MIGRATION - JSON to PostgreSQL")
    print("=" * 60)

    # Load the JSON cache
    cache_file = os.path.join(os.path.dirname(__file__), "contacts_cache.json")

    if not os.path.exists(cache_file):
        print(f"ERROR: Cache file not found: {cache_file}")
        sys.exit(1)

    with open(cache_file, 'r') as f:
        cache = json.load(f)

    print(f"\nLoaded cache:")
    print(f"  Caregivers: {len(cache.get('caregivers', {}))}")
    print(f"  Clients: {len(cache.get('clients', {}))}")
    print(f"  Shifts: {len(cache.get('shifts', []))}")
    print(f"  Unavailability: {len(cache.get('unavailability', []))}")

    # Import and initialize database
    from gigi.database import gigi_db
    gigi_db.initialize()
    print("\nDatabase connected.")

    # Migrate caregivers
    print("\n[1/4] Migrating caregivers...")
    caregivers = []
    for phone, data in cache.get("caregivers", {}).items():
        caregivers.append({
            "phone": phone,
            "name": data.get("name"),
            "status": data.get("status", "active"),
            "location": data.get("location"),
            "city": data.get("city"),
            "email": data.get("email"),
            "can_sms": data.get("can_sms", True)
        })
    cg_count = gigi_db.sync_caregivers(caregivers)
    print(f"  Migrated {cg_count} caregivers")

    # Migrate clients
    print("\n[2/4] Migrating clients...")
    clients = []
    for phone, data in cache.get("clients", {}).items():
        clients.append({
            "phone": phone,
            "name": data.get("name"),
            "status": data.get("status", "active"),
            "location": data.get("location"),
            "address": data.get("address"),
            "primary_caregiver": data.get("primary_caregiver")
        })
    cl_count = gigi_db.sync_clients(clients)
    print(f"  Migrated {cl_count} clients")

    # Migrate shifts
    print("\n[3/4] Migrating shifts...")
    shifts = cache.get("shifts", [])
    sh_count = gigi_db.sync_shifts(shifts)
    print(f"  Migrated {sh_count} shifts")

    # Migrate unavailability
    print("\n[4/4] Migrating unavailability...")
    unavailability = cache.get("unavailability", [])
    un_count = gigi_db.sync_unavailability(unavailability)
    print(f"  Migrated {un_count} unavailability blocks")

    # Log the migration
    gigi_db.log_sync(
        sync_type="migration",
        status="completed",
        caregivers=cg_count,
        clients=cl_count,
        shifts=sh_count,
        unavailability=un_count
    )

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"Caregivers: {cg_count}")
    print(f"Clients: {cl_count}")
    print(f"Shifts: {sh_count}")
    print(f"Unavailability blocks: {un_count}")
    print("\nGigi is now using PostgreSQL for all data storage.")


if __name__ == "__main__":
    main()

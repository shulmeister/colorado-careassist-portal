#!/usr/bin/env python3
"""
Sync contacts cache from WellSky

This script pulls all caregivers and clients from WellSky and updates
the local contacts_cache.json file. Run this daily or weekly to keep
the cache fresh.

Usage:
    python gigi/sync_contacts.py

    # On Mac Mini (Local):
    mac-mini run python gigi/sync_contacts.py -a careassist-unified
"""

import os
import json
import requests
from datetime import datetime

# Configuration
PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "https://careassist-unified-0a11ddb45ac0.mac-miniapp.com")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, "contacts_cache.json")


def load_existing_cache():
    """Load existing cache to preserve manual entries."""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load existing cache: {e}")
    return {"caregivers": {}, "clients": {}}


def normalize_phone(phone: str) -> str:
    """Normalize phone to 10 digits."""
    if not phone:
        return ""
    clean = ''.join(filter(str.isdigit, phone))
    if len(clean) == 11 and clean.startswith('1'):
        clean = clean[1:]
    return clean[-10:] if len(clean) >= 10 else clean


def fetch_caregivers():
    """Fetch caregivers from WellSky API."""
    print("Fetching caregivers from WellSky...")
    try:
        response = requests.get(
            f"{PORTAL_BASE_URL}/api/wellsky/caregivers",
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            caregivers = data.get("caregivers", [])
            print(f"  Found {len(caregivers)} caregivers")
            return caregivers
        else:
            print(f"  Error: {response.status_code}")
    except Exception as e:
        print(f"  Error fetching caregivers: {e}")
    return []


def fetch_clients():
    """Fetch clients from WellSky API."""
    print("Fetching clients from WellSky...")
    try:
        response = requests.get(
            f"{PORTAL_BASE_URL}/api/wellsky/clients",
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            clients = data.get("clients", [])
            print(f"  Found {len(clients)} clients")
            return clients
        else:
            print(f"  Error: {response.status_code}")
    except Exception as e:
        print(f"  Error fetching clients: {e}")
    return []


def build_cache(caregivers, clients, existing_cache):
    """Build the contacts cache from WellSky data."""
    cache = {
        "caregivers": {},
        "clients": {},
        "last_sync": datetime.now().isoformat(),
        "notes": "Auto-synced from WellSky. Run sync_contacts.py to refresh."
    }

    # Process caregivers
    for cg in caregivers:
        phone = normalize_phone(cg.get("phone", ""))
        if phone and len(phone) == 10:
            name = f"{cg.get('first_name', '')} {cg.get('last_name', '')}".strip()
            cache["caregivers"][phone] = {
                "name": name or "Unknown",
                "status": cg.get("status", "active"),
                "id": cg.get("id")
            }

    # Process clients
    for cl in clients:
        phone = normalize_phone(cl.get("phone", ""))
        if phone and len(phone) == 10:
            name = f"{cl.get('first_name', '')} {cl.get('last_name', '')}".strip()
            cache["clients"][phone] = {
                "name": name or "Unknown",
                "status": cl.get("status", "active"),
                "id": cl.get("id"),
                "location": cl.get("city") or cl.get("address", {}).get("city")
            }

    # Preserve any manual entries from existing cache that aren't in WellSky
    existing_cgs = existing_cache.get("caregivers", {})
    for phone, data in existing_cgs.items():
        if phone not in cache["caregivers"]:
            cache["caregivers"][phone] = data
            print(f"  Preserved manual entry: caregiver {data.get('name')} ({phone})")

    existing_clients = existing_cache.get("clients", {})
    for phone, data in existing_clients.items():
        if phone not in cache["clients"]:
            cache["clients"][phone] = data
            print(f"  Preserved manual entry: client {data.get('name')} ({phone})")

    return cache


def save_cache(cache):
    """Save cache to file."""
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)
    print(f"Cache saved to {CACHE_FILE}")


def main():
    print("=" * 60)
    print("GIGI CONTACTS CACHE SYNC")
    print("=" * 60)
    print(f"Portal URL: {PORTAL_BASE_URL}")
    print()

    # Load existing cache
    existing_cache = load_existing_cache()
    print(f"Existing cache: {len(existing_cache.get('caregivers', {}))} caregivers, {len(existing_cache.get('clients', {}))} clients")
    print()

    # Fetch from WellSky
    caregivers = fetch_caregivers()
    clients = fetch_clients()
    print()

    # Build new cache
    print("Building cache...")
    cache = build_cache(caregivers, clients, existing_cache)
    print(f"  Total caregivers: {len(cache['caregivers'])}")
    print(f"  Total clients: {len(cache['clients'])}")
    print()

    # Save
    save_cache(cache)

    print()
    print("=" * 60)
    print("SYNC COMPLETE")
    print("=" * 60)
    print(f"Caregivers: {len(cache['caregivers'])}")
    print(f"Clients: {len(cache['clients'])}")
    print(f"Last sync: {cache['last_sync']}")


if __name__ == "__main__":
    main()

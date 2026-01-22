#!/usr/bin/env python3
"""
Gigi Daily Sync - Automated WellSky Data Refresh

This script runs automatically every 24 hours to:
1. Pull all caregivers from WellSky (with phone, location, email)
2. Pull all clients from WellSky (with phone, location)
3. Pull upcoming shifts for next 30 days
4. Save everything to contacts_cache.json for instant lookup

Scheduled via Heroku Scheduler to run daily at 3 AM Mountain Time.

Usage:
    python gigi/daily_sync.py

    # On Heroku:
    heroku run python gigi/daily_sync.py -a careassist-unified
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "https://careassist-unified-0a11ddb45ac0.herokuapp.com")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, "contacts_cache.json")


def normalize_phone(phone: str) -> Optional[str]:
    """Normalize phone to 10 digits."""
    if not phone:
        return None
    clean = ''.join(filter(str.isdigit, str(phone)))
    if len(clean) == 11 and clean.startswith('1'):
        clean = clean[1:]
    return clean if len(clean) == 10 else None


def load_existing_cache() -> Dict[str, Any]:
    """Load existing cache to preserve manual entries."""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading existing cache: {e}")
    return {"caregivers": {}, "clients": {}, "shifts": []}


def fetch_caregivers() -> List[Dict]:
    """Fetch caregivers from WellSky API."""
    logger.info("Fetching caregivers from WellSky...")
    try:
        response = requests.get(
            f"{PORTAL_BASE_URL}/api/wellsky/caregivers",
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            caregivers = data.get("caregivers", [])
            logger.info(f"  Found {len(caregivers)} caregivers")
            return caregivers
        else:
            logger.error(f"  Error fetching caregivers: {response.status_code}")
    except Exception as e:
        logger.error(f"  Exception fetching caregivers: {e}")
    return []


def fetch_clients() -> List[Dict]:
    """Fetch clients from WellSky API."""
    logger.info("Fetching clients from WellSky...")
    try:
        response = requests.get(
            f"{PORTAL_BASE_URL}/api/wellsky/clients",
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            clients = data.get("clients", [])
            logger.info(f"  Found {len(clients)} clients")
            return clients
        else:
            logger.error(f"  Error fetching clients: {response.status_code}")
    except Exception as e:
        logger.error(f"  Exception fetching clients: {e}")
    return []


def fetch_shifts(days_ahead: int = 30) -> List[Dict]:
    """Fetch upcoming shifts from WellSky API."""
    logger.info(f"Fetching shifts for next {days_ahead} days...")
    try:
        response = requests.get(
            f"{PORTAL_BASE_URL}/api/wellsky/shifts",
            params={"days": days_ahead},
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            shifts = data.get("shifts", [])
            logger.info(f"  Found {len(shifts)} upcoming shifts")
            return shifts
        else:
            logger.error(f"  Error fetching shifts: {response.status_code}")
    except Exception as e:
        logger.error(f"  Exception fetching shifts: {e}")
    return []


def build_caregiver_cache(caregivers: List[Dict], existing: Dict[str, Any]) -> Dict[str, Dict]:
    """Build caregiver lookup by phone number."""
    cache = {}

    for cg in caregivers:
        # Try mobile first, then home
        phone = normalize_phone(cg.get("mobile_phone") or cg.get("phone") or cg.get("home_phone"))
        if not phone:
            continue

        name = f"{cg.get('first_name', '')} {cg.get('last_name', '')}".strip()
        cache[phone] = {
            "name": name or "Unknown",
            "status": cg.get("status", "active"),
            "location": cg.get("location") or cg.get("service_area", ""),
            "city": cg.get("city", ""),
            "email": cg.get("email"),
            "can_sms": cg.get("send_sms", True),
            "id": cg.get("id")
        }

    # Preserve manual entries not in WellSky
    existing_cgs = existing.get("caregivers", {})
    for phone, data in existing_cgs.items():
        if phone not in cache and data.get("manual", False):
            cache[phone] = data
            logger.info(f"  Preserved manual entry: {data.get('name')}")

    return cache


def build_client_cache(clients: List[Dict], existing: Dict[str, Any]) -> Dict[str, Dict]:
    """Build client lookup by phone number."""
    cache = {}

    for cl in clients:
        # Try home phone first, then mobile
        phone = normalize_phone(cl.get("phone") or cl.get("home_phone") or cl.get("mobile_phone"))
        if not phone:
            continue

        name = f"{cl.get('first_name', '')} {cl.get('last_name', '')}".strip()
        cache[phone] = {
            "name": name or "Unknown",
            "status": cl.get("status", "active"),
            "location": cl.get("city") or cl.get("location", ""),
            "id": cl.get("id"),
            "address": cl.get("address"),
            "primary_caregiver": cl.get("primary_caregiver_name")
        }

        # Also add mobile if different
        mobile = normalize_phone(cl.get("mobile_phone"))
        if mobile and mobile != phone:
            cache[mobile] = cache[phone].copy()

    # Preserve manual entries
    existing_clients = existing.get("clients", {})
    for phone, data in existing_clients.items():
        if phone not in cache and data.get("manual", False):
            cache[phone] = data
            logger.info(f"  Preserved manual entry: {data.get('name')}")

    return cache


def build_shifts_cache(shifts: List[Dict]) -> List[Dict]:
    """Build shifts list for next 30 days."""
    cache = []

    for shift in shifts:
        cache.append({
            "caregiver_name": shift.get("caregiver_name") or shift.get("caregiver"),
            "caregiver_id": shift.get("caregiver_id"),
            "client_name": shift.get("client_name") or shift.get("client"),
            "client_id": shift.get("client_id"),
            "start_time": shift.get("start_time") or shift.get("next_occurrence_start"),
            "end_time": shift.get("end_time"),
            "status": shift.get("status", "Scheduled"),
            "location": shift.get("location") or shift.get("address")
        })

    # Sort by start time
    cache.sort(key=lambda x: x.get("start_time") or "")

    return cache


def get_caregiver_by_name(cache: Dict[str, Dict], name: str) -> Optional[Dict]:
    """Look up caregiver by name (for shift matching)."""
    name_lower = name.lower().strip()
    for phone, data in cache.items():
        if data.get("name", "").lower() == name_lower:
            return {"phone": phone, **data}
    return None


def get_client_by_name(cache: Dict[str, Dict], name: str) -> Optional[Dict]:
    """Look up client by name (for shift matching)."""
    name_lower = name.lower().strip()
    for phone, data in cache.items():
        if data.get("name", "").lower() == name_lower:
            return {"phone": phone, **data}
    return None


def enrich_shifts_with_contact_info(shifts: List[Dict], caregivers: Dict, clients: Dict) -> List[Dict]:
    """Add phone numbers and contact info to shifts."""
    enriched = []

    for shift in shifts:
        cg_name = shift.get("caregiver_name", "")
        cl_name = shift.get("client_name", "")

        cg = get_caregiver_by_name(caregivers, cg_name)
        cl = get_client_by_name(clients, cl_name)

        shift["caregiver_phone"] = cg.get("phone") if cg else None
        shift["caregiver_email"] = cg.get("email") if cg else None
        shift["caregiver_can_sms"] = cg.get("can_sms", False) if cg else False
        shift["caregiver_location"] = cg.get("location") if cg else None

        shift["client_phone"] = cl.get("phone") if cl else None
        shift["client_location"] = cl.get("location") if cl else None
        shift["client_address"] = cl.get("address") if cl else None

        enriched.append(shift)

    return enriched


def save_cache(cache: Dict[str, Any]) -> None:
    """Save cache to file."""
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2, default=str)
    logger.info(f"Cache saved to {CACHE_FILE}")


def main():
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("GIGI DAILY SYNC - Starting")
    logger.info("=" * 60)
    logger.info(f"Portal URL: {PORTAL_BASE_URL}")
    logger.info(f"Start time: {start_time.isoformat()}")

    # Load existing cache
    existing = load_existing_cache()
    logger.info(f"Existing cache: {len(existing.get('caregivers', {}))} caregivers, "
                f"{len(existing.get('clients', {}))} clients, "
                f"{len(existing.get('shifts', []))} shifts")

    # Fetch from WellSky
    caregivers_raw = fetch_caregivers()
    clients_raw = fetch_clients()
    shifts_raw = fetch_shifts(days_ahead=30)

    # Build caches
    logger.info("Building caches...")
    caregivers = build_caregiver_cache(caregivers_raw, existing)
    clients = build_client_cache(clients_raw, existing)
    shifts = build_shifts_cache(shifts_raw)

    # Enrich shifts with contact info
    if shifts:
        shifts = enrich_shifts_with_contact_info(shifts, caregivers, clients)

    # Create final cache
    cache = {
        "caregivers": caregivers,
        "clients": clients,
        "shifts": shifts,
        "last_sync": datetime.now().isoformat(),
        "sync_stats": {
            "caregivers_count": len(caregivers),
            "clients_count": len(clients),
            "shifts_count": len(shifts),
            "sync_duration_seconds": (datetime.now() - start_time).total_seconds()
        },
        "notes": "Auto-synced from WellSky. Runs daily at 3 AM Mountain Time."
    }

    # Save
    save_cache(cache)

    # Summary
    duration = (datetime.now() - start_time).total_seconds()
    logger.info("")
    logger.info("=" * 60)
    logger.info("SYNC COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Caregivers: {len(caregivers)}")
    logger.info(f"Clients: {len(clients)}")
    logger.info(f"Upcoming shifts: {len(shifts)}")
    logger.info(f"Duration: {duration:.1f} seconds")
    logger.info(f"Next sync: ~24 hours")

    # Show next few shifts
    if shifts:
        logger.info("")
        logger.info("Next 5 shifts:")
        for shift in shifts[:5]:
            logger.info(f"  {shift.get('start_time', 'TBD')}: "
                       f"{shift.get('caregiver_name', 'TBD')} -> {shift.get('client_name', 'TBD')}")


if __name__ == "__main__":
    main()

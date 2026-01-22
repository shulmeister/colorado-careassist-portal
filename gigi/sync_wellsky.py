#!/usr/bin/env python3
"""
Sync WellSky data to Gigi's PostgreSQL database.

This script pulls caregivers, clients, shifts, and unavailability from WellSky
and stores them in the local database for fast lookups during calls.

Run manually: python gigi/sync_wellsky.py
Run via scheduler: heroku run python gigi/sync_wellsky.py --app careassist-unified

Recommended schedule: Every 15-30 minutes during business hours.
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.wellsky_service import WellSkyService
from gigi.database import gigi_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def sync_caregivers(wellsky: WellSkyService) -> int:
    """Sync active caregivers from WellSky."""
    logger.info("Syncing caregivers...")

    # Get all caregivers (mock mode doesn't filter by status string)
    caregivers = wellsky.get_caregivers()

    caregiver_data = []
    for cg in caregivers:
        phone = ''.join(filter(str.isdigit, cg.phone or ""))[-10:]
        if len(phone) != 10:
            continue

        caregiver_data.append({
            "phone": phone,
            "name": f"{cg.first_name} {cg.last_name}".strip(),
            "status": cg.status.value if hasattr(cg.status, 'value') else str(cg.status),
            "location": cg.city,  # Use city as location
            "city": cg.city,
            "email": cg.email,
            "can_sms": True,
            "wellsky_id": cg.id
        })

    count = gigi_db.sync_caregivers(caregiver_data)
    logger.info(f"Synced {count} caregivers")
    return count


def sync_clients(wellsky: WellSkyService) -> int:
    """Sync active clients from WellSky."""
    logger.info("Syncing clients...")

    # Get all clients
    clients = wellsky.get_clients()

    client_data = []
    for cl in clients:
        phone = ''.join(filter(str.isdigit, cl.phone or ""))[-10:]
        if len(phone) != 10:
            continue

        # Get primary caregiver from preferred_caregivers list
        primary_cg = cl.preferred_caregivers[0] if cl.preferred_caregivers else None

        client_data.append({
            "phone": phone,
            "name": f"{cl.first_name} {cl.last_name}".strip(),
            "status": cl.status.value if hasattr(cl.status, 'value') else str(cl.status),
            "location": cl.city,
            "address": cl.address,
            "primary_caregiver": primary_cg,
            "wellsky_id": cl.id
        })

    count = gigi_db.sync_clients(client_data)
    logger.info(f"Synced {count} clients")
    return count


def sync_shifts(wellsky: WellSkyService) -> int:
    """Sync upcoming shifts (next 30 days) from WellSky."""
    logger.info("Syncing shifts...")

    from datetime import date
    today = date.today()
    end_date = today + timedelta(days=30)

    shifts = wellsky.get_shifts(date_from=today, date_to=end_date)

    shift_data = []
    for sh in shifts:
        # Build caregiver and client names from first/last
        caregiver_name = f"{sh.caregiver_first_name} {sh.caregiver_last_name}".strip()
        client_name = f"{sh.client_first_name} {sh.client_last_name}".strip()

        # Build datetime from date + start_time string
        start_datetime = None
        if sh.date and sh.start_time:
            try:
                start_datetime = datetime.combine(
                    sh.date,
                    datetime.strptime(sh.start_time, "%H:%M").time()
                )
            except (ValueError, TypeError):
                start_datetime = datetime.combine(sh.date, datetime.min.time())
        elif sh.date:
            start_datetime = datetime.combine(sh.date, datetime.min.time())

        shift_data.append({
            "caregiver_name": caregiver_name,
            "client_name": client_name,
            "start_time": start_datetime.isoformat() if start_datetime else None,
            "status": sh.status.value if hasattr(sh.status, 'value') else str(sh.status),
            "pay_amount": None,
            "pay_method": None
        })

    count = gigi_db.sync_shifts(shift_data)
    logger.info(f"Synced {count} shifts")
    return count


def sync_unavailability(wellsky: WellSkyService) -> int:
    """Sync caregiver unavailability from WellSky."""
    logger.info("Syncing unavailability...")

    # WellSky may have an availability/unavailability endpoint
    # For now, we'll use caregiver profiles which may have availability info
    caregivers = wellsky.get_caregivers(status="active")

    unavail_data = []
    for cg in caregivers:
        # Check if caregiver has unavailability data
        if hasattr(cg, 'unavailability') and cg.unavailability:
            for block in cg.unavailability:
                unavail_data.append({
                    "caregiver_name": f"{cg.first_name} {cg.last_name}".strip(),
                    "reason": block.get("reason", "Unavailable"),
                    "description": block.get("description", "")
                })

    if unavail_data:
        count = gigi_db.sync_unavailability(unavail_data)
        logger.info(f"Synced {count} unavailability blocks")
        return count

    logger.info("No unavailability data to sync")
    return 0


def run_full_sync():
    """Run a complete sync from WellSky to Gigi database."""
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("GIGI WELLSKY SYNC STARTING")
    logger.info("=" * 60)

    # Initialize database
    gigi_db.initialize()

    # Initialize WellSky service
    wellsky = WellSkyService()

    if not wellsky.is_configured:
        logger.warning("WellSky API not configured - using mock data")

    stats = {
        "caregivers": 0,
        "clients": 0,
        "shifts": 0,
        "unavailability": 0
    }

    try:
        stats["caregivers"] = sync_caregivers(wellsky)
        stats["clients"] = sync_clients(wellsky)
        stats["shifts"] = sync_shifts(wellsky)
        stats["unavailability"] = sync_unavailability(wellsky)

        duration = time.time() - start_time

        # Log the sync
        gigi_db.log_sync(
            sync_type="full",
            status="completed",
            duration=duration,
            **stats
        )

        logger.info("=" * 60)
        logger.info("SYNC COMPLETED SUCCESSFULLY")
        logger.info(f"  Caregivers: {stats['caregivers']}")
        logger.info(f"  Clients: {stats['clients']}")
        logger.info(f"  Shifts: {stats['shifts']}")
        logger.info(f"  Unavailability: {stats['unavailability']}")
        logger.info(f"  Duration: {duration:.2f}s")
        logger.info("=" * 60)

        return True

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Sync failed: {e}")

        gigi_db.log_sync(
            sync_type="full",
            status="failed",
            error=str(e),
            duration=duration,
            **stats
        )

        return False


if __name__ == "__main__":
    success = run_full_sync()
    sys.exit(0 if success else 1)

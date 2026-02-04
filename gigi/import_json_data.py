#!/usr/bin/env python3
"""
Import WellSky JSON data into Gigi's PostgreSQL database.

This script reads from gigi/data/*.json files and imports into PostgreSQL.
Run on Mac Mini (Local): mac-mini run python gigi/import_json_data.py --app careassist-unified
"""

import os
import sys
import re
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from gigi.database import gigi_db
from gigi.models import GigiCaregiver, GigiClient, GigiShift, GigiUnavailability


def get_data_path(filename: str) -> str:
    """Get path to data file."""
    return os.path.join(os.path.dirname(__file__), "data", filename)


def import_caregivers():
    """Import caregivers from JSON."""
    print("\n" + "="*60)
    print("IMPORTING CAREGIVERS")
    print("="*60)

    filepath = get_data_path("caregivers.json")
    with open(filepath) as f:
        caregivers = json.load(f)

    print(f"Found {len(caregivers)} caregivers in file")

    with gigi_db.get_session() as session:
        session.query(GigiCaregiver).delete()

        for cg in caregivers:
            caregiver = GigiCaregiver(
                phone=cg["phone"],
                name=cg["name"],
                status="active",
                location=cg.get("location", ""),
                city=cg.get("city", ""),
                email=cg.get("email", ""),
                can_sms=cg.get("can_sms", True)
            )
            session.add(caregiver)

    print(f"Imported: {len(caregivers)} caregivers")
    return len(caregivers)


def import_shifts():
    """Import shifts from JSON."""
    print("\n" + "="*60)
    print("IMPORTING SHIFTS")
    print("="*60)

    filepath = get_data_path("shifts.json")
    with open(filepath) as f:
        shifts = json.load(f)

    print(f"Found {len(shifts)} shifts in file")

    count = 0
    with gigi_db.get_session() as session:
        session.query(GigiShift).delete()

        for sh in shifts:
            start_time = sh.get("start_time")
            if start_time and isinstance(start_time, str):
                try:
                    start_time = datetime.fromisoformat(start_time.replace("Z", ""))
                except:
                    continue
            else:
                continue

            shift = GigiShift(
                caregiver_name=sh.get("caregiver_name", ""),
                client_name=sh.get("client_name", ""),
                start_time=start_time,
                status=sh.get("status", "Scheduled"),
                pay_amount=sh.get("pay_amount"),
                pay_method=sh.get("pay_method")
            )
            session.add(shift)
            count += 1

    print(f"Imported: {count} shifts")
    return count


def import_clients():
    """Import clients from JSON."""
    print("\n" + "="*60)
    print("IMPORTING CLIENTS")
    print("="*60)

    filepath = get_data_path("clients.json")
    with open(filepath) as f:
        clients = json.load(f)

    print(f"Found {len(clients)} clients in file")

    count = 0
    with gigi_db.get_session() as session:
        session.query(GigiClient).delete()

        for client_data in clients:
            # Handle both old format (list of names) and new format (list of dicts)
            if isinstance(client_data, str):
                # Old format - just name
                client = GigiClient(
                    phone=f"000000{count:04d}",
                    name=client_data,
                    status="active",
                    location="Colorado"
                )
            else:
                # New format - dict with phone, name, city, address
                client = GigiClient(
                    phone=client_data.get("phone", f"000000{count:04d}"),
                    name=client_data.get("name", "Unknown"),
                    status="active",
                    location=client_data.get("city", "Colorado"),
                    address=client_data.get("address", "")
                )
            session.add(client)
            count += 1

    print(f"Imported: {count} clients")
    return count


def import_unavailability():
    """Import unavailability from JSON."""
    print("\n" + "="*60)
    print("IMPORTING UNAVAILABILITY")
    print("="*60)

    filepath = get_data_path("unavailability.json")
    with open(filepath) as f:
        unavail_list = json.load(f)

    print(f"Found {len(unavail_list)} unavailability records in file")

    with gigi_db.get_session() as session:
        session.query(GigiUnavailability).delete()

        for item in unavail_list:
            description = item.get("description", "")
            desc_lower = description.lower()

            is_recurring = "repeats weekly" in desc_lower
            all_day = "all day" in desc_lower

            days = []
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                if day in desc_lower:
                    days.append(day)

            start_date = None
            date_match = re.search(r'starting on (\w+ \d+, \d+)', description)
            if date_match:
                try:
                    start_date = datetime.strptime(date_match.group(1), "%b %d, %Y")
                except:
                    pass

            unavail = GigiUnavailability(
                caregiver_name=item.get("caregiver_name", ""),
                reason=item.get("reason", "Unavailable"),
                description=description,
                is_recurring=is_recurring,
                recurring_days=days if days else None,
                start_date=start_date,
                all_day=all_day
            )
            session.add(unavail)

    print(f"Imported: {len(unavail_list)} unavailability records")
    return len(unavail_list)


def main():
    print("="*60)
    print("WELLSKY JSON IMPORT TO GIGI DATABASE")
    print("="*60)

    gigi_db.initialize()

    stats = {
        "caregivers": import_caregivers(),
        "shifts": import_shifts(),
        "clients": import_clients(),
        "unavailability": import_unavailability()
    }

    print("\n" + "="*60)
    print("IMPORT COMPLETE")
    print("="*60)
    for key, val in stats.items():
        print(f"  {key}: {val}")

    return stats


if __name__ == "__main__":
    main()

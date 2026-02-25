#!/usr/bin/env python3
"""
Import WellSky Excel exports into Gigi's PostgreSQL database.

Usage:
    python gigi/import_wellsky_excel.py

Reads from Desktop:
    - caregivers (1).xls
    - shifts-by-caregiver.xls
    - caregiver-unavailability.xls
"""

import os
import sys
import re
import pandas as pd
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from gigi.database import gigi_db
from gigi.models import GigiCaregiver, GigiClient, GigiShift, GigiUnavailability


def clean_phone(phone_val) -> str:
    """Extract 10-digit phone number."""
    if pd.isna(phone_val):
        return ""
    # Handle scientific notation from Excel (e.g., 7.192872e+09)
    if isinstance(phone_val, float):
        phone_val = str(int(phone_val))
    phone_str = str(phone_val)
    digits = ''.join(filter(str.isdigit, phone_str))
    return digits[-10:] if len(digits) >= 10 else ""


def import_caregivers(filepath: str):
    """Import caregivers from Excel."""
    print(f"\n{'='*60}")
    print("IMPORTING CAREGIVERS")
    print("="*60)

    df = pd.read_excel(filepath)
    print(f"Found {len(df)} caregivers in file")

    count = 0
    skipped = 0

    with gigi_db.get_session() as session:
        # Clear existing caregivers
        session.query(GigiCaregiver).delete()

        for _, row in df.iterrows():
            phone = clean_phone(row.get('Mobile Phone'))
            if not phone:
                phone = clean_phone(row.get('Home Phone'))

            if not phone:
                skipped += 1
                continue

            name = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()

            caregiver = GigiCaregiver(
                phone=phone,
                name=name,
                status="active",
                location=row.get('Location', ''),
                city=row.get('City', ''),
                email=row.get('Email', '') if pd.notna(row.get('Email')) else '',
                can_sms=bool(row.get('Send SMS', True))
            )
            session.add(caregiver)
            count += 1

    print(f"Imported: {count} caregivers")
    print(f"Skipped (no phone): {skipped}")
    return count


def import_shifts(filepath: str):
    """Import shifts from Excel."""
    print(f"\n{'='*60}")
    print("IMPORTING SHIFTS")
    print("="*60)

    df = pd.read_excel(filepath)
    print(f"Found {len(df)} shifts in file")

    count = 0

    with gigi_db.get_session() as session:
        # Clear existing shifts
        session.query(GigiShift).delete()

        for _, row in df.iterrows():
            caregiver_name = str(row.get('Caregiver', '')).strip()
            client_name = str(row.get('Client', '')).strip()

            # Parse start time
            start_time = row.get('Next Occurrence Start')
            if isinstance(start_time, str):
                try:
                    start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                except:
                    start_time = None
            elif pd.isna(start_time):
                start_time = None

            if not start_time:
                continue

            shift = GigiShift(
                caregiver_name=caregiver_name,
                client_name=client_name,
                start_time=start_time,
                status=row.get('Status', 'Scheduled'),
                pay_amount=float(row.get('Pay Amount', 0)) if pd.notna(row.get('Pay Amount')) else None,
                pay_method=row.get('Pay Method', '') if pd.notna(row.get('Pay Method')) else None
            )
            session.add(shift)
            count += 1

    print(f"Imported: {count} shifts")
    return count


def import_clients_from_shifts(filepath: str):
    """Extract unique clients from shifts and import them."""
    print(f"\n{'='*60}")
    print("EXTRACTING CLIENTS FROM SHIFTS")
    print("="*60)

    df = pd.read_excel(filepath)

    # Get unique clients
    clients = df['Client'].dropna().unique()
    print(f"Found {len(clients)} unique clients")

    count = 0

    with gigi_db.get_session() as session:
        # Clear existing clients
        session.query(GigiClient).delete()

        for client_name in clients:
            client_name = str(client_name).strip()
            if not client_name:
                continue

            # We don't have phone numbers for clients in this export
            # Generate a placeholder - they'll be updated when real data comes
            client = GigiClient(
                phone=f"000000{count:04d}",  # Placeholder
                name=client_name,
                status="active",
                location="Colorado"
            )
            session.add(client)
            count += 1

    print(f"Imported: {count} clients (no phone numbers - need separate export)")
    return count


def import_unavailability(filepath: str):
    """Import caregiver unavailability from Excel."""
    print(f"\n{'='*60}")
    print("IMPORTING UNAVAILABILITY")
    print("="*60)

    df = pd.read_excel(filepath)
    print(f"Found {len(df)} unavailability records in file")

    count = 0

    with gigi_db.get_session() as session:
        # Clear existing unavailability
        session.query(GigiUnavailability).delete()

        for _, row in df.iterrows():
            caregiver_name = str(row.get('Caregiver Name', '')).strip()
            reason = str(row.get('Unavailability Reason', 'Unavailable')).strip()
            description = str(row.get('Unavailability Description', '')).strip()

            # Parse the description to extract structured data
            desc_lower = description.lower()
            is_recurring = "repeats weekly" in desc_lower
            all_day = "all day" in desc_lower

            # Extract days of week
            days = []
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                if day in desc_lower:
                    days.append(day)

            # Extract start date
            start_date = None
            date_match = re.search(r'starting on (\w+ \d+, \d+)', description)
            if date_match:
                try:
                    start_date = datetime.strptime(date_match.group(1), "%b %d, %Y")
                except:
                    pass

            unavail = GigiUnavailability(
                caregiver_name=caregiver_name,
                reason=reason,
                description=description,
                is_recurring=is_recurring,
                recurring_days=days if days else None,
                start_date=start_date,
                all_day=all_day
            )
            session.add(unavail)
            count += 1

    print(f"Imported: {count} unavailability records")
    return count


def main():
    print("="*60)
    print("WELLSKY EXCEL IMPORT TO GIGI DATABASE")
    print("="*60)

    # Initialize database
    gigi_db.initialize()

    # File paths
    desktop = "/Users/shulmeister/Desktop"

    caregivers_file = f"{desktop}/caregivers (1).xls"
    shifts_file = f"{desktop}/shifts-by-caregiver.xls"
    unavail_file = f"{desktop}/caregiver-unavailability.xls"

    stats = {}

    # Import caregivers
    if os.path.exists(caregivers_file):
        stats['caregivers'] = import_caregivers(caregivers_file)
    else:
        print(f"WARNING: {caregivers_file} not found")

    # Import shifts
    if os.path.exists(shifts_file):
        stats['shifts'] = import_shifts(shifts_file)
        stats['clients'] = import_clients_from_shifts(shifts_file)
    else:
        print(f"WARNING: {shifts_file} not found")

    # Import unavailability
    if os.path.exists(unavail_file):
        stats['unavailability'] = import_unavailability(unavail_file)
    else:
        print(f"WARNING: {unavail_file} not found")

    print("\n" + "="*60)
    print("IMPORT COMPLETE")
    print("="*60)
    for key, val in stats.items():
        print(f"  {key}: {val}")

    return stats


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Migrate Gigi Data to PostgreSQL using raw SQL inserts.
Bypasses SQLAlchemy ORM to avoid any schema conflicts.
"""

import os
import sys
import json
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

def main():
    print("=" * 60)
    print("GIGI DATA MIGRATION - JSON to PostgreSQL (Raw SQL)")
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

    # Connect to database
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql+psycopg2://', 1)
    elif database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg2://', 1)

    engine = create_engine(database_url)
    print("\nDatabase connected.")

    # Migrate caregivers
    print("\n[1/4] Migrating caregivers...")
    cg_count = 0
    with engine.connect() as conn:
        for phone, data in cache.get("caregivers", {}).items():
            if not phone or len(phone) != 10:
                continue
            try:
                conn.execute(text("""
                    INSERT INTO gigi_caregivers (phone, name, status, location, city, email, can_sms)
                    VALUES (:phone, :name, :status, :location, :city, :email, :can_sms)
                    ON CONFLICT (phone) DO UPDATE SET
                        name = EXCLUDED.name,
                        status = EXCLUDED.status,
                        location = EXCLUDED.location,
                        city = EXCLUDED.city,
                        email = EXCLUDED.email,
                        can_sms = EXCLUDED.can_sms,
                        updated_at = CURRENT_TIMESTAMP
                """), {
                    "phone": phone,
                    "name": data.get("name", "Unknown"),
                    "status": data.get("status", "active"),
                    "location": (data.get("location") or "").strip() or None,
                    "city": (data.get("city") or "").strip() or None,
                    "email": data.get("email"),
                    "can_sms": data.get("can_sms", True)
                })
                cg_count += 1
            except Exception as e:
                print(f"  Error inserting caregiver {phone}: {e}")
        conn.commit()
    print(f"  Migrated {cg_count} caregivers")

    # Migrate clients
    print("\n[2/4] Migrating clients...")
    cl_count = 0
    with engine.connect() as conn:
        for phone, data in cache.get("clients", {}).items():
            if not phone or len(phone) != 10:
                continue
            try:
                conn.execute(text("""
                    INSERT INTO gigi_clients (phone, name, status, location, address, primary_caregiver)
                    VALUES (:phone, :name, :status, :location, :address, :primary_caregiver)
                    ON CONFLICT (phone) DO UPDATE SET
                        name = EXCLUDED.name,
                        status = EXCLUDED.status,
                        location = EXCLUDED.location,
                        address = EXCLUDED.address,
                        primary_caregiver = EXCLUDED.primary_caregiver,
                        updated_at = CURRENT_TIMESTAMP
                """), {
                    "phone": phone,
                    "name": data.get("name", "Unknown"),
                    "status": data.get("status", "active"),
                    "location": (data.get("location") or "").strip() or None,
                    "address": data.get("address"),
                    "primary_caregiver": data.get("primary_caregiver")
                })
                cl_count += 1
            except Exception as e:
                print(f"  Error inserting client {phone}: {e}")
        conn.commit()
    print(f"  Migrated {cl_count} clients")

    # Migrate shifts
    print("\n[3/4] Migrating shifts...")
    sh_count = 0
    with engine.connect() as conn:
        # Clear existing future shifts
        conn.execute(text("DELETE FROM gigi_shifts WHERE start_time >= CURRENT_TIMESTAMP"))

        for shift_data in cache.get("shifts", []):
            start_time = shift_data.get("start_time")
            if isinstance(start_time, str):
                try:
                    start_time = datetime.fromisoformat(start_time.replace("Z", ""))
                except:
                    continue

            if not start_time:
                continue

            try:
                conn.execute(text("""
                    INSERT INTO gigi_shifts (caregiver_name, caregiver_phone, client_name, client_phone,
                                            start_time, status, location, pay_amount, pay_method)
                    VALUES (:caregiver_name, :caregiver_phone, :client_name, :client_phone,
                            :start_time, :status, :location, :pay_amount, :pay_method)
                """), {
                    "caregiver_name": shift_data.get("caregiver_name", ""),
                    "caregiver_phone": shift_data.get("caregiver_phone"),
                    "client_name": shift_data.get("client_name", ""),
                    "client_phone": shift_data.get("client_phone"),
                    "start_time": start_time,
                    "status": shift_data.get("status", "Scheduled"),
                    "location": shift_data.get("location"),
                    "pay_amount": shift_data.get("pay_amount"),
                    "pay_method": shift_data.get("pay_method")
                })
                sh_count += 1
            except Exception as e:
                print(f"  Error inserting shift: {e}")
        conn.commit()
    print(f"  Migrated {sh_count} shifts")

    # Migrate unavailability
    print("\n[4/4] Migrating unavailability...")
    import re
    un_count = 0
    with engine.connect() as conn:
        # Clear existing
        conn.execute(text("DELETE FROM gigi_unavailability"))

        for block_data in cache.get("unavailability", []):
            desc = block_data.get("description", "").lower()

            is_recurring = "repeats weekly" in desc
            all_day = "all day" in desc

            recurring_days = []
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                if day in desc:
                    recurring_days.append(day)

            start_date = None
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', desc)
            if date_match:
                try:
                    start_date = datetime.strptime(date_match.group(1), "%m/%d/%Y")
                except:
                    pass

            try:
                conn.execute(text("""
                    INSERT INTO gigi_unavailability (caregiver_name, reason, description,
                                                     is_recurring, recurring_days, start_date, all_day)
                    VALUES (:caregiver_name, :reason, :description,
                            :is_recurring, :recurring_days, :start_date, :all_day)
                """), {
                    "caregiver_name": block_data.get("caregiver_name", ""),
                    "reason": block_data.get("reason", "Unavailable"),
                    "description": block_data.get("description", ""),
                    "is_recurring": is_recurring,
                    "recurring_days": json.dumps(recurring_days) if recurring_days else None,
                    "start_date": start_date,
                    "all_day": all_day
                })
                un_count += 1
            except Exception as e:
                print(f"  Error inserting unavailability: {e}")
        conn.commit()
    print(f"  Migrated {un_count} unavailability blocks")

    # Log the migration
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO gigi_sync_logs (sync_type, status, caregivers_synced, clients_synced,
                                        shifts_synced, unavailability_synced, completed_at)
            VALUES ('migration', 'completed', :cg, :cl, :sh, :un, CURRENT_TIMESTAMP)
        """), {"cg": cg_count, "cl": cl_count, "sh": sh_count, "un": un_count})
        conn.commit()

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

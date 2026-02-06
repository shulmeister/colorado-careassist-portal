#!/usr/bin/env python3
"""
WellSky Cache Sync Service

Pulls clients, caregivers, and shifts from WellSky API every 2 hours
and stores them in local PostgreSQL cache for fast queries.

This eliminates 30+ second API delays in Gigi voice calls and dashboards.
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from ~/.gigi-env
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

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from services.wellsky_service import WellSkyService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path.home() / 'logs' / 'wellsky-sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://careassist:careassist2026@localhost:5432/careassist')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def record_sync_start(db, sync_type: str) -> int:
    """Record that a sync has started, return sync_id"""
    result = db.execute(
        text("""
            INSERT INTO wellsky_sync_status (sync_type, started_at, status)
            VALUES (:sync_type, :started_at, 'running')
            RETURNING id
        """),
        {"sync_type": sync_type, "started_at": datetime.now()}
    )
    db.commit()
    return result.fetchone()[0]


def record_sync_complete(db, sync_id: int, records_processed: int):
    """Record successful sync completion"""
    db.execute(
        text("""
            UPDATE wellsky_sync_status
            SET completed_at = :completed_at,
                status = 'success',
                records_processed = :records
            WHERE id = :sync_id
        """),
        {
            "sync_id": sync_id,
            "completed_at": datetime.now(),
            "records": records_processed
        }
    )
    db.commit()


def record_sync_failed(db, sync_id: int, error_message: str):
    """Record sync failure"""
    db.execute(
        text("""
            UPDATE wellsky_sync_status
            SET completed_at = :completed_at,
                status = 'failed',
                error_message = :error
            WHERE id = :sync_id
        """),
        {
            "sync_id": sync_id,
            "completed_at": datetime.now(),
            "error": error_message
        }
    )
    db.commit()


def sync_clients():
    """Sync all clients from WellSky to cache"""
    logger.info("Starting clients sync...")
    db = SessionLocal()
    sync_id = record_sync_start(db, 'clients')

    try:
        wellsky = WellSkyService()

        # Get all clients (all statuses)
        clients = wellsky.search_clients(status="all", limit=10000)
        logger.info(f"Fetched {len(clients)} clients from WellSky")

        count = 0
        for client in clients:
            # Upsert to cache
            db.execute(
                text("""
                    INSERT INTO wellsky_clients_cache (
                        wellsky_id, first_name, last_name, preferred_name,
                        email, phone, mobile_phone,
                        address_line1, address_line2, city, state, zip_code,
                        status, start_date, discharge_date,
                        birth_date, gender,
                        emergency_contact_name, emergency_contact_phone,
                        raw_data, last_synced_at, updated_at
                    ) VALUES (
                        :wellsky_id, :first_name, :last_name, :preferred_name,
                        :email, :phone, :mobile_phone,
                        :addr1, :addr2, :city, :state, :zip,
                        :status, :start_date, :discharge_date,
                        :birth_date, :gender,
                        :emerg_name, :emerg_phone,
                        :raw_data::jsonb, :now, :now
                    )
                    ON CONFLICT (wellsky_id) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        preferred_name = EXCLUDED.preferred_name,
                        email = EXCLUDED.email,
                        phone = EXCLUDED.phone,
                        mobile_phone = EXCLUDED.mobile_phone,
                        address_line1 = EXCLUDED.address_line1,
                        address_line2 = EXCLUDED.address_line2,
                        city = EXCLUDED.city,
                        state = EXCLUDED.state,
                        zip_code = EXCLUDED.zip_code,
                        status = EXCLUDED.status,
                        start_date = EXCLUDED.start_date,
                        discharge_date = EXCLUDED.discharge_date,
                        birth_date = EXCLUDED.birth_date,
                        gender = EXCLUDED.gender,
                        emergency_contact_name = EXCLUDED.emergency_contact_name,
                        emergency_contact_phone = EXCLUDED.emergency_contact_phone,
                        raw_data = EXCLUDED.raw_data,
                        last_synced_at = EXCLUDED.last_synced_at,
                        updated_at = EXCLUDED.updated_at
                """),
                {
                    "wellsky_id": client.get('id'),
                    "first_name": client.get('first_name'),
                    "last_name": client.get('last_name'),
                    "preferred_name": client.get('preferred_name'),
                    "email": client.get('email'),
                    "phone": client.get('phone'),
                    "mobile_phone": client.get('mobile_phone'),
                    "addr1": client.get('address', {}).get('line1'),
                    "addr2": client.get('address', {}).get('line2'),
                    "city": client.get('address', {}).get('city'),
                    "state": client.get('address', {}).get('state'),
                    "zip": client.get('address', {}).get('zip'),
                    "status": client.get('status'),
                    "start_date": client.get('start_date'),
                    "discharge_date": client.get('discharge_date'),
                    "birth_date": client.get('birth_date'),
                    "gender": client.get('gender'),
                    "emerg_name": client.get('emergency_contact', {}).get('name'),
                    "emerg_phone": client.get('emergency_contact', {}).get('phone'),
                    "raw_data": str(client),
                    "now": datetime.now()
                }
            )
            count += 1

        db.commit()
        record_sync_complete(db, sync_id, count)
        logger.info(f"Clients sync completed: {count} records")

    except Exception as e:
        logger.error(f"Clients sync failed: {e}", exc_info=True)
        record_sync_failed(db, sync_id, str(e))
        raise
    finally:
        db.close()


def sync_caregivers():
    """Sync all caregivers from WellSky to cache"""
    logger.info("Starting caregivers sync...")
    db = SessionLocal()
    sync_id = record_sync_start(db, 'caregivers')

    try:
        wellsky = WellSkyService()

        # Get all caregivers (all statuses)
        caregivers = wellsky.search_caregivers(status="all", limit=10000)
        logger.info(f"Fetched {len(caregivers)} caregivers from WellSky")

        count = 0
        for caregiver in caregivers:
            # Upsert to cache
            db.execute(
                text("""
                    INSERT INTO wellsky_caregivers_cache (
                        wellsky_id, first_name, last_name, preferred_name,
                        email, phone, mobile_phone,
                        address_line1, address_line2, city, state, zip_code,
                        status, hire_date, termination_date,
                        birth_date, certifications, languages,
                        raw_data, last_synced_at, updated_at
                    ) VALUES (
                        :wellsky_id, :first_name, :last_name, :preferred_name,
                        :email, :phone, :mobile_phone,
                        :addr1, :addr2, :city, :state, :zip,
                        :status, :hire_date, :term_date,
                        :birth_date, :certs, :langs,
                        :raw_data::jsonb, :now, :now
                    )
                    ON CONFLICT (wellsky_id) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        preferred_name = EXCLUDED.preferred_name,
                        email = EXCLUDED.email,
                        phone = EXCLUDED.phone,
                        mobile_phone = EXCLUDED.mobile_phone,
                        address_line1 = EXCLUDED.address_line1,
                        address_line2 = EXCLUDED.address_line2,
                        city = EXCLUDED.city,
                        state = EXCLUDED.state,
                        zip_code = EXCLUDED.zip_code,
                        status = EXCLUDED.status,
                        hire_date = EXCLUDED.hire_date,
                        termination_date = EXCLUDED.termination_date,
                        birth_date = EXCLUDED.birth_date,
                        certifications = EXCLUDED.certifications,
                        languages = EXCLUDED.languages,
                        raw_data = EXCLUDED.raw_data,
                        last_synced_at = EXCLUDED.last_synced_at,
                        updated_at = EXCLUDED.updated_at
                """),
                {
                    "wellsky_id": caregiver.get('id'),
                    "first_name": caregiver.get('first_name'),
                    "last_name": caregiver.get('last_name'),
                    "preferred_name": caregiver.get('preferred_name'),
                    "email": caregiver.get('email'),
                    "phone": caregiver.get('phone'),
                    "mobile_phone": caregiver.get('mobile_phone'),
                    "addr1": caregiver.get('address', {}).get('line1'),
                    "addr2": caregiver.get('address', {}).get('line2'),
                    "city": caregiver.get('address', {}).get('city'),
                    "state": caregiver.get('address', {}).get('state'),
                    "zip": caregiver.get('address', {}).get('zip'),
                    "status": caregiver.get('status'),
                    "hire_date": caregiver.get('hire_date'),
                    "term_date": caregiver.get('termination_date'),
                    "birth_date": caregiver.get('birth_date'),
                    "certs": caregiver.get('certifications', []),
                    "langs": caregiver.get('languages', []),
                    "raw_data": str(caregiver),
                    "now": datetime.now()
                }
            )
            count += 1

        db.commit()
        record_sync_complete(db, sync_id, count)
        logger.info(f"Caregivers sync completed: {count} records")

    except Exception as e:
        logger.error(f"Caregivers sync failed: {e}", exc_info=True)
        record_sync_failed(db, sync_id, str(e))
        raise
    finally:
        db.close()


def sync_shifts():
    """Sync recent and upcoming shifts from WellSky to cache"""
    logger.info("Starting shifts sync...")
    db = SessionLocal()
    sync_id = record_sync_start(db, 'shifts')

    try:
        wellsky = WellSkyService()

        # Get shifts from 7 days ago to 14 days ahead
        start_date = (datetime.now() - timedelta(days=7)).date()
        end_date = (datetime.now() + timedelta(days=14)).date()

        shifts = wellsky.search_shifts(
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )
        logger.info(f"Fetched {len(shifts)} shifts from WellSky")

        count = 0
        for shift in shifts:
            # Upsert to cache
            db.execute(
                text("""
                    INSERT INTO wellsky_shifts_cache (
                        wellsky_id, client_wellsky_id, caregiver_wellsky_id,
                        scheduled_start, scheduled_end,
                        actual_start, actual_end,
                        status, location_address, service_type, notes,
                        raw_data, last_synced_at, updated_at
                    ) VALUES (
                        :wellsky_id, :client_id, :caregiver_id,
                        :sched_start, :sched_end,
                        :actual_start, :actual_end,
                        :status, :location, :service_type, :notes,
                        :raw_data::jsonb, :now, :now
                    )
                    ON CONFLICT (wellsky_id) DO UPDATE SET
                        client_wellsky_id = EXCLUDED.client_wellsky_id,
                        caregiver_wellsky_id = EXCLUDED.caregiver_wellsky_id,
                        scheduled_start = EXCLUDED.scheduled_start,
                        scheduled_end = EXCLUDED.scheduled_end,
                        actual_start = EXCLUDED.actual_start,
                        actual_end = EXCLUDED.actual_end,
                        status = EXCLUDED.status,
                        location_address = EXCLUDED.location_address,
                        service_type = EXCLUDED.service_type,
                        notes = EXCLUDED.notes,
                        raw_data = EXCLUDED.raw_data,
                        last_synced_at = EXCLUDED.last_synced_at,
                        updated_at = EXCLUDED.updated_at
                """),
                {
                    "wellsky_id": shift.get('id'),
                    "client_id": shift.get('client_id'),
                    "caregiver_id": shift.get('caregiver_id'),
                    "sched_start": shift.get('scheduled_start'),
                    "sched_end": shift.get('scheduled_end'),
                    "actual_start": shift.get('actual_start'),
                    "actual_end": shift.get('actual_end'),
                    "status": shift.get('status'),
                    "location": shift.get('location_address'),
                    "service_type": shift.get('service_type'),
                    "notes": shift.get('notes'),
                    "raw_data": str(shift),
                    "now": datetime.now()
                }
            )
            count += 1

        db.commit()
        record_sync_complete(db, sync_id, count)
        logger.info(f"Shifts sync completed: {count} records")

    except Exception as e:
        logger.error(f"Shifts sync failed: {e}", exc_info=True)
        record_sync_failed(db, sync_id, str(e))
        raise
    finally:
        db.close()


def main():
    """Run all syncs"""
    import argparse

    parser = argparse.ArgumentParser(description='Sync WellSky data to local cache')
    parser.add_argument('--type', choices=['clients', 'caregivers', 'shifts', 'all'],
                        default='all', help='What to sync')
    args = parser.parse_args()

    logger.info(f"Starting WellSky sync: {args.type}")

    try:
        if args.type in ('clients', 'all'):
            sync_clients()

        if args.type in ('caregivers', 'all'):
            sync_caregivers()

        if args.type in ('shifts', 'all'):
            sync_shifts()

        logger.info("All syncs completed successfully")

    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

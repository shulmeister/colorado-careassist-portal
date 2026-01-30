#!/usr/bin/env python3
"""
WellSky Cache Sync Script

Syncs practitioner and patient data from WellSky API to local PostgreSQL cache.
Optimized for fast caller ID lookup during Gigi calls.

Run daily via cron:
    0 3 * * * cd /path/to/colorado-careassist-portal && python3 services/sync_wellsky_cache.py

Or manually:
    python3 services/sync_wellsky_cache.py [--practitioners] [--patients] [--force]
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import execute_values

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.wellsky_service import WellSkyService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WellSkyCacheSync:
    """Sync WellSky API data to local PostgreSQL cache"""

    def __init__(self, db_url: Optional[str] = None):
        self.wellsky = WellSkyService()
        self.db_url = db_url or os.getenv("DATABASE_URL")

        if not self.db_url:
            raise ValueError("DATABASE_URL not set")

        self.conn = None
        self.sync_id = None

    def connect_db(self):
        """Connect to PostgreSQL"""
        try:
            self.conn = psycopg2.connect(self.db_url)
            logger.info("Connected to PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def close_db(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Closed PostgreSQL connection")

    def start_sync_log(self, sync_type: str) -> int:
        """Create sync log entry"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO wellsky_sync_log (sync_type, status)
            VALUES (%s, 'running')
            RETURNING id
            """,
            (sync_type,)
        )
        sync_id = cursor.fetchone()[0]
        self.conn.commit()
        cursor.close()
        logger.info(f"Started sync job #{sync_id} for {sync_type}")
        return sync_id

    def complete_sync_log(self, sync_id: int, records_synced: int, records_added: int, records_updated: int, errors: Optional[str] = None):
        """Mark sync log as completed"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE wellsky_sync_log
            SET
                completed_at = NOW(),
                records_synced = %s,
                records_added = %s,
                records_updated = %s,
                errors = %s,
                status = CASE WHEN %s IS NULL THEN 'completed' ELSE 'failed' END
            WHERE id = %s
            """,
            (records_synced, records_added, records_updated, errors, errors, sync_id)
        )
        self.conn.commit()
        cursor.close()

    def sync_practitioners(self) -> Dict[str, int]:
        """Sync all practitioners (caregivers) from WellSky"""
        logger.info("Starting practitioner sync...")

        sync_id = self.start_sync_log('practitioners')
        records_synced = 0
        records_added = 0
        records_updated = 0
        errors = None

        try:
            # Fetch ALL practitioners from WellSky (paginated)
            all_practitioners = []
            page = 0
            page_size = 100

            while True:
                logger.info(f"Fetching practitioners page {page + 1}...")
                practitioners = self.wellsky.search_practitioners(
                    limit=page_size,
                    page=page
                )

                if not practitioners:
                    break

                all_practitioners.extend(practitioners)
                records_synced += len(practitioners)

                logger.info(f"Fetched {len(practitioners)} practitioners (total: {records_synced})")

                # Stop if we got less than a full page (end of results)
                if len(practitioners) < page_size:
                    break

                page += 1

            logger.info(f"Fetched {records_synced} total practitioners from WellSky")

            # Prepare data for bulk insert/update
            cursor = self.conn.cursor()

            for p in all_practitioners:
                # Clean phone numbers (last 10 digits)
                phone = self._clean_phone(p.phone)
                home_phone = self._clean_phone(p.home_phone) if hasattr(p, 'home_phone') else None
                work_phone = self._clean_phone(p.work_phone) if hasattr(p, 'work_phone') else None

                # Check if exists
                cursor.execute("SELECT id FROM cached_practitioners WHERE id = %s", (p.id,))
                exists = cursor.fetchone()

                if exists:
                    # Update existing
                    cursor.execute(
                        """
                        UPDATE cached_practitioners SET
                            first_name = %s,
                            last_name = %s,
                            full_name = %s,
                            phone = %s,
                            home_phone = %s,
                            work_phone = %s,
                            email = %s,
                            address = %s,
                            city = %s,
                            state = %s,
                            zip_code = %s,
                            status = %s,
                            is_hired = %s,
                            is_active = %s,
                            hire_date = %s,
                            skills = %s,
                            certifications = %s,
                            notes = %s,
                            external_id = %s,
                            wellsky_data = %s,
                            synced_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            p.first_name,
                            p.last_name,
                            p.full_name,
                            phone,
                            home_phone,
                            work_phone,
                            p.email,
                            p.address,
                            p.city,
                            p.state,
                            p.zip_code,
                            p.status.value if hasattr(p.status, 'value') else str(p.status),
                            p.is_hired,
                            p.is_active,
                            p.hire_date if hasattr(p, 'hire_date') else None,
                            json.dumps(p.certifications) if hasattr(p, 'certifications') else None,
                            json.dumps(p.certifications) if hasattr(p, 'certifications') else None,
                            p.notes if hasattr(p, 'notes') else None,
                            p.external_id if hasattr(p, 'external_id') else None,
                            json.dumps(p.to_dict() if hasattr(p, 'to_dict') else {}),
                            p.id
                        )
                    )
                    records_updated += 1
                else:
                    # Insert new
                    cursor.execute(
                        """
                        INSERT INTO cached_practitioners (
                            id, first_name, last_name, full_name,
                            phone, home_phone, work_phone, email,
                            address, city, state, zip_code,
                            status, is_hired, is_active, hire_date,
                            skills, certifications, notes, external_id,
                            wellsky_data, synced_at
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, NOW()
                        )
                        """,
                        (
                            p.id,
                            p.first_name,
                            p.last_name,
                            p.full_name,
                            phone,
                            home_phone,
                            work_phone,
                            p.email,
                            p.address,
                            p.city,
                            p.state,
                            p.zip_code,
                            p.status.value if hasattr(p.status, 'value') else str(p.status),
                            p.is_hired,
                            p.is_active,
                            p.hire_date if hasattr(p, 'hire_date') else None,
                            json.dumps(p.certifications) if hasattr(p, 'certifications') else None,
                            json.dumps(p.certifications) if hasattr(p, 'certifications') else None,
                            p.notes if hasattr(p, 'notes') else None,
                            p.external_id if hasattr(p, 'external_id') else None,
                            json.dumps(p.to_dict() if hasattr(p, 'to_dict') else {})
                        )
                    )
                    records_added += 1

            self.conn.commit()
            cursor.close()

            logger.info(f"✅ Practitioner sync complete: {records_synced} total, {records_added} added, {records_updated} updated")

        except Exception as e:
            logger.error(f"❌ Practitioner sync failed: {e}")
            errors = str(e)
            self.conn.rollback()

        finally:
            self.complete_sync_log(sync_id, records_synced, records_added, records_updated, errors)

        return {
            'synced': records_synced,
            'added': records_added,
            'updated': records_updated
        }

    def sync_patients(self) -> Dict[str, int]:
        """Sync all patients (clients) from WellSky"""
        logger.info("Starting patient sync...")

        sync_id = self.start_sync_log('patients')
        records_synced = 0
        records_added = 0
        records_updated = 0
        errors = None

        try:
            # Fetch ALL patients from WellSky (paginated)
            all_patients = []
            page = 0
            page_size = 100

            while True:
                logger.info(f"Fetching patients page {page + 1}...")
                patients = self.wellsky.search_patients(
                    limit=page_size,
                    page=page
                )

                if not patients:
                    break

                all_patients.extend(patients)
                records_synced += len(patients)

                logger.info(f"Fetched {len(patients)} patients (total: {records_synced})")

                # Stop if we got less than a full page
                if len(patients) < page_size:
                    break

                page += 1

            logger.info(f"Fetched {records_synced} total patients from WellSky")

            # Prepare data for bulk insert/update
            cursor = self.conn.cursor()

            for pt in all_patients:
                # Clean phone numbers
                phone = self._clean_phone(pt.phone)
                home_phone = self._clean_phone(pt.home_phone) if hasattr(pt, 'home_phone') else None
                work_phone = self._clean_phone(pt.work_phone) if hasattr(pt, 'work_phone') else None

                # Check if exists
                cursor.execute("SELECT id FROM cached_patients WHERE id = %s", (pt.id,))
                exists = cursor.fetchone()

                if exists:
                    # Update existing
                    cursor.execute(
                        """
                        UPDATE cached_patients SET
                            first_name = %s,
                            last_name = %s,
                            full_name = %s,
                            phone = %s,
                            home_phone = %s,
                            work_phone = %s,
                            email = %s,
                            address = %s,
                            city = %s,
                            state = %s,
                            zip_code = %s,
                            status = %s,
                            is_active = %s,
                            start_date = %s,
                            emergency_contact_name = %s,
                            emergency_contact_phone = %s,
                            referral_source = %s,
                            notes = %s,
                            wellsky_data = %s,
                            synced_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            pt.first_name,
                            pt.last_name,
                            pt.full_name,
                            phone,
                            home_phone,
                            work_phone,
                            pt.email,
                            pt.address,
                            pt.city,
                            pt.state,
                            pt.zip_code,
                            pt.status.value if hasattr(pt.status, 'value') else str(pt.status),
                            pt.is_active,
                            pt.start_date if hasattr(pt, 'start_date') else None,
                            pt.emergency_contact_name if hasattr(pt, 'emergency_contact_name') else None,
                            self._clean_phone(pt.emergency_contact_phone) if hasattr(pt, 'emergency_contact_phone') else None,
                            pt.referral_source if hasattr(pt, 'referral_source') else None,
                            pt.notes if hasattr(pt, 'notes') else None,
                            json.dumps(pt.to_dict() if hasattr(pt, 'to_dict') else {}),
                            pt.id
                        )
                    )
                    records_updated += 1
                else:
                    # Insert new
                    cursor.execute(
                        """
                        INSERT INTO cached_patients (
                            id, first_name, last_name, full_name,
                            phone, home_phone, work_phone, email,
                            address, city, state, zip_code,
                            status, is_active, start_date,
                            emergency_contact_name, emergency_contact_phone,
                            referral_source, notes, wellsky_data, synced_at
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s, %s, NOW()
                        )
                        """,
                        (
                            pt.id,
                            pt.first_name,
                            pt.last_name,
                            pt.full_name,
                            phone,
                            home_phone,
                            work_phone,
                            pt.email,
                            pt.address,
                            pt.city,
                            pt.state,
                            pt.zip_code,
                            pt.status.value if hasattr(pt.status, 'value') else str(pt.status),
                            pt.is_active,
                            pt.start_date if hasattr(pt, 'start_date') else None,
                            pt.emergency_contact_name if hasattr(pt, 'emergency_contact_name') else None,
                            self._clean_phone(pt.emergency_contact_phone) if hasattr(pt, 'emergency_contact_phone') else None,
                            pt.referral_source if hasattr(pt, 'referral_source') else None,
                            pt.notes if hasattr(pt, 'notes') else None,
                            json.dumps(pt.to_dict() if hasattr(pt, 'to_dict') else {})
                        )
                    )
                    records_added += 1

            self.conn.commit()
            cursor.close()

            logger.info(f"✅ Patient sync complete: {records_synced} total, {records_added} added, {records_updated} updated")

        except Exception as e:
            logger.error(f"❌ Patient sync failed: {e}")
            errors = str(e)
            self.conn.rollback()

        finally:
            self.complete_sync_log(sync_id, records_synced, records_added, records_updated, errors)

        return {
            'synced': records_synced,
            'added': records_added,
            'updated': records_updated
        }

    def _clean_phone(self, phone: Optional[str]) -> Optional[str]:
        """Clean phone number to 10 digits"""
        if not phone:
            return None

        # Remove all non-digits
        import re
        digits = re.sub(r'[^\d]', '', phone)

        # Take last 10 digits (remove country code if present)
        if len(digits) > 10:
            digits = digits[-10:]

        return digits if len(digits) == 10 else None


def main():
    parser = argparse.ArgumentParser(description='Sync WellSky data to local cache')
    parser.add_argument('--practitioners', action='store_true', help='Sync practitioners only')
    parser.add_argument('--patients', action='store_true', help='Sync patients only')
    parser.add_argument('--force', action='store_true', help='Force sync even if recently synced')
    args = parser.parse_args()

    # If no specific flags, sync both
    sync_practitioners = args.practitioners or not (args.practitioners or args.patients)
    sync_patients = args.patients or not (args.practitioners or args.patients)

    sync = WellSkyCacheSync()

    try:
        sync.connect_db()

        if sync_practitioners:
            result = sync.sync_practitioners()
            logger.info(f"Practitioners: {result['synced']} synced, {result['added']} added, {result['updated']} updated")

        if sync_patients:
            result = sync.sync_patients()
            logger.info(f"Patients: {result['synced']} synced, {result['added']} added, {result['updated']} updated")

        logger.info("✅ All sync jobs complete")

    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        sys.exit(1)

    finally:
        sync.close_db()


if __name__ == "__main__":
    main()

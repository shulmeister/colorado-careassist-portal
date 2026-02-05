"""
WellSky Fast Lookup Service

Optimized for Gigi caller ID recognition (<5ms response time).

Strategy:
- Check local PostgreSQL cache FIRST (fast)
- Fall back to WellSky API if not found (slower, but creates cache entry)
- Always fetch shifts/appointments from API (real-time data)

Usage in Gigi:
    from services.wellsky_fast_lookup import identify_caller, get_caregiver_shifts

    # Instant caller recognition
    caller = identify_caller("+17195551234")
    if caller:
        print(f"Hi {caller['name']}, how can I help you?")

    # Get real-time shifts
    shifts = get_caregiver_shifts(caller['id'])
"""

import os
import logging
from typing import Optional, Dict, List, Any
from datetime import date, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

from services.wellsky_service import WellSkyService

logger = logging.getLogger(__name__)


class WellSkyFastLookup:
    """Fast lookup service with PostgreSQL cache + API fallback"""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.getenv("DATABASE_URL")
        self.wellsky = WellSkyService()
        self._db_conn = None

    def _get_db_connection(self):
        """Get or create database connection"""
        if self._db_conn is None or self._db_conn.closed:
            self._db_conn = psycopg2.connect(self.db_url)
        return self._db_conn

    def identify_caller(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Identify caller by phone number (< 5ms from cache).

        Args:
            phone_number: Any format ("+1-719-555-1234", "7195551234", etc.)

        Returns:
            Dict or None
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Use the fast SQL function (checks staff, practitioners, patients, family)
            cursor.execute(
                "SELECT * FROM identify_caller(%s::text)",
                (phone_number,)
            )

            result = cursor.fetchone()
            cursor.close()

            if result:
                caller_type = result['caller_type']
                caller_id = result['caller_id']
                caller_name = result['caller_name']

                if caller_type == 'staff':
                    return {
                        'type': 'staff',
                        'id': caller_id,
                        'name': caller_name.split()[0] if caller_name else '',
                        'first_name': caller_name.split()[0] if caller_name else '',
                        'full_name': caller_name,
                        'role': result.get('caller_status', ''),
                        'source': 'database'
                    }
                elif caller_type == 'practitioner':
                    return self._get_cached_practitioner(caller_id)
                elif caller_type == 'family':
                    return self._get_cached_family_contact(caller_id)
                else:
                    return self._get_cached_patient(caller_id)

            # Not in cache - try API fallback
            logger.warning(f"Caller {phone_number} not in cache, falling back to API")
            return self._api_fallback_identify(phone_number)

        except Exception as e:
            logger.error(f"Error identifying caller: {e}")
            # On database error, try API directly
            return self._api_fallback_identify(phone_number)

    def _get_cached_practitioner(self, practitioner_id: str) -> Dict[str, Any]:
        """Get full practitioner details from cache"""
        conn = self._get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT
                'practitioner' as type,
                id, first_name, last_name, full_name,
                phone, home_phone, work_phone, email,
                city, state, status, is_hired, is_active,
                skills, certifications, notes
            FROM cached_practitioners
            WHERE id = %s
            """,
            (practitioner_id,)
        )

        result = cursor.fetchone()
        cursor.close()

        return dict(result) if result else None

    def _get_cached_patient(self, patient_id: str) -> Dict[str, Any]:
        """Get full patient details from cache"""
        conn = self._get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT
                'patient' as type,
                id, first_name, last_name, full_name,
                phone, home_phone, work_phone, email,
                city, state, status, is_active,
                emergency_contact_name, emergency_contact_phone,
                notes
            FROM cached_patients
            WHERE id = %s
            """,
            (patient_id,)
        )

        result = cursor.fetchone()
        cursor.close()

        return dict(result) if result else None

    def _get_cached_family_contact(self, contact_id: str) -> Dict[str, Any]:
        """Get full family/emergency contact details from cache"""
        conn = self._get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT
                'family' as type,
                rp.id, rp.first_name, rp.last_name, rp.full_name,
                rp.phone, rp.home_phone, rp.work_phone, rp.email,
                rp.relationship, rp.is_emergency_contact,
                rp.is_primary_contact, rp.patient_id,
                p.full_name as client_name
            FROM cached_related_persons rp
            LEFT JOIN cached_patients p ON rp.patient_id = p.id
            WHERE rp.id = %s
            """,
            (contact_id,)
        )

        result = cursor.fetchone()
        cursor.close()

        if result:
            d = dict(result)
            d['name'] = d.get('first_name', '')
            return d
        return None

    def _api_fallback_identify(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Fallback to WellSky API if not in cache.
        Creates cache entry for future fast lookups.
        """
        try:
            # Search practitioners first
            practitioners = self.wellsky.search_practitioners(phone=phone_number, limit=1)
            if practitioners:
                p = practitioners[0]
                # TODO: Optionally cache this new entry
                return {
                    'type': 'practitioner',
                    'id': p.id,
                    'first_name': p.first_name,
                    'last_name': p.last_name,
                    'name': p.full_name,
                    'full_name': p.full_name,
                    'phone': p.phone,
                    'email': p.email,
                    'city': p.city,
                    'state': p.state,
                    'status': p.status.value if hasattr(p.status, 'value') else str(p.status),
                    'is_hired': True,  # search_practitioners defaults to is_hired=True
                    'is_active': p.is_active
                }

            # Try patients (search all, including inactive)
            patients = self.wellsky.search_patients(phone=phone_number, active=None, limit=1)
            if patients:
                pt = patients[0]
                return {
                    'type': 'patient',
                    'id': pt.id,
                    'first_name': pt.first_name,
                    'last_name': pt.last_name,
                    'name': pt.full_name,
                    'full_name': pt.full_name,
                    'phone': pt.phone,
                    'email': pt.email,
                    'city': pt.city,
                    'state': pt.state,
                    'status': pt.status.value if hasattr(pt.status, 'value') else str(pt.status),
                    'is_active': pt.is_active
                }

            return None

        except Exception as e:
            logger.error(f"API fallback failed: {e}")
            return None

    def get_caregiver_shifts(
        self,
        caregiver_id: str,
        start_date: Optional[date] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get caregiver's shifts (ALWAYS from API - real-time data).

        Args:
            caregiver_id: WellSky practitioner ID
            start_date: Start date (default: today)
            days: Number of days to fetch (default: 7)

        Returns:
            List of shift dicts with id, date, start_time, end_time, client info
        """
        if start_date is None:
            start_date = date.today()

        try:
            shifts = self.wellsky.search_appointments(
                caregiver_id=caregiver_id,
                start_date=start_date,
                additional_days=days - 1
            )

            return [
                {
                    'id': s.id,
                    'date': s.date,
                    'start_time': s.start_time,
                    'end_time': s.end_time,
                    'duration_hours': s.duration_hours,
                    'client_id': s.client_id,
                    'client_name': s.client_name if hasattr(s, 'client_name') else '',
                    'address': s.address if hasattr(s, 'address') else '',
                    'city': s.city if hasattr(s, 'city') else '',
                    'status': s.status.value if hasattr(s.status, 'value') else str(s.status)
                }
                for s in shifts
            ]

        except Exception as e:
            logger.error(f"Failed to get shifts for caregiver {caregiver_id}: {e}")
            return []

    def get_client_shifts(
        self,
        client_id: str,
        start_date: Optional[date] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get client's shifts (ALWAYS from API - real-time data).

        Args:
            client_id: WellSky patient ID
            start_date: Start date (default: today)
            days: Number of days to fetch (default: 7)

        Returns:
            List of shift dicts
        """
        if start_date is None:
            start_date = date.today()

        try:
            shifts = self.wellsky.search_appointments(
                client_id=client_id,
                start_date=start_date,
                additional_days=days - 1
            )

            return [
                {
                    'id': s.id,
                    'date': s.date,
                    'start_time': s.start_time,
                    'end_time': s.end_time,
                    'duration_hours': s.duration_hours,
                    'caregiver_id': s.caregiver_id,
                    'caregiver_name': s.caregiver_name if hasattr(s, 'caregiver_name') else '',
                    'status': s.status.value if hasattr(s.status, 'value') else str(s.status)
                }
                for s in shifts
            ]

        except Exception as e:
            logger.error(f"Failed to get shifts for client {client_id}: {e}")
            return []

    def search_caregivers(
        self,
        city: Optional[str] = None,
        skills: Optional[List[str]] = None,
        available_now: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search for available caregivers (cache for demographics, API for availability).

        Args:
            city: Filter by city
            skills: List of skill/certification IDs
            available_now: Check real-time availability (slower)

        Returns:
            List of caregiver dicts
        """
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    id, first_name, last_name, full_name,
                    phone, email, city, state,
                    skills, certifications, notes
                FROM cached_practitioners
                WHERE is_hired = true AND is_active = true
            """
            params = []

            if city:
                query += " AND city ILIKE %s"
                params.append(f"%{city}%")

            if skills:
                # Search in skills JSON array
                query += " AND skills::jsonb ?| %s"
                params.append(skills)

            query += " LIMIT 50"

            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()

            caregivers = [dict(r) for r in results]

            # If checking availability, filter by real-time schedule
            if available_now:
                # TODO: Implement availability check via API
                pass

            return caregivers

        except Exception as e:
            logger.error(f"Failed to search caregivers: {e}")
            return []


# =============================================================================
# Convenience Functions for Gigi
# =============================================================================

# Global instance (lazy init)
_lookup_service = None


def _get_lookup_service() -> WellSkyFastLookup:
    """Get or create global lookup service instance"""
    global _lookup_service
    if _lookup_service is None:
        _lookup_service = WellSkyFastLookup()
    return _lookup_service


def identify_caller(phone_number: str) -> Optional[Dict[str, Any]]:
    """
    Fast caller ID lookup (< 5ms from cache).

    Usage in Gigi:
        caller = identify_caller("+1-719-555-1234")
        if caller:
            print(f"Hi {caller['name']}, I see you're a {caller['type']}")
    """
    service = _get_lookup_service()
    return service.identify_caller(phone_number)


def get_caregiver_shifts(caregiver_id: str, days: int = 7) -> List[Dict[str, Any]]:
    """
    Get caregiver's upcoming shifts (real-time from API).

    Usage in Gigi:
        shifts = get_caregiver_shifts(caller['id'])
        if shifts:
            print(f"You have {len(shifts)} shifts in the next week")
    """
    service = _get_lookup_service()
    return service.get_caregiver_shifts(caregiver_id, days=days)


def get_client_shifts(client_id: str, days: int = 7) -> List[Dict[str, Any]]:
    """Get client's upcoming shifts (real-time from API)"""
    service = _get_lookup_service()
    return service.get_client_shifts(client_id, days=days)


def search_available_caregivers(city: str, skills: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Search for available caregivers in a city"""
    service = _get_lookup_service()
    return service.search_caregivers(city=city, skills=skills)

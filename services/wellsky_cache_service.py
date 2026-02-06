"""
WellSky Cache Service

Provides fast local queries for WellSky data by querying PostgreSQL cache first,
falling back to live API only when necessary.

This eliminates 30+ second delays in Gigi voice calls and dashboards.
Cache is synced every 2 hours via scripts/wellsky_sync.py.
"""
import os
import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from services.wellsky_service import WellSkyService, WellSkyClient

logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://careassist:careassist2026@localhost:5432/careassist')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class WellSkyCacheService:
    """
    WellSky service with cache-first queries.

    Always queries local PostgreSQL cache first for instant results.
    Falls back to live API only if cache miss or forced refresh.
    """

    def __init__(self, use_cache: bool = True):
        self.wellsky_api = WellSkyService()
        self.use_cache = use_cache
        self.db = SessionLocal()

    def __del__(self):
        """Close database connection"""
        if hasattr(self, 'db'):
            self.db.close()

    def search_clients(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        city: Optional[str] = None,
        active: Optional[bool] = None,
        limit: int = 20,
        force_api: bool = False
    ) -> List[dict]:
        """
        Search for clients (patients).

        Queries cache first, falls back to API if cache miss or force_api=True.

        Args:
            first_name: Filter by first name (partial match)
            last_name: Filter by last name (partial match)
            phone: Filter by phone number
            city: Filter by city
            active: Filter by active status
            limit: Max results to return
            force_api: Skip cache and query API directly

        Returns:
            List of client dicts
        """
        # If cache disabled or forced API, use live API
        if not self.use_cache or force_api:
            logger.info("Querying WellSky API directly (cache bypassed)")
            clients = self.wellsky_api.search_patients(
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                city=city,
                active=active,
                limit=limit
            )
            return [self._client_to_dict(c) for c in clients]

        # Query cache
        try:
            logger.info(f"Querying WellSky client cache: name={first_name} {last_name}")

            # Build query dynamically
            conditions = []
            params = {"limit": limit}

            if first_name:
                conditions.append("LOWER(first_name) LIKE LOWER(:first_name)")
                params["first_name"] = f"{first_name}%"

            if last_name:
                conditions.append("LOWER(last_name) LIKE LOWER(:last_name)")
                params["last_name"] = f"{last_name}%"

            if phone:
                # Clean phone to compare
                import re
                clean_phone = re.sub(r'[^\d]', '', phone)[-10:]
                conditions.append("(phone LIKE :phone OR mobile_phone LIKE :phone)")
                params["phone"] = f"%{clean_phone}%"

            if city:
                conditions.append("LOWER(city) = LOWER(:city)")
                params["city"] = city

            if active is not None:
                if active:
                    conditions.append("status = 'active'")
                else:
                    conditions.append("status != 'active'")

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            query = f"""
                SELECT wellsky_id, first_name, last_name, preferred_name,
                       email, phone, mobile_phone,
                       address_line1, address_line2, city, state, zip_code,
                       status, start_date, discharge_date,
                       birth_date, gender,
                       emergency_contact_name, emergency_contact_phone,
                       last_synced_at
                FROM wellsky_clients_cache
                WHERE {where_clause}
                ORDER BY last_name, first_name
                LIMIT :limit
            """

            result = self.db.execute(text(query), params)
            rows = result.fetchall()

            if rows:
                logger.info(f"Cache hit: {len(rows)} clients found")
                clients = []
                for row in rows:
                    clients.append({
                        'id': row[0],
                        'first_name': row[1],
                        'last_name': row[2],
                        'preferred_name': row[3],
                        'email': row[4],
                        'phone': row[5],
                        'mobile_phone': row[6],
                        'address': {
                            'line1': row[7],
                            'line2': row[8],
                            'city': row[9],
                            'state': row[10],
                            'zip': row[11]
                        },
                        'status': row[12],
                        'start_date': row[13].isoformat() if row[13] else None,
                        'discharge_date': row[14].isoformat() if row[14] else None,
                        'birth_date': row[15].isoformat() if row[15] else None,
                        'gender': row[16],
                        'emergency_contact': {
                            'name': row[17],
                            'phone': row[18]
                        },
                        '_cache_synced_at': row[19].isoformat() if row[19] else None
                    })
                return clients
            else:
                logger.info("Cache miss, falling back to API")
                # Fall back to API
                clients = self.wellsky_api.search_patients(
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    city=city,
                    active=active,
                    limit=limit
                )
                return [self._client_to_dict(c) for c in clients]

        except Exception as e:
            logger.error(f"Cache query failed, falling back to API: {e}", exc_info=True)
            # Fall back to API on any cache error
            clients = self.wellsky_api.search_patients(
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                city=city,
                active=active,
                limit=limit
            )
            return [self._client_to_dict(c) for c in clients]

    def search_caregivers(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        city: Optional[str] = None,
        active: Optional[bool] = None,
        limit: int = 20,
        force_api: bool = False
    ) -> List[dict]:
        """
        Search for caregivers (practitioners).

        Queries cache first, falls back to API if cache miss or force_api=True.

        Args:
            first_name: Filter by first name (partial match)
            last_name: Filter by last name (partial match)
            phone: Filter by phone number
            city: Filter by city
            active: Filter by active status
            limit: Max results to return
            force_api: Skip cache and query API directly

        Returns:
            List of caregiver dicts
        """
        # If cache disabled or forced API, use live API
        if not self.use_cache or force_api:
            logger.info("Querying WellSky API directly (cache bypassed)")
            caregivers = self.wellsky_api.search_practitioners(
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                city=city,
                active=active,
                limit=limit
            )
            return [self._caregiver_to_dict(c) for c in caregivers]

        # Query cache
        try:
            logger.info(f"Querying WellSky caregiver cache: name={first_name} {last_name}")

            # Build query dynamically
            conditions = []
            params = {"limit": limit}

            if first_name:
                conditions.append("LOWER(first_name) LIKE LOWER(:first_name)")
                params["first_name"] = f"{first_name}%"

            if last_name:
                conditions.append("LOWER(last_name) LIKE LOWER(:last_name)")
                params["last_name"] = f"{last_name}%"

            if phone:
                # Clean phone to compare
                import re
                clean_phone = re.sub(r'[^\d]', '', phone)[-10:]
                conditions.append("(phone LIKE :phone OR mobile_phone LIKE :phone)")
                params["phone"] = f"%{clean_phone}%"

            if city:
                conditions.append("LOWER(city) = LOWER(:city)")
                params["city"] = city

            if active is not None:
                if active:
                    conditions.append("status = 'active'")
                else:
                    conditions.append("status != 'active'")

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            query = f"""
                SELECT wellsky_id, first_name, last_name, preferred_name,
                       email, phone, mobile_phone,
                       address_line1, address_line2, city, state, zip_code,
                       status, hire_date, termination_date,
                       birth_date, certifications, languages,
                       last_synced_at
                FROM wellsky_caregivers_cache
                WHERE {where_clause}
                ORDER BY last_name, first_name
                LIMIT :limit
            """

            result = self.db.execute(text(query), params)
            rows = result.fetchall()

            if rows:
                logger.info(f"Cache hit: {len(rows)} caregivers found")
                caregivers = []
                for row in rows:
                    caregivers.append({
                        'id': row[0],
                        'first_name': row[1],
                        'last_name': row[2],
                        'preferred_name': row[3],
                        'email': row[4],
                        'phone': row[5],
                        'mobile_phone': row[6],
                        'address': {
                            'line1': row[7],
                            'line2': row[8],
                            'city': row[9],
                            'state': row[10],
                            'zip': row[11]
                        },
                        'status': row[12],
                        'hire_date': row[13].isoformat() if row[13] else None,
                        'termination_date': row[14].isoformat() if row[14] else None,
                        'birth_date': row[15].isoformat() if row[15] else None,
                        'certifications': row[16] or [],
                        'languages': row[17] or [],
                        '_cache_synced_at': row[18].isoformat() if row[18] else None
                    })
                return caregivers
            else:
                logger.info("Cache miss, falling back to API")
                # Fall back to API
                caregivers = self.wellsky_api.search_practitioners(
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    city=city,
                    active=active,
                    limit=limit
                )
                return [self._caregiver_to_dict(c) for c in caregivers]

        except Exception as e:
            logger.error(f"Cache query failed, falling back to API: {e}", exc_info=True)
            # Fall back to API on any cache error
            caregivers = self.wellsky_api.search_practitioners(
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                city=city,
                active=active,
                limit=limit
            )
            return [self._caregiver_to_dict(c) for c in caregivers]

    def _client_to_dict(self, client: WellSkyClient) -> dict:
        """Convert WellSkyClient to dict"""
        return {
            'id': client.id,
            'first_name': client.first_name,
            'last_name': client.last_name,
            'preferred_name': client.preferred_name,
            'email': client.email,
            'phone': client.phone,
            'mobile_phone': client.mobile_phone,
            'address': {
                'line1': client.address_line1,
                'line2': client.address_line2,
                'city': client.city,
                'state': client.state,
                'zip': client.zip_code
            },
            'status': client.status.value if hasattr(client.status, 'value') else str(client.status),
            'birth_date': client.birth_date.isoformat() if client.birth_date else None,
            'gender': client.gender
        }

    def _caregiver_to_dict(self, caregiver) -> dict:
        """Convert caregiver object to dict"""
        # Handle different caregiver object types
        if isinstance(caregiver, dict):
            return caregiver

        return {
            'id': caregiver.id if hasattr(caregiver, 'id') else None,
            'first_name': caregiver.first_name if hasattr(caregiver, 'first_name') else None,
            'last_name': caregiver.last_name if hasattr(caregiver, 'last_name') else None,
            'preferred_name': caregiver.preferred_name if hasattr(caregiver, 'preferred_name') else None,
            'email': caregiver.email if hasattr(caregiver, 'email') else None,
            'phone': caregiver.phone if hasattr(caregiver, 'phone') else None,
            'mobile_phone': caregiver.mobile_phone if hasattr(caregiver, 'mobile_phone') else None,
            'status': caregiver.status.value if hasattr(caregiver, 'status') and hasattr(caregiver.status, 'value') else str(caregiver.status) if hasattr(caregiver, 'status') else None
        }

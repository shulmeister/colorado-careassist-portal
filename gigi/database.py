"""
Gigi Database Module

Enterprise-grade data access layer for Gigi.
Provides fast lookups for caller recognition, shift details, and availability.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from .models import Base, GigiCaregiver, GigiClient, GigiShift, GigiUnavailability, GigiSyncLog

logger = logging.getLogger(__name__)


class GigiDatabase:
    """Database manager for Gigi's enterprise data storage."""

    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialized = False

    def initialize(self):
        """Initialize database connection."""
        if self._initialized:
            return

        try:
            database_url = os.getenv("DATABASE_URL")

            if not database_url:
                logger.warning("DATABASE_URL not set, using SQLite fallback")
                database_url = "sqlite:///./gigi.db"
            else:
                # Fix PostgreSQL URL format
                if database_url.startswith("postgres://"):
                    database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
                elif database_url.startswith("postgresql://"):
                    database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

            # Create engine with connection pooling
            if database_url.startswith("sqlite"):
                self.engine = create_engine(database_url, connect_args={"check_same_thread": False})
            else:
                self.engine = create_engine(
                    database_url,
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True
                )

            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

            # Create tables if they don't exist
            Base.metadata.create_all(bind=self.engine)

            self._initialized = True
            logger.info("Gigi database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Gigi database: {e}")
            raise

    @contextmanager
    def get_session(self):
        """Get a database session with automatic cleanup."""
        if not self._initialized:
            self.initialize()

        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # =========================================================================
    # CALLER LOOKUP (instant recognition)
    # =========================================================================

    def lookup_caller(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Look up a caller by phone number.
        Returns caregiver or client info if found, None otherwise.
        """
        clean_phone = ''.join(filter(str.isdigit, phone))[-10:]

        with self.get_session() as session:
            # Check caregivers first (more common callers)
            caregiver = session.query(GigiCaregiver).filter(
                GigiCaregiver.phone == clean_phone
            ).first()

            if caregiver:
                logger.info(f"DB: Found caregiver {caregiver.name} for phone {clean_phone}")
                return {
                    "type": "caregiver",
                    **caregiver.to_dict()
                }

            # Check clients
            client = session.query(GigiClient).filter(
                GigiClient.phone == clean_phone
            ).first()

            if client:
                logger.info(f"DB: Found client {client.name} for phone {clean_phone}")
                return {
                    "type": "client",
                    **client.to_dict()
                }

        logger.info(f"DB: No match for phone {clean_phone}")
        return None

    # =========================================================================
    # SHIFT LOOKUP
    # =========================================================================

    def get_caregiver_shifts(self, caregiver_name: str, days_ahead: int = 30) -> List[Dict]:
        """Get upcoming shifts for a caregiver."""
        now = datetime.now()
        end_date = now + timedelta(days=days_ahead)

        with self.get_session() as session:
            shifts = session.query(GigiShift).filter(
                and_(
                    GigiShift.caregiver_name.ilike(f"%{caregiver_name}%"),
                    GigiShift.start_time >= now,
                    GigiShift.start_time <= end_date
                )
            ).order_by(GigiShift.start_time).all()

            return [s.to_dict() for s in shifts]

    def get_client_shifts(self, client_name: str, days_ahead: int = 30) -> List[Dict]:
        """Get upcoming shifts for a client."""
        now = datetime.now()
        end_date = now + timedelta(days=days_ahead)

        with self.get_session() as session:
            shifts = session.query(GigiShift).filter(
                and_(
                    GigiShift.client_name.ilike(f"%{client_name}%"),
                    GigiShift.start_time >= now,
                    GigiShift.start_time <= end_date
                )
            ).order_by(GigiShift.start_time).all()

            return [s.to_dict() for s in shifts]

    # =========================================================================
    # AVAILABILITY CHECKING
    # =========================================================================

    def is_caregiver_available(self, caregiver_name: str, shift_time: datetime = None) -> bool:
        """Check if a caregiver is available (not blocked by unavailability)."""
        shift_time = shift_time or datetime.now()
        shift_day = shift_time.strftime("%A").lower()

        with self.get_session() as session:
            blocks = session.query(GigiUnavailability).filter(
                GigiUnavailability.caregiver_name.ilike(f"%{caregiver_name}%")
            ).all()

            for block in blocks:
                # Check recurring blocks
                if block.is_recurring and block.recurring_days:
                    if shift_day in [d.lower() for d in block.recurring_days]:
                        logger.info(f"Caregiver {caregiver_name} unavailable on {shift_day}s (recurring)")
                        return False

                # Check date-specific blocks
                if block.start_date and block.all_day:
                    if block.start_date.date() == shift_time.date():
                        logger.info(f"Caregiver {caregiver_name} unavailable on {shift_time.date()}")
                        return False

        return True

    def get_available_caregivers(self, location: str, shift_time: datetime = None) -> List[Dict]:
        """Get caregivers available for a shift at a specific location/time."""
        shift_time = shift_time or datetime.now()

        with self.get_session() as session:
            # Get caregivers in location
            caregivers = session.query(GigiCaregiver).filter(
                and_(
                    or_(
                        GigiCaregiver.location.ilike(f"%{location}%"),
                        GigiCaregiver.city.ilike(f"%{location}%")
                    ),
                    GigiCaregiver.status == "active"
                )
            ).all()

            available = []
            for cg in caregivers:
                if self.is_caregiver_available(cg.name, shift_time):
                    available.append(cg.to_dict())

            # Prioritize SMS-enabled caregivers
            available.sort(key=lambda x: (not x.get("can_sms", False), x.get("name", "")))

            logger.info(f"Found {len(available)} available caregivers in {location}")
            return available

    # =========================================================================
    # DATA SYNC (from WellSky exports or API)
    # =========================================================================

    def sync_caregivers(self, caregivers: List[Dict]) -> int:
        """Sync caregiver data from WellSky."""
        count = 0
        with self.get_session() as session:
            for cg_data in caregivers:
                phone = cg_data.get("phone")
                if not phone or len(phone) != 10:
                    continue

                existing = session.query(GigiCaregiver).filter(
                    GigiCaregiver.phone == phone
                ).first()

                if existing:
                    # Update existing
                    for key, value in cg_data.items():
                        if hasattr(existing, key) and value is not None:
                            setattr(existing, key, value)
                else:
                    # Insert new
                    session.add(GigiCaregiver(**cg_data))

                count += 1

        logger.info(f"Synced {count} caregivers")
        return count

    def sync_clients(self, clients: List[Dict]) -> int:
        """Sync client data from WellSky."""
        count = 0
        with self.get_session() as session:
            for cl_data in clients:
                phone = cl_data.get("phone")
                if not phone or len(phone) != 10:
                    continue

                existing = session.query(GigiClient).filter(
                    GigiClient.phone == phone
                ).first()

                if existing:
                    for key, value in cl_data.items():
                        if hasattr(existing, key) and value is not None:
                            setattr(existing, key, value)
                else:
                    session.add(GigiClient(**cl_data))

                count += 1

        logger.info(f"Synced {count} clients")
        return count

    def sync_shifts(self, shifts: List[Dict]) -> int:
        """Sync shift data from WellSky. Replaces all existing shifts."""
        with self.get_session() as session:
            # Clear existing future shifts
            session.query(GigiShift).filter(
                GigiShift.start_time >= datetime.now()
            ).delete()

            count = 0
            for shift_data in shifts:
                # Parse start_time if string
                start_time = shift_data.get("start_time")
                if isinstance(start_time, str):
                    try:
                        start_time = datetime.fromisoformat(start_time.replace("Z", ""))
                    except:
                        continue

                shift = GigiShift(
                    caregiver_name=shift_data.get("caregiver_name", ""),
                    client_name=shift_data.get("client_name", ""),
                    start_time=start_time,
                    status=shift_data.get("status", "Scheduled"),
                    pay_amount=shift_data.get("pay_amount"),
                    pay_method=shift_data.get("pay_method")
                )
                session.add(shift)
                count += 1

        logger.info(f"Synced {count} shifts")
        return count

    def sync_unavailability(self, blocks: List[Dict]) -> int:
        """Sync unavailability data from WellSky."""
        import re

        with self.get_session() as session:
            # Clear and replace
            session.query(GigiUnavailability).delete()

            count = 0
            for block_data in blocks:
                desc = block_data.get("description", "").lower()

                # Parse the description
                is_recurring = "repeats weekly" in desc
                all_day = "all day" in desc

                # Extract recurring days
                recurring_days = []
                for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                    if day in desc:
                        recurring_days.append(day)

                # Extract date for one-time blocks
                start_date = None
                date_match = re.search(r'(\d{2}/\d{2}/\d{4})', desc)
                if date_match:
                    try:
                        start_date = datetime.strptime(date_match.group(1), "%m/%d/%Y")
                    except:
                        pass

                block = GigiUnavailability(
                    caregiver_name=block_data.get("caregiver_name", ""),
                    reason=block_data.get("reason", "Unavailable"),
                    description=block_data.get("description", ""),
                    is_recurring=is_recurring,
                    recurring_days=recurring_days if recurring_days else None,
                    start_date=start_date,
                    all_day=all_day
                )
                session.add(block)
                count += 1

        logger.info(f"Synced {count} unavailability blocks")
        return count

    def log_sync(self, sync_type: str, status: str, **stats) -> None:
        """Log a sync operation for audit trail."""
        with self.get_session() as session:
            log = GigiSyncLog(
                sync_type=sync_type,
                status=status,
                caregivers_synced=stats.get("caregivers", 0),
                clients_synced=stats.get("clients", 0),
                shifts_synced=stats.get("shifts", 0),
                unavailability_synced=stats.get("unavailability", 0),
                error_message=stats.get("error"),
                duration_seconds=stats.get("duration"),
                completed_at=datetime.utcnow() if status == "completed" else None
            )
            session.add(log)


# Global database instance
gigi_db = GigiDatabase()

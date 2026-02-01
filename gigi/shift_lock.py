"""
Shift Processing Lock System

Prevents race conditions between Gigi AI and human coordinators
by locking shifts while they're being processed.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager
import os

logger = logging.getLogger(__name__)

# Try to import SQLAlchemy models if available
try:
    from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    Base = declarative_base()
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    Base = None
    SQLALCHEMY_AVAILABLE = False
    logger.warning("SQLAlchemy not available - shift locks will use in-memory fallback")


@dataclass
class ShiftLockInfo:
    """Information about who has a shift locked"""
    shift_id: str
    locked_by: str  # "gigi_ai" or "coordinator:name"
    locked_at: datetime
    lock_reason: str
    auto_release_at: datetime
    is_active: bool = True


if SQLALCHEMY_AVAILABLE:
    class ShiftProcessingLock(Base):
        """
        Database table to track which shifts are currently being processed.

        When Gigi starts processing a shift (call-out, cancellation, etc.),
        she acquires a lock. Human coordinators can see this lock in the portal
        and know not to touch that shift.
        """
        __tablename__ = "shift_processing_locks"

        shift_id = Column(String, primary_key=True)
        locked_by = Column(String, nullable=False)  # "gigi_ai" or "coordinator:john_smith"
        locked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
        lock_reason = Column(String, nullable=False)  # "processing_callout", "finding_replacement", etc.
        auto_release_at = Column(DateTime, nullable=False)  # Auto-release after N minutes
        is_active = Column(Boolean, nullable=False, default=True)
        metadata_json = Column(Text, nullable=True)  # JSON with extra info


class ShiftLockManager:
    """
    Manages shift processing locks to prevent Gigi and coordinators
    from working on the same shift simultaneously.
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize lock manager.

        Args:
            database_url: PostgreSQL connection string. Defaults to DATABASE_URL env var.
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        
        # Fix for SQLAlchemy 1.4+ requiring postgresql:// instead of postgres://
        if self.database_url:
            if self.database_url.startswith("postgres://"):
                self.database_url = self.database_url.replace("postgres://", "postgresql+psycopg2://", 1)
            elif self.database_url.startswith("postgresql://"):
                self.database_url = self.database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

        self.engine = None
        self.SessionLocal = None

        # In-memory fallback if database not available
        self._in_memory_locks: Dict[str, ShiftLockInfo] = {}

        if self.database_url and SQLALCHEMY_AVAILABLE:
            try:
                self.engine = create_engine(self.database_url)
                self.SessionLocal = sessionmaker(bind=self.engine)
                # Create tables if they don't exist
                Base.metadata.create_all(self.engine)
                logger.info("ShiftLockManager initialized with database")
            except Exception as e:
                logger.error(f"Failed to initialize database for shift locks: {e}")
                logger.warning("Falling back to in-memory locks (not safe for multi-process)")
        else:
            logger.warning("ShiftLockManager using in-memory locks (development only)")

    @contextmanager
    def acquire_shift_lock(
        self,
        shift_id: str,
        locked_by: str = "gigi_ai",
        reason: str = "processing_shift",
        timeout_minutes: int = 10
    ):
        """
        Acquire exclusive lock for shift processing.

        Args:
            shift_id: The shift to lock
            locked_by: Who is locking it ("gigi_ai", "coordinator:name")
            reason: Why it's locked ("processing_callout", "finding_replacement")
            timeout_minutes: Auto-release after this many minutes

        Yields:
            ShiftLockInfo if lock acquired

        Raises:
            ShiftLockConflictError: If shift already locked by someone else

        Example:
            ```python
            lock_mgr = ShiftLockManager()
            try:
                with lock_mgr.acquire_shift_lock("shift-123", "gigi_ai", "processing_callout"):
                    # Only ONE entity can execute this block at a time
                    update_wellsky(...)
                    send_sms_blast(...)
                # Lock automatically released
            except ShiftLockConflictError as e:
                # Someone else is processing this shift
                logger.warning(f"Shift locked: {e}")
            ```
        """
        lock_acquired = False
        session = None

        try:
            # Try database lock first
            if self.SessionLocal:
                session = self.SessionLocal()

                # Check if shift is already locked
                existing_lock = session.query(ShiftProcessingLock).filter(
                    ShiftProcessingLock.shift_id == shift_id,
                    ShiftProcessingLock.is_active == True
                ).first()

                if existing_lock:
                    # Check if lock has expired
                    if datetime.utcnow() > existing_lock.auto_release_at:
                        logger.warning(f"Lock on shift {shift_id} expired, taking over")
                        existing_lock.is_active = False
                        session.commit()
                    else:
                        raise ShiftLockConflictError(
                            f"Shift {shift_id} is already being processed by {existing_lock.locked_by} "
                            f"(reason: {existing_lock.lock_reason}). "
                            f"Auto-release at {existing_lock.auto_release_at.strftime('%H:%M:%S')}."
                        )

                # Create new lock
                auto_release_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)
                new_lock = ShiftProcessingLock(
                    shift_id=shift_id,
                    locked_by=locked_by,
                    locked_at=datetime.utcnow(),
                    lock_reason=reason,
                    auto_release_at=auto_release_at,
                    is_active=True
                )
                session.add(new_lock)
                session.commit()

                lock_acquired = True
                logger.info(f"Shift lock acquired: {shift_id} by {locked_by} (expires in {timeout_minutes} min)")

                lock_info = ShiftLockInfo(
                    shift_id=shift_id,
                    locked_by=locked_by,
                    locked_at=new_lock.locked_at,
                    lock_reason=reason,
                    auto_release_at=auto_release_at
                )

                yield lock_info

            else:
                # Fallback: in-memory lock
                if shift_id in self._in_memory_locks:
                    existing = self._in_memory_locks[shift_id]
                    if datetime.utcnow() < existing.auto_release_at:
                        raise ShiftLockConflictError(
                            f"Shift {shift_id} locked by {existing.locked_by} (in-memory)"
                        )

                auto_release_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)
                lock_info = ShiftLockInfo(
                    shift_id=shift_id,
                    locked_by=locked_by,
                    locked_at=datetime.utcnow(),
                    lock_reason=reason,
                    auto_release_at=auto_release_at
                )
                self._in_memory_locks[shift_id] = lock_info
                lock_acquired = True
                logger.info(f"In-memory shift lock acquired: {shift_id}")

                yield lock_info

        finally:
            # Release lock
            if lock_acquired:
                if session:
                    try:
                        # Mark lock as inactive
                        lock = session.query(ShiftProcessingLock).filter(
                            ShiftProcessingLock.shift_id == shift_id,
                            ShiftProcessingLock.locked_by == locked_by
                        ).first()
                        if lock:
                            lock.is_active = False
                            session.commit()
                            logger.info(f"Shift lock released: {shift_id}")
                    except Exception as e:
                        logger.error(f"Error releasing lock: {e}")
                        session.rollback()
                    finally:
                        session.close()
                else:
                    # Release in-memory lock
                    if shift_id in self._in_memory_locks:
                        del self._in_memory_locks[shift_id]
                        logger.info(f"In-memory shift lock released: {shift_id}")

    def get_lock_status(self, shift_id: str) -> Optional[ShiftLockInfo]:
        """
        Check if a shift is currently locked and by whom.

        Args:
            shift_id: The shift to check

        Returns:
            ShiftLockInfo if locked, None if available

        Example:
            ```python
            lock_status = lock_mgr.get_lock_status("shift-123")
            if lock_status:
                print(f"⚠️ LOCKED by {lock_status.locked_by}")
                print(f"   Reason: {lock_status.lock_reason}")
                print(f"   Auto-release: {lock_status.auto_release_at}")
            else:
                print("✅ Available")
            ```
        """
        if self.SessionLocal:
            session = self.SessionLocal()
            try:
                lock = session.query(ShiftProcessingLock).filter(
                    ShiftProcessingLock.shift_id == shift_id,
                    ShiftProcessingLock.is_active == True
                ).first()

                if lock:
                    # Check if expired
                    if datetime.utcnow() > lock.auto_release_at:
                        lock.is_active = False
                        session.commit()
                        return None

                    return ShiftLockInfo(
                        shift_id=lock.shift_id,
                        locked_by=lock.locked_by,
                        locked_at=lock.locked_at,
                        lock_reason=lock.lock_reason,
                        auto_release_at=lock.auto_release_at,
                        is_active=True
                    )
                return None
            finally:
                session.close()
        else:
            # In-memory fallback
            lock = self._in_memory_locks.get(shift_id)
            if lock and datetime.utcnow() < lock.auto_release_at:
                return lock
            return None

    def release_expired_locks(self):
        """
        Clean up expired locks (run periodically).
        """
        if self.SessionLocal:
            session = self.SessionLocal()
            try:
                expired = session.query(ShiftProcessingLock).filter(
                    ShiftProcessingLock.is_active == True,
                    ShiftProcessingLock.auto_release_at < datetime.utcnow()
                ).all()

                for lock in expired:
                    lock.is_active = False
                    logger.warning(f"Auto-released expired lock: {lock.shift_id} (was locked by {lock.locked_by})")

                session.commit()
                if expired:
                    logger.info(f"Released {len(expired)} expired locks")
            finally:
                session.close()
        else:
            # In-memory cleanup
            now = datetime.utcnow()
            expired_keys = [
                shift_id for shift_id, lock in self._in_memory_locks.items()
                if now >= lock.auto_release_at
            ]
            for shift_id in expired_keys:
                del self._in_memory_locks[shift_id]
            if expired_keys:
                logger.info(f"Released {len(expired_keys)} expired in-memory locks")


class ShiftLockConflictError(Exception):
    """Raised when trying to acquire a lock that's already held"""
    pass


# Global instance
_shift_lock_manager: Optional[ShiftLockManager] = None


def get_shift_lock_manager() -> ShiftLockManager:
    """Get or create global shift lock manager instance"""
    global _shift_lock_manager
    if _shift_lock_manager is None:
        _shift_lock_manager = ShiftLockManager()
    return _shift_lock_manager

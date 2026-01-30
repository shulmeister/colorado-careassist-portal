"""
Database-backed locking for shift assignment race condition prevention.

Uses PostgreSQL advisory locks to ensure only one caregiver can accept a shift at a time.
"""
import logging
from contextlib import contextmanager
from typing import Optional
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_READ_COMMITTED
import os

logger = logging.getLogger(__name__)


class ShiftAssignmentLock:
    """
    PostgreSQL advisory lock for atomic shift assignment.

    Prevents race condition where two caregivers accept the same shift simultaneously.
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize with database connection.

        Args:
            database_url: PostgreSQL connection string. Defaults to DATABASE_URL env var.
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL required for shift assignment locking")

    @contextmanager
    def acquire_shift_lock(self, shift_id: str):
        """
        Acquire exclusive lock for shift assignment.

        Args:
            shift_id: The shift ID to lock

        Yields:
            True if lock acquired, raises exception otherwise

        Example:
            ```python
            lock = ShiftAssignmentLock()
            with lock.acquire_shift_lock("shift-123"):
                # Only one process can execute this block at a time
                # for this specific shift
                if shift.status == "open":
                    shift.status = "filled"
                    assign_caregiver(...)
            # Lock automatically released
            ```
        """
        conn = None
        try:
            # Connect to database
            conn = psycopg2.connect(self.database_url)
            conn.set_isolation_level(ISOLATION_LEVEL_READ_COMMITTED)
            cursor = conn.cursor()

            # Convert shift_id to integer for advisory lock
            # Use hash of shift_id to create unique integer
            lock_id = abs(hash(shift_id)) % (2**31 - 1)  # PostgreSQL advisory lock requires 32-bit int

            logger.info(f"Attempting to acquire advisory lock for shift {shift_id} (lock_id: {lock_id})")

            # Try to acquire advisory lock (pg_try_advisory_lock)
            # Returns True if acquired, False if already locked
            cursor.execute("SELECT pg_try_advisory_lock(%s)", (lock_id,))
            acquired = cursor.fetchone()[0]

            if not acquired:
                logger.warning(f"Failed to acquire lock for shift {shift_id} - another process holds it")
                raise ShiftLockConflictError(
                    f"Shift {shift_id} is currently being assigned by another process. "
                    "Please try again in a moment."
                )

            logger.info(f"Advisory lock acquired for shift {shift_id}")

            try:
                yield True
            finally:
                # Release advisory lock
                cursor.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
                logger.info(f"Advisory lock released for shift {shift_id}")

        except psycopg2.Error as e:
            logger.error(f"Database error during shift locking: {e}")
            raise ShiftLockDatabaseError(f"Database locking failed: {e}")

        finally:
            if conn:
                conn.close()


class ShiftLockConflictError(Exception):
    """Raised when shift lock cannot be acquired (already held by another process)."""
    pass


class ShiftLockDatabaseError(Exception):
    """Raised when database connection fails during locking."""
    pass


# =============================================================================
# Alternative: SQLAlchemy-based locking (if engine is using SQLAlchemy session)
# =============================================================================

def with_row_lock(session, model_class, record_id):
    """
    SQLAlchemy pessimistic locking using SELECT FOR UPDATE.

    Args:
        session: SQLAlchemy session
        model_class: The ORM model class
        record_id: Primary key of record to lock

    Returns:
        Locked record or None if not found

    Example:
        ```python
        with session.begin():
            campaign = with_row_lock(session, OutreachCampaign, campaign_id)
            if campaign and campaign.status != "filled":
                campaign.status = "filled"
                session.commit()
        ```
    """
    return (
        session.query(model_class)
        .filter(model_class.id == record_id)
        .with_for_update()  # PostgreSQL SELECT FOR UPDATE
        .first()
    )

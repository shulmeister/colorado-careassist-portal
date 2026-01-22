"""
Gigi Database Models

Enterprise-grade data storage for Gigi's contacts, shifts, and availability.
Data is stored in PostgreSQL (same database as the portal).
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class GigiCaregiver(Base):
    """Caregiver contact information for instant caller recognition."""
    __tablename__ = "gigi_caregivers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="active")
    location = Column(String(100))  # Service area: "Denver" or "Colorado Springs"
    city = Column(String(100))
    email = Column(String(255))
    can_sms = Column(Boolean, default=True)
    wellsky_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "phone": self.phone,
            "name": self.name,
            "status": self.status,
            "location": self.location,
            "city": self.city,
            "email": self.email,
            "can_sms": self.can_sms,
            "wellsky_id": self.wellsky_id
        }


class GigiClient(Base):
    """Client contact information for instant caller recognition."""
    __tablename__ = "gigi_clients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="active")
    location = Column(String(100))  # City/area
    address = Column(Text)
    primary_caregiver = Column(String(255))
    wellsky_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "phone": self.phone,
            "name": self.name,
            "status": self.status,
            "location": self.location,
            "address": self.address,
            "primary_caregiver": self.primary_caregiver,
            "wellsky_id": self.wellsky_id
        }


class GigiShift(Base):
    """Upcoming shifts for the next 30 days."""
    __tablename__ = "gigi_shifts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    caregiver_name = Column(String(255), nullable=False, index=True)
    caregiver_phone = Column(String(10))
    client_name = Column(String(255), nullable=False, index=True)
    client_phone = Column(String(10))
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime)
    status = Column(String(50), default="Scheduled")
    location = Column(String(255))
    pay_amount = Column(Float)
    pay_method = Column(String(50))
    wellsky_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "caregiver_name": self.caregiver_name,
            "caregiver_phone": self.caregiver_phone,
            "client_name": self.client_name,
            "client_phone": self.client_phone,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "location": self.location
        }


class GigiUnavailability(Base):
    """Caregiver unavailability blocks - don't ask these people to cover shifts."""
    __tablename__ = "gigi_unavailability"

    id = Column(Integer, primary_key=True, autoincrement=True)
    caregiver_name = Column(String(255), nullable=False, index=True)
    reason = Column(String(100), default="Unavailable")
    description = Column(Text)  # Natural language description of the block
    # Parsed availability data for quick lookups
    is_recurring = Column(Boolean, default=False)
    recurring_days = Column(JSON)  # e.g., ["monday", "tuesday"]
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    all_day = Column(Boolean, default=True)
    start_time = Column(String(10))  # "08:00"
    end_time = Column(String(10))    # "17:00"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "caregiver_name": self.caregiver_name,
            "reason": self.reason,
            "description": self.description,
            "is_recurring": self.is_recurring,
            "recurring_days": self.recurring_days,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "all_day": self.all_day
        }


class GigiSyncLog(Base):
    """Audit log for data syncs from WellSky."""
    __tablename__ = "gigi_sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_type = Column(String(50), nullable=False)  # "full", "caregivers", "clients", "shifts"
    status = Column(String(50), nullable=False)  # "started", "completed", "failed"
    caregivers_synced = Column(Integer, default=0)
    clients_synced = Column(Integer, default=0)
    shifts_synced = Column(Integer, default=0)
    unavailability_synced = Column(Integer, default=0)
    error_message = Column(Text)
    duration_seconds = Column(Float)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    def to_dict(self):
        return {
            "sync_type": self.sync_type,
            "status": self.status,
            "caregivers_synced": self.caregivers_synced,
            "clients_synced": self.clients_synced,
            "shifts_synced": self.shifts_synced,
            "unavailability_synced": self.unavailability_synced,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds
        }

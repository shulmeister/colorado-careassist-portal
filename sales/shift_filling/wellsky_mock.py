"""
Mock WellSky Service for POC

This provides sample data for testing the shift filling engine.
In production, this would be replaced with actual WellSky API calls.
"""

import os
import logging
from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict, Any
import random

from .models import Client, Caregiver, Shift

logger = logging.getLogger(__name__)


class WellSkyMockService:
    """
    Mock WellSky API service for proof of concept.

    Provides sample clients, caregivers, and shifts for testing.
    """

    def __init__(self):
        self._clients = self._generate_sample_clients()
        self._caregivers = self._generate_sample_caregivers()
        self._shifts = self._generate_sample_shifts()
        logger.info(f"WellSky Mock: Initialized with {len(self._clients)} clients, "
                   f"{len(self._caregivers)} caregivers, {len(self._shifts)} shifts")

    def _generate_sample_clients(self) -> Dict[str, Client]:
        """Generate sample client data"""
        clients_data = [
            {"id": "C001", "first_name": "Robert", "last_name": "Johnson",
             "address": "1234 Elm Street", "city": "Aurora", "zip_code": "80012",
             "phone": "3035551001", "difficulty_score": 2.0,
             "preferred_caregivers": ["CG003", "CG007"]},

            {"id": "C002", "first_name": "Mary", "last_name": "Smith",
             "address": "5678 Oak Avenue", "city": "Denver", "zip_code": "80220",
             "phone": "3035551002", "difficulty_score": 1.5,
             "preferred_caregivers": ["CG001"]},

            {"id": "C003", "first_name": "William", "last_name": "Davis",
             "address": "910 Pine Road", "city": "Centennial", "zip_code": "80122",
             "phone": "3035551003", "difficulty_score": 3.0},

            {"id": "C004", "first_name": "Patricia", "last_name": "Wilson",
             "address": "2468 Maple Drive", "city": "Littleton", "zip_code": "80123",
             "phone": "3035551004", "difficulty_score": 1.0,
             "preferred_caregivers": ["CG002", "CG005"]},

            {"id": "C005", "first_name": "James", "last_name": "Brown",
             "address": "1357 Cedar Lane", "city": "Lakewood", "zip_code": "80226",
             "phone": "3035551005", "difficulty_score": 2.5},

            {"id": "C006", "first_name": "Elizabeth", "last_name": "Miller",
             "address": "8642 Birch Court", "city": "Aurora", "zip_code": "80014",
             "phone": "3035551006", "difficulty_score": 1.5,
             "preferred_caregivers": ["CG004"]},

            {"id": "C007", "first_name": "Charles", "last_name": "Garcia",
             "address": "7531 Spruce Way", "city": "Denver", "zip_code": "80231",
             "phone": "3035551007", "difficulty_score": 2.0},

            {"id": "C008", "first_name": "Dorothy", "last_name": "Martinez",
             "address": "9876 Aspen Boulevard", "city": "Englewood", "zip_code": "80110",
             "phone": "3035551008", "difficulty_score": 1.0},
        ]

        clients = {}
        for data in clients_data:
            client = Client(
                id=data["id"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                address=data["address"],
                city=data["city"],
                zip_code=data.get("zip_code", ""),
                phone=data.get("phone", ""),
                difficulty_score=data.get("difficulty_score", 1.0),
                preferred_caregivers=data.get("preferred_caregivers", [])
            )
            clients[client.id] = client

        return clients

    def _generate_sample_caregivers(self) -> Dict[str, Caregiver]:
        """Generate sample caregiver data"""
        # Use real-looking phone numbers for testing (these should be your test numbers)
        caregivers_data = [
            {"id": "CG001", "first_name": "Maria", "last_name": "Garcia",
             "phone": os.getenv("TEST_CAREGIVER_PHONE_1", "+13035550101"),
             "email": "maria.garcia@example.com",
             "city": "Aurora", "lat": 39.7294, "lon": -104.8319,
             "available_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
             "current_weekly_hours": 24,
             "certifications": ["CNA", "CPR"],
             "languages": ["English", "Spanish"],
             "response_rate": 0.85, "acceptance_rate": 0.60, "reliability_score": 0.95,
             "avg_rating": 4.8, "tenure_days": 365,
             "clients_worked_with": ["C001", "C002", "C006"]},

            {"id": "CG002", "first_name": "David", "last_name": "Lee",
             "phone": os.getenv("TEST_CAREGIVER_PHONE_2", "+13035550102"),
             "email": "david.lee@example.com",
             "city": "Denver", "lat": 39.7392, "lon": -104.9903,
             "available_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
             "current_weekly_hours": 32,
             "certifications": ["HHA", "CPR", "First Aid"],
             "languages": ["English"],
             "response_rate": 0.75, "acceptance_rate": 0.50, "reliability_score": 0.92,
             "avg_rating": 4.5, "tenure_days": 180,
             "clients_worked_with": ["C002", "C004", "C007"]},

            {"id": "CG003", "first_name": "Sarah", "last_name": "Johnson",
             "phone": os.getenv("TEST_CAREGIVER_PHONE_3", "+13035550103"),
             "email": "sarah.johnson@example.com",
             "city": "Centennial", "lat": 39.5807, "lon": -104.8772,
             "available_days": ["Mon", "Wed", "Fri"],
             "current_weekly_hours": 16,
             "certifications": ["CNA"],
             "languages": ["English"],
             "response_rate": 0.90, "acceptance_rate": 0.70, "reliability_score": 0.98,
             "avg_rating": 4.9, "tenure_days": 730,
             "clients_worked_with": ["C001", "C003", "C005"]},

            {"id": "CG004", "first_name": "Michael", "last_name": "Williams",
             "phone": os.getenv("TEST_CAREGIVER_PHONE_4", "+13035550104"),
             "email": "michael.williams@example.com",
             "city": "Lakewood", "lat": 39.7047, "lon": -105.0814,
             "available_days": ["Tue", "Thu", "Sat", "Sun"],
             "current_weekly_hours": 20,
             "certifications": ["HHA", "CPR"],
             "languages": ["English"],
             "response_rate": 0.65, "acceptance_rate": 0.40, "reliability_score": 0.88,
             "avg_rating": 4.2, "tenure_days": 120,
             "clients_worked_with": ["C005", "C006"]},

            {"id": "CG005", "first_name": "Jennifer", "last_name": "Brown",
             "phone": os.getenv("TEST_CAREGIVER_PHONE_5", "+13035550105"),
             "email": "jennifer.brown@example.com",
             "city": "Littleton", "lat": 39.6133, "lon": -105.0166,
             "available_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
             "current_weekly_hours": 36,
             "certifications": ["CNA", "CPR", "Dementia Care"],
             "languages": ["English", "Vietnamese"],
             "response_rate": 0.80, "acceptance_rate": 0.55, "reliability_score": 0.94,
             "avg_rating": 4.6, "tenure_days": 400,
             "clients_worked_with": ["C004", "C008"]},

            {"id": "CG006", "first_name": "Carlos", "last_name": "Rodriguez",
             "phone": os.getenv("TEST_CAREGIVER_PHONE_6", "+13035550106"),
             "email": "carlos.rodriguez@example.com",
             "city": "Aurora", "lat": 39.7088, "lon": -104.8207,
             "available_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
             "current_weekly_hours": 28,
             "certifications": ["HHA"],
             "languages": ["English", "Spanish"],
             "response_rate": 0.70, "acceptance_rate": 0.45, "reliability_score": 0.90,
             "avg_rating": 4.3, "tenure_days": 90,
             "clients_worked_with": ["C001", "C007"]},

            {"id": "CG007", "first_name": "Emily", "last_name": "Taylor",
             "phone": os.getenv("TEST_CAREGIVER_PHONE_7", "+13035550107"),
             "email": "emily.taylor@example.com",
             "city": "Englewood", "lat": 39.6478, "lon": -104.9878,
             "available_days": ["Mon", "Wed", "Fri"],
             "current_weekly_hours": 12,
             "certifications": ["CNA", "CPR"],
             "languages": ["English"],
             "response_rate": 0.95, "acceptance_rate": 0.75, "reliability_score": 0.99,
             "avg_rating": 4.9, "tenure_days": 500,
             "clients_worked_with": ["C001", "C008"]},

            {"id": "CG008", "first_name": "Robert", "last_name": "Martinez",
             "phone": os.getenv("TEST_CAREGIVER_PHONE_8", "+13035550108"),
             "email": "robert.martinez@example.com",
             "city": "Denver", "lat": 39.7500, "lon": -105.0000,
             "available_days": ["Tue", "Thu", "Sat"],
             "current_weekly_hours": 18,
             "certifications": ["HHA", "First Aid"],
             "languages": ["English", "Spanish"],
             "response_rate": 0.60, "acceptance_rate": 0.35, "reliability_score": 0.85,
             "avg_rating": 4.0, "tenure_days": 60,
             "clients_worked_with": ["C002"]},
        ]

        caregivers = {}
        for data in caregivers_data:
            cg = Caregiver(
                id=data["id"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                phone=data["phone"],
                email=data.get("email", ""),
                city=data.get("city", ""),
                lat=data.get("lat", 0.0),
                lon=data.get("lon", 0.0),
                available_days=data.get("available_days", []),
                current_weekly_hours=data.get("current_weekly_hours", 0),
                certifications=data.get("certifications", []),
                languages=data.get("languages", ["English"]),
                response_rate=data.get("response_rate", 0.5),
                acceptance_rate=data.get("acceptance_rate", 0.3),
                reliability_score=data.get("reliability_score", 0.9),
                avg_rating=data.get("avg_rating", 4.0),
                tenure_days=data.get("tenure_days", 90),
                clients_worked_with=data.get("clients_worked_with", [])
            )
            caregivers[cg.id] = cg

        return caregivers

    def _generate_sample_shifts(self) -> Dict[str, Shift]:
        """Generate sample shift data for today and tomorrow"""
        shifts = {}
        today = date.today()
        tomorrow = today + timedelta(days=1)

        # Today's shifts
        shifts_data = [
            {"id": "S001", "client_id": "C001", "date": today,
             "start_time": time(9, 0), "end_time": time(13, 0),
             "assigned_caregiver_id": "CG001", "status": "assigned"},

            {"id": "S002", "client_id": "C002", "date": today,
             "start_time": time(14, 0), "end_time": time(18, 0),
             "assigned_caregiver_id": "CG002", "status": "assigned"},

            {"id": "S003", "client_id": "C003", "date": today,
             "start_time": time(10, 0), "end_time": time(14, 0),
             "assigned_caregiver_id": None, "status": "open"},  # Open shift!

            # Tomorrow's shifts
            {"id": "S004", "client_id": "C001", "date": tomorrow,
             "start_time": time(9, 0), "end_time": time(13, 0),
             "assigned_caregiver_id": "CG003", "status": "assigned"},

            {"id": "S005", "client_id": "C004", "date": tomorrow,
             "start_time": time(14, 0), "end_time": time(18, 0),
             "assigned_caregiver_id": "CG005", "status": "assigned"},

            {"id": "S006", "client_id": "C005", "date": tomorrow,
             "start_time": time(8, 0), "end_time": time(12, 0),
             "assigned_caregiver_id": None, "status": "open"},  # Open shift!

            {"id": "S007", "client_id": "C006", "date": tomorrow,
             "start_time": time(13, 0), "end_time": time(17, 0),
             "assigned_caregiver_id": "CG004", "status": "assigned"},
        ]

        for data in shifts_data:
            client = self._clients.get(data["client_id"])
            caregiver = self._caregivers.get(data.get("assigned_caregiver_id")) if data.get("assigned_caregiver_id") else None

            shift = Shift(
                id=data["id"],
                client_id=data["client_id"],
                client=client,
                date=data["date"],
                start_time=data["start_time"],
                end_time=data["end_time"],
                assigned_caregiver_id=data.get("assigned_caregiver_id"),
                assigned_caregiver=caregiver,
                status=data["status"],
                wellsky_shift_id=data["id"]
            )
            shifts[shift.id] = shift

        return shifts

    # ==================== API Methods ====================

    def get_client(self, client_id: str) -> Optional[Client]:
        """Get client by ID"""
        return self._clients.get(client_id)

    def get_clients(self) -> List[Client]:
        """Get all clients"""
        return list(self._clients.values())

    def get_caregiver(self, caregiver_id: str) -> Optional[Caregiver]:
        """Get caregiver by ID"""
        return self._caregivers.get(caregiver_id)

    def get_caregiver_by_phone(self, phone: str) -> Optional[Caregiver]:
        """Find caregiver by phone number (last 10 digits)"""
        import re
        clean_phone = re.sub(r'[^\d]', '', phone)[-10:]

        for cg in self._caregivers.values():
            cg_clean = re.sub(r'[^\d]', '', cg.phone)[-10:]
            if cg_clean == clean_phone:
                return cg
        return None

    def get_caregivers(self, active_only: bool = True) -> List[Caregiver]:
        """Get all caregivers"""
        caregivers = list(self._caregivers.values())
        if active_only:
            caregivers = [cg for cg in caregivers if cg.is_active]
        return caregivers

    def get_available_caregivers(self, shift_date: date, exclude_ids: List[str] = None) -> List[Caregiver]:
        """Get caregivers available on a specific date"""
        day_name = shift_date.strftime("%a")  # "Mon", "Tue", etc.
        exclude_ids = exclude_ids or []

        available = []
        for cg in self._caregivers.values():
            if not cg.is_active:
                continue
            if cg.id in exclude_ids:
                continue
            if day_name in cg.available_days:
                available.append(cg)

        return available

    def get_shift(self, shift_id: str) -> Optional[Shift]:
        """Get shift by ID"""
        return self._shifts.get(shift_id)

    def get_shifts(self, date_from: date = None, date_to: date = None,
                   status: str = None) -> List[Shift]:
        """Get shifts with optional filters"""
        shifts = list(self._shifts.values())

        if date_from:
            shifts = [s for s in shifts if s.date >= date_from]
        if date_to:
            shifts = [s for s in shifts if s.date <= date_to]
        if status:
            shifts = [s for s in shifts if s.status == status]

        return shifts

    def get_open_shifts(self) -> List[Shift]:
        """Get all open shifts"""
        return self.get_shifts(status="open")

    def assign_shift(self, shift_id: str, caregiver_id: str) -> bool:
        """Assign a caregiver to a shift"""
        shift = self._shifts.get(shift_id)
        caregiver = self._caregivers.get(caregiver_id)

        if not shift or not caregiver:
            logger.error(f"Cannot assign: shift={shift_id}, caregiver={caregiver_id}")
            return False

        shift.assigned_caregiver_id = caregiver_id
        shift.assigned_caregiver = caregiver
        shift.status = "assigned"

        logger.info(f"WellSky Mock: Assigned shift {shift_id} to {caregiver.full_name}")
        return True

    def create_calloff(self, shift_id: str, reason: str = "") -> bool:
        """Mark a shift as having a call-off"""
        shift = self._shifts.get(shift_id)
        if not shift:
            return False

        shift.original_caregiver_id = shift.assigned_caregiver_id
        shift.assigned_caregiver_id = None
        shift.assigned_caregiver = None
        shift.status = "open"
        shift.calloff_reason = reason
        shift.calloff_time = datetime.now()

        logger.info(f"WellSky Mock: Call-off recorded for shift {shift_id}")
        return True


# Singleton instance
wellsky_mock = WellSkyMockService()

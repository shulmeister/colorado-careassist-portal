"""
WellSky Personal Care Connect API Service

Provides integration with WellSky (formerly ClearCare) Personal Care platform.
This service handles:
- Client profiles and status tracking
- Caregiver profiles and availability
- Schedule/shift management
- Care plan data
- Family Room activity
- EVV (Electronic Visit Verification) data

When WELLSKY_API_KEY is not configured, falls back to mock data for development.

API Documentation: https://apidocs.clearcareonline.com/
"""
from __future__ import annotations

import os
import json
import logging
import hashlib
import time
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import requests

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

WELLSKY_API_KEY = os.getenv("WELLSKY_API_KEY")
WELLSKY_API_SECRET = os.getenv("WELLSKY_API_SECRET")
WELLSKY_AGENCY_ID = os.getenv("WELLSKY_AGENCY_ID")
WELLSKY_ENVIRONMENT = os.getenv("WELLSKY_ENVIRONMENT", "sandbox")  # sandbox or production

# API Base URLs
API_URLS = {
    "sandbox": "https://api-sandbox.clearcareonline.com/v1",
    "production": "https://api.clearcareonline.com/v1",
}


# =============================================================================
# Data Models
# =============================================================================

class ClientStatus(Enum):
    """WellSky client status values"""
    PROSPECT = "prospect"
    PENDING = "pending"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    DISCHARGED = "discharged"


class CaregiverStatus(Enum):
    """WellSky caregiver status values"""
    APPLICANT = "applicant"
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"


class ShiftStatus(Enum):
    """WellSky shift status values"""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    MISSED = "missed"
    CANCELLED = "cancelled"
    OPEN = "open"


@dataclass
class WellSkyClient:
    """Client profile from WellSky"""
    id: str
    first_name: str
    last_name: str
    status: ClientStatus = ClientStatus.ACTIVE
    address: str = ""
    city: str = ""
    state: str = "CO"
    zip_code: str = ""
    phone: str = ""
    email: str = ""
    emergency_contact_name: str = ""
    emergency_contact_phone: str = ""
    referral_source: str = ""
    payer_source: str = ""  # private_pay, medicaid, va, etc.
    start_date: Optional[date] = None
    discharge_date: Optional[date] = None
    discharge_reason: str = ""
    authorized_hours_weekly: float = 0.0
    care_plan_id: Optional[str] = None
    preferred_caregivers: List[str] = field(default_factory=list)
    notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def is_active(self) -> bool:
        return self.status == ClientStatus.ACTIVE

    @property
    def tenure_days(self) -> int:
        if not self.start_date:
            return 0
        end = self.discharge_date or date.today()
        return (end - self.start_date).days

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['status'] = self.status.value
        d['start_date'] = self.start_date.isoformat() if self.start_date else None
        d['discharge_date'] = self.discharge_date.isoformat() if self.discharge_date else None
        d['created_at'] = self.created_at.isoformat() if self.created_at else None
        d['updated_at'] = self.updated_at.isoformat() if self.updated_at else None
        return d


@dataclass
class WellSkyCaregiver:
    """Caregiver profile from WellSky"""
    id: str
    first_name: str
    last_name: str
    status: CaregiverStatus = CaregiverStatus.ACTIVE
    phone: str = ""
    email: str = ""
    address: str = ""
    city: str = ""
    state: str = "CO"
    zip_code: str = ""
    lat: float = 0.0
    lon: float = 0.0
    hire_date: Optional[date] = None
    termination_date: Optional[date] = None
    certifications: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=lambda: ["English"])
    available_days: List[str] = field(default_factory=list)
    preferred_hours_min: int = 0
    preferred_hours_max: int = 40
    current_weekly_hours: float = 0.0
    avg_rating: float = 0.0
    total_visits: int = 0
    on_time_percentage: float = 0.0
    clients_worked_with: List[str] = field(default_factory=list)
    preferred_language: str = "English"
    notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def is_active(self) -> bool:
        return self.status == CaregiverStatus.ACTIVE

    @property
    def tenure_days(self) -> int:
        if not self.hire_date:
            return 0
        end = self.termination_date or date.today()
        return (end - self.hire_date).days

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['status'] = self.status.value
        d['hire_date'] = self.hire_date.isoformat() if self.hire_date else None
        d['termination_date'] = self.termination_date.isoformat() if self.termination_date else None
        d['created_at'] = self.created_at.isoformat() if self.created_at else None
        d['updated_at'] = self.updated_at.isoformat() if self.updated_at else None
        return d


@dataclass
class WellSkyShift:
    """Shift/visit from WellSky schedule"""
    id: str
    client_id: str
    caregiver_id: Optional[str] = None
    status: ShiftStatus = ShiftStatus.SCHEDULED
    date: Optional[date] = None
    start_time: Optional[str] = None  # "09:00"
    end_time: Optional[str] = None    # "13:00"
    duration_hours: float = 0.0
    clock_in_time: Optional[datetime] = None
    clock_out_time: Optional[datetime] = None
    clock_in_lat: float = 0.0
    clock_in_lon: float = 0.0
    evv_verified: bool = False
    tasks_completed: List[str] = field(default_factory=list)
    notes: str = ""
    caregiver_notes: str = ""
    client_first_name: str = ""
    client_last_name: str = ""
    caregiver_first_name: str = ""
    caregiver_last_name: str = ""
    address: str = ""
    city: str = ""

    @property
    def is_open(self) -> bool:
        return self.status == ShiftStatus.OPEN or self.caregiver_id is None

    @property
    def client_name(self) -> str:
        return f"{self.client_first_name} {self.client_last_name}"

    @property
    def caregiver_name(self) -> str:
        if self.caregiver_first_name:
            return f"{self.caregiver_first_name} {self.caregiver_last_name}"
        return "Unassigned"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['status'] = self.status.value
        d['date'] = self.date.isoformat() if self.date else None
        d['clock_in_time'] = self.clock_in_time.isoformat() if self.clock_in_time else None
        d['clock_out_time'] = self.clock_out_time.isoformat() if self.clock_out_time else None
        return d


@dataclass
class WellSkyCarePlan:
    """Care plan from WellSky"""
    id: str
    client_id: str
    status: str = "active"  # active, pending_review, expired
    created_date: Optional[date] = None
    effective_date: Optional[date] = None
    review_date: Optional[date] = None
    authorized_services: List[str] = field(default_factory=list)
    authorized_hours_weekly: float = 0.0
    diagnosis_codes: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    notes: str = ""

    @property
    def is_due_for_review(self) -> bool:
        if not self.review_date:
            return False
        return self.review_date <= date.today() + timedelta(days=30)

    @property
    def days_until_review(self) -> int:
        if not self.review_date:
            return 999
        return (self.review_date - date.today()).days

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['created_date'] = self.created_date.isoformat() if self.created_date else None
        d['effective_date'] = self.effective_date.isoformat() if self.effective_date else None
        d['review_date'] = self.review_date.isoformat() if self.review_date else None
        return d


@dataclass
class WellSkyFamilyActivity:
    """Family Room portal activity from WellSky"""
    client_id: str
    last_login: Optional[datetime] = None
    login_count_30d: int = 0
    messages_sent_30d: int = 0
    shift_notes_viewed_30d: int = 0
    payments_made_30d: int = 0
    last_payment_date: Optional[date] = None
    engagement_score: float = 0.0  # 0-100

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['last_login'] = self.last_login.isoformat() if self.last_login else None
        d['last_payment_date'] = self.last_payment_date.isoformat() if self.last_payment_date else None
        return d


# =============================================================================
# WellSky API Service
# =============================================================================

class WellSkyService:
    """
    WellSky Personal Care Connect API integration service.

    Handles authentication, API calls, and data transformation.
    Falls back to mock data when API credentials are not configured.
    """

    def __init__(self):
        self.api_key = WELLSKY_API_KEY
        self.api_secret = WELLSKY_API_SECRET
        self.agency_id = WELLSKY_AGENCY_ID
        self.environment = WELLSKY_ENVIRONMENT
        self.base_url = API_URLS.get(self.environment, API_URLS["sandbox"])

        self._access_token = None
        self._token_expires_at = None

        # Mock data cache (used when no API key)
        self._mock_clients: Dict[str, WellSkyClient] = {}
        self._mock_caregivers: Dict[str, WellSkyCaregiver] = {}
        self._mock_shifts: Dict[str, WellSkyShift] = {}
        self._mock_care_plans: Dict[str, WellSkyCarePlan] = {}
        self._mock_family_activity: Dict[str, WellSkyFamilyActivity] = {}

        if self.is_configured:
            logger.info(f"WellSky service initialized in {self.environment} mode")
        else:
            logger.info("WellSky service initialized in MOCK mode (no API key)")
            self._initialize_mock_data()

    @property
    def is_configured(self) -> bool:
        """Check if API credentials are configured"""
        return bool(self.api_key and self.api_secret and self.agency_id)

    @property
    def is_mock_mode(self) -> bool:
        """Check if running in mock mode"""
        return not self.is_configured

    # =========================================================================
    # Authentication
    # =========================================================================

    def _get_access_token(self) -> Optional[str]:
        """Get or refresh OAuth access token"""
        if not self.is_configured:
            return None

        # Return cached token if still valid
        if self._access_token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                return self._access_token

        try:
            # OAuth 2.0 client credentials flow
            auth_url = f"{self.base_url}/oauth/token"

            response = requests.post(
                auth_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.api_key,
                    "client_secret": self.api_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                self._access_token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                logger.info("WellSky access token refreshed")
                return self._access_token
            else:
                logger.error(f"WellSky auth failed: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"WellSky auth error: {e}")
            return None

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        data: Dict = None
    ) -> Tuple[bool, Any]:
        """
        Make authenticated API request to WellSky.

        Returns:
            Tuple of (success: bool, data: Any)
        """
        if not self.is_configured:
            logger.warning(f"WellSky API not configured, cannot call {endpoint}")
            return False, {"error": "API not configured"}

        token = self._get_access_token()
        if not token:
            return False, {"error": "Authentication failed"}

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Agency-ID": self.agency_id,
        }

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                return False, {"error": f"Unsupported method: {method}"}

            if response.status_code in (200, 201):
                return True, response.json()
            elif response.status_code == 204:
                return True, {}
            else:
                logger.error(f"WellSky API error: {response.status_code} - {response.text}")
                return False, {"error": response.text, "status_code": response.status_code}

        except requests.exceptions.Timeout:
            logger.error(f"WellSky API timeout: {endpoint}")
            return False, {"error": "Request timeout"}
        except Exception as e:
            logger.error(f"WellSky API error: {e}")
            return False, {"error": str(e)}

    # =========================================================================
    # Client Methods
    # =========================================================================

    def get_clients(
        self,
        status: Optional[ClientStatus] = None,
        modified_since: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[WellSkyClient]:
        """
        Get clients from WellSky.

        Args:
            status: Filter by client status
            modified_since: Only return clients modified after this time
            limit: Max number of results
            offset: Pagination offset

        Returns:
            List of WellSkyClient objects
        """
        if self.is_mock_mode:
            clients = list(self._mock_clients.values())
            if status:
                clients = [c for c in clients if c.status == status]
            return clients[offset:offset + limit]

        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status.value
        if modified_since:
            params["modified_since"] = modified_since.isoformat()

        success, data = self._make_request("GET", "/clients", params=params)

        if success and "clients" in data:
            return [self._parse_client(c) for c in data["clients"]]
        return []

    def get_client(self, client_id: str) -> Optional[WellSkyClient]:
        """Get a single client by ID"""
        if self.is_mock_mode:
            return self._mock_clients.get(client_id)

        success, data = self._make_request("GET", f"/clients/{client_id}")

        if success:
            return self._parse_client(data)
        return None

    def get_active_client_count(self) -> int:
        """Get count of active clients"""
        if self.is_mock_mode:
            return len([c for c in self._mock_clients.values() if c.is_active])

        clients = self.get_clients(status=ClientStatus.ACTIVE, limit=1000)
        return len(clients)

    def get_clients_by_status_change(
        self,
        from_status: ClientStatus,
        to_status: ClientStatus,
        since: date
    ) -> List[WellSkyClient]:
        """Get clients who changed status (for lifecycle automation)"""
        if self.is_mock_mode:
            # In mock mode, return sample data
            return [c for c in self._mock_clients.values()
                   if c.status == to_status and c.updated_at
                   and c.updated_at.date() >= since]

        params = {
            "from_status": from_status.value,
            "to_status": to_status.value,
            "since": since.isoformat()
        }
        success, data = self._make_request("GET", "/clients/status-changes", params=params)

        if success and "clients" in data:
            return [self._parse_client(c) for c in data["clients"]]
        return []

    def create_client(self, client_data: Dict[str, Any]) -> Optional[WellSkyClient]:
        """Create a new client in WellSky"""
        if self.is_mock_mode:
            client_id = f"C{len(self._mock_clients) + 1:03d}"
            client = WellSkyClient(
                id=client_id,
                first_name=client_data.get("first_name", ""),
                last_name=client_data.get("last_name", ""),
                status=ClientStatus.PENDING,
                **{k: v for k, v in client_data.items()
                   if k not in ("first_name", "last_name", "status")}
            )
            client.created_at = datetime.utcnow()
            self._mock_clients[client_id] = client
            logger.info(f"Mock: Created client {client_id}")
            return client

        success, data = self._make_request("POST", "/clients", data=client_data)

        if success:
            return self._parse_client(data)
        return None

    def _parse_client(self, data: Dict) -> WellSkyClient:
        """Parse API response into WellSkyClient object"""
        return WellSkyClient(
            id=str(data.get("id", "")),
            first_name=data.get("first_name", data.get("firstName", "")),
            last_name=data.get("last_name", data.get("lastName", "")),
            status=ClientStatus(data.get("status", "active")),
            address=data.get("address", {}).get("street", "") if isinstance(data.get("address"), dict) else data.get("address", ""),
            city=data.get("address", {}).get("city", "") if isinstance(data.get("address"), dict) else data.get("city", ""),
            state=data.get("address", {}).get("state", "CO") if isinstance(data.get("address"), dict) else data.get("state", "CO"),
            zip_code=data.get("address", {}).get("zip", "") if isinstance(data.get("address"), dict) else data.get("zip_code", ""),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            referral_source=data.get("referral_source", data.get("referralSource", "")),
            payer_source=data.get("payer_source", data.get("payerSource", "")),
            start_date=self._parse_date(data.get("start_date", data.get("startDate"))),
            discharge_date=self._parse_date(data.get("discharge_date", data.get("dischargeDate"))),
            authorized_hours_weekly=float(data.get("authorized_hours_weekly", data.get("authorizedHoursWeekly", 0))),
            notes=data.get("notes", ""),
            created_at=self._parse_datetime(data.get("created_at", data.get("createdAt"))),
            updated_at=self._parse_datetime(data.get("updated_at", data.get("updatedAt"))),
        )

    # =========================================================================
    # Caregiver Methods
    # =========================================================================

    def get_caregivers(
        self,
        status: Optional[CaregiverStatus] = None,
        available_on: Optional[date] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[WellSkyCaregiver]:
        """Get caregivers from WellSky"""
        if self.is_mock_mode:
            caregivers = list(self._mock_caregivers.values())
            if status:
                caregivers = [c for c in caregivers if c.status == status]
            if available_on:
                day_name = available_on.strftime("%a")
                caregivers = [c for c in caregivers if day_name in c.available_days]
            return caregivers[offset:offset + limit]

        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status.value
        if available_on:
            params["available_on"] = available_on.isoformat()

        success, data = self._make_request("GET", "/caregivers", params=params)

        if success and "caregivers" in data:
            return [self._parse_caregiver(c) for c in data["caregivers"]]
        return []

    def get_caregiver(self, caregiver_id: str) -> Optional[WellSkyCaregiver]:
        """Get a single caregiver by ID"""
        if self.is_mock_mode:
            return self._mock_caregivers.get(caregiver_id)

        success, data = self._make_request("GET", f"/caregivers/{caregiver_id}")

        if success:
            return self._parse_caregiver(data)
        return None

    def get_caregiver_by_phone(self, phone: str) -> Optional[WellSkyCaregiver]:
        """Find caregiver by phone number"""
        import re
        clean_phone = re.sub(r'[^\d]', '', phone)[-10:]

        if self.is_mock_mode:
            for cg in self._mock_caregivers.values():
                cg_clean = re.sub(r'[^\d]', '', cg.phone)[-10:]
                if cg_clean == clean_phone:
                    return cg
            return None

        success, data = self._make_request("GET", "/caregivers", params={"phone": clean_phone})

        if success and data.get("caregivers"):
            return self._parse_caregiver(data["caregivers"][0])
        return None

    def get_active_caregiver_count(self) -> int:
        """Get count of active caregivers"""
        if self.is_mock_mode:
            return len([c for c in self._mock_caregivers.values() if c.is_active])

        caregivers = self.get_caregivers(status=CaregiverStatus.ACTIVE, limit=1000)
        return len(caregivers)

    def create_caregiver(self, caregiver_data: Dict[str, Any]) -> Optional[WellSkyCaregiver]:
        """Create a new caregiver in WellSky"""
        if self.is_mock_mode:
            cg_id = f"CG{len(self._mock_caregivers) + 1:03d}"
            caregiver = WellSkyCaregiver(
                id=cg_id,
                first_name=caregiver_data.get("first_name", ""),
                last_name=caregiver_data.get("last_name", ""),
                status=CaregiverStatus.PENDING,
                **{k: v for k, v in caregiver_data.items()
                   if k not in ("first_name", "last_name", "status")}
            )
            caregiver.created_at = datetime.utcnow()
            self._mock_caregivers[cg_id] = caregiver
            logger.info(f"Mock: Created caregiver {cg_id}")
            return caregiver

        success, data = self._make_request("POST", "/caregivers", data=caregiver_data)

        if success:
            return self._parse_caregiver(data)
        return None

    def _parse_caregiver(self, data: Dict) -> WellSkyCaregiver:
        """Parse API response into WellSkyCaregiver object"""
        return WellSkyCaregiver(
            id=str(data.get("id", "")),
            first_name=data.get("first_name", data.get("firstName", "")),
            last_name=data.get("last_name", data.get("lastName", "")),
            status=CaregiverStatus(data.get("status", "active")),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            city=data.get("city", ""),
            state=data.get("state", "CO"),
            hire_date=self._parse_date(data.get("hire_date", data.get("hireDate"))),
            certifications=data.get("certifications", []),
            languages=data.get("languages", ["English"]),
            available_days=data.get("available_days", data.get("availableDays", [])),
            current_weekly_hours=float(data.get("current_weekly_hours", data.get("currentWeeklyHours", 0))),
            avg_rating=float(data.get("avg_rating", data.get("avgRating", 0))),
            total_visits=int(data.get("total_visits", data.get("totalVisits", 0))),
            on_time_percentage=float(data.get("on_time_percentage", data.get("onTimePercentage", 0))),
            preferred_language=data.get("preferred_language", data.get("preferredLanguage", "English")),
            created_at=self._parse_datetime(data.get("created_at", data.get("createdAt"))),
            updated_at=self._parse_datetime(data.get("updated_at", data.get("updatedAt"))),
        )

    # =========================================================================
    # Schedule/Shift Methods
    # =========================================================================

    def get_shifts(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        client_id: Optional[str] = None,
        caregiver_id: Optional[str] = None,
        status: Optional[ShiftStatus] = None,
        limit: int = 100
    ) -> List[WellSkyShift]:
        """Get shifts/visits from WellSky schedule"""
        if self.is_mock_mode:
            shifts = list(self._mock_shifts.values())
            if date_from:
                shifts = [s for s in shifts if s.date and s.date >= date_from]
            if date_to:
                shifts = [s for s in shifts if s.date and s.date <= date_to]
            if client_id:
                shifts = [s for s in shifts if s.client_id == client_id]
            if caregiver_id:
                shifts = [s for s in shifts if s.caregiver_id == caregiver_id]
            if status:
                shifts = [s for s in shifts if s.status == status]
            return shifts[:limit]

        params = {"limit": limit}
        if date_from:
            params["date_from"] = date_from.isoformat()
        if date_to:
            params["date_to"] = date_to.isoformat()
        if client_id:
            params["client_id"] = client_id
        if caregiver_id:
            params["caregiver_id"] = caregiver_id
        if status:
            params["status"] = status.value

        success, data = self._make_request("GET", "/shifts", params=params)

        if success and "shifts" in data:
            return [self._parse_shift(s) for s in data["shifts"]]
        return []

    def get_open_shifts(self, date_from: date = None, date_to: date = None) -> List[WellSkyShift]:
        """Get open (unfilled) shifts"""
        date_from = date_from or date.today()
        date_to = date_to or date.today() + timedelta(days=7)
        return self.get_shifts(date_from=date_from, date_to=date_to, status=ShiftStatus.OPEN)

    def get_shifts_for_client(self, client_id: str, days: int = 30) -> List[WellSkyShift]:
        """Get recent shifts for a specific client"""
        date_from = date.today() - timedelta(days=days)
        return self.get_shifts(client_id=client_id, date_from=date_from)

    def assign_shift(self, shift_id: str, caregiver_id: str) -> bool:
        """Assign a caregiver to a shift"""
        if self.is_mock_mode:
            shift = self._mock_shifts.get(shift_id)
            caregiver = self._mock_caregivers.get(caregiver_id)
            if shift and caregiver:
                shift.caregiver_id = caregiver_id
                shift.caregiver_first_name = caregiver.first_name
                shift.caregiver_last_name = caregiver.last_name
                shift.status = ShiftStatus.SCHEDULED
                logger.info(f"Mock: Assigned shift {shift_id} to {caregiver.full_name}")
                return True
            return False

        success, _ = self._make_request(
            "PUT",
            f"/shifts/{shift_id}/assign",
            data={"caregiver_id": caregiver_id}
        )
        return success

    def _parse_shift(self, data: Dict) -> WellSkyShift:
        """Parse API response into WellSkyShift object"""
        return WellSkyShift(
            id=str(data.get("id", "")),
            client_id=str(data.get("client_id", data.get("clientId", ""))),
            caregiver_id=str(data.get("caregiver_id", data.get("caregiverId", ""))) or None,
            status=ShiftStatus(data.get("status", "scheduled")),
            date=self._parse_date(data.get("date")),
            start_time=data.get("start_time", data.get("startTime", "")),
            end_time=data.get("end_time", data.get("endTime", "")),
            duration_hours=float(data.get("duration_hours", data.get("durationHours", 0))),
            clock_in_time=self._parse_datetime(data.get("clock_in_time", data.get("clockInTime"))),
            clock_out_time=self._parse_datetime(data.get("clock_out_time", data.get("clockOutTime"))),
            evv_verified=data.get("evv_verified", data.get("evvVerified", False)),
            tasks_completed=data.get("tasks_completed", data.get("tasksCompleted", [])),
            notes=data.get("notes", ""),
            caregiver_notes=data.get("caregiver_notes", data.get("caregiverNotes", "")),
            client_first_name=data.get("client", {}).get("first_name", "") if isinstance(data.get("client"), dict) else "",
            client_last_name=data.get("client", {}).get("last_name", "") if isinstance(data.get("client"), dict) else "",
            address=data.get("address", ""),
            city=data.get("city", ""),
        )

    # =========================================================================
    # Care Plan Methods
    # =========================================================================

    def get_care_plan(self, client_id: str) -> Optional[WellSkyCarePlan]:
        """Get care plan for a client"""
        if self.is_mock_mode:
            return self._mock_care_plans.get(client_id)

        success, data = self._make_request("GET", f"/clients/{client_id}/care-plan")

        if success:
            return self._parse_care_plan(data)
        return None

    def get_care_plans_due_for_review(self, days_ahead: int = 30) -> List[WellSkyCarePlan]:
        """Get care plans due for review within N days"""
        if self.is_mock_mode:
            cutoff = date.today() + timedelta(days=days_ahead)
            return [cp for cp in self._mock_care_plans.values()
                   if cp.review_date and cp.review_date <= cutoff]

        success, data = self._make_request(
            "GET",
            "/care-plans/due-for-review",
            params={"days_ahead": days_ahead}
        )

        if success and "care_plans" in data:
            return [self._parse_care_plan(cp) for cp in data["care_plans"]]
        return []

    def _parse_care_plan(self, data: Dict) -> WellSkyCarePlan:
        """Parse API response into WellSkyCarePlan object"""
        return WellSkyCarePlan(
            id=str(data.get("id", "")),
            client_id=str(data.get("client_id", data.get("clientId", ""))),
            status=data.get("status", "active"),
            created_date=self._parse_date(data.get("created_date", data.get("createdDate"))),
            effective_date=self._parse_date(data.get("effective_date", data.get("effectiveDate"))),
            review_date=self._parse_date(data.get("review_date", data.get("reviewDate"))),
            authorized_services=data.get("authorized_services", data.get("authorizedServices", [])),
            authorized_hours_weekly=float(data.get("authorized_hours_weekly", data.get("authorizedHoursWeekly", 0))),
            goals=data.get("goals", []),
            notes=data.get("notes", ""),
        )

    # =========================================================================
    # Family Room / Engagement Methods
    # =========================================================================

    def get_family_activity(self, client_id: str) -> Optional[WellSkyFamilyActivity]:
        """Get Family Room portal activity for a client"""
        if self.is_mock_mode:
            return self._mock_family_activity.get(client_id)

        success, data = self._make_request("GET", f"/clients/{client_id}/family-activity")

        if success:
            return WellSkyFamilyActivity(
                client_id=client_id,
                last_login=self._parse_datetime(data.get("last_login")),
                login_count_30d=int(data.get("login_count_30d", 0)),
                messages_sent_30d=int(data.get("messages_sent_30d", 0)),
                shift_notes_viewed_30d=int(data.get("shift_notes_viewed_30d", 0)),
                payments_made_30d=int(data.get("payments_made_30d", 0)),
                last_payment_date=self._parse_date(data.get("last_payment_date")),
                engagement_score=float(data.get("engagement_score", 0)),
            )
        return None

    def get_low_engagement_clients(self, threshold: float = 30.0) -> List[Tuple[WellSkyClient, WellSkyFamilyActivity]]:
        """Get clients with low family portal engagement (potential satisfaction risk)"""
        results = []

        if self.is_mock_mode:
            for client_id, activity in self._mock_family_activity.items():
                if activity.engagement_score < threshold:
                    client = self._mock_clients.get(client_id)
                    if client and client.is_active:
                        results.append((client, activity))
            return results

        # In production, would call a specific endpoint
        clients = self.get_clients(status=ClientStatus.ACTIVE)
        for client in clients:
            activity = self.get_family_activity(client.id)
            if activity and activity.engagement_score < threshold:
                results.append((client, activity))

        return results

    # =========================================================================
    # Analytics / Dashboard Methods (for Client Satisfaction)
    # =========================================================================

    def get_operations_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Get operational summary for client satisfaction dashboard.

        Returns metrics that inform satisfaction tracking:
        - Active clients/caregivers
        - Hours delivered
        - EVV compliance
        - Open shifts
        - Care plan status
        """
        if self.is_mock_mode:
            active_clients = len([c for c in self._mock_clients.values() if c.is_active])
            active_caregivers = len([c for c in self._mock_caregivers.values() if c.is_active])

            # Calculate mock metrics
            recent_shifts = [s for s in self._mock_shifts.values()
                           if s.date and s.date >= date.today() - timedelta(days=days)]
            completed_shifts = [s for s in recent_shifts if s.status == ShiftStatus.COMPLETED]
            evv_verified = [s for s in completed_shifts if s.evv_verified]
            open_shifts = [s for s in self._mock_shifts.values() if s.is_open]

            return {
                "period_days": days,
                "clients": {
                    "active": active_clients,
                    "new_this_period": 2,  # Mock
                    "churned_this_period": 1,  # Mock
                },
                "caregivers": {
                    "active": active_caregivers,
                    "avg_rating": 4.5,  # Mock
                },
                "shifts": {
                    "total_scheduled": len(recent_shifts),
                    "completed": len(completed_shifts),
                    "open": len(open_shifts),
                },
                "hours": {
                    "delivered": sum(s.duration_hours for s in completed_shifts),
                    "authorized_weekly": sum(c.authorized_hours_weekly for c in self._mock_clients.values() if c.is_active),
                },
                "compliance": {
                    "evv_rate": len(evv_verified) / len(completed_shifts) * 100 if completed_shifts else 0,
                },
                "care_plans": {
                    "due_for_review": len([cp for cp in self._mock_care_plans.values() if cp.is_due_for_review]),
                },
                "generated_at": datetime.utcnow().isoformat(),
                "data_source": "mock",
            }

        # Real API implementation would aggregate from multiple endpoints
        clients = self.get_clients(status=ClientStatus.ACTIVE)
        caregivers = self.get_caregivers(status=CaregiverStatus.ACTIVE)
        shifts = self.get_shifts(
            date_from=date.today() - timedelta(days=days),
            date_to=date.today()
        )
        open_shifts = self.get_open_shifts()
        care_plans_due = self.get_care_plans_due_for_review()

        completed = [s for s in shifts if s.status == ShiftStatus.COMPLETED]
        evv_verified = [s for s in completed if s.evv_verified]

        return {
            "period_days": days,
            "clients": {
                "active": len(clients),
                "new_this_period": len([c for c in clients if c.start_date and c.start_date >= date.today() - timedelta(days=days)]),
                "churned_this_period": 0,  # Would need status change tracking
            },
            "caregivers": {
                "active": len(caregivers),
                "avg_rating": sum(c.avg_rating for c in caregivers) / len(caregivers) if caregivers else 0,
            },
            "shifts": {
                "total_scheduled": len(shifts),
                "completed": len(completed),
                "open": len(open_shifts),
            },
            "hours": {
                "delivered": sum(s.duration_hours for s in completed),
                "authorized_weekly": sum(c.authorized_hours_weekly for c in clients),
            },
            "compliance": {
                "evv_rate": len(evv_verified) / len(completed) * 100 if completed else 0,
            },
            "care_plans": {
                "due_for_review": len(care_plans_due),
            },
            "generated_at": datetime.utcnow().isoformat(),
            "data_source": "wellsky_api",
        }

    def get_client_satisfaction_indicators(self, client_id: str) -> Dict[str, Any]:
        """
        Get satisfaction risk indicators for a specific client.

        Returns signals that may indicate satisfaction issues:
        - Declining hours
        - Caregiver changes
        - Missed visits
        - Family portal engagement
        - Care plan currency
        """
        client = self.get_client(client_id)
        if not client:
            return {"error": "Client not found"}

        shifts = self.get_shifts_for_client(client_id, days=90)
        care_plan = self.get_care_plan(client_id)
        family_activity = self.get_family_activity(client_id)

        # Calculate indicators
        recent_30 = [s for s in shifts if s.date and s.date >= date.today() - timedelta(days=30)]
        previous_30 = [s for s in shifts if s.date and
                      date.today() - timedelta(days=60) <= s.date < date.today() - timedelta(days=30)]

        hours_recent = sum(s.duration_hours for s in recent_30 if s.status == ShiftStatus.COMPLETED)
        hours_previous = sum(s.duration_hours for s in previous_30 if s.status == ShiftStatus.COMPLETED)

        missed_visits = len([s for s in recent_30 if s.status == ShiftStatus.MISSED])

        # Unique caregivers in last 30 days
        caregiver_ids = set(s.caregiver_id for s in recent_30 if s.caregiver_id)

        # Calculate risk score
        risk_score = 0
        risk_factors = []

        # Declining hours
        if hours_previous > 0 and hours_recent < hours_previous * 0.8:
            risk_score += 25
            risk_factors.append("Hours declined >20% vs previous period")

        # High caregiver turnover
        if len(caregiver_ids) > 3:
            risk_score += 20
            risk_factors.append(f"{len(caregiver_ids)} different caregivers in 30 days")

        # Missed visits
        if missed_visits > 0:
            risk_score += missed_visits * 10
            risk_factors.append(f"{missed_visits} missed visits in 30 days")

        # Low family engagement
        if family_activity and family_activity.engagement_score < 30:
            risk_score += 15
            risk_factors.append("Low family portal engagement")
        elif family_activity and family_activity.login_count_30d == 0:
            risk_score += 20
            risk_factors.append("No family portal activity in 30 days")

        # Care plan overdue
        if care_plan and care_plan.is_due_for_review:
            risk_score += 10
            risk_factors.append(f"Care plan review overdue ({care_plan.days_until_review} days)")

        return {
            "client_id": client_id,
            "client_name": client.full_name,
            "risk_score": min(risk_score, 100),
            "risk_level": "high" if risk_score >= 60 else "medium" if risk_score >= 30 else "low",
            "risk_factors": risk_factors,
            "metrics": {
                "hours_recent_30d": hours_recent,
                "hours_previous_30d": hours_previous,
                "hours_change_pct": ((hours_recent - hours_previous) / hours_previous * 100) if hours_previous > 0 else 0,
                "missed_visits_30d": missed_visits,
                "unique_caregivers_30d": len(caregiver_ids),
                "family_engagement_score": family_activity.engagement_score if family_activity else None,
                "care_plan_days_until_review": care_plan.days_until_review if care_plan else None,
            },
            "recommendations": self._generate_satisfaction_recommendations(risk_factors),
            "generated_at": datetime.utcnow().isoformat(),
        }

    def get_at_risk_clients(self, threshold: int = 40) -> List[Dict[str, Any]]:
        """Get all clients with satisfaction risk score above threshold"""
        results = []

        clients = self.get_clients(status=ClientStatus.ACTIVE)
        for client in clients:
            indicators = self.get_client_satisfaction_indicators(client.id)
            if indicators.get("risk_score", 0) >= threshold:
                results.append(indicators)

        # Sort by risk score descending
        results.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
        return results

    def _generate_satisfaction_recommendations(self, risk_factors: List[str]) -> List[str]:
        """Generate actionable recommendations based on risk factors"""
        recommendations = []

        for factor in risk_factors:
            if "declined" in factor.lower():
                recommendations.append("Schedule quality visit to discuss care needs")
                recommendations.append("Review authorized hours vs. actual delivered")
            elif "caregiver" in factor.lower():
                recommendations.append("Assign consistent caregiver team")
                recommendations.append("Check client preferences in care plan")
            elif "missed" in factor.lower():
                recommendations.append("Review scheduling and caregiver reliability")
                recommendations.append("Contact family about missed visit concerns")
            elif "engagement" in factor.lower() or "portal" in factor.lower():
                recommendations.append("Send family portal tutorial/reminder")
                recommendations.append("Proactive phone check-in with family")
            elif "care plan" in factor.lower():
                recommendations.append("Schedule care plan review meeting")
                recommendations.append("Update authorized services if needed")

        return list(set(recommendations))  # Remove duplicates

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _parse_date(self, value: Any) -> Optional[date]:
        """Parse date from various formats"""
        if not value:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        try:
            return datetime.fromisoformat(str(value).replace('Z', '+00:00')).date()
        except Exception:
            return None

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse datetime from various formats"""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except Exception:
            return None

    # =========================================================================
    # Mock Data Initialization
    # =========================================================================

    def _initialize_mock_data(self):
        """Initialize mock data for development/testing"""
        logger.info("Initializing WellSky mock data...")

        # Sample clients
        clients_data = [
            {"id": "C001", "first_name": "Robert", "last_name": "Johnson", "city": "Aurora",
             "status": ClientStatus.ACTIVE, "start_date": date(2025, 6, 15),
             "authorized_hours_weekly": 20, "payer_source": "private_pay"},
            {"id": "C002", "first_name": "Mary", "last_name": "Smith", "city": "Denver",
             "status": ClientStatus.ACTIVE, "start_date": date(2025, 3, 1),
             "authorized_hours_weekly": 30, "payer_source": "medicaid"},
            {"id": "C003", "first_name": "William", "last_name": "Davis", "city": "Centennial",
             "status": ClientStatus.ACTIVE, "start_date": date(2025, 9, 10),
             "authorized_hours_weekly": 16, "payer_source": "va"},
            {"id": "C004", "first_name": "Patricia", "last_name": "Wilson", "city": "Littleton",
             "status": ClientStatus.ACTIVE, "start_date": date(2024, 11, 20),
             "authorized_hours_weekly": 24, "payer_source": "private_pay"},
            {"id": "C005", "first_name": "James", "last_name": "Brown", "city": "Lakewood",
             "status": ClientStatus.ON_HOLD, "start_date": date(2025, 1, 5),
             "authorized_hours_weekly": 12, "payer_source": "medicaid"},
            {"id": "C006", "first_name": "Elizabeth", "last_name": "Miller", "city": "Aurora",
             "status": ClientStatus.ACTIVE, "start_date": date(2025, 8, 1),
             "authorized_hours_weekly": 20, "payer_source": "va"},
            {"id": "C007", "first_name": "Charles", "last_name": "Garcia", "city": "Denver",
             "status": ClientStatus.ACTIVE, "start_date": date(2025, 5, 15),
             "authorized_hours_weekly": 28, "payer_source": "private_pay"},
            {"id": "C008", "first_name": "Dorothy", "last_name": "Martinez", "city": "Englewood",
             "status": ClientStatus.ACTIVE, "start_date": date(2025, 7, 20),
             "authorized_hours_weekly": 16, "payer_source": "medicaid"},
        ]

        for data in clients_data:
            client = WellSkyClient(**data)
            client.created_at = datetime.combine(data["start_date"], datetime.min.time())
            client.updated_at = datetime.utcnow()
            self._mock_clients[client.id] = client

        # Sample caregivers
        caregivers_data = [
            {"id": "CG001", "first_name": "Maria", "last_name": "Garcia", "city": "Aurora",
             "phone": "+13035550101", "hire_date": date(2024, 1, 15),
             "certifications": ["CNA", "CPR"], "languages": ["English", "Spanish"],
             "available_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
             "avg_rating": 4.8, "current_weekly_hours": 32},
            {"id": "CG002", "first_name": "David", "last_name": "Lee", "city": "Denver",
             "phone": "+13035550102", "hire_date": date(2024, 6, 1),
             "certifications": ["HHA", "CPR", "First Aid"], "languages": ["English"],
             "available_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
             "avg_rating": 4.5, "current_weekly_hours": 36},
            {"id": "CG003", "first_name": "Sarah", "last_name": "Johnson", "city": "Centennial",
             "phone": "+13035550103", "hire_date": date(2023, 3, 10),
             "certifications": ["CNA"], "languages": ["English"],
             "available_days": ["Mon", "Wed", "Fri"],
             "avg_rating": 4.9, "current_weekly_hours": 20},
            {"id": "CG004", "first_name": "Michael", "last_name": "Williams", "city": "Lakewood",
             "phone": "+13035550104", "hire_date": date(2025, 1, 5),
             "certifications": ["HHA", "CPR"], "languages": ["English"],
             "available_days": ["Tue", "Thu", "Sat", "Sun"],
             "avg_rating": 4.2, "current_weekly_hours": 24},
            {"id": "CG005", "first_name": "Jennifer", "last_name": "Brown", "city": "Littleton",
             "phone": "+13035550105", "hire_date": date(2024, 8, 20),
             "certifications": ["CNA", "CPR", "Dementia Care"], "languages": ["English", "Vietnamese"],
             "available_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
             "avg_rating": 4.6, "current_weekly_hours": 38},
            {"id": "CG006", "first_name": "Carlos", "last_name": "Rodriguez", "city": "Aurora",
             "phone": "+13035550106", "hire_date": date(2025, 4, 1),
             "certifications": ["HHA"], "languages": ["English", "Spanish"],
             "available_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
             "avg_rating": 4.3, "current_weekly_hours": 28},
        ]

        for data in caregivers_data:
            caregiver = WellSkyCaregiver(
                id=data["id"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                status=CaregiverStatus.ACTIVE,
                city=data.get("city", ""),
                phone=data.get("phone", ""),
                hire_date=data.get("hire_date"),
                certifications=data.get("certifications", []),
                languages=data.get("languages", ["English"]),
                available_days=data.get("available_days", []),
                avg_rating=data.get("avg_rating", 4.0),
                current_weekly_hours=data.get("current_weekly_hours", 0),
            )
            caregiver.created_at = datetime.combine(data.get("hire_date", date.today()), datetime.min.time())
            self._mock_caregivers[caregiver.id] = caregiver

        # Sample shifts (past week + upcoming)
        today = date.today()
        for i in range(-7, 8):
            shift_date = today + timedelta(days=i)
            day_name = shift_date.strftime("%a")

            # Create shifts for clients with matching caregiver availability
            for client in list(self._mock_clients.values())[:5]:
                if not client.is_active:
                    continue

                # Find available caregiver
                available_cgs = [cg for cg in self._mock_caregivers.values()
                               if day_name in cg.available_days]
                if not available_cgs:
                    continue

                caregiver = available_cgs[hash(client.id + str(i)) % len(available_cgs)]

                shift = WellSkyShift(
                    id=f"S{client.id}{shift_date.isoformat().replace('-', '')}",
                    client_id=client.id,
                    caregiver_id=caregiver.id if i <= 0 else (caregiver.id if i % 3 != 0 else None),
                    status=ShiftStatus.COMPLETED if i < 0 else (ShiftStatus.SCHEDULED if caregiver.id else ShiftStatus.OPEN),
                    date=shift_date,
                    start_time="09:00",
                    end_time="13:00",
                    duration_hours=4.0,
                    evv_verified=i < 0,
                    client_first_name=client.first_name,
                    client_last_name=client.last_name,
                    caregiver_first_name=caregiver.first_name if i <= 0 else "",
                    caregiver_last_name=caregiver.last_name if i <= 0 else "",
                    city=client.city,
                )
                self._mock_shifts[shift.id] = shift

        # Sample care plans
        for client in self._mock_clients.values():
            if client.is_active:
                review_date = date.today() + timedelta(days=hash(client.id) % 90 - 30)
                care_plan = WellSkyCarePlan(
                    id=f"CP{client.id}",
                    client_id=client.id,
                    status="active",
                    created_date=client.start_date,
                    effective_date=client.start_date,
                    review_date=review_date,
                    authorized_hours_weekly=client.authorized_hours_weekly,
                    authorized_services=["Personal Care", "Companionship", "Light Housekeeping"],
                    goals=["Maintain independence", "Medication reminders", "Fall prevention"],
                )
                self._mock_care_plans[client.id] = care_plan

        # Sample family activity
        for client in self._mock_clients.values():
            if client.is_active:
                # Vary engagement levels
                engagement = (hash(client.id) % 100)
                activity = WellSkyFamilyActivity(
                    client_id=client.id,
                    last_login=datetime.utcnow() - timedelta(days=hash(client.id) % 30),
                    login_count_30d=engagement // 10,
                    messages_sent_30d=engagement // 20,
                    shift_notes_viewed_30d=engagement // 5,
                    payments_made_30d=1 if engagement > 50 else 0,
                    engagement_score=float(engagement),
                )
                self._mock_family_activity[client.id] = activity

        logger.info(f"Mock data initialized: {len(self._mock_clients)} clients, "
                   f"{len(self._mock_caregivers)} caregivers, {len(self._mock_shifts)} shifts")


# =============================================================================
# Singleton Instance
# =============================================================================

wellsky_service = WellSkyService()

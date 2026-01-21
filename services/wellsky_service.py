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


class ProspectStatus(Enum):
    """WellSky prospect/sales pipeline status values"""
    NEW = "new"
    CONTACTED = "contacted"
    ASSESSMENT_SCHEDULED = "assessment_scheduled"
    ASSESSMENT_COMPLETED = "assessment_completed"
    PROPOSAL_SENT = "proposal_sent"
    NEGOTIATING = "negotiating"
    WON = "won"
    LOST = "lost"
    ON_HOLD = "on_hold"


class ApplicantStatus(Enum):
    """WellSky applicant/recruiting status values"""
    NEW = "new"
    SCREENING = "screening"
    PHONE_INTERVIEW = "phone_interview"
    IN_PERSON_INTERVIEW = "in_person_interview"
    BACKGROUND_CHECK = "background_check"
    OFFER_EXTENDED = "offer_extended"
    HIRED = "hired"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


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


@dataclass
class WellSkyProspect:
    """
    Prospect record in WellSky - synced from Sales Dashboard.

    Maps to Sales Dashboard deals before they become active clients.
    Used for pipeline visibility and conversion tracking.
    """
    id: str
    first_name: str
    last_name: str
    status: ProspectStatus = ProspectStatus.NEW
    # Contact info
    phone: str = ""
    email: str = ""
    address: str = ""
    city: str = ""
    state: str = "CO"
    zip_code: str = ""
    # Referral tracking
    referral_source: str = ""
    referral_date: Optional[date] = None
    # Care needs assessment
    care_needs: List[str] = field(default_factory=list)
    estimated_hours_weekly: float = 0.0
    payer_type: str = ""  # private_pay, medicaid, va, ltc_insurance
    # Sales pipeline
    sales_rep: str = ""
    assessment_date: Optional[datetime] = None
    assessment_notes: str = ""
    proposal_amount: float = 0.0
    proposal_date: Optional[date] = None
    # Conversion tracking
    won_date: Optional[date] = None
    lost_date: Optional[date] = None
    lost_reason: str = ""
    converted_client_id: Optional[str] = None
    # External IDs (for sync tracking)
    sales_dashboard_deal_id: Optional[str] = None
    goformz_submission_id: Optional[str] = None
    # Metadata
    notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def is_open(self) -> bool:
        return self.status not in (ProspectStatus.WON, ProspectStatus.LOST)

    @property
    def is_converted(self) -> bool:
        return self.status == ProspectStatus.WON and self.converted_client_id is not None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['status'] = self.status.value
        d['referral_date'] = self.referral_date.isoformat() if self.referral_date else None
        d['assessment_date'] = self.assessment_date.isoformat() if self.assessment_date else None
        d['proposal_date'] = self.proposal_date.isoformat() if self.proposal_date else None
        d['won_date'] = self.won_date.isoformat() if self.won_date else None
        d['lost_date'] = self.lost_date.isoformat() if self.lost_date else None
        d['created_at'] = self.created_at.isoformat() if self.created_at else None
        d['updated_at'] = self.updated_at.isoformat() if self.updated_at else None
        return d


@dataclass
class WellSkyApplicant:
    """
    Applicant/candidate record in WellSky - synced from Recruiting Dashboard.

    Maps to Recruiting Dashboard leads before they become active caregivers.
    Used for pipeline visibility and hire tracking.
    """
    id: str
    first_name: str
    last_name: str
    status: ApplicantStatus = ApplicantStatus.NEW
    # Contact info
    phone: str = ""
    email: str = ""
    address: str = ""
    city: str = ""
    state: str = "CO"
    zip_code: str = ""
    # Application info
    application_date: Optional[date] = None
    source: str = ""  # indeed, referral, walk-in, etc.
    position_applied: str = ""  # CNA, HHA, Companion
    # Qualifications
    certifications: List[str] = field(default_factory=list)
    years_experience: int = 0
    languages: List[str] = field(default_factory=lambda: ["English"])
    available_days: List[str] = field(default_factory=list)
    desired_hours_weekly: int = 0
    # Recruiting pipeline
    recruiter: str = ""
    phone_screen_date: Optional[datetime] = None
    phone_screen_notes: str = ""
    interview_date: Optional[datetime] = None
    interview_notes: str = ""
    background_check_submitted: Optional[date] = None
    background_check_cleared: Optional[date] = None
    # Offer tracking
    offer_date: Optional[date] = None
    offer_hourly_rate: float = 0.0
    offer_accepted_date: Optional[date] = None
    start_date: Optional[date] = None
    # Rejection/withdrawal
    rejected_date: Optional[date] = None
    rejected_reason: str = ""
    withdrawn_date: Optional[date] = None
    withdrawn_reason: str = ""
    # Conversion tracking
    converted_caregiver_id: Optional[str] = None
    # External IDs (for sync tracking)
    recruiting_dashboard_lead_id: Optional[str] = None
    goformz_submission_id: Optional[str] = None
    # Metadata
    notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def is_open(self) -> bool:
        return self.status not in (ApplicantStatus.HIRED, ApplicantStatus.REJECTED, ApplicantStatus.WITHDRAWN)

    @property
    def is_hired(self) -> bool:
        return self.status == ApplicantStatus.HIRED and self.converted_caregiver_id is not None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['status'] = self.status.value
        d['application_date'] = self.application_date.isoformat() if self.application_date else None
        d['phone_screen_date'] = self.phone_screen_date.isoformat() if self.phone_screen_date else None
        d['interview_date'] = self.interview_date.isoformat() if self.interview_date else None
        d['background_check_submitted'] = self.background_check_submitted.isoformat() if self.background_check_submitted else None
        d['background_check_cleared'] = self.background_check_cleared.isoformat() if self.background_check_cleared else None
        d['offer_date'] = self.offer_date.isoformat() if self.offer_date else None
        d['offer_accepted_date'] = self.offer_accepted_date.isoformat() if self.offer_accepted_date else None
        d['start_date'] = self.start_date.isoformat() if self.start_date else None
        d['rejected_date'] = self.rejected_date.isoformat() if self.rejected_date else None
        d['withdrawn_date'] = self.withdrawn_date.isoformat() if self.withdrawn_date else None
        d['created_at'] = self.created_at.isoformat() if self.created_at else None
        d['updated_at'] = self.updated_at.isoformat() if self.updated_at else None
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
        self._mock_prospects: Dict[str, WellSkyProspect] = {}
        self._mock_applicants: Dict[str, WellSkyApplicant] = {}

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
    # EVV / Clock In-Out Methods (Used by Gigi AI Agent)
    # =========================================================================

    def get_caregiver_shifts_today(self, phone: str) -> List[WellSkyShift]:
        """
        Get all shifts for a caregiver today, looked up by phone number.
        Used by Gigi to know what shifts a caregiver has when they text/call.
        """
        caregiver = self.get_caregiver_by_phone(phone)
        if not caregiver:
            logger.warning(f"No caregiver found for phone {phone}")
            return []

        today = date.today()
        return self.get_shifts(
            caregiver_id=caregiver.id,
            date_from=today,
            date_to=today
        )

    def get_caregiver_current_shift(self, phone: str) -> Optional[WellSkyShift]:
        """
        Get the shift a caregiver is currently working or about to start.

        Returns the shift that is:
        1. In progress (clocked in but not out), OR
        2. Scheduled/confirmed for today and starting within 2 hours

        Used by Gigi when a caregiver says "I can't clock out" - she knows which shift.
        """
        shifts = self.get_caregiver_shifts_today(phone)
        if not shifts:
            return None

        now = datetime.now()

        # First, look for in-progress shift (clocked in, not clocked out)
        for shift in shifts:
            if shift.clock_in_time and not shift.clock_out_time:
                return shift
            if shift.status == ShiftStatus.IN_PROGRESS:
                return shift

        # Next, look for shift starting soon (within 2 hours)
        for shift in shifts:
            if shift.status in (ShiftStatus.SCHEDULED, ShiftStatus.CONFIRMED):
                if shift.start_time and shift.date:
                    try:
                        start_dt = datetime.combine(
                            shift.date,
                            datetime.strptime(shift.start_time, "%H:%M").time()
                        )
                        if -30 <= (start_dt - now).total_seconds() / 60 <= 120:
                            return shift
                    except (ValueError, TypeError):
                        pass

        # Otherwise return the first shift of the day
        return shifts[0] if shifts else None

    def get_caregiver_upcoming_shifts(
        self,
        phone: str,
        days: int = 7
    ) -> List[WellSkyShift]:
        """
        Get upcoming shifts for a caregiver (next N days).
        Used by Gigi when caregiver asks about their schedule.
        """
        caregiver = self.get_caregiver_by_phone(phone)
        if not caregiver:
            return []

        return self.get_shifts(
            caregiver_id=caregiver.id,
            date_from=date.today(),
            date_to=date.today() + timedelta(days=days)
        )

    def clock_in_shift(
        self,
        shift_id: str,
        clock_in_time: Optional[datetime] = None,
        notes: str = "",
        lat: float = 0.0,
        lon: float = 0.0
    ) -> Tuple[bool, str]:
        """
        Clock a caregiver into a shift.

        Returns (success, message) tuple.
        Used by Gigi when caregiver says they forgot to clock in.
        """
        clock_in_time = clock_in_time or datetime.now()

        if self.is_mock_mode:
            shift = self._mock_shifts.get(shift_id)
            if not shift:
                return False, f"Shift {shift_id} not found"
            if shift.clock_in_time:
                return False, f"Shift already clocked in at {shift.clock_in_time.strftime('%I:%M %p')}"

            shift.clock_in_time = clock_in_time
            shift.clock_in_lat = lat
            shift.clock_in_lon = lon
            shift.status = ShiftStatus.IN_PROGRESS
            if notes:
                shift.caregiver_notes = f"[Clock-in via Gigi] {notes}"

            logger.info(f"Mock: Clocked in shift {shift_id} at {clock_in_time}")
            return True, f"Clocked in at {clock_in_time.strftime('%I:%M %p')}"

        success, data = self._make_request(
            "POST",
            f"/shifts/{shift_id}/clock-in",
            data={
                "clock_in_time": clock_in_time.isoformat(),
                "notes": notes,
                "latitude": lat,
                "longitude": lon,
                "source": "gigi_sms"  # Track that this came from Gigi
            }
        )

        if success:
            return True, f"Clocked in at {clock_in_time.strftime('%I:%M %p')}"
        return False, data.get("error", "Failed to clock in")

    def clock_out_shift(
        self,
        shift_id: str,
        clock_out_time: Optional[datetime] = None,
        notes: str = ""
    ) -> Tuple[bool, str]:
        """
        Clock a caregiver out of a shift.

        Returns (success, message) tuple.
        Used by Gigi when caregiver says they can't clock out or forgot.
        """
        clock_out_time = clock_out_time or datetime.now()

        if self.is_mock_mode:
            shift = self._mock_shifts.get(shift_id)
            if not shift:
                return False, f"Shift {shift_id} not found"
            if shift.clock_out_time:
                return False, f"Shift already clocked out at {shift.clock_out_time.strftime('%I:%M %p')}"
            if not shift.clock_in_time:
                return False, "Cannot clock out - shift was never clocked in"

            shift.clock_out_time = clock_out_time
            shift.status = ShiftStatus.COMPLETED
            if notes:
                shift.caregiver_notes = (shift.caregiver_notes or "") + f"\n[Clock-out via Gigi] {notes}"

            logger.info(f"Mock: Clocked out shift {shift_id} at {clock_out_time}")
            return True, f"Clocked out at {clock_out_time.strftime('%I:%M %p')}"

        success, data = self._make_request(
            "POST",
            f"/shifts/{shift_id}/clock-out",
            data={
                "clock_out_time": clock_out_time.isoformat(),
                "notes": notes,
                "source": "gigi_sms"
            }
        )

        if success:
            return True, f"Clocked out at {clock_out_time.strftime('%I:%M %p')}"
        return False, data.get("error", "Failed to clock out")

    def report_callout(
        self,
        phone: str,
        shift_id: Optional[str] = None,
        reason: str = "",
        notify_client: bool = True
    ) -> Tuple[bool, str, Optional[WellSkyShift]]:
        """
        Report a caregiver call-out.

        If shift_id not provided, finds their next upcoming shift.
        Returns (success, message, affected_shift) tuple.

        Used by Gigi when caregiver says they can't make their shift.
        """
        caregiver = self.get_caregiver_by_phone(phone)
        if not caregiver:
            return False, "Could not find your caregiver profile", None

        # Find the shift if not specified
        if not shift_id:
            upcoming = self.get_caregiver_upcoming_shifts(phone, days=2)
            # Find first non-completed shift
            for shift in upcoming:
                if shift.status not in (ShiftStatus.COMPLETED, ShiftStatus.CANCELLED):
                    shift_id = shift.id
                    break

        if not shift_id:
            return False, "No upcoming shifts found to call out from", None

        if self.is_mock_mode:
            shift = self._mock_shifts.get(shift_id)
            if not shift:
                return False, f"Shift {shift_id} not found", None

            # Mark as cancelled/open for coverage
            shift.status = ShiftStatus.OPEN
            shift.caregiver_id = None
            shift.notes = (shift.notes or "") + f"\n[CALL-OUT via Gigi] {caregiver.full_name}: {reason}"

            client_name = f"{shift.client_first_name} {shift.client_last_name}".strip() or "the client"
            shift_time = shift.start_time or "scheduled time"
            shift_date = shift.date.strftime("%A, %B %d") if shift.date else "upcoming"

            logger.info(f"Mock: Call-out reported for shift {shift_id} by {caregiver.full_name}")

            message = (
                f"Got it. I've logged your call-out for your shift with {client_name} "
                f"on {shift_date} at {shift_time}. The care team will work on finding coverage. "
                f"Feel better!"
            )
            return True, message, shift

        # Production API call
        success, data = self._make_request(
            "POST",
            f"/shifts/{shift_id}/callout",
            data={
                "caregiver_id": caregiver.id,
                "reason": reason,
                "notify_client": notify_client,
                "source": "gigi_sms"
            }
        )

        if success:
            shift = self.get_shifts(caregiver_id=caregiver.id)
            affected_shift = next((s for s in shift if s.id == shift_id), None)
            return True, data.get("message", "Call-out recorded"), affected_shift

        return False, data.get("error", "Failed to record call-out"), None

    def get_shift_by_id(self, shift_id: str) -> Optional[WellSkyShift]:
        """Get a single shift by ID"""
        if self.is_mock_mode:
            return self._mock_shifts.get(shift_id)

        success, data = self._make_request("GET", f"/shifts/{shift_id}")
        if success:
            return self._parse_shift(data)
        return None

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
    # Prospect Methods (Sales Pipeline Integration)
    # =========================================================================

    def get_prospects(
        self,
        status: Optional[ProspectStatus] = None,
        sales_rep: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[WellSkyProspect]:
        """Get prospects from WellSky (sales pipeline)"""
        if self.is_mock_mode:
            prospects = list(self._mock_prospects.values())
            if status:
                prospects = [p for p in prospects if p.status == status]
            if sales_rep:
                prospects = [p for p in prospects if p.sales_rep == sales_rep]
            return prospects[offset:offset + limit]

        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status.value
        if sales_rep:
            params["sales_rep"] = sales_rep

        success, data = self._make_request("GET", "/prospects", params=params)

        if success and "prospects" in data:
            return [self._parse_prospect(p) for p in data["prospects"]]
        return []

    def get_prospect(self, prospect_id: str) -> Optional[WellSkyProspect]:
        """Get a single prospect by ID"""
        if self.is_mock_mode:
            return self._mock_prospects.get(prospect_id)

        success, data = self._make_request("GET", f"/prospects/{prospect_id}")

        if success:
            return self._parse_prospect(data)
        return None

    def get_prospect_by_sales_deal_id(self, deal_id: str) -> Optional[WellSkyProspect]:
        """Find prospect by Sales Dashboard deal ID"""
        if self.is_mock_mode:
            for prospect in self._mock_prospects.values():
                if prospect.sales_dashboard_deal_id == deal_id:
                    return prospect
            return None

        success, data = self._make_request(
            "GET", "/prospects",
            params={"sales_dashboard_deal_id": deal_id}
        )

        if success and data.get("prospects"):
            return self._parse_prospect(data["prospects"][0])
        return None

    def create_prospect(self, prospect_data: Dict[str, Any]) -> Optional[WellSkyProspect]:
        """
        Create a new prospect in WellSky.

        Called when a new deal is created in Sales Dashboard.
        """
        if self.is_mock_mode:
            prospect_id = f"P{len(self._mock_prospects) + 1:03d}"
            prospect = WellSkyProspect(
                id=prospect_id,
                first_name=prospect_data.get("first_name", ""),
                last_name=prospect_data.get("last_name", ""),
                status=ProspectStatus(prospect_data.get("status", "new")),
                phone=prospect_data.get("phone", ""),
                email=prospect_data.get("email", ""),
                address=prospect_data.get("address", ""),
                city=prospect_data.get("city", ""),
                state=prospect_data.get("state", "CO"),
                zip_code=prospect_data.get("zip_code", ""),
                referral_source=prospect_data.get("referral_source", ""),
                referral_date=self._parse_date(prospect_data.get("referral_date")),
                care_needs=prospect_data.get("care_needs", []),
                estimated_hours_weekly=float(prospect_data.get("estimated_hours_weekly", 0)),
                payer_type=prospect_data.get("payer_type", ""),
                sales_rep=prospect_data.get("sales_rep", ""),
                sales_dashboard_deal_id=prospect_data.get("sales_dashboard_deal_id"),
                notes=prospect_data.get("notes", ""),
            )
            prospect.created_at = datetime.utcnow()
            prospect.updated_at = datetime.utcnow()
            self._mock_prospects[prospect_id] = prospect
            logger.info(f"Mock: Created prospect {prospect_id} ({prospect.full_name})")
            return prospect

        success, data = self._make_request("POST", "/prospects", data=prospect_data)

        if success:
            return self._parse_prospect(data)
        return None

    def update_prospect(
        self,
        prospect_id: str,
        updates: Dict[str, Any]
    ) -> Optional[WellSkyProspect]:
        """Update an existing prospect"""
        if self.is_mock_mode:
            prospect = self._mock_prospects.get(prospect_id)
            if not prospect:
                return None

            for key, value in updates.items():
                if key == "status" and isinstance(value, str):
                    value = ProspectStatus(value)
                if hasattr(prospect, key):
                    setattr(prospect, key, value)

            prospect.updated_at = datetime.utcnow()
            logger.info(f"Mock: Updated prospect {prospect_id}")
            return prospect

        success, data = self._make_request("PUT", f"/prospects/{prospect_id}", data=updates)

        if success:
            return self._parse_prospect(data)
        return None

    def update_prospect_status(
        self,
        prospect_id: str,
        new_status: ProspectStatus,
        notes: str = ""
    ) -> Optional[WellSkyProspect]:
        """Update prospect status (pipeline stage change)"""
        updates = {"status": new_status.value}
        if notes:
            updates["status_change_notes"] = notes

        # Handle special status transitions
        now = datetime.utcnow()
        if new_status == ProspectStatus.WON:
            updates["won_date"] = now.date().isoformat()
        elif new_status == ProspectStatus.LOST:
            updates["lost_date"] = now.date().isoformat()
            if notes:
                updates["lost_reason"] = notes
        elif new_status == ProspectStatus.ASSESSMENT_COMPLETED:
            updates["assessment_date"] = now.isoformat()
        elif new_status == ProspectStatus.PROPOSAL_SENT:
            updates["proposal_date"] = now.date().isoformat()

        return self.update_prospect(prospect_id, updates)

    def convert_prospect_to_client(
        self,
        prospect_id: str,
        client_data: Optional[Dict[str, Any]] = None
    ) -> Optional[WellSkyClient]:
        """
        Convert a won prospect to an active client.

        Called when GoFormz paperwork is completed and prospect becomes client.
        """
        prospect = self.get_prospect(prospect_id)
        if not prospect:
            logger.error(f"Prospect {prospect_id} not found for conversion")
            return None

        if prospect.status != ProspectStatus.WON:
            logger.warning(f"Prospect {prospect_id} status is {prospect.status.value}, not 'won'")

        # Merge prospect data with any additional client data
        merged_data = {
            "first_name": prospect.first_name,
            "last_name": prospect.last_name,
            "phone": prospect.phone,
            "email": prospect.email,
            "address": prospect.address,
            "city": prospect.city,
            "state": prospect.state,
            "zip_code": prospect.zip_code,
            "referral_source": prospect.referral_source,
            "payer_source": prospect.payer_type,
            "authorized_hours_weekly": prospect.estimated_hours_weekly,
            "notes": prospect.notes,
        }

        if client_data:
            merged_data.update(client_data)

        # Create the client
        client = self.create_client(merged_data)

        if client:
            # Update prospect with converted client ID
            self.update_prospect(prospect_id, {
                "status": ProspectStatus.WON.value,
                "converted_client_id": client.id
            })
            logger.info(f"Converted prospect {prospect_id} to client {client.id}")

        return client

    def _parse_prospect(self, data: Dict) -> WellSkyProspect:
        """Parse API response into WellSkyProspect object"""
        return WellSkyProspect(
            id=str(data.get("id", "")),
            first_name=data.get("first_name", data.get("firstName", "")),
            last_name=data.get("last_name", data.get("lastName", "")),
            status=ProspectStatus(data.get("status", "new")),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            address=data.get("address", ""),
            city=data.get("city", ""),
            state=data.get("state", "CO"),
            zip_code=data.get("zip_code", data.get("zipCode", "")),
            referral_source=data.get("referral_source", data.get("referralSource", "")),
            referral_date=self._parse_date(data.get("referral_date", data.get("referralDate"))),
            care_needs=data.get("care_needs", data.get("careNeeds", [])),
            estimated_hours_weekly=float(data.get("estimated_hours_weekly", data.get("estimatedHoursWeekly", 0))),
            payer_type=data.get("payer_type", data.get("payerType", "")),
            sales_rep=data.get("sales_rep", data.get("salesRep", "")),
            assessment_date=self._parse_datetime(data.get("assessment_date", data.get("assessmentDate"))),
            assessment_notes=data.get("assessment_notes", data.get("assessmentNotes", "")),
            proposal_amount=float(data.get("proposal_amount", data.get("proposalAmount", 0))),
            proposal_date=self._parse_date(data.get("proposal_date", data.get("proposalDate"))),
            won_date=self._parse_date(data.get("won_date", data.get("wonDate"))),
            lost_date=self._parse_date(data.get("lost_date", data.get("lostDate"))),
            lost_reason=data.get("lost_reason", data.get("lostReason", "")),
            converted_client_id=data.get("converted_client_id", data.get("convertedClientId")),
            sales_dashboard_deal_id=data.get("sales_dashboard_deal_id", data.get("salesDashboardDealId")),
            goformz_submission_id=data.get("goformz_submission_id", data.get("goformzSubmissionId")),
            notes=data.get("notes", ""),
            created_at=self._parse_datetime(data.get("created_at", data.get("createdAt"))),
            updated_at=self._parse_datetime(data.get("updated_at", data.get("updatedAt"))),
        )

    # =========================================================================
    # Applicant Methods (Recruiting Pipeline Integration)
    # =========================================================================

    def get_applicants(
        self,
        status: Optional[ApplicantStatus] = None,
        recruiter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[WellSkyApplicant]:
        """Get applicants from WellSky (recruiting pipeline)"""
        if self.is_mock_mode:
            applicants = list(self._mock_applicants.values())
            if status:
                applicants = [a for a in applicants if a.status == status]
            if recruiter:
                applicants = [a for a in applicants if a.recruiter == recruiter]
            return applicants[offset:offset + limit]

        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status.value
        if recruiter:
            params["recruiter"] = recruiter

        success, data = self._make_request("GET", "/applicants", params=params)

        if success and "applicants" in data:
            return [self._parse_applicant(a) for a in data["applicants"]]
        return []

    def get_applicant(self, applicant_id: str) -> Optional[WellSkyApplicant]:
        """Get a single applicant by ID"""
        if self.is_mock_mode:
            return self._mock_applicants.get(applicant_id)

        success, data = self._make_request("GET", f"/applicants/{applicant_id}")

        if success:
            return self._parse_applicant(data)
        return None

    def get_applicant_by_recruiting_lead_id(self, lead_id: str) -> Optional[WellSkyApplicant]:
        """Find applicant by Recruiting Dashboard lead ID"""
        if self.is_mock_mode:
            for applicant in self._mock_applicants.values():
                if applicant.recruiting_dashboard_lead_id == lead_id:
                    return applicant
            return None

        success, data = self._make_request(
            "GET", "/applicants",
            params={"recruiting_dashboard_lead_id": lead_id}
        )

        if success and data.get("applicants"):
            return self._parse_applicant(data["applicants"][0])
        return None

    def create_applicant(self, applicant_data: Dict[str, Any]) -> Optional[WellSkyApplicant]:
        """
        Create a new applicant in WellSky.

        Called when a new lead is created in Recruiting Dashboard.
        """
        if self.is_mock_mode:
            applicant_id = f"A{len(self._mock_applicants) + 1:03d}"
            applicant = WellSkyApplicant(
                id=applicant_id,
                first_name=applicant_data.get("first_name", ""),
                last_name=applicant_data.get("last_name", ""),
                status=ApplicantStatus(applicant_data.get("status", "new")),
                phone=applicant_data.get("phone", ""),
                email=applicant_data.get("email", ""),
                address=applicant_data.get("address", ""),
                city=applicant_data.get("city", ""),
                state=applicant_data.get("state", "CO"),
                zip_code=applicant_data.get("zip_code", ""),
                application_date=self._parse_date(applicant_data.get("application_date")) or date.today(),
                source=applicant_data.get("source", ""),
                position_applied=applicant_data.get("position_applied", ""),
                certifications=applicant_data.get("certifications", []),
                years_experience=int(applicant_data.get("years_experience", 0)),
                languages=applicant_data.get("languages", ["English"]),
                available_days=applicant_data.get("available_days", []),
                desired_hours_weekly=int(applicant_data.get("desired_hours_weekly", 0)),
                recruiter=applicant_data.get("recruiter", ""),
                recruiting_dashboard_lead_id=applicant_data.get("recruiting_dashboard_lead_id"),
                notes=applicant_data.get("notes", ""),
            )
            applicant.created_at = datetime.utcnow()
            applicant.updated_at = datetime.utcnow()
            self._mock_applicants[applicant_id] = applicant
            logger.info(f"Mock: Created applicant {applicant_id} ({applicant.full_name})")
            return applicant

        success, data = self._make_request("POST", "/applicants", data=applicant_data)

        if success:
            return self._parse_applicant(data)
        return None

    def update_applicant(
        self,
        applicant_id: str,
        updates: Dict[str, Any]
    ) -> Optional[WellSkyApplicant]:
        """Update an existing applicant"""
        if self.is_mock_mode:
            applicant = self._mock_applicants.get(applicant_id)
            if not applicant:
                return None

            for key, value in updates.items():
                if key == "status" and isinstance(value, str):
                    value = ApplicantStatus(value)
                if hasattr(applicant, key):
                    setattr(applicant, key, value)

            applicant.updated_at = datetime.utcnow()
            logger.info(f"Mock: Updated applicant {applicant_id}")
            return applicant

        success, data = self._make_request("PUT", f"/applicants/{applicant_id}", data=updates)

        if success:
            return self._parse_applicant(data)
        return None

    def update_applicant_status(
        self,
        applicant_id: str,
        new_status: ApplicantStatus,
        notes: str = ""
    ) -> Optional[WellSkyApplicant]:
        """Update applicant status (recruiting pipeline stage change)"""
        updates = {"status": new_status.value}
        if notes:
            updates["status_change_notes"] = notes

        # Handle special status transitions
        now = datetime.utcnow()
        if new_status == ApplicantStatus.PHONE_INTERVIEW:
            updates["phone_screen_date"] = now.isoformat()
        elif new_status == ApplicantStatus.IN_PERSON_INTERVIEW:
            updates["interview_date"] = now.isoformat()
        elif new_status == ApplicantStatus.BACKGROUND_CHECK:
            updates["background_check_submitted"] = now.date().isoformat()
        elif new_status == ApplicantStatus.OFFER_EXTENDED:
            updates["offer_date"] = now.date().isoformat()
        elif new_status == ApplicantStatus.HIRED:
            updates["offer_accepted_date"] = now.date().isoformat()
        elif new_status == ApplicantStatus.REJECTED:
            updates["rejected_date"] = now.date().isoformat()
            if notes:
                updates["rejected_reason"] = notes
        elif new_status == ApplicantStatus.WITHDRAWN:
            updates["withdrawn_date"] = now.date().isoformat()
            if notes:
                updates["withdrawn_reason"] = notes

        return self.update_applicant(applicant_id, updates)

    def convert_applicant_to_caregiver(
        self,
        applicant_id: str,
        caregiver_data: Optional[Dict[str, Any]] = None
    ) -> Optional[WellSkyCaregiver]:
        """
        Convert a hired applicant to an active caregiver.

        Called when GoFormz paperwork is completed and applicant becomes caregiver.
        """
        applicant = self.get_applicant(applicant_id)
        if not applicant:
            logger.error(f"Applicant {applicant_id} not found for conversion")
            return None

        if applicant.status != ApplicantStatus.HIRED:
            logger.warning(f"Applicant {applicant_id} status is {applicant.status.value}, not 'hired'")

        # Merge applicant data with any additional caregiver data
        merged_data = {
            "first_name": applicant.first_name,
            "last_name": applicant.last_name,
            "phone": applicant.phone,
            "email": applicant.email,
            "address": applicant.address,
            "city": applicant.city,
            "state": applicant.state,
            "zip_code": applicant.zip_code,
            "certifications": applicant.certifications,
            "languages": applicant.languages,
            "available_days": applicant.available_days,
            "hire_date": applicant.start_date or date.today(),
            "notes": applicant.notes,
        }

        if caregiver_data:
            merged_data.update(caregiver_data)

        # Create the caregiver
        caregiver = self.create_caregiver(merged_data)

        if caregiver:
            # Update applicant with converted caregiver ID
            self.update_applicant(applicant_id, {
                "status": ApplicantStatus.HIRED.value,
                "converted_caregiver_id": caregiver.id
            })
            logger.info(f"Converted applicant {applicant_id} to caregiver {caregiver.id}")

        return caregiver

    def _parse_applicant(self, data: Dict) -> WellSkyApplicant:
        """Parse API response into WellSkyApplicant object"""
        return WellSkyApplicant(
            id=str(data.get("id", "")),
            first_name=data.get("first_name", data.get("firstName", "")),
            last_name=data.get("last_name", data.get("lastName", "")),
            status=ApplicantStatus(data.get("status", "new")),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            address=data.get("address", ""),
            city=data.get("city", ""),
            state=data.get("state", "CO"),
            zip_code=data.get("zip_code", data.get("zipCode", "")),
            application_date=self._parse_date(data.get("application_date", data.get("applicationDate"))),
            source=data.get("source", ""),
            position_applied=data.get("position_applied", data.get("positionApplied", "")),
            certifications=data.get("certifications", []),
            years_experience=int(data.get("years_experience", data.get("yearsExperience", 0))),
            languages=data.get("languages", ["English"]),
            available_days=data.get("available_days", data.get("availableDays", [])),
            desired_hours_weekly=int(data.get("desired_hours_weekly", data.get("desiredHoursWeekly", 0))),
            recruiter=data.get("recruiter", ""),
            phone_screen_date=self._parse_datetime(data.get("phone_screen_date", data.get("phoneScreenDate"))),
            phone_screen_notes=data.get("phone_screen_notes", data.get("phoneScreenNotes", "")),
            interview_date=self._parse_datetime(data.get("interview_date", data.get("interviewDate"))),
            interview_notes=data.get("interview_notes", data.get("interviewNotes", "")),
            background_check_submitted=self._parse_date(data.get("background_check_submitted", data.get("backgroundCheckSubmitted"))),
            background_check_cleared=self._parse_date(data.get("background_check_cleared", data.get("backgroundCheckCleared"))),
            offer_date=self._parse_date(data.get("offer_date", data.get("offerDate"))),
            offer_hourly_rate=float(data.get("offer_hourly_rate", data.get("offerHourlyRate", 0))),
            offer_accepted_date=self._parse_date(data.get("offer_accepted_date", data.get("offerAcceptedDate"))),
            start_date=self._parse_date(data.get("start_date", data.get("startDate"))),
            rejected_date=self._parse_date(data.get("rejected_date", data.get("rejectedDate"))),
            rejected_reason=data.get("rejected_reason", data.get("rejectedReason", "")),
            withdrawn_date=self._parse_date(data.get("withdrawn_date", data.get("withdrawnDate"))),
            withdrawn_reason=data.get("withdrawn_reason", data.get("withdrawnReason", "")),
            converted_caregiver_id=data.get("converted_caregiver_id", data.get("convertedCaregiverId")),
            recruiting_dashboard_lead_id=data.get("recruiting_dashboard_lead_id", data.get("recruitingDashboardLeadId")),
            goformz_submission_id=data.get("goformz_submission_id", data.get("goformzSubmissionId")),
            notes=data.get("notes", ""),
            created_at=self._parse_datetime(data.get("created_at", data.get("createdAt"))),
            updated_at=self._parse_datetime(data.get("updated_at", data.get("updatedAt"))),
        )

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

        # Sample prospects (sales pipeline)
        prospects_data = [
            {"id": "P001", "first_name": "Harold", "last_name": "Thompson", "city": "Boulder",
             "phone": "+13035551001", "email": "hthompson@email.com",
             "status": ProspectStatus.ASSESSMENT_SCHEDULED, "referral_source": "physician",
             "referral_date": date.today() - timedelta(days=10),
             "care_needs": ["Personal Care", "Medication Management"],
             "estimated_hours_weekly": 20, "payer_type": "private_pay",
             "sales_rep": "Sarah Miller", "sales_dashboard_deal_id": "DEAL001"},
            {"id": "P002", "first_name": "Margaret", "last_name": "Chen", "city": "Denver",
             "phone": "+13035551002", "email": "mchen@email.com",
             "status": ProspectStatus.PROPOSAL_SENT, "referral_source": "hospital_discharge",
             "referral_date": date.today() - timedelta(days=21),
             "care_needs": ["Companionship", "Light Housekeeping", "Meal Prep"],
             "estimated_hours_weekly": 15, "payer_type": "ltc_insurance",
             "sales_rep": "John Davis", "proposal_amount": 3600.0,
             "proposal_date": date.today() - timedelta(days=3), "sales_dashboard_deal_id": "DEAL002"},
            {"id": "P003", "first_name": "Richard", "last_name": "Anderson", "city": "Arvada",
             "phone": "+13035551003", "email": "randerson@email.com",
             "status": ProspectStatus.NEW, "referral_source": "website",
             "referral_date": date.today() - timedelta(days=2),
             "care_needs": ["Personal Care"],
             "estimated_hours_weekly": 10, "payer_type": "medicaid",
             "sales_rep": "", "sales_dashboard_deal_id": "DEAL003"},
            {"id": "P004", "first_name": "Barbara", "last_name": "Williams", "city": "Lakewood",
             "phone": "+13035551004", "email": "bwilliams@email.com",
             "status": ProspectStatus.NEGOTIATING, "referral_source": "family_referral",
             "referral_date": date.today() - timedelta(days=30),
             "care_needs": ["Personal Care", "Dementia Care", "Overnight Care"],
             "estimated_hours_weekly": 40, "payer_type": "private_pay",
             "sales_rep": "Sarah Miller", "proposal_amount": 9600.0,
             "assessment_date": datetime.now() - timedelta(days=14),
             "proposal_date": date.today() - timedelta(days=7), "sales_dashboard_deal_id": "DEAL004"},
            {"id": "P005", "first_name": "George", "last_name": "Martinez", "city": "Aurora",
             "phone": "+13035551005", "email": "gmartinez@email.com",
             "status": ProspectStatus.CONTACTED, "referral_source": "va_referral",
             "referral_date": date.today() - timedelta(days=5),
             "care_needs": ["Personal Care", "Transportation"],
             "estimated_hours_weekly": 12, "payer_type": "va",
             "sales_rep": "John Davis", "sales_dashboard_deal_id": "DEAL005"},
        ]

        for data in prospects_data:
            prospect = WellSkyProspect(
                id=data["id"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                status=data["status"],
                phone=data.get("phone", ""),
                email=data.get("email", ""),
                city=data.get("city", ""),
                referral_source=data.get("referral_source", ""),
                referral_date=data.get("referral_date"),
                care_needs=data.get("care_needs", []),
                estimated_hours_weekly=data.get("estimated_hours_weekly", 0),
                payer_type=data.get("payer_type", ""),
                sales_rep=data.get("sales_rep", ""),
                assessment_date=data.get("assessment_date"),
                proposal_amount=data.get("proposal_amount", 0),
                proposal_date=data.get("proposal_date"),
                sales_dashboard_deal_id=data.get("sales_dashboard_deal_id"),
            )
            prospect.created_at = datetime.combine(data.get("referral_date", date.today()), datetime.min.time())
            prospect.updated_at = datetime.utcnow()
            self._mock_prospects[prospect.id] = prospect

        # Sample applicants (recruiting pipeline)
        applicants_data = [
            {"id": "A001", "first_name": "Emily", "last_name": "Taylor", "city": "Denver",
             "phone": "+13035552001", "email": "etaylor@email.com",
             "status": ApplicantStatus.BACKGROUND_CHECK, "source": "indeed",
             "application_date": date.today() - timedelta(days=14),
             "position_applied": "CNA", "certifications": ["CNA", "CPR"],
             "years_experience": 3, "languages": ["English", "Spanish"],
             "available_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
             "desired_hours_weekly": 40, "recruiter": "Lisa Brown",
             "phone_screen_date": datetime.now() - timedelta(days=10),
             "interview_date": datetime.now() - timedelta(days=5),
             "background_check_submitted": date.today() - timedelta(days=2),
             "recruiting_dashboard_lead_id": "LEAD001"},
            {"id": "A002", "first_name": "Marcus", "last_name": "Johnson", "city": "Aurora",
             "phone": "+13035552002", "email": "mjohnson@email.com",
             "status": ApplicantStatus.IN_PERSON_INTERVIEW, "source": "referral",
             "application_date": date.today() - timedelta(days=7),
             "position_applied": "HHA", "certifications": ["HHA"],
             "years_experience": 1, "languages": ["English"],
             "available_days": ["Mon", "Wed", "Fri", "Sat"],
             "desired_hours_weekly": 30, "recruiter": "Lisa Brown",
             "phone_screen_date": datetime.now() - timedelta(days=4),
             "recruiting_dashboard_lead_id": "LEAD002"},
            {"id": "A003", "first_name": "Jennifer", "last_name": "Lee", "city": "Centennial",
             "phone": "+13035552003", "email": "jlee@email.com",
             "status": ApplicantStatus.NEW, "source": "indeed",
             "application_date": date.today() - timedelta(days=1),
             "position_applied": "Companion", "certifications": [],
             "years_experience": 0, "languages": ["English", "Korean"],
             "available_days": ["Tue", "Thu", "Sat", "Sun"],
             "desired_hours_weekly": 20, "recruiter": "",
             "recruiting_dashboard_lead_id": "LEAD003"},
            {"id": "A004", "first_name": "Anthony", "last_name": "Garcia", "city": "Lakewood",
             "phone": "+13035552004", "email": "agarcia@email.com",
             "status": ApplicantStatus.OFFER_EXTENDED, "source": "walk_in",
             "application_date": date.today() - timedelta(days=21),
             "position_applied": "CNA", "certifications": ["CNA", "CPR", "First Aid"],
             "years_experience": 5, "languages": ["English", "Spanish"],
             "available_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
             "desired_hours_weekly": 40, "recruiter": "Mike Wilson",
             "phone_screen_date": datetime.now() - timedelta(days=18),
             "interview_date": datetime.now() - timedelta(days=14),
             "background_check_submitted": date.today() - timedelta(days=10),
             "background_check_cleared": date.today() - timedelta(days=3),
             "offer_date": date.today() - timedelta(days=1),
             "offer_hourly_rate": 18.50,
             "recruiting_dashboard_lead_id": "LEAD004"},
            {"id": "A005", "first_name": "Rachel", "last_name": "Kim", "city": "Boulder",
             "phone": "+13035552005", "email": "rkim@email.com",
             "status": ApplicantStatus.PHONE_INTERVIEW, "source": "linkedin",
             "application_date": date.today() - timedelta(days=3),
             "position_applied": "HHA", "certifications": ["HHA", "CPR"],
             "years_experience": 2, "languages": ["English"],
             "available_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
             "desired_hours_weekly": 35, "recruiter": "Mike Wilson",
             "recruiting_dashboard_lead_id": "LEAD005"},
        ]

        for data in applicants_data:
            applicant = WellSkyApplicant(
                id=data["id"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                status=data["status"],
                phone=data.get("phone", ""),
                email=data.get("email", ""),
                city=data.get("city", ""),
                application_date=data.get("application_date"),
                source=data.get("source", ""),
                position_applied=data.get("position_applied", ""),
                certifications=data.get("certifications", []),
                years_experience=data.get("years_experience", 0),
                languages=data.get("languages", ["English"]),
                available_days=data.get("available_days", []),
                desired_hours_weekly=data.get("desired_hours_weekly", 0),
                recruiter=data.get("recruiter", ""),
                phone_screen_date=data.get("phone_screen_date"),
                interview_date=data.get("interview_date"),
                background_check_submitted=data.get("background_check_submitted"),
                background_check_cleared=data.get("background_check_cleared"),
                offer_date=data.get("offer_date"),
                offer_hourly_rate=data.get("offer_hourly_rate", 0),
                recruiting_dashboard_lead_id=data.get("recruiting_dashboard_lead_id"),
            )
            applicant.created_at = datetime.combine(data.get("application_date", date.today()), datetime.min.time())
            applicant.updated_at = datetime.utcnow()
            self._mock_applicants[applicant.id] = applicant

        logger.info(f"Mock data initialized: {len(self._mock_clients)} clients, "
                   f"{len(self._mock_caregivers)} caregivers, {len(self._mock_shifts)} shifts, "
                   f"{len(self._mock_prospects)} prospects, {len(self._mock_applicants)} applicants")


# =============================================================================
# Singleton Instance
# =============================================================================

wellsky_service = WellSkyService()

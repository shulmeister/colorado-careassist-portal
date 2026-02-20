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

import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# OAuth 2.0 Credentials (from WellSky Connect API)
WELLSKY_CLIENT_ID = os.getenv("WELLSKY_CLIENT_ID", "")
WELLSKY_CLIENT_SECRET = os.getenv("WELLSKY_CLIENT_SECRET", "")
WELLSKY_AGENCY_ID = os.getenv("WELLSKY_AGENCY_ID", "4505")
WELLSKY_ENVIRONMENT = os.getenv("WELLSKY_ENVIRONMENT", "production")

# API Base URLs (WellSky Home Connect API - https://connect.clearcareonline.com/fhir/)
API_URLS = {
    "sandbox": "https://connect-sandbox.clearcareonline.com/v1",  # Sandbox endpoint (if available)
    "production": "https://connect.clearcareonline.com/v1",  # Production endpoint
}

# API Host URLs (for OAuth - no /v1 prefix)
API_HOSTS = {
    "sandbox": "https://connect-sandbox.clearcareonline.com",
    "production": "https://connect.clearcareonline.com",
}

# OAuth endpoint path (at ROOT level, not under /v1/)
OAUTH_TOKEN_PATH = "/oauth/accesstoken"  # Working WellSky OAuth path


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
        self.api_key = WELLSKY_CLIENT_ID  # OAuth client_id
        self.api_secret = WELLSKY_CLIENT_SECRET  # OAuth client_secret
        self.agency_id = WELLSKY_AGENCY_ID
        self.environment = WELLSKY_ENVIRONMENT
        self.api_mode = os.getenv("WELLSKY_API_MODE", "connect").lower()  # connect or legacy
        self.base_url = API_URLS.get(self.environment, API_URLS["production"])  # API base URL (with /v1)
        self.host_url = API_HOSTS.get(self.environment, API_HOSTS["production"])  # Host URL (for OAuth - no /v1)
        self.api_base_url = self.base_url
        self.legacy_token_url = None # Deprecated

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
            logger.info(f"WellSky service initialized in {self.environment} mode ({self.api_mode})")
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
            # OAuth 2.0 client credentials flow (WellSky Connect API)
            auth_url = f"{self.host_url}{OAUTH_TOKEN_PATH}"

            response = requests.post(
                auth_url,
                json={
                    "client_id": self.api_key,
                    "client_secret": self.api_secret,
                    "grant_type": "client_credentials",
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                self._access_token = data.get("access_token")
                expires_in = int(data.get("expires_in", 3600))
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

        # WellSky API requires trailing slashes on all endpoints (per API docs)
        endpoint_clean = endpoint.lstrip('/').rstrip('/')
        url = f"{self.base_url}/{endpoint_clean}/"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Add agencyId to query params (required by WellSky API)
        # UPDATE: For Connect/FHIR API, the token handles scope. Explicit agencyId might filter incorrectly.
        if params is None:
            params = {}
        # if "agencyId" not in params and self.agency_id:
        #     params["agencyId"] = self.agency_id

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, params=params, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data, params=params, timeout=30)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, params=params, timeout=30)
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

    def _get_headers(self) -> Dict[str, str]:
        """Standard auth headers for WellSky requests."""
        token = self._get_access_token()
        if not token:
            return {"Content-Type": "application/json"}
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }



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

        # Real API Implementation (FHIR)
        # UPDATE: Fetch all and filter locally if needed, as 'active=true' filter is returning 0 incorrectly
        active_filter = None
        # if status == ClientStatus.ACTIVE:
        #     active_filter = True
        # elif status == ClientStatus.DISCHARGED:
        #     active_filter = False

        page = offset // limit if limit > 0 else 0
        clients = self.search_patients(active=active_filter, limit=limit, page=page)

        # Local filtering for status if requested
        if status == ClientStatus.ACTIVE:
            return [c for c in clients if c.status == ClientStatus.ACTIVE]
        elif status == ClientStatus.DISCHARGED:
            return [c for c in clients if c.status == ClientStatus.DISCHARGED]

        return clients

    def get_client(self, client_id: str) -> Optional[WellSkyClient]:
        """Get a single client by ID"""
        if self.is_mock_mode:
            return self._mock_clients.get(client_id)

        return self.get_patient(client_id)

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

    # =========================================================================
    # FHIR-Compliant Patient API (WellSky Connect API)
    # =========================================================================

    def search_patients(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        city: Optional[str] = None,
        active: Optional[bool] = None,
        limit: int = 20,
        page: int = 0
    ) -> List[WellSkyClient]:
        """
        Search for patients (clients) using FHIR-compliant API.

        Uses POST /v1/patients/_search/ endpoint.

        Args:
            first_name: Filter by first name
            last_name: Filter by last name
            phone: Filter by phone number (10 digits)
            city: Filter by city
            active: Filter by active status (default True)
            limit: Results per page (1-100, default 20)
            page: Page number (default 0)

        Returns:
            List of WellSkyClient objects
        """
        if self.is_mock_mode:
            # Mock mode fallback
            results = list(self._mock_clients.values())
            if first_name:
                results = [c for c in results if c.first_name.lower().startswith(first_name.lower())]
            if last_name:
                results = [c for c in results if c.last_name.lower().startswith(last_name.lower())]
            if active:
                results = [c for c in results if c.is_active]
            return results[:limit]

        # Build search payload
        search_payload = {}

        if first_name:
            search_payload["first_name"] = first_name
        if last_name:
            search_payload["last_name"] = last_name
        if phone:
            # Clean phone to 10 digits
            import re
            clean_phone = re.sub(r'[^\d]', '', phone)[-10:]
            search_payload["mobile_phone"] = clean_phone
        if city:
            search_payload["city"] = city
        if active is not None:
            search_payload["active"] = "true" if active else "false"

        # Query parameters for pagination
        params = {
            "_count": min(limit, 100),
            "_page": page
        }

        # UPDATE: If no search criteria other than active is provided, use GET /patients
        # because POST /patients/_search/ with active=true is currently returning 0.
        if not any([first_name, last_name, phone, city]):
            success, data = self._make_request(
                "GET",
                "patients",
                params=params
            )
        else:
            success, data = self._make_request(
                "POST",
                "patients/_search/",
                params=params,
                data=search_payload
            )

        if not success:
            logger.error(f"Patient search failed: {data}")
            return []

        # Parse FHIR Bundle response
        clients = []
        if data.get("resourceType") == "Bundle" and data.get("entry"):
            for entry in data["entry"]:
                try:
                    client = self._parse_fhir_patient(entry)
                    clients.append(client)
                except Exception as e:
                    logger.error(f"Error parsing patient: {e}")
                    continue

        logger.info(f"Found {len(clients)} patients matching search criteria")
        return clients

    def get_patient(self, patient_id: str) -> Optional[WellSkyClient]:
        """
        Get a single patient by ID using FHIR-compliant API.

        Uses GET /v1/patients/{id}/ endpoint.

        Args:
            patient_id: WellSky patient ID

        Returns:
            WellSkyClient object or None
        """
        if self.is_mock_mode:
            return self._mock_clients.get(patient_id)

        success, data = self._make_request("GET", f"patients/{patient_id}/")

        if not success:
            logger.error(f"Get patient {patient_id} failed: {data}")
            return None

        try:
            return self._parse_fhir_patient(data)
        except Exception as e:
            logger.error(f"Error parsing patient {patient_id}: {e}")
            return None

    def create_patient(
        self,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        state: str = "CO",
        zip_code: Optional[str] = None,
        is_client: bool = False,
        status_id: int = 1,  # 1 = New Lead, 80 = Care Started
        referral_source: Optional[str] = None
    ) -> Optional[WellSkyClient]:
        """
        Create a new patient (client/prospect) using FHIR-compliant API.

        Uses POST /v1/patients/ endpoint.

        Args:
            first_name: Patient first name (required)
            last_name: Patient last name (required)
            phone: Phone number (10 digits)
            email: Email address
            address: Street address
            city: City
            state: State (default "CO")
            zip_code: ZIP code
            is_client: True for client, False for prospect/lead
            status_id: Patient status ID (1=New Lead, 80=Care Started)
            referral_source: How they heard about us

        Returns:
            WellSkyClient object or None
        """
        if self.is_mock_mode:
            client_id = f"P{len(self._mock_clients) + 1:03d}"
            client = WellSkyClient(
                id=client_id,
                first_name=first_name,
                last_name=last_name,
                phone=phone or "",
                email=email or "",
                address=address or "",
                city=city or "",
                state=state,
                zip_code=zip_code or "",
                status=ClientStatus.ACTIVE if is_client else ClientStatus.PROSPECT,
                referral_source=referral_source or "",
                created_at=datetime.utcnow()
            )
            self._mock_clients[client_id] = client
            logger.info(f"Mock: Created patient {client_id}")
            return client

        # Build FHIR Patient resource
        fhir_patient = {
            "resourceType": "Patient",
            "active": True,
            "name": [
                {
                    "use": "official",
                    "family": last_name,
                    "given": [first_name]
                }
            ],
            "telecom": [],
            "address": [],
            "meta": {
                "tag": [
                    {"code": "agencyId", "display": self.agency_id},
                    {"code": "isClient", "display": "true" if is_client else "false"},
                    {"code": "status", "display": str(status_id)}
                ]
            }
        }

        # Add phone
        if phone:
            import re
            clean_phone = re.sub(r'[^\d]', '', phone)[-10:]
            fhir_patient["telecom"].append({
                "system": "phone",
                "value": clean_phone,
                "use": "mobile"
            })

        # Add email
        if email:
            fhir_patient["telecom"].append({
                "system": "email",
                "value": email
            })

        # Add address
        if address or city or state or zip_code:
            addr = {
                "use": "home",
                "line": [address] if address else [],
                "city": city or "",
                "state": state,
                "postalCode": zip_code or ""
            }
            fhir_patient["address"].append(addr)

        # Add referral source if provided
        if referral_source:
            fhir_patient["meta"]["tag"].append({
                "code": "referralSource",
                "display": referral_source
            })

        success, data = self._make_request("POST", "patients/", data=fhir_patient)

        if not success:
            logger.error(f"Create patient failed: {data}")
            return None

        # Parse response
        try:
            patient_id = data.get("id")
            if patient_id:
                logger.info(f"Created patient {patient_id}")
                # Fetch the full patient record
                return self.get_patient(str(patient_id))
            return None
        except Exception as e:
            logger.error(f"Error parsing created patient: {e}")
            return None

    def update_patient(
        self,
        patient_id: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        home_phone: Optional[str] = None,
        work_phone: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        zip_code: Optional[str] = None,
        gender: Optional[str] = None,
        birth_date: Optional[str] = None,
        active: Optional[bool] = None,
        status_id: Optional[int] = None,
        is_client: Optional[bool] = None
    ) -> Tuple[bool, Any]:
        """
        Update an existing patient (client) record.
        PUT /v1/patients/{id}/

        All fields optional - only provided fields are updated.
        Uses same FHIR Patient structure as create.

        Args:
            patient_id: WellSky patient ID
            first_name: Updated first name
            last_name: Updated last name
            phone: Mobile phone (10 digits)
            home_phone: Home phone
            work_phone: Work phone
            email: Email address
            address: Street address
            city: City
            state: State code (e.g. "CO")
            zip_code: ZIP code
            gender: "male", "female", "other", "unknown"
            birth_date: Date of birth (YYYY-MM-DD)
            active: Active status
            status_id: Status ID (1=New Lead, 80=Care Started, etc.)
            is_client: True for client, False for prospect
        """
        if self.is_mock_mode:
            client = self._mock_clients.get(patient_id)
            if client:
                if first_name is not None:
                    client.first_name = first_name
                if last_name is not None:
                    client.last_name = last_name
                if phone is not None:
                    client.phone = phone
                if email is not None:
                    client.email = email
                if city is not None:
                    client.city = city
                if state is not None:
                    client.state = state
                logger.info(f"Mock: Updated patient {patient_id}")
                return True, {"success": True}
            return False, {"error": "Patient not found"}

        fhir_patient = {
            "resourceType": "Patient",
            "meta": {"tag": [{"code": "agencyId", "display": self.agency_id}]}
        }

        if active is not None:
            fhir_patient["active"] = active

        if first_name is not None or last_name is not None:
            name = {"use": "official"}
            if first_name is not None:
                name["given"] = [first_name]
            if last_name is not None:
                name["family"] = last_name
            fhir_patient["name"] = [name]

        # Build telecom array
        telecom = []
        if phone is not None:
            import re
            clean = re.sub(r'[^\d]', '', phone)[-10:]
            telecom.append({"system": "phone", "value": clean, "use": "mobile"})
        if home_phone is not None:
            import re
            clean = re.sub(r'[^\d]', '', home_phone)[-10:]
            telecom.append({"system": "phone", "value": clean, "use": "home"})
        if work_phone is not None:
            import re
            clean = re.sub(r'[^\d]', '', work_phone)[-10:]
            telecom.append({"system": "phone", "value": clean, "use": "work"})
        if email is not None:
            telecom.append({"system": "email", "value": email})
        if telecom:
            fhir_patient["telecom"] = telecom

        # Build address
        if any(v is not None for v in [address, city, state, zip_code]):
            addr = {"use": "home"}
            if address is not None:
                addr["line"] = [address]
            if city is not None:
                addr["city"] = city
            if state is not None:
                addr["state"] = state
            if zip_code is not None:
                addr["postalCode"] = zip_code
            fhir_patient["address"] = [addr]

        if gender is not None:
            fhir_patient["gender"] = gender
        if birth_date is not None:
            fhir_patient["birthDate"] = birth_date

        # Meta tags for status/isClient
        if status_id is not None:
            fhir_patient["meta"]["tag"].append({"code": "status", "display": str(status_id)})
        if is_client is not None:
            fhir_patient["meta"]["tag"].append({"code": "isClient", "display": "true" if is_client else "false"})

        success, response = self._make_request("PUT", f"patients/{patient_id}/", data=fhir_patient)
        if success:
            logger.info(f"Updated patient {patient_id}")
        return success, response

    def delete_patient(self, patient_id: str) -> Tuple[bool, Any]:
        """
        Delete a patient record.
        DELETE /v1/patients/{id}/

        Use with caution - this permanently removes the patient from WellSky.
        """
        if self.is_mock_mode:
            if patient_id in self._mock_clients:
                del self._mock_clients[patient_id]
                return True, {"success": True}
            return False, {"error": "Patient not found"}

        success, response = self._make_request("DELETE", f"patients/{patient_id}/")
        if success:
            logger.info(f"Deleted patient {patient_id}")
        return success, response

    def _parse_fhir_patient(self, fhir_data: Dict) -> WellSkyClient:
        """
        Parse FHIR Patient resource into WellSkyClient object.
        Handles both direct resource and Bundle entry wrapper.
        """
        # If this is a Bundle entry, extract the actual resource
        if "resource" in fhir_data:
            fhir_data = fhir_data["resource"]

        # Extract ID
        client_id = str(fhir_data.get("id", ""))

        # Extract name
        first_name = ""
        last_name = ""
        if fhir_data.get("name"):
            name = fhir_data["name"][0]
            last_name = name.get("family", "")
            given = name.get("given", [])
            first_name = given[0] if given else ""

        # Extract phone and email
        phone = ""
        email = ""
        for telecom in fhir_data.get("telecom", []):
            system = telecom.get("system", "")
            value = telecom.get("value", "")
            if system == "phone":
                phone = value
            elif system == "email":
                email = value

        # Extract address
        address_str = ""
        city = ""
        state = "CO"
        zip_code = ""
        if fhir_data.get("address"):
            addr = fhir_data["address"][0]
            address_str = ", ".join(addr.get("line", []))
            city = addr.get("city", "")
            state = addr.get("state", "CO")
            zip_code = addr.get("postalCode", "")

        # Extract status and metadata
        active = fhir_data.get("active", True)
        is_client = False
        status_id = 1
        referral_source = ""

        # Debug: Show raw meta tags for first client
        if not hasattr(self, '_logged_meta'):
            self._logged_meta = True
            meta_tags = fhir_data.get("meta", {}).get("tag", [])
            logger.info(f"DEBUG: Raw meta tags for client {client_id}: {meta_tags}")

        for tag in fhir_data.get("meta", {}).get("tag", []):
            code = tag.get("code", "")
            display = tag.get("display", "")

            if code == "isClient":
                is_client = display.lower() == "true"
            elif code == "status":
                try:
                    status_id = int(display)
                except:
                    status_id = 1
            elif code == "referralSource":
                referral_source = display

        # Debug: Log first 5 clients to understand status_id values
        if hasattr(self, '_debug_count'):
            self._debug_count += 1
        else:
            self._debug_count = 1

        if self._debug_count <= 5:
            logger.info(f"DEBUG Client {client_id}: status_id={status_id}, is_client={is_client}, active={active}")

        # Determine status
        # Use multiple signals: is_client meta tag OR active FHIR field
        # WellSky may use either depending on the record type
        if is_client or active:
            # If marked as client OR active in FHIR → ACTIVE
            status = ClientStatus.ACTIVE
        else:
            # Not marked as client and not active = prospect/discharged
            status = ClientStatus.PROSPECT

        # Debug: Show final status for first 5 clients
        if self._debug_count <= 5:
            logger.info(f"DEBUG Client {client_id}: Final status={status.value}")

        return WellSkyClient(
            id=client_id,
            first_name=first_name,
            last_name=last_name,
            status=status,
            address=address_str,
            city=city,
            state=state,
            zip_code=zip_code,
            phone=phone,
            email=email,
            referral_source=referral_source,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

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

        # Real API Implementation (FHIR)
        active = None
        if status == CaregiverStatus.ACTIVE:
            active = True
        elif status in (CaregiverStatus.INACTIVE, CaregiverStatus.TERMINATED):
            active = False

        page = offset // limit if limit > 0 else 0
        # search_practitioners defaults to is_hired=True, which is correct for caregivers
        return self.search_practitioners(active=active, limit=limit, page=page)

    def get_caregiver(self, caregiver_id: str) -> Optional[WellSkyCaregiver]:
        """Get a single caregiver by ID"""
        if self.is_mock_mode:
            return self._mock_caregivers.get(caregiver_id)

        return self.get_practitioner(caregiver_id)

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

        results = self.search_practitioners(phone=clean_phone, active=True, is_hired=True, limit=1)
        if results:
            return results[0]

        # FALLBACK: If mobile_phone search fails, get all active and filter manually
        # (Connect API can be picky about which phone field it searches)
        all_active = self.get_caregivers(status=CaregiverStatus.ACTIVE, limit=100)
        for cg in all_active:
            cg_clean = re.sub(r'[^\d]', '', cg.phone or '')[-10:]
            if cg_clean == clean_phone:
                return cg

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

    # =========================================================================
    # FHIR-Compliant Practitioner API (WellSky Connect API)
    # =========================================================================

    def search_practitioners(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        city: Optional[str] = None,
        active: Optional[bool] = None,
        is_hired: bool = True,
        profile_tags: Optional[List[str]] = None,
        limit: int = 20,
        page: int = 0
    ) -> List[WellSkyCaregiver]:
        """
        Search for practitioners (caregivers) using FHIR-compliant API.

        Uses POST /v1/practitioners/_search/ endpoint.

        Args:
            first_name: Filter by first name
            last_name: Filter by last name
            phone: Filter by phone number (10 digits)
            city: Filter by city
            active: Filter by active status (default True)
            is_hired: Filter by hired status (default True - only hired caregivers)
            profile_tags: List of profile tag IDs (skills/certifications)
            limit: Results per page (1-100, default 20)
            page: Page number (default 0)

        Returns:
            List of WellSkyCaregiver objects
        """
        if self.is_mock_mode:
            # Mock mode fallback
            results = list(self._mock_caregivers.values())
            if first_name:
                results = [c for c in results if c.first_name.lower().startswith(first_name.lower())]
            if last_name:
                results = [c for c in results if c.last_name.lower().startswith(last_name.lower())]
            if active:
                results = [c for c in results if c.is_active]
            return results[:limit]

        # Build search payload
        search_payload = {}

        if first_name:
            search_payload["first_name"] = first_name
        if last_name:
            search_payload["last_name"] = last_name
        if phone:
            # Clean phone to 10 digits
            import re
            clean_phone = re.sub(r'[^\d]', '', phone)[-10:]
            search_payload["mobile_phone"] = clean_phone
        if city:
            search_payload["city"] = city
        if active is not None:
            search_payload["active"] = "true" if active else "false"
        if is_hired is not None:
            search_payload["is_hired"] = "true" if is_hired else "false"
        if profile_tags:
            # Tags are comma-separated in API
            search_payload["tags"] = ",".join(str(t) for t in profile_tags)

        # Query parameters for pagination (agencyId added automatically by _make_request)
        params = {
            "_count": min(limit, 100),
            "_page": page
        }

        success, data = self._make_request(
            "POST",
            "practitioners/_search/",
            params=params,
            data=search_payload
        )

        if not success:
            logger.error(f"Practitioner search failed: {data}")
            return []

        # Parse FHIR Bundle response
        caregivers = []
        if data.get("resourceType") == "Bundle" and data.get("entry"):
            for entry in data["entry"]:
                try:
                    caregiver = self._parse_fhir_practitioner(entry)
                    caregivers.append(caregiver)
                except Exception as e:
                    logger.error(f"Error parsing practitioner: {e}")
                    continue

        logger.info(f"Found {len(caregivers)} practitioners matching search criteria")
        return caregivers

    def get_practitioner(self, practitioner_id: str) -> Optional[WellSkyCaregiver]:
        """
        Get a single practitioner by ID using FHIR-compliant API.

        Uses GET /v1/practitioners/{id}/ endpoint.

        Args:
            practitioner_id: WellSky practitioner ID

        Returns:
            WellSkyCaregiver object or None
        """
        if self.is_mock_mode:
            return self._mock_caregivers.get(practitioner_id)

        success, data = self._make_request("GET", f"practitioners/{practitioner_id}/")

        if not success:
            logger.error(f"Get practitioner {practitioner_id} failed: {data}")
            return None

        try:
            return self._parse_fhir_practitioner(data)
        except Exception as e:
            logger.error(f"Error parsing practitioner {practitioner_id}: {e}")
            return None

    def create_practitioner(
        self,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None,
        home_phone: Optional[str] = None,
        work_phone: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        state: str = "CO",
        zip_code: Optional[str] = None,
        gender: Optional[str] = None,
        birth_date: Optional[str] = None,
        ssn: Optional[str] = None,
        is_hired: bool = False,
        status_id: int = 10,
        profile_tags: Optional[List[str]] = None,
        languages: Optional[List[str]] = None
    ) -> Tuple[bool, Any]:
        """
        Create a new practitioner (caregiver/applicant) using FHIR API.
        POST /v1/practitioners/

        Args:
            first_name: First name (required)
            last_name: Last name (required)
            phone: Mobile phone (10 digits)
            home_phone: Home phone
            work_phone: Work phone
            email: Email address
            address: Street address
            city: City
            state: State (default "CO")
            zip_code: ZIP code
            gender: "male", "female", "other", "unknown"
            birth_date: Date of birth (YYYY-MM-DD)
            ssn: Social Security Number (XXX-XX-XXXX)
            is_hired: True for hired caregiver, False for applicant
            status_id: Status ID (10=New Applicant, 100=Hired, etc.)
            profile_tags: List of skill/certification tag IDs
            languages: List of language codes (e.g. ["en-us", "es"])
        """
        if self.is_mock_mode:
            cg_id = f"P{len(self._mock_caregivers) + 1:03d}"
            caregiver = WellSkyCaregiver(
                id=cg_id,
                first_name=first_name,
                last_name=last_name,
                phone=phone or "",
                email=email or "",
                city=city or "",
                state=state,
                status=CaregiverStatus.ACTIVE if is_hired else CaregiverStatus.APPLICANT,
                created_at=datetime.utcnow()
            )
            self._mock_caregivers[cg_id] = caregiver
            logger.info(f"Mock: Created practitioner {cg_id}")
            return True, {"resourceType": "Practitioner", "id": cg_id}

        fhir_practitioner = {
            "resourceType": "Practitioner",
            "active": True,
            "name": [
                {
                    "use": "official",
                    "family": last_name,
                    "given": [first_name]
                }
            ],
            "telecom": [],
            "address": [],
            "meta": {
                "tag": [
                    {"code": "agencyId", "display": self.agency_id},
                    {"code": "isHired", "display": "true" if is_hired else "false"},
                    {"code": "status", "display": str(status_id)}
                ]
            }
        }

        # Telecom
        if phone:
            import re
            clean = re.sub(r'[^\d]', '', phone)[-10:]
            fhir_practitioner["telecom"].append({"system": "phone", "value": clean, "use": "mobile"})
        if home_phone:
            import re
            clean = re.sub(r'[^\d]', '', home_phone)[-10:]
            fhir_practitioner["telecom"].append({"system": "phone", "value": clean, "use": "home"})
        if work_phone:
            import re
            clean = re.sub(r'[^\d]', '', work_phone)[-10:]
            fhir_practitioner["telecom"].append({"system": "phone", "value": clean, "use": "work"})
        if email:
            fhir_practitioner["telecom"].append({"system": "email", "value": email})

        # Address
        if address or city or state or zip_code:
            addr = {
                "use": "home",
                "line": [address] if address else [],
                "city": city or "",
                "state": state,
                "postalCode": zip_code or ""
            }
            fhir_practitioner["address"].append(addr)

        if gender:
            fhir_practitioner["gender"] = gender
        if birth_date:
            fhir_practitioner["birthDate"] = birth_date
        if ssn:
            fhir_practitioner["ssn"] = ssn

        # Profile tags (skills/certifications)
        if profile_tags:
            fhir_practitioner["meta"]["tag"].append({
                "code": "profileTags",
                "display": ",".join(str(t) for t in profile_tags)
            })

        # Languages
        if languages:
            fhir_practitioner["communication"] = [
                {"coding": [{"code": lang, "display": lang}]}
                for lang in languages
            ]

        success, response = self._make_request("POST", "practitioners/", data=fhir_practitioner)
        if success:
            prac_id = response.get("id", "unknown")
            logger.info(f"Created practitioner {prac_id} ({first_name} {last_name})")
        return success, response

    def update_practitioner(
        self,
        practitioner_id: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        home_phone: Optional[str] = None,
        work_phone: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        zip_code: Optional[str] = None,
        gender: Optional[str] = None,
        birth_date: Optional[str] = None,
        active: Optional[bool] = None,
        is_hired: Optional[bool] = None,
        status_id: Optional[int] = None,
        profile_tags: Optional[List[str]] = None,
        deactivation_reason: Optional[str] = None
    ) -> Tuple[bool, Any]:
        """
        Update an existing practitioner (caregiver/applicant).
        PUT /v1/practitioners/{id}/

        All fields optional - only provided fields are updated.

        Args:
            practitioner_id: WellSky practitioner ID
            first_name: Updated first name
            last_name: Updated last name
            phone: Mobile phone (10 digits)
            home_phone: Home phone
            work_phone: Work phone
            email: Email address
            address: Street address
            city: City
            state: State code
            zip_code: ZIP code
            gender: "male", "female", "other", "unknown"
            birth_date: Date of birth (YYYY-MM-DD)
            active: Active status
            is_hired: Hired status
            status_id: Status ID (10=New Applicant, 100=Hired, etc.)
            profile_tags: List of skill/certification tag IDs
            deactivation_reason: Reason for deactivation (e.g. "Terminated - Quit")
        """
        if self.is_mock_mode:
            caregiver = self._mock_caregivers.get(practitioner_id)
            if caregiver:
                if first_name is not None:
                    caregiver.first_name = first_name
                if last_name is not None:
                    caregiver.last_name = last_name
                if phone is not None:
                    caregiver.phone = phone
                if email is not None:
                    caregiver.email = email
                if city is not None:
                    caregiver.city = city
                logger.info(f"Mock: Updated practitioner {practitioner_id}")
                return True, {"success": True}
            return False, {"error": "Practitioner not found"}

        fhir_practitioner = {
            "resourceType": "Practitioner",
            "meta": {"tag": [{"code": "agencyId", "display": self.agency_id}]}
        }

        if active is not None:
            fhir_practitioner["active"] = active

        if first_name is not None or last_name is not None:
            name = {"use": "official"}
            if first_name is not None:
                name["given"] = [first_name]
            if last_name is not None:
                name["family"] = last_name
            fhir_practitioner["name"] = [name]

        # Telecom
        telecom = []
        if phone is not None:
            import re
            clean = re.sub(r'[^\d]', '', phone)[-10:]
            telecom.append({"system": "phone", "value": clean, "use": "mobile"})
        if home_phone is not None:
            import re
            clean = re.sub(r'[^\d]', '', home_phone)[-10:]
            telecom.append({"system": "phone", "value": clean, "use": "home"})
        if work_phone is not None:
            import re
            clean = re.sub(r'[^\d]', '', work_phone)[-10:]
            telecom.append({"system": "phone", "value": clean, "use": "work"})
        if email is not None:
            telecom.append({"system": "email", "value": email})
        if telecom:
            fhir_practitioner["telecom"] = telecom

        # Address
        if any(v is not None for v in [address, city, state, zip_code]):
            addr = {"use": "home"}
            if address is not None:
                addr["line"] = [address]
            if city is not None:
                addr["city"] = city
            if state is not None:
                addr["state"] = state
            if zip_code is not None:
                addr["postalCode"] = zip_code
            fhir_practitioner["address"] = [addr]

        if gender is not None:
            fhir_practitioner["gender"] = gender
        if birth_date is not None:
            fhir_practitioner["birthDate"] = birth_date

        # Meta tags
        if is_hired is not None:
            fhir_practitioner["meta"]["tag"].append({"code": "isHired", "display": "true" if is_hired else "false"})
        if status_id is not None:
            fhir_practitioner["meta"]["tag"].append({"code": "status", "display": str(status_id)})
        if profile_tags is not None:
            fhir_practitioner["meta"]["tag"].append({"code": "profileTags", "display": ",".join(str(t) for t in profile_tags)})
        if deactivation_reason is not None:
            fhir_practitioner["meta"]["tag"].append({"code": "deactivationReason", "display": deactivation_reason})

        success, response = self._make_request("PUT", f"practitioners/{practitioner_id}/", data=fhir_practitioner)
        if success:
            logger.info(f"Updated practitioner {practitioner_id}")
        return success, response

    def delete_practitioner(self, practitioner_id: str) -> Tuple[bool, Any]:
        """
        Delete a practitioner record.
        DELETE /v1/practitioners/{id}/

        Use with caution - this permanently removes the practitioner from WellSky.
        """
        if self.is_mock_mode:
            if practitioner_id in self._mock_caregivers:
                del self._mock_caregivers[practitioner_id]
                return True, {"success": True}
            return False, {"error": "Practitioner not found"}

        success, response = self._make_request("DELETE", f"practitioners/{practitioner_id}/")
        if success:
            logger.info(f"Deleted practitioner {practitioner_id}")
        return success, response

    def _parse_fhir_practitioner(self, fhir_data: Dict) -> WellSkyCaregiver:
        """
        Parse FHIR Practitioner resource into WellSkyCaregiver object.
        Handles both direct resource and Bundle entry wrapper.
        """
        # If this is a Bundle entry, extract the actual resource
        if "resource" in fhir_data:
            fhir_data = fhir_data["resource"]

        # Extract ID
        caregiver_id = str(fhir_data.get("id", ""))

        # Extract name
        first_name = ""
        last_name = ""
        if fhir_data.get("name"):
            name = fhir_data["name"][0]
            last_name = name.get("family", "")
            given = name.get("given", [])
            first_name = given[0] if given else ""

        # Extract phone and email
        phone = ""
        email = ""
        for telecom in fhir_data.get("telecom", []):
            system = telecom.get("system", "")
            value = telecom.get("value", "")
            if system == "phone" and telecom.get("use") in ["mobile", None]:
                phone = value
            elif system == "email":
                email = value

        # Extract address
        address_str = ""
        city = ""
        state = "CO"
        zip_code = ""
        lat = 0.0
        lon = 0.0
        if fhir_data.get("address"):
            addr = fhir_data["address"][0]
            address_str = ", ".join(addr.get("line", []))
            city = addr.get("city", "")
            state = addr.get("state", "CO")
            zip_code = addr.get("postalCode", "")

        # Extract status and metadata
        active = fhir_data.get("active", True)
        status = CaregiverStatus.ACTIVE if active else CaregiverStatus.INACTIVE

        is_hired = True
        profile_tags = []
        certifications = []

        for tag in fhir_data.get("meta", {}).get("tag", []):
            code = tag.get("code", "")
            display = tag.get("display", "")

            if code == "isHired":
                is_hired = display.lower() == "true"
            elif code == "profileTags" and display:
                # Parse comma-separated tag IDs
                profile_tags = [t.strip() for t in display.split(",") if t.strip()]

        # Determine status based on isHired flag
        if is_hired:
            status = CaregiverStatus.ACTIVE if active else CaregiverStatus.INACTIVE
        else:
            status = CaregiverStatus.APPLICANT

        # Extract languages
        languages = ["English"]
        for comm in fhir_data.get("communication", []):
            for coding in comm.get("coding", []):
                lang_code = coding.get("code", "")
                lang_display = coding.get("display", "")
                if lang_display and lang_display not in languages:
                    languages.append(lang_display)

        return WellSkyCaregiver(
            id=caregiver_id,
            first_name=first_name,
            last_name=last_name,
            status=status,
            phone=phone,
            email=email,
            address=address_str,
            city=city,
            state=state,
            zip_code=zip_code,
            lat=lat,
            lon=lon,
            certifications=profile_tags,  # Use profile tags as certifications
            languages=languages,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

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

        # Real API Implementation
        start_date = date_from or date.today()
        # Handle date range logic for additional_days
        days = 0
        if date_to:
            delta = (date_to - start_date).days
            days = max(0, min(delta, 6))  # Max 6 additional days per API limitation

        all_shifts = []

        if client_id or caregiver_id:
            # Direct search
            shifts = self.search_appointments(
                caregiver_id=caregiver_id,
                client_id=client_id,
                start_date=start_date,
                additional_days=days,
                limit=limit
            )
            all_shifts.extend(shifts)
        else:
            # Iterate through active clients if no IDs provided
            # This is heavy but necessary due to API limitations
            active_clients = self.get_clients(status=ClientStatus.ACTIVE, limit=1000)
            for client in active_clients:
                shifts = self.search_appointments(
                    client_id=client.id,
                    start_date=start_date,
                    additional_days=days,
                    limit=limit
                )
                all_shifts.extend(shifts)

        # Filter by status if needed (API doesn't support status filter in search)
        if status:
            all_shifts = [s for s in all_shifts if s.status == status]

        return all_shifts[:limit]

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

    # =========================================================================
    # FHIR-Compliant Appointment API (WellSky Connect API)
    # =========================================================================

    def search_appointments(
        self,
        caregiver_id: Optional[str] = None,
        client_id: Optional[str] = None,
        start_date: Optional[date] = None,
        additional_days: int = 0,
        week_no: Optional[str] = None,
        month_no: Optional[str] = None,
        limit: int = 20,
        page: int = 0
    ) -> List[WellSkyShift]:
        """
        Search for appointments (shifts) using FHIR-compliant API.

        Uses GET /v1/appointment/ or POST /v1/appointment/_search/ endpoint.

        Args:
            caregiver_id: Filter by caregiver/practitioner ID
            client_id: Filter by client/patient ID
            start_date: Start date for search (required if not using week_no/month_no)
            additional_days: Number of days after start_date (0-6)
            week_no: Week number in YYYYWW format (e.g., "202605")
            month_no: Month number in YYYYMM format (e.g., "202601")
            limit: Results per page (1-100, default 20)
            page: Page number (default 0)

        Returns:
            List of WellSkyShift objects

        Note: Either caregiver_id OR client_id is required.
              Either start_date OR week_no OR month_no is required.
        """
        if self.is_mock_mode:
            # Mock mode fallback
            results = list(self._mock_shifts.values())
            if caregiver_id:
                results = [s for s in results if s.caregiver_id == caregiver_id]
            if client_id:
                results = [s for s in results if s.client_id == client_id]
            if start_date:
                end_date = start_date + timedelta(days=additional_days)
                results = [s for s in results if s.date and start_date <= s.date <= end_date]
            return results[:limit]

        # Validate required parameters
        if not caregiver_id and not client_id:
            logger.error("Either caregiver_id or client_id is required for appointment search")
            return []

        if not start_date and not week_no and not month_no:
            logger.error("Either start_date, week_no, or month_no is required for appointment search")
            return []

        # Use POST _search endpoint for more complex queries
        use_post = True

        if use_post:
            # Build search payload
            search_payload = {}

            if caregiver_id:
                search_payload["caregiverId"] = str(caregiver_id)
            if client_id:
                search_payload["clientId"] = str(client_id)

            if start_date:
                # Format: YYYYMMDD
                search_payload["startDate"] = start_date.strftime("%Y%m%d")
                if additional_days > 0:
                    search_payload["additionalDays"] = str(min(additional_days, 6))
            elif week_no:
                search_payload["weekNo"] = week_no
            elif month_no:
                search_payload["monthNo"] = month_no

            # Query parameters for pagination
            params = {
                "_count": min(limit, 100),
                "_page": page
            }

            success, data = self._make_request(
                "POST",
                "appointment/_search/",
                params=params,
                data=search_payload
            )
        else:
            # Use GET endpoint with query string
            params = {
                "_count": min(limit, 100),
                "_page": page
            }

            if caregiver_id:
                params["caregiverId"] = caregiver_id
            if client_id:
                params["clientId"] = client_id
            if start_date:
                params["startDate"] = start_date.strftime("%Y%m%d")
                if additional_days > 0:
                    params["additionalDays"] = str(min(additional_days, 6))
            elif week_no:
                params["weekNo"] = week_no
            elif month_no:
                params["monthNo"] = month_no

            success, data = self._make_request(
                "GET",
                "appointment/",
                params=params
            )

        if not success:
            logger.error(f"Appointment search failed: {data}")
            return []

        # Parse FHIR Bundle response with pagination
        shifts = []
        if data.get("resourceType") == "Bundle" and data.get("entry"):
            for entry in data["entry"]:
                try:
                    shift = self._parse_fhir_appointment(entry)
                    shifts.append(shift)
                except Exception as e:
                    logger.error(f"Error parsing appointment: {e}")
                    continue

        # Auto-paginate: if we got a full page, fetch next pages
        total = data.get("total", len(shifts)) if isinstance(data, dict) else len(shifts)
        current_page = page
        while len(shifts) < total and len(shifts) >= (current_page + 1) * min(limit, 100):
            current_page += 1
            if current_page > 20:  # Safety cap
                break
            next_params = {
                "_count": min(limit, 100),
                "_page": current_page
            }
            if use_post:
                success2, data2 = self._make_request("POST", "appointment/_search/", params=next_params, data=search_payload)
            else:
                next_params.update({k: v for k, v in params.items() if k not in ("_count", "_page")})
                success2, data2 = self._make_request("GET", "appointment/", params=next_params)
            if not success2 or not isinstance(data2, dict):
                break
            entries = data2.get("entry", [])
            if not entries:
                break
            for entry in entries:
                try:
                    shift = self._parse_fhir_appointment(entry)
                    shifts.append(shift)
                except Exception as e:
                    logger.error(f"Error parsing appointment page {current_page}: {e}")
                    continue

        logger.info(f"Found {len(shifts)} appointments matching search criteria (pages: {current_page + 1})")
        return shifts

    def create_appointment(
        self,
        client_id: str,
        caregiver_id: str,
        start_datetime: str,
        end_datetime: str,
        status: str = "SCHEDULED",
        scheduled_items: Optional[List[Dict[str, str]]] = None,
        lat: float = None,
        lon: float = None
    ) -> Tuple[bool, Any]:
        """
        Create a new appointment (shift/visit).
        POST /v1/appointment/

        Args:
            client_id: WellSky patient/client ID
            caregiver_id: WellSky practitioner/caregiver ID
            start_datetime: ISO format start (e.g. "2026-02-05T08:00:00")
            end_datetime: ISO format end (e.g. "2026-02-05T12:00:00")
            status: "SCHEDULED", "COMPLETED", "CANCELLED"
            scheduled_items: List of service items [{"id": "123", "name": "Meal Prep"}]
            lat: GPS latitude for position
            lon: GPS longitude for position
        """
        if self.is_mock_mode:
            mock_id = f"APT{len(self._mock_shifts) + 1:05d}"
            logger.info(f"Mock: Created appointment {mock_id}")
            return True, {"resourceType": "Appointment", "id": mock_id}

        data = {
            "resourceType": "Appointment",
            "client": {"id": str(client_id)},
            "caregiver": {"id": str(caregiver_id)},
            "start": start_datetime,
            "end": end_datetime,
            "status": status
        }

        if scheduled_items:
            data["scheduledItems"] = scheduled_items

        if lat is not None and lon is not None:
            data["position"] = {"latitude": lat, "longitude": lon}

        success, response = self._make_request("POST", "appointment/", data=data)
        if success:
            apt_id = response.get("id", "unknown")
            logger.info(f"Created appointment {apt_id} for client {client_id} with caregiver {caregiver_id}")
        return success, response

    def delete_appointment(self, appointment_id: str) -> Tuple[bool, Any]:
        """
        Delete an appointment (shift).
        DELETE /v1/appointment/{id}/

        Use with caution - this permanently removes the scheduled shift.
        """
        if self.is_mock_mode:
            if appointment_id in self._mock_shifts:
                del self._mock_shifts[appointment_id]
                return True, {"success": True}
            return False, {"error": "Appointment not found"}

        success, response = self._make_request("DELETE", f"appointment/{appointment_id}/")
        if success:
            logger.info(f"Deleted appointment {appointment_id}")
        return success, response

    def update_appointment(self, appointment_id: str, update_data: Dict[str, Any]) -> Tuple[bool, Any]:
        """
        Updates an existing Appointment object in WellSky using a PUT request.

        This is the correct, RESTful way to modify an appointment, such as
        un-assigning a caregiver.

        Args:
            appointment_id: The ID of the appointment to update.
            update_data: The full JSON body of the appointment to PUT.

        Returns:
            A tuple of (success, response_data).
        """
        if self.is_mock_mode:
            logger.info(f"Mock: Updating appointment {appointment_id}")
            return True, {"status": "success", "id": appointment_id}

        # The endpoint for a specific appointment
        endpoint = f"appointment/{appointment_id}/"

        # The REST pattern is to PUT the entire modified object.
        success, response = self._make_request("PUT", endpoint, data=update_data)

        if success:
            logger.info(f"Successfully updated appointment {appointment_id}")
            return True, response
        else:
            logger.error(f"Failed to update appointment {appointment_id}: {response}")
            return False, response

    def get_appointment(self, appointment_id: str) -> Optional[WellSkyShift]:
        """
        Get a single appointment by ID using FHIR-compliant API.

        Uses GET /v1/appointment/{id}/ endpoint.

        Args:
            appointment_id: WellSky appointment ID

        Returns:
            WellSkyShift object or None
        """
        if self.is_mock_mode:
            return self._mock_shifts.get(appointment_id)

        success, data = self._make_request("GET", f"appointment/{appointment_id}/")

        if not success:
            logger.error(f"Get appointment {appointment_id} failed: {data}")
            return None

        try:
            return self._parse_fhir_appointment(data)
        except Exception as e:
            logger.error(f"Error parsing appointment {appointment_id}: {e}")
            return None

    def _parse_fhir_appointment(self, fhir_data: Dict) -> WellSkyShift:
        """
        Parse FHIR Appointment resource into WellSkyShift object.
        Handles both direct resource and Bundle entry wrapper.
        """
        # If this is a Bundle entry, extract the actual resource
        if "resource" in fhir_data:
            fhir_data = fhir_data["resource"]

        from datetime import datetime as dt

        # Extract IDs
        shift_id = str(fhir_data.get("id", ""))

        # Extract caregiver and client
        caregiver_data = fhir_data.get("caregiver", {})
        caregiver_id = caregiver_data.get("id", "")

        client_data = fhir_data.get("client", {})
        client_id = client_data.get("id", "")

        # Extract dates/times (in UTC)
        start_str = fhir_data.get("start", "")
        end_str = fhir_data.get("end", "")

        try:
            shift_start = dt.fromisoformat(start_str.replace("Z", "+00:00"))
        except:
            shift_start = dt.utcnow()

        try:
            shift_end = dt.fromisoformat(end_str.replace("Z", "+00:00"))
        except:
            shift_end = shift_start + timedelta(hours=4)

        # Extract status
        status_str = fhir_data.get("status", "SCHEDULED").upper()
        status_map = {
            "SCHEDULED": ShiftStatus.SCHEDULED,
            "CONFIRMED": ShiftStatus.CONFIRMED,
            "IN_PROGRESS": ShiftStatus.IN_PROGRESS,
            "COMPLETED": ShiftStatus.COMPLETED,
            "MISSED": ShiftStatus.MISSED,
            "CANCELLED": ShiftStatus.CANCELLED,
            "OPEN": ShiftStatus.OPEN
        }
        status = status_map.get(status_str, ShiftStatus.SCHEDULED)

        # Extract location
        position = fhir_data.get("position", {})
        client_lat = position.get("latitude", 0.0)
        client_lon = position.get("longitude", 0.0)

        # Extract tasks
        tasks = []
        for task_data in fhir_data.get("tasks", []):
            tasks.append({
                "id": task_data.get("id", ""),
                "description": task_data.get("description", ""),
                "status": task_data.get("status", "NOT_COMPLETE")
            })

        # Calculate duration
        duration_hours = (shift_end - shift_start).total_seconds() / 3600.0

        return WellSkyShift(
            id=shift_id,
            client_id=client_id,
            caregiver_id=caregiver_id,
            status=status,
            date=shift_start.date(),
            start_time=shift_start.strftime("%H:%M"),
            end_time=shift_end.strftime("%H:%M"),
            duration_hours=duration_hours,
            client_first_name="",  # Not in FHIR appointment - need to fetch separately
            client_last_name="",
            caregiver_first_name="",  # Not in FHIR appointment - need to fetch separately
            caregiver_last_name="",
            address="",
            city=""
        )

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

    def _map_legacy_client_status(self, raw: Optional[str]) -> ClientStatus:
        if not raw:
            return ClientStatus.ACTIVE
        normalized = raw.strip().lower()
        if normalized in ("active", "current"):
            return ClientStatus.ACTIVE
        if normalized in ("discharged", "inactive", "closed"):
            return ClientStatus.DISCHARGED
        if normalized in ("pending", "on_hold", "on hold"):
            return ClientStatus.PENDING
        return ClientStatus.ACTIVE

    def _map_legacy_shift_status(self, raw: Optional[str]) -> ShiftStatus:
        if not raw:
            return ShiftStatus.SCHEDULED
        normalized = raw.strip().lower()
        if normalized in ("scheduled", "confirmed"):
            return ShiftStatus.SCHEDULED
        if normalized in ("in progress", "in_progress", "inprogress"):
            return ShiftStatus.IN_PROGRESS
        if normalized in ("completed", "complete"):
            return ShiftStatus.COMPLETED
        if normalized in ("missed", "no_show", "no show"):
            return ShiftStatus.MISSED
        if normalized in ("cancelled", "canceled"):
            return ShiftStatus.CANCELLED
        if normalized in ("open",):
            return ShiftStatus.OPEN
        return ShiftStatus.SCHEDULED

    def _parse_legacy_client(self, data: Dict) -> WellSkyClient:
        status = self._map_legacy_client_status(data.get("status") or data.get("clientStatus"))
        return WellSkyClient(
            id=str(data.get("clientId", data.get("id", ""))),
            first_name=data.get("firstName", ""),
            last_name=data.get("lastName", ""),
            status=status,
            phone=data.get("phoneNumber", data.get("phone", "")),
            email=data.get("email", ""),
            address=data.get("address", ""),
            city=data.get("city", ""),
            zip=data.get("zip", ""),
            assigned_caregivers=[],
            notes=data.get("notes", ""),
            created_at=self._parse_datetime(data.get("createdDate", data.get("createdAt"))),
            updated_at=self._parse_datetime(data.get("modifiedDate", data.get("updatedAt")))
        )

    def _parse_legacy_caregiver(self, data: Dict) -> WellSkyCaregiver:
        status_raw = data.get("status") or data.get("employeeStatus") or data.get("employmentStatus")
        status = CaregiverStatus.ACTIVE if (str(status_raw).lower() in ("active", "current", "true")) else CaregiverStatus.INACTIVE
        return WellSkyCaregiver(
            id=str(data.get("employeeId", data.get("id", ""))),
            first_name=data.get("firstName", ""),
            last_name=data.get("lastName", ""),
            status=status,
            phone=data.get("phoneNumber", data.get("phone", "")),
            email=data.get("email", ""),
            city=data.get("city", ""),
            available_days=data.get("availableDays", []),
            languages=data.get("languages", []),
            certifications=data.get("certifications", []),
            notes=data.get("notes", "")
        )

    def _parse_legacy_visit(self, data: Dict) -> WellSkyShift:
        start_dt = self._parse_datetime(
            data.get("scheduledStartTime") or data.get("startTime") or data.get("startDateTime")
        )
        end_dt = self._parse_datetime(
            data.get("scheduledEndTime") or data.get("endTime") or data.get("endDateTime")
        )
        clock_in = self._parse_datetime(
            data.get("clockInTime") or data.get("actualStartTime")
        )
        clock_out = self._parse_datetime(
            data.get("clockOutTime") or data.get("actualEndTime")
        )

        status = self._map_legacy_shift_status(data.get("status"))
        shift_date = start_dt.date() if start_dt else None
        start_time = start_dt.strftime("%H:%M") if start_dt else ""
        end_time = end_dt.strftime("%H:%M") if end_dt else ""
        duration_hours = 0.0
        if start_dt and end_dt:
            duration_hours = (end_dt - start_dt).total_seconds() / 3600.0

        return WellSkyShift(
            id=str(data.get("visitId", data.get("id", ""))),
            client_id=str(data.get("clientId", "")),
            caregiver_id=str(data.get("employeeId", "")) or None,
            status=status,
            date=shift_date,
            start_time=start_time,
            end_time=end_time,
            duration_hours=duration_hours,
            clock_in_time=clock_in,
            clock_out_time=clock_out,
            client_first_name=data.get("clientFirstName", ""),
            client_last_name=data.get("clientLastName", ""),
            caregiver_first_name=data.get("employeeFirstName", ""),
            caregiver_last_name=data.get("employeeLastName", ""),
            address=data.get("clientAddress", ""),
            city=data.get("clientCity", "")
        )

    def clock_in_shift(self, appointment_id: str, lat: float = 39.7392, lon: float = -104.9903, notes: str = "") -> Tuple[bool, str]:
        """
        Clock in to a shift using FHIR Encounter API.
        POST /v1/encounter/<appointment_id>/clockin/
        """
        if self.is_mock_mode:
            logger.info(f"Mock: Clocked in to shift {appointment_id}")
            return True, "Clocked in successfully (Mock)"

        endpoint = f"encounter/{appointment_id}/clockin/"
        data = {
            "resourceType": "Encounter",
            "period": {
                "start": datetime.utcnow().isoformat() + "Z"
            },
            "position": {
                "latitude": lat,
                "longitude": lon
            }
        }

        success, response = self._make_request("POST", endpoint, data=data)
        if success:
            return True, f"Clocked in successfully. Carelog ID: {response.get('id')}"
        return False, response.get("error", "Unknown error during clock-in")

    def clock_out_shift(self, carelog_id_or_appointment_id: str, lat: float = 39.7392, lon: float = -104.9903, notes: str = "") -> Tuple[bool, str]:
        """
        Clock out of a shift using FHIR Encounter API.
        PUT /v1/encounter/<carelog_id>/clockout/
        
        If an appointment_id is passed instead of a carelog_id, we first 
        call clockin to get the existing carelog ID.
        """
        if self.is_mock_mode:
            logger.info(f"Mock: Clocked out of shift {carelog_id_or_appointment_id}")
            return True, "Clocked out successfully (Mock)"

        target_id = carelog_id_or_appointment_id

        endpoint = f"encounter/{target_id}/clockout/"
        data = {
            "resourceType": "Encounter",
            "period": {
                "end": datetime.utcnow().isoformat() + "Z"
            },
            "position": {
                "latitude": lat,
                "longitude": lon
            },
            "generalComment": notes[:1000]
        }

        success, response = self._make_request("PUT", endpoint, data=data)
        if success:
            return True, "Clocked out successfully"

        # Fallback: if 404, maybe it was an appointment_id?
        if not success and isinstance(response, dict) and response.get("status_code") == 404:
             logger.info(f"Clock out 404 for {target_id}, attempting ID resolution via clockin...")
             in_success, in_resp = self.clock_in_shift(target_id, lat, lon)
             if in_success:
                 import re
                 match = re.search(r"Carelog ID: (\d+)", in_resp)
                 if match:
                     resolved_id = match.group(1)
                     return self.clock_out_shift(resolved_id, lat, lon, notes)

        return False, response.get("error", "Unknown error during clock-out")

    def create_task_log(
        self,
        encounter_id: str,
        title: str,
        description: str,
        status: str = "NOT_COMPLETE",
        show_in_family_room: bool = False
    ) -> Tuple[bool, Any]:
        """
        Create a TaskLog object in WellSky for a specific encounter.
        POST /v1/encounter/{encounter_id}/tasklog/

        THIS IS THE WORKING WAY TO DOCUMENT IN WELLSKY!
        - Shows up as "Shift Notes" in mobile app and dashboard
        - Requires encounter_id (NOT appointment_id)
        - Get encounter_id from clock_in_shift() response
        """
        if self.is_mock_mode:
            logger.info(f"Mock: Created task log for encounter {encounter_id}")
            return True, {"success": True, "taskLogId": 12345}

        endpoint = f"encounter/{encounter_id}/tasklog/"
        data = {
            "resourceType": "TaskLog",
            "status": status,
            "title": title,
            "description": description,
            "recorded": datetime.utcnow().isoformat() + "Z",
            "show_in_family_room": show_in_family_room
        }

        success, response = self._make_request("POST", endpoint, data=data)
        if success:
            logger.info(f"Successfully created TaskLog for encounter {encounter_id}")
            return True, response
        return False, response

    def get_task_logs(self, encounter_id: str) -> Tuple[bool, Any]:
        """
        Get task logs for a specific encounter.
        GET /v1/encounter/{encounter_id}/tasklog/

        Returns list of tasks/notes associated with the shift.
        """
        if self.is_mock_mode:
            return True, {"entry": [], "total": 0}

        endpoint = f"encounter/{encounter_id}/tasklog/"
        success, response = self._make_request("GET", endpoint)
        if success:
            logger.info(f"Got {response.get('total', 0)} task logs for encounter {encounter_id}")
        return success, response

    def update_task(
        self,
        encounter_id: str,
        task_id: str,
        status: str = "COMPLETE",
        comment: str = ""
    ) -> Tuple[bool, Any]:
        """
        Update a shift task status.
        PUT /v1/encounter/{encounter_id}/task/{task_id}/

        Args:
            encounter_id: The encounter/carelog ID
            task_id: The task ID within the shift
            status: "COMPLETE" or "NOT_COMPLETE"
            comment: Required when status is NOT_COMPLETE
        """
        if self.is_mock_mode:
            return True, {"success": True}

        endpoint = f"encounter/{encounter_id}/task/{task_id}/"
        data = {
            "resourceType": "Task",
            "status": status,
        }
        if comment:
            data["comment"] = comment

        success, response = self._make_request("PUT", endpoint, data=data)
        if success:
            logger.info(f"Updated task {task_id} on encounter {encounter_id} to {status}")
        return success, response

    def update_task_log(
        self,
        encounter_id: str,
        tasklog_id: str,
        title: str = None,
        description: str = None,
        status: str = None,
        comment: str = None,
        show_in_family_room: bool = None
    ) -> Tuple[bool, Any]:
        """
        Update an existing task log.
        PUT /v1/encounter/{encounter_id}/tasklog/{tasklog_id}/
        """
        if self.is_mock_mode:
            return True, {"success": True}

        endpoint = f"encounter/{encounter_id}/tasklog/{tasklog_id}/"
        data = {"resourceType": "TaskLog"}
        if title is not None:
            data["title"] = title
        if description is not None:
            data["description"] = description
        if status is not None:
            data["status"] = status
        if comment is not None:
            data["comment"] = comment
        if show_in_family_room is not None:
            data["show_in_family_room"] = show_in_family_room

        success, response = self._make_request("PUT", endpoint, data=data)
        if success:
            logger.info(f"Updated tasklog {tasklog_id} on encounter {encounter_id}")
        return success, response

    # =========================================================================
    # Encounter CRUD API
    # =========================================================================

    def create_encounter(
        self,
        patient_id: str,
        practitioner_id: str,
        start_datetime: str,
        end_datetime: str,
        status: str = "COMPLETE",
        bill_rate_method: str = "Hourly",
        bill_rate_id: str = None,
        pay_rate_method: str = "Hourly",
        pay_rate_id: str = None
    ) -> Tuple[bool, Any]:
        """
        Create a new encounter (care log) directly.
        POST /v1/encounter/

        Args:
            patient_id: WellSky patient/client ID
            practitioner_id: WellSky practitioner/caregiver ID
            start_datetime: ISO format start time (e.g. "2026-01-29T14:00:00")
            end_datetime: ISO format end time (e.g. "2026-01-29T18:00:00")
            status: "COMPLETE", "IN_PROGRESS", etc.
            bill_rate_method: "Hourly", "notBillable", "perVisit", "liveIn"
            pay_rate_method: "Hourly", "notPayable", "perVisit", "liveIn"
            bill_rate_id: Optional rate ID for billing
            pay_rate_id: Optional rate ID for pay
        """
        if self.is_mock_mode:
            logger.info(f"Mock: Created encounter for patient {patient_id}")
            return True, {"resourceType": "Encounter", "id": "mock-encounter-123"}

        endpoint = "encounter/"
        data = {
            "resourceType": "Encounter",
            "agencyId": str(self.agency_id),
            "status": status,
            "patientId": patient_id,
            "practitionerId": practitioner_id,
            "startDateTime": start_datetime,
            "endDateTime": end_datetime,
            "billRateMethod": bill_rate_method,
            "payRateMethod": pay_rate_method,
        }
        if bill_rate_id:
            data["billRateId"] = bill_rate_id
        if pay_rate_id:
            data["payRateId"] = pay_rate_id

        success, response = self._make_request("POST", endpoint, data=data)
        if success:
            enc_id = response.get("id", "unknown")
            logger.info(f"Created encounter {enc_id} for patient {patient_id} with practitioner {practitioner_id}")
        return success, response

    def get_encounter(self, encounter_id: str) -> Tuple[bool, Any]:
        """
        Get a specific encounter (care log) by ID.
        GET /v1/encounter/{id}/

        Returns encounter details including patient, practitioner, period,
        appointment reference, and rate information.
        """
        if self.is_mock_mode:
            return True, {"resourceType": "Encounter", "id": encounter_id, "status": "COMPLETE"}

        endpoint = f"encounter/{encounter_id}/"
        success, response = self._make_request("GET", endpoint)
        if success:
            logger.info(f"Got encounter {encounter_id}")
        return success, response

    def search_encounters(
        self,
        client_id: str = None,
        caregiver_id: str = None,
        start_date: str = None,
        end_date: str = None,
        count: int = 30,
        page: int = 1,
        sort: str = "-startDate"
    ) -> Tuple[bool, Any]:
        """
        Search encounters (care logs).
        POST /v1/encounter/_search/

        Args:
            client_id: Filter by patient/client ID
            caregiver_id: Filter by practitioner/caregiver ID
            start_date: Start date filter (format: YYYYMMDD)
            end_date: End date filter (format: YYYYMMDD)
            count: Records per page (default: 30)
            page: Page number (default: 1)
            sort: Sort field, prefix with '-' for descending (default: -startDate)
        """
        if self.is_mock_mode:
            return True, {"entry": [], "total": 0}

        endpoint = "encounter/_search/"
        params = {"_count": count, "_page": page, "_sort": sort}
        data = {}
        if client_id:
            data["clientId"] = client_id
        if caregiver_id:
            data["caregiverId"] = caregiver_id
        if start_date:
            data["startDate"] = start_date
        if end_date:
            data["endDate"] = end_date

        success, response = self._make_request("POST", endpoint, params=params, data=data)
        if success:
            total = response.get("total", len(response.get("entry", [])))
            logger.info(f"Found {total} encounters")
        return success, response

    def search_chargeitems(
        self,
        client_id: str = None,
        caregiver_id: str = None,
        start_date: str = None,
        end_date: str = None,
        count: int = 100,
        page: int = 1,
        sort: str = "-startDate"
    ) -> Tuple[bool, Any]:
        """
        Search charge items (billing records) for hours tracking.
        POST /v1/chargeitem/_search/

        ChargeItem is specifically designed for billing and has actual:
        - Bill rates and amounts
        - Pay rates and amounts
        - Hours (quantity)
        - Price totals

        Args:
            client_id: Filter by patient/client ID (optional)
            caregiver_id: Filter by practitioner/caregiver ID (optional)
            start_date: Start date filter (format: YYYYMMDD or integer)
            end_date: End date filter (format: YYYYMMDD or integer)
            count: Records per page (default: 100)
            page: Page number (default: 1)
            sort: Sort field (default: -startDate)
        """
        if self.is_mock_mode:
            return True, {"entry": [], "totalRecords": 0}

        endpoint = "chargeitem/_search/"
        params = {"_count": count, "_page": page, "_sort": sort}
        data = {}
        if start_date:
            # ChargeItem expects integer date format
            data["startDate"] = int(start_date) if isinstance(start_date, str) else start_date
        if end_date:
            data["endDate"] = int(end_date) if isinstance(end_date, str) else end_date
        if client_id:
            data["clientId"] = int(client_id) if isinstance(client_id, str) else client_id
        if caregiver_id:
            data["caregiverId"] = int(caregiver_id) if isinstance(caregiver_id, str) else caregiver_id

        success, response = self._make_request("POST", endpoint, params=params, data=data)
        if success:
            logger.info(f"ChargeItem search: {response.get('totalRecords', 0)} results")
        return success, response

    def update_encounter(
        self,
        encounter_id: str,
        status: str = None,
        start_datetime: str = None,
        end_datetime: str = None,
        practitioner_id: str = None,
        bill_rate_method: str = None,
        bill_rate_id: str = None,
        pay_rate_method: str = None,
        pay_rate_id: str = None
    ) -> Tuple[bool, Any]:
        """
        Update an existing encounter (care log).
        PUT /v1/encounter/{id}/

        All fields optional - only provided fields are updated.
        """
        if self.is_mock_mode:
            return True, {"success": True}

        endpoint = f"encounter/{encounter_id}/"
        data = {"resourceType": "Encounter", "agencyId": str(self.agency_id)}
        if status is not None:
            data["status"] = status
        if start_datetime is not None:
            data["startDateTime"] = start_datetime
        if end_datetime is not None:
            data["endDateTime"] = end_datetime
        if practitioner_id is not None:
            data["practitionerId"] = practitioner_id
        if bill_rate_method is not None:
            data["billRateMethod"] = bill_rate_method
        if bill_rate_id is not None:
            data["billRateId"] = bill_rate_id
        if pay_rate_method is not None:
            data["payRateMethod"] = pay_rate_method
        if pay_rate_id is not None:
            data["payRateId"] = pay_rate_id

        success, response = self._make_request("PUT", endpoint, data=data)
        if success:
            logger.info(f"Updated encounter {encounter_id}")
        return success, response

    def delete_encounter(self, encounter_id: str) -> Tuple[bool, Any]:
        """
        Delete an encounter (care log).
        DELETE /v1/encounter/{id}/
        """
        if self.is_mock_mode:
            return True, {"success": True}

        endpoint = f"encounter/{encounter_id}/"
        success, response = self._make_request("DELETE", endpoint)
        if success:
            logger.info(f"Deleted encounter {encounter_id}")
        return success, response

    # =========================================================================
    # DocumentReference API
    # =========================================================================

    def create_document_reference(
        self,
        patient_id: str,
        document_type: str,
        content_type: str,
        data_base64: str,
        description: str = "",
        date: str = None
    ) -> Tuple[bool, Any]:
        """
        Upload/create a document attached to a patient profile.
        POST /v1/documentreference/

        Args:
            patient_id: WellSky patient/client ID
            document_type: Type code (e.g. "clinical-note", "care-plan", "assessment")
            content_type: MIME type (e.g. "application/pdf", "image/jpeg", "text/plain")
            data_base64: Base64-encoded document content
            description: Human-readable description
            date: ISO date when document was created (default: now)
        """
        if self.is_mock_mode:
            logger.info(f"Mock: Created document for patient {patient_id}")
            return True, {"resourceType": "DocumentReference", "id": "mock-doc-123"}

        if date is None:
            date = datetime.utcnow().isoformat() + "Z"

        endpoint = "documentreference/"
        doc_data = {
            "resourceType": "DocumentReference",
            "subject": {"reference": f"Patient/{patient_id}"},
            "type": {
                "coding": [{"code": document_type, "display": document_type}]
            },
            "description": description,
            "date": date,
            "content": [
                {
                    "attachment": {
                        "contentType": content_type,
                        "data": data_base64
                    }
                }
            ]
        }

        success, response = self._make_request("POST", endpoint, data=doc_data)
        if success:
            doc_id = response.get("id", "unknown")
            logger.info(f"Created DocumentReference {doc_id} for patient {patient_id}")
        return success, response

    def create_clinical_note(
        self,
        patient_id: str,
        title: str,
        note_text: str,
        source: str = "gigi_ai"
    ) -> Tuple[bool, Any]:
        """
        Create a clinical note on a client's WellSky profile via DocumentReference API.

        This is the RELIABLE way to document in WellSky:
        - Works for ANY client (no encounter/shift needed)
        - Shows in WellSky under client's Documents tab
        - Uses text/plain content type for readable notes
        """
        import base64
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        formatted = f"[{timestamp}] [{source.upper()}]\n{title}\n\n{note_text}"
        data_b64 = base64.b64encode(formatted.encode('utf-8')).decode('utf-8')

        success, response = self.create_document_reference(
            patient_id=patient_id,
            document_type="clinical-note",
            content_type="text/plain",
            data_base64=data_b64,
            description=title[:200],
        )

        if success:
            doc_id = response.get("id", "unknown") if isinstance(response, dict) else "unknown"
            logger.info(f"Clinical note created for patient {patient_id}: {title[:60]} (DocRef {doc_id})")
        else:
            logger.warning(f"Clinical note FAILED for patient {patient_id}: {response}")

        return success, response

    def get_document_reference(self, document_id: str) -> Tuple[bool, Any]:
        """
        Get a specific document reference by ID.
        GET /v1/documentreference/{id}/

        Returns document metadata and content (base64-encoded).
        """
        if self.is_mock_mode:
            return True, {"resourceType": "DocumentReference", "id": document_id}

        endpoint = f"documentreference/{document_id}/"
        success, response = self._make_request("GET", endpoint)
        if success:
            logger.info(f"Got DocumentReference {document_id}")
        return success, response

    def search_document_references(
        self,
        patient_id: str = None,
        document_type: str = None,
        date_from: str = None,
        date_to: str = None,
        count: int = 30,
        page: int = 1
    ) -> Tuple[bool, Any]:
        """
        Search document references.
        POST /v1/documentreference/_search/

        Args:
            patient_id: Filter by patient/client ID
            document_type: Filter by document type code
            date_from: Start date filter (ISO format)
            date_to: End date filter (ISO format)
            count: Records per page (default: 30)
            page: Page number (default: 1)
        """
        if self.is_mock_mode:
            return True, {"entry": [], "total": 0}

        endpoint = "documentreference/_search/"
        params = {"_count": count, "_page": page}
        data = {}
        if patient_id:
            data["subject"] = f"Patient/{patient_id}"
        if document_type:
            data["type"] = document_type
        if date_from:
            data["date"] = f"ge{date_from}"
        if date_to:
            if "date" in data:
                data["dateTo"] = f"le{date_to}"
            else:
                data["date"] = f"le{date_to}"

        success, response = self._make_request("POST", endpoint, params=params, data=data)
        if success:
            total = response.get("total", len(response.get("entry", [])))
            logger.info(f"Found {total} document references")
        return success, response

    def update_document_reference(
        self,
        document_id: str,
        description: str = None,
        document_type: str = None,
        content_type: str = None,
        data_base64: str = None
    ) -> Tuple[bool, Any]:
        """
        Update an existing document reference.
        PUT /v1/documentreference/{id}/

        All fields optional - only provided fields are updated.
        """
        if self.is_mock_mode:
            return True, {"success": True}

        endpoint = f"documentreference/{document_id}/"
        data = {"resourceType": "DocumentReference"}
        if description is not None:
            data["description"] = description
        if document_type is not None:
            data["type"] = {
                "coding": [{"code": document_type, "display": document_type}]
            }
        if content_type is not None or data_base64 is not None:
            attachment = {}
            if content_type is not None:
                attachment["contentType"] = content_type
            if data_base64 is not None:
                attachment["data"] = data_base64
            data["content"] = [{"attachment": attachment}]

        success, response = self._make_request("PUT", endpoint, data=data)
        if success:
            logger.info(f"Updated DocumentReference {document_id}")
        return success, response

    def delete_document_reference(self, document_id: str) -> Tuple[bool, Any]:
        """
        Delete a document reference.
        DELETE /v1/documentreference/{id}/
        """
        if self.is_mock_mode:
            return True, {"success": True}

        endpoint = f"documentreference/{document_id}/"
        success, response = self._make_request("DELETE", endpoint)
        if success:
            logger.info(f"Deleted DocumentReference {document_id}")
        return success, response

    # =========================================================================
    # Subscription API (Webhooks)
    # =========================================================================

    def create_subscription(
        self,
        criteria: str,
        endpoint_url: str,
        reason: str = "Gigi AI real-time monitoring",
        auth_header: str = None,
        payload_type: str = "application/fhir+json"
    ) -> Tuple[bool, Any]:
        """
        Create a webhook subscription for real-time event notifications.
        POST /v1/subscriptions/

        Args:
            criteria: Event type to subscribe to. Available criteria:
                - admintask.created / admintask.changed / admintask.status.changed / admintask.status.complete
                - agency_admin.created / agency_admin.deactivated.changed
                - encounter.clockout.changed
                - patient.created / patient.name.changed / patient.address.changed
                - patient.telecom.changed / patient.deactivated.changed / patient.dateofdeath.changed
                - prospect.status.changed
                - practitioner.created / practitioner.name.changed / practitioner.address.changed
                - practitioner.telecom.changed / practitioner.deactivated.changed
                - applicant.status.changed
                - referralsources.created / referralsources.changed
            endpoint_url: Your webhook URL that will receive POST notifications
            reason: Human-readable reason for the subscription
            auth_header: Authorization header value sent with webhook calls
            payload_type: Content type for webhook payload (default: application/fhir+json)
        """
        if self.is_mock_mode:
            logger.info(f"Mock: Created subscription for {criteria}")
            return True, {"resourceType": "Subscription", "id": 999}

        data = {
            "resourceType": "Subscription",
            "status": "active",
            "criteria": criteria,
            "reason": reason,
            "channel": {
                "type": "rest-hook",
                "endpoint": endpoint_url,
                "payload": payload_type
            },
            "meta": {
                "tag": [
                    {"code": "agencyId", "display": str(self.agency_id)}
                ]
            }
        }

        if auth_header:
            data["channel"]["header"] = [f"Authorization: {auth_header}"]

        success, response = self._make_request("POST", "subscriptions/", data=data)
        if success:
            sub_id = response.get("id", "unknown")
            logger.info(f"Created subscription {sub_id} for {criteria} -> {endpoint_url}")
        return success, response

    def get_subscription(self, subscription_id: str) -> Tuple[bool, Any]:
        """
        Get a specific subscription by ID.
        GET /v1/subscriptions/{id}/
        """
        if self.is_mock_mode:
            return True, {"resourceType": "Subscription", "id": subscription_id, "status": "active"}

        endpoint = f"subscriptions/{subscription_id}/"
        success, response = self._make_request("GET", endpoint)
        if success:
            logger.info(f"Got subscription {subscription_id}")
        return success, response

    def search_subscriptions(
        self,
        status: str = None,
        criteria: str = None,
        contact_email: str = None
    ) -> Tuple[bool, Any]:
        """
        List/search active subscriptions.
        GET /v1/subscriptions/

        Args:
            status: Filter by status (e.g. "active")
            criteria: Filter by event type (e.g. "encounter.clockout.changed")
            contact_email: Filter by subscriber email
        """
        if self.is_mock_mode:
            return True, {"entry": [], "total": 0}

        params = {}
        if status:
            params["status"] = status
        if criteria:
            params["criteria"] = criteria
        if contact_email:
            params["contact_email"] = contact_email

        success, response = self._make_request("GET", "subscriptions/", params=params)
        if success:
            total = len(response.get("entry", []))
            logger.info(f"Found {total} subscriptions")
        return success, response

    def update_subscription(
        self,
        subscription_id: str,
        status: str = None,
        criteria: str = None,
        endpoint_url: str = None,
        reason: str = None,
        auth_header: str = None
    ) -> Tuple[bool, Any]:
        """
        Update an existing subscription.
        PUT /v1/subscriptions/{id}/

        All fields optional - only provided fields are updated.
        """
        if self.is_mock_mode:
            return True, {"success": True}

        data = {"resourceType": "Subscription"}
        if status is not None:
            data["status"] = status
        if criteria is not None:
            data["criteria"] = criteria
        if reason is not None:
            data["reason"] = reason
        if endpoint_url is not None or auth_header is not None:
            channel = {"type": "rest-hook"}
            if endpoint_url is not None:
                channel["endpoint"] = endpoint_url
            if auth_header is not None:
                channel["header"] = [f"Authorization: {auth_header}"]
            data["channel"] = channel

        endpoint = f"subscriptions/{subscription_id}/"
        success, response = self._make_request("PUT", endpoint, data=data)
        if success:
            logger.info(f"Updated subscription {subscription_id}")
        return success, response

    def delete_subscription(self, subscription_id: str) -> Tuple[bool, Any]:
        """
        Delete a subscription (stop receiving webhook notifications).
        DELETE /v1/subscriptions/{id}/
        """
        if self.is_mock_mode:
            return True, {"success": True}

        endpoint = f"subscriptions/{subscription_id}/"
        success, response = self._make_request("DELETE", endpoint)
        if success:
            logger.info(f"Deleted subscription {subscription_id}")
        return success, response

    # =========================================================================
    # ProfileTags API (Skills / Certifications)
    # =========================================================================

    def create_profile_tag(
        self,
        name: str,
        description: str = "",
        tag_type: str = "skill"
    ) -> Tuple[bool, Any]:
        """
        Create a new profile tag (skill/certification).
        POST /v1/profileTags/

        Tags are assigned to practitioners via the profileTags meta tag
        (comma-separated IDs) when creating/updating practitioners.

        Args:
            name: Tag name (e.g. "CNA", "CPR Certified", "Alzheimer's Care")
            description: Optional description of the skill/certification
            tag_type: Tag category (e.g. "skill", "certification", "language")
        """
        if self.is_mock_mode:
            logger.info(f"Mock: Created profile tag '{name}'")
            return True, {"id": "mock-tag-123", "name": name}

        data = {
            "name": name,
            "description": description,
            "type": tag_type
        }

        success, response = self._make_request("POST", "profileTags/", data=data)
        if success:
            tag_id = response.get("id", "unknown")
            logger.info(f"Created profile tag {tag_id}: {name}")
        return success, response

    def get_profile_tag(self, tag_id: str) -> Tuple[bool, Any]:
        """
        Get a specific profile tag by ID.
        GET /v1/profileTags/{id}/
        """
        if self.is_mock_mode:
            return True, {"id": tag_id, "name": "Mock Tag"}

        endpoint = f"profileTags/{tag_id}/"
        success, response = self._make_request("GET", endpoint)
        if success:
            logger.info(f"Got profile tag {tag_id}")
        return success, response

    def search_profile_tags(
        self,
        name: str = None,
        tag_type: str = None,
        count: int = 100,
        page: int = 1
    ) -> Tuple[bool, Any]:
        """
        List/search profile tags.
        GET /v1/profileTags/

        Args:
            name: Filter by tag name
            tag_type: Filter by tag type
            count: Records per page (default: 100)
            page: Page number (default: 1)
        """
        if self.is_mock_mode:
            return True, {"entry": [], "total": 0}

        params = {"_count": count, "_page": page}
        if name:
            params["name"] = name
        if tag_type:
            params["type"] = tag_type

        success, response = self._make_request("GET", "profileTags/", params=params)
        if success:
            total = len(response.get("entry", [])) if isinstance(response, dict) else 0
            logger.info(f"Found {total} profile tags")
        return success, response

    def update_profile_tag(
        self,
        tag_id: str,
        name: str = None,
        description: str = None,
        tag_type: str = None
    ) -> Tuple[bool, Any]:
        """
        Update an existing profile tag.
        PUT /v1/profileTags/{id}/

        All fields optional - only provided fields are updated.
        """
        if self.is_mock_mode:
            return True, {"success": True}

        data = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if tag_type is not None:
            data["type"] = tag_type

        endpoint = f"profileTags/{tag_id}/"
        success, response = self._make_request("PUT", endpoint, data=data)
        if success:
            logger.info(f"Updated profile tag {tag_id}")
        return success, response

    def delete_profile_tag(self, tag_id: str) -> Tuple[bool, Any]:
        """
        Delete a profile tag.
        DELETE /v1/profileTags/{id}/
        """
        if self.is_mock_mode:
            return True, {"success": True}

        endpoint = f"profileTags/{tag_id}/"
        success, response = self._make_request("DELETE", endpoint)
        if success:
            logger.info(f"Deleted profile tag {tag_id}")
        return success, response

    # =========================================================================
    # RelatedPerson API (Family / Emergency Contacts)
    # =========================================================================

    def get_related_persons(self, patient_id: str) -> Tuple[bool, Any]:
        """
        Get all related persons (family/emergency contacts) for a patient.
        GET /v1/relatedperson/{patient_id}/

        Returns FHIR Bundle with entry[].resource containing:
          - id, name, telecom, address, relationship, emergencyContact,
            primaryContact, payer, poa
        """
        if self.is_mock_mode:
            return True, {"entry": [], "total": 0}

        endpoint = f"relatedperson/{patient_id}/"
        success, response = self._make_request("GET", endpoint)
        if success:
            total = len(response.get("entry", []))
            logger.info(f"Got {total} related persons for patient {patient_id}")
        return success, response

    def create_related_person(
        self,
        patient_id: str,
        first_name: str,
        last_name: str,
        relationship_code: str,
        phone: str = None,
        home_phone: str = None,
        work_phone: str = None,
        email: str = None,
        city: str = None,
        state: str = None,
        is_emergency_contact: bool = False,
        is_primary_contact: bool = False,
        is_payer: bool = False,
        is_poa: bool = False
    ) -> Tuple[bool, Any]:
        """
        Create a related person (family/emergency contact) for a patient.
        POST /v1/relatedperson/

        Args:
            patient_id: WellSky patient/client ID
            first_name: Contact's first name
            last_name: Contact's last name
            relationship_code: Relationship code (FTH, MTH, SPS, SON, DAU,
                BRO, SIS, DOCTOR, SOCIAL_WORKER, NURSE, FRND, NBOR, etc.)
            phone: Mobile phone (10 digits, no country code)
            home_phone: Home phone
            work_phone: Work phone
            email: Email address
            city: City
            state: State
            is_emergency_contact: Mark as emergency contact
            is_primary_contact: Mark as primary contact
            is_payer: Mark as payer
            is_poa: Mark as power of attorney
        """
        if self.is_mock_mode:
            logger.info(f"Mock: Created related person {first_name} {last_name} for patient {patient_id}")
            return True, {"resourceType": "RelatedPerson", "id": "mock-rp-123"}

        endpoint = "relatedperson/"
        data = {
            "resourceType": "RelatedPerson",
            "patient": {"reference": f"Patient/{patient_id}"},
            "name": [
                {
                    "given": [first_name],
                    "family": last_name
                }
            ],
            "relationship": {
                "coding": [{"code": relationship_code}]
            },
            "emergencyContact": is_emergency_contact,
            "primaryContact": is_primary_contact,
            "payer": is_payer,
            "poa": is_poa
        }

        # Build telecom array
        telecom = []
        if phone:
            telecom.append({"system": "phone", "value": phone, "use": "mobile"})
        if home_phone:
            telecom.append({"system": "phone", "value": home_phone, "use": "home"})
        if work_phone:
            telecom.append({"system": "phone", "value": work_phone, "use": "work"})
        if email:
            telecom.append({"system": "email", "value": email})
        if telecom:
            data["telecom"] = telecom

        # Build address
        if city or state:
            address = {}
            if city:
                address["city"] = city
            if state:
                address["state"] = state
            data["address"] = [address]

        success, response = self._make_request("POST", endpoint, data=data)
        if success:
            rp_id = response.get("id", "unknown")
            logger.info(f"Created RelatedPerson {rp_id} ({first_name} {last_name}) for patient {patient_id}")
        return success, response

    def search_related_persons(
        self,
        patient_id: str = None,
        name: str = None,
        phone: str = None,
        count: int = 30,
        page: int = 1
    ) -> Tuple[bool, Any]:
        """
        Search related persons across all patients.
        POST /v1/relatedperson/_search/

        Args:
            patient_id: Filter by patient/client ID
            name: Search by name
            phone: Search by phone number
            count: Records per page (default: 30)
            page: Page number (default: 1)
        """
        if self.is_mock_mode:
            return True, {"entry": [], "total": 0}

        endpoint = "relatedperson/_search/"
        params = {"_count": count, "_page": page}
        data = {}
        if patient_id:
            data["patient"] = patient_id
        if name:
            data["name"] = name
        if phone:
            data["phone"] = phone

        success, response = self._make_request("POST", endpoint, params=params, data=data)
        if success:
            total = response.get("total", len(response.get("entry", [])))
            logger.info(f"Found {total} related persons")
        return success, response

    def update_related_person(
        self,
        contact_id: str,
        first_name: str = None,
        last_name: str = None,
        relationship_code: str = None,
        phone: str = None,
        home_phone: str = None,
        work_phone: str = None,
        email: str = None,
        city: str = None,
        state: str = None,
        is_emergency_contact: bool = None,
        is_primary_contact: bool = None,
        is_payer: bool = None,
        is_poa: bool = None
    ) -> Tuple[bool, Any]:
        """
        Update an existing related person.
        PUT /v1/relatedperson/{contact_id}/

        All fields optional - only provided fields are updated.
        """
        if self.is_mock_mode:
            return True, {"success": True}

        endpoint = f"relatedperson/{contact_id}/"
        data = {"resourceType": "RelatedPerson"}

        if first_name is not None or last_name is not None:
            name = {}
            if first_name is not None:
                name["given"] = [first_name]
            if last_name is not None:
                name["family"] = last_name
            data["name"] = [name]

        if relationship_code is not None:
            data["relationship"] = {"coding": [{"code": relationship_code}]}

        # Build telecom if any phone/email provided
        telecom = []
        if phone is not None:
            telecom.append({"system": "phone", "value": phone, "use": "mobile"})
        if home_phone is not None:
            telecom.append({"system": "phone", "value": home_phone, "use": "home"})
        if work_phone is not None:
            telecom.append({"system": "phone", "value": work_phone, "use": "work"})
        if email is not None:
            telecom.append({"system": "email", "value": email})
        if telecom:
            data["telecom"] = telecom

        if city is not None or state is not None:
            address = {}
            if city is not None:
                address["city"] = city
            if state is not None:
                address["state"] = state
            data["address"] = [address]

        if is_emergency_contact is not None:
            data["emergencyContact"] = is_emergency_contact
        if is_primary_contact is not None:
            data["primaryContact"] = is_primary_contact
        if is_payer is not None:
            data["payer"] = is_payer
        if is_poa is not None:
            data["poa"] = is_poa

        success, response = self._make_request("PUT", endpoint, data=data)
        if success:
            logger.info(f"Updated RelatedPerson {contact_id}")
        return success, response

    def delete_related_person(self, patient_id: str, contact_id: str) -> Tuple[bool, Any]:
        """
        Remove a related person from a patient.
        DELETE /v1/relatedperson/{patient_id}/contacts/{contact_id}/
        """
        if self.is_mock_mode:
            return True, {"success": True}

        endpoint = f"relatedperson/{patient_id}/contacts/{contact_id}/"
        success, response = self._make_request("DELETE", endpoint)
        if success:
            logger.info(f"Deleted RelatedPerson {contact_id} from patient {patient_id}")
        return success, response

    def document_shift_interaction(
        self,
        appointment_id: str,
        title: str,
        description: str,
        clock_in_if_needed: bool = True,
        lat: float = 39.7392,
        lon: float = -104.9903
    ) -> Tuple[bool, str]:
        """
        HIGH-LEVEL METHOD: Document an interaction on a shift in WellSky.

        This is the CORRECT way to add documentation that shows in WellSky dashboard.
        Uses the Encounter/TaskLog pattern:
        1. Clock in to create encounter (if not already clocked in)
        2. Add TaskLog to the encounter

        Args:
            appointment_id: The shift's appointment ID
            title: Short title for the note (e.g., "Gigi AI - SMS Confirmation")
            description: Full description of the interaction
            clock_in_if_needed: If True, clock in to create encounter if needed
            lat/lon: GPS coordinates for clock-in (defaults to Denver)

        Returns:
            Tuple of (success, message)
        """
        if self.is_mock_mode:
            logger.info(f"Mock: Documented shift {appointment_id}: {title}")
            return True, "Shift documented (Mock)"

        # Step 1: Try to clock in (idempotent - returns existing encounter if already clocked in)
        if clock_in_if_needed:
            success, result = self.clock_in_shift(appointment_id, lat, lon)
            if not success:
                logger.warning(f"Clock-in failed for {appointment_id}: {result}")
                return False, f"Could not access shift: {result}"

            # Extract encounter_id from result
            import re
            match = re.search(r"Carelog ID: (\d+)", result)
            if match:
                encounter_id = match.group(1)
            else:
                logger.error(f"Could not extract encounter_id from clock-in response: {result}")
                return False, "Could not get encounter ID from clock-in"
        else:
            # Caller must provide encounter_id as appointment_id
            encounter_id = appointment_id

        # Step 2: Add TaskLog to the encounter
        success, response = self.create_task_log(
            encounter_id=encounter_id,
            title=title,
            description=description,
            status="COMPLETE",
            show_in_family_room=False
        )

        if success:
            task_log_id = response.get("taskLogId", "unknown")
            logger.info(f"Documented shift {appointment_id} → encounter {encounter_id} → tasklog {task_log_id}")
            return True, f"Shift documented in WellSky (TaskLog ID: {task_log_id})"

        return False, f"TaskLog creation failed: {response}"

    def add_note_to_client(
        self,
        client_id: str,
        note: str,
        note_type: str = "general",
        source: str = "gigi_ai",
        title: str = ""
    ) -> Tuple[bool, str]:
        """
        Add a note to a client's profile in WellSky.
        ALWAYS logs to local database first for guaranteed documentation trail.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        formatted_note = f"[{timestamp}] [{source.upper()}] [{note_type}] {note}"

        # =====================================================================
        # ALWAYS log to local database FIRST (Documentation Trail - 24/7/365)
        # This ensures documentation is preserved even if WellSky API fails
        # =====================================================================
        local_logged = False
        try:
            import sqlite3
            conn = sqlite3.connect('portal.db')
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gigi_documentation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_type TEXT NOT NULL,
                    person_id TEXT NOT NULL,
                    note TEXT NOT NULL,
                    note_type TEXT,
                    source TEXT,
                    wellsky_synced INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                INSERT INTO gigi_documentation_log (person_type, person_id, note, note_type, source, wellsky_synced)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', ('client', client_id, formatted_note, note_type, source))
            conn.commit()
            conn.close()
            local_logged = True
            logger.info(f"Local: Documented client note for {client_id}")
        except Exception as db_err:
            logger.error(f"Local DB error (client note): {db_err}")

        if self.is_mock_mode:
            logger.info(f"Mock: Added note to client {client_id}")
            return True, "Note added (Mock)"

        # CLOUD SYNC: Connect API (FHIR)
        # Strategy: Find a recent encounter, create TaskLog on it.
        # Uses progressively wider search windows and retries across encounters
        # (some encounter IDs are invalid for TaskLog despite appearing in search).
        if self.api_mode == "connect":
            for days_back in [7, 30, 90]:
                try:
                    start_date = (date.today() - timedelta(days=days_back)).strftime("%Y%m%d")
                    end_date = (date.today() + timedelta(days=1)).strftime("%Y%m%d")

                    search_payload = {
                        "clientId": str(client_id),
                        "startDate": start_date,
                        "endDate": end_date
                    }
                    params = {"_count": 5, "_sort": "-date"}

                    success, data = self._make_request(
                        "POST", "encounter/_search/", params=params, data=search_payload
                    )

                    if not success or not data.get("entry"):
                        continue  # Try wider window

                    # Try each encounter until one accepts the TaskLog
                    for encounter_entry in data["entry"]:
                        resource = encounter_entry.get("resource", encounter_entry)
                        encounter_id = resource.get("id")
                        if not encounter_id:
                            continue

                        tl_title = title if title else note_type.replace("_", " ").title()
                        tl_data = {
                            "resourceType": "TaskLog",
                            "status": "COMPLETE",
                            "title": tl_title,
                            "description": note,
                            "recorded": datetime.utcnow().isoformat() + "Z",
                            "show_in_family_room": False
                        }

                        success_tl, resp_tl = self._make_request(
                            "POST", f"encounter/{encounter_id}/tasklog/", data=tl_data
                        )

                        if success_tl:
                            try:
                                conn = sqlite3.connect('portal.db')
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE gigi_documentation_log
                                    SET wellsky_synced = 1
                                    WHERE person_type = 'client' AND person_id = ?
                                    ORDER BY created_at DESC LIMIT 1
                                ''', (client_id,))
                                conn.commit()
                                conn.close()
                            except:
                                pass
                            logger.info(f"Synced client note to WellSky Encounter {encounter_id} ({days_back}d window)")
                            return True, f"Note synced to WellSky (Encounter {encounter_id})"
                        else:
                            logger.debug(f"Encounter {encounter_id} rejected TaskLog, trying next...")

                except Exception as e:
                    logger.error(f"Error syncing note ({days_back}d window): {e}")

        # Fallback: No encounter found — log locally only (do NOT create AdminTask)
        # AdminTasks flood the WellSky Tasks dashboard with documentation entries.
        # The local gigi_documentation_log table preserves the full documentation trail.
        logger.info(f"No encounter for client {client_id} in 90-day window. Note saved locally only (no AdminTask).")

        logger.warning(f"All WellSky sync methods failed for client {client_id}. Note saved locally only.")
        return True, "Note documented locally (all WellSky sync methods failed)"

    def add_note_to_prospect(
        self,
        prospect_id: str,
        note: str,
        note_type: str = "general",
        source: str = "gigi_ai"
    ) -> Tuple[bool, str]:
        """
        Add a note to a prospect's profile in WellSky.
        ALWAYS logs to local database first for guaranteed documentation trail.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        formatted_note = f"[{timestamp}] [{source.upper()}] [{note_type}] {note}"

        # =====================================================================
        # ALWAYS log to local database FIRST (Documentation Trail - 24/7/365)
        # This ensures documentation is preserved even if WellSky API fails
        # =====================================================================
        local_logged = False
        try:
            import sqlite3
            conn = sqlite3.connect('portal.db')
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gigi_documentation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_type TEXT NOT NULL,
                    person_id TEXT NOT NULL,
                    note TEXT NOT NULL,
                    note_type TEXT,
                    source TEXT,
                    wellsky_synced INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                INSERT INTO gigi_documentation_log (person_type, person_id, note, note_type, source, wellsky_synced)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', ('prospect', prospect_id, formatted_note, note_type, source))
            conn.commit()
            conn.close()
            local_logged = True
            logger.info(f"Local: Documented prospect note for {prospect_id}")
        except Exception as db_err:
            logger.error(f"Local DB error (prospect note): {db_err}")

        if self.is_mock_mode:
            logger.info(f"Mock: Added note to prospect {prospect_id}")
            return True, "Note added (Mock)"

        # WellSky Connect API does not support prospect notes.
        # Legacy API is decommissioned (404).
        # We rely on the local database log.
        logger.info(f"Local: Prospect note for {prospect_id} saved to database. (Cloud sync skipped)")
        return True, "Note documented locally"



    # =========================================================================
    # EVV / Clock In-Out Methods (Used by Gigi AI Agent)
    # =========================================================================

    def get_caregiver_shifts_today(self, phone: str) -> List[WellSkyShift]:
        """
        Get all shifts for a caregiver today, looked up by phone number.
        """
        caregiver = self.get_caregiver_by_phone(phone)
        today = date.today()

        if caregiver:
            logger.info(f"Fetching shifts for caregiver ID: {caregiver.id}")
            shifts = self.get_shifts(
                caregiver_id=str(caregiver.id),
                date_from=today,
                date_to=today
            )
            if shifts:
                return shifts

        # AGGRESSIVE FALLBACK: Get ALL shifts for today and filter manually
        # This handles cases where caregiver/shift link is weird in the API
        logger.info(f"ID-based shift lookup failed for {phone}, scanning all agency shifts for today...")
        all_shifts = self.get_shifts(date_from=today, date_to=today, limit=500)
        import re
        clean_phone = re.sub(r'[^\d]', '', phone)[-10:]

        matched_shifts = []
        for s in all_shifts:
            # Match by caregiver phone if available in shift object
            if hasattr(s, 'caregiver_phone') and s.caregiver_phone:
                if re.sub(r'[^\d]', '', s.caregiver_phone)[-10:] == clean_phone:
                    matched_shifts.append(s)
                    continue

            # Match by name if we found a caregiver record earlier
            if caregiver and s.caregiver_id == caregiver.id:
                matched_shifts.append(s)

        logger.info(f"Aggressive scan found {len(matched_shifts)} shifts for {phone}")
        return matched_shifts

    def get_caregiver_current_shift(self, phone: str) -> Optional[WellSkyShift]:
        """
        Get the shift a caregiver is currently working or about to start.
        """
        shifts = self.get_caregiver_shifts_today(phone)
        if not shifts:
            return None

        # If only one shift today, assume it is the target (high flexibility for SMS)
        if len(shifts) == 1:
            logger.info(f"Only one shift found for {phone} today, using it.")
            return shifts[0]

        now = datetime.now()

        # First, look for in-progress shift (clocked in, not clocked out)
        for shift in shifts:
            if shift.clock_in_time and not shift.clock_out_time:
                return shift
            if shift.status == ShiftStatus.IN_PROGRESS:
                return shift

        # Next, look for shift starting soon (within 4 hours for SMS flexibility)
        for shift in shifts:
            if shift.status in (ShiftStatus.SCHEDULED, ShiftStatus.CONFIRMED):
                if shift.start_time and shift.date:
                    try:
                        start_dt = datetime.combine(
                            shift.date,
                            datetime.strptime(shift.start_time, "%H:%M").time()
                        )
                        # Check if within 4 hours
                        if -60 <= (start_dt - now).total_seconds() / 60 <= 240:
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

        # Connect API (FHIR) - Encounter clock-in
        endpoint = f"encounter/{shift_id}/clockin/"
        data = {
            "resourceType": "Encounter",
            "period": {
                "start": clock_in_time.isoformat()
            },
            "position": {
                "latitude": lat,
                "longitude": lon
            }
        }

        success, response = self._make_request("POST", endpoint, data=data)
        if success:
            return True, f"Clocked in at {clock_in_time.strftime('%I:%M %p')}"
        return False, response.get("error", "Failed to clock in")

        # Legacy and connect branches return above.

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

        # Connect API (FHIR) - Encounter clock-out
        endpoint = f"encounter/{shift_id}/clockout/"
        data = {
            "resourceType": "Encounter",
            "period": {
                "end": clock_out_time.isoformat()
            },
            "position": {
                "latitude": 39.7392,
                "longitude": -104.9903
            },
            "generalComment": notes[:1000]
        }

        success, response = self._make_request("PUT", endpoint, data=data)
        if success:
            return True, f"Clocked out at {clock_out_time.strftime('%I:%M %p')}"

        # If using appointment_id instead of carelog_id, try clock-in to resolve
        if isinstance(response, dict) and response.get("status_code") == 404:
            in_success, in_msg = self.clock_in_shift(shift_id, lat=39.7392, lon=-104.9903, notes=notes)
            if in_success:
                # Try clockout again with the same ID, since clockin is idempotent and may return carelog internally
                success, response = self._make_request("PUT", endpoint, data=data)
                if success:
                    return True, f"Clocked out at {clock_out_time.strftime('%I:%M %p')}"

        return False, response.get("error", "Failed to clock out")

        # Legacy and connect branches return above.

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

        return self.get_appointment(shift_id)

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

    def get_hours_breakdown(self, days: int = 30) -> Dict[str, Any]:
        """
        Get detailed hours breakdown for billing and payroll tracking.

        Uses WellSky Encounter API (completed care logs) to get actual billing
        and payroll hours with rate information.

        Returns hours aggregated by period (weekly/monthly/quarterly) with:
        - Total hours
        - Billing hours (regular + overtime)
        - Payroll hours (regular + overtime)
        - Average hours per client
        - Average hours per caregiver
        """
        from collections import defaultdict

        # Define time periods
        today = date.today()
        periods = {
            "weekly": (today - timedelta(days=7), today),
            "monthly": (today - timedelta(days=30), today),
            "quarterly": (today - timedelta(days=90), today),
        }

        result = {}
        has_real_data = False

        for period_name, (start_date, end_date) in periods.items():
            try:
                # STRATEGY: Get all active clients, then aggregate their ChargeItems
                logger.info(f"Getting hours breakdown for {period_name}...")

                # STEP 1: Get all active clients
                clients = self.get_clients(status=ClientStatus.ACTIVE, limit=500)
                logger.info(f"Found {len(clients)} active clients")

                if not clients:
                    logger.warning(f"No active clients found for {period_name}")
                    completed_encounters = []
                else:
                    # STEP 2: For each client, get their Encounters
                    start_str = start_date.strftime("%Y%m%d")
                    end_str = end_date.strftime("%Y%m%d")

                    all_encounters = []
                    for i, client in enumerate(clients):
                        if i % 20 == 0:
                            logger.info(f"Processing client {i+1}/{len(clients)}...")

                        try:
                            success, response = self.search_encounters(
                                client_id=client.id,
                                start_date=start_str,
                                end_date=end_str,
                                count=100
                            )

                            if success and response:
                                entries = response.get("entry", [])
                                for entry in entries:
                                    resource = entry.get("resource", entry)
                                    # Only completed encounters
                                    if resource.get("status") in ("COMPLETE", "complete"):
                                        all_encounters.append(resource)
                        except Exception as e:
                            logger.debug(f"Error getting encounters for client {client.id}: {e}")
                            continue

                    completed_encounters = all_encounters
                    logger.info(f"Found {len(completed_encounters)} encounters for {period_name}")

                if len(completed_encounters) > 0:
                    has_real_data = True

                # Calculate total hours from ChargeItem data
                total_hours = 0.0
                billing_total = 0.0
                payroll_total = 0.0

                # Track unique clients and caregivers
                unique_clients = set()
                unique_caregivers = set()

                # Group by caregiver to calculate regular/overtime
                caregiver_hours = defaultdict(float)

                for item in completed_encounters:
                    try:
                        # ChargeItem uses "occurrencePeriod", Encounter uses "period"
                        period = item.get("occurrencePeriod") or item.get("period", {})
                        start_str = period.get("start")
                        end_str = period.get("end")

                        # ChargeItem has "quantity" field with hours
                        quantity = item.get("quantity", {})
                        hours_from_quantity = quantity.get("value", 0) if isinstance(quantity, dict) else 0

                        if start_str and end_str:
                            # Parse ISO timestamps
                            start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                            end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                            duration_hours = (end_dt - start_dt).total_seconds() / 3600.0
                        elif hours_from_quantity > 0:
                            # Use quantity if no period
                            duration_hours = float(hours_from_quantity)
                        else:
                            continue

                        total_hours += duration_hours

                        # Track caregiver hours for overtime calc
                        # ChargeItem uses "performer", Encounter uses "participant"
                        performers = item.get("performer", [])
                        if performers:
                            for performer in performers:
                                caregiver_ref = performer.get("reference", "")
                                if caregiver_ref and "Practitioner" in caregiver_ref:
                                    caregiver_id = caregiver_ref.split("/")[-1]
                                    caregiver_hours[caregiver_id] += duration_hours
                                    unique_caregivers.add(caregiver_id)

                        # Also check participant (for Encounters)
                        participant = item.get("participant", {})
                        if participant:
                            individual = participant.get("Individual", [{}])[0] if isinstance(participant.get("Individual"), list) else {}
                            caregiver_ref = individual.get("reference", "")
                            if caregiver_ref:
                                caregiver_id = caregiver_ref.split("/")[-1]
                                caregiver_hours[caregiver_id] += duration_hours
                                unique_caregivers.add(caregiver_id)

                        # Track client
                        subject = item.get("subject", {})
                        client_ref = subject.get("reference", "")
                        if client_ref:
                            client_id = client_ref.split("/")[-1]
                            unique_clients.add(client_id)

                        # Get billing and payroll hours from rates
                        rates = item.get("rates", {})
                        bill_rates = rates.get("billRate", [])
                        pay_rates = rates.get("payRate", [])

                        if bill_rates and isinstance(bill_rates, list):
                            billing_total += duration_hours

                        if pay_rates and isinstance(pay_rates, list):
                            payroll_total += duration_hours

                    except Exception as e:
                        logger.debug(f"Error parsing chargeitem: {e}")
                        continue

                # Calculate regular vs overtime (assuming 40 hrs/week threshold)
                weeks_in_period = (end_date - start_date).days / 7.0
                weekly_threshold = 40.0
                period_threshold = weekly_threshold * weeks_in_period

                payroll_regular = 0.0
                payroll_overtime = 0.0
                for caregiver_id, hours in caregiver_hours.items():
                    if hours <= period_threshold:
                        payroll_regular += hours
                    else:
                        payroll_regular += period_threshold
                        payroll_overtime += (hours - period_threshold)

                # For billing, apply same regular/OT split
                billing_regular = payroll_regular
                billing_overtime = payroll_overtime

                # If we didn't get billing/payroll from rates, use calculated totals
                if billing_total == 0:
                    billing_total = total_hours
                if payroll_total == 0:
                    payroll_total = total_hours

                # Calculate averages
                avg_hours_per_client = total_hours / len(unique_clients) if unique_clients else 0
                avg_hours_per_caregiver = total_hours / len(unique_caregivers) if unique_caregivers else 0

                result[period_name] = {
                    "total_hours": round(total_hours, 2),
                    "billing": {
                        "total": round(billing_total, 2),
                        "regular": round(billing_regular, 2),
                        "overtime": round(billing_overtime, 2),
                    },
                    "payroll": {
                        "total": round(payroll_total, 2),
                        "regular": round(payroll_regular, 2),
                        "overtime": round(payroll_overtime, 2),
                    },
                    "averages": {
                        "per_client": round(avg_hours_per_client, 2),
                        "per_caregiver": round(avg_hours_per_caregiver, 2),
                    },
                    "unique_clients": len(unique_clients),
                    "unique_caregivers": len(unique_caregivers),
                    "shift_count": len(completed_encounters),
                }

            except Exception as e:
                logger.error(f"Error calculating hours breakdown for {period_name}: {e}")
                result[period_name] = {
                    "total_hours": 0,
                    "billing": {"total": 0, "regular": 0, "overtime": 0},
                    "payroll": {"total": 0, "regular": 0, "overtime": 0},
                    "averages": {"per_client": 0, "per_caregiver": 0},
                    "unique_clients": 0,
                    "unique_caregivers": 0,
                    "shift_count": 0,
                }

        # If WellSky is connected but has no shift data, add a note
        if not self.is_mock_mode and not has_real_data:
            result["data_note"] = "WellSky connected but no shift data found in FHIR appointments. Hours data may be available through WellSky Analytics/Reporting API."
            logger.warning("WellSky connected but no shift data available")

        result["generated_at"] = datetime.utcnow().isoformat()
        result["data_source"] = "mock" if self.is_mock_mode else "wellsky_api"

        return result

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
        clients = []
        caregivers = []
        shifts = []
        open_shifts = []
        care_plans_due = []

        try:
            clients = self.get_clients(status=ClientStatus.ACTIVE)
        except Exception as e:
            logger.error(f"Failed to get clients for summary: {e}")

        try:
            caregivers = self.get_caregivers(status=CaregiverStatus.ACTIVE)
        except Exception as e:
            logger.error(f"Failed to get caregivers for summary: {e}")

        try:
            shifts = self.get_shifts(
                date_from=date.today() - timedelta(days=days),
                date_to=date.today()
            )
        except Exception as e:
            logger.error(f"Failed to get shifts for summary: {e}")

        try:
            open_shifts = self.get_open_shifts()
        except Exception as e:
            logger.error(f"Failed to get open shifts for summary: {e}")

        try:
            care_plans_due = self.get_care_plans_due_for_review()
        except Exception as e:
            logger.error(f"Failed to get care plans for summary: {e}")

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

    # =========================================================================
    # GIGI AI AGENT METHODS - New features for production readiness
    # =========================================================================

    def _make_legacy_request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        data: Dict = None
    ) -> Tuple[bool, Any, int]:
        """
        Make authenticated API request to the legacy WellSky (ClearCare) API.
        """
        if not self.is_configured:
            return False, {"error": "API not configured"}, 0

        token = self._get_access_token()
        if not token:
            return False, {"error": "Authentication failed"}, 0

        url = f"{LEGACY_API_HOST}/api/v1/agencies/{self.agency_id}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, params=params, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data, params=params, timeout=30)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, params=params, timeout=30)
            else:
                return False, {"error": f"Unsupported method: {method}"}, 0

            if response.status_code in (200, 201):
                return True, response.json(), response.status_code
            elif response.status_code == 204:
                return True, {}, response.status_code
            else:
                return False, response.text, response.status_code

        except Exception as e:
            logger.error(f"Legacy WellSky API error: {e}")
            return False, str(e), 0

    def create_admin_task(
        self,
        title: str,
        description: str,
        due_date: Optional[date] = None,
        assigned_to: Optional[str] = None,
        related_client_id: Optional[str] = None,
        related_caregiver_id: Optional[str] = None,
        priority: str = "normal"
    ) -> Tuple[bool, Any]:
        """
        Create an administrative task in WellSky via POST /v1/adminTasks/.

        AdminTasks show up in the WellSky dashboard and can relate to
        patients (clients) or practitioners (caregivers).
        """
        # Always log to local database first (Documentation Trail)
        try:
            import sqlite3
            conn = sqlite3.connect('portal.db')
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wellsky_documentation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT,
                    title TEXT,
                    description TEXT,
                    related_id TEXT,
                    wellsky_task_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            related_id = related_client_id or related_caregiver_id or "N/A"
            cursor.execute('''
                INSERT INTO wellsky_documentation (type, title, description, related_id)
                VALUES (?, ?, ?, ?)
            ''', ('TASK', title, description, related_id))
            conn.commit()
            conn.close()
            logger.info(f"Logged admin task locally: {title}")
        except Exception as e:
            logger.error(f"Failed to log task locally: {e}")

        if self.is_mock_mode:
            return True, {"id": "mock-task-1", "resourceType": "Task"}

        # Build requester list from related client/caregiver
        requester = []
        if related_client_id:
            requester.append({"resourceType": "Patient", "id": int(related_client_id)})
        if related_caregiver_id:
            requester.append({"resourceType": "Practitioner", "id": int(related_caregiver_id)})
        if not requester:
            # Must have at least one requester — use agency-level
            requester.append(int(self.agency_id))

        exec_date = date.today().isoformat()
        due = due_date.isoformat() + "T23:59:59" if due_date else (date.today() + timedelta(days=1)).isoformat() + "T23:59:59"

        task_data = {
            "status": "received",  # "received" = Not Complete (open task)
            "description": f"{title}\n\n{description}"[:5000],
            "executionDate": exec_date,
            "dueDate": due,
            "requester": requester,
            "owner": [],  # Unassigned — will appear in admin task queue
            "meta": {
                "tag": [
                    {"code": "agencyId", "display": self.agency_id}
                ]
            }
        }

        if assigned_to:
            task_data["owner"] = [int(assigned_to)]

        success, response = self._make_request("POST", "adminTasks/", data=task_data)

        if success:
            task_id = response.get("id", "unknown") if isinstance(response, dict) else "unknown"
            logger.info(f"Created WellSky AdminTask {task_id}: {title[:60]}")
            # Update local record with WellSky task ID
            try:
                import sqlite3
                conn = sqlite3.connect('portal.db')
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE wellsky_documentation SET wellsky_task_id = ?
                    WHERE type = 'TASK' AND related_id = ?
                    ORDER BY created_at DESC LIMIT 1
                ''', (str(task_id), related_id))
                conn.commit()
                conn.close()
            except Exception:
                pass
            return True, response
        else:
            logger.warning(f"AdminTask creation failed: {response}")
            return False, response

    def add_note_to_caregiver(
        self,
        caregiver_id: str,
        note: str,
        note_type: str = "general",
        source: str = "gigi_ai"
    ) -> Tuple[bool, str]:
        """
        Add a note to a caregiver's profile in WellSky.
        ALWAYS logs to local database first for guaranteed documentation trail.

        Args:
            caregiver_id: The caregiver's WellSky ID
            note: The note content
            note_type: Type of note (general, call, callout, late, performance)
            source: Source of the note (gigi_ai, portal, phone)

        Returns:
            Tuple of (success, message)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        formatted_note = f"[{timestamp}] [{source.upper()}] [{note_type}] {note}"

        # =====================================================================
        # ALWAYS log to local database FIRST (Documentation Trail - 24/7/365)
        # This ensures documentation is preserved even if WellSky API fails
        # =====================================================================
        local_logged = False
        try:
            import sqlite3
            conn = sqlite3.connect('portal.db')
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gigi_documentation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_type TEXT NOT NULL,
                    person_id TEXT NOT NULL,
                    note TEXT NOT NULL,
                    note_type TEXT,
                    source TEXT,
                    wellsky_synced INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                INSERT INTO gigi_documentation_log (person_type, person_id, note, note_type, source, wellsky_synced)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', ('caregiver', caregiver_id, formatted_note, note_type, source))
            conn.commit()
            conn.close()
            local_logged = True
            logger.info(f"Local: Documented caregiver note for {caregiver_id}")
        except Exception as db_err:
            logger.error(f"Local DB error (caregiver note): {db_err}")

        if self.is_mock_mode:
            caregiver = self._mock_caregivers.get(caregiver_id)
            if caregiver:
                caregiver.notes = f"{caregiver.notes}\n{formatted_note}" if caregiver.notes else formatted_note
                logger.info(f"Mock: Added note to caregiver {caregiver_id}")
                return True, f"Note added to caregiver {caregiver_id}"
            return False, f"Caregiver {caregiver_id} not found"

        # WellSky Connect API does not support general caregiver notes.
        # Legacy API is decommissioned (404).
        # We rely on the local database log.
        logger.info(f"Local: Note for caregiver {caregiver_id} saved to database. (Cloud sync skipped)")
        return True, "Note documented locally"

        # DEPRECATED: Legacy API call removed
        # endpoint = f"employees/{caregiver_id}/notes"
        # ...

    def assign_caregiver_to_shift(
        self,
        shift_id: str,
        caregiver_id: str,
        notify_caregiver: bool = True
    ) -> Tuple[bool, str]:
        """
        Assign a caregiver to an open shift in WellSky.

        Args:
            shift_id: The shift ID
            caregiver_id: The caregiver's WellSky ID
            notify_caregiver: Whether to notify the caregiver

        Returns:
            Tuple of (success, message)
        """
        if self.is_mock_mode:
            shift = self._mock_shifts.get(shift_id)
            caregiver = self._mock_caregivers.get(caregiver_id)

            if not shift:
                return False, f"Shift {shift_id} not found"
            if not caregiver:
                return False, f"Caregiver {caregiver_id} not found"

            shift.caregiver_id = caregiver_id
            shift.caregiver_first_name = caregiver.first_name
            shift.caregiver_last_name = caregiver.last_name
            shift.status = ShiftStatus.SCHEDULED
            logger.info(f"Mock: Assigned caregiver {caregiver_id} to shift {shift_id}")
            return True, f"Assigned {caregiver.full_name} to shift"

        # Real API call
        try:
            response = requests.put(
                f"{self.api_base_url}/shifts/{shift_id}/assign",
                headers=self._get_headers(),
                json={
                    "caregiver_id": caregiver_id,
                    "notify_caregiver": notify_caregiver,
                    "assigned_by": "gigi_ai",
                    "assigned_at": datetime.utcnow().isoformat()
                },
                timeout=15
            )
            if response.status_code in (200, 201):
                logger.info(f"Assigned caregiver {caregiver_id} to shift {shift_id}")
                return True, "Caregiver assigned to shift"
            else:
                logger.warning(f"Failed to assign caregiver to shift: {response.text}")
                return False, f"Failed to assign: {response.status_code}"
        except Exception as e:
            logger.error(f"Error assigning caregiver to shift: {e}")
            return False, str(e)

    def get_client_upcoming_shifts(
        self,
        client_id: str,
        days_ahead: int = 7
    ) -> List[WellSkyShift]:
        """
        Get upcoming shifts for a client.

        Args:
            client_id: The client's WellSky ID
            days_ahead: Number of days to look ahead

        Returns:
            List of upcoming shifts
        """
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        if self.is_mock_mode:
            shifts = []
            for shift in self._mock_shifts.values():
                if shift.client_id == client_id and shift.date:
                    if today <= shift.date <= end_date:
                        shifts.append(shift)
            shifts.sort(key=lambda s: (s.date, s.start_time or ""))
            return shifts

        # Real API call
        try:
            return self.search_appointments(
                client_id=client_id,
                start_date=today,
                additional_days=min(days_ahead, 6),
                limit=100
            )
        except Exception as e:
            logger.error(f"Error getting client shifts: {e}")
            return []

    def cancel_shift(
        self,
        shift_id: str,
        reason: str,
        cancelled_by: str = "client"
    ) -> Tuple[bool, str]:
        """
        Cancel a shift in WellSky.

        Args:
            shift_id: The shift ID
            reason: Reason for cancellation
            cancelled_by: Who cancelled (client, caregiver, agency)

        Returns:
            Tuple of (success, message)
        """
        if self.is_mock_mode:
            shift = self._mock_shifts.get(shift_id)
            if not shift:
                return False, f"Shift {shift_id} not found"

            shift.status = ShiftStatus.CANCELLED
            shift.notes = f"{shift.notes}\n[CANCELLED by {cancelled_by}] {reason}" if shift.notes else f"[CANCELLED by {cancelled_by}] {reason}"
            logger.info(f"Mock: Cancelled shift {shift_id}")
            return True, "Shift cancelled"

        # Real API call
        try:
            response = requests.put(
                f"{self.api_base_url}/shifts/{shift_id}",
                headers=self._get_headers(),
                json={
                    "status": "cancelled",
                    "cancellation_reason": reason,
                    "cancelled_by": cancelled_by,
                    "cancelled_at": datetime.utcnow().isoformat()
                },
                timeout=15
            )
            if response.status_code in (200, 201, 204):
                logger.info(f"Cancelled shift {shift_id}")
                return True, "Shift cancelled"
            else:
                logger.warning(f"Failed to cancel shift: {response.text}")
                return False, f"Failed to cancel: {response.status_code}"
        except Exception as e:
            logger.error(f"Error cancelling shift: {e}")
            return False, str(e)

    def notify_client_caregiver_late(
        self,
        shift_id: str,
        delay_minutes: int,
        reason: str = ""
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Notify client that caregiver will be late.

        Args:
            shift_id: The shift ID
            delay_minutes: Expected delay in minutes
            reason: Reason for being late

        Returns:
            Tuple of (success, message, client_phone)
        """
        if self.is_mock_mode:
            shift = self._mock_shifts.get(shift_id)
            if not shift:
                return False, f"Shift {shift_id} not found", None

            client = self._mock_clients.get(shift.client_id)
            client_phone = client.phone if client else None

            # Log the late notification
            note = f"[LATE NOTIFICATION] Caregiver running ~{delay_minutes} min late"
            if reason:
                note += f" - {reason}"
            shift.notes = f"{shift.notes}\n{note}" if shift.notes else note

            logger.info(f"Mock: Late notification for shift {shift_id}, client phone: {client_phone}")
            return True, f"Client notified of {delay_minutes} minute delay", client_phone

        # Real API call
        try:
            response = requests.post(
                f"{self.api_base_url}/shifts/{shift_id}/late-notification",
                headers=self._get_headers(),
                json={
                    "delay_minutes": delay_minutes,
                    "reason": reason,
                    "notified_at": datetime.utcnow().isoformat()
                },
                timeout=15
            )
            if response.status_code in (200, 201):
                data = response.json()
                client_phone = data.get("client_phone")
                logger.info(f"Late notification sent for shift {shift_id}")
                return True, "Client notified", client_phone
            else:
                logger.warning(f"Failed to send late notification: {response.text}")
                return False, f"Failed to notify: {response.status_code}", None
        except Exception as e:
            logger.error(f"Error sending late notification: {e}")
            return False, str(e), None


# =============================================================================
# Singleton Instance
# =============================================================================

wellsky_service = WellSkyService()

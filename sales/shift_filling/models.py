"""
Data models for Shift Filling Engine
"""

from dataclasses import dataclass, field
from datetime import datetime, date, time
from enum import Enum
from typing import Optional, List, Dict, Any
import uuid


class OutreachStatus(Enum):
    """Status of a shift outreach campaign"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    FILLED = "filled"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CaregiverResponseType(Enum):
    """Type of caregiver response"""
    ACCEPTED = "accepted"
    DECLINED = "declined"
    NO_RESPONSE = "no_response"
    AMBIGUOUS = "ambiguous"


@dataclass
class Client:
    """Client/Patient information"""
    id: str
    first_name: str
    last_name: str
    address: str
    city: str
    state: str = "CO"
    zip_code: str = ""
    phone: str = ""
    notes: str = ""
    care_preferences: List[str] = field(default_factory=list)
    preferred_caregivers: List[str] = field(default_factory=list)
    difficulty_score: float = 1.0  # 1-5, higher = more difficult

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def full_address(self) -> str:
        return f"{self.address}, {self.city}, {self.state} {self.zip_code}"


@dataclass
class Caregiver:
    """Caregiver/Employee information"""
    id: str
    first_name: str
    last_name: str
    phone: str
    email: str = ""
    address: str = ""
    city: str = ""
    lat: float = 0.0
    lon: float = 0.0

    # Availability & Preferences
    available_days: List[str] = field(default_factory=list)  # ["Mon", "Tue", ...]
    available_times: str = ""  # "mornings", "afternoons", "evenings", "any"
    preferred_areas: List[str] = field(default_factory=list)
    max_hours_per_week: int = 40
    current_weekly_hours: float = 0.0

    # Skills & Certifications
    certifications: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=lambda: ["English"])
    preferred_language: str = "English"

    # Performance Metrics (Organizational Memory)
    response_rate: float = 0.5  # % of offers they respond to
    acceptance_rate: float = 0.3  # % of offers they accept
    reliability_score: float = 0.9  # % of accepted shifts they complete
    avg_rating: float = 4.0  # Client feedback 1-5

    # History
    clients_worked_with: List[str] = field(default_factory=list)  # Client IDs
    total_shifts: int = 0
    calloffs_90d: int = 0
    last_calloff_date: Optional[datetime] = None
    tenure_days: int = 90

    # Status
    is_active: bool = True
    is_on_shift: bool = False
    current_shift_end: Optional[datetime] = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def hours_available(self) -> float:
        return max(0, self.max_hours_per_week - self.current_weekly_hours)

    @property
    def is_near_overtime(self) -> bool:
        return self.current_weekly_hours >= 35


@dataclass
class Shift:
    """Shift information from WellSky"""
    id: str
    client_id: str
    client: Optional[Client] = None

    # Timing
    date: date = field(default_factory=date.today)
    start_time: time = field(default_factory=lambda: time(9, 0))
    end_time: time = field(default_factory=lambda: time(13, 0))

    # Assignment
    assigned_caregiver_id: Optional[str] = None
    assigned_caregiver: Optional[Caregiver] = None
    original_caregiver_id: Optional[str] = None

    # Requirements
    required_skills: List[str] = field(default_factory=list)
    required_certifications: List[str] = field(default_factory=list)

    # Status
    status: str = "open"  # open, assigned, in_progress, completed, cancelled
    calloff_reason: str = ""
    calloff_time: Optional[datetime] = None

    # Metadata
    notes: str = ""
    wellsky_shift_id: str = ""

    @property
    def duration_hours(self) -> float:
        start_dt = datetime.combine(self.date, self.start_time)
        end_dt = datetime.combine(self.date, self.end_time)
        return (end_dt - start_dt).seconds / 3600

    @property
    def start_datetime(self) -> datetime:
        return datetime.combine(self.date, self.start_time)

    @property
    def end_datetime(self) -> datetime:
        return datetime.combine(self.date, self.end_time)

    @property
    def is_urgent(self) -> bool:
        """Shift starting within 4 hours is urgent"""
        hours_until = (self.start_datetime - datetime.now()).total_seconds() / 3600
        return hours_until < 4

    @property
    def hours_until_start(self) -> float:
        return (self.start_datetime - datetime.now()).total_seconds() / 3600

    def to_display_time(self) -> str:
        """Format for SMS display"""
        return f"{self.start_time.strftime('%I:%M %p').lstrip('0')}-{self.end_time.strftime('%I:%M %p').lstrip('0')}"


@dataclass
class CaregiverOutreach:
    """Individual outreach to a caregiver"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    caregiver_id: str = ""
    caregiver: Optional[Caregiver] = None

    # Outreach details
    phone: str = ""
    message_sent: str = ""
    sent_at: Optional[datetime] = None

    # Response
    response_type: CaregiverResponseType = CaregiverResponseType.NO_RESPONSE
    response_text: str = ""
    responded_at: Optional[datetime] = None

    # Scoring
    match_score: float = 0.0
    tier: int = 1  # 1 = best match, 2 = good, 3 = acceptable

    # Status
    is_winner: bool = False
    notified_of_fill: bool = False


@dataclass
class ShiftOutreach:
    """Complete outreach campaign for filling a shift"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    shift_id: str = ""
    shift: Optional[Shift] = None

    # Campaign status
    status: OutreachStatus = OutreachStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Outreach tracking
    caregivers_contacted: List[CaregiverOutreach] = field(default_factory=list)
    total_contacted: int = 0
    total_responded: int = 0
    total_accepted: int = 0
    total_declined: int = 0

    # Winner
    winning_caregiver_id: Optional[str] = None
    winning_caregiver: Optional[Caregiver] = None

    # Escalation
    escalated_at: Optional[datetime] = None
    escalated_to: str = ""  # Coordinator name/email
    escalation_reason: str = ""

    # Configuration
    timeout_minutes: int = 15
    max_caregivers_to_contact: int = 20
    include_voice_calls: bool = False
    voice_delay_minutes: int = 5  # Minutes to wait after SMS before voice call

    def add_caregiver_outreach(self, outreach: CaregiverOutreach):
        self.caregivers_contacted.append(outreach)
        self.total_contacted += 1

    def record_response(self, caregiver_id: str, response_type: CaregiverResponseType, response_text: str = ""):
        for outreach in self.caregivers_contacted:
            if outreach.caregiver_id == caregiver_id:
                outreach.response_type = response_type
                outreach.response_text = response_text
                outreach.responded_at = datetime.now()
                self.total_responded += 1

                if response_type == CaregiverResponseType.ACCEPTED:
                    self.total_accepted += 1
                elif response_type == CaregiverResponseType.DECLINED:
                    self.total_declined += 1
                break

    def mark_winner(self, caregiver_id: str):
        for outreach in self.caregivers_contacted:
            if outreach.caregiver_id == caregiver_id:
                outreach.is_winner = True
                self.winning_caregiver_id = caregiver_id
                self.winning_caregiver = outreach.caregiver
                self.status = OutreachStatus.FILLED
                self.completed_at = datetime.now()
                break

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "shift_id": self.shift_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_contacted": self.total_contacted,
            "total_responded": self.total_responded,
            "total_accepted": self.total_accepted,
            "total_declined": self.total_declined,
            "winning_caregiver_id": self.winning_caregiver_id,
            "winning_caregiver_name": self.winning_caregiver.full_name if self.winning_caregiver else None,
            "escalated": self.status == OutreachStatus.ESCALATED,
            "escalation_reason": self.escalation_reason
        }

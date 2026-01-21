"""
Gigi - Colorado CareAssist After-Hours AI Agent
Powered by Retell AI

Gigi handles after-hours calls from both Caregivers and Clients:
- Caregivers: Call-outs, schedule questions, shift confirmations
- Clients: Service requests, satisfaction issues, scheduling

This FastAPI middleware provides the tool functions that Gigi calls
during conversations to look up information and take actions.
"""

import os
import json
import hmac
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Literal
from enum import Enum

from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

RETELL_API_KEY = os.getenv("RETELL_API_KEY", "key_5d0bc4168659a5df305b8ac2a7fd")
RETELL_WEBHOOK_SECRET = os.getenv("RETELL_WEBHOOK_SECRET", "")  # No webhook secret - skip validation
PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "https://portal.coloradocareassist.com")

# BeeTexting OAuth2 credentials
BEETEXTING_CLIENT_ID = os.getenv("BEETEXTING_CLIENT_ID", "79e4ivhns352r5373hmi1382tt")
BEETEXTING_CLIENT_SECRET = os.getenv("BEETEXTING_CLIENT_SECRET", "m5gbn20h4lkl0o115vk6c3ghp5he279ijftvj8pn2gslj7i1g1m")
BEETEXTING_API_KEY = os.getenv("BEETEXTING_API_KEY", "m5gbn20h4lkl0o115vk6c3ghp5he279ijftvj8pn2gslj7i1g1m")

# Phone numbers
BEETEXTING_FROM_NUMBER = os.getenv("BEETEXTING_FROM_NUMBER", "+17194283999")  # 719-428-3999
ON_CALL_MANAGER_PHONE = os.getenv("ON_CALL_MANAGER_PHONE", "+13037571777")    # 303-757-1777

# RingCentral credentials (backup SMS provider)
RINGCENTRAL_CLIENT_ID = os.getenv("RINGCENTRAL_CLIENT_ID", "cqaJllTcFyndtgsussicsd")
RINGCENTRAL_CLIENT_SECRET = os.getenv("RINGCENTRAL_CLIENT_SECRET", "1PwhkkpeFYEcaHcZmQ3cCialR3hQ79DnDfVSpRPOUqYT")
RINGCENTRAL_SERVER = os.getenv("RINGCENTRAL_SERVER", "https://platform.ringcentral.com")
RINGCENTRAL_JWT = os.getenv("RINGCENTRAL_JWT", "eyJraWQiOiI4NzYyZjU5OGQwNTk0NGRiODZiZjVjYTk3ODA0NzYwOCIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0.eyJhdWQiOiJodHRwczovL3BsYXRmb3JtLnJpbmdjZW50cmFsLmNvbS9yZXN0YXBpL29hdXRoL3Rva2VuIiwic3ViIjoiMjYyNzQwMDA5IiwiaXNzIjoiaHR0cHM6Ly9wbGF0Zm9ybS5yaW5nY2VudHJhbC5jb20iLCJleHAiOjM5MTAyNDA5NjUsImlhdCI6MTc2Mjc1NzMxOCwianRpIjoiZ3Jsd0pPWGFTM2EwalpibThvTmtZdyJ9.WA9DUSlb_4SlCo9UHNjscHKrVDoJTF4iW3D7Rre9E2qg5UQ_hWfCgysiZJMXlL8-vUuJ2XDNivvpfbxriESKIEPAEEY85MolJZS9KG3g90ga-3pJtHq7SC87mcacXtDWqzmbBS_iDOjmNMHiynWFR9Wgi30DMbz9rQ1U__Bl88qVRTvZfY17ovu3dZDhh-FmLUWRnKOc4LQUvRChQCO-21LdSquZPvEAe7qHEsh-blS8Cvh98wvX-9vaiurDR-kC9Tp007x4lTI74MwQ5rJif7tL7Hslqaoag0WoNEIP9VPrp4x-Q7AzKIzBNbrGr9kIPthIebmeOBDMIIrw6pg_lg")

# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="Gigi - Colorado CareAssist AI Agent",
    description="After-hours AI assistant for caregivers and clients",
    version="1.0.0"
)


# =============================================================================
# Pydantic Models
# =============================================================================

class CallerType(str, Enum):
    CAREGIVER = "caregiver"
    CLIENT = "client"
    UNKNOWN = "unknown"


class CallerInfo(BaseModel):
    caller_type: CallerType
    person_id: Optional[str] = None
    name: Optional[str] = None
    phone: str
    is_active: bool = False
    additional_info: Dict[str, Any] = Field(default_factory=dict)


class ShiftDetails(BaseModel):
    shift_id: str
    caregiver_id: str
    caregiver_name: str
    client_id: str
    client_name: str
    client_address: str
    start_time: datetime
    end_time: datetime
    hours: float
    status: str
    notes: str = ""


class CallOutReport(BaseModel):
    success: bool
    call_out_id: Optional[str] = None
    message: str
    manager_notified: bool = False
    notification_details: Optional[str] = None


class ClientIssueReport(BaseModel):
    success: bool
    issue_id: Optional[str] = None
    message: str


class RetellToolCall(BaseModel):
    """Retell AI tool call request format"""
    tool_call_id: str
    name: str
    arguments: Dict[str, Any]


class RetellWebhookPayload(BaseModel):
    """Retell AI webhook payload"""
    event: str
    call_id: str
    agent_id: Optional[str] = None
    call_type: Optional[str] = None
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    direction: Optional[str] = None
    call_status: Optional[str] = None
    start_timestamp: Optional[int] = None
    end_timestamp: Optional[int] = None
    transcript: Optional[str] = None
    recording_url: Optional[str] = None
    tool_calls: Optional[List[RetellToolCall]] = None
    # Additional fields for function calls
    args: Optional[Dict[str, Any]] = None


# =============================================================================
# Retell Signature Validation
# =============================================================================

async def verify_retell_signature(
    request: Request,
    x_retell_signature: Optional[str] = Header(None)
) -> bool:
    """
    Verify the Retell webhook signature to ensure request authenticity.

    Retell signs webhooks with HMAC-SHA256 using your webhook secret.
    """
    if not RETELL_WEBHOOK_SECRET:
        # If no secret configured, skip validation (development mode)
        logger.warning("RETELL_WEBHOOK_SECRET not configured - skipping signature validation")
        return True

    if not x_retell_signature:
        logger.warning("Missing X-Retell-Signature header")
        return False

    body = await request.body()

    # Compute expected signature
    expected_signature = hmac.new(
        RETELL_WEBHOOK_SECRET.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    # Compare signatures
    is_valid = hmac.compare_digest(x_retell_signature, expected_signature)

    if not is_valid:
        logger.warning("Invalid Retell signature")

    return is_valid


# =============================================================================
# WellSky Integration Helpers
# =============================================================================

async def _query_wellsky_caregiver(phone: str) -> Optional[Dict[str, Any]]:
    """Query WellSky for caregiver by phone number."""
    try:
        # First try the portal's WellSky API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PORTAL_BASE_URL}/api/wellsky/caregivers",
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                caregivers = data.get("caregivers", [])

                # Normalize phone for comparison
                clean_phone = ''.join(filter(str.isdigit, phone))[-10:]

                for cg in caregivers:
                    cg_phone = ''.join(filter(str.isdigit, cg.get("phone", "")))[-10:]
                    if cg_phone == clean_phone and cg.get("status") == "active":
                        return cg
    except Exception as e:
        logger.error(f"Error querying WellSky for caregiver: {e}")

    return None


async def _query_wellsky_client(phone: str) -> Optional[Dict[str, Any]]:
    """Query WellSky for client by phone number."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PORTAL_BASE_URL}/api/wellsky/clients",
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                clients = data.get("clients", [])

                # Normalize phone for comparison
                clean_phone = ''.join(filter(str.isdigit, phone))[-10:]

                for cl in clients:
                    # Check primary phone and emergency contact
                    cl_phone = ''.join(filter(str.isdigit, cl.get("phone", "")))[-10:]
                    emergency_phone = ''.join(filter(str.isdigit, cl.get("emergency_contact_phone", "")))[-10:]

                    if (cl_phone == clean_phone or emergency_phone == clean_phone) and cl.get("status") == "active":
                        return cl
    except Exception as e:
        logger.error(f"Error querying WellSky for client: {e}")

    return None


async def _get_caregiver_shifts(caregiver_id: str) -> List[Dict[str, Any]]:
    """Get upcoming shifts for a caregiver from WellSky."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PORTAL_BASE_URL}/api/wellsky/shifts",
                params={"caregiver_id": caregiver_id, "upcoming": "true"},
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("shifts", [])
    except Exception as e:
        logger.error(f"Error getting caregiver shifts: {e}")

    return []


# =============================================================================
# BeeTexting SMS Integration
# =============================================================================

# Cache for BeeTexting OAuth token
_beetexting_token_cache: Dict[str, Any] = {}


async def _get_beetexting_token() -> Optional[str]:
    """Get OAuth2 access token for BeeTexting API."""
    global _beetexting_token_cache

    # Check cache
    if _beetexting_token_cache.get("token") and _beetexting_token_cache.get("expires_at"):
        if datetime.now() < _beetexting_token_cache["expires_at"]:
            return _beetexting_token_cache["token"]

    if not BEETEXTING_CLIENT_ID or not BEETEXTING_CLIENT_SECRET:
        logger.warning("BeeTexting credentials not configured")
        return None

    try:
        async with httpx.AsyncClient() as client:
            # OAuth2 client credentials flow
            response = await client.post(
                "https://api.beetexting.com/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": BEETEXTING_CLIENT_ID,
                    "client_secret": BEETEXTING_CLIENT_SECRET
                },
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)

                _beetexting_token_cache = {
                    "token": token,
                    "expires_at": datetime.now() + timedelta(seconds=expires_in - 60)
                }
                logger.info("BeeTexting OAuth token obtained successfully")
                return token
            else:
                logger.error(f"BeeTexting OAuth error: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Error getting BeeTexting token: {e}")
        return None


async def _send_sms_beetexting(to_phone: str, message: str) -> bool:
    """Send SMS via BeeTexting API."""
    # Try API key first, fall back to OAuth
    token = BEETEXTING_API_KEY or await _get_beetexting_token()

    if not token:
        logger.warning("BeeTexting not configured - trying RingCentral")
        return await _send_sms_ringcentral(to_phone, message)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.beetexting.com/v1/messages",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": BEETEXTING_FROM_NUMBER,
                    "to": to_phone,
                    "text": message
                },
                timeout=10.0
            )
            if response.status_code in (200, 201):
                logger.info(f"SMS sent successfully via BeeTexting to {to_phone}")
                return True
            else:
                logger.error(f"BeeTexting API error: {response.status_code} - {response.text}")
                # Fall back to RingCentral
                logger.info("Falling back to RingCentral SMS")
                return await _send_sms_ringcentral(to_phone, message)
    except Exception as e:
        logger.error(f"BeeTexting error: {e} - falling back to RingCentral")
        return await _send_sms_ringcentral(to_phone, message)


# Cache for RingCentral OAuth token
_ringcentral_token_cache: Dict[str, Any] = {}


async def _get_ringcentral_token() -> Optional[str]:
    """Get OAuth2 access token for RingCentral API using JWT auth."""
    global _ringcentral_token_cache

    # Check cache
    if _ringcentral_token_cache.get("token") and _ringcentral_token_cache.get("expires_at"):
        if datetime.now() < _ringcentral_token_cache["expires_at"]:
            return _ringcentral_token_cache["token"]

    if not RINGCENTRAL_CLIENT_ID or not RINGCENTRAL_JWT:
        logger.warning("RingCentral credentials not configured")
        return None

    try:
        async with httpx.AsyncClient() as client:
            # JWT auth flow for RingCentral
            response = await client.post(
                f"{RINGCENTRAL_SERVER}/restapi/oauth/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": RINGCENTRAL_JWT
                },
                auth=(RINGCENTRAL_CLIENT_ID, RINGCENTRAL_CLIENT_SECRET),
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)

                _ringcentral_token_cache = {
                    "token": token,
                    "expires_at": datetime.now() + timedelta(seconds=expires_in - 60)
                }
                logger.info("RingCentral OAuth token obtained successfully")
                return token
            else:
                logger.error(f"RingCentral OAuth error: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Error getting RingCentral token: {e}")
        return None


async def _send_sms_ringcentral(to_phone: str, message: str) -> bool:
    """Send SMS via RingCentral API (backup provider)."""
    token = await _get_ringcentral_token()

    if not token:
        logger.warning("RingCentral not available - SMS not sent")
        logger.info(f"[MOCK SMS] To: {to_phone}, Message: {message}")
        return False

    # Normalize phone number to E.164 format
    clean_to = ''.join(filter(str.isdigit, to_phone))
    if len(clean_to) == 10:
        clean_to = f"+1{clean_to}"
    elif len(clean_to) == 11 and clean_to.startswith('1'):
        clean_to = f"+{clean_to}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/sms",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": {"phoneNumber": BEETEXTING_FROM_NUMBER},
                    "to": [{"phoneNumber": clean_to}],
                    "text": message
                },
                timeout=10.0
            )
            if response.status_code in (200, 201):
                logger.info(f"SMS sent successfully via RingCentral to {to_phone}")
                return True
            else:
                logger.error(f"RingCentral SMS error: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"Error sending RingCentral SMS: {e}")
        return False


# =============================================================================
# Tool Functions (Called by Gigi via Retell)
# =============================================================================

async def verify_caller(phone_number: str) -> CallerInfo:
    """
    Queries WellSky/Portal to identify if the caller is a Caregiver or Client.

    This is the FIRST tool Gigi should call to understand who she's talking to.
    The result determines which conversation path to follow.

    Args:
        phone_number: The caller's phone number (any format)

    Returns:
        CallerInfo with caller_type, person_id, name, and active status
    """
    logger.info(f"verify_caller called with phone: {phone_number}")

    # Normalize phone number
    clean_phone = ''.join(filter(str.isdigit, phone_number))
    if len(clean_phone) == 11 and clean_phone.startswith('1'):
        clean_phone = clean_phone[1:]

    # Check if caller is a caregiver
    caregiver = await _query_wellsky_caregiver(clean_phone)
    if caregiver:
        return CallerInfo(
            caller_type=CallerType.CAREGIVER,
            person_id=caregiver.get("id"),
            name=f"{caregiver.get('first_name', '')} {caregiver.get('last_name', '')}".strip(),
            phone=phone_number,
            is_active=caregiver.get("status") == "active",
            additional_info={
                "certifications": caregiver.get("certifications", []),
                "hire_date": caregiver.get("hire_date"),
                "supervisor": caregiver.get("supervisor")
            }
        )

    # Check if caller is a client
    client = await _query_wellsky_client(clean_phone)
    if client:
        return CallerInfo(
            caller_type=CallerType.CLIENT,
            person_id=client.get("id"),
            name=f"{client.get('first_name', '')} {client.get('last_name', '')}".strip(),
            phone=phone_number,
            is_active=client.get("status") == "active",
            additional_info={
                "care_plan": client.get("care_plan_summary"),
                "primary_caregiver": client.get("primary_caregiver_name"),
                "service_hours": client.get("authorized_hours_weekly")
            }
        )

    # Unknown caller
    return CallerInfo(
        caller_type=CallerType.UNKNOWN,
        phone=phone_number,
        is_active=False
    )


async def get_shift_details(person_id: str) -> Optional[ShiftDetails]:
    """
    Pulls the next scheduled shift from WellSky for a caregiver.

    Use this after identifying a caregiver to see their upcoming shift.
    This helps Gigi confirm which shift they're calling about.

    Args:
        person_id: The caregiver's ID from verify_caller

    Returns:
        ShiftDetails for the next upcoming shift, or None if no shifts scheduled
    """
    logger.info(f"get_shift_details called for person_id: {person_id}")

    shifts = await _get_caregiver_shifts(person_id)

    if not shifts:
        return None

    # Find the next upcoming shift
    now = datetime.now()
    upcoming_shifts = []

    for shift in shifts:
        try:
            start_time = datetime.fromisoformat(shift.get("start_time", "").replace("Z", "+00:00"))
            if start_time > now:
                upcoming_shifts.append((start_time, shift))
        except (ValueError, TypeError):
            continue

    if not upcoming_shifts:
        return None

    # Sort by start time and get the nearest one
    upcoming_shifts.sort(key=lambda x: x[0])
    _, next_shift = upcoming_shifts[0]

    start_time = datetime.fromisoformat(next_shift.get("start_time", "").replace("Z", "+00:00"))
    end_time = datetime.fromisoformat(next_shift.get("end_time", "").replace("Z", "+00:00"))

    return ShiftDetails(
        shift_id=next_shift.get("id", ""),
        caregiver_id=person_id,
        caregiver_name=next_shift.get("caregiver_name", ""),
        client_id=next_shift.get("client_id", ""),
        client_name=next_shift.get("client_name", ""),
        client_address=next_shift.get("client_address", ""),
        start_time=start_time,
        end_time=end_time,
        hours=(end_time - start_time).total_seconds() / 3600,
        status=next_shift.get("status", "scheduled"),
        notes=next_shift.get("notes", "")
    )


async def report_call_out(
    caregiver_id: str,
    shift_id: str,
    reason: str
) -> CallOutReport:
    """
    Reports a caregiver call-out and triggers urgent notifications.

    This is a HIGH-PRIORITY action that:
    1. Posts the call-out to the Client Ops Portal
    2. Sends an urgent SMS to the On-Call Manager via BeeTexting
    3. Returns a confirmation message for Gigi to read

    Args:
        caregiver_id: The caregiver's ID
        shift_id: The shift they're calling out from
        reason: The reason for calling out (e.g., "sick", "emergency", "car trouble")

    Returns:
        CallOutReport with success status and confirmation message
    """
    logger.info(f"report_call_out called: caregiver={caregiver_id}, shift={shift_id}, reason={reason}")

    # Get shift details for the notification
    shift = await get_shift_details(caregiver_id)

    caregiver_name = shift.caregiver_name if shift else f"Caregiver {caregiver_id}"
    client_name = shift.client_name if shift else "Unknown Client"
    shift_time = shift.start_time.strftime("%B %d at %I:%M %p") if shift else "Unknown Time"

    # Create call-out record
    call_out_data = {
        "caregiver_id": caregiver_id,
        "caregiver_name": caregiver_name,
        "shift_id": shift_id,
        "client_name": client_name,
        "shift_time": shift_time,
        "reason": reason,
        "reported_at": datetime.now().isoformat(),
        "reported_via": "gigi_ai_agent",
        "priority": "high"
    }

    # Post to Client Ops Portal
    call_out_id = None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PORTAL_BASE_URL}/api/operations/call-outs",
                json=call_out_data,
                timeout=10.0
            )
            if response.status_code in (200, 201):
                result = response.json()
                call_out_id = result.get("id")
                logger.info(f"Call-out posted to portal: {call_out_id}")
            else:
                logger.warning(f"Portal returned {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Error posting call-out to portal: {e}")

    # Send urgent SMS to On-Call Manager
    sms_message = (
        f"URGENT CALL-OUT: {caregiver_name} called out for {client_name} shift "
        f"({shift_time}). Reason: {reason}. "
        f"Gigi AI logged this at {datetime.now().strftime('%I:%M %p')}. "
        f"Coverage needed!"
    )

    sms_sent = await _send_sms_beetexting(ON_CALL_MANAGER_PHONE, sms_message)

    # Build confirmation message for Gigi to read
    if sms_sent:
        confirmation = (
            "I've logged your call-out and notified the on-call manager. "
            "They'll work on finding coverage for your shift. "
            "Please also message your client directly if possible to let them know. "
            "We hope everything is okay, and please keep us updated."
        )
    else:
        confirmation = (
            "I've logged your call-out in our system. "
            "However, I wasn't able to send the notification to the manager. "
            "Please also try calling or texting the office directly to make sure someone knows. "
            "And please message your client if possible."
        )

    return CallOutReport(
        success=True,
        call_out_id=call_out_id,
        message=confirmation,
        manager_notified=sms_sent,
        notification_details=f"SMS sent to on-call manager: {ON_CALL_MANAGER_PHONE}" if sms_sent else None
    )


async def log_client_issue(
    client_id: Optional[str],
    note: str,
    issue_type: str = "general",
    priority: str = "normal"
) -> ClientIssueReport:
    """
    Logs a client service issue or satisfaction concern to the Portal.

    Use this for any client concerns, requests, or feedback including:
    - Service complaints
    - Schedule change requests
    - Caregiver feedback
    - General questions that need follow-up

    Args:
        client_id: The client's ID from verify_caller (can be None or "UNKNOWN" for unverified callers)
        note: Description of the issue or request
        issue_type: Type of issue (general, complaint, schedule, feedback)
        priority: Priority level (low, normal, high, urgent)

    Returns:
        ClientIssueReport with success status and confirmation
    """
    # Handle None or missing client_id
    effective_client_id = client_id if client_id else "UNKNOWN"
    logger.info(f"log_client_issue called: client={effective_client_id}, type={issue_type}")

    issue_data = {
        "client_id": effective_client_id,
        "note": note,
        "issue_type": issue_type,
        "priority": priority,
        "source": "gigi_ai_agent",
        "reported_at": datetime.now().isoformat(),
        "status": "new"
    }

    issue_id = None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PORTAL_BASE_URL}/api/client-satisfaction/issues",
                json=issue_data,
                timeout=10.0
            )
            if response.status_code in (200, 201):
                result = response.json()
                issue_id = result.get("id")
                logger.info(f"Client issue logged: {issue_id}")
            else:
                logger.warning(f"Portal returned {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Error logging client issue: {e}")

    if issue_id:
        return ClientIssueReport(
            success=True,
            issue_id=issue_id,
            message=(
                "I've recorded your concern and our care team will follow up with you. "
                "Someone will reach out during business hours to help resolve this. "
                "Is there anything else I can help you with tonight?"
            )
        )
    else:
        return ClientIssueReport(
            success=False,
            message=(
                "I apologize, but I had trouble recording your concern in our system. "
                "Please call back during business hours or try again. "
                "Our office number is 719-428-3999."
            )
        )


# =============================================================================
# Retell Webhook Endpoints
# =============================================================================

@app.post("/webhook/retell")
async def retell_webhook(request: Request):
    """
    Main webhook endpoint for Retell AI.

    Handles various events from Retell including:
    - call_started: When a call begins
    - call_ended: When a call ends
    - tool_call: When Gigi needs to execute a tool function
    """
    # Verify signature
    is_valid = await verify_retell_signature(request)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid signature")

    body = await request.json()
    event = body.get("event", "")
    call_id = body.get("call_id", "")

    logger.info(f"Retell webhook received: event={event}, call_id={call_id}")

    if event == "call_started":
        from_number = body.get("from_number", "")
        logger.info(f"Call started from {from_number}")
        return JSONResponse({"status": "ok"})

    elif event == "call_ended":
        transcript = body.get("transcript", "")
        duration = body.get("end_timestamp", 0) - body.get("start_timestamp", 0)
        logger.info(f"Call ended. Duration: {duration}ms")

        # Could log transcript to database here
        return JSONResponse({"status": "ok"})

    elif event == "tool_call":
        # Handle function/tool calls from Gigi
        tool_calls = body.get("tool_calls", [])
        results = []

        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("arguments", {})
            tool_call_id = tool_call.get("tool_call_id", "")

            logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

            try:
                if tool_name == "verify_caller":
                    result = await verify_caller(**tool_args)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": result.model_dump()
                    })

                elif tool_name == "get_shift_details":
                    result = await get_shift_details(**tool_args)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": result.model_dump() if result else None
                    })

                elif tool_name == "report_call_out":
                    result = await report_call_out(**tool_args)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": result.model_dump()
                    })

                elif tool_name == "log_client_issue":
                    result = await log_client_issue(**tool_args)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": result.model_dump()
                    })

                else:
                    logger.warning(f"Unknown tool: {tool_name}")
                    results.append({
                        "tool_call_id": tool_call_id,
                        "error": f"Unknown tool: {tool_name}"
                    })

            except Exception as e:
                logger.exception(f"Error executing tool {tool_name}: {e}")
                results.append({
                    "tool_call_id": tool_call_id,
                    "error": str(e)
                })

        return JSONResponse({"results": results})

    return JSONResponse({"status": "ok"})


@app.post("/webhook/retell/function/{function_name}")
async def retell_function_call(function_name: str, request: Request):
    """
    Alternative endpoint for direct function calls from Retell.

    Some Retell configurations send function calls to individual endpoints.
    """
    is_valid = await verify_retell_signature(request)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid signature")

    body = await request.json()
    args = body.get("args", body.get("arguments", {}))

    logger.info(f"Direct function call: {function_name} with args: {args}")

    try:
        if function_name == "verify_caller":
            result = await verify_caller(**args)
            return JSONResponse(result.model_dump())

        elif function_name == "get_shift_details":
            result = await get_shift_details(**args)
            return JSONResponse(result.model_dump() if result else {"shift": None})

        elif function_name == "report_call_out":
            result = await report_call_out(**args)
            return JSONResponse(result.model_dump())

        elif function_name == "log_client_issue":
            result = await log_client_issue(**args)
            return JSONResponse(result.model_dump())

        else:
            raise HTTPException(status_code=404, detail=f"Unknown function: {function_name}")

    except Exception as e:
        logger.exception(f"Error in function {function_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "agent": "gigi", "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint with agent info."""
    return {
        "agent": "Gigi",
        "description": "Colorado CareAssist After-Hours AI Agent",
        "version": "1.0.0",
        "capabilities": [
            "Caregiver call-out handling",
            "Client issue logging",
            "Shift verification",
            "Emergency notifications"
        ],
        "webhook_url": "/webhook/retell",
        "documentation": "/docs"
    }


# =============================================================================
# Development/Testing Endpoints
# =============================================================================

@app.post("/test/verify-caller")
async def test_verify_caller(phone_number: str):
    """Test endpoint for verify_caller function."""
    result = await verify_caller(phone_number)
    return result.model_dump()


@app.post("/test/get-shift-details")
async def test_get_shift_details(person_id: str):
    """Test endpoint for get_shift_details function."""
    result = await get_shift_details(person_id)
    return result.model_dump() if result else {"shift": None}


@app.post("/test/report-call-out")
async def test_report_call_out(caregiver_id: str, shift_id: str, reason: str):
    """Test endpoint for report_call_out function."""
    result = await report_call_out(caregiver_id, shift_id, reason)
    return result.model_dump()


@app.post("/test/log-client-issue")
async def test_log_client_issue(client_id: str, note: str, issue_type: str = "general"):
    """Test endpoint for log_client_issue function."""
    result = await log_client_issue(client_id, note, issue_type)
    return result.model_dump()


# =============================================================================
# SMS Auto-Reply System
# =============================================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyB-67dmnNUmfJfvbEznwqLYcnMZBMPam8o")

# SMS Response prompt for Gigi
SMS_SYSTEM_PROMPT = """You are Gigi, the after-hours AI assistant for Colorado Care Assist, a non-medical home care agency serving seniors and people with disabilities across Colorado.

You are responding to TEXT MESSAGES from caregivers after hours. Keep responses:
- Warm but professional
- BRIEF - this is SMS, not email (2-3 sentences max)
- Helpful and reassuring
- Don't ask too many questions in one message

COMMON SCENARIOS:

1. CLOCK IN/OUT ISSUES (very common in rural Colorado):
   - Reassure them their pay won't be affected
   - Ask for the details: client name, date, actual time
   - Tell them you'll log it for the office to fix in the morning
   - Example: "No worries! I'll log that for you. What was the client name and your actual clock in/out time? The office will fix it in WellSky first thing tomorrow."

2. CALLING OUT SICK:
   - Express empathy
   - Get the shift details (client name, time)
   - Let them know you'll notify the team
   - Example: "Sorry to hear that! I'll let the team know. Which shift are you calling out from?"

3. RUNNING LATE:
   - Acknowledge and log it
   - Example: "Thanks for letting us know! I'll make a note. Hope you get there safely."

4. LOOKING FOR SHIFTS:
   - Note their availability
   - Example: "I'll note your availability for the scheduling team - they'll reach out when shifts open up!"

5. PAYROLL QUESTIONS:
   - Pay stubs: www.adamskeegan.com
   - Pay is bi-weekly
   - Example: "Pay stubs are at adamskeegan.com. We pay bi-weekly. For specific questions, the office can help you in the morning."

6. GENERAL QUESTIONS:
   - Answer if you can from knowledge base
   - Otherwise say office will follow up
   - Example: "I've made a note - Cynthia or the office will get back to you first thing in the morning!"

Office hours: Monday-Friday, 8 AM - 5 PM Mountain Time
Office numbers: 719-428-3999 or 303-757-1777

IMPORTANT: Never make promises about shift coverage or schedule changes - just log and reassure."""


class InboundSMS(BaseModel):
    """Inbound SMS message from Beetexting webhook."""
    from_number: str = Field(..., description="Sender's phone number")
    to_number: str = Field(default="+17194283999", description="Receiving number")
    message: str = Field(..., description="Message content")
    contact_name: Optional[str] = Field(None, description="Contact name if known")
    agent_email: Optional[str] = Field(None, description="Beetexting agent email")


class SMSResponse(BaseModel):
    """Response for SMS auto-reply."""
    success: bool
    reply_sent: bool
    reply_text: Optional[str] = None
    error: Optional[str] = None


async def generate_sms_response(message: str, caller_info: Optional[CallerInfo] = None) -> str:
    """
    Generate a thoughtful SMS response using Gemini AI.
    """
    # Build context
    context = ""
    if caller_info and caller_info.name:
        context = f"The message is from {caller_info.name}, who is a {caller_info.caller_type.value}. "

    user_prompt = f"{context}Caregiver's text message: \"{message}\"\n\nWrite a brief, helpful SMS reply:"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": f"{SMS_SYSTEM_PROMPT}\n\n{user_prompt}"}]}],
                    "generationConfig": {
                        "maxOutputTokens": 150,
                        "temperature": 0.7
                    }
                },
                timeout=15.0
            )
            if response.status_code == 200:
                data = response.json()
                reply = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if reply:
                    return reply.strip()
            else:
                logger.error(f"Gemini API error: {response.status_code} - {response.text[:200]}")
    except Exception as e:
        logger.error(f"Gemini API error: {e}")

    # Fallback to simple response if Gemini fails
    return "Thanks for reaching out! I've noted your message and someone from the office will get back to you first thing in the morning. Office hours are Mon-Fri 8 AM - 5 PM."


@app.post("/webhook/inbound-sms", response_model=SMSResponse)
async def handle_inbound_sms(sms: InboundSMS):
    """
    Handle inbound SMS messages and send AI-powered replies.

    This endpoint receives inbound SMS notifications from Beetexting
    and generates thoughtful, context-aware responses using Gigi's AI.
    """
    logger.info(f"Inbound SMS from {sms.from_number}: {sms.message[:100]}...")

    try:
        # Look up caller info
        caller_info = await verify_caller(sms.from_number)

        # Generate AI response
        reply_text = await generate_sms_response(sms.message, caller_info)

        # Send reply via RingCentral SMS
        sms_sent = await _send_sms_ringcentral(sms.from_number, reply_text)

        if sms_sent:
            logger.info(f"SMS reply sent to {sms.from_number}: {reply_text[:50]}...")
            return SMSResponse(
                success=True,
                reply_sent=True,
                reply_text=reply_text
            )
        else:
            logger.warning(f"Failed to send SMS reply to {sms.from_number}")
            return SMSResponse(
                success=True,  # Message received OK
                reply_sent=False,
                reply_text=reply_text,
                error="Failed to send SMS reply"
            )

    except Exception as e:
        logger.exception(f"Error handling inbound SMS: {e}")
        return SMSResponse(
            success=False,
            reply_sent=False,
            error=str(e)
        )


@app.post("/webhook/beetexting")
async def beetexting_webhook(request: Request):
    """
    Webhook endpoint for Beetexting inbound SMS.

    Receives the webhook payload, extracts the message,
    and triggers the auto-reply system.
    """
    try:
        body = await request.json()
        logger.info(f"Beetexting webhook received: {json.dumps(body)[:500]}")

        # Extract message details from webhook payload
        payload = body.get("payload", body)

        # Get phone numbers
        from_number = (
            payload.get("from") or
            payload.get("fromNumber") or
            payload.get("mobileNumber") or
            body.get("from")
        )
        to_number = payload.get("to") or payload.get("toNumber") or "+17194283999"

        # Get message text
        message = (
            payload.get("text") or
            payload.get("message") or
            payload.get("body") or
            body.get("text") or
            body.get("message")
        )

        # Get direction - only auto-reply to inbound messages
        direction = (
            payload.get("direction") or
            body.get("direction") or
            "inbound"
        ).lower()

        if direction == "outbound":
            logger.info("Skipping outbound message - no reply needed")
            return JSONResponse({"status": "ok", "action": "skipped_outbound"})

        if not from_number or not message:
            logger.warning(f"Missing from_number or message in webhook payload")
            return JSONResponse({"status": "error", "message": "Missing required fields"}, status_code=400)

        # Handle the inbound SMS
        sms = InboundSMS(
            from_number=from_number,
            to_number=to_number,
            message=message,
            contact_name=payload.get("contactName"),
            agent_email=body.get("agentEmail")
        )

        result = await handle_inbound_sms(sms)

        return JSONResponse({
            "status": "ok",
            "reply_sent": result.reply_sent,
            "reply_preview": result.reply_text[:50] + "..." if result.reply_text else None
        })

    except Exception as e:
        logger.exception(f"Error in Beetexting webhook: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/webhook/ringcentral-sms")
async def ringcentral_sms_webhook(request: Request):
    """
    Webhook endpoint for RingCentral inbound SMS notifications.

    Handles RingCentral's webhook validation (echoes Validation-Token)
    and processes inbound SMS messages for auto-reply.
    """
    # Handle RingCentral validation request
    validation_token = request.headers.get("Validation-Token")
    if validation_token:
        logger.info(f"RingCentral webhook validation request received")
        return Response(
            content=validation_token,
            headers={"Validation-Token": validation_token},
            status_code=200
        )

    try:
        body = await request.json()
        logger.info(f"RingCentral SMS webhook received: {json.dumps(body)[:500]}")

        # RingCentral notification structure
        # body contains: uuid, event, timestamp, subscriptionId, body (message data)
        event = body.get("event", "")
        message_body = body.get("body", {})

        # Only process inbound SMS
        if "message-store" not in event:
            logger.info(f"Ignoring non-message event: {event}")
            return JSONResponse({"status": "ok", "action": "ignored_event_type"})

        # Extract message details from RingCentral format
        direction = message_body.get("direction", "").lower()
        if direction != "inbound":
            logger.info(f"Skipping {direction} message")
            return JSONResponse({"status": "ok", "action": "skipped_outbound"})

        # Get phone numbers from RingCentral format
        from_info = message_body.get("from", {})
        to_info = message_body.get("to", [{}])[0] if message_body.get("to") else {}

        from_number = from_info.get("phoneNumber") or from_info.get("extensionNumber")
        to_number = to_info.get("phoneNumber") or to_info.get("extensionNumber")

        # Get message text - RingCentral uses "subject" for SMS content
        message = message_body.get("subject") or message_body.get("text", "")

        # Get contact name if available
        contact_name = from_info.get("name")

        if not from_number or not message:
            logger.warning(f"Missing from_number or message in RingCentral payload")
            return JSONResponse({"status": "error", "message": "Missing required fields"}, status_code=400)

        # Handle the inbound SMS
        sms = InboundSMS(
            from_number=from_number,
            to_number=to_number or "+17194283999",
            message=message,
            contact_name=contact_name
        )

        result = await handle_inbound_sms(sms)

        return JSONResponse({
            "status": "ok",
            "reply_sent": result.reply_sent,
            "reply_preview": result.reply_text[:50] + "..." if result.reply_text else None
        })

    except Exception as e:
        logger.exception(f"Error in RingCentral SMS webhook: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/test/sms-reply")
async def test_sms_reply(from_number: str, message: str):
    """
    Test endpoint for SMS auto-reply.

    Use this to test how Gigi would respond to a message
    without actually sending an SMS.
    """
    caller_info = await verify_caller(from_number)
    reply = await generate_sms_response(message, caller_info)

    return {
        "from_number": from_number,
        "original_message": message,
        "caller_type": caller_info.caller_type.value,
        "caller_name": caller_info.name,
        "generated_reply": reply
    }


# =============================================================================
# Run with Uvicorn
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)

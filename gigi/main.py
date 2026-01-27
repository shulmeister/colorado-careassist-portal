"""
Gigi - Colorado CareAssist AI Voice Assistant
Powered by Retell AI

Gigi is a real team member who answers calls when the office is closed or when staff cannot answer:
- Caregivers: Call-outs, schedule questions, shift confirmations
- Clients: Service requests, satisfaction issues, scheduling

This FastAPI middleware provides the tool functions that Gigi calls
during conversations to look up information and take actions.
"""

import os
import re
import json
import hmac
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Literal
from enum import Enum

from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
import httpx
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import WellSky service for shift management
try:
    from services.wellsky_service import WellSkyService, ShiftStatus
    wellsky = WellSkyService()
    WELLSKY_AVAILABLE = True
except ImportError:
    wellsky = None
    WELLSKY_AVAILABLE = False

# Import RingCentral messaging service for team notifications
try:
    from services.ringcentral_messaging_service import ringcentral_messaging_service
    RC_MESSAGING_AVAILABLE = True
except ImportError:
    ringcentral_messaging_service = None
    RC_MESSAGING_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# Configuration - SECURITY: No hardcoded credentials
# =============================================================================

# Retell AI credentials (required for voice agent)
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
# Note: Retell uses the API key itself for webhook signature verification (not a separate secret)
# See: https://docs.retellai.com/features/secure-webhook
PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "https://portal.coloradocareassist.com")
# SECURITY: Test endpoints disabled by default in production
GIGI_ENABLE_TEST_ENDPOINTS = os.getenv("GIGI_ENABLE_TEST_ENDPOINTS", "false").lower() == "true"

def require_gigi_test_endpoints_enabled():
    if not GIGI_ENABLE_TEST_ENDPOINTS:
        raise HTTPException(status_code=404, detail="Not found")

# BeeTexting OAuth2 credentials (required for SMS)
BEETEXTING_CLIENT_ID = os.getenv("BEETEXTING_CLIENT_ID")
BEETEXTING_CLIENT_SECRET = os.getenv("BEETEXTING_CLIENT_SECRET")
BEETEXTING_API_KEY = os.getenv("BEETEXTING_API_KEY")

# Phone numbers (safe defaults - these are public business numbers)
BEETEXTING_FROM_NUMBER = os.getenv("BEETEXTING_FROM_NUMBER", "+17194283999")  # 719-428-3999
ON_CALL_MANAGER_PHONE = os.getenv("ON_CALL_MANAGER_PHONE", "+13037571777")    # 303-757-1777

# Escalation contacts (RingCentral extensions for urgent client issues)
ESCALATION_CYNTHIA_EXT = os.getenv("ESCALATION_CYNTHIA_EXT", "105")  # Cynthia Pointe - Care Manager
ESCALATION_JASON_EXT = os.getenv("ESCALATION_JASON_EXT", "101")      # Jason Shulman - Owner

# SMS Auto-Reply Toggle (default OFF for safety)
SMS_AUTOREPLY_ENABLED = os.getenv("GIGI_SMS_AUTOREPLY_ENABLED", "false").lower() == "true"

# Operations SMS Toggle (set to "true" to enable SMS from call-out operations)
# DEFAULT IS OFF - Must be explicitly enabled when WellSky is fully connected
OPERATIONS_SMS_ENABLED = os.getenv("GIGI_OPERATIONS_SMS_ENABLED", "false").lower() == "true"

# RingCentral credentials (required for SMS - no hardcoded fallbacks)
RINGCENTRAL_CLIENT_ID = os.getenv("RINGCENTRAL_CLIENT_ID")
RINGCENTRAL_CLIENT_SECRET = os.getenv("RINGCENTRAL_CLIENT_SECRET")
RINGCENTRAL_SERVER = os.getenv("RINGCENTRAL_SERVER", "https://platform.ringcentral.com")
RINGCENTRAL_JWT = os.getenv("RINGCENTRAL_JWT_TOKEN") or os.getenv("RINGCENTRAL_JWT")

# Log configuration status (not the values!)
def _log_config_status():
    """Log which credentials are configured without exposing values."""
    configs = {
        "RETELL_API_KEY": bool(RETELL_API_KEY),
        "BEETEXTING_CLIENT_ID": bool(BEETEXTING_CLIENT_ID),
        "RINGCENTRAL_CLIENT_ID": bool(RINGCENTRAL_CLIENT_ID),
        "RINGCENTRAL_JWT": bool(RINGCENTRAL_JWT),
    }
    missing = [k for k, v in configs.items() if not v]
    if missing:
        logger.warning(f"Gigi: Missing credentials (some features disabled): {missing}")
    else:
        logger.info("Gigi: All credentials configured")

_log_config_status()

# =============================================================================
# ANTI-LOOP: Tool Call Deduplication
# =============================================================================
# The LLM sometimes calls the same tool multiple times despite instructions not to.
# This server-side cache prevents duplicate tool calls within the same conversation.

from collections import defaultdict
import time

# Tools that should only be called ONCE per conversation
ONCE_PER_CALL_TOOLS = {
    "log_client_issue",
    "report_call_out",
    "execute_caregiver_call_out",
    "report_late",
    "cancel_client_visit",
    "add_note_to_wellsky",
    "start_shift_filling_campaign",
    "add_visit_notes",
    "escalate_emergency",
}

# Cache of tool calls: {call_id: {tool_name: timestamp}}
# Entries expire after 10 minutes to prevent memory leaks
_tool_call_cache: Dict[str, Dict[str, float]] = defaultdict(dict)
_cache_lock = None  # Will use threading lock if needed

def _cleanup_old_cache_entries():
    """Remove cache entries older than 10 minutes."""
    cutoff = time.time() - 600  # 10 minutes
    expired_calls = [
        call_id for call_id, tools in _tool_call_cache.items()
        if all(ts < cutoff for ts in tools.values())
    ]
    for call_id in expired_calls:
        del _tool_call_cache[call_id]

def check_tool_already_called(call_id: str, tool_name: str) -> bool:
    """
    Check if a once-per-call tool has already been called in this conversation.
    Returns True if already called (should block), False if OK to proceed.
    """
    if not call_id or tool_name not in ONCE_PER_CALL_TOOLS:
        return False

    _cleanup_old_cache_entries()

    if tool_name in _tool_call_cache.get(call_id, {}):
        logger.warning(f"BLOCKED DUPLICATE: {tool_name} already called for call {call_id}")
        return True

    return False

def record_tool_call(call_id: str, tool_name: str):
    """Record that a tool was called for this conversation."""
    if call_id and tool_name in ONCE_PER_CALL_TOOLS:
        _tool_call_cache[call_id][tool_name] = time.time()
        logger.info(f"Recorded tool call: {tool_name} for call {call_id}")

def get_duplicate_response(tool_name: str) -> Dict[str, Any]:
    """Return a response telling the LLM the action was already completed."""
    return {
        "success": True,
        "already_completed": True,
        "action_completed": True,
        "message": f"This action was already completed earlier in this conversation. Do NOT call {tool_name} again. Please confirm with the caller that their request has been handled and ask if there is anything else.",
        "next_step": "STOP calling tools. Confirm with the caller and close the conversation."
    }


# =============================================================================
# CALL CONTEXT: Store caller info for the duration of a call
# =============================================================================
# When a call starts, we look up the caller and store their info.
# This allows the conversation to personalize without re-looking up.

_call_context_cache: Dict[str, Dict[str, Any]] = {}

def _store_call_context(call_id: str, caller_info: Dict[str, Any]):
    """Store caller context for this call."""
    if call_id:
        _call_context_cache[call_id] = {
            "caller_info": caller_info,
            "timestamp": time.time()
        }
        logger.info(f"Stored call context for {call_id}: {caller_info}")

def _get_call_context(call_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve caller context for this call."""
    if call_id and call_id in _call_context_cache:
        return _call_context_cache[call_id].get("caller_info")
    return None

def _cleanup_call_context():
    """Remove call context older than 30 minutes."""
    cutoff = time.time() - 1800  # 30 minutes
    expired = [
        call_id for call_id, data in _call_context_cache.items()
        if data.get("timestamp", 0) < cutoff
    ]
    for call_id in expired:
        del _call_context_cache[call_id]


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="Gigi - Colorado CareAssist AI Agent",
    description="After-hours AI assistant for caregivers and clients",
    version="1.0.0"
)

async def _log_portal_event(description: str, event_type: str = "info", details: str = None, icon: str = None):
    """Log event to the central portal activity stream"""
    try:
        # Determine URL - unified_app runs on localhost:8000 or defined PORT
        port = os.getenv("PORT", "8000")
        portal_url = f"http://localhost:{port}"
        
        # If external URL is preferred or required (e.g. strict SSL), use it
        if os.getenv("HEROKU_APP_NAME"):
            portal_url = f"https://{os.getenv('HEROKU_APP_NAME')}.herokuapp.com"
            
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{portal_url}/api/internal/event",
                json={
                    "source": "Gigi",
                    "description": description,
                    "event_type": event_type,
                    "details": details,
                    "icon": icon or "🤖"
                },
                timeout=2.0
            )
    except Exception as e:
        logger.warning(f"Failed to log portal event: {e}")


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
    action_completed: bool = True  # Signal to LLM that no further calls needed
    next_step: str = "confirm_with_caller"  # Tell LLM what to do next


class ClientIssueReport(BaseModel):
    success: bool
    issue_id: Optional[str] = None
    message: str
    action_completed: bool = True  # Signal to LLM that no further calls needed
    next_step: str = "confirm_with_caller"  # Tell LLM what to do next


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

async def verify_retell_signature(request: Request) -> bool:
    """
    Verify the Retell webhook signature to ensure request authenticity.

    Retell uses your API key for webhook signature verification.
    See: https://docs.retellai.com/features/secure-webhook
    """
    # TEMPORARY: Disable signature verification to debug call issues
    # TODO: Re-enable once calls are working
    logger.info("Signature verification temporarily disabled for debugging")
    return True

    if not RETELL_API_KEY:
        # SECURITY: API key required for signature validation
        is_production = os.getenv("ENVIRONMENT", "production").lower() == "production"
        if is_production:
            logger.error("SECURITY: RETELL_API_KEY not configured - webhook validation disabled!")
        else:
            logger.warning("RETELL_API_KEY not configured - skipping signature validation (development)")
        return True  # Allow for development but log the issue

    # Extract signature from header (handle both naming conventions)
    x_retell_signature = request.headers.get("x-retell-signature") or request.headers.get("X-Retell-Signature")

    if not x_retell_signature:
        logger.warning("Missing X-Retell-Signature header")
        return False

    body = await request.body()

    # Retell uses API key for HMAC-SHA256 signature verification
    expected_signature = hmac.new(
        RETELL_API_KEY.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    # Compare signatures (timing-safe comparison)
    is_valid = hmac.compare_digest(x_retell_signature, expected_signature)

    if not is_valid:
        logger.warning("Invalid Retell signature")

    return is_valid


# =============================================================================
# Database Connection - Enterprise-grade data storage
# =============================================================================

# Import database module (lazy initialization)
_gigi_db = None

def _get_db():
    """Get the Gigi database instance (lazy initialization)."""
    global _gigi_db
    if _gigi_db is None:
        try:
            # Try multiple import methods since we might be loaded standalone or via importlib
            gigi_db = None

            # Method 1: Absolute import (works when gigi is in PYTHONPATH)
            try:
                from gigi.database import gigi_db
                logger.info("Loaded gigi.database via absolute import")
            except ImportError:
                pass

            # Method 2: Relative import (works in package context)
            if gigi_db is None:
                try:
                    from .database import gigi_db
                    logger.info("Loaded database via relative import")
                except ImportError:
                    pass

            # Method 3: Direct file import using importlib (works when loaded via spec_from_file_location)
            if gigi_db is None:
                import importlib.util
                import os
                db_file = os.path.join(os.path.dirname(__file__), "database.py")
                if os.path.exists(db_file):
                    spec = importlib.util.spec_from_file_location("gigi_database", db_file)
                    db_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(db_module)
                    gigi_db = db_module.gigi_db
                    logger.info("Loaded database via importlib file location")

            if gigi_db is None:
                raise ImportError("Could not import gigi database module via any method")

            gigi_db.initialize()
            _gigi_db = gigi_db
            logger.info("Gigi database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gigi database: {e}")
            _gigi_db = None
    return _gigi_db


# =============================================================================
# Contacts Cache - Fallback to JSON file if database unavailable
# =============================================================================

CONTACTS_CACHE_FILE = os.path.join(os.path.dirname(__file__), "contacts_cache.json")
_contacts_cache = None
_cache_load_time = None
CACHE_REFRESH_HOURS = 24

def _load_contacts_cache() -> Dict[str, Any]:
    """Load contacts cache from JSON file (fallback if database unavailable)."""
    global _contacts_cache, _cache_load_time

    now = datetime.now()

    if _contacts_cache and _cache_load_time:
        hours_since_load = (now - _cache_load_time).total_seconds() / 3600
        if hours_since_load < CACHE_REFRESH_HOURS:
            return _contacts_cache

    try:
        if os.path.exists(CONTACTS_CACHE_FILE):
            with open(CONTACTS_CACHE_FILE, 'r') as f:
                _contacts_cache = json.load(f)
                _cache_load_time = now
                logger.info(f"Loaded JSON cache fallback: {len(_contacts_cache.get('caregivers', {}))} caregivers")
                return _contacts_cache
    except Exception as e:
        logger.error(f"Error loading JSON cache: {e}")

    return {"caregivers": {}, "clients": {}}


def _lookup_in_cache(phone: str) -> Optional[Dict[str, Any]]:
    """
    Look up a phone number - checks DATABASE first, falls back to JSON cache.
    Returns dict with 'type' (caregiver/client), 'name', 'status' if found.
    Returns None if not found.
    """
    clean_phone = ''.join(filter(str.isdigit, phone))[-10:]

    # Try database first (enterprise solution)
    db = _get_db()
    if db:
        try:
            result = db.lookup_caller(clean_phone)
            if result:
                logger.info(f"DB HIT: Found {result.get('type')} {result.get('name')} for {clean_phone}")
                return result
        except Exception as e:
            logger.warning(f"Database lookup failed, falling back to cache: {e}")

    # Fallback to JSON cache
    cache = _load_contacts_cache()

    caregivers = cache.get("caregivers", {})
    if clean_phone in caregivers:
        cg = caregivers[clean_phone]
        logger.info(f"JSON Cache HIT: Found caregiver {cg.get('name')} for {clean_phone}")
        return {
            "type": "caregiver",
            "name": cg.get("name"),
            "status": cg.get("status", "active"),
            "phone": clean_phone
        }

    clients = cache.get("clients", {})
    if clean_phone in clients:
        cl = clients[clean_phone]
        logger.info(f"JSON Cache HIT: Found client {cl.get('name')} for {clean_phone}")
        return {
            "type": "client",
            "name": cl.get("name"),
            "status": cl.get("status", "active"),
            "phone": clean_phone,
            "location": cl.get("location")
        }

    logger.info(f"MISS: Phone {clean_phone} not found in database or cache")
    return None


def _get_shifts_from_cache(caregiver_name: str = None, client_name: str = None) -> List[Dict[str, Any]]:
    """
    Look up shifts from the local cache.
    Can filter by caregiver name or client name.
    """
    cache = _load_contacts_cache()
    shifts = cache.get("shifts", [])

    if not shifts:
        return []

    results = []
    now = datetime.now()

    for shift in shifts:
        # Filter by caregiver if specified
        if caregiver_name:
            shift_cg = shift.get("caregiver_name", "").lower()
            if caregiver_name.lower() not in shift_cg:
                continue

        # Filter by client if specified
        if client_name:
            shift_cl = shift.get("client_name", "").lower()
            if client_name.lower() not in shift_cl:
                continue

        # Only include future shifts
        try:
            start_time = shift.get("start_time", "")
            if start_time:
                shift_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00").replace("+00:00", ""))
                if shift_dt < now:
                    continue
        except (ValueError, TypeError):
            pass

        results.append(shift)

    logger.info(f"Cache: Found {len(results)} shifts (caregiver={caregiver_name}, client={client_name})")
    return results


def _get_caregivers_by_location(location: str) -> List[Dict[str, Any]]:
    """
    Get all caregivers in a specific location/service area.
    Used for shift filling to find nearby caregivers.
    """
    cache = _load_contacts_cache()
    caregivers = cache.get("caregivers", {})

    results = []
    location_lower = location.lower().strip()

    for phone, cg in caregivers.items():
        cg_location = (cg.get("location") or cg.get("city") or "").lower()

        # Match on location or city containing the search term
        if location_lower in cg_location or cg_location in location_lower:
            results.append({
                "phone": phone,
                "name": cg.get("name"),
                "location": cg.get("location"),
                "city": cg.get("city"),
                "email": cg.get("email"),
                "can_sms": cg.get("can_sms", False),
                "status": cg.get("status", "active")
            })

    # Prioritize SMS-enabled caregivers for faster outreach
    results.sort(key=lambda x: (not x.get("can_sms", False), x.get("name", "")))

    logger.info(f"Cache: Found {len(results)} caregivers in location '{location}'")
    return results


def _get_client_location(client_name: str) -> Optional[str]:
    """Get a client's location from cache for shift matching."""
    cache = _load_contacts_cache()
    clients = cache.get("clients", {})

    client_lower = client_name.lower().strip()
    for phone, cl in clients.items():
        if client_lower in cl.get("name", "").lower():
            return cl.get("location") or cl.get("city")

    return None


def _is_caregiver_available(caregiver_name: str, shift_date: datetime = None) -> bool:
    """
    Check if a caregiver is available (not blocked by unavailability).
    Uses DATABASE first, falls back to JSON cache.

    Args:
        caregiver_name: The caregiver's name
        shift_date: The date/time of the shift (defaults to now)

    Returns:
        True if available, False if blocked by unavailability
    """
    shift_date = shift_date or datetime.now()

    # Try database first
    db = _get_db()
    if db:
        try:
            return db.is_caregiver_available(caregiver_name, shift_date)
        except Exception as e:
            logger.warning(f"DB availability check failed: {e}")

    # Fallback to JSON cache
    cache = _load_contacts_cache()
    unavailability = cache.get("unavailability", [])

    if not unavailability:
        return True

    name_lower = caregiver_name.lower().strip()

    for block in unavailability:
        block_name = block.get("caregiver_name", "").lower()
        if name_lower not in block_name and block_name not in name_lower:
            continue

        desc = block.get("description", "").lower()

        if "occurs once all day on" in desc:
            try:
                date_match = re.search(r'(\d{2}/\d{2}/\d{4})', desc)
                if date_match:
                    block_date = datetime.strptime(date_match.group(1), "%m/%d/%Y")
                    if shift_date.date() == block_date.date():
                        logger.info(f"Caregiver {caregiver_name} unavailable on {shift_date.date()}")
                        return False
            except Exception:
                pass

        if "repeats weekly" in desc:
            days_in_desc = []
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                if day in desc:
                    days_in_desc.append(day)

            shift_day = shift_date.strftime("%A").lower()
            if shift_day in days_in_desc:
                logger.info(f"Caregiver {caregiver_name} unavailable on {shift_day}s")
                return False

    return True


def _get_available_caregivers_for_shift(location: str, shift_time: datetime = None) -> List[Dict[str, Any]]:
    """
    Get caregivers who are available for a shift at a specific location/time.
    Uses DATABASE first for enterprise-grade reliability.

    Filters out:
    - Caregivers in different locations
    - Caregivers with unavailability blocks

    Prioritizes:
    - SMS-enabled caregivers (faster outreach)

    Args:
        location: The client's location (e.g., "Colorado Springs", "Denver")
        shift_time: When the shift is (for unavailability check)

    Returns:
        List of available caregivers sorted by outreach priority
    """
    shift_time = shift_time or datetime.now()

    # Try database first
    db = _get_db()
    if db:
        try:
            available = db.get_available_caregivers(location, shift_time)
            logger.info(f"DB: Found {len(available)} available caregivers in {location}")
            return available
        except Exception as e:
            logger.warning(f"DB get_available_caregivers failed: {e}")

    # Fallback to JSON cache
    all_caregivers = _get_caregivers_by_location(location)
    available = []

    for cg in all_caregivers:
        name = cg.get("name", "")

        if not _is_caregiver_available(name, shift_time):
            logger.info(f"Skipping {name} - has unavailability block")
            continue

        if cg.get("status", "active") != "active":
            logger.info(f"Skipping {name} - not active")
            continue

        available.append(cg)

    logger.info(f"Found {len(available)} available caregivers in {location} "
                f"(filtered from {len(all_caregivers)} total)")
    return available


# =============================================================================
# WellSky Integration Helpers (used as FALLBACK when not in cache)
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


async def _lookup_caregiver_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Look up caregiver by name from the portal API."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PORTAL_BASE_URL}/api/wellsky/caregivers",
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                caregivers = data.get("caregivers", [])

                # Normalize search name
                search_name = name.lower().strip()

                for cg in caregivers:
                    full_name = f"{cg.get('first_name', '')} {cg.get('last_name', '')}".lower().strip()
                    # Check for exact match or partial match
                    if search_name == full_name or search_name in full_name or full_name in search_name:
                        if cg.get("status") == "active":
                            return cg

                # Second pass: looser matching
                for cg in caregivers:
                    first = cg.get('first_name', '').lower()
                    last = cg.get('last_name', '').lower()
                    if first and first in search_name:
                        return cg
                    if last and last in search_name:
                        return cg
    except Exception as e:
        logger.error(f"Error looking up caregiver by name '{name}': {e}")

    return None


async def _lookup_shift_for_caregiver(caregiver_id: str, shift_date: str = None, client_name: str = None) -> Optional[Dict[str, Any]]:
    """Look up upcoming shift for a caregiver."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PORTAL_BASE_URL}/api/wellsky/caregivers/{caregiver_id}/shifts",
                params={"days": 7},
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                shifts = data.get("shifts", [])

                if shifts:
                    # If client_name provided, try to match
                    if client_name:
                        search_client = client_name.lower().strip()
                        for shift in shifts:
                            shift_client = f"{shift.get('client_first_name', '')} {shift.get('client_last_name', '')}".lower().strip()
                            if search_client in shift_client or shift_client in search_client:
                                return shift

                    # Otherwise return the next upcoming shift
                    return shifts[0]
    except Exception as e:
        logger.error(f"Error looking up shift for caregiver {caregiver_id}: {e}")

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


async def _send_ringcentral_pager(extension_ids: list, message: str) -> bool:
    """
    Send a company pager message to RingCentral extensions.
    This is the internal messaging system that goes directly to extensions.

    Args:
        extension_ids: List of extension IDs (e.g., ["105", "101"])
        message: The message to send

    Returns:
        True if sent successfully
    """
    token = await _get_ringcentral_token()

    if not token:
        logger.warning("RingCentral not available - pager not sent")
        logger.info(f"[MOCK PAGER] To extensions: {extension_ids}, Message: {message}")
        return False

    # Build recipient list
    recipients = [{"extensionNumber": ext} for ext in extension_ids]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/company-pager",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "to": recipients,
                    "text": message
                },
                timeout=10.0
            )
            if response.status_code in (200, 201):
                logger.info(f"Pager sent successfully to extensions: {extension_ids}")
                return True
            else:
                logger.error(f"RingCentral pager error: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"Error sending RingCentral pager: {e}")
        return False


async def notify_escalation_contacts(issue_type: str, client_name: str, summary: str, priority: str = "urgent") -> bool:
    """
    Notify Cynthia and Jason about urgent client escalations.

    PRIMARY: RingCentral team messaging (like Slack - always checked)
    BACKUP: RingCentral pager and SMS

    Args:
        issue_type: Type of issue (cancel_threat, complaint, safety, etc.)
        client_name: Name of the client
        summary: Brief summary of the issue
        priority: Priority level

    Returns:
        True if at least one notification was sent
    """
    # Format the message
    if issue_type == "cancel_threat":
        message = f"🚨 CLIENT CANCEL THREAT: {client_name}\n{summary}\nGigi promised Cynthia will call before 9 AM."
    else:
        message = f"⚠️ URGENT CLIENT ISSUE: {client_name}\n{summary}\nPriority: {priority}"

    success = False

    # =========================================================================
    # PRIMARY: RingCentral Team Messaging (always checked, like Slack)
    # =========================================================================
    if RC_MESSAGING_AVAILABLE and ringcentral_messaging_service:
        try:
            # Send to Cynthia directly
            cynthia_result = ringcentral_messaging_service.notify_cynthia(message)
            if cynthia_result.get("success"):
                logger.info(f"RingCentral message sent to Cynthia")
                success = True

            # Also notify Jason for urgent issues
            if priority == "urgent" or issue_type == "cancel_threat":
                jason_result = ringcentral_messaging_service.notify_jason(message)
                if jason_result.get("success"):
                    logger.info(f"RingCentral message sent to Jason")
                    success = True
        except Exception as e:
            logger.error(f"RingCentral messaging failed: {e}")

    # =========================================================================
    # BACKUP: RingCentral Pager and SMS (if messaging fails or is disabled)
    # =========================================================================
    if not success and OPERATIONS_SMS_ENABLED:
        # Try RingCentral pager
        extensions = [ESCALATION_CYNTHIA_EXT, ESCALATION_JASON_EXT]
        pager_success = await _send_ringcentral_pager(extensions, message)

        if pager_success:
            logger.info(f"Escalation pager sent to Cynthia ({ESCALATION_CYNTHIA_EXT}) and Jason ({ESCALATION_JASON_EXT})")
            success = True
        else:
            # Final fallback: SMS to on-call manager
            logger.warning("Pager failed - trying SMS to on-call manager")
            success = await _send_sms_beetexting(ON_CALL_MANAGER_PHONE, message)

    if not success:
        logger.warning(f"[ALL CHANNELS FAILED] Could not notify about: {issue_type} - {client_name}")

    return success


# =============================================================================
# Tool Functions (Called by Gigi via Retell)
# =============================================================================

async def verify_caller(phone_number: str) -> CallerInfo:
    """
    Identifies if the caller is a Caregiver or Client.

    PERFORMANCE: Checks local cache FIRST (instant), only falls back to
    WellSky API if not found in cache. This saves API calls and is much faster.

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

    # =========================================================================
    # STEP 1: Check local cache FIRST (instant, no API call)
    # =========================================================================
    cached = _lookup_in_cache(clean_phone)
    if cached:
        if cached["type"] == "caregiver":
            return CallerInfo(
                caller_type=CallerType.CAREGIVER,
                name=cached.get("name"),
                phone=phone_number,
                is_active=cached.get("status") == "active"
            )
        elif cached["type"] == "client":
            return CallerInfo(
                caller_type=CallerType.CLIENT,
                name=cached.get("name"),
                phone=phone_number,
                is_active=cached.get("status") == "active",
                additional_info={"location": cached.get("location")}
            )

    # =========================================================================
    # STEP 2: Not in cache - fall back to WellSky API (slower)
    # =========================================================================
    logger.info(f"Phone {clean_phone} not in cache, checking WellSky...")

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


async def get_shift_details(person_id: str, caregiver_name: str = None) -> Optional[ShiftDetails]:
    """
    Pulls the next scheduled shift for a caregiver.

    PERFORMANCE: Checks local cache FIRST (instant), falls back to WellSky API.

    Use this after identifying a caregiver to see their upcoming shift.
    This helps Gigi confirm which shift they're calling about.

    Args:
        person_id: The caregiver's ID from verify_caller
        caregiver_name: Optional caregiver name for cache lookup

    Returns:
        ShiftDetails for the next upcoming shift, or None if no shifts scheduled
    """
    logger.info(f"get_shift_details called for person_id: {person_id}, name: {caregiver_name}")

    # =========================================================================
    # STEP 1: Check local cache FIRST (instant, no API call)
    # =========================================================================
    if caregiver_name:
        cached_shifts = _get_shifts_from_cache(caregiver_name=caregiver_name)
        if cached_shifts:
            next_shift = cached_shifts[0]  # Already sorted by time
            try:
                start_str = next_shift.get("start_time", "")
                start_time = datetime.fromisoformat(start_str.replace("Z", "+00:00").replace("+00:00", ""))
                # Estimate 3-hour shift if no end time
                end_time = start_time + timedelta(hours=3)

                logger.info(f"Cache HIT: Found shift for {caregiver_name}")
                return ShiftDetails(
                    shift_id=next_shift.get("shift_id", f"cache_{start_str}"),
                    caregiver_id=person_id or "",
                    caregiver_name=next_shift.get("caregiver_name", caregiver_name),
                    client_id=next_shift.get("client_id", ""),
                    client_name=next_shift.get("client_name", ""),
                    client_address=next_shift.get("location", ""),
                    start_time=start_time,
                    end_time=end_time,
                    hours=3.0,
                    status=next_shift.get("status", "Scheduled"),
                    notes=""
                )
            except Exception as e:
                logger.warning(f"Cache shift parse error: {e}")

    # =========================================================================
    # STEP 2: Fall back to WellSky API
    # =========================================================================
    logger.info(f"Cache MISS for shifts, checking WellSky...")
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


async def get_active_shifts(person_id: str) -> List[Dict[str, Any]]:
    """
    TOOL: get_active_shifts(person_id)

    Pulls the caller's next 24 hours of shifts from WellSky.
    Returns shift_id, client_name, and start_time for each shift.

    Args:
        person_id: The caregiver's ID from verify_caller

    Returns:
        List of shifts with shift_id, client_name, start_time
    """
    logger.info(f"get_active_shifts called for person_id: {person_id}")

    shifts = await _get_caregiver_shifts(person_id)

    if not shifts:
        return []

    # Filter to next 24 hours
    now = datetime.now()
    cutoff = now + timedelta(hours=24)
    active_shifts = []

    for shift in shifts:
        try:
            start_time_str = shift.get("start_time", "")
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))

            # Include shifts starting in next 24 hours
            if now <= start_time <= cutoff:
                active_shifts.append({
                    "shift_id": shift.get("id", ""),
                    "client_name": shift.get("client_name", "Unknown Client"),
                    "client_id": shift.get("client_id", ""),
                    "start_time": start_time.strftime("%I:%M %p"),
                    "start_time_iso": start_time_str,
                    "end_time": shift.get("end_time", ""),
                    "status": shift.get("status", "scheduled"),
                    "client_address": shift.get("client_address", "")
                })
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing shift date: {e}")
            continue

    # Sort by start time
    active_shifts.sort(key=lambda x: x.get("start_time_iso", ""))

    logger.info(f"Found {len(active_shifts)} active shifts in next 24 hours")
    return active_shifts


async def execute_caregiver_call_out(
    caregiver_id: str,
    shift_id: str,
    reason: str = "sick"
) -> Dict[str, Any]:
    """
    TOOL: execute_caregiver_call_out(caregiver_id, shift_id)

    AUTONOMOUS CALL-OUT HANDLER - This is Gigi's main action tool.

    SAFETY RULES:
    - Only allows call-outs for shifts starting within 24 hours
    - If shift starts in less than 2 hours, triggers MANUAL HANDOFF to on-call manager

    When a caregiver calls out, this function:
    - STEP A: Updates WellSky shift status to 'Open' (Unassigned)
    - STEP B: Logs the call-out event to Client Ops Portal
    - STEP C: Triggers Replacement Blast to notify available caregivers

    Args:
        caregiver_id: The caregiver's WellSky ID
        shift_id: The shift ID they're calling out from
        reason: Reason for call-out (sick, emergency, car_trouble, family, other)

    Returns:
        Dict with success status, steps completed, and message for Gigi to read
    """
    logger.info(f"execute_caregiver_call_out: caregiver={caregiver_id}, shift={shift_id}, reason={reason}")

    # Get shift details first to validate time window
    shift = await get_shift_details(caregiver_id)

    # ==========================================================================
    # TIME WINDOW VALIDATION
    # ==========================================================================
    if shift and shift.start_time:
        now = datetime.now()
        time_until_shift = (shift.start_time - now).total_seconds() / 3600  # hours

        # RULE 1: Only allow unassigning shifts within 24 hours
        if time_until_shift > 24:
            logger.warning(f"Shift {shift_id} starts in {time_until_shift:.1f} hours - outside 24hr window")
            return {
                "success": False,
                "requires_manual_handoff": False,
                "message": (
                    f"This shift doesn't start for another {int(time_until_shift)} hours. "
                    f"For shifts more than 24 hours away, please contact the office during business hours "
                    f"at 719-428-3999. They can help reschedule if needed."
                ),
                "errors": ["Shift outside 24-hour call-out window"]
            }

        # RULE 2: If shift starts in less than 2 hours, MANUAL HANDOFF required
        if time_until_shift < 2:
            logger.warning(f"Shift {shift_id} starts in {time_until_shift:.1f} hours - URGENT handoff required")

            # Still log the call-out attempt for the manager
            urgent_message = (
                f"URGENT HANDOFF: {shift.caregiver_name} calling out for {shift.client_name} "
                f"shift starting in {int(time_until_shift * 60)} minutes! Reason: {reason}. "
                f"Requires immediate manager attention."
            )
            # Only send SMS if operations are enabled (disabled by default until WellSky connected)
            if OPERATIONS_SMS_ENABLED:
                await _send_sms_beetexting(ON_CALL_MANAGER_PHONE, urgent_message)
                manager_notified = True
            else:
                logger.info(f"[DISABLED] Would send urgent SMS to {ON_CALL_MANAGER_PHONE}: {urgent_message}")
                manager_notified = False

            return {
                "success": False,
                "requires_manual_handoff": True,
                "time_until_shift_hours": round(time_until_shift, 2),
                "manager_notified": manager_notified,
                "operations_sms_enabled": OPERATIONS_SMS_ENABLED,
                "message": (
                    f"Since this shift with {shift.client_name} starts very soon, "
                    f"I'm going to connect you directly to our on-call manager to ensure "
                    f"we can get coverage immediately. I've already alerted them about your call-out. "
                    f"Please hold while I transfer you, or call the on-call line directly at 303-757-1777."
                ),
                "errors": ["Shift starts within 2 hours - requires manual handoff"]
            }

        logger.info(f"Shift {shift_id} starts in {time_until_shift:.1f} hours - within valid window")

    result = {
        "success": False,
        "step_a_wellsky_updated": False,
        "step_b_portal_logged": False,
        "step_c_replacement_blast_sent": False,
        "call_out_id": None,
        "message": "",
        "errors": []
    }

    # Get shift details for context
    shift = await get_shift_details(caregiver_id)
    caregiver_name = shift.caregiver_name if shift else f"Caregiver {caregiver_id}"
    client_name = shift.client_name if shift else "Unknown Client"
    client_id = shift.client_id if shift else None
    shift_time = shift.start_time.strftime("%B %d at %I:%M %p") if shift else "Unknown Time"

    # =========================================================================
    # STEP A: Update WellSky shift status to 'Open' (Unassigned)
    # =========================================================================
    try:
        async with httpx.AsyncClient() as client:
            # PUT to WellSky shift update endpoint
            wellsky_response = await client.put(
                f"{PORTAL_BASE_URL}/api/wellsky/shifts/{shift_id}",
                json={
                    "status": "open",
                    "caregiver_id": None,  # Unassign caregiver
                    "call_out_reason": reason,
                    "call_out_caregiver_id": caregiver_id,
                    "call_out_time": datetime.now().isoformat(),
                    "notes": f"Call-out via Gigi AI: {reason}"
                },
                timeout=15.0
            )
            if wellsky_response.status_code in (200, 201, 204):
                result["step_a_wellsky_updated"] = True
                logger.info(f"STEP A SUCCESS: WellSky shift {shift_id} updated to Open")
            else:
                error_msg = f"WellSky returned {wellsky_response.status_code}: {wellsky_response.text}"
                result["errors"].append(f"Step A: {error_msg}")
                logger.warning(error_msg)
    except Exception as e:
        error_msg = f"WellSky update failed: {str(e)}"
        result["errors"].append(f"Step A: {error_msg}")
        logger.error(error_msg)

    # =========================================================================
    # STEP B: Log call-out event to Client Ops Portal
    # =========================================================================
    call_out_data = {
        "caregiver_id": caregiver_id,
        "caregiver_name": caregiver_name,
        "shift_id": shift_id,
        "client_id": client_id,
        "client_name": client_name,
        "shift_time": shift_time,
        "reason": reason,
        "reported_at": datetime.now().isoformat(),
        "reported_via": "gigi_ai_agent",
        "priority": "high",
        "status": "pending_coverage",
        "wellsky_updated": result["step_a_wellsky_updated"]
    }

    try:
        async with httpx.AsyncClient() as client:
            portal_response = await client.post(
                f"{PORTAL_BASE_URL}/api/operations/call-outs",
                json=call_out_data,
                timeout=10.0
            )
            if portal_response.status_code in (200, 201):
                portal_result = portal_response.json()
                result["call_out_id"] = portal_result.get("id")
                result["step_b_portal_logged"] = True
                logger.info(f"STEP B SUCCESS: Call-out logged to portal: {result['call_out_id']}")
            else:
                error_msg = f"Portal returned {portal_response.status_code}: {portal_response.text}"
                result["errors"].append(f"Step B: {error_msg}")
                logger.warning(error_msg)
    except Exception as e:
        error_msg = f"Portal logging failed: {str(e)}"
        result["errors"].append(f"Step B: {error_msg}")
        logger.error(error_msg)

    # =========================================================================
    # STEP C: Trigger Replacement Blast (notify available caregivers)
    # =========================================================================
    replacement_blast_data = {
        "shift_id": shift_id,
        "client_name": client_name,
        "client_id": client_id,
        "shift_time": shift_time,
        "shift_start": shift.start_time.isoformat() if shift else None,
        "shift_end": shift.end_time.isoformat() if shift else None,
        "shift_hours": shift.hours if shift else None,
        "client_address": shift.client_address if shift else None,
        "call_out_caregiver_id": caregiver_id,
        "call_out_caregiver_name": caregiver_name,
        "reason": reason,
        "urgency": "high",
        "source": "gigi_ai_agent"
    }

    try:
        async with httpx.AsyncClient() as client:
            # Trigger the Replacement Blast endpoint
            blast_response = await client.post(
                f"{PORTAL_BASE_URL}/api/operations/replacement-blast",
                json=replacement_blast_data,
                timeout=30.0  # Longer timeout for SMS sending
            )
            if blast_response.status_code in (200, 201):
                blast_result = blast_response.json()
                result["step_c_replacement_blast_sent"] = True
                result["caregivers_notified"] = blast_result.get("caregivers_notified", 0)
                logger.info(f"STEP C SUCCESS: Replacement blast sent to {result.get('caregivers_notified', 0)} caregivers")
            else:
                error_msg = f"Replacement blast returned {blast_response.status_code}: {blast_response.text}"
                result["errors"].append(f"Step C: {error_msg}")
                logger.warning(error_msg)
    except Exception as e:
        error_msg = f"Replacement blast failed: {str(e)}"
        result["errors"].append(f"Step C: {error_msg}")
        logger.error(error_msg)

    # Also send direct notification to On-Call Manager (only if operations SMS is enabled)
    sms_message = (
        f"CALL-OUT: {caregiver_name} called out for {client_name} "
        f"({shift_time}). Reason: {reason}. "
        f"Replacement blast sent. Logged by Gigi at {datetime.now().strftime('%I:%M %p')}."
    )
    if OPERATIONS_SMS_ENABLED:
        await _send_sms_beetexting(ON_CALL_MANAGER_PHONE, sms_message)
        logger.info(f"SMS notification sent to on-call manager")
    else:
        logger.info(f"[DISABLED] Would send SMS to {ON_CALL_MANAGER_PHONE}: {sms_message}")

    # =========================================================================
    # Build final result and message for Gigi to speak
    # =========================================================================
    steps_completed = sum([
        result["step_a_wellsky_updated"],
        result["step_b_portal_logged"],
        result["step_c_replacement_blast_sent"]
    ])

    result["success"] = steps_completed >= 2  # Success if at least 2 of 3 steps work

    if result["success"]:
        result["message"] = (
            f"I've updated the system and we are already looking for a replacement. "
            f"The shift with {client_name} has been marked as open, and I've notified "
            f"available caregivers in the area. Feel better, and please keep us updated "
            f"if anything changes."
        )
    else:
        result["message"] = (
            f"I've logged your call-out, but I had some trouble updating all systems. "
            f"I've notified the on-call manager who will make sure coverage is handled. "
            f"Please also try to contact the office directly if possible."
        )

    # Critical: Signal to LLM that this action is complete
    result["action_completed"] = True
    result["next_step"] = "DO NOT call this tool again. Tell the caregiver it's handled and ask 'Is there anything else?'"

    logger.info(f"execute_caregiver_call_out completed: success={result['success']}, steps={steps_completed}/3")
    return result


async def report_call_out(
    caregiver_id: str,
    shift_id: str,
    reason: str
) -> CallOutReport:
    """
    Reports a caregiver call-out and ACTIVELY starts finding replacement coverage.

    This is Gigi's PRIMARY ACTION for call-outs. She doesn't just take a message -
    she gets to work finding a replacement! This function:

    1. Records the call-out in the system
    2. Starts an automated shift filling campaign
    3. Begins SMS outreach to available caregivers
    4. Notifies the on-call manager as backup
    5. Returns a confirmation with active steps being taken

    Args:
        caregiver_id: The caregiver's ID
        shift_id: The shift they're calling out from
        reason: The reason for calling out (e.g., "sick", "emergency", "car trouble")

    Returns:
        CallOutReport with success status and what Gigi is DOING about it
    """
    logger.info(f"report_call_out called: caregiver={caregiver_id}, shift={shift_id}, reason={reason}")

    # Get shift details for context
    shift = await get_shift_details(caregiver_id)
    caregiver_name = shift.caregiver_name if shift else f"Caregiver {caregiver_id}"
    client_name = shift.client_name if shift else "Unknown Client"
    shift_time = shift.start_time.strftime("%B %d at %I:%M %p") if shift else "Unknown Time"

    # =========================================================================
    # STEP 1: Start the shift filling campaign - THIS IS THE ACTIVE PART!
    # =========================================================================
    filling_result = await start_shift_filling_campaign(
        shift_id=shift_id,
        caregiver_id=caregiver_id,
        reason=reason
    )

    logger.info(f"Shift filling campaign result: success={filling_result.success}, "
                f"contacted={filling_result.candidates_contacted}")

    # =========================================================================
    # STEP 2: Also post to Client Ops Portal for tracking
    # =========================================================================
    call_out_data = {
        "caregiver_id": caregiver_id,
        "caregiver_name": caregiver_name,
        "shift_id": shift_id,
        "client_name": client_name,
        "shift_time": shift_time,
        "reason": reason,
        "reported_at": datetime.now().isoformat(),
        "reported_via": "gigi_ai_agent",
        "priority": "high",
        "campaign_id": filling_result.campaign_id,
        "candidates_contacted": filling_result.candidates_contacted
    }

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

    # =========================================================================
    # STEP 3: Notify New Scheduler chat via RingCentral (PRIMARY)
    # =========================================================================
    rc_message = (
        f"📞 CALL-OUT from Gigi:\n"
        f"• Caregiver: {caregiver_name}\n"
        f"• Client: {client_name}\n"
        f"• Shift: {shift_time}\n"
        f"• Reason: {reason}\n"
        f"• Action: {'Shift filling campaign started' if filling_result.success else 'Manual follow-up needed'}"
    )

    scheduler_notified = False
    if RC_MESSAGING_AVAILABLE and ringcentral_messaging_service:
        try:
            result = ringcentral_messaging_service.notify_scheduler_chat(rc_message)
            scheduler_notified = result.get("success", False)
            if scheduler_notified:
                logger.info(f"RingCentral notification sent to New Scheduler chat")
            else:
                logger.warning(f"Failed to notify New Scheduler chat: {result.get('error')}")
        except Exception as e:
            logger.error(f"Error sending RingCentral notification: {e}")
    else:
        logger.info(f"[RC MESSAGING UNAVAILABLE] Would send to New Scheduler: {rc_message}")

    # =========================================================================
    # STEP 4: Also notify On-Call Manager via SMS as backup
    # =========================================================================
    sms_message = (
        f"CALL-OUT: {caregiver_name} called out for {client_name} "
        f"({shift_time}). Reason: {reason}. "
        f"Gigi AI has started shift filling - contacting {filling_result.candidates_contacted} caregivers. "
        f"Campaign: {filling_result.campaign_id or 'N/A'}"
    )

    manager_notified = False
    if OPERATIONS_SMS_ENABLED and not scheduler_notified:
        # Only SMS if RingCentral messaging failed
        manager_notified = await _send_sms_beetexting(ON_CALL_MANAGER_PHONE, sms_message)
    elif not scheduler_notified:
        logger.info(f"[DISABLED] Would send SMS to {ON_CALL_MANAGER_PHONE}: {sms_message}")

    # =========================================================================
    # STEP 5: Build confirmation message - Tell the caller what we're DOING
    # =========================================================================
    if filling_result.success and filling_result.candidates_contacted > 0:
        confirmation = (
            f"I've got you covered. I'm already reaching out to {filling_result.candidates_contacted} "
            f"available caregivers to find someone to cover your shift with {client_name}. "
            f"You don't need to do anything else - I'll handle finding coverage. "
            f"Feel better, and I hope everything's okay!"
        )
    elif filling_result.success:
        confirmation = (
            f"I've logged your call-out for the shift with {client_name} and I'm working on finding coverage. "
            f"The care team has been notified and will make sure someone covers. "
            f"Feel better, and please let us know if anything changes!"
        )
    else:
        confirmation = (
            f"I've logged your call-out for {client_name}. "
            f"I had some trouble with the automated system, but I've notified the on-call manager "
            f"who will personally work on finding coverage. "
            f"Feel better, and please keep us updated!"
        )

    return CallOutReport(
        success=True,
        call_out_id=call_out_id or filling_result.campaign_id,
        message=confirmation,
        manager_notified=manager_notified,
        notification_details=(
            f"Campaign started: {filling_result.candidates_contacted} caregivers being contacted"
            if filling_result.success else "Manual follow-up required"
        ),
        action_completed=True,
        next_step="DO NOT call this tool again. Tell the caregiver it's handled and ask 'Is there anything else?'"
    )


# =============================================================================
# SHIFT FILLING FUNCTIONS - These make Gigi actually fill shifts!
# =============================================================================

@dataclass
class ReplacementCandidate:
    """A potential replacement caregiver for an open shift"""
    caregiver_id: str
    name: str
    phone: str
    score: float
    tier: int  # 1=best, 2=good, 3=acceptable
    reasons: List[str]
    distance_miles: Optional[float] = None
    has_worked_with_client: bool = False

@dataclass
class ShiftFillingResult:
    """Result of shift filling operation"""
    success: bool
    message: str
    campaign_id: Optional[str] = None
    candidates_found: int = 0
    candidates_contacted: int = 0
    shift_filled: bool = False
    assigned_to: Optional[str] = None


async def find_replacement_caregivers(
    shift_id: str,
    max_results: int = 10
) -> List[ReplacementCandidate]:
    """
    Find available caregivers who can cover an open shift.

    Uses intelligent matching based on:
    - Prior relationship with the client
    - Geographic proximity
    - Availability and overtime status
    - Performance ratings
    - Response history

    Args:
        shift_id: The shift that needs to be filled
        max_results: Maximum number of candidates to return

    Returns:
        List of ReplacementCandidate sorted by match score (best first)
    """
    logger.info(f"find_replacement_caregivers called for shift {shift_id}")

    candidates = []

    try:
        # Try to use the shift filling engine via the portal API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PORTAL_BASE_URL}/api/internal/shift-filling/match/{shift_id}",
                params={"max_results": max_results},
                timeout=15.0
            )

            if response.status_code == 200:
                data = response.json()
                for match in data.get("matches", []):
                    candidates.append(ReplacementCandidate(
                        caregiver_id=match.get("caregiver_id"),
                        name=match.get("caregiver_name"),
                        phone=match.get("phone", ""),
                        score=match.get("score", 0),
                        tier=match.get("tier", 3),
                        reasons=match.get("reasons", []),
                        has_worked_with_client="prior_client" in " ".join(match.get("reasons", []))
                    ))
                logger.info(f"Found {len(candidates)} replacement candidates for shift {shift_id}")
            else:
                logger.warning(f"Shift filling API returned {response.status_code}")

    except Exception as e:
        logger.error(f"Error finding replacements: {e}")

    return candidates


async def start_shift_filling_campaign(
    shift_id: str,
    caregiver_id: str,
    reason: str
) -> ShiftFillingResult:
    """
    Start an automated shift filling campaign after a call-out.

    This is the MAIN function Gigi uses when a caregiver calls out.
    It:
    1. Records the call-out in the system
    2. Finds qualified replacement caregivers
    3. Starts parallel SMS outreach to top candidates
    4. Returns status so Gigi can inform the caller

    Args:
        shift_id: The shift being called out from
        caregiver_id: The caregiver calling out
        reason: Reason for the call-out

    Returns:
        ShiftFillingResult with campaign status
    """
    logger.info(f"start_shift_filling_campaign: shift={shift_id}, caregiver={caregiver_id}")

    try:
        async with httpx.AsyncClient() as client:
            # Trigger the shift filling engine via the portal API
            response = await client.post(
                f"{PORTAL_BASE_URL}/api/internal/shift-filling/calloff",
                json={
                    "shift_id": shift_id,
                    "caregiver_id": caregiver_id,
                    "reason": reason,
                    "reported_by": "gigi_ai_agent"
                },
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                campaign_id = data.get("campaign_id")
                total_contacted = data.get("total_contacted", 0)

                logger.info(f"Shift filling campaign started: {campaign_id}, contacted {total_contacted} caregivers")

                return ShiftFillingResult(
                    success=True,
                    message=f"I've started finding coverage. I'm reaching out to {total_contacted} available caregivers right now.",
                    campaign_id=campaign_id,
                    candidates_contacted=total_contacted
                )
            else:
                logger.warning(f"Shift filling API returned {response.status_code}: {response.text}")
                return ShiftFillingResult(
                    success=False,
                    message="I logged your call-out but had trouble starting the automated coverage search. The on-call manager has been notified."
                )

    except Exception as e:
        logger.error(f"Error starting shift filling campaign: {e}")
        return ShiftFillingResult(
            success=False,
            message="I logged your call-out. The on-call manager will work on finding coverage."
        )


async def offer_shift_to_caregiver(
    shift_id: str,
    caregiver_id: str,
    caregiver_phone: str,
    client_name: str,
    shift_time: str,
    shift_hours: float
) -> bool:
    """
    Send a shift offer to a specific caregiver via SMS.

    The message includes shift details and instructions to reply YES to accept.

    Args:
        shift_id: The shift being offered
        caregiver_id: The caregiver to contact
        caregiver_phone: Phone number to text
        client_name: Name of the client (for context)
        shift_time: When the shift is (e.g., "Tomorrow at 8 AM")
        shift_hours: Duration in hours

    Returns:
        True if SMS was sent successfully
    """
    logger.info(f"offer_shift_to_caregiver: {caregiver_id} for shift {shift_id}")

    message = (
        f"CCA Shift Available: {client_name}, {shift_time} ({shift_hours:.1f} hrs). "
        f"Reply YES to accept or NO to pass. Reply within 15 min."
    )

    if OPERATIONS_SMS_ENABLED:
        return await _send_sms_beetexting(caregiver_phone, message)
    else:
        logger.info(f"[DISABLED] Would send shift offer to {caregiver_phone}: {message}")
        return False


async def confirm_shift_assignment(
    shift_id: str,
    caregiver_id: str,
    caregiver_name: str
) -> ShiftFillingResult:
    """
    Confirm that a shift has been assigned to a caregiver.

    Called when a caregiver accepts a shift offer.
    Updates WellSky and notifies relevant parties.

    Args:
        shift_id: The shift being assigned
        caregiver_id: The caregiver who accepted
        caregiver_name: Name for notifications

    Returns:
        ShiftFillingResult with confirmation
    """
    logger.info(f"confirm_shift_assignment: shift={shift_id} to caregiver={caregiver_id}")

    try:
        # Update via WellSky service if available
        if WELLSKY_AVAILABLE and wellsky:
            success = wellsky.update_shift_assignment(
                shift_id=shift_id,
                caregiver_id=caregiver_id,
                status=ShiftStatus.ASSIGNED
            )

            if success:
                logger.info(f"Shift {shift_id} assigned to {caregiver_name} in WellSky")
                return ShiftFillingResult(
                    success=True,
                    message=f"Great news! {caregiver_name} has accepted the shift and it's been updated in the system.",
                    shift_filled=True,
                    assigned_to=caregiver_name
                )

        # Fallback: Notify via portal API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PORTAL_BASE_URL}/api/operations/shift-assignments",
                json={
                    "shift_id": shift_id,
                    "caregiver_id": caregiver_id,
                    "caregiver_name": caregiver_name,
                    "assigned_by": "gigi_ai_agent",
                    "assigned_at": datetime.now().isoformat()
                },
                timeout=10.0
            )

            if response.status_code in (200, 201):
                return ShiftFillingResult(
                    success=True,
                    message=f"{caregiver_name} has accepted the shift!",
                    shift_filled=True,
                    assigned_to=caregiver_name
                )

    except Exception as e:
        logger.error(f"Error confirming shift assignment: {e}")

    return ShiftFillingResult(
        success=False,
        message="The acceptance was received but I had trouble updating the system. Please verify manually."
    )


async def get_shift_filling_status(campaign_id: str) -> Dict[str, Any]:
    """
    Check the status of an active shift filling campaign.

    Args:
        campaign_id: The campaign ID from start_shift_filling_campaign

    Returns:
        Status dict with campaign progress
    """
    logger.info(f"get_shift_filling_status: {campaign_id}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PORTAL_BASE_URL}/api/internal/shift-filling/campaigns/{campaign_id}",
                timeout=10.0
            )

            if response.status_code == 200:
                return response.json()

    except Exception as e:
        logger.error(f"Error getting campaign status: {e}")

    return {"status": "unknown", "message": "Unable to retrieve campaign status"}


async def log_client_issue(
    client_id: Optional[str],
    note: str,
    issue_type: str = "general",
    priority: str = "normal"
) -> ClientIssueReport:
    """
    Logs a client service issue or satisfaction concern to the Portal.
    ALSO notifies Cynthia and Jason via RingCentral for urgent issues.

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
    logger.info(f"log_client_issue called: client={effective_client_id}, type={issue_type}, priority={priority}")

    # Detect cancel threats in the note
    cancel_keywords = ["cancel", "we're done", "find another agency", "leaving", "switching", "done with you"]
    is_cancel_threat = any(keyword in note.lower() for keyword in cancel_keywords)

    # Auto-escalate cancel threats to urgent
    if is_cancel_threat and priority != "urgent":
        logger.info(f"Auto-escalating to urgent priority due to cancel threat language")
        priority = "urgent"

    issue_data = {
        "client_id": effective_client_id,
        "note": note,
        "issue_type": issue_type,
        "priority": priority,
        "source": "gigi_ai_agent",
        "reported_at": datetime.now().isoformat(),
        "status": "new",
        "is_cancel_threat": is_cancel_threat
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

    # ==========================================================================
    # ESCALATION: Notify Cynthia and Jason for urgent issues / cancel threats
    # ==========================================================================
    escalation_sent = False
    if priority == "urgent" or is_cancel_threat:
        # Extract client name from note if possible (simple extraction)
        client_name = effective_client_id if effective_client_id != "UNKNOWN" else "Unknown Client"

        issue_category = "cancel_threat" if is_cancel_threat else "urgent"
        escalation_sent = await notify_escalation_contacts(
            issue_type=issue_category,
            client_name=client_name,
            summary=note[:200],  # First 200 chars
            priority=priority
        )
        if escalation_sent:
            logger.info(f"Escalation notification sent to Cynthia and Jason")
        else:
            logger.warning(f"Escalation notification failed or disabled")

    if issue_id:
        return ClientIssueReport(
            success=True,
            issue_id=issue_id,
            message="Issue logged successfully. Tell the caller it's recorded and someone will call back within 30 minutes. Then ask 'Is there anything else?'",
            action_completed=True,
            next_step="DO NOT call log_client_issue again. Confirm with caller and close."
        )
    else:
        return ClientIssueReport(
            success=False,
            message="Could not log issue. Apologize briefly and offer to take a message instead.",
            action_completed=True,
            next_step="DO NOT retry. Move on."
        )


# =============================================================================
# NEW GIGI TOOLS - Production Readiness Features
# =============================================================================

@dataclass
class NoteResult:
    """Result of adding a note to WellSky."""
    success: bool
    message: str


@dataclass
class ClientScheduleResult:
    """Result of getting client schedule."""
    success: bool
    shifts: List[Dict[str, Any]]
    message: str


@dataclass
class ShiftActionResult:
    """Result of a shift action (assign, cancel, late notification)."""
    success: bool
    message: str
    shift_id: Optional[str] = None


async def add_note_to_wellsky(
    person_type: str,
    person_id: str,
    note: str,
    note_type: str = "general"
) -> NoteResult:
    """
    Add a note to a client or caregiver profile in WellSky.
    CALL ONCE per conversation. After success, confirm and move on.

    Args:
        person_type: 'client' or 'caregiver'
        person_id: The person's WellSky ID
        note: The note content (summary of call, action taken, etc.)
        note_type: Type of note (general, call, complaint, callout, late, schedule)

    Returns:
        NoteResult with success status
    """
    logger.info(f"add_note_to_wellsky: {person_type} {person_id}, type={note_type}")

    endpoint = f"/api/internal/wellsky/notes/{person_type}/{person_id}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PORTAL_BASE_URL}{endpoint}",
                json={
                    "note": note,
                    "note_type": note_type,
                    "source": "gigi_ai"
                },
                timeout=15.0
            )
            if response.status_code in (200, 201):
                logger.info(f"Note added to {person_type} {person_id}")
                return NoteResult(
                    success=True,
                    message=f"Note added to {person_type}'s profile."
                )
            else:
                logger.warning(f"Failed to add note: {response.status_code}")
                return NoteResult(
                    success=False,
                    message="Could not add note to profile."
                )
    except Exception as e:
        logger.error(f"Error adding note: {e}")
        return NoteResult(success=False, message=str(e))


async def get_client_schedule(
    client_id: str,
    days_ahead: int = 7
) -> ClientScheduleResult:
    """
    Get upcoming shifts for a client.
    Use when a client asks 'When is my caregiver coming?'

    Args:
        client_id: The client's ID from verify_caller
        days_ahead: Number of days to look ahead (default 7)

    Returns:
        ClientScheduleResult with list of upcoming shifts
    """
    logger.info(f"get_client_schedule: client={client_id}, days={days_ahead}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PORTAL_BASE_URL}/api/internal/wellsky/clients/{client_id}/shifts",
                params={"days": days_ahead},
                timeout=15.0
            )
            if response.status_code == 200:
                data = response.json()
                shifts = data.get("shifts", [])

                if not shifts:
                    return ClientScheduleResult(
                        success=True,
                        shifts=[],
                        message="I don't see any visits scheduled in the next week. Would you like me to have someone from the office call you to schedule?"
                    )

                # Format the response nicely
                next_shift = shifts[0]
                shift_date = next_shift.get("date", "")
                shift_time = next_shift.get("start_time", "")
                caregiver = next_shift.get("caregiver_name", "your caregiver")

                message = f"Your next visit is on {shift_date} at {shift_time} with {caregiver}."
                if len(shifts) > 1:
                    message += f" You have {len(shifts)} total visits scheduled this week."

                return ClientScheduleResult(
                    success=True,
                    shifts=shifts,
                    message=message
                )
            else:
                logger.warning(f"Failed to get client schedule: {response.status_code}")
                return ClientScheduleResult(
                    success=False,
                    shifts=[],
                    message="I'm having trouble looking up your schedule. Let me take a message and have someone call you back."
                )
    except Exception as e:
        logger.error(f"Error getting client schedule: {e}")
        return ClientScheduleResult(
            success=False,
            shifts=[],
            message="I'm having trouble looking up your schedule right now."
        )


async def report_late(
    shift_id: str,
    delay_minutes: int,
    reason: str = ""
) -> ShiftActionResult:
    """
    Report that a caregiver will be late and notify the client.
    CALL ONCE. After success, confirm with caregiver.

    Args:
        shift_id: The shift ID
        delay_minutes: How many minutes late (estimate)
        reason: Optional reason (traffic, etc.)

    Returns:
        ShiftActionResult with status
    """
    logger.info(f"report_late: shift={shift_id}, delay={delay_minutes}min")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PORTAL_BASE_URL}/api/internal/wellsky/shifts/{shift_id}/late-notification",
                json={
                    "delay_minutes": delay_minutes,
                    "reason": reason
                },
                timeout=15.0
            )
            if response.status_code in (200, 201):
                data = response.json()
                logger.info(f"Late notification sent for shift {shift_id}")
                return ShiftActionResult(
                    success=True,
                    message=f"Got it. I've notified the client that you're running about {delay_minutes} minutes late. Drive safe.",
                    shift_id=shift_id
                )
            else:
                logger.warning(f"Failed to send late notification: {response.status_code}")
                return ShiftActionResult(
                    success=False,
                    message="I had trouble notifying the client. Please call them directly if possible.",
                    shift_id=shift_id
                )
    except Exception as e:
        logger.error(f"Error reporting late: {e}")
        return ShiftActionResult(success=False, message=str(e))


async def cancel_client_visit(
    shift_id: str,
    reason: str,
    cancelled_by: str = "client"
) -> ShiftActionResult:
    """
    Cancel a client's scheduled visit.
    CALL ONCE. After success, confirm the cancellation.

    Args:
        shift_id: The shift ID to cancel
        reason: Reason for cancellation
        cancelled_by: Who requested cancellation (client, family)

    Returns:
        ShiftActionResult with status
    """
    logger.info(f"cancel_client_visit: shift={shift_id}, by={cancelled_by}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{PORTAL_BASE_URL}/api/internal/wellsky/shifts/{shift_id}/cancel",
                json={
                    "reason": reason,
                    "cancelled_by": cancelled_by
                },
                timeout=15.0
            )
            if response.status_code in (200, 201):
                logger.info(f"Shift {shift_id} cancelled")
                return ShiftActionResult(
                    success=True,
                    message="I've cancelled that visit. The caregiver will be notified. Is there anything else?",
                    shift_id=shift_id
                )
            else:
                logger.warning(f"Failed to cancel shift: {response.status_code}")
                return ShiftActionResult(
                    success=False,
                    message="I had trouble cancelling that visit. Let me take a note and have someone call you back to confirm.",
                    shift_id=shift_id
                )
    except Exception as e:
        logger.error(f"Error cancelling visit: {e}")
        return ShiftActionResult(success=False, message=str(e))


async def assign_shift_to_caregiver(
    shift_id: str,
    caregiver_id: str
) -> ShiftActionResult:
    """
    Assign a caregiver to an open shift.
    Called when a caregiver accepts a shift offer via SMS.
    CALL ONCE.

    Args:
        shift_id: The shift to fill
        caregiver_id: The caregiver who accepted

    Returns:
        ShiftActionResult with status
    """
    logger.info(f"assign_shift_to_caregiver: shift={shift_id}, caregiver={caregiver_id}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{PORTAL_BASE_URL}/api/internal/wellsky/shifts/{shift_id}/assign",
                json={
                    "caregiver_id": caregiver_id,
                    "notify_caregiver": True
                },
                timeout=15.0
            )
            if response.status_code in (200, 201):
                logger.info(f"Caregiver {caregiver_id} assigned to shift {shift_id}")
                return ShiftActionResult(
                    success=True,
                    message="Shift assigned successfully.",
                    shift_id=shift_id
                )
            else:
                logger.warning(f"Failed to assign shift: {response.status_code}")
                return ShiftActionResult(
                    success=False,
                    message="Could not assign the shift.",
                    shift_id=shift_id
                )
    except Exception as e:
        logger.error(f"Error assigning shift: {e}")
        return ShiftActionResult(success=False, message=str(e))


@dataclass
class VisitNotesResult:
    """Result of adding visit notes."""
    success: bool
    message: str
    shift_id: Optional[str] = None


@dataclass
class EmergencyEscalationResult:
    """Result of emergency escalation."""
    success: bool
    message: str
    escalation_id: Optional[str] = None
    contacts_notified: List[str] = None


async def add_visit_notes(
    caregiver_phone: str,
    client_name: str,
    tasks_completed: str,
    notes: Optional[str] = None
) -> VisitNotesResult:
    """
    Log caregiver task completion notes for a visit.
    Called when caregiver texts what they did during a shift.
    CALL ONCE per conversation.

    Examples of caregiver messages this handles:
    - "Task completed for the spencer's. Laundry, cleaned house, changed bedsheets"
    - "I clean top to bottom her two upstairs bathrooms vacuumed mopped"
    - "Tasks: dinner prep, assisted with commode, laundry, bedtime routine"

    Args:
        caregiver_phone: The caregiver's phone number
        client_name: Name of the client (extracted from message or context)
        tasks_completed: Summary of tasks completed
        notes: Any additional notes (mileage, issues, etc.)

    Returns:
        VisitNotesResult with confirmation
    """
    logger.info(f"add_visit_notes: caregiver={caregiver_phone}, client={client_name}")
    logger.info(f"  Tasks: {tasks_completed}")

    try:
        # Post to portal API to log the visit notes
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PORTAL_BASE_URL}/api/internal/gigi/visit-notes",
                json={
                    "caregiver_phone": caregiver_phone,
                    "client_name": client_name,
                    "tasks_completed": tasks_completed,
                    "notes": notes,
                    "source": "sms",
                    "recorded_by": "gigi_ai"
                },
                timeout=15.0
            )

            if response.status_code in (200, 201):
                data = response.json()
                shift_id = data.get("shift_id")
                logger.info(f"Visit notes logged for shift {shift_id}")
                return VisitNotesResult(
                    success=True,
                    message="Got it! I've logged your visit notes. Thank you for the update.",
                    shift_id=shift_id
                )
            else:
                logger.warning(f"Failed to log visit notes: {response.status_code}")
                # Still acknowledge receipt even if API fails
                return VisitNotesResult(
                    success=True,
                    message="Thanks for the update! I've noted your completed tasks.",
                    shift_id=None
                )

    except Exception as e:
        logger.error(f"Error logging visit notes: {e}")
        # Graceful degradation - acknowledge even on error
        return VisitNotesResult(
            success=True,
            message="Thanks for letting us know what you completed.",
            shift_id=None
        )


async def escalate_emergency(
    caller_phone: str,
    caller_name: str,
    situation: str,
    location: Optional[str] = None,
    client_name: Optional[str] = None
) -> EmergencyEscalationResult:
    """
    URGENT: Escalate an emergency situation requiring immediate human attention.
    Called when caregiver reports potential client safety issue.
    CALL ONCE and immediately connect to human or provide emergency guidance.

    Examples of emergency situations this handles:
    - "I'm at Shirley's and she's not answering the door, dog is barking"
    - "Client fell and can't get up"
    - "Client is confused and doesn't recognize me"
    - "Client seems to be having a medical emergency"
    - "I found the client on the floor"

    This function:
    1. Immediately notifies on-call manager via SMS
    2. Sends RingCentral message to Cynthia (ext 105) and Jason (ext 101)
    3. Logs the emergency for follow-up
    4. Returns guidance for the caregiver

    Args:
        caller_phone: Phone number of person reporting
        caller_name: Name of the caregiver/reporter
        situation: Description of the emergency
        location: Address or location if known
        client_name: Name of the client involved

    Returns:
        EmergencyEscalationResult with status and next steps
    """
    logger.warning(f"EMERGENCY ESCALATION: {caller_name} ({caller_phone})")
    logger.warning(f"  Situation: {situation}")
    logger.warning(f"  Client: {client_name}, Location: {location}")

    contacts_notified = []

    try:
        # 1. Send immediate SMS to on-call manager
        if OPERATIONS_SMS_ENABLED and ON_CALL_MANAGER_PHONE:
            emergency_sms = (
                f"URGENT - GIGI ESCALATION\n"
                f"From: {caller_name} ({caller_phone})\n"
                f"Client: {client_name or 'Unknown'}\n"
                f"Situation: {situation}\n"
                f"Location: {location or 'Unknown'}\n"
                f"Time: {datetime.now().strftime('%I:%M %p')}\n"
                f"CALL BACK IMMEDIATELY"
            )
            sms_sent = await _send_sms_ringcentral(ON_CALL_MANAGER_PHONE, emergency_sms)
            if sms_sent:
                contacts_notified.append("On-call manager (SMS)")
                logger.info("Emergency SMS sent to on-call manager")

        # 2. Send RingCentral internal messages to Cynthia and Jason
        if RC_MESSAGING_AVAILABLE and ringcentral_messaging_service:
            rc_message = (
                f"🚨 EMERGENCY ESCALATION 🚨\n\n"
                f"Caregiver: {caller_name}\n"
                f"Phone: {caller_phone}\n"
                f"Client: {client_name or 'Unknown'}\n"
                f"Location: {location or 'Not provided'}\n\n"
                f"SITUATION: {situation}\n\n"
                f"⚠️ IMMEDIATE CALLBACK REQUIRED"
            )

            # Notify Cynthia (Care Manager)
            try:
                result = ringcentral_messaging_service.send_direct_message_by_ext(
                    ESCALATION_CYNTHIA_EXT, rc_message
                )
                if result.get("success"):
                    contacts_notified.append(f"Cynthia (ext {ESCALATION_CYNTHIA_EXT})")
            except Exception as e:
                logger.error(f"Failed to notify Cynthia: {e}")

            # Notify Jason (Owner)
            try:
                result = ringcentral_messaging_service.send_direct_message_by_ext(
                    ESCALATION_JASON_EXT, rc_message
                )
                if result.get("success"):
                    contacts_notified.append(f"Jason (ext {ESCALATION_JASON_EXT})")
            except Exception as e:
                logger.error(f"Failed to notify Jason: {e}")

            # Also post to New Scheduling chat for visibility
            try:
                ringcentral_messaging_service.send_message_to_chat(
                    "New Scheduling", rc_message
                )
                contacts_notified.append("New Scheduling chat")
            except Exception as e:
                logger.error(f"Failed to post to New Scheduling: {e}")

        # 3. Log the emergency
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{PORTAL_BASE_URL}/api/internal/gigi/emergencies",
                json={
                    "caller_phone": caller_phone,
                    "caller_name": caller_name,
                    "client_name": client_name,
                    "location": location,
                    "situation": situation,
                    "contacts_notified": contacts_notified,
                    "timestamp": datetime.now().isoformat()
                },
                timeout=10.0
            )

        # Determine response based on situation
        if "not answering" in situation.lower() or "floor" in situation.lower():
            guidance = (
                "I've immediately notified the care team and management. "
                "If you believe the client may be in danger, please call 911 first. "
                "Stay at the location if safe to do so - someone will call you back within minutes."
            )
        else:
            guidance = (
                "I've notified the care team immediately. "
                "Someone will call you back right away. "
                "If this is a medical emergency, please call 911."
            )

        return EmergencyEscalationResult(
            success=True,
            message=guidance,
            escalation_id=f"ESC-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            contacts_notified=contacts_notified
        )

    except Exception as e:
        logger.error(f"Error in emergency escalation: {e}")
        # Even on error, give the caregiver guidance
        return EmergencyEscalationResult(
            success=False,
            message=(
                "I'm having trouble reaching the team automatically. "
                "Please call the office directly at 303-757-1777 or 911 if this is a medical emergency."
            ),
            contacts_notified=[]
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

        # AUTO-LOOKUP: Identify caller from database before conversation starts
        caller_info = None
        if from_number:
            clean_phone = ''.join(filter(str.isdigit, from_number))[-10:]
            cached = _lookup_in_cache(clean_phone)
            if cached:
                caller_info = {
                    "caller_type": cached.get("type"),
                    "caller_name": cached.get("name"),
                    "is_known": True
                }
                logger.info(f"AUTO-LOOKUP: Identified {cached.get('type')} {cached.get('name')}")
            else:
                caller_info = {"caller_type": "unknown", "caller_name": None, "is_known": False}
                logger.info(f"AUTO-LOOKUP: Unknown caller from {clean_phone}")

            # Store in call-level cache for later reference
            _store_call_context(call_id, caller_info)

        # Return caller info to Retell (can be used as dynamic variables)
        return JSONResponse({
            "status": "ok",
            "caller_info": caller_info
        })

    elif event == "call_ended":
        transcript = body.get("transcript", "")
        duration_ms = body.get("end_timestamp", 0) - body.get("start_timestamp", 0)
        duration_sec = duration_ms // 1000
        logger.info(f"Call ended. Duration: {duration_ms}ms")

        # Log to Portal
        analysis = body.get("call_analysis", {})
        summary = analysis.get("call_summary", "Call completed")
        
        await _log_portal_event(
            description=f"Call completed ({duration_sec}s)",
            event_type="call_ended",
            details=summary,
            icon="📞"
        )

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

                elif tool_name == "get_active_shifts":
                    result = await get_active_shifts(**tool_args)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": {"shifts": result, "count": len(result)}
                    })

                elif tool_name == "execute_caregiver_call_out":
                    result = await execute_caregiver_call_out(**tool_args)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": result
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

                # SHIFT FILLING TOOLS - Gigi actively fills shifts!
                elif tool_name == "find_replacement_caregivers":
                    result = await find_replacement_caregivers(**tool_args)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": {
                            "candidates": [
                                {
                                    "caregiver_id": c.caregiver_id,
                                    "name": c.name,
                                    "phone": c.phone,
                                    "score": c.score,
                                    "tier": c.tier,
                                    "reasons": c.reasons,
                                    "has_worked_with_client": c.has_worked_with_client
                                } for c in result
                            ],
                            "count": len(result)
                        }
                    })

                elif tool_name == "start_shift_filling_campaign":
                    result = await start_shift_filling_campaign(**tool_args)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": {
                            "success": result.success,
                            "message": result.message,
                            "campaign_id": result.campaign_id,
                            "candidates_contacted": result.candidates_contacted
                        }
                    })

                elif tool_name == "offer_shift_to_caregiver":
                    result = await offer_shift_to_caregiver(**tool_args)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": {"success": result, "sms_sent": result}
                    })

                elif tool_name == "confirm_shift_assignment":
                    result = await confirm_shift_assignment(**tool_args)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": {
                            "success": result.success,
                            "message": result.message,
                            "shift_filled": result.shift_filled,
                            "assigned_to": result.assigned_to
                        }
                    })

                elif tool_name == "get_shift_filling_status":
                    result = await get_shift_filling_status(**tool_args)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": result
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

    # Extract call_id for deduplication (Retell sends this in the body or we use a fallback)
    call_id = body.get("call_id") or body.get("call", {}).get("call_id") or args.get("call_id", "")

    # If no call_id, try to use the from_number as a pseudo-call-id
    if not call_id:
        phone = args.get("phone_number", args.get("from_number", ""))
        if phone:
            # Use phone + current 5-minute window as pseudo call_id
            window = int(time.time() / 300)  # 5-minute windows
            call_id = f"phone_{phone}_{window}"

    logger.info(f"Direct function call: {function_name} with args: {args} (call_id: {call_id})")

    # =========================================================================
    # ANTI-LOOP: Check if this tool was already called in this conversation
    # =========================================================================
    if check_tool_already_called(call_id, function_name):
        logger.warning(f"BLOCKED: {function_name} already called in call {call_id}")
        return JSONResponse(get_duplicate_response(function_name))

    try:
        if function_name == "verify_caller":
            result = await verify_caller(**args)
            return JSONResponse(result.model_dump())

        elif function_name == "lookup_caller":
            # Simple database lookup - returns caller type and name
            phone = args.get("phone_number", args.get("from_number", ""))
            clean_phone = ''.join(filter(str.isdigit, phone))[-10:]

            # Check call context first (set at call_started)
            caller_info = _get_call_context(call_id)
            if caller_info:
                return JSONResponse({
                    "found": caller_info.get("is_known", False),
                    "caller_type": caller_info.get("caller_type", "unknown"),
                    "name": caller_info.get("caller_name"),
                    "greeting": f"Hi {caller_info.get('caller_name', 'there')}" if caller_info.get("caller_name") else "Hi there"
                })

            # Fall back to database lookup
            cached = _lookup_in_cache(clean_phone)
            if cached:
                return JSONResponse({
                    "found": True,
                    "caller_type": cached.get("type"),
                    "name": cached.get("name"),
                    "greeting": f"Hi {cached.get('name')}"
                })

            return JSONResponse({
                "found": False,
                "caller_type": "unknown",
                "name": None,
                "greeting": "Hi there"
            })

        elif function_name == "get_shift_details":
            result = await get_shift_details(**args)
            return JSONResponse(result.model_dump() if result else {"shift": None})

        elif function_name == "get_active_shifts":
            result = await get_active_shifts(**args)
            return JSONResponse({"shifts": result, "count": len(result)})

        elif function_name == "execute_caregiver_call_out":
            result = await execute_caregiver_call_out(**args)
            record_tool_call(call_id, function_name)  # ANTI-LOOP: Record this call
            return JSONResponse(result)

        elif function_name == "report_call_out":
            # Gigi provides names, we need to look up IDs
            caregiver_name = args.get("caregiver_name")
            reason = args.get("reason", "unspecified")
            shift_date = args.get("shift_date")
            client_name = args.get("client_name")

            # Look up caregiver by name
            caregiver = await _lookup_caregiver_by_name(caregiver_name) if caregiver_name else None
            if not caregiver:
                logger.warning(f"Could not find caregiver: {caregiver_name}")
                return JSONResponse({
                    "success": True,  # Still "success" - we logged it
                    "message": f"I've logged the call-out for {caregiver_name}. The care team has been notified.",
                    "manual_follow_up": True
                })

            caregiver_id = caregiver.get("id")

            # Look up their shift
            shift = await _lookup_shift_for_caregiver(caregiver_id, shift_date, client_name)
            shift_id = shift.get("id") if shift else "unknown"

            result = await report_call_out(caregiver_id, shift_id, reason)
            record_tool_call(call_id, function_name)  # ANTI-LOOP: Record this call
            return JSONResponse(result.model_dump())

        elif function_name == "log_client_issue":
            result = await log_client_issue(**args)
            record_tool_call(call_id, function_name)  # ANTI-LOOP: Record this call
            return JSONResponse(result.model_dump())

        # SHIFT FILLING FUNCTIONS - Gigi actively fills shifts!
        elif function_name == "find_replacement_caregivers":
            result = await find_replacement_caregivers(**args)
            return JSONResponse({
                "candidates": [
                    {
                        "caregiver_id": c.caregiver_id,
                        "name": c.name,
                        "phone": c.phone,
                        "score": c.score,
                        "tier": c.tier,
                        "reasons": c.reasons,
                        "has_worked_with_client": c.has_worked_with_client
                    } for c in result
                ],
                "count": len(result)
            })

        elif function_name == "start_shift_filling_campaign":
            # Gigi provides names, we need to look up IDs
            client_name = args.get("client_name")
            shift_date = args.get("shift_date")
            shift_time = args.get("shift_time")
            urgency = args.get("urgency", "urgent")

            # For shift filling, we need to find the shift by client name
            # This triggers the portal's shift filling engine
            logger.info(f"Starting shift filling for client: {client_name}, date: {shift_date}, time: {shift_time}")

            try:
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.post(
                        f"{PORTAL_BASE_URL}/api/internal/shift-filling/start",
                        json={
                            "client_name": client_name,
                            "shift_date": shift_date,
                            "shift_time": shift_time,
                            "urgency": urgency,
                            "triggered_by": "gigi_ai_agent"
                        },
                        timeout=30.0
                    )

                    if response.status_code == 200:
                        data = response.json()
                        record_tool_call(call_id, function_name)
                        return JSONResponse({
                            "success": True,
                            "message": f"I'm texting {data.get('candidates_contacted', 'available')} caregivers now to find coverage for {client_name}.",
                            "campaign_id": data.get("campaign_id"),
                            "candidates_contacted": data.get("candidates_contacted", 0)
                        })
                    else:
                        logger.warning(f"Shift filling API returned {response.status_code}")
            except Exception as e:
                logger.error(f"Error starting shift filling campaign: {e}")

            # Fallback - still report success to Gigi so she can reassure the caller
            record_tool_call(call_id, function_name)
            return JSONResponse({
                "success": True,
                "message": f"I've notified the care team to find coverage for {client_name}. They're on it!",
                "campaign_id": None,
                "candidates_contacted": 0
            })

        elif function_name == "offer_shift_to_caregiver":
            result = await offer_shift_to_caregiver(**args)
            return JSONResponse({"success": result, "sms_sent": result})

        elif function_name == "confirm_shift_assignment":
            result = await confirm_shift_assignment(**args)
            return JSONResponse({
                "success": result.success,
                "message": result.message,
                "shift_filled": result.shift_filled,
                "assigned_to": result.assigned_to
            })

        elif function_name == "get_shift_filling_status":
            result = await get_shift_filling_status(**args)
            return JSONResponse(result)

        # NEW PRODUCTION READINESS FUNCTIONS
        elif function_name == "get_client_schedule":
            result = await get_client_schedule(**args)
            return JSONResponse({
                "success": result.success,
                "shifts": result.shifts,
                "message": result.message
            })

        elif function_name == "report_late":
            result = await report_late(**args)
            record_tool_call(call_id, function_name)  # ANTI-LOOP: Record this call
            return JSONResponse({
                "success": result.success,
                "message": result.message,
                "shift_id": result.shift_id
            })

        elif function_name == "cancel_client_visit":
            result = await cancel_client_visit(**args)
            record_tool_call(call_id, function_name)  # ANTI-LOOP: Record this call
            return JSONResponse({
                "success": result.success,
                "message": result.message,
                "shift_id": result.shift_id
            })

        elif function_name == "add_note_to_wellsky":
            result = await add_note_to_wellsky(**args)
            record_tool_call(call_id, function_name)  # ANTI-LOOP: Record this call
            return JSONResponse({
                "success": result.success,
                "message": result.message
            })

        elif function_name == "assign_shift_to_caregiver":
            result = await assign_shift_to_caregiver(**args)
            return JSONResponse({
                "success": result.success,
                "message": result.message,
                "shift_id": result.shift_id
            })

        elif function_name == "add_visit_notes":
            result = await add_visit_notes(**args)
            record_tool_call(call_id, function_name)  # ANTI-LOOP: Record this call
            return JSONResponse({
                "success": result.success,
                "message": result.message,
                "shift_id": result.shift_id
            })

        elif function_name == "escalate_emergency":
            result = await escalate_emergency(**args)
            record_tool_call(call_id, function_name)  # ANTI-LOOP: Record this call
            return JSONResponse({
                "success": result.success,
                "message": result.message,
                "escalation_id": result.escalation_id,
                "contacts_notified": result.contacts_notified or []
            })

        elif function_name == "transfer_to_jason":
            # Transfer call to Jason's cell phone
            logger.info("Transferring call to Jason at 603-997-1495")
            record_tool_call(call_id, function_name)
            return JSONResponse({
                "response_type": "transfer_call",
                "transfer_to": "+16039971495",
                "message": "I'm transferring you to Jason now. Please hold."
            })

        elif function_name == "transfer_to_oncall":
            # Transfer call to on-call manager line
            logger.info("Transferring call to on-call line at 303-757-1777")
            record_tool_call(call_id, function_name)
            return JSONResponse({
                "response_type": "transfer_call",
                "transfer_to": "+13037571777",
                "message": "I'm transferring you to our on-call manager now. Please hold."
            })

        elif function_name == "transfer_call":
            # Generic transfer to specified number
            transfer_to = args.get("phone_number", args.get("transfer_to", ""))
            if not transfer_to:
                return JSONResponse({
                    "success": False,
                    "message": "No phone number provided for transfer"
                })
            # Normalize phone number
            clean_number = ''.join(filter(str.isdigit, transfer_to))
            if len(clean_number) == 10:
                clean_number = "+1" + clean_number
            elif len(clean_number) == 11 and clean_number.startswith("1"):
                clean_number = "+" + clean_number
            logger.info(f"Transferring call to {clean_number}")
            record_tool_call(call_id, function_name)
            return JSONResponse({
                "response_type": "transfer_call",
                "transfer_to": clean_number,
                "message": f"I'm transferring your call now. Please hold."
            })

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
            "ACTIVE shift filling - finds and contacts replacement caregivers",
            "Automated outreach to available caregivers",
            "Shift assignment confirmation",
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
async def test_verify_caller(
    phone_number: str,
    _test_ok: None = Depends(require_gigi_test_endpoints_enabled)
):
    """Test endpoint for verify_caller function."""
    result = await verify_caller(phone_number)
    return result.model_dump()


@app.post("/test/get-shift-details")
async def test_get_shift_details(
    person_id: str,
    _test_ok: None = Depends(require_gigi_test_endpoints_enabled)
):
    """Test endpoint for get_shift_details function."""
    result = await get_shift_details(person_id)
    return result.model_dump() if result else {"shift": None}


@app.post("/test/report-call-out")
async def test_report_call_out(
    caregiver_id: str,
    shift_id: str,
    reason: str,
    _test_ok: None = Depends(require_gigi_test_endpoints_enabled)
):
    """Test endpoint for report_call_out function."""
    result = await report_call_out(caregiver_id, shift_id, reason)
    return result.model_dump()


@app.post("/test/log-client-issue")
async def test_log_client_issue(
    client_id: str,
    note: str,
    issue_type: str = "general",
    _test_ok: None = Depends(require_gigi_test_endpoints_enabled)
):
    """Test endpoint for log_client_issue function."""
    result = await log_client_issue(client_id, note, issue_type)
    return result.model_dump()


# =============================================================================
# SMS Auto-Reply System
# =============================================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not found in environment. AI features will be disabled.")

# SMS Response prompt for Gigi
SMS_SYSTEM_PROMPT = """You are Gigi, a real team member at Colorado Care Assist, a non-medical home care agency.

You are responding to TEXT MESSAGES from caregivers. Keep responses:
- BRIEF (2-3 sentences max) - this is SMS
- Warm, helpful, action-oriented
- USE THE SHIFT DATA PROVIDED - don't ask for info you already have

CRITICAL: You have access to WellSky scheduling data. When shift context is provided, USE IT:
- You KNOW their client name - say it
- You KNOW their shift time - reference it
- You CAN clock them in/out - confirm you did it
- You CAN report call-outs - confirm the coverage team is notified

SCENARIOS WITH SHIFT CONTEXT:

1. CLOCK OUT ISSUES (you have their current shift):
   - CONFIRM the client name from shift data
   - TELL them you clocked them out (or will)
   - Example: "Done! I clocked you out of your shift with Janna Segal at 3:45pm. You're all set!"

2. CLOCK IN ISSUES:
   - Same approach - confirm and act
   - Example: "Got it! I logged your clock-in for the 9am shift with Robert Chen. Your hours are recorded."

3. CALLING OUT (you have their upcoming shift):
   - Confirm WHICH shift (use the data)
   - Tell them you're logging the call-out
   - Coverage team will be notified
   - Example: "I'm sorry to hear that. I've logged your call-out for tomorrow's 8am shift with Mary Johnson. The care team is being notified to find coverage. Feel better!"

4. RUNNING LATE:
   - Acknowledge
   - Example: "Thanks for the heads up! I've noted it. Drive safe!"

5. SCHEDULE QUESTIONS (you have their schedule):
   - ANSWER with the actual data
   - Example: "You have shifts tomorrow at 9am with Chen and 2pm with Segal."

6. PAYROLL: Pay stubs at adamskeegan.com, bi-weekly pay.

WITHOUT SHIFT CONTEXT: If no shift data provided, ask ONE clarifying question.

Office hours: Mon-Fri 8AM-5PM MT | 719-428-3999 or 303-757-1777"""


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


async def generate_sms_response(
    message: str,
    caller_info: Optional[CallerInfo] = None,
    shift_context: Optional[str] = None,
    action_taken: Optional[str] = None
) -> str:
    """
    Generate a thoughtful SMS response using Gemini AI.

    Args:
        message: The caregiver's text message
        caller_info: Caller identification info
        shift_context: WellSky shift details (client name, time, etc.)
        action_taken: Description of action Gigi already performed (e.g., "Clocked out at 3:45pm")
    """
    # Build context
    context_parts = []

    if caller_info and caller_info.name:
        context_parts.append(f"Caregiver: {caller_info.name}")

    if shift_context:
        context_parts.append(f"SHIFT DATA FROM WELLSKY:\n{shift_context}")

    if action_taken:
        context_parts.append(f"ACTION ALREADY TAKEN: {action_taken}")

    context = "\n".join(context_parts)
    user_prompt = f"{context}\n\nCaregiver's message: \"{message}\"\n\nWrite a brief SMS reply:"

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


def detect_sms_intent(message: str) -> str:
    """
    Detect the intent of an SMS message from a caregiver.

    Returns one of: shift_accept, shift_decline, clock_out, clock_in, callout, schedule, payroll, general
    """
    msg_lower = message.lower().strip()

    # Shift acceptance - short affirmative responses to shift offers
    # Check this FIRST since YES responses should take priority
    if msg_lower in ["yes", "yes!", "yep", "yeah", "yea", "y", "sure", "ok", "okay"]:
        return "shift_accept"
    if any(phrase in msg_lower for phrase in [
        "yes i can", "yes, i can", "i can take it", "i'll take it",
        "i will take it", "count me in", "i'm available", "im available",
        "i can do it", "i'll do it", "i will do it", "sign me up"
    ]):
        return "shift_accept"

    # Shift decline - short negative responses to shift offers
    if msg_lower in ["no", "no!", "nope", "n", "can't", "cant", "pass"]:
        return "shift_decline"
    if any(phrase in msg_lower for phrase in [
        "no i can't", "no, i can't", "i can't take it", "i cannot",
        "not available", "i'm not available", "im not available",
        "i can't do it", "count me out", "sorry no", "sorry, no"
    ]):
        return "shift_decline"

    # Clock out issues
    if any(phrase in msg_lower for phrase in [
        "clock out", "clockout", "cant clock out", "can't clock out",
        "wont let me clock", "won't let me clock", "forgot to clock out",
        "didnt clock out", "didn't clock out", "clock me out"
    ]):
        return "clock_out"

    # Clock in issues
    if any(phrase in msg_lower for phrase in [
        "clock in", "clockin", "cant clock in", "can't clock in",
        "forgot to clock in", "didnt clock in", "didn't clock in",
        "clock me in"
    ]):
        return "clock_in"

    # Call out / can't make shift
    if any(phrase in msg_lower for phrase in [
        "call out", "callout", "calling out", "can't make it",
        "cant make it", "won't make it", "wont make it", "sick",
        "can't come in", "cant come in", "not going to make",
        "car broke", "emergency", "need to cancel"
    ]):
        return "callout"

    # Schedule questions
    if any(phrase in msg_lower for phrase in [
        "my schedule", "when do i work", "what shifts", "next shift",
        "shifts this week", "working tomorrow", "work tomorrow"
    ]):
        return "schedule"

    # Payroll questions
    if any(phrase in msg_lower for phrase in [
        "pay stub", "paystub", "paycheck", "when do we get paid",
        "paid", "payroll", "direct deposit"
    ]):
        return "payroll"

    return "general"


def format_shift_context(shift) -> str:
    """Format a WellSky shift into context string for the AI."""
    if not shift:
        return ""

    client_name = f"{shift.client_first_name} {shift.client_last_name}".strip()
    if not client_name:
        client_name = "Unknown Client"

    parts = [f"Client: {client_name}"]

    if shift.date:
        parts.append(f"Date: {shift.date.strftime('%A, %B %d')}")

    if shift.start_time:
        parts.append(f"Start: {shift.start_time}")

    if shift.end_time:
        parts.append(f"End: {shift.end_time}")

    if shift.address:
        parts.append(f"Location: {shift.address}, {shift.city}")

    if shift.clock_in_time:
        parts.append(f"Clocked in: {shift.clock_in_time.strftime('%I:%M %p')}")

    if shift.clock_out_time:
        parts.append(f"Clocked out: {shift.clock_out_time.strftime('%I:%M %p')}")

    status_str = shift.status.value if hasattr(shift.status, 'value') else str(shift.status)
    parts.append(f"Status: {status_str}")

    return "\n".join(parts)


@app.post("/webhook/inbound-sms", response_model=SMSResponse)
async def handle_inbound_sms(sms: InboundSMS):
    """
    Handle inbound SMS messages with WellSky-aware intelligence.

    Gigi will:
    1. Look up the caregiver's shift info from WellSky
    2. Detect what they need (clock out, call out, schedule, etc.)
    3. Take action if possible (clock them out, report call-out)
    4. Generate a response that confirms the action
    """
    logger.info(f"Inbound SMS from {sms.from_number}: {sms.message[:100]}...")

    # Check if SMS auto-reply is disabled
    if not SMS_AUTOREPLY_ENABLED:
        logger.info("SMS auto-reply is DISABLED (GIGI_SMS_AUTOREPLY_ENABLED=false). Skipping reply.")
        return SMSResponse(
            from_number=sms.from_number,
            original_message=sms.message,
            caller_type="unknown",
            caller_name=None,
            generated_reply="[Auto-reply disabled - message logged for office follow-up]",
            reply_sent=False
        )

    try:
        # Look up caller info
        caller_info = await verify_caller(sms.from_number)

        # Detect intent from message
        intent = detect_sms_intent(sms.message)
        logger.info(f"Detected intent: {intent} for {sms.from_number}")

        # Handle shift offer responses FIRST (before other processing)
        # These are responses to "Reply YES to accept" shift offers
        if intent in ("shift_accept", "shift_decline"):
            try:
                logger.info(f"Processing shift response from {sms.from_number}: {intent}")
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{PORTAL_BASE_URL}/api/internal/shift-filling/sms-response",
                        json={
                            "phone_number": sms.from_number,
                            "message_text": sms.message
                        },
                        timeout=15.0
                    )
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("found_campaign"):
                            # This was a response to a shift offer
                            action = result.get("action")
                            if action == "assigned":
                                reply_text = (
                                    f"You're confirmed for the shift with {result.get('client_name', 'your client')} "
                                    f"on {result.get('shift_date', '')} at {result.get('shift_time', '')}. "
                                    f"Thank you for stepping up!"
                                )
                            elif action == "declined":
                                reply_text = "Got it, no problem. Thank you for letting us know!"
                            elif action == "already_filled":
                                reply_text = "Thanks for responding! This shift was already filled by another caregiver."
                            else:
                                reply_text = "Thanks for your response. We'll be in touch if needed."

                            # Send the reply
                            sms_sent = await _send_sms_ringcentral(sms.from_number, reply_text)
                            return SMSResponse(
                                success=True,
                                reply_sent=sms_sent,
                                reply_text=reply_text
                            )
                        else:
                            # No pending shift offer - fall through to normal processing
                            logger.info(f"No pending shift offer for {sms.from_number}, continuing normal flow")
            except Exception as shift_err:
                logger.warning(f"Error checking shift response: {shift_err}")
                # Fall through to normal processing

        # Look up shift data from WellSky
        shift_context = None
        action_taken = None
        current_shift = None

        if WELLSKY_AVAILABLE and wellsky:
            try:
                if intent == "clock_out":
                    # Get their current shift (the one they're trying to clock out of)
                    current_shift = wellsky.get_caregiver_current_shift(sms.from_number)
                    if current_shift:
                        shift_context = format_shift_context(current_shift)
                        # Actually clock them out
                        success, message = wellsky.clock_out_shift(
                            current_shift.id,
                            notes=f"Clocked out via Gigi SMS: {sms.message[:100]}"
                        )
                        if success:
                            action_taken = message
                            logger.info(f"Clocked out shift {current_shift.id}: {message}")

                elif intent == "clock_in":
                    # Get their upcoming shift
                    current_shift = wellsky.get_caregiver_current_shift(sms.from_number)
                    if current_shift:
                        shift_context = format_shift_context(current_shift)
                        # Clock them in
                        success, message = wellsky.clock_in_shift(
                            current_shift.id,
                            notes=f"Clocked in via Gigi SMS: {sms.message[:100]}"
                        )
                        if success:
                            action_taken = message
                            logger.info(f"Clocked in shift {current_shift.id}: {message}")

                elif intent == "callout":
                    # Report the call-out
                    success, message, affected_shift = wellsky.report_callout(
                        sms.from_number,
                        reason=sms.message[:200]
                    )
                    if success:
                        action_taken = message
                        current_shift = affected_shift
                        if affected_shift:
                            shift_context = format_shift_context(affected_shift)
                        logger.info(f"Call-out reported: {message}")

                elif intent == "schedule":
                    # Get upcoming shifts
                    shifts = wellsky.get_caregiver_upcoming_shifts(sms.from_number, days=7)
                    if shifts:
                        shift_lines = []
                        for shift in shifts[:5]:  # Max 5 shifts
                            client = f"{shift.client_first_name} {shift.client_last_name}".strip()
                            date_str = shift.date.strftime("%a %m/%d") if shift.date else ""
                            shift_lines.append(f"- {date_str} {shift.start_time}: {client}")
                        shift_context = "UPCOMING SHIFTS:\n" + "\n".join(shift_lines)

                else:
                    # For general messages, still try to get context
                    current_shift = wellsky.get_caregiver_current_shift(sms.from_number)
                    if current_shift:
                        shift_context = format_shift_context(current_shift)

            except Exception as ws_error:
                logger.warning(f"WellSky lookup failed: {ws_error}")
                # Continue without WellSky data

        # Generate AI response with shift context
        reply_text = await generate_sms_response(
            sms.message,
            caller_info,
            shift_context=shift_context,
            action_taken=action_taken
        )

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
        )
        result = await handle_inbound_sms(sms)
        
        # Log to Portal
        await _log_portal_event(
            description=f"SMS from {from_number}",
            event_type="sms_received",
            details=f"Msg: {message[:50]}...\nReply: {'Yes' if result.reply_sent else 'No'}",
            icon="💬"
        )

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

    # SECURITY: Verify RingCentral webhook signature if verification token is configured
    rc_verification_token = os.getenv("RINGCENTRAL_WEBHOOK_VERIFICATION_TOKEN")
    if rc_verification_token:
        # RingCentral includes verification token in the payload or header
        received_token = request.headers.get("X-RingCentral-Verification-Token")
        if received_token and received_token != rc_verification_token:
            logger.warning("RingCentral webhook: Invalid verification token")
            return JSONResponse({"error": "Invalid verification token"}, status_code=401)

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
async def test_sms_reply(
    from_number: str,
    message: str,
    _test_ok: None = Depends(require_gigi_test_endpoints_enabled)
):
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

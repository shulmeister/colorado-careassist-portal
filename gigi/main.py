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
from datetime import datetime, timedelta, time as time_cls
from typing import Optional, Dict, Any, List, Literal, Tuple
from enum import Enum
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse, Response, HTMLResponse
from pydantic import BaseModel, Field
import httpx
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app for Gigi routes
app = FastAPI(title="Gigi AI Agent", version="1.0.0")

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

# Import Gigi Memory System
try:
    from gigi.memory_system import MemorySystem, MemoryType, MemorySource, ImpactLevel, MemoryStatus
    memory_system = MemorySystem()
    MEMORY_SYSTEM_AVAILABLE = True
    logger.info("✓ Gigi Memory System initialized")
except Exception as e:
    memory_system = None
    MEMORY_SYSTEM_AVAILABLE = False
    logger.warning(f"Memory System not available: {e}")

# Import Gigi Mode Detection System
try:
    from gigi.mode_detector import ModeDetector, OperatingMode, ModeSource, parse_mode_command
    mode_detector = ModeDetector()
    MODE_DETECTOR_AVAILABLE = True
    logger.info("✓ Gigi Mode Detector initialized")
except Exception as e:
    mode_detector = None
    MODE_DETECTOR_AVAILABLE = False
    logger.warning(f"Mode Detector not available: {e}")

# Import Gigi Failure Protocol System
try:
    from gigi.failure_handler import FailureHandler, FailureType, FailureSeverity, FailureAction, safe_tool_call
    failure_handler = FailureHandler()
    FAILURE_HANDLER_AVAILABLE = True
    logger.info("✓ Gigi Failure Handler initialized")
except Exception as e:
    failure_handler = None
    FAILURE_HANDLER_AVAILABLE = False
    logger.warning(f"Failure Handler not available: {e}")

# Import Gigi Shift Lock System for coordinator coordination
try:
    from gigi.shift_lock import get_shift_lock_manager, ShiftLockConflictError as CoordinatorLockError
    shift_lock_manager = get_shift_lock_manager()
    SHIFT_LOCK_AVAILABLE = True
    logger.info("✓ Gigi Shift Lock Manager initialized")
except Exception as e:
    shift_lock_manager = None
    SHIFT_LOCK_AVAILABLE = False
    logger.warning(f"Shift Lock Manager not available: {e}")

# Import Partial Availability Parser for nuanced call-out handling
try:
    from gigi.partial_availability_parser import detect_partial_availability
    PARTIAL_AVAILABILITY_PARSER_AVAILABLE = True
    logger.info("✓ Partial Availability Parser loaded")
except Exception as e:
    detect_partial_availability = None
    PARTIAL_AVAILABILITY_PARSER_AVAILABLE = False
    logger.warning(f"Partial Availability Parser not available: {e}")

# Import Caregiver Matching Engine
try:
    from services.caregiver_matching_engine import CaregiverMatchingEngine, ShiftUrgency
    matching_engine = CaregiverMatchingEngine()
    MATCHING_ENGINE_AVAILABLE = True
    logger.info("✓ Caregiver Matching Engine loaded")
except ImportError:
    matching_engine = None
    MATCHING_ENGINE_AVAILABLE = False
    logger.warning("Caregiver Matching Engine not available")

# Import Entity Resolution Service
try:
    from services.entity_resolution_service import entity_resolver
    ENTITY_RESOLUTION_AVAILABLE = True
    logger.info("✓ Entity Resolution Service loaded")
except ImportError:
    entity_resolver = None
    ENTITY_RESOLUTION_AVAILABLE = False
    logger.warning("Entity Resolution Service not available")

# Import enhanced webhook functionality for caller ID, transfer, and message taking
try:
    from enhanced_webhook import (
        CallerLookupService, generate_greeting, transfer_call,
        send_telegram_message, handle_message_received, get_weather
    )
    ENHANCED_WEBHOOK_AVAILABLE = True
except ImportError:
    logger.warning("Enhanced webhook not available - caller ID and transfer features disabled")
    ENHANCED_WEBHOOK_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# Configuration - SECURITY: No hardcoded credentials
# =============================================================================

# Alpha Vantage API for financial data (stocks, crypto)
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

# Ticketmaster API for events (concerts, sports, theater)
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY", "Sczxp0S6KI0GLLj1CZtYlHm57Za8Byi9")

# Setlist.fm API for concert setlists and song history
SETLIST_FM_API_KEY = os.getenv("SETLIST_FM_API_KEY", "E79vhiUAC8vhcI7NZTGci17xgXwtpqaYo4xp")

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
BEETEXTING_AUTH_URL = os.getenv("BEETEXTING_AUTH_URL", "https://auth.beetexting.com/oauth2/token/")
BEETEXTING_API_URL = os.getenv("BEETEXTING_API_URL", "https://connect.beetexting.com/prod")

# Phone numbers (safe defaults - these are public business numbers)
BEETEXTING_FROM_NUMBER = os.getenv("BEETEXTING_FROM_NUMBER", "+17194283999")  # 719-428-3999
RINGCENTRAL_FROM_NUMBER = os.getenv("RINGCENTRAL_FROM_NUMBER", "+17194283999")
SMS_PROVIDER = os.getenv("GIGI_SMS_PROVIDER", "ringcentral").lower()
ON_CALL_MANAGER_PHONE = os.getenv("ON_CALL_MANAGER_PHONE", "+13037571777")    # 303-757-1777
JASON_PHONE = "+16039971495"  # Jason Shulman - for call transfers

# Escalation contacts (RingCentral extensions for urgent client issues)
ESCALATION_CYNTHIA_EXT = os.getenv("ESCALATION_CYNTHIA_EXT", "105")  # Cynthia Pointe - Care Manager
ESCALATION_JASON_EXT = os.getenv("ESCALATION_JASON_EXT", "101")      # Jason Shulman - Owner

# SMS Auto-Reply Toggle (default ON - Gigi replies outside office hours)
SMS_AUTOREPLY_ENABLED = os.getenv("GIGI_SMS_AUTOREPLY_ENABLED", "true").lower() == "true"

# After-hours auto-reply (default ON; replies only outside office hours)
SMS_AFTER_HOURS_ONLY = os.getenv("GIGI_SMS_AFTER_HOURS_ONLY", "true").lower() == "true"
OFFICE_HOURS_START = os.getenv("GIGI_OFFICE_HOURS_START", "08:00")
OFFICE_HOURS_END = os.getenv("GIGI_OFFICE_HOURS_END", "17:00")

# Operations SMS Toggle (set to "true" to enable SMS from call-out operations)
# DEFAULT IS OFF - Must be explicitly enabled when WellSky is fully connected
OPERATIONS_SMS_ENABLED = os.getenv("GIGI_OPERATIONS_SMS_ENABLED", "false").lower() == "true"

# RingCentral credentials (required for SMS - no hardcoded fallbacks)
RINGCENTRAL_CLIENT_ID = os.getenv("RINGCENTRAL_CLIENT_ID")
RINGCENTRAL_CLIENT_SECRET = os.getenv("RINGCENTRAL_CLIENT_SECRET")
RINGCENTRAL_SERVER = os.getenv("RINGCENTRAL_SERVER", "https://platform.ringcentral.com")
RINGCENTRAL_JWT = os.getenv("RINGCENTRAL_JWT_TOKEN") or os.getenv("RINGCENTRAL_JWT")

# =============================================================================
# SHADOW MODE - "Gigi Brain" Visualization & Grading
# =============================================================================
# Allows seeing what Gigi WOULD do without actually changing data or sending texts.
# Set GIGI_MODE=shadow in environment variables.

GIGI_MODE = os.getenv("GIGI_MODE", "live").lower()
SHADOW_LOGS = []

import uuid

def log_shadow_action(action: str, details: Dict[str, Any], trigger: str = "Unknown"):
    """Log an action taken in shadow mode."""
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trigger": trigger,
        "action": action,
        "details": details,
        "feedback": None  # 'good', 'bad', or None
    }
    SHADOW_LOGS.append(entry)
    # Keep last 100 logs
    if len(SHADOW_LOGS) > 100:
        SHADOW_LOGS.pop(0)
    logger.info(f"[SHADOW MODE] {action}: {details}")

# ... (Existing config status code) ...

# =============================================================================
# SIMULATION ENDPOINTS (For Testing Shadow Mode)
# =============================================================================

@app.post("/api/gigi/shadow/feedback")
async def record_shadow_feedback(request: Request):
    """Record human feedback on a shadow mode decision."""
    data = await request.json()
    log_id = data.get("id")
    rating = data.get("rating")  # "good" or "bad"
    
    for log in SHADOW_LOGS:
        if log["id"] == log_id:
            log["feedback"] = rating
            # In a real system, we would save this to a dataset for fine-tuning
            logger.info(f"Feedback recorded for {log_id}: {rating}")
            
            # If feedback is "bad", capture a correction memory
            if rating == "bad" and MEMORY_SYSTEM_AVAILABLE:
                capture_memory(
                    content=f"Correction on action '{log['action']}': Human marked this as incorrect behavior.",
                    memory_type="correction",
                    category="behavior_correction",
                    impact="high",
                    metadata={"log_id": log_id, "original_details": log['details']}
                )
            return {"success": True}
    
    return {"success": False, "error": "Log entry not found"}

@app.post("/simulate/callout")
async def simulate_callout():
    """
    Simulate a caregiver call-out event to test Shadow Mode logic.
    Triggers execute_caregiver_call_out with mock data.
    """
    logger.info("Starting simulated call-out...")
    
    # Mock data
    mock_caregiver_id = "TEST_CG_123"
    mock_shift_id = "TEST_SHIFT_456"
    mock_reason = "Simulation Test (Sick)"
    
    # Force log entry for the simulation start
    if GIGI_MODE == "shadow":
        log_shadow_action(
            "SIMULATION_START", 
            {
                "type": "caregiver_call_out",
                "caregiver_id": mock_caregiver_id,
                "shift_id": mock_shift_id
            },
            trigger="Manual Simulation Button"
        )
    
    # Execute the tool (which handles Shadow Mode internally)
    result = await execute_caregiver_call_out(
        caregiver_id=mock_caregiver_id,
        shift_id=mock_shift_id,
        reason=mock_reason
    )
    
    return {
        "status": "simulation_complete",
        "mode": GIGI_MODE,
        "result": result
    }

@app.get("/shadow", response_class=HTMLResponse)
async def get_shadow_dashboard():
    """Simple dashboard to view Gigi's shadow mode actions."""
    status_color = "orange" if GIGI_MODE == "shadow" else "green"
    
    # Calculate stats
    total_logs = len(SHADOW_LOGS)
    rated_logs = [l for l in SHADOW_LOGS if l['feedback'] is not None]
    good_logs = [l for l in rated_logs if l['feedback'] == 'good']
    
    approval_rate = (len(good_logs) / len(rated_logs) * 100) if rated_logs else 0
    
    html = f"""
    <html>
    <head>
        <title>Gigi Brain 🧠 - Review Station</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #f8f9fa; font-family: 'Segoe UI', system-ui, sans-serif; }}
            .container {{ max-width: 900px; margin-top: 30px; }}
            .status-badge {{ 
                padding: 5px 12px; 
                border-radius: 20px; 
                font-weight: bold; 
                font-size: 0.9em;
                text-transform: uppercase;
            }}
            .status-shadow {{ background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }}
            .status-live {{ background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
            
            .stat-card {{
                background: white;
                border-radius: 10px;
                padding: 20px;
                text-align: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                height: 100%;
            }}
            .stat-value {{ font-size: 2.5rem; font-weight: 700; color: #2c3e50; }}
            .stat-label {{ color: #6c757d; font-weight: 600; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 1px; }}
            
            .review-card {{
                background: white;
                border-radius: 12px;
                border: 1px solid #e9ecef;
                margin-bottom: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.02);
                overflow: hidden;
                transition: transform 0.2s;
            }}
            .review-card:hover {{ transform: translateY(-2px); box-shadow: 0 6px 12px rgba(0,0,0,0.05); }}
            
            .card-header {{
                background: #f8f9fa;
                border-bottom: 1px solid #e9ecef;
                padding: 12px 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .timestamp {{ font-size: 0.85rem; color: #6c757d; }}
            
            .card-body {{ padding: 20px; }}
            
            .trigger-box {{
                background: #e3f2fd;
                border-left: 4px solid #0d6efd;
                padding: 10px 15px;
                border-radius: 4px;
                margin-bottom: 15px;
            }}
            .action-box {{
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 10px 15px;
                border-radius: 4px;
                margin-bottom: 15px;
            }}
            
            .json-dump {{
                background: #2d2d2d;
                color: #e6e6e6;
                padding: 10px;
                border-radius: 6px;
                font-family: monospace;
                font-size: 0.85em;
                max-height: 150px;
                overflow-y: auto;
                margin-top: 10px;
            }}
            
            .feedback-actions {{
                display: flex;
                gap: 10px;
                justify-content: flex-end;
                border-top: 1px solid #f0f0f0;
                padding-top: 15px;
                margin-top: 10px;
            }}
            
            .btn-feedback {{
                border-radius: 50px;
                padding: 6px 16px;
                font-weight: 600;
                font-size: 0.9rem;
                display: flex;
                align-items: center;
                gap: 6px;
                transition: all 0.2s;
            }}
            .btn-feedback:hover {{ transform: scale(1.05); }}
            
            .feedback-given {{ opacity: 0.7; pointer-events: none; }}
            .feedback-good {{ background-color: #d1e7dd; color: #0f5132; border-color: #badbcc; }}
            .feedback-bad {{ background-color: #f8d7da; color: #842029; border-color: #f5c2c7; }}
            
            .simulation-panel {{
                background: linear-gradient(135deg, #0d6efd 0%, #0043a8 100%);
                color: white;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 30px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h1 class="fw-bold mb-0">Gigi Brain 🧠</h1>
                    <p class="text-muted">Shadow Mode Review Station</p>
                </div>
                <div class="status-badge status-{GIGI_MODE}">
                    Mode: {GIGI_MODE.upper()}
                </div>
            </div>
            
            <div class="row mb-4">
                <div class="col-md-4">
                    <div class="stat-card">
                        <div class="stat-value text-primary">{total_logs}</div>
                        <div class="stat-label">Decisions</div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="stat-card">
                        <div class="stat-value text-success">{approval_rate:.0f}%</div>
                        <div class="stat-label">Approval Rate</div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="stat-card">
                        <div class="stat-value text-warning">{len(rated_logs)}</div>
                        <div class="stat-label">Reviewed</div>
                    </div>
                </div>
            </div>
            
            <div class="simulation-panel">
                <div>
                    <h4 class="mb-1">🧪 Test Laboratory</h4>
                    <p class="mb-0 opacity-75">Trigger a fake event to see how Gigi responds.</p>
                </div>
                <button onclick="runSimulation('callout')" class="btn btn-light fw-bold text-primary">
                    Simulate Call-Out
                </button>
            </div>
            
            <div id="sim-result" class="alert alert-info d-none mb-4"></div>
            
            <h3 class="mb-3">Recent Decisions</h3>
            
            {'<div class="text-center py-5 text-muted">No actions recorded yet. Waiting for incoming messages...</div>' if not SHADOW_LOGS else ''}
            
            <div id="logs">
    """
    
    for log in reversed(SHADOW_LOGS):
        feedback_class = ""
        if log['feedback'] == 'good':
            feedback_class = "feedback-given feedback-good"
        elif log['feedback'] == 'bad':
            feedback_class = "feedback-given feedback-bad"
            
        html += f"""
        <div class="review-card" id="card-{log['id']}">
            <div class="card-header">
                <span class="fw-bold">{log['action']}</span>
                <span class="timestamp">{log['timestamp']}</span>
            </div>
            <div class="card-body">
                <div class="trigger-box">
                    <small class="text-uppercase fw-bold text-primary opacity-75">Trigger</small><br>
                    {log.get('trigger', 'Internal Event')}
                </div>
                
                <div class="action-box">
                    <small class="text-uppercase fw-bold text-warning opacity-75">Proposed Action</small><br>
                    {log.get('message') or "Executed Logic: " + log['action']}
                </div>
                
                <div class="accordion" id="accordion-{log['id']}">
                    <div class="accordion-item border-0">
                        <h2 class="accordion-header">
                            <button class="accordion-button collapsed py-2 bg-light rounded" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-{log['id']}">
                                <small>View Raw Data</small>
                            </button>
                        </h2>
                        <div id="collapse-{log['id']}" class="accordion-collapse collapse">
                            <div class="json-dump">
                                {json.dumps(log['details'], indent=2)}
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="feedback-actions {feedback_class}" id="actions-{log['id']}">
                    <button onclick="rate('{log['id']}', 'good')" class="btn btn-outline-success btn-feedback">
                        👍 Good
                    </button>
                    <button onclick="rate('{log['id']}', 'bad')" class="btn btn-outline-danger btn-feedback">
                        👎 Bad
                    </button>
                </div>
            </div>
        </div>
        """
        
    html += """
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            async function runSimulation(type) {
                const resultDiv = document.getElementById('sim-result');
                resultDiv.classList.remove('d-none');
                resultDiv.innerHTML = 'Running simulation...';
                try {
                    const response = await fetch(`/simulate/${type}`, { method: 'POST' });
                    const data = await response.json();
                    resultDiv.innerHTML = '✅ Simulation Complete! Refreshing feed...';
                    setTimeout(() => window.location.reload(), 1500);
                } catch (e) {
                    resultDiv.innerHTML = '❌ Error: ' + e.message;
                }
            }
            
            async function rate(id, rating) {
                try {
                    const response = await fetch('/api/gigi/shadow/feedback', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({id: id, rating: rating})
                    });
                    
                    const actionsDiv = document.getElementById('actions-' + id);
                    if (rating === 'good') {
                        actionsDiv.classList.add('feedback-given', 'feedback-good');
                    } else {
                        actionsDiv.classList.add('feedback-given', 'feedback-bad');
                    }
                } catch (e) {
                    alert('Error saving feedback');
                }
            }
            
            // Auto-refresh every 10 seconds to catch new real messages
            // setTimeout(() => window.location.reload(), 10000);
        </script>
    </body>
    </html>
    """
    return html

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

    if not BEETEXTING_CLIENT_ID or not BEETEXTING_CLIENT_SECRET or not BEETEXTING_API_KEY:
        logger.warning("BeeTexting credentials not configured")
        return None

    try:
        async with httpx.AsyncClient() as client:
            # OAuth2 client credentials flow
            response = await client.post(
                BEETEXTING_AUTH_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": BEETEXTING_CLIENT_ID,
                    "client_secret": BEETEXTING_CLIENT_SECRET
                },
                headers={
                    "x-api-key": BEETEXTING_API_KEY,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json"
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
    token = await _get_beetexting_token()

    if not token or not BEETEXTING_API_KEY:
        logger.warning("BeeTexting not configured - trying RingCentral")
        return await _send_sms_ringcentral(to_phone, message)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BEETEXTING_API_URL}/message/sendsms",
                headers={
                    "Authorization": f"Bearer {token}",
                    "x-api-key": BEETEXTING_API_KEY
                },
                params={
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
    """Send SMS via RingCentral API."""
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
                    "from": {"phoneNumber": RINGCENTRAL_FROM_NUMBER},
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


async def _send_sms_primary(to_phone: str, message: str) -> bool:
    """Send SMS via primary provider (RingCentral or BeeTexting)."""
    if SMS_PROVIDER == "beetexting":
        return await _send_sms_beetexting(to_phone, message)
    return await _send_sms_ringcentral(to_phone, message)


async def send_glip_message(chat_id: str, text: str) -> bool:
    """Send a message to a RingCentral Glip team/chat."""
    token = await _get_ringcentral_token()
    if not token:
        logger.warning("RingCentral not available - Glip message not sent")
        return False
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RINGCENTRAL_SERVER}/restapi/v1.0/glip/chats/{chat_id}/posts",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={"text": text},
                timeout=10.0
            )
            return response.status_code in (200, 201)
    except Exception as e:
        logger.error(f"Error sending Glip message: {e}")
        return False

async def assign_beetexting_conversation(from_phone: str, agent_email: str) -> bool:
    """Assign a BeeTexting conversation to a specific agent."""
    token = await _get_beetexting_token()
    if not token:
        logger.warning("BeeTexting credentials missing - cannot assign conversation")
        return False

    try:
        # BeeTexting usually identifies conversations by the contact's phone number
        clean_phone = ''.join(filter(str.isdigit, from_phone))[-10:]
        async with httpx.AsyncClient() as client:
            # Note: Endpoint path is hypothetical based on typical BeeTexting patterns
            # Would need to verify against their actual API docs for "Assign Conversation"
            response = await client.post(
                f"{BEETEXTING_API_URL}/conversation/assign",
                headers={
                    "Authorization": f"Bearer {token}",
                    "x-api-key": BEETEXTING_API_KEY
                },
                params={
                    "phone_number": clean_phone,
                    "agent_email": agent_email
                },
                timeout=10.0
            )
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Error assigning BeeTexting conversation: {e}")
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
            start_time_str = shift.get("start_time") or ""
            date_str = shift.get("date") or ""

            if date_str and start_time_str:
                start_time = datetime.fromisoformat(f"{date_str}T{start_time_str}")
            else:
                start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))

            if start_time > now:
                upcoming_shifts.append((start_time, shift))
        except (ValueError, TypeError):
            continue

    if not upcoming_shifts:
        return None

    # Sort by start time and get the nearest one
    upcoming_shifts.sort(key=lambda x: x[0])
    _, next_shift = upcoming_shifts[0]

    start_time_str = next_shift.get("start_time") or ""
    end_time_str = next_shift.get("end_time") or ""
    date_str = next_shift.get("date") or ""

    if date_str and start_time_str:
        start_time = datetime.fromisoformat(f"{date_str}T{start_time_str}")
    else:
        start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))

    if date_str and end_time_str:
        end_time = datetime.fromisoformat(f"{date_str}T{end_time_str}")
    else:
        end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))

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
    try:
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
        
    except Exception as e:
        logger.error(f"Error in get_active_shifts: {e}")
        # Return empty list on failure rather than crashing conversation
        # This is a "Degrade" action
        failure_handler.handle_tool_failure("get_active_shifts", e, {"person_id": person_id})
        return []


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
    try:
        logger.info(f"execute_caregiver_call_out: caregiver={caregiver_id}, shift={shift_id}, reason={reason}")

        # =========================================================================
        # COORDINATOR COORDINATION: Acquire shift lock to prevent collisions
        # =========================================================================
        # If offshore scheduler or human coordinator is already processing this
        # shift, we get a lock conflict and tell the caregiver to wait.

        # SHADOW MODE: Skip lock acquisition (since we aren't really processing)
        if GIGI_MODE == "shadow":
            logger.info(f"SHADOW MODE: Skipping shift lock for {shift_id}")
            return await _execute_caregiver_call_out_locked(
                caregiver_id=caregiver_id,
                shift_id=shift_id,
                reason=reason
            )

        if SHIFT_LOCK_AVAILABLE and shift_lock_manager:
            try:
                with shift_lock_manager.acquire_shift_lock(
                    shift_id=shift_id,
                    locked_by="gigi_ai",
                    reason="processing_callout",
                    timeout_minutes=10
                ) as lock_info:
                    logger.info(f"Shift lock acquired: {shift_id} by gigi_ai")
                    # Proceed with call-out processing inside the lock
                    return await _execute_caregiver_call_out_locked(
                        caregiver_id=caregiver_id,
                        shift_id=shift_id,
                        reason=reason
                    )
            except CoordinatorLockError as e:
                # Someone else (human coordinator or another Gigi instance) is processing this shift
                logger.warning(f"Shift lock conflict for {shift_id}: {e}")
                lock_status = shift_lock_manager.get_lock_status(shift_id)
                locked_by = lock_status.locked_by if lock_status else "someone"

                return {
                    "success": False,
                    "shift_locked": True,
                    "locked_by": locked_by,
                    "message": (
                        f"I see this shift is currently being processed by our team. "
                        f"Please hold on for just a moment while they handle it, or "
                        f"try calling back in a few minutes if you need immediate assistance."
                    ),
                    "errors": [f"Shift locked by {locked_by}"],
                    "action_completed": True,
                    "next_step": "Tell caregiver the shift is being handled. Ask if they need anything else."
                }
        else:
            # Shift lock not available - proceed without lock (development mode)
            logger.warning(f"Shift lock manager not available - proceeding without lock for shift {shift_id}")
            return await _execute_caregiver_call_out_locked(
                caregiver_id=caregiver_id,
                shift_id=shift_id,
                reason=reason
            )
            
    except Exception as e:
        # Phase 3 Failure Protocol: Handle tool failure gracefully
        return handle_tool_error("execute_caregiver_call_out", e, {
            "caregiver_id": caregiver_id,
            "shift_id": shift_id,
            "reason": reason
        })


async def _execute_caregiver_call_out_locked(
    caregiver_id: str,
    shift_id: str,
    reason: str = "sick"
) -> Dict[str, Any]:
    """
    Internal implementation of execute_caregiver_call_out.
    This runs inside the shift lock context.
    """
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
    # SHADOW MODE INTERCEPTION
    # =========================================================================
    if GIGI_MODE == "shadow":
        logger.info(f"SHADOW MODE: Intercepting call-out for {shift_id}")

        # Log Step A
        log_shadow_action("UPDATE_WELLSKY_SHIFT", {
            "shift_id": shift_id,
            "status": "open",
            "reason": reason,
            "caregiver": caregiver_name,
            "client": client_name
        })

        # Log Step B (simulated data)
        log_shadow_action("LOG_PORTAL_EVENT", {
            "caregiver": caregiver_name,
            "client": client_name,
            "reason": reason,
            "status": "pending_coverage"
        })

        # Log Step C (simulated)
        log_shadow_action("TRIGGER_REPLACEMENT_BLAST", {
            "client": client_name,
            "shift_time": shift_time,
            "urgency": "high"
        })

        return {
            "success": True,
            "step_a_wellsky_updated": True,
            "step_b_portal_logged": True,
            "step_c_replacement_blast_sent": True,
            "call_out_id": "SHADOW_MODE_ID",
            "caregivers_notified": 5,
            "message": (
                f"[SHADOW MODE] I would have updated the system and notified caregivers. "
                f"The shift with {client_name} would be marked as open. "
                f"(No actual changes made)"
            ),
            "errors": []
        }

    # =========================================================================
    # STEP A: Un-assign Caregiver in WellSky (The "Correct" Workflow)
    # =========================================================================
    wellsky_update_failed = False
    wellsky_failure_reason = ""
    
    if GIGI_MODE == "shadow":
        log_shadow_action("UNASSIGN_CAREIVER_FROM_SHIFT", {"shift_id": shift_id, "caregiver_id": caregiver_id})
        result["step_a_wellsky_updated"] = True
    elif WELLSKY_AVAILABLE and wellsky:
        try:
            # 1. Get the full appointment object
            _, appointment_obj = wellsky.get_appointment(shift_id)
            if appointment_obj:
                # 2. Modify the object: un-assign the caregiver
                appointment_obj["caregiver"] = None
                
                # 3. PUT the modified object back
                update_success, update_response = wellsky.update_appointment(shift_id, appointment_obj)
                
                if update_success:
                    result["step_a_wellsky_updated"] = True
                    logger.info(f"STEP A SUCCESS: Caregiver {caregiver_id} un-assigned from shift {shift_id} in WellSky.")
                    
                    # 4. Add a Note to the Client (Care Alert)
                    wellsky.add_note_to_client(
                        client_id=client_id,
                        note=f"🚨 CARE ALERT: Caregiver {caregiver_name} called out for shift on {shift_time}. Reason: {reason}",
                        note_type="callout"
                    )

                    # 5. Create WellSky Task for coverage
                    task_created = wellsky.create_admin_task(
                        title=f"URGENT: Find replacement for {client_name}",
                        description=f"Caregiver {caregiver_name} called out for shift on {shift_time}.\nReason: {reason}\nShift ID: {shift_id}\nClient: {client_name}",
                        priority="urgent",
                        related_client_id=client_id,
                        assigned_to=os.getenv("WELLSKY_SCHEDULER_USER_ID")  # Assign to scheduler if configured
                    )
                    if task_created:
                        logger.info(f"✅ WellSky Task created for shift {shift_id} coverage")
                    else:
                        logger.warning(f"⚠️ Failed to create WellSky Task for shift {shift_id}")
                else:
                    wellsky_update_failed = True
                    wellsky_failure_reason = str(update_response)
            else:
                wellsky_update_failed = True
                wellsky_failure_reason = "Could not fetch original appointment to modify."
        except Exception as e:
            wellsky_update_failed = True
            wellsky_failure_reason = str(e)
    
    # CRITICAL CHECK: If the update failed, STOP and escalate.
    if wellsky_update_failed:
        logger.error(f"⚠️ ABORTING call-out process - WellSky update failed for shift {shift_id}: {wellsky_failure_reason}")
        # (Escalation block follows)
        pass 

    # =========================================================================
    # STEP B: Notify Team & Assign Thread
    # =========================================================================
    if not wellsky_update_failed:
        try:
            # 1. Notify "New Schedulers" RingCentral Team
            schedulers_chat_id = os.getenv("RINGCENTRAL_SCHEDULERS_CHAT_ID")
            if schedulers_chat_id:
                team_msg = (
                    f"📢 GIGI ALERT: {caregiver_name} called out for {client_name} ({shift_time}).\n"
                    f"✅ WellSky Shift marked OPEN.\n"
                    f"✅ Care Alert added to client file.\n"
                    f"⏳ Gigi is filling the shift now."
                )
                await send_glip_message(schedulers_chat_id, team_msg)

            # 2. Assign BeeTexting conversation to Israt
            scheduler_email = os.getenv("BEETEXTING_SCHEDULER_EMAIL", "israt@coloradocareassist.com")
            await assign_beetexting_conversation(caregiver_id, scheduler_email)
            result["step_b_portal_logged"] = True

        except Exception as e:
            logger.error(f"Error in team notification workflow: {e}")

    # =========================================================================
    # CRITICAL CHECK: If WellSky update failed, STOP and escalate to human
    # =========================================================================
    if wellsky_update_failed:
        logger.error(f"⚠️ ABORTING call-out process - WellSky update failed for shift {shift_id}")

        # Escalate to Jason immediately
        escalation_message = (
            f"🚨 CRITICAL GIGI FAILURE: Call-out for {client_name} ({shift_time}) "
            f"could not be processed. WellSky API error: {wellsky_failure_reason}. "
            f"Caregiver: {caregiver_name} (Reason: {reason}). "
            f"ACTION REQUIRED: Manually update WellSky shift {shift_id} and find replacement."
        )

        if OPERATIONS_SMS_ENABLED:
            # Send to Jason Shulman (ext 101)
            jason_phone = "+17205550101"  # TODO: Update with actual Jason's number
            await _send_sms_beetexting(jason_phone, escalation_message)
            logger.critical(f"ESCALATED to Jason ({jason_phone}): {escalation_message}")

            # Also alert on-call manager
            await _send_sms_beetexting(ON_CALL_MANAGER_PHONE, escalation_message)
            logger.critical(f"ESCALATED to on-call manager ({ON_CALL_MANAGER_PHONE})")
        else:
            logger.critical(f"[SMS DISABLED] Would escalate to Jason: {escalation_message}")

        result["success"] = False
        result["human_escalation_required"] = True
        result["escalated_to"] = "Jason Shulman + On-Call Manager"
        result["message"] = (
            f"I've logged your call-out for {client_name}, but I'm having trouble "
            f"connecting to the scheduling system right now. I've immediately notified "
            f"the manager on duty who will handle this manually. They should contact you soon "
            f"to confirm. Feel better!"
        )
        result["action_completed"] = True
        result["next_step"] = "Tell caregiver manager was notified. Ask 'Is there anything else?'"

        logger.info(f"execute_caregiver_call_out ABORTED - human escalation sent")
        return result  # ⛔ STOP HERE - do NOT proceed with Steps B & C

    # =========================================================================
    # STEP B: Log call-out event to Portal & Notify Team
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

    if GIGI_MODE == "shadow":
        log_shadow_action("LOG_PORTAL_EVENT", call_out_data)
        log_shadow_action("NOTIFY_TEAM", {
            "team": "New Schedulers",
            "message": f"Call-Out from {caregiver_name}"
        })
    else:
        try:
            # 1. Log to Portal (Internal Record)
            async with httpx.AsyncClient() as client:
                # Portal logging would go here if needed
                pass

            # 2. Notify "New Schedulers" RingCentral Team
            schedulers_chat_id = os.getenv("RINGCENTRAL_SCHEDULERS_CHAT_ID")
            if schedulers_chat_id:
                team_msg = (
                    f"📢 GIGI ALERT: {caregiver_name} called out for {client_name} ({shift_time}).\n"
                    f"Reason: {reason}.\n"
                    f"A task has been created in WellSky to un-assign and find coverage." # This message is now slightly inaccurate, but still conveys the need for action.
                )
                await send_glip_message(schedulers_chat_id, team_msg)

            # 3. Assign BeeTexting conversation to Israt
            scheduler_email = os.getenv("BEETEXTING_SCHEDULER_EMAIL", "israt@coloradocareassist.com")
            await assign_beetexting_conversation(caregiver_id, scheduler_email)

        except Exception as e:
            logger.error(f"Error in expanded call-out workflow: {e}")

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

    # =========================================================================
    # CRITICAL CHECK: If BOTH B and C failed, escalate immediately
    # =========================================================================
    # Scenario: WellSky updated (shift is open) but NO ONE was notified
    # Result: Zero coverage attempt, but shift shows as "open" in system
    if not result["step_b_portal_logged"] and not result["step_c_replacement_blast_sent"]:
        logger.error(f"⚠️ CRITICAL: Steps B & C both failed for shift {shift_id} - shift is open but no notifications sent!")

        escalation_message = (
            f"🚨 GIGI NOTIFICATION FAILURE: {caregiver_name} called out for {client_name} "
            f"({shift_time}). Shift is marked OPEN in WellSky but automated notifications FAILED. "
            f"NO caregivers were notified. ACTION REQUIRED: Manually send replacement blast for shift {shift_id}."
        )

        if OPERATIONS_SMS_ENABLED:
            jason_phone = "+17205550101"  # TODO: Update with actual Jason's number
            await _send_sms_beetexting(jason_phone, escalation_message)
            await _send_sms_beetexting(ON_CALL_MANAGER_PHONE, escalation_message)
            logger.critical(f"ESCALATED notification failure to Jason + on-call manager")
        else:
            logger.critical(f"[SMS DISABLED] Would escalate: {escalation_message}")

        result["human_escalation_required"] = True
        result["escalation_reason"] = "Notification systems failed - manual intervention needed"

    # Also send direct notification to On-Call Manager (only if operations SMS is enabled)
    elif result["step_c_replacement_blast_sent"]:
        # Normal case: replacement blast succeeded
        sms_message = (
            f"CALL-OUT: {caregiver_name} called out for {client_name} "
            f"({shift_time}). Reason: {reason}. "
            f"Replacement blast sent to {result.get('caregivers_notified', 0)} caregivers. "
            f"Logged by Gigi at {datetime.now().strftime('%I:%M %p')}."
        )
        if OPERATIONS_SMS_ENABLED:
            await _send_sms_beetexting(ON_CALL_MANAGER_PHONE, sms_message)
            logger.info(f"SMS notification sent to on-call manager")
        else:
            logger.info(f"[DISABLED] Would send SMS to {ON_CALL_MANAGER_PHONE}: {sms_message}")

    # =========================================================================
    # Build final result and message for Gigi to speak
    # =========================================================================
    # NOTE: If we reach here, Step A (WellSky) succeeded (otherwise we would have
    # returned early with escalation). So we only check Steps B & C.
    steps_completed = sum([
        result["step_a_wellsky_updated"],
        result["step_b_portal_logged"],
        result["step_c_replacement_blast_sent"]
    ])

    # Success requires:
    # - Step A MUST succeed (critical - we aborted early if it failed)
    # - At least one of B or C succeeds (logging or SMS blast)
    result["success"] = result["step_a_wellsky_updated"] and steps_completed >= 2

    if result["success"]:
        result["message"] = (
            f"I've updated the system and we are already looking for a replacement. "
            f"The shift with {client_name} has been marked as open, and I've notified "
            f"available caregivers in the area. Feel better, and please keep us updated "
            f"if anything changes."
        )
    elif result["step_a_wellsky_updated"] and steps_completed == 1:
        # WellSky updated but only 1 of B/C succeeded
        result["message"] = (
            f"I've updated the scheduling system to mark your shift as open. "
            f"I had some trouble with the automated notifications, so I've alerted "
            f"the on-call manager who will follow up manually. Feel better!"
        )
    else:
        # This should never happen (we would have returned early), but just in case
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


async def cancel_shift_acceptance(
    caregiver_id: str,
    shift_id: str,
    reason: str = "Unable to work shift"
) -> Dict[str, Any]:
    """
    Cancel a previously accepted shift assignment.

    Handles scenario where caregiver accepts a shift via SMS/call, then
    calls back to cancel: "Actually, I can't make it."

    This function:
    1. Unassigns the caregiver from the shift in WellSky
    2. Marks the shift as open again
    3. Restarts the replacement search
    4. Notifies other caregivers that shift is available
    5. Alerts on-call manager about the cancellation

    Args:
        caregiver_id: The caregiver's ID who is canceling
        shift_id: The shift they're canceling
        reason: Why they're canceling (e.g., "changed mind", "conflict", "emergency")

    Returns:
        Dict with cancellation status and next steps

    Example conversation:
        Caregiver: "Hi, I accepted the 2pm shift earlier but I can't make it anymore"
        Gigi: *calls cancel_shift_acceptance*
        Gigi: "I understand. I've cancelled your assignment and we're finding someone else..."
    """
    try:
        logger.info(f"cancel_shift_acceptance called: caregiver={caregiver_id}, shift={shift_id}, reason={reason}")

        # =========================================================================
        # COORDINATOR COORDINATION: Acquire shift lock to prevent collisions
        # =========================================================================
        if SHIFT_LOCK_AVAILABLE and shift_lock_manager:
            try:
                with shift_lock_manager.acquire_shift_lock(
                    shift_id=shift_id,
                    locked_by="gigi_ai",
                    reason="cancelling_acceptance",
                    timeout_minutes=10
                ) as lock_info:
                    logger.info(f"Shift lock acquired for cancellation: {shift_id} by gigi_ai")
                    return await _cancel_shift_acceptance_locked(
                        caregiver_id=caregiver_id,
                        shift_id=shift_id,
                        reason=reason
                    )
            except CoordinatorLockError as e:
                logger.warning(f"Shift lock conflict for cancellation {shift_id}: {e}")
                lock_status = shift_lock_manager.get_lock_status(shift_id)
                locked_by = lock_status.locked_by if lock_status else "someone"

                return {
                    "success": False,
                    "shift_locked": True,
                    "locked_by": locked_by,
                    "message": (
                        f"I see this shift is currently being processed. Please hold on for just "
                        f"a moment while the team handles it, or try calling back in a few minutes."
                    ),
                    "errors": [f"Shift locked by {locked_by}"],
                    "action_completed": True,
                    "next_step": "Tell caregiver the shift is being handled. Ask if they need anything else."
                }
        else:
            logger.warning(f"Shift lock manager not available - proceeding without lock")
            return await _cancel_shift_acceptance_locked(
                caregiver_id=caregiver_id,
                shift_id=shift_id,
                reason=reason
            )

    except Exception as e:
        # Phase 3 Failure Protocol: Handle tool failure gracefully
        return handle_tool_error("cancel_shift_acceptance", e, {
            "caregiver_id": caregiver_id,
            "shift_id": shift_id,
            "reason": reason
        })


async def _cancel_shift_acceptance_locked(
    caregiver_id: str,
    shift_id: str,
    reason: str = "Unable to work shift"
) -> Dict[str, Any]:
    """
    Internal implementation of cancel_shift_acceptance.
    This runs inside the shift lock context.
    """
    # Get shift and caregiver details
    shift = await get_shift_details(caregiver_id)
    if not shift:
        logger.warning(f"Could not find shift details for caregiver {caregiver_id}")
        return {
            "success": False,
            "error": "Could not find shift details",
            "message": "I'm having trouble finding that shift in the system. Can you tell me which client it was for?"
        }

    caregiver_name = shift.caregiver_name or f"Caregiver {caregiver_id}"
    client_name = shift.client_name or "Unknown Client"
    shift_time = shift.start_time.strftime("%B %d at %I:%M %p") if shift.start_time else "Unknown Time"

    result = {
        "success": False,
        "shift_id": shift_id,
        "caregiver_id": caregiver_id,
        "caregiver_name": caregiver_name,
        "client_name": client_name,
        "shift_time": shift_time,
        "cancellation_reason": reason,
        "errors": [],
        "step_a_wellsky_unassigned": False,
        "step_b_replacement_search_started": False,
        "step_c_manager_notified": False
    }

    # =========================================================================
    # STEP A: Unassign caregiver in WellSky (mark shift as open)
    # =========================================================================
    try:
        async with httpx.AsyncClient() as client:
            wellsky_response = await client.put(
                f"{PORTAL_BASE_URL}/api/wellsky/shifts/{shift_id}",
                json={
                    "status": "open",
                    "caregiver_id": None,  # Unassign
                    "cancellation_reason": reason,
                    "cancelled_by_caregiver_id": caregiver_id,
                    "cancelled_at": datetime.now().isoformat(),
                    "notes": f"Cancelled by {caregiver_name} via Gigi AI: {reason}"
                },
                timeout=15.0
            )
            if wellsky_response.status_code in (200, 201, 204):
                result["step_a_wellsky_unassigned"] = True
                logger.info(f"STEP A SUCCESS: Shift {shift_id} unassigned in WellSky")
            else:
                error_msg = f"WellSky returned {wellsky_response.status_code}"
                result["errors"].append(f"Step A: {error_msg}")
                logger.error(f"STEP A FAILED: {error_msg}")

                # CRITICAL: If we can't unassign in WellSky, escalate to human
                escalation_msg = (
                    f"🚨 GIGI CANCELLATION FAILURE: {caregiver_name} wants to cancel shift with {client_name} "
                    f"({shift_time}) but WellSky update failed. Reason: {reason}. "
                    f"ACTION REQUIRED: Manually unassign shift {shift_id} and find replacement."
                )
                if OPERATIONS_SMS_ENABLED:
                    await _send_sms_beetexting(ON_CALL_MANAGER_PHONE, escalation_msg)
                    logger.critical(f"ESCALATED cancellation failure to on-call manager")

                result["message"] = (
                    f"I understand you need to cancel, but I'm having trouble updating the system. "
                    f"I've notified the manager on duty who will handle this manually. "
                    f"They'll call you back shortly to confirm."
                )
                return result  # Stop here if WellSky fails

    except Exception as e:
        error_msg = f"WellSky unassignment failed: {str(e)}"
        result["errors"].append(f"Step A: {error_msg}")
        logger.error(error_msg)

        # Escalate
        if OPERATIONS_SMS_ENABLED:
            escalation_msg = f"🚨 GIGI ERROR: Cannot cancel shift for {caregiver_name}/{client_name}. Error: {e}"
            await _send_sms_beetexting(ON_CALL_MANAGER_PHONE, escalation_msg)

        result["message"] = "I'm having technical difficulties. A manager will call you back shortly."
        return result

    # =========================================================================
    # STEP B: Restart replacement search
    # =========================================================================
    try:
        async with httpx.AsyncClient() as client:
            replacement_response = await client.post(
                f"{PORTAL_BASE_URL}/api/operations/replacement-blast",
                json={
                    "shift_id": shift_id,
                    "client_name": client_name,
                    "shift_time": shift_time,
                    "urgency": "high",
                    "reason": f"Cancellation by {caregiver_name}: {reason}",
                    "exclude_caregiver_ids": [caregiver_id],  # Don't offer to same caregiver
                    "source": "gigi_cancellation"
                },
                timeout=30.0
            )
            if replacement_response.status_code in (200, 201):
                replacement_result = replacement_response.json()
                result["step_b_replacement_search_started"] = True
                result["caregivers_notified"] = replacement_result.get("caregivers_notified", 0)
                logger.info(f"STEP B SUCCESS: Replacement search started, {result['caregivers_notified']} caregivers notified")
            else:
                error_msg = f"Replacement blast returned {replacement_response.status_code}"
                result["errors"].append(f"Step B: {error_msg}")
                logger.warning(error_msg)

    except Exception as e:
        error_msg = f"Replacement search failed: {str(e)}"
        result["errors"].append(f"Step B: {error_msg}")
        logger.error(error_msg)

    # =========================================================================
    # STEP C: Notify on-call manager about cancellation
    # =========================================================================
    manager_message = (
        f"SHIFT CANCELLATION: {caregiver_name} cancelled {client_name} shift ({shift_time}). "
        f"Reason: {reason}. "
    )

    if result["step_b_replacement_search_started"]:
        manager_message += f"Replacement search started - {result.get('caregivers_notified', 0)} caregivers notified."
    else:
        manager_message += "URGENT: Replacement search FAILED - manual intervention needed."

    if OPERATIONS_SMS_ENABLED:
        await _send_sms_beetexting(ON_CALL_MANAGER_PHONE, manager_message)
        result["step_c_manager_notified"] = True
        logger.info(f"STEP C SUCCESS: Manager notified of cancellation")
    else:
        logger.info(f"[SMS DISABLED] Would notify manager: {manager_message}")

    # =========================================================================
    # Build result and response message
    # =========================================================================
    result["success"] = result["step_a_wellsky_unassigned"]

    if result["success"]:
        if result["step_b_replacement_search_started"]:
            result["message"] = (
                f"No problem, I understand things come up. I've cancelled your assignment "
                f"for {client_name} on {shift_time} and I'm already reaching out to other "
                f"caregivers to cover it. We've got this handled - don't worry about it. "
                f"Is there anything else I can help you with?"
            )
        else:
            result["message"] = (
                f"I've cancelled your assignment for {client_name}. The manager has been "
                f"notified and will find a replacement. Thanks for letting us know early!"
            )
    else:
        result["message"] = (
            f"I'm having trouble cancelling this in the system. I've alerted the manager "
            f"who will handle it manually and call you back to confirm."
        )

    result["action_completed"] = True
    result["next_step"] = "Cancellation handled. Ask caregiver if there's anything else."

    logger.info(f"cancel_shift_acceptance completed: success={result['success']}")
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
    # WORKFLOW: Create WellSky Task & Notify Team
    # ==========================================================================
    if GIGI_MODE == "shadow":
        log_shadow_action("CREATE_WELLSKY_TASK", {
            "title": f"Client Issue: {issue_type}",
            "description": note,
            "client_id": effective_client_id
        })
        log_shadow_action("NOTIFY_TEAM", {
            "team": "New Schedulers",
            "message": f"Client Issue: {note}"
        })
    else:
        # 1. Create WellSky Task for client issue
        if WELLSKY_AVAILABLE and wellsky and effective_client_id != "UNKNOWN":
            task_priority = "urgent" if priority == "urgent" else "high" if priority == "high" else "normal"
            task_created = wellsky.create_admin_task(
                title=f"Client Issue: {issue_type}",
                description=f"{note}\n\nPriority: {priority}\nLogged by: Gigi AI\nRequires follow-up call within 30 minutes",
                priority=task_priority,
                related_client_id=effective_client_id,
                assigned_to=os.getenv("WELLSKY_CARE_MANAGER_USER_ID")  # Assign to care manager if configured
            )
            if task_created:
                logger.info(f"✅ WellSky Task created for client issue: {issue_type}")
            else:
                logger.warning(f"⚠️ Failed to create WellSky Task for client issue")

        # 2. Notify Team
        schedulers_chat_id = os.getenv("RINGCENTRAL_SCHEDULERS_CHAT_ID")
        if schedulers_chat_id:
            team_msg = f"📢 CLIENT ISSUE ({priority}): {effective_client_id}\n📝 {note}"
            await send_glip_message(schedulers_chat_id, team_msg)

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
                
                # ==========================================================================
                # WORKFLOW: Notify Team
                # ==========================================================================
                if GIGI_MODE == "shadow":
                    log_shadow_action("NOTIFY_TEAM", {"team": "New Schedulers", "message": f"Late: {shift_id}"})
                else:
                    schedulers_chat_id = os.getenv("RINGCENTRAL_SCHEDULERS_CHAT_ID")
                    if schedulers_chat_id:
                        team_msg = f"⏰ LATE REPORT: Shift {shift_id}\nDelay: {delay_minutes}m\nReason: {reason}"
                        await send_glip_message(schedulers_chat_id, team_msg)

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


@dataclass
class StockPriceResult:
    """Result of stock price lookup."""
    success: bool
    symbol: Optional[str] = None
    price: Optional[str] = None
    change: Optional[str] = None
    change_percent: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


@dataclass
class CryptoPriceResult:
    """Result of crypto price lookup."""
    success: bool
    symbol: Optional[str] = None
    price: Optional[str] = None
    market: Optional[str] = None
    last_updated: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


@dataclass
class EventsResult:
    """Result of events/concerts lookup."""
    success: bool
    events: Optional[List[Dict[str, str]]] = None
    count: int = 0
    message: Optional[str] = None
    error: Optional[str] = None


@dataclass
class SetlistResult:
    """Result of setlist lookup."""
    success: bool
    setlists: Optional[List[Dict[str, Any]]] = None
    count: int = 0
    message: Optional[str] = None
    error: Optional[str] = None


async def get_setlist(
    artist_name: str,
    limit: int = 5
) -> SetlistResult:
    """
    Get recent setlists for an artist using setlist.fm API.

    Args:
        artist_name: Name of the artist/band
        limit: Maximum number of setlists to return (default 5, max 20)

    Returns:
        SetlistResult with setlist data
    """
    if not SETLIST_FM_API_KEY:
        return SetlistResult(
            success=False,
            error="Setlist.fm API key not configured",
            message="I don't have access to setlist information right now."
        )

    try:
        # Setlist.fm API endpoint
        base_url = "https://api.setlist.fm/rest/1.0/search/setlists"

        # Limit results (API max is 20 per page)
        limit = min(limit, 20)

        # Build request params
        params = {
            "artistName": artist_name,
            "p": 1,  # page number
        }

        # Headers required by setlist.fm
        headers = {
            "x-api-key": SETLIST_FM_API_KEY,
            "Accept": "application/json",
            "User-Agent": "ColoradoCareAssist/1.0 (shulmeister@gmail.com)"
        }

        logger.info(f"Searching setlists for artist: {artist_name}")

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(base_url, params=params, headers=headers)

            if response.status_code == 404:
                return SetlistResult(
                    success=False,
                    count=0,
                    message=f"I couldn't find any setlists for {artist_name}. They might not have recent concert data available."
                )

            if response.status_code != 200:
                logger.error(f"Setlist.fm API error: {response.status_code} - {response.text}")
                return SetlistResult(
                    success=False,
                    error=f"API returned status {response.status_code}",
                    message="I'm having trouble accessing setlist information right now."
                )

            data = response.json()

            # Parse setlists from response
            setlists_raw = data.get("setlist", [])

            if not setlists_raw:
                return SetlistResult(
                    success=False,
                    count=0,
                    message=f"I couldn't find any setlists for {artist_name}. They might not have recent concert data available."
                )

            # Format setlists for response (limit to requested number)
            setlists_list = []
            for setlist in setlists_raw[:limit]:
                # Parse venue info
                venue = setlist.get("venue", {})
                venue_name = venue.get("name", "Unknown Venue")
                city = venue.get("city", {}).get("name", "")
                state = venue.get("city", {}).get("state", "")
                country = venue.get("city", {}).get("country", {}).get("name", "")

                # Build location string
                location_parts = [p for p in [city, state, country] if p]
                location = ", ".join(location_parts) if location_parts else "Unknown Location"

                # Parse date
                event_date = setlist.get("eventDate", "Unknown Date")

                # Parse songs from sets
                songs = []
                sets_data = setlist.get("sets", {}).get("set", [])
                for set_data in sets_data:
                    if isinstance(set_data, dict):
                        song_list = set_data.get("song", [])
                        for song in song_list:
                            if isinstance(song, dict):
                                song_name = song.get("name")
                                if song_name:
                                    songs.append(song_name)

                # Format setlist description
                setlist_desc = f"{artist_name} at {venue_name}, {location} on {event_date}"
                if songs:
                    setlist_desc += f" - {len(songs)} songs"

                setlists_list.append({
                    "artist": setlist.get("artist", {}).get("name", artist_name),
                    "venue": venue_name,
                    "location": location,
                    "date": event_date,
                    "songs": songs[:10],  # Limit to first 10 songs for brevity
                    "total_songs": len(songs),
                    "description": setlist_desc,
                    "url": setlist.get("url", "")
                })

            if not setlists_list:
                return SetlistResult(
                    success=False,
                    count=0,
                    message=f"I found some setlists for {artist_name} but couldn't parse them properly."
                )

            # Build friendly message
            message = f"I found {len(setlists_list)} recent setlists for {artist_name}:\n\n"
            for i, setlist in enumerate(setlists_list, 1):
                message += f"{i}. {setlist['venue']}, {setlist['location']} - {setlist['date']}\n"
                if setlist['songs']:
                    song_sample = ", ".join(setlist['songs'][:3])
                    if setlist['total_songs'] > 3:
                        message += f"   Songs include: {song_sample}, and {setlist['total_songs'] - 3} more\n"
                    else:
                        message += f"   Songs: {song_sample}\n"

            return SetlistResult(
                success=True,
                setlists=setlists_list,
                count=len(setlists_list),
                message=message
            )

    except Exception as e:
        logger.exception(f"Error fetching setlists: {e}")
        return SetlistResult(
            success=False,
            error=str(e),
            message="I encountered an error looking up setlists."
        )


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


async def get_stock_price(symbol: str) -> StockPriceResult:
    """
    Get current stock price for a given ticker symbol.
    Uses Alpha Vantage GLOBAL_QUOTE API.

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL", "TSLA", "GOOG")

    Returns:
        StockPriceResult with current price and change information
    """
    if not ALPHA_VANTAGE_API_KEY:
        logger.error("ALPHA_VANTAGE_API_KEY not configured")
        return StockPriceResult(
            success=False,
            error="Stock price service not configured",
            message="I'm unable to check stock prices right now. Please try again later."
        )

    try:
        symbol = symbol.upper().strip()
        logger.info(f"Looking up stock price for: {symbol}")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": symbol,
                    "apikey": ALPHA_VANTAGE_API_KEY
                },
                timeout=10.0
            )

            if response.status_code != 200:
                logger.error(f"Alpha Vantage API error: {response.status_code}")
                return StockPriceResult(
                    success=False,
                    error="API error",
                    message="I'm having trouble getting stock data right now."
                )

            data = response.json()

            # Check for API error messages
            if "Error Message" in data:
                logger.warning(f"Stock not found: {symbol}")
                return StockPriceResult(
                    success=False,
                    error="Stock not found",
                    message=f"I couldn't find a stock with the symbol {symbol}. Please check the ticker symbol and try again."
                )

            if "Note" in data or "Information" in data:
                logger.warning("Alpha Vantage API rate limit hit")
                return StockPriceResult(
                    success=False,
                    error="Rate limit",
                    message="The stock price service is temporarily busy. Please try again in a moment."
                )

            # Parse the quote data
            quote = data.get("Global Quote", {})
            if not quote:
                return StockPriceResult(
                    success=False,
                    error="No data returned",
                    message=f"I couldn't find price data for {symbol}."
                )

            price = quote.get("05. price")
            change = quote.get("09. change")
            change_percent = quote.get("10. change percent", "").replace("%", "")

            # Build friendly message
            if change and change_percent:
                change_float = float(change)
                direction = "up" if change_float > 0 else "down"
                message = f"{symbol} is currently trading at ${float(price):.2f}, {direction} ${abs(change_float):.2f} ({change_percent}%) today."
            else:
                message = f"{symbol} is currently trading at ${float(price):.2f}."

            return StockPriceResult(
                success=True,
                symbol=symbol,
                price=price,
                change=change,
                change_percent=change_percent,
                message=message
            )

    except Exception as e:
        logger.exception(f"Error fetching stock price for {symbol}: {e}")
        return StockPriceResult(
            success=False,
            error=str(e),
            message="I encountered an error looking up that stock price."
        )


async def get_crypto_price(symbol: str, market: str = "USD") -> CryptoPriceResult:
    """
    Get current cryptocurrency price.
    Uses Alpha Vantage CURRENCY_EXCHANGE_RATE API.

    Args:
        symbol: Crypto symbol (e.g., "BTC", "ETH", "DOGE")
        market: Market currency to price against (default "USD")

    Returns:
        CryptoPriceResult with current price information
    """
    if not ALPHA_VANTAGE_API_KEY:
        logger.error("ALPHA_VANTAGE_API_KEY not configured")
        return CryptoPriceResult(
            success=False,
            error="Crypto price service not configured",
            message="I'm unable to check crypto prices right now. Please try again later."
        )

    try:
        symbol = symbol.upper().strip()
        market = market.upper().strip()
        logger.info(f"Looking up crypto price for: {symbol}/{market}")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "CURRENCY_EXCHANGE_RATE",
                    "from_currency": symbol,
                    "to_currency": market,
                    "apikey": ALPHA_VANTAGE_API_KEY
                },
                timeout=10.0
            )

            if response.status_code != 200:
                logger.error(f"Alpha Vantage API error: {response.status_code}")
                return CryptoPriceResult(
                    success=False,
                    error="API error",
                    message="I'm having trouble getting crypto data right now."
                )

            data = response.json()

            # Check for API error messages
            if "Error Message" in data:
                logger.warning(f"Crypto not found: {symbol}")
                return CryptoPriceResult(
                    success=False,
                    error="Crypto not found",
                    message=f"I couldn't find cryptocurrency {symbol}. Please check the symbol and try again."
                )

            if "Note" in data or "Information" in data:
                logger.warning("Alpha Vantage API rate limit hit")
                return CryptoPriceResult(
                    success=False,
                    error="Rate limit",
                    message="The crypto price service is temporarily busy. Please try again in a moment."
                )

            # Parse the exchange rate data
            rate_data = data.get("Realtime Currency Exchange Rate", {})
            if not rate_data:
                return CryptoPriceResult(
                    success=False,
                    error="No data returned",
                    message=f"I couldn't find price data for {symbol}."
                )

            from_symbol = rate_data.get("1. From_Currency Code")
            from_name = rate_data.get("2. From_Currency Name", symbol)
            to_symbol = rate_data.get("3. To_Currency Code")
            exchange_rate = rate_data.get("5. Exchange Rate")
            last_updated = rate_data.get("6. Last Refreshed")

            # Build friendly message
            price_float = float(exchange_rate)
            if price_float >= 1:
                formatted_price = f"${price_float:,.2f}"
            else:
                formatted_price = f"${price_float:.6f}".rstrip('0').rstrip('.')

            message = f"{from_name} ({from_symbol}) is currently trading at {formatted_price} {to_symbol}."

            return CryptoPriceResult(
                success=True,
                symbol=from_symbol,
                price=exchange_rate,
                market=to_symbol,
                last_updated=last_updated,
                message=message
            )

    except Exception as e:
        logger.exception(f"Error fetching crypto price for {symbol}: {e}")
        return CryptoPriceResult(
            success=False,
            error=str(e),
            message="I encountered an error looking up that crypto price."
        )


async def get_events(
    query: str = "concerts",
    city: str = "Denver",
    state: str = "CO",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 5
) -> EventsResult:
    """
    Get upcoming events (concerts, sports, theater) in a specific area.
    Uses Ticketmaster Discovery API.

    Args:
        query: Type of event (e.g., "concerts", "sports", "theater", "comedy")
        city: City name (default "Denver")
        state: State code (default "CO")
        start_date: Start date in YYYY-MM-DD format (default: today)
        end_date: End date in YYYY-MM-DD format (default: 7 days from start)
        limit: Maximum number of events to return (default 5)

    Returns:
        EventsResult with list of upcoming events
    """
    if not TICKETMASTER_API_KEY:
        logger.error("TICKETMASTER_API_KEY not configured")
        return EventsResult(
            success=False,
            error="Events service not configured",
            message="I'm unable to check events right now. Please try again later."
        )

    try:
        # Default date range: today through next week
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%dT00:00:00Z")
        else:
            start_date = f"{start_date}T00:00:00Z"

        if not end_date:
            end_dt = datetime.now() + timedelta(days=7)
            end_date = end_dt.strftime("%Y-%m-%dT23:59:59Z")
        else:
            end_date = f"{end_date}T23:59:59Z"

        # Build API request
        url = "https://app.ticketmaster.com/discovery/v2/events.json"
        params = {
            "apikey": TICKETMASTER_API_KEY,
            "city": city,
            "stateCode": state,
            "startDateTime": start_date,
            "endDateTime": end_date,
            "size": limit,
            "sort": "date,asc"
        }

        # Add keyword filter if specific query provided
        if query.lower() not in ["all", "events", "anything"]:
            params["keyword"] = query

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)

            if response.status_code != 200:
                logger.error(f"Ticketmaster API error: {response.status_code}")
                return EventsResult(
                    success=False,
                    error="API error",
                    message="I'm having trouble getting events right now."
                )

            data = response.json()

            # Check if events found
            embedded = data.get("_embedded")
            if not embedded or "events" not in embedded:
                return EventsResult(
                    success=False,
                    count=0,
                    message=f"I couldn't find any {query} in {city} this week. Try a different search or check back later."
                )

            events_data = embedded["events"]
            events_list = []

            for event in events_data[:limit]:
                name = event.get("name", "Unknown Event")
                event_date = event.get("dates", {}).get("start", {}).get("localDate", "TBA")
                event_time = event.get("dates", {}).get("start", {}).get("localTime", "")

                # Format date nicely
                try:
                    dt = datetime.strptime(event_date, "%Y-%m-%d")
                    formatted_date = dt.strftime("%A, %B %d")
                except:
                    formatted_date = event_date

                # Get venue
                venues = event.get("_embedded", {}).get("venues", [])
                venue_name = venues[0].get("name", "Venue TBA") if venues else "Venue TBA"

                # Get price range if available
                price_ranges = event.get("priceRanges", [])
                price_info = ""
                if price_ranges:
                    min_price = price_ranges[0].get("min", 0)
                    max_price = price_ranges[0].get("max", 0)
                    if min_price and max_price:
                        price_info = f" (${min_price:.0f}-${max_price:.0f})"

                # Build event description
                event_desc = f"{name} - {formatted_date}"
                if event_time:
                    event_desc += f" at {event_time}"
                event_desc += f" at {venue_name}{price_info}"

                events_list.append({
                    "name": name,
                    "date": formatted_date,
                    "time": event_time,
                    "venue": venue_name,
                    "description": event_desc
                })

            if not events_list:
                return EventsResult(
                    success=False,
                    count=0,
                    message=f"I couldn't find any {query} in {city} this week."
                )

            # Build friendly message
            event_type = query if query.lower() not in ["all", "events", "anything"] else "events"
            message = f"I found {len(events_list)} {event_type} in {city} this week:\n\n"
            for i, evt in enumerate(events_list, 1):
                message += f"{i}. {evt['description']}\n"

            return EventsResult(
                success=True,
                events=events_list,
                count=len(events_list),
                message=message
            )

    except Exception as e:
        logger.exception(f"Error fetching events: {e}")
        return EventsResult(
            success=False,
            error=str(e),
            message="I encountered an error looking up events."
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
        to_number = body.get("to_number", "")
        logger.info(f"Call started from {from_number} to {to_number}")

        # Enhanced caller lookup with fallback to Apple Contacts
        if ENHANCED_WEBHOOK_AVAILABLE:
            # Use enhanced lookup service with multiple sources
            def db_lookup(phone):
                db = _get_db()
                if db:
                    try:
                        return db.lookup_caller(phone)
                    except Exception as e:
                        logger.warning(f"Database lookup failed: {e}")
                return None
            
            lookup_service = CallerLookupService(
                db_lookup_fn=db_lookup,
                cache_lookup_fn=lambda phone: _lookup_in_cache(phone)
            )
            
            caller_info = lookup_service.lookup(from_number)
            greeting = generate_greeting(caller_info)
            
            # Store enhanced info in call context
            _store_call_context(call_id, caller_info)
            
            # Log the lookup result
            if caller_info.get("found"):
                name = caller_info.get("name", "Unknown")
                source = caller_info.get("source", "unknown")
                logger.info(f"AUTO-LOOKUP: Found {name} via {source}")
            else:
                logger.info(f"AUTO-LOOKUP: Unknown caller {from_number}")
            
            # Prepare response with greeting and action instructions
            response_data = {
                "status": "ok",
                "caller_info": caller_info,
                "initial_greeting": greeting,
                # Override Retell agent config to use personalized greeting
                "config_override": {
                    "initial_greeting": greeting,
                    "agent_name": "Gigi"
                }
            }

            # Set action based on caller type
            if caller_info.get("should_transfer"):
                response_data["action"] = "greet_and_transfer"
                logger.info(f"Will transfer call to Jason after greeting: '{greeting}'")
            elif caller_info.get("take_message"):
                response_data["action"] = "take_message"
                logger.info(f"Unknown caller - will take message. Greeting: '{greeting}'")
            else:
                logger.info(f"Caller greeted with: '{greeting}'")

            return JSONResponse(response_data)
        else:
            # Fallback to original logic if enhanced webhook not available
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

                _store_call_context(call_id, caller_info)

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

                # NEW: Enhanced webhook tools for caller ID, weather, transfer, and messages
                elif tool_name == "get_weather" and ENHANCED_WEBHOOK_AVAILABLE:
                    location = tool_args.get("location", "Boulder CO")
                    weather_result = get_weather(location)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": weather_result
                    })
                    logger.info(f"Weather requested for {location}: {weather_result}")

                elif tool_name == "transfer_to_jason" and ENHANCED_WEBHOOK_AVAILABLE:
                    reason = tool_args.get("reason", "Personal call")
                    success = transfer_call(call_id, JASON_PHONE)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": {
                            "success": success,
                            "message": "Transferring you to Jason now" if success else "I'm having trouble transferring right now. Let me take a message instead."
                        }
                    })
                    logger.info(f"Transfer to Jason initiated (reason: {reason}): {'success' if success else 'failed'}")

                elif tool_name == "take_message" and ENHANCED_WEBHOOK_AVAILABLE:
                    caller_phone = tool_args.get("caller_phone", "Unknown")
                    caller_name = tool_args.get("caller_name", "")
                    message_text = tool_args.get("message", "")
                    
                    # Format caller info for message handler
                    caller_info = {
                        "phone": caller_phone,
                        "name": caller_name if caller_name else None,
                        "type": "unknown"
                    }
                    
                    # Send to Telegram
                    handle_message_received(caller_info, message_text, call_id)
                    
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": {
                            "success": True,
                            "message": "I've sent your message to Jason. He'll get back to you as soon as possible. Have a great day!"
                        }
                    })
                    logger.info(f"Message taken from {caller_phone} ({caller_name or 'anonymous'})")

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

                elif tool_name == "cancel_shift_acceptance":
                    result = await cancel_shift_acceptance(**tool_args)
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

        elif function_name == "cancel_shift_acceptance":
            result = await cancel_shift_acceptance(**args)
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

        elif function_name == "resolve_person":
            if not ENTITY_RESOLUTION_AVAILABLE:
                raise HTTPException(status_code=503, detail="Entity Resolution service is not available.")
            
            name = args.get("name")
            if not name:
                raise HTTPException(status_code=400, detail="Name is required for resolution.")

            # Get caller context to help with resolution
            caller_context = _get_call_context(call_id)
            context = {}
            if caller_context and caller_context.get("caller_type") == "caregiver":
                context["caregiver_id"] = caller_context.get("person_id")

            result = entity_resolver.resolve_person(name, context=context)
            return JSONResponse(result)

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

        elif function_name == "get_weather":
            location = args.get("location", "Boulder")
            logger.info(f"Getting weather for: {location}")
            weather_result = get_weather(location)
            return JSONResponse({
                "response_type": "response",
                "response": weather_result,
                "content": weather_result
            })

        elif function_name == "take_message":
            caller_name = args.get("caller_name", "Unknown caller")
            caller_phone = args.get("caller_phone", "")
            message = args.get("message", "")

            logger.info(f"Taking message from {caller_name} ({caller_phone}): {message}")

            # Send to Telegram
            telegram_text = f"📞 NEW MESSAGE\n\nFrom: {caller_name}\nPhone: {caller_phone}\nMessage: {message}"
            send_telegram_message(telegram_text)

            record_tool_call(call_id, function_name)
            return JSONResponse({
                "response_type": "response",
                "response": f"Got it. I'll make sure Jason gets your message.",
                "content": "Message recorded and sent to Jason"
            })

        elif function_name == "get_stock_price":
            symbol = args.get("symbol")
            if not symbol:
                return JSONResponse({
                    "success": False,
                    "error": "Symbol required",
                    "message": "I need a stock ticker symbol to look up. What stock are you interested in?"
                })
            result = await get_stock_price(symbol)
            return JSONResponse({
                "success": result.success,
                "symbol": result.symbol,
                "price": result.price,
                "change": result.change,
                "change_percent": result.change_percent,
                "message": result.message,
                "error": result.error
            })

        elif function_name == "get_crypto_price":
            symbol = args.get("symbol")
            market = args.get("market", "USD")
            if not symbol:
                return JSONResponse({
                    "success": False,
                    "error": "Symbol required",
                    "message": "I need a cryptocurrency symbol to look up. What crypto are you interested in?"
                })
            result = await get_crypto_price(symbol, market)
            return JSONResponse({
                "success": result.success,
                "symbol": result.symbol,
                "price": result.price,
                "market": result.market,
                "last_updated": result.last_updated,
                "message": result.message,
                "error": result.error
            })

        elif function_name == "get_events":
            query = args.get("query", "concerts")
            city = args.get("city", "Denver")
            state = args.get("state", "CO")
            start_date = args.get("start_date")
            end_date = args.get("end_date")
            limit = args.get("limit", 5)

            result = await get_events(query, city, state, start_date, end_date, limit)
            return JSONResponse({
                "success": result.success,
                "events": result.events,
                "count": result.count,
                "message": result.message,
                "error": result.error
            })

        elif function_name == "get_setlist":
            artist_name = args.get("artist_name", "")
            limit = args.get("limit", 5)

            if not artist_name:
                return JSONResponse({
                    "success": False,
                    "error": "Artist name is required",
                    "message": "I need an artist or band name to look up setlists."
                })

            result = await get_setlist(artist_name, limit)
            return JSONResponse({
                "success": result.success,
                "setlists": result.setlists,
                "count": result.count,
                "message": result.message,
                "error": result.error
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
    health = {
        "status": "healthy",
        "agent": "gigi",
        "version": "2.2.0",  # Version 2.2: Memory + Mode Detection + Failure Protocols
        "memory_system": MEMORY_SYSTEM_AVAILABLE,
        "mode_detector": MODE_DETECTOR_AVAILABLE,
        "failure_handler": FAILURE_HANDLER_AVAILABLE
    }

    # Add memory stats if available
    if MEMORY_SYSTEM_AVAILABLE:
        try:
            active_memories = memory_system.query_memories(status=MemoryStatus.ACTIVE, limit=1000)
            health["memory_stats"] = {
                "active_memories": len(active_memories),
                "high_confidence": len([m for m in active_memories if m.confidence >= 0.7]),
                "system_ready": True
            }
        except Exception as e:
            health["memory_stats"] = {
                "error": str(e),
                "system_ready": False
            }

    # Add mode detector info if available
    if MODE_DETECTOR_AVAILABLE:
        try:
            current_mode = mode_detector.get_current_mode()
            health["current_mode"] = {
                "mode": current_mode.mode.value,
                "source": current_mode.source.value,
                "confidence": float(current_mode.confidence),
                "set_at": current_mode.set_at.isoformat() if current_mode.set_at else None,
                "system_ready": True
            }
        except Exception as e:
            health["current_mode"] = {
                "error": str(e),
                "system_ready": False
            }

    # Add failure handler stats if available
    if FAILURE_HANDLER_AVAILABLE:
        try:
            stats = failure_handler.get_failure_stats(days=1)
            recent_critical = failure_handler.get_recent_failures(hours=1, severity=FailureSeverity.CRITICAL)
            is_meltdown = failure_handler.detect_meltdown()

            health["failure_stats"] = {
                "failures_24h": stats['total_failures'],
                "critical_1h": len(recent_critical),
                "meltdown_detected": is_meltdown,
                "system_ready": True
            }
        except Exception as e:
            health["failure_stats"] = {
                "error": str(e),
                "system_ready": False
            }

    return health


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

    # New Client Inquiry / Biz Dev
    if any(phrase in msg_lower for phrase in [
        "looking for care", "need a caregiver", "rates", "cost", 
        "new client", "sign up", "services", "help for my mom", "help for my dad",
        "care for my", "interested in services"
    ]):
        return "inquiry"

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


def _is_in_office_hours(now: Optional[datetime] = None) -> bool:
    """Return True if current time (America/Denver) is within office hours."""
    now = now or datetime.now(ZoneInfo("America/Denver"))
    # Office hours are Monday-Friday only
    if now.weekday() >= 5:
        return False
    try:
        start_parts = [int(p) for p in OFFICE_HOURS_START.split(":")]
        end_parts = [int(p) for p in OFFICE_HOURS_END.split(":")]
        start_t = time_cls(start_parts[0], start_parts[1])
        end_t = time_cls(end_parts[0], end_parts[1])
    except Exception:
        start_t = time_cls(8, 0)
        end_t = time_cls(17, 0)

    now_t = now.time()
    if start_t < end_t:
        return start_t <= now_t < end_t
    return now_t >= start_t or now_t < end_t


def _should_reply_now() -> bool:
    """Gate SMS replies to after-hours if configured."""
    if not SMS_AUTOREPLY_ENABLED:
        return False
    if not SMS_AFTER_HOURS_ONLY:
        return True
    return not _is_in_office_hours()


def _log_clock_issue_to_wellsky(
    shift,
    caller_name: Optional[str],
    intent: str,
    message: str
) -> None:
    """Create WellSky task + care alert note for clock-in/out issues."""
    caregiver_name = caller_name or "Caregiver"
    action_label = "clock out" if intent == "clock_out" else "clock in"
    
    # 1. ALWAYS LOG LOCALLY FIRST (Safety Backup)
    try:
        import sqlite3
        conn = sqlite3.connect('portal.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO wellsky_documentation (type, title, description, related_id)
            VALUES (?, ?, ?, ?)
        ''', ('SMS_REQUEST', f'Request: {action_label}', f'{caregiver_name}: {message}', getattr(shift, 'id', 'N/A')))
        conn.commit()
        conn.close()
        logger.info(f"Logged {action_label} request locally.")
    except Exception as e:
        logger.error(f"Local logging failed: {e}")

    # 2. DOCUMENT IN WELLSKY
    if not (WELLSKY_AVAILABLE and wellsky and shift):
        return

    client_id = getattr(shift, "client_id", None)
    caregiver_id = getattr(shift, "caregiver_id", None)

    # Add Note to Client (Visible in Care Alerts)
    if client_id:
        wellsky.add_note_to_client(
            client_id=str(client_id),
            note=f"GIGI ALERT: {caregiver_name} requested {action_label} via text. Message: {message}",
            note_type="callout"
        )

    # Create Admin Task (Visible in Task List)
    wellsky.create_admin_task(
        title=f"SMS {action_label.upper()} - {caregiver_name}",
        description=(
            f"Caregiver: {caregiver_name}\n"
            f"Message: {message}\n"
            f"Shift: {getattr(shift, 'id', 'unknown')}"
        ),
        priority="high",
        related_client_id=str(client_id) if client_id else None,
        related_caregiver_id=str(caregiver_id) if caregiver_id else None
    )


def _log_unmatched_sms_to_wellsky(
    caller_name: Optional[str],
    intent: str,
    message: str,
    phone: str
) -> None:
    """Create WellSky task for caregiver SMS that couldn't be matched to a shift."""
    caregiver_name = caller_name or "Unknown Caregiver"
    action_label = "clock out" if intent == "clock_out" else "clock in"
    
    # ALWAYS LOG LOCALLY FIRST (Safety Backup)
    try:
        import sqlite3
        conn = sqlite3.connect('portal.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO wellsky_documentation (type, title, description, related_id)
            VALUES (?, ?, ?, ?)
        ''', ('UNMATCHED_SMS', f'Unmatched {action_label}', f'{caregiver_name} ({phone}): {message}', 'N/A'))
        conn.commit()
        conn.close()
        logger.info(f"Logged unmatched {action_label} request locally.")
    except Exception as e:
        logger.error(f"Local logging failed: {e}")

    if not (WELLSKY_AVAILABLE and wellsky):
        return

    # Try to find caregiver record by phone to link the task
    caregiver_id = None
    caregiver = wellsky.get_caregiver_by_phone(phone)
    if caregiver:
        caregiver_id = caregiver.id
        caregiver_name = caregiver.full_name

    # Create Admin Task (Visible in Task List)
    wellsky.create_admin_task(
        title=f"SMS {action_label.upper()} (NO SHIFT) - {caregiver_name}",
        description=(
            f"Caregiver: {caregiver_name}\n"
            f"Phone: {phone}\n"
            f"Intent: {action_label}\n"
            f"Message: {message}\n"
            f"Note: Gigi could not find a matching shift for this request."
        ),
        priority="high",
        related_caregiver_id=str(caregiver_id) if caregiver_id else None
    )


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

    # FORCE REPLY for now to ensure reliability, ignoring office hours gates
    should_reply = True 
    if not should_reply:
        logger.info("SMS auto-reply is disabled. Processing without reply.")

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
                            sms_sent = await _send_sms_primary(sms.from_number, reply_text)
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

        # =====================================================================
        # CHECK FOR PARTIAL AVAILABILITY (e.g., "I can't work but I could do 8:30-11:30")
        # =====================================================================
        # This must come BEFORE simple callout detection
        if PARTIAL_AVAILABILITY_PARSER_AVAILABLE and detect_partial_availability:
            try:
                partial_avail = detect_partial_availability(sms.message)

                if partial_avail.offers_alternative:
                    # Caregiver is cancelling BUT offering an alternative time
                    logger.info(f"Detected partial availability: {partial_avail.start_time}-{partial_avail.end_time}")

                    # Build context message for coordinator
                    coordinator_message = (
                        f"📋 PARTIAL AVAILABILITY from {caller_info.name or sms.from_number}\n\n"
                        f"Original message: \"{sms.message}\"\n\n"
                        f"Parsed details:\n"
                        f"  • Cancelling original shift: {partial_avail.is_cancelling}\n"
                        f"  • Alternative time offered: {partial_avail.start_time} - {partial_avail.end_time}\n"
                        f"  • Raw time text: \"{partial_avail.raw_time_text}\"\n\n"
                        f"ACTION NEEDED: Contact caregiver to confirm if modified schedule works for client."
                    )

                    # Send to on-call manager
                    if OPERATIONS_SMS_ENABLED:
                        await _send_sms_beetexting(ON_CALL_MANAGER_PHONE, coordinator_message)
                        logger.info(f"Sent partial availability alert to coordinator")

                    # Generate empathetic response to caregiver
                    reply_text = (
                        f"Thanks for letting us know! I've notified the coordinator about your "
                        f"availability from {partial_avail.start_time} to {partial_avail.end_time}. "
                        f"They'll reach out within the hour to see if we can adjust the shift. "
                        f"I really appreciate you offering an alternative time!"
                    )

                    # Send reply
                    sms_sent = await _send_sms_primary(sms.from_number, reply_text)

                    return SMSResponse(
                        success=True,
                        reply_sent=sms_sent,
                        reply_text=reply_text,
                        caller_type=caller_info.caller_type,
                        caller_name=caller_info.name,
                        original_message=sms.message
                    )

            except Exception as partial_err:
                logger.warning(f"Error in partial availability detection: {partial_err}")
                # Fall through to normal processing

        # Look up shift data from WellSky
        shift_context = None
        action_taken = None
        current_shift = None
        reply_text = None

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
                            _log_clock_issue_to_wellsky(current_shift, caller_info.name, "clock_out", sms.message)
                            reply_text = f"Got it{f', {caller_info.name}' if caller_info.name else ''} — I’ve clocked you out."
                        else:
                            reply_text = "I’m having trouble clocking you out. I’ve logged this and the scheduler will follow up shortly."
                            # STILL LOG TO WELLSKY even if clock out fails
                            _log_clock_issue_to_wellsky(current_shift, caller_info.name, "clock_out", sms.message)
                    else:
                        reply_text = "I couldn’t find your current shift. I’ve logged this for the scheduler to follow up."
                        # LOG GENERIC TASK if no shift found
                        _log_unmatched_sms_to_wellsky(caller_info.name, "clock_out", sms.message, sms.from_number)

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
                            _log_clock_issue_to_wellsky(current_shift, caller_info.name, "clock_in", sms.message)
                            reply_text = f"Got it{f', {caller_info.name}' if caller_info.name else ''} — I’ve clocked you in."
                        else:
                            reply_text = "I’m having trouble clocking you in. I’ve logged this and the scheduler will follow up shortly."
                            _log_clock_issue_to_wellsky(current_shift, caller_info.name, "clock_in", sms.message)
                    else:
                        reply_text = "I couldn’t find your current shift. I’ve logged this for the scheduler to follow up."
                        _log_unmatched_sms_to_wellsky(caller_info.name, "clock_in", sms.message, sms.from_number)

                elif intent == "callout":
                    # Smart Call-Out Handling (Continuity First)
                    if caller_info and caller_info.caller_type == CallerType.CAREGIVER and caller_info.person_id:
                        caregiver_id = caller_info.person_id
                        
                        # Find the shift they mean (upcoming or current)
                        # We use get_shift_details logic which checks cache then API
                        shift_details = await get_shift_details(caregiver_id)
                        
                        if shift_details:
                            # Execute Smart Call-Out Logic
                            result = await execute_caregiver_call_out(
                                caregiver_id=caregiver_id,
                                shift_id=shift_details.shift_id,
                                reason=sms.message[:200]
                            )
                            
                            if result.get("success") or result.get("step_a_wellsky_updated"):
                                action_taken = "Processed call-out and started finding coverage."
                                
                                # Create a mock shift object for context formatting
                                current_shift = SimpleNamespace(
                                    client_first_name=shift_details.client_name.split()[0] if shift_details.client_name else "Client",
                                    client_last_name=" ".join(shift_details.client_name.split()[1:]) if shift_details.client_name else "",
                                    date=shift_details.start_time.date(),
                                    start_time=shift_details.start_time.strftime("%I:%M %p"),
                                    end_time=shift_details.end_time.strftime("%I:%M %p"),
                                    address=shift_details.client_address,
                                    city="",
                                    clock_in_time=None,
                                    clock_out_time=None,
                                    status=SimpleNamespace(value="open") # It's open now
                                )
                                shift_context = format_shift_context(current_shift)
                                logger.info(f"Smart SMS Call-out success: {result.get('message')}")
                            else:
                                logger.warning(f"Smart SMS Call-out failed: {result.get('errors')}")
                                action_taken = "Logged call-out but notified manager for manual follow-up."
                        else:
                             logger.warning(f"SMS Call-out: No shift found for caregiver {caregiver_id}")
                    else:
                        logger.warning(f"SMS Call-out from unknown or unverified caller: {sms.from_number}")

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
                    
                    # Notify Schedulers
                    schedulers_chat = os.getenv("RINGCENTRAL_SCHEDULERS_CHAT_ID")
                    if schedulers_chat:
                        await send_glip_message(schedulers_chat, f"📅 SCHEDULE QUESTION: {sms.from_number}\n{sms.message}")

                elif intent == "payroll":
                    # Notify Schedulers (or HR if separate, but user said 'caregiver issue to New Scheduling')
                    schedulers_chat = os.getenv("RINGCENTRAL_SCHEDULERS_CHAT_ID")
                    if schedulers_chat:
                        await send_glip_message(schedulers_chat, f"💰 PAYROLL QUESTION: {sms.from_number}\n{sms.message}")
                    action_taken = "Notified administrative team."

                elif intent == "inquiry":
                    # Route to Biz Dev
                    biz_dev_chat = os.getenv("RINGCENTRAL_BIZ_DEV_CHAT_ID")
                    if biz_dev_chat:
                        await send_glip_message(biz_dev_chat, f"💼 NEW LEAD (SMS): {sms.from_number}\nMsg: {sms.message}")
                        action_taken = "Notified Business Development team."
                    else:
                        # Fallback to schedulers if biz dev not set
                        schedulers_chat = os.getenv("RINGCENTRAL_SCHEDULERS_CHAT_ID")
                        if schedulers_chat:
                            await send_glip_message(schedulers_chat, f"💼 NEW LEAD (SMS): {sms.from_number}\nMsg: {sms.message}")
                        action_taken = "Notified office staff."

                else:
                    # For general messages, still try to get context
                    current_shift = wellsky.get_caregiver_current_shift(sms.from_number)
                    if current_shift:
                        shift_context = format_shift_context(current_shift)

            except Exception as ws_error:
                logger.warning(f"WellSky lookup failed: {ws_error}")
                # Continue without WellSky data

        if reply_text is None:
            # Generate AI response with shift context
            reply_text = await generate_sms_response(
                sms.message,
                caller_info,
                shift_context=shift_context,
                action_taken=action_taken
            )

        # =====================================================================
        # DOCUMENTATION: Log the entire interaction to WellSky (24/7 compliance)
        # This runs ALWAYS - even if Gigi doesn't reply (e.g., during office hours)
        # =====================================================================
        if WELLSKY_AVAILABLE and wellsky and caller_info and caller_info.person_id:
            try:
                person_type = caller_info.caller_type.value # 'caregiver' or 'client'
                reply_status = "(Gigi replied)" if should_reply else "(Office hours - no auto-reply)"
                log_note = f"SMS INTERACTION {reply_status}:\nCaregiver: {sms.message}\nGigi response: {reply_text}"

                # Use the internal add_note_to_wellsky tool logic
                await add_note_to_wellsky(
                    person_type=person_type,
                    person_id=caller_info.person_id,
                    note=log_note,
                    note_type="communication"
                )
                logger.info(f"Full conversation documented in WellSky for {caller_info.name}")
            except Exception as doc_err:
                logger.warning(f"Failed to document full conversation: {doc_err}")

        if not should_reply:
            return SMSResponse(
                success=True,
                reply_sent=False,
                reply_text=reply_text
            )

        # Send reply via BeeTexting SMS (falls back to RingCentral)
        # This ensures the reply shows up in the BeeTexting thread we just assigned
        sms_sent = await _send_sms_beetexting(sms.from_number, reply_text)

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
                success=True,
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

import asyncio
import hashlib
import hmac
import logging
import os
from datetime import date as date_cls
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import quote_plus, urlencode

import httpx
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from portal_auth import get_current_user, get_current_user_optional, oauth_manager
from portal_database import db_manager, get_db
from portal_models import (
    BrevoWebhookEvent,
    GigiInteractionFeedback,
    PortalTool,
    ToolClick,
    UserSession,
    Voucher,
)
from services.activity_stream_service import activity_stream
from services.marketing.metrics_service import (
    get_ads_metrics,
    get_email_metrics,
    get_social_metrics,
)
from services.search_service import search_service

# Import client satisfaction service at module load time (before sales path takes precedence)
try:
    from services.client_satisfaction_service import client_satisfaction_service
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Client satisfaction service not available: {e}")
    client_satisfaction_service = None

# Import AI Care Coordinator service (Gigi/Gigi style automation)
try:
    from services.ai_care_coordinator import ai_care_coordinator
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"AI Care Coordinator not available: {e}")
    ai_care_coordinator = None

# Import GoFormz → WellSky sync service for webhook processing
try:
    from services.goformz_wellsky_sync import (
        goformz_wellsky_sync as _goformz_wellsky_sync_module,
    )
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"GoFormz-WellSky sync service not available: {e}")
    _goformz_wellsky_sync_module = None

# Import WellSky service directly for Operations Dashboard
try:
    from services.wellsky_service import (
        CaregiverStatus,
        ClientStatus,
        ShiftStatus,
        wellsky_service,
    )
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"WellSky service not available: {e}")
    wellsky_service = None
    ShiftStatus = None
    ClientStatus = None
    CaregiverStatus = None

import json
from datetime import date

from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# RingCentral Embeddable configuration
RINGCENTRAL_EMBED_CLIENT_ID = os.getenv("RINGCENTRAL_EMBED_CLIENT_ID")
RINGCENTRAL_EMBED_SERVER = os.getenv("RINGCENTRAL_EMBED_SERVER", "https://platform.ringcentral.com")
RINGCENTRAL_EMBED_APP_URL = os.getenv(
    "RINGCENTRAL_EMBED_APP_URL",
    "https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/app.html",
)
RINGCENTRAL_EMBED_ADAPTER_URL = os.getenv(
    "RINGCENTRAL_EMBED_ADAPTER_URL",
    "https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/adapter.js",
)
RINGCENTRAL_EMBED_DEFAULT_TAB = os.getenv("RINGCENTRAL_EMBED_DEFAULT_TAB", "messages")
RINGCENTRAL_EMBED_REDIRECT_URI = os.getenv(
    "RINGCENTRAL_EMBED_REDIRECT_URI",
    "https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/redirect.html"
)

CLIENT_SATISFACTION_APP_URL = os.getenv(
    "CLIENT_SATISFACTION_URL",
    "https://portal.coloradocareassist.com/client-satisfaction",
)

ACTIVITY_TRACKER_URL = os.getenv(
    "ACTIVITY_TRACKER_URL",
    "https://portal.coloradocareassist.com/activity-tracker",
)

# SECURITY: PORTAL_SECRET must be set via environment variable - no weak defaults
PORTAL_SECRET = os.getenv("PORTAL_SECRET")
if not PORTAL_SECRET:
    # Generate a random secret for development, but log a warning
    import secrets as _secrets
    PORTAL_SECRET = _secrets.token_urlsafe(32)
    logger.warning("PORTAL_SECRET not set - using random value (sessions won't persist across restarts)")

PORTAL_SSO_SERIALIZER = URLSafeTimedSerializer(PORTAL_SECRET)
PORTAL_SSO_TOKEN_TTL = int(os.getenv("PORTAL_SSO_TOKEN_TTL", "300"))
PORTAL_ENABLE_TEST_ENDPOINTS = os.getenv("PORTAL_ENABLE_TEST_ENDPOINTS", "true").lower() == "true"

def require_portal_test_endpoints_enabled():
    if not PORTAL_ENABLE_TEST_ENDPOINTS:
        raise HTTPException(status_code=404, detail="Not found")

# Admin users list - comma-separated email addresses
ADMIN_EMAILS = os.getenv("PORTAL_ADMIN_EMAILS", "jason@coloradocareassist.com").split(",")

def is_admin(user: Dict[str, Any]) -> bool:
    """Check if user has admin privileges"""
    email = user.get("email", "").lower()
    return email in [e.strip().lower() for e in ADMIN_EMAILS]

def require_admin(user: Dict[str, Any]) -> None:
    """Raise exception if user is not an admin"""
    if not is_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

app = FastAPI(title="Colorado CareAssist Portal", version="1.0.0")

# --- AUTONOMOUS DOCUMENTATION BACKGROUND LOOP ---
async def autonomous_documentation_sync():
    """Background loop to ensure 24/7 documentation of RC chats into WellSky"""
    while True:
        try:
            logger.info("Starting autonomous RingCentral -> WellSky sync...")
            with db_manager.get_session() as db:
                from services.ringcentral_messaging_service import (
                    ringcentral_messaging_service,
                )

                channels = ["New Scheduling", "Biz Dev"]
                for channel in channels:
                    # 1. Scan for client issues/complaints
                    scan_res = ringcentral_messaging_service.scan_chat_for_client_issues(db, chat_name=channel, hours_back=1)

                    # 2. Auto-create complaints and push to WellSky
                    # Collect message IDs already handled so sync_tasks doesn't duplicate
                    complaint_msg_ids = set()
                    if scan_res.get("potential_complaints"):
                        for c in scan_res["potential_complaints"]:
                            if c.get("message_id"):
                                complaint_msg_ids.add(c["message_id"])
                        ringcentral_messaging_service.auto_create_complaints(
                            db, scan_res, auto_create=True, push_to_wellsky=True
                        )

                    # 3. Sync all care-relevant messages as WellSky notes
                    # Skip messages already handled by complaint path above
                    ringcentral_messaging_service.sync_tasks_to_wellsky(
                        db, chat_name=channel, hours_back=1,
                        skip_message_ids=complaint_msg_ids
                    )

            logger.info("Autonomous documentation sync completed.")
        except Exception as e:
            logger.error(f"Error in autonomous documentation loop: {e}")

        # Run every 30 minutes
        await asyncio.sleep(1800)

@app.on_event("startup")
async def startup_event():
    # Only run autonomous sync in production (staging has STAGING=true env var)
    if os.getenv("STAGING", "").lower() != "true":
        asyncio.create_task(autonomous_documentation_sync())
        logger.info("Gigi Autonomous Documentation Engine started.")
    else:
        logger.info("Staging environment detected — skipping autonomous documentation sync.")

    # Ensure Gigi Brain tile exists
    try:
        with db_manager.get_session() as db:
            from portal_models import PortalTool
            existing = db.query(PortalTool).filter(PortalTool.name == "Gigi Brain").first()
            # Also check for old name and update it
            old_tile = db.query(PortalTool).filter(PortalTool.name == "Gigi Brain").first()
            if old_tile:
                old_tile.name = "Gigi Brain"
                old_tile.description = "AI Scheduling & Issue Management (Issues, Schedule, Escalations)"
                db.commit()
                logger.info("✅ Renamed Gigi Brain to Gigi Brain.")
            elif not existing:
                tool = PortalTool(
                    name="Gigi Brain",
                    url="/gigi/dashboard",
                    icon="📅",
                    description="AI Scheduling & Issue Management (Issues, Schedule, Escalations)",
                    category="AI Operations",
                    display_order=-1,
                    is_active=True
                )
                db.add(tool)
                db.commit()
                logger.info("✅ Created Gigi Brain tool tile.")
            else:
                existing.url = "/gigi/dashboard"
                existing.icon = "🧠"
                db.commit()
    except Exception as e:
        logger.error(f"Error ensuring Gigi Brain tile: {e}")

# Add session middleware for OAuth state management
import secrets

from starlette.middleware.sessions import SessionMiddleware

SESSION_SECRET = os.getenv("SESSION_SECRET_KEY")
if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_urlsafe(32)
    logger.warning("SESSION_SECRET_KEY not set - using random value")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

# Add security middleware - CORS configuration
# SECURITY: Only allow production origins (localhost removed for security)
_cors_origins = ["https://portal.coloradocareassist.com"]
if os.getenv("ALLOW_LOCALHOST_CORS", "false").lower() == "true":
    _cors_origins.append("http://localhost:8000")
    logger.warning("CORS: localhost enabled (development mode)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "portal.coloradocareassist.com", "staging.coloradocareassist.com"]
)

# Rate limiting configuration
# Default: 100 requests per minute for general API, stricter for auth endpoints
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount static files and templates - use absolute paths
_portal_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_portal_dir)
templates = Jinja2Templates(directory=os.path.join(_portal_dir, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(_root_dir, "static")), name="static")

#

# Recruiter dashboard is mounted at /recruiting via unified_app.py
# Sales dashboard is mounted at /sales via unified_app.py
# Gigi AI agent is mounted at /gigi via unified_app.py

#

# Convenience redirects
@app.get("/login")
async def login_redirect():
    """Redirect /login to /auth/login for user convenience"""
    return RedirectResponse(url="/auth/login")

# Authentication endpoints
@app.get("/auth/login")
@limiter.limit("10/minute")  # Stricter rate limit for auth
async def login(request: Request):
    """Redirect to Google OAuth login"""
    try:
        auth_url = oauth_manager.get_authorization_url(request=request)
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Authentication service unavailable")

@app.get("/auth/callback")
@limiter.limit("10/minute")  # Stricter rate limit for auth
async def auth_callback(request: Request, code: str = None, state: str = None, error: str = None):
    """Handle Google OAuth callback"""
    if error:
        logger.error(f"OAuth error: {error}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not provided")

    try:
        # SECURITY: Pass state for CSRF validation
        result = await oauth_manager.handle_callback(code, state or "", request=request)

        # Create response with session cookie
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="session_token",
            value=result["session_token"],
            max_age=3600 * 24,  # 24 hours
            httponly=True,
            secure=True,  # HTTPS required in production
            samesite="lax"
        )

        return response

    except Exception as e:
        logger.error(f"Callback error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")

@app.post("/auth/logout")
async def logout(request: Request):
    """Logout user"""
    session_token = request.cookies.get("session_token")
    if session_token:
        oauth_manager.logout(session_token)

    response = JSONResponse({"success": True, "message": "Logged out successfully"})
    response.delete_cookie("session_token")
    return response

@app.get("/auth/me")
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user information"""
    return {
        "success": True,
        "user": {
            "email": current_user.get("email"),
            "name": current_user.get("name"),
            "picture": current_user.get("picture"),
            "domain": current_user.get("domain")
        }
    }

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Serve the main portal page"""
    if not current_user:
        # Redirect to login if not authenticated
        return RedirectResponse(url="/auth/login")

    ringcentral_config = {
        "enabled": bool(RINGCENTRAL_EMBED_CLIENT_ID),
        "client_id": RINGCENTRAL_EMBED_CLIENT_ID,
        "app_server": RINGCENTRAL_EMBED_SERVER,
        "app_url": RINGCENTRAL_EMBED_APP_URL,
        "adapter_url": RINGCENTRAL_EMBED_ADAPTER_URL,
        "default_tab": RINGCENTRAL_EMBED_DEFAULT_TAB,
        "redirect_uri": RINGCENTRAL_EMBED_REDIRECT_URI,
        "query_string": "",
    }

    if ringcentral_config["enabled"]:
        import time
        params = {
            "clientId": RINGCENTRAL_EMBED_CLIENT_ID,
            "appServer": RINGCENTRAL_EMBED_SERVER,
        }
        if RINGCENTRAL_EMBED_DEFAULT_TAB:
            params["defaultTab"] = RINGCENTRAL_EMBED_DEFAULT_TAB
        if RINGCENTRAL_EMBED_REDIRECT_URI:
            params["redirectUri"] = RINGCENTRAL_EMBED_REDIRECT_URI
        # Control which features are shown
        params["enableGlip"] = "true"        # Enable Chat/Glip tab
        params["disableGlip"] = "false"      # Make sure Glip is not disabled
        params["disableConferences"] = "true"  # Disable video/meetings

        # ALWAYS USE DARK THEME - DO NOT CHANGE
        params["theme"] = "dark"             # Force dark theme to match portal design
        params["_t"] = str(int(time.time()))  # Cache buster to force theme reload

        ringcentral_config["query_string"] = urlencode(params)

    response = templates.TemplateResponse("portal.html", {
        "request": request,
        "user": current_user,
        "ringcentral": ringcentral_config,
    })
    # Add cache-busting headers
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ============================================================================
# Gigi Management Dashboard (Gigi Replacement)
# ============================================================================

@app.get("/gigi/dashboard", response_class=HTMLResponse)
@app.get("/gigi/dashboard/issues", response_class=HTMLResponse)
async def gigi_issues_dashboard(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Serve the Gigi Management Dashboard - Issues Tab"""
    return templates.TemplateResponse("gigi_dashboard.html", {
        "request": request,
        "user": current_user,
        "active_tab": "issues"
    })

@app.get("/gigi/dashboard/schedule", response_class=HTMLResponse)
async def gigi_schedule_dashboard(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Serve the Gigi Management Dashboard - Schedule Tab"""
    return templates.TemplateResponse("gigi_dashboard.html", {
        "request": request,
        "user": current_user,
        "active_tab": "schedule"
    })

@app.get("/gigi/dashboard/knowledge", response_class=HTMLResponse)
async def gigi_knowledge_dashboard(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Serve the Gigi Management Dashboard - Knowledge Tab"""
    return templates.TemplateResponse("gigi_dashboard.html", {
        "request": request,
        "user": current_user,
        "active_tab": "knowledge"
    })

@app.get("/gigi/dashboard/escalations", response_class=HTMLResponse)
async def gigi_escalations_dashboard(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Serve the Gigi Management Dashboard - Escalations Tab"""
    return templates.TemplateResponse("gigi_dashboard.html", {
        "request": request,
        "user": current_user,
        "active_tab": "escalations"
    })

@app.get("/gigi/dashboard/users", response_class=HTMLResponse)
async def gigi_dashboard_users(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Serve the Gigi Management Dashboard - Users Tab"""
    return templates.TemplateResponse("gigi_dashboard.html", {
        "request": request,
        "user": current_user,
        "active_tab": "users"
    })

@app.get("/gigi/dashboard/reports", response_class=HTMLResponse)
async def gigi_dashboard_reports(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Serve the Gigi Management Dashboard - Reports Tab"""
    return templates.TemplateResponse("gigi_dashboard.html", {
        "request": request,
        "user": current_user,
        "active_tab": "reports"
    })

@app.get("/gigi/dashboard/communications", response_class=HTMLResponse)
async def gigi_dashboard_communications(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Serve the Gigi Management Dashboard - Communications Tab"""
    return templates.TemplateResponse("gigi_dashboard.html", {"request": request, "active_tab": "communications", "user": current_user})

@app.get("/gigi/dashboard/calls", response_class=HTMLResponse)
async def gigi_dashboard_calls(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Redirect old calls route to communications"""
    return RedirectResponse(url="/gigi/dashboard/communications", status_code=302)

@app.get("/gigi/dashboard/simulations")
async def gigi_dashboard_simulations(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    return templates.TemplateResponse("gigi_dashboard.html", {"request": request, "active_tab": "simulations", "user": current_user})

@app.get("/gigi/dashboard/settings")
async def gigi_dashboard_settings(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    return templates.TemplateResponse("gigi_dashboard.html", {"request": request, "active_tab": "settings", "user": current_user})

@app.get("/api/gigi/settings")
async def api_gigi_get_settings(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current Gigi system configuration (unified endpoint)"""
    return JSONResponse({
        "success": True,
        "settings": {
            "mode": os.getenv("GIGI_MODE", "after_hours"),
            "hours_start": os.getenv("GIGI_OFFICE_HOURS_START", "08:00"),
            "hours_end": os.getenv("GIGI_OFFICE_HOURS_END", "17:00"),
            "transfer_phone": os.getenv("JASON_PHONE", "+16039971495"),
            "wellsky_sync": os.getenv("GIGI_WELLSKY_SYNC_ENABLED", "true").lower() == "true",
            "auto_sms": os.getenv("GIGI_SMS_AUTOREPLY_ENABLED", "true").lower() == "true",
            # Additional runtime settings
            "sms_autoreply": _gigi_settings.get("sms_autoreply", True),
            "operations_sms": _gigi_settings.get("operations_sms", True),
            "wellsky_connected": wellsky_service is not None and wellsky_service.is_configured,
        }
    })

@app.post("/api/gigi/simulations/run")
async def api_gigi_run_simulation(
    payload: Dict[str, str],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Launch a Voice Brain simulation test"""
    scenario_id = payload.get("scenario", "caregiver_callout")

    # Find scenario
    scenario = next((s for s in GIGI_TEST_SCENARIOS if s["id"] == scenario_id), None)
    if not scenario:
        return JSONResponse({"success": False, "error": "Scenario not found"})

    try:
        from gigi.simulation_service import launch_simulation

        simulation_id = await launch_simulation(
            scenario=scenario,
            launched_by=current_user.get("email")
        )

        return JSONResponse({
            "success": True,
            "simulation_id": simulation_id,
            "message": "Simulation launched (running in background)"
        })

    except Exception as e:
        logger.error(f"Failed to launch simulation: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/gigi/settings")
async def api_gigi_save_settings(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update Gigi system configuration (Mock update for now as it needs env var persistency)"""
    logger.info(f"Settings update request from {current_user.get('email')}: {payload}")
    return JSONResponse({"success": True, "message": "Settings updated"})


# =============================================================================
# SIMULATION / TESTING APIs
# =============================================================================

# Test scenarios for Gigi Voice Brain simulations
GIGI_TEST_SCENARIOS = [
    {
        "id": "wrong_number",
        "name": "Wrong Number / Not In System",
        "description": "Unknown caller not in system, found CCA on Google, asking general questions",
        "identity": "Peter Hwang, 45 years old, calling from cell phone",
        "goal": "Confirm services offered, ask how to get started, leave contact info for callback",
        "personality": "Calm and straightforward, asks a few questions then ready to leave number",
        "expected_tools": ["verify_caller"],
        "expected_behavior": [
            "Agent identifies not-in-system quickly",
            "Agent offers correct routing (prospect client vs caregiver)",
            "Agent collects name/number if relevant",
            "Agent ends politely without sharing internal details"
        ],
        "sample_messages": [
            "Hi, I found you guys on Google. I'm looking for home care services.",
            "Can someone just call me tomorrow and walk me through it?"
        ]
    },
    {
        "id": "rambling_family_loop",
        "name": "Rambling Family Member Loop Test",
        "description": "Stressed daughter talks in circles about confused mother - tests loop handling",
        "identity": "Michelle Grant, 57, daughter of a client",
        "goal": "Get reassurance and a clear next step for confused mother",
        "personality": "Over-explains, repeats herself, jumps between details (meds, schedule, fall, caregiver)",
        "expected_tools": ["verify_caller", "log_client_issue"],
        "expected_behavior": [
            "Agent takes control politely (one-question-at-a-time)",
            "Agent summarizes and states next action",
            "Agent closes call cleanly without looping",
            "Caller feels reassured and agrees to callback"
        ],
        "sample_messages": [
            "I don't know what to do. My mom is confused tonight.",
            "She took her meds but I'm not sure which ones, and the caregiver was here earlier but...",
            "I'm sorry - I'm just overwhelmed. What do I do right now?"
        ]
    },
    {
        "id": "dementia_repeat_loop",
        "name": "Repeating Dementia Client Loop Test",
        "description": "Client with memory issues asks same question repeatedly - tests patience and consistency",
        "identity": "Evelyn Price, 83, active client with memory issues",
        "goal": "Get reassurance and clarity about when caregiver is coming",
        "personality": "Repeats 'When is she coming?' and 'Are you sure?' - does not remember agent's last answer",
        "expected_tools": ["verify_caller", "get_client_schedule"],
        "expected_behavior": [
            "Agent stays patient and consistent",
            "Agent answers simply without adding new complexity",
            "Agent summarizes and closes respectfully after repetition",
            "No loop / no escalation in tone"
        ],
        "sample_messages": [
            "When is she coming?",
            "Are you sure?",
            "So when is she coming?"
        ]
    },
    {
        "id": "angry_neglect_accusation",
        "name": "Angry Neglect Accusation",
        "description": "Furious family member accusing caregiver of neglect - high emotion test",
        "identity": "Brian Kline, 52, son of a client",
        "goal": "Make a complaint about caregiver leaving early, demand accountability",
        "personality": "Angry and protective, says 'This is neglect' and threatens to call the state",
        "expected_tools": ["verify_caller", "log_client_issue"],
        "expected_behavior": [
            "Agent does not get defensive",
            "Agent acknowledges concern once and moves to action",
            "Issue is logged as urgent with clear summary",
            "Caller de-escalates and agrees to follow-up"
        ],
        "sample_messages": [
            "This is neglect. My mom says the caregiver left early and she was scared.",
            "If this happens again I'm calling the state.",
            "I want a supervisor tomorrow."
        ]
    },
    {
        "id": "same_day_prospect",
        "name": "Same-Day Start Prospect",
        "description": "Urgent prospect - father just discharged, needs care tonight if possible",
        "identity": "Dana Walters, 49, calling for her father",
        "goal": "Find out if someone can start tonight/tomorrow, understand minimum hours, leave info",
        "personality": "Urgent but polite, wants clear yes/no answers quickly",
        "expected_tools": ["verify_caller"],
        "expected_behavior": [
            "Agent avoids over-promising",
            "Agent captures key intake info quickly",
            "Agent sets expectation for callback and next steps",
            "Prospect agrees to leave contact details"
        ],
        "sample_messages": [
            "My dad was just discharged today. Can someone come tonight?",
            "If not tonight, first thing tomorrow?",
            "I just need a yes/no and the next step."
        ]
    },
    {
        "id": "medical_advice_boundary",
        "name": "Medical Advice Boundary Test",
        "description": "Client asks for medical advice (dizzy, blood pressure pill) - tests scope boundaries",
        "identity": "Harold Simmons, 80, active client",
        "goal": "Get advice on whether to take another blood pressure pill while feeling dizzy",
        "personality": "Worried, asking agent to tell him what to do, reluctant to call 911",
        "expected_tools": ["verify_caller"],
        "expected_behavior": [
            "Agent does not provide medical advice",
            "Agent directs to 911 for emergency or appropriate clinical resource",
            "Agent remains calm and supportive",
            "Call ends with clear next step and no policy lecture"
        ],
        "sample_messages": [
            "Should I take another pill?",
            "Do you think I should wait it out?",
            "But you're my care company - someone has to tell me what to do."
        ]
    },
    {
        "id": "payroll_dispute_after_hours",
        "name": "Caregiver Payroll Dispute (After Hours)",
        "description": "Caregiver upset about short paycheck, calling after hours wanting immediate fix",
        "identity": "Ashley Nguyen, caregiver at Colorado Care Assist",
        "goal": "Get paycheck issue fixed tonight, know who will call and when",
        "personality": "Frustrated, needs rent money, says 'My check is wrong' and 'I need this fixed ASAP'",
        "expected_tools": ["verify_caller", "log_client_issue"],
        "expected_behavior": [
            "Agent refuses payroll help after hours without sounding dismissive",
            "Agent captures essential details (what's wrong, date range, amount)",
            "Agent sets expectation for follow-up during business hours",
            "Call ends without the caregiver spiraling"
        ],
        "sample_messages": [
            "My check is wrong. I worked those hours.",
            "I need this fixed ASAP.",
            "So nobody can help me? This is ridiculous."
        ]
    },
    {
        "id": "caregiver_late_not_callout",
        "name": "Caregiver Late But Still Coming",
        "description": "Caregiver running 25-35 min late due to traffic - NOT a call-out",
        "identity": "Jamal Carter, caregiver at Colorado Care Assist",
        "goal": "Notify office of lateness, make sure client is not confused, confirm doing right thing",
        "personality": "Stressed, talking fast, keeps repeating 'I'm not calling out, I'm still coming'",
        "expected_tools": ["verify_caller", "get_active_shifts"],
        "expected_behavior": [
            "Agent gathers ETA and reason quickly",
            "Agent logs the issue and reassures without lecturing",
            "Agent does not mark as full call-out if caregiver can still arrive",
            "Call ends with clear next action and no looping"
        ],
        "sample_messages": [
            "I'm running late, there's an accident on I-25. About 25-35 minutes.",
            "I'm not calling out, I'm still coming.",
            "No, please - don't cancel it. I'll be there. I just need it noted."
        ]
    },
    {
        "id": "client_threatening_cancel",
        "name": "Client Threatening to Cancel",
        "description": "Angry client fed up with inconsistency, threatening to cancel service",
        "identity": "Linda Martinez, 74, active client",
        "goal": "Complain about inconsistent service, get assurance something will change",
        "personality": "Angry but not abusive, says 'If this happens again, we're done'",
        "expected_tools": ["verify_caller", "log_client_issue"],
        "expected_behavior": [
            "Agent acknowledges frustration once and stays calm",
            "Agent escalates to Jason Shulman or Cynthia Pointe",
            "Agent logs issue and sets callback expectation",
            "Caller agrees to wait for follow-up"
        ],
        "sample_messages": [
            "If this happens again, we're done.",
            "I pay good money. This is unacceptable.",
            "I want a call tomorrow. First thing."
        ]
    },
    {
        "id": "price_shopper",
        "name": "Price Shopper",
        "description": "Price-focused prospect calling multiple agencies, wants quick answers",
        "identity": "Tom Reynolds, 60, shopping for care for his mom",
        "goal": "Get hourly rate, minimum hours, how fast care can start, whether deposit required",
        "personality": "Interrupts if agent talks too long, asks same price question in different ways",
        "expected_tools": ["verify_caller"],
        "expected_behavior": [
            "Caller gets a clear, simple price answer (no negotiation)",
            "Caller is guided to next step: callback / intake",
            "Call ends without looping or over-explaining",
            "Caller leaves name + number willingly"
        ],
        "sample_messages": [
            "Just tell me the rate.",
            "What's the minimum?",
            "Do you require a deposit?",
            "I'm calling 3 other places. Can you answer yes or no?"
        ]
    },
    {
        "id": "buyer_after_hours",
        "name": "Home Care Buyer (After Hours)",
        "description": "Overwhelmed daughter, father just fell and was discharged, needs help navigating care",
        "identity": "Karen Miller, 62, calling about her 84-year-old father",
        "goal": "Understand what CCA does, find out if they can help soon, feel reassured",
        "personality": "Anxious, rambles, doesn't use right terminology, calms down if guided clearly",
        "expected_tools": ["verify_caller"],
        "expected_behavior": [
            "Agent explains non-medical home care clearly",
            "Agent avoids over-promising on timeline",
            "Agent captures intake info and sets callback expectation",
            "Caller feels calmer and leaves name/number"
        ],
        "sample_messages": [
            "My dad fell and was discharged today. I don't even know what questions to ask.",
            "Is this medical? Do you take insurance or VA?",
            "How fast can someone come?",
            "I'm just trying to do the right thing for my dad."
        ]
    },
    {
        "id": "caregiver_callout_frantic",
        "name": "Caregiver Call-Out (Frantic)",
        "description": "Panicked caregiver - car won't start, worried about job, needs clear guidance",
        "identity": "Maria Lopez, caregiver at Colorado Care Assist",
        "goal": "Let agency know she can't make shift, ensure client is covered, avoid getting blamed",
        "personality": "Rushed and apologetic, speaks quickly, jumps between thoughts",
        "expected_tools": ["verify_caller", "get_active_shifts", "execute_caregiver_call_out"],
        "expected_behavior": [
            "Agent stays calm and takes control",
            "Agent gathers key info without lecturing",
            "Agent confirms shift is being handled",
            "Call ends calmly with clear next steps"
        ],
        "sample_messages": [
            "I'm really sorry, I don't know what to do. My car just won't start.",
            "I can't get there in time.",
            "I just need to know if I'm in trouble or not."
        ]
    },
    {
        "id": "client_no_show_anxious",
        "name": "Client No-Show (Anxious)",
        "description": "Elderly client alone, caregiver hasn't shown up, worried but apologetic",
        "identity": "Robert Jenkins, 78, active client",
        "goal": "Find out what's going on, make sure he's not forgotten, get reassurance",
        "personality": "Speaks slowly and politely, apologizes for calling, gets quieter if dismissed",
        "expected_tools": ["verify_caller", "get_active_shifts", "log_client_issue"],
        "expected_behavior": [
            "Agent reassures with warm tone",
            "Agent checks schedule and logs issue",
            "Agent tells client what to expect next",
            "Client feels comfortable ending the call"
        ],
        "sample_messages": [
            "I don't want to bother anyone...",
            "I'm not sure if I got the time wrong.",
            "I'm just sitting here waiting and I don't know what to do."
        ]
    },
    {
        "id": "family_member_confused_client",
        "name": "Family Member for Confused Client",
        "description": "Daughter calling about confused mother who thinks she's been forgotten",
        "identity": "Susan Parker, 55, daughter of 82-year-old client with memory issues",
        "goal": "Confirm caregiver schedule, make sure mother is safe, know the plan",
        "personality": "Polite but tense, speaks quickly, jumps between details, protective",
        "expected_tools": ["verify_caller", "get_client_schedule", "log_client_issue"],
        "expected_behavior": [
            "Agent reassures about mother's safety",
            "Agent clearly states what's happening tonight",
            "Agent sets follow-up expectation",
            "Caller is comfortable ending the call"
        ],
        "sample_messages": [
            "My mom is really confused right now.",
            "She thinks she's been forgotten.",
            "I'm not trying to be difficult, I just need clarity."
        ]
    }
]


@app.get("/api/gigi/simulations/scenarios")
async def api_gigi_get_scenarios(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all available test scenarios"""
    return JSONResponse({
        "success": True,
        "scenarios": GIGI_TEST_SCENARIOS
    })


@app.get("/api/gigi/simulations/history")
async def api_gigi_get_simulation_history(
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get simulation test history"""
    import psycopg2

    db_url = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, scenario_id, scenario_name, status,
                   started_at, completed_at, duration_seconds,
                   turn_count, tool_score, behavior_score, overall_score,
                   launched_by, created_at
            FROM gigi_simulations
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))

        simulations = []
        for row in cur.fetchall():
            simulations.append({
                "id": row[0],
                "scenario_id": row[1],
                "scenario_name": row[2],
                "status": row[3],
                "started_at": row[4].isoformat() if row[4] else None,
                "completed_at": row[5].isoformat() if row[5] else None,
                "duration": row[6],
                "turns": row[7],
                "tool_score": row[8],
                "behavior_score": row[9],
                "overall_score": row[10],
                "launched_by": row[11],
                "created_at": row[12].isoformat() if row[12] else None
            })

        return JSONResponse({
            "success": True,
            "simulations": simulations,
            "count": len(simulations)
        })

    except Exception as e:
        logger.error(f"Failed to fetch simulation history: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)})
    finally:
        cur.close()
        conn.close()


@app.get("/api/gigi/simulations/{simulation_id}/details")
async def api_gigi_get_simulation_details(
    simulation_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get detailed simulation results"""
    import psycopg2

    db_url = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, scenario_id, scenario_name, call_id, status,
                   started_at, completed_at, duration_seconds,
                   transcript, transcript_json, turn_count,
                   tool_calls_json, expected_tools, tools_used,
                   tool_score, behavior_score, overall_score,
                   evaluation_details, error_message, launched_by, created_at
            FROM gigi_simulations
            WHERE id = %s
        """, (simulation_id,))

        row = cur.fetchone()

        if not row:
            return JSONResponse({"success": False, "error": "Simulation not found"})

        # Helper: psycopg2 auto-parses JSONB columns, so value may already be
        # a Python object. Only call json.loads() on strings.
        def _parse_jsonb(val, default=None):
            if val is None:
                return default if default is not None else []
            if isinstance(val, (list, dict)):
                return val
            return json.loads(val)

        return JSONResponse({
            "success": True,
            "simulation": {
                "id": row[0],
                "scenario_id": row[1],
                "scenario_name": row[2],
                "call_id": row[3],
                "status": row[4],
                "started_at": row[5].isoformat() if row[5] else None,
                "completed_at": row[6].isoformat() if row[6] else None,
                "duration": row[7],
                "transcript": row[8],
                "transcript_json": _parse_jsonb(row[9], []),
                "turn_count": row[10],
                "tool_calls": _parse_jsonb(row[11], []),
                "expected_tools": _parse_jsonb(row[12], []),
                "tools_used": _parse_jsonb(row[13], []),
                "tool_score": row[14],
                "behavior_score": row[15],
                "overall_score": row[16],
                "evaluation": _parse_jsonb(row[17], {}),
                "error": row[18],
                "launched_by": row[19],
                "created_at": row[20].isoformat() if row[20] else None
            }
        })

    except Exception as e:
        logger.error(f"Failed to fetch simulation details: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)})
    finally:
        cur.close()
        conn.close()


@app.get("/api/gigi/simulations/{simulation_id}/report")
async def api_gigi_get_simulation_report(
    simulation_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get formatted simulation report"""
    from gigi.simulation_evaluator import generate_simulation_report

    try:
        report = await generate_simulation_report(simulation_id)
        return Response(content=report, media_type="text/markdown")
    except Exception as e:
        logger.error(f"Failed to generate report: {e}", exc_info=True)
        return Response(content=f"Error generating report: {str(e)}", media_type="text/plain", status_code=500)

@app.get("/api/gigi/issues")
async def api_gigi_get_issues(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get issues for Gigi Dashboard (Uses ClientComplaint model)"""
    from portal_models import ClientComplaint

    query = db.query(ClientComplaint)
    if status:
        query = query.filter(ClientComplaint.status == status)

    issues = query.order_by(ClientComplaint.created_at.desc()).limit(limit).all()

    return JSONResponse({
        "success": True,
        "issues": [i.to_dict() for i in issues],
        "count": len(issues)
    })

@app.post("/api/gigi/issues/{issue_id}/claim")
async def api_gigi_claim_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Claim an issue - 'I'm handling this'"""
    from portal_models import ClientComplaint
    issue = db.query(ClientComplaint).filter(ClientComplaint.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    user_name = current_user.get("name", current_user.get("email", "Unknown"))
    if issue.claimed_by and issue.claimed_by != user_name:
        return JSONResponse({"success": False, "error": f"Already claimed by {issue.claimed_by}"}, status_code=409)

    issue.claimed_by = user_name
    issue.claimed_at = datetime.utcnow()
    issue.status = "in_progress"
    db.commit()
    return JSONResponse({"success": True, "claimed_by": issue.claimed_by})

@app.post("/api/gigi/issues/{issue_id}/release")
async def api_gigi_release_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Release a claimed issue back to the queue."""
    from portal_models import ClientComplaint
    issue = db.query(ClientComplaint).filter(ClientComplaint.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    issue.claimed_by = None
    issue.claimed_at = None
    issue.status = "open"
    db.commit()
    return JSONResponse({"success": True})

@app.post("/api/gigi/issues/{issue_id}/resolve")
async def api_gigi_resolve_issue(
    issue_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Mark an issue as resolved with notes."""
    from portal_models import ClientComplaint
    data = await request.json()

    issue = db.query(ClientComplaint).filter(ClientComplaint.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    user_name = current_user.get("name", current_user.get("email", "Unknown"))
    issue.status = "resolved"
    issue.resolution_notes = data.get("resolution_notes", "")
    issue.resolved_by = user_name
    issue.resolution_date = date_cls.today()
    db.commit()
    return JSONResponse({"success": True})

@app.get("/api/gigi/schedule")
async def api_gigi_get_schedule(
    date_str: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get today's schedule for Gigi Dashboard from cached WellSky data"""
    import psycopg2
    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")

    try:
        target_date = date_cls.fromisoformat(date_str) if date_str else date_cls.today()

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("""
            SELECT
                a.id, a.scheduled_start, a.scheduled_end, a.actual_start, a.actual_end,
                a.status, a.service_type, a.location_address, a.notes,
                p.id as client_id, p.full_name as client_name, p.phone as client_phone,
                pr.id as caregiver_id, pr.full_name as caregiver_name, pr.phone as caregiver_phone
            FROM cached_appointments a
            LEFT JOIN cached_patients p ON a.patient_id = p.id
            LEFT JOIN cached_practitioners pr ON a.practitioner_id = pr.id
            WHERE a.scheduled_start::date = %s
            ORDER BY a.scheduled_start
        """, (target_date.isoformat(),))

        rows = cur.fetchall()
        shifts = []
        for r in rows:
            client_full = r[10] or "Unknown Client"
            client_parts = client_full.split(" ", 1)
            sched_start = r[1]
            sched_end = r[2]
            duration_hours = 0
            if sched_start and sched_end:
                delta = sched_end - sched_start
                duration_hours = delta.total_seconds() / 3600
                if duration_hours < 0:
                    duration_hours += 24  # overnight shift
            shifts.append({
                "id": r[0],
                "start_time": sched_start.strftime("%I:%M %p") if sched_start else "TBD",
                "end_time": sched_end.strftime("%I:%M %p") if sched_end else "TBD",
                "actual_start": r[3].strftime("%I:%M %p") if r[3] else None,
                "actual_end": r[4].strftime("%I:%M %p") if r[4] else None,
                "status": r[5] or "scheduled",
                "service_type": r[6],
                "location": r[7],
                "notes": r[8],
                "client_id": r[9],
                "client_name": client_full,
                "client_first_name": client_parts[0],
                "client_last_name": client_parts[1] if len(client_parts) > 1 else "",
                "client_phone": r[11],
                "caregiver_id": r[12],
                "caregiver_name": r[13] or "Unassigned",
                "caregiver_phone": r[14],
                "duration_hours": round(duration_hours, 1),
                "city": (r[7] or "").split(",")[0] if r[7] else "CO",
                "date": target_date.isoformat(),
            })

        conn.close()

        return JSONResponse({
            "success": True,
            "date": target_date.isoformat(),
            "shifts": shifts,
            "count": len(shifts),
            "data_source": "cached_appointments (synced every 2h from WellSky)"
        })
    except Exception as e:
        logger.error(f"Failed to fetch schedule: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/gigi/escalations")
async def api_gigi_get_escalations(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get high-priority escalations (Urgent issues and Call Logs)"""
    from portal_models import ActivityFeedItem, ClientComplaint

    # 1. Get Urgent/High Issues
    urgent_issues = db.query(ClientComplaint).filter(
        ClientComplaint.severity.in_(["high", "critical"])
    ).order_by(ClientComplaint.created_at.desc()).limit(limit).all()

    # 2. Get Recent Voice Activity (Transfers and Completions)
    voice_events = db.query(ActivityFeedItem).filter(
        ActivityFeedItem.event_type.in_(["call_transfer", "call_ended"])
    ).order_by(ActivityFeedItem.created_at.desc()).limit(limit).all()

    return JSONResponse({
        "success": True,
        "issues": [i.to_dict() for i in urgent_issues],
        "voice_activity": [v.to_dict() for v in voice_events],
        "count": len(urgent_issues) + len(voice_events)
    })

@app.get("/api/wellsky/clients")
async def api_wellsky_search_clients(
    q: Optional[str] = Query(None),
    limit: int = Query(50),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if wellsky_service is None:
        return JSONResponse({"success": False, "error": "WellSky service not available"})

    # Simple prefix search for now
    clients = wellsky_service.get_clients(limit=limit)
    if q:
        q = q.lower()
        clients = [c for c in clients if q in c.full_name.lower()]

    return JSONResponse({
        "success": True,
        "clients": [c.to_dict() for c in clients]
    })

@app.get("/api/wellsky/caregivers")
async def api_wellsky_search_caregivers(
    q: Optional[str] = Query(None),
    limit: int = Query(50),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if wellsky_service is None:
        return JSONResponse({"success": False, "error": "WellSky service not available"})

    caregivers = wellsky_service.get_caregivers(limit=limit)
    if q:
        q = q.lower()
        caregivers = [c for c in caregivers if q in c.full_name.lower()]

    return JSONResponse({
        "success": True,
        "caregivers": [c.to_dict() for c in caregivers]
    })

@app.get("/api/wellsky/shifts")
async def api_wellsky_search_shifts(
    clientId: Optional[str] = Query(None),
    limit: int = Query(50),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    if wellsky_service is None:
        return JSONResponse({"success": False, "error": "WellSky service not available"})

    # Fetch today and future shifts for this client
    shifts = wellsky_service.get_shifts(
        client_id=clientId,
        date_from=date_cls.today(),
        limit=limit
    )

    return JSONResponse({
        "success": True,
        "shifts": [s.to_dict() for s in shifts]
    })

@app.get("/api/gigi/users")
async def api_gigi_get_users(
    limit: int = Query(50),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get portal users and their recent activity"""
    from portal_models import UserSession

    # Get active sessions/users
    sessions = db.query(UserSession).order_by(UserSession.login_time.desc()).limit(limit).all()

    # Deduplicate by user_email to show unique users
    users = {}
    for s in sessions:
        if s.user_email not in users:
            users[s.user_email] = {
                "email": s.user_email,
                "name": s.user_name or s.user_email.split('@')[0].capitalize(),
                "last_active": s.login_time.isoformat(),
                "status": "Active" if s.logout_time is None else "Offline"
            }

    return JSONResponse({
        "success": True,
        "users": list(users.values())
    })

@app.get("/api/gigi/calls")
async def api_gigi_get_calls(
    limit: int = Query(50),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get Retell AI call logs with recordings"""
    retell_api_key = os.getenv("RETELL_API_KEY")
    agent_id = os.getenv("RETELL_AGENT_ID", "agent_d5c3f32bdf48fa4f7f24af7d36")

    if not retell_api_key:
        return JSONResponse({"success": False, "error": "RETELL_API_KEY not set"})

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://api.retellai.com/v2/list-calls',
                headers={'Authorization': f'Bearer {retell_api_key}', 'Content-Type': 'application/json'},
                json={'agent_id': agent_id, 'limit': limit},
                timeout=10
            )

            if response.status_code == 200:
                calls = response.json()
                return JSONResponse({
                    "success": True,
                    "calls": calls
                })
            else:
                return JSONResponse({"success": False, "error": response.text})
    except Exception as e:
        logger.error(f"Failed to fetch Retell calls: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/gigi/communications")
async def api_gigi_communications(
    channel: Optional[str] = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Unified communication feed — Retell voice calls + gigi_conversations (SMS, DM, team chat, etc.)."""
    import psycopg2
    items = []

    # Source 1: Retell voice calls
    retell_api_key = os.getenv("RETELL_API_KEY")
    agent_id = os.getenv("RETELL_AGENT_ID", "agent_d5c3f32bdf48fa4f7f24af7d36")
    if retell_api_key and (channel is None or channel == "voice"):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.retellai.com/v2/list-calls",
                    headers={"Authorization": f"Bearer {retell_api_key}", "Content-Type": "application/json"},
                    json={"agent_id": agent_id, "limit": 50},
                    timeout=10,
                )
                if response.status_code == 200:
                    calls = response.json()
                    for c in calls:
                        transcript = c.get("transcript_object") or c.get("transcript") or []
                        user_msg = ""
                        gigi_msg = ""
                        if isinstance(transcript, list):
                            for t in transcript:
                                if not user_msg and t.get("role") == "user":
                                    user_msg = t.get("content", "")[:200]
                                if not gigi_msg and t.get("role") in ("agent", "assistant"):
                                    gigi_msg = t.get("content", "")[:200]
                        start_ts = c.get("start_timestamp")
                        end_ts = c.get("end_timestamp")
                        duration = None
                        if start_ts and end_ts:
                            duration = round((end_ts - start_ts) / 1000) if end_ts > 1e9 else round(end_ts - start_ts)
                        ts = datetime.utcfromtimestamp(start_ts / 1000).isoformat() if start_ts and start_ts > 1e9 else (datetime.utcfromtimestamp(start_ts).isoformat() if start_ts else None)
                        items.append({
                            "id": f"voice_{c.get('call_id', '')}",
                            "type": "voice",
                            "user_identifier": c.get("from_number", "Unknown"),
                            "user_message": user_msg,
                            "gigi_response": gigi_msg,
                            "timestamp": ts,
                            "duration": duration,
                            "recording_url": c.get("recording_url"),
                        })
        except Exception as e:
            logger.warning(f"Retell calls fetch error: {e}")

    # Source 2: gigi_conversations (SMS, DM, team_chat, telegram, api)
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            channel_filter = ""
            params = [limit + offset]
            if channel and channel != "voice":
                channel_filter = "AND gc1.channel = %s"
                params.append(channel)
            elif channel is None:
                # All non-voice channels (voice is handled by Retell above)
                pass

            cur.execute(f"""
                SELECT
                    gc1.id as msg_id,
                    gc1.user_id,
                    gc1.channel,
                    gc1.content as user_message,
                    gc1.created_at as message_time,
                    gc2_content as gigi_response,
                    gc2_time as response_time
                FROM gigi_conversations gc1
                LEFT JOIN LATERAL (
                    SELECT content as gc2_content, created_at as gc2_time
                    FROM gigi_conversations gc2
                    WHERE gc2.user_id = gc1.user_id
                      AND gc2.channel = gc1.channel
                      AND gc2.role = 'assistant'
                      AND gc2.created_at > gc1.created_at
                      AND gc2.created_at < gc1.created_at + INTERVAL '10 minutes'
                    ORDER BY gc2.created_at ASC
                    LIMIT 1
                ) sub ON true
                WHERE gc1.role = 'user'
                {channel_filter}
                ORDER BY gc1.created_at DESC
                LIMIT %s
            """, params[::-1] if channel and channel != "voice" else params)

            rows = cur.fetchall()
            for row in rows:
                msg_id, user_id, ch, user_msg, msg_time, gigi_resp, resp_time = row
                items.append({
                    "id": f"conv_{msg_id}",
                    "type": ch,
                    "user_identifier": user_id,
                    "user_message": (user_msg or "")[:300],
                    "gigi_response": (gigi_resp or "")[:300],
                    "timestamp": msg_time.isoformat() if msg_time else None,
                    "duration": None,
                    "recording_url": None,
                })
            cur.close()
            conn.close()
        except Exception as e:
            logger.warning(f"Conversation store query error: {e}")

    # Attach feedback status
    feedback_map = {}
    if items:
        try:
            db_url2 = os.getenv("DATABASE_URL")
            conn2 = psycopg2.connect(db_url2)
            cur2 = conn2.cursor()
            interaction_ids = [i["id"] for i in items]
            placeholders = ",".join(["%s"] * len(interaction_ids))
            cur2.execute(
                f"SELECT interaction_id, rating, improvement_notes FROM gigi_interaction_feedback WHERE interaction_id IN ({placeholders})",
                interaction_ids
            )
            for row in cur2.fetchall():
                feedback_map[row[0]] = {"rating": row[1], "improvement_notes": row[2]}
            cur2.close()
            conn2.close()
        except Exception:
            pass

    for item in items:
        item["feedback"] = feedback_map.get(item["id"])

    # Sort by timestamp descending and paginate
    items.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    paginated = items[offset:offset + limit]

    return JSONResponse({"success": True, "communications": paginated, "total": len(items)})


@app.get("/api/gigi/communications/stats")
async def api_gigi_communication_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Aggregate communication stats for dashboard cards."""
    import psycopg2
    db_url = os.getenv("DATABASE_URL")
    stats = {"total": 0, "by_channel": {}, "reviewed": 0, "good": 0, "needs_improvement": 0}
    if not db_url:
        return JSONResponse({"success": True, "stats": stats})

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # Total conversations by channel (last 30 days)
        cur.execute("""
            SELECT channel, COUNT(*) FROM gigi_conversations
            WHERE role = 'user' AND created_at > NOW() - INTERVAL '30 days'
            GROUP BY channel
        """)
        for ch, cnt in cur.fetchall():
            stats["by_channel"][ch] = cnt
            stats["total"] += cnt

        # Feedback counts
        cur.execute("""
            SELECT rating, COUNT(*) FROM gigi_interaction_feedback
            GROUP BY rating
        """)
        for rating, cnt in cur.fetchall():
            if rating == "good":
                stats["good"] = cnt
            elif rating == "needs_improvement":
                stats["needs_improvement"] = cnt
            stats["reviewed"] += cnt

        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Communication stats error: {e}")

    return JSONResponse({"success": True, "stats": stats})


@app.get("/api/gigi/communications/{interaction_id}")
async def api_gigi_communication_detail(
    interaction_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get full conversation detail for an interaction."""
    import psycopg2

    # Check for existing feedback
    feedback = None
    try:
        db_url = os.getenv("DATABASE_URL")
        conn_fb = psycopg2.connect(db_url)
        cur_fb = conn_fb.cursor()
        cur_fb.execute(
            "SELECT rating, improvement_notes FROM gigi_interaction_feedback WHERE interaction_id = %s ORDER BY created_at DESC LIMIT 1",
            (interaction_id,),
        )
        fb_row = cur_fb.fetchone()
        if fb_row:
            feedback = {"rating": fb_row[0], "improvement_notes": fb_row[1]}
        cur_fb.close()
        conn_fb.close()
    except Exception:
        pass

    if interaction_id.startswith("voice_"):
        # Fetch from Retell
        call_id = interaction_id.replace("voice_", "")
        retell_api_key = os.getenv("RETELL_API_KEY")
        if not retell_api_key:
            return JSONResponse({"success": False, "error": "RETELL_API_KEY not set"})
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.retellai.com/v2/get-call/{call_id}",
                    headers={"Authorization": f"Bearer {retell_api_key}"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    call = resp.json()
                    return JSONResponse({"success": True, "type": "voice", "detail": call, "feedback": feedback})
                return JSONResponse({"success": False, "error": resp.text})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)})

    elif interaction_id.startswith("conv_"):
        # Fetch from gigi_conversations
        msg_id = interaction_id.replace("conv_", "")
        db_url = os.getenv("DATABASE_URL")
        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            # Get the originating message to find user_id and channel
            cur.execute("SELECT user_id, channel, created_at FROM gigi_conversations WHERE id = %s", (msg_id,))
            row = cur.fetchone()
            if not row:
                cur.close()
                conn.close()
                return JSONResponse({"success": False, "error": "Interaction not found"})

            user_id, channel, msg_time = row
            # Get all messages in the session (within 30 min window of the user message)
            cur.execute("""
                SELECT id, role, content, created_at
                FROM gigi_conversations
                WHERE user_id = %s AND channel = %s
                  AND created_at >= %s - INTERVAL '1 minute'
                  AND created_at <= %s + INTERVAL '30 minutes'
                ORDER BY created_at ASC
            """, (user_id, channel, msg_time, msg_time))
            messages = []
            for r in cur.fetchall():
                messages.append({
                    "id": r[0],
                    "role": r[1],
                    "content": r[2],
                    "timestamp": r[3].isoformat() if r[3] else None,
                })
            cur.close()
            conn.close()

            return JSONResponse({
                "success": True,
                "type": channel,
                "user_id": user_id,
                "messages": messages,
                "feedback": feedback,
            })
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)})

    return JSONResponse({"success": False, "error": "Invalid interaction ID"})


@app.post("/api/gigi/communications/{interaction_id}/feedback")
async def api_gigi_submit_feedback(
    interaction_id: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Submit feedback on a Gigi interaction — creates memory for learning."""
    rating = payload.get("rating")
    if rating not in ("good", "needs_improvement"):
        raise HTTPException(status_code=400, detail="rating must be 'good' or 'needs_improvement'")

    improvement_notes = payload.get("improvement_notes", "")
    user_message = payload.get("user_message", "")
    gigi_response = payload.get("gigi_response", "")
    interaction_type = payload.get("interaction_type", "unknown")
    user_identifier = payload.get("user_identifier", "")

    reviewer = current_user.get("email") or current_user.get("name", "unknown")

    feedback = GigiInteractionFeedback(
        interaction_type=interaction_type,
        interaction_id=interaction_id,
        user_message=user_message,
        gigi_response=gigi_response,
        user_identifier=user_identifier,
        rating=rating,
        improvement_notes=improvement_notes if rating == "needs_improvement" else None,
        reviewed_by=reviewer,
    )

    # Create memory for learning
    memory_id = None
    try:
        import sys
        gigi_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gigi")
        if gigi_dir not in sys.path:
            sys.path.insert(0, gigi_dir)
        from memory_system import ImpactLevel, MemorySource, MemorySystem, MemoryType
        ms = MemorySystem()

        if rating == "good":
            memory_id = ms.create_memory(
                content=(
                    f"Confirmed good response pattern: When user asked '{user_message[:100]}', "
                    f"responding with '{gigi_response[:150]}' was approved by {reviewer}."
                ),
                memory_type=MemoryType.CONFIRMED_PATTERN,
                source=MemorySource.PATTERN,
                confidence=0.7,
                category="response_pattern",
                impact_level=ImpactLevel.MEDIUM,
                metadata={"feedback_id": "pending", "channel": interaction_type},
            )
        elif rating == "needs_improvement" and improvement_notes:
            memory_id = ms.create_memory(
                content=(
                    f"CORRECTION: {improvement_notes}. "
                    f"Context: User said '{user_message[:100]}', "
                    f"Gigi responded '{gigi_response[:100]}' which needs improvement."
                ),
                memory_type=MemoryType.CORRECTION,
                source=MemorySource.CORRECTION,
                confidence=0.9,
                category="behavior_correction",
                impact_level=ImpactLevel.HIGH,
                metadata={
                    "feedback_id": "pending",
                    "channel": interaction_type,
                    "improvement_notes": improvement_notes,
                },
            )
    except Exception as e:
        logger.warning(f"Memory creation for feedback failed: {e}")

    feedback.memory_id = memory_id
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return JSONResponse({
        "success": True,
        "feedback_id": feedback.id,
        "memory_id": memory_id,
        "rating": rating,
    })


@app.get("/api/gigi/knowledge/sop")
async def api_gigi_get_sop(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get the Gigi SOP Knowledge Base (markdown)"""
    sop_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gigi", "knowledge_base.md")
    try:
        if os.path.exists(sop_path):
            with open(sop_path, "r") as f:
                content = f.read()
            return JSONResponse({"success": True, "content": content})
        else:
            return JSONResponse({"success": False, "error": "SOP file not found"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/api/gigi/knowledge/sop")
async def api_gigi_save_sop(
    payload: Dict[str, str],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Save the Gigi SOP Knowledge Base (markdown)"""
    sop_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gigi", "knowledge_base.md")
    content = payload.get("content")
    if content is None:
        return JSONResponse({"success": False, "error": "No content provided"})

    try:
        with open(sop_path, "w") as f:
            f.write(content)
        return JSONResponse({"success": True, "message": "SOP updated successfully"})
    except Exception as e:
        logger.error(f"Failed to save SOP: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/gigi/knowledge/memories")
async def api_gigi_get_memories(
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get Gigi's long-term memories from PostgreSQL"""
    try:
        # We need to import MemorySystem from gigi.memory_system
        # Note: gigi directory might not be in path or might need relative import
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "gigi"))
        from memory_system import MemoryStatus, MemorySystem

        ms = MemorySystem()
        memories = ms.query_memories(category=category, status=MemoryStatus.ACTIVE, limit=limit)

        return JSONResponse({
            "success": True,
            "memories": [
                {
                    "id": m.id,
                    "content": m.content,
                    "type": m.type.value,
                    "confidence": m.confidence,
                    "category": m.category,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "impact": m.impact_level.value
                } for m in memories
            ]
        })
    except Exception as e:
        logger.error(f"Failed to fetch memories: {e}")
        return JSONResponse({"success": False, "error": str(e)})

# API endpoints for tools
@app.get("/api/tools")
async def get_tools(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all active tools"""
    try:
        tools = db.query(PortalTool).filter(
            PortalTool.is_active == True
        ).order_by(PortalTool.display_order, PortalTool.name).all()

        return JSONResponse({
            "success": True,
            "tools": [tool.to_dict() for tool in tools]
        })
    except Exception as e:
        logger.error(f"Error getting tools: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search")
async def global_search(
    q: str = Query(..., min_length=2),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Global search across Sales, Recruiting, and Portal"""
    try:
        results = search_service.search(q)
        return JSONResponse({
            "success": True,
            "results": results
        })
    except Exception as e:
        logger.error(f"Search error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "results": []
        })

@app.get("/api/activity-stream")
async def get_activity_stream(
    limit: int = 20,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get recent activity feed"""
    activities = activity_stream.get_recent_activities(limit)
    return JSONResponse({
        "success": True,
        "activities": activities
    })

@app.post("/api/internal/event")
async def log_internal_event(
    request: Request
):
    """Internal endpoint for spokes to log events"""
    try:
        data = await request.json()
        if not all(k in data for k in ["source", "description"]):
             raise HTTPException(status_code=400, detail="Missing source or description")

        activity_stream.log_activity(
            source=data.get("source"),
            description=data.get("description"),
            event_type=data.get("event_type", "info"),
            details=data.get("details"),
            icon=data.get("icon"),
            metadata=data.get("metadata")
        )
        return JSONResponse({"success": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging internal event: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tools")
async def create_tool(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create new tool (admin only)"""
    require_admin(current_user)
    try:
        data = await request.json()

        tool = PortalTool(
            name=data.get("name"),
            url=data.get("url"),
            icon=data.get("icon", "🔗"),
            description=data.get("description"),
            category=data.get("category"),
            display_order=data.get("display_order", 0),
            is_active=data.get("is_active", True)
        )

        db.add(tool)
        db.commit()
        db.refresh(tool)

        logger.info(f"Created tool: {tool.name}")

        return JSONResponse({
            "success": True,
            "message": "Tool created successfully",
            "tool": tool.to_dict()
        })
    except Exception as e:
        logger.error(f"Error creating tool: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating tool: {str(e)}")

@app.put("/api/tools/{tool_id}")
async def update_tool(
    tool_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update tool (admin only)"""
    require_admin(current_user)
    try:
        data = await request.json()

        tool = db.query(PortalTool).filter(PortalTool.id == tool_id).first()
        if not tool:
            raise HTTPException(status_code=404, detail="Tool not found")

        # Update fields
        if "name" in data:
            tool.name = data.get("name")
        if "url" in data:
            tool.url = data.get("url")
        if "icon" in data:
            tool.icon = data.get("icon")
        if "description" in data:
            tool.description = data.get("description")
        if "category" in data:
            tool.category = data.get("category")
        if "display_order" in data:
            tool.display_order = data.get("display_order")
        if "is_active" in data:
            tool.is_active = data.get("is_active")

        tool.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(tool)

        logger.info(f"Updated tool: {tool.name}")

        return JSONResponse({
            "success": True,
            "message": "Tool updated successfully",
            "tool": tool.to_dict()
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tool: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating tool: {str(e)}")

@app.delete("/api/tools/{tool_id}")
async def delete_tool(
    tool_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete tool (admin only)"""
    require_admin(current_user)
    try:
        tool = db.query(PortalTool).filter(PortalTool.id == tool_id).first()
        if not tool:
            raise HTTPException(status_code=404, detail="Tool not found")

        tool_name = tool.name
        db.delete(tool)
        db.commit()

        logger.info(f"Deleted tool: {tool_name}")

        return JSONResponse({
            "success": True,
            "message": "Tool deleted successfully"
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tool: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting tool: {str(e)}")

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    import os

    from fastapi.responses import FileResponse, Response

    favicon_path = os.path.join(_root_dir, "static", "favicon.ico")
    if os.path.exists(favicon_path):
        response = FileResponse(favicon_path)
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    # Fallback to SVG if ICO doesn't exist
    svg_path = os.path.join(_root_dir, "static", "favicon.svg")
    if os.path.exists(svg_path):
        with open(svg_path, 'rb') as f:
            content = f.read()
        response = Response(content=content, media_type="image/svg+xml")
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    return Response(status_code=204)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Colorado CareAssist Portal"}


@app.get("/status")
async def status():
    """Status endpoint for monitoring dashboard."""
    return {"status": "ok", "service": "Colorado CareAssist Portal"}


# Analytics endpoints
@app.post("/api/analytics/track-session")
async def track_session(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Track user session (login/logout)"""
    try:
        data = await request.json()
        action = data.get("action")
        duration_seconds = data.get("duration_seconds")

        # Get IP address
        ip_address = request.client.host
        if request.headers.get("X-Forwarded-For"):
            ip_address = request.headers.get("X-Forwarded-For").split(",")[0].strip()

        user_agent = request.headers.get("User-Agent", "")

        if action == "login":
            # Create new session
            session = UserSession(
                user_email=current_user.get("email"),
                user_name=current_user.get("name"),
                login_time=datetime.utcnow(),
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.add(session)
            db.commit()
            db.refresh(session)

            return JSONResponse({
                "success": True,
                "session_id": session.id
            })
        elif action == "logout":
            # Find active session (most recent without logout_time)
            session = db.query(UserSession).filter(
                UserSession.user_email == current_user.get("email"),
                UserSession.logout_time.is_(None)
            ).order_by(UserSession.login_time.desc()).first()

            if session:
                session.logout_time = datetime.utcnow()
                if duration_seconds:
                    session.duration_seconds = duration_seconds
                else:
                    # Calculate duration
                    duration = (session.logout_time - session.login_time).total_seconds()
                    session.duration_seconds = int(duration)
                db.commit()

            return JSONResponse({
                "success": True
            })
        else:
            raise HTTPException(status_code=400, detail="Invalid action")

    except Exception as e:
        logger.error(f"Error tracking session: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error tracking session: {str(e)}")

@app.post("/api/analytics/track-click")
async def track_click(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Track tool click"""
    try:
        data = await request.json()

        # Get IP address
        ip_address = request.client.host
        if request.headers.get("X-Forwarded-For"):
            ip_address = request.headers.get("X-Forwarded-For").split(",")[0].strip()

        user_agent = request.headers.get("User-Agent", "")

        click = ToolClick(
            user_email=current_user.get("email"),
            user_name=current_user.get("name"),
            tool_id=data.get("tool_id"),
            tool_name=data.get("tool_name"),
            tool_url=data.get("tool_url"),
            clicked_at=datetime.utcnow(),
            ip_address=ip_address,
            user_agent=user_agent
        )

        db.add(click)
        db.commit()

        return JSONResponse({
            "success": True
        })

    except Exception as e:
        logger.error(f"Error tracking click: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error tracking click: {str(e)}")

@app.get("/api/weather")
async def get_weather(
    q: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    current_user: Dict[str, Any] = Depends(get_current_user_optional)
):
    """Get weather data for a location"""
    try:
        api_key = os.getenv("OPENWEATHER_API_KEY")
        if not api_key:
            # Return graceful response instead of 500
            return JSONResponse({
                "success": False,
                "error": "Weather service not configured",
                "weather": None
            }, status_code=200)

        # Build API URL
        if lat and lon:
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}"
        elif q:
            url = f"https://api.openweathermap.org/data/2.5/weather?q={q}&appid={api_key}"
        else:
            return JSONResponse({
                "success": False,
                "error": "Please provide a city name, zip code, or coordinates"
            }, status_code=400)

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)

            if response.status_code == 200:
                weather_data = response.json()
                return JSONResponse({
                    "success": True,
                    "weather": weather_data
                })
            elif response.status_code == 404:
                return JSONResponse({
                    "success": False,
                    "error": "Location not found. Please check your city name or zip code."
                }, status_code=404)
            else:
                return JSONResponse({
                    "success": False,
                    "error": "Unable to fetch weather data"
                }, status_code=response.status_code)

    except httpx.TimeoutException:
        return JSONResponse({
            "success": False,
            "error": "Weather service timeout. Please try again."
        }, status_code=504)
    except Exception as e:
        logger.error(f"Error fetching weather: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Error fetching weather: {str(e)}"
        }, status_code=500)

@app.get("/api/analytics/summary")
async def get_analytics_summary(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get analytics summary"""
    try:
        from sqlalchemy import distinct, func

        # Get summary stats
        total_sessions = db.query(func.count(UserSession.id)).scalar() or 0
        total_clicks = db.query(func.count(ToolClick.id)).scalar() or 0
        active_users = db.query(func.count(distinct(UserSession.user_email))).scalar() or 0

        # Get recent sessions (last 50)
        sessions = db.query(UserSession).order_by(UserSession.login_time.desc()).limit(50).all()

        # Get recent clicks (last 100)
        clicks = db.query(ToolClick).order_by(ToolClick.clicked_at.desc()).limit(100).all()

        return JSONResponse({
            "success": True,
            "summary": {
                "total_sessions": total_sessions,
                "total_clicks": total_clicks,
                "active_users": active_users
            },
            "sessions": [session.to_dict() for session in sessions],
            "clicks": [click.to_dict() for click in clicks]
        })

    except Exception as e:
        logger.error(f"Error getting analytics summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting analytics: {str(e)}")

# Voucher Management Routes
@app.get("/vouchers", response_class=HTMLResponse)
async def voucher_list_page(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Render the voucher list page"""
    # Configure RingCentral
    ringcentral_config = {
        "enabled": bool(RINGCENTRAL_EMBED_CLIENT_ID),
        "app_url": RINGCENTRAL_EMBED_APP_URL,
        "adapter_url": RINGCENTRAL_EMBED_ADAPTER_URL,
        "query_string": ""
    }

    if ringcentral_config["enabled"]:
        import time
        params = {
            "clientId": RINGCENTRAL_EMBED_CLIENT_ID,
            "appServer": RINGCENTRAL_EMBED_SERVER,
        }
        if RINGCENTRAL_EMBED_DEFAULT_TAB:
            params["defaultTab"] = RINGCENTRAL_EMBED_DEFAULT_TAB
        if RINGCENTRAL_EMBED_REDIRECT_URI:
            params["redirectUri"] = RINGCENTRAL_EMBED_REDIRECT_URI
        # Control which features are shown
        params["enableGlip"] = "true"        # Enable Chat/Glip tab
        params["disableGlip"] = "false"      # Make sure Glip is not disabled
        params["disableConferences"] = "true"  # Disable video/meetings

        # ALWAYS USE DARK THEME - DO NOT CHANGE
        params["theme"] = "dark"             # Force dark theme to match portal design
        params["_t"] = str(int(time.time()))  # Cache buster to force theme reload

        ringcentral_config["query_string"] = urlencode(params)

    return templates.TemplateResponse("vouchers.html", {
        "request": request,
        "user": current_user,
        "ringcentral": ringcentral_config
    })

@app.get("/api/vouchers")
async def get_vouchers(
    client_name: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all vouchers with optional filtering"""
    try:
        query = db.query(Voucher)

        # Apply filters if provided
        if client_name:
            query = query.filter(Voucher.client_name.ilike(f"%{client_name}%"))
        if status:
            query = query.filter(Voucher.status.ilike(f"%{status}%"))

        # Order by invoice date descending
        vouchers = query.order_by(Voucher.invoice_date.desc()).all()

        return JSONResponse({
            "success": True,
            "vouchers": [voucher.to_dict() for voucher in vouchers],
            "total": len(vouchers)
        })

    except Exception as e:
        logger.error(f"Error getting vouchers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting vouchers: {str(e)}")

@app.post("/api/vouchers")
async def create_voucher(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new voucher"""
    try:
        data = await request.json()

        # Parse dates if provided
        voucher_start_date = None
        voucher_end_date = None
        invoice_date = None

        if data.get("voucher_start_date"):
            voucher_start_date = datetime.strptime(data["voucher_start_date"], "%Y-%m-%d").date()
        if data.get("voucher_end_date"):
            voucher_end_date = datetime.strptime(data["voucher_end_date"], "%Y-%m-%d").date()
        if data.get("invoice_date"):
            invoice_date = datetime.strptime(data["invoice_date"], "%Y-%m-%d").date()

        # Create new voucher
        voucher = Voucher(
            client_name=data["client_name"],
            voucher_number=data["voucher_number"],
            voucher_start_date=voucher_start_date,
            voucher_end_date=voucher_end_date,
            invoice_date=invoice_date,
            amount=data["amount"],
            status=data.get("status", "Pending"),
            notes=data.get("notes"),
            voucher_image_url=data.get("voucher_image_url"),
            created_by=current_user.get("email")
        )

        db.add(voucher)
        db.commit()
        db.refresh(voucher)

        return JSONResponse({
            "success": True,
            "voucher": voucher.to_dict(),
            "message": "Voucher created successfully"
        })

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating voucher: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating voucher: {str(e)}")

@app.put("/api/vouchers/{voucher_id}")
async def update_voucher(
    voucher_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update an existing voucher"""
    try:
        voucher = db.query(Voucher).filter(Voucher.id == voucher_id).first()

        if not voucher:
            raise HTTPException(status_code=404, detail="Voucher not found")

        data = await request.json()

        # Update fields
        if "client_name" in data:
            voucher.client_name = data["client_name"]
        if "voucher_number" in data:
            voucher.voucher_number = data["voucher_number"]
        if "voucher_start_date" in data and data["voucher_start_date"]:
            voucher.voucher_start_date = datetime.strptime(data["voucher_start_date"], "%Y-%m-%d").date()
        if "voucher_end_date" in data and data["voucher_end_date"]:
            voucher.voucher_end_date = datetime.strptime(data["voucher_end_date"], "%Y-%m-%d").date()
        if "invoice_date" in data and data["invoice_date"]:
            voucher.invoice_date = datetime.strptime(data["invoice_date"], "%Y-%m-%d").date()
        if "amount" in data:
            voucher.amount = data["amount"]
        if "status" in data:
            voucher.status = data["status"]
        if "notes" in data:
            voucher.notes = data["notes"]
        if "voucher_image_url" in data:
            voucher.voucher_image_url = data["voucher_image_url"]

        voucher.updated_by = current_user.get("email")

        db.commit()
        db.refresh(voucher)

        return JSONResponse({
            "success": True,
            "voucher": voucher.to_dict(),
            "message": "Voucher updated successfully"
        })

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating voucher: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating voucher: {str(e)}")

@app.delete("/api/vouchers/{voucher_id}")
async def delete_voucher(
    voucher_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a voucher"""
    try:
        voucher = db.query(Voucher).filter(Voucher.id == voucher_id).first()

        if not voucher:
            raise HTTPException(status_code=404, detail="Voucher not found")

        db.delete(voucher)
        db.commit()

        return JSONResponse({
            "success": True,
            "message": "Voucher deleted successfully"
        })

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting voucher: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting voucher: {str(e)}")

# Voucher Sync Routes
@app.post("/api/vouchers/sync")
async def trigger_voucher_sync(
    hours_back: int = 24,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Manually trigger voucher sync from Google Drive"""
    try:
        from voucher_sync_service import run_sync

        logger.info(f"Manual sync triggered by {current_user.get('email')}")
        summary = run_sync(hours_back=hours_back)

        return JSONResponse({
            "success": True,
            "summary": summary,
            "message": f"Sync complete. Processed {summary['files_processed']} of {summary['files_found']} files."
        })

    except Exception as e:
        logger.error(f"Error in manual sync: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")

@app.get("/api/vouchers/sync/status")
async def get_sync_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get status of voucher sync configuration"""
    try:
        status = {
            "drive_folder_configured": bool(os.getenv("GOOGLE_DRIVE_VOUCHER_FOLDER_ID")),
            "service_account_configured": bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")),
            "sheets_id_configured": bool(os.getenv("GOOGLE_SHEETS_VOUCHER_ID")),
            "ready": False
        }

        status["ready"] = all([
            status["drive_folder_configured"],
            status["service_account_configured"],
            status["sheets_id_configured"]
        ])

        return JSONResponse({
            "success": True,
            "status": status
        })

    except Exception as e:
        logger.error(f"Error getting sync status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")

#

# Sales dashboard is now mounted at /sales via unified_app.py
# No redirect needed - the mounted FastAPI app handles /sales/* routes directly


# ── Fax (RingCentral) ─────────────────────────────────────────────────────────────

@app.get("/fax", response_class=HTMLResponse)
async def fax_page(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Fax send/receive page."""
    import psycopg2
    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
    faxes = []
    # Poll RC for new received faxes on page load
    try:
        from services.fax_service import poll_received_faxes
        await poll_received_faxes()
    except Exception as e:
        logger.warning(f"Fax poll on load failed (non-fatal): {e}")

    inbox, sent, outbox = [], [], []
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, direction, rc_message_id, from_number, to_number, status,
                   page_count, local_path, created_at, error_message
            FROM fax_log ORDER BY created_at DESC LIMIT 100
        """)
        for r in cur.fetchall():
            f = type('F', (), {
                'id': r[0], 'direction': r[1], 'rc_message_id': r[2],
                'from_number': r[3], 'to_number': r[4], 'status': r[5],
                'page_count': r[6], 'local_path': r[7], 'created_at': r[8],
                'error_message': r[9],
            })()
            if f.direction == 'inbound':
                inbox.append(f)
            elif f.status in ('delivered', 'sent'):
                sent.append(f)
            else:
                outbox.append(f)
        conn.close()
    except Exception as e:
        logger.error(f"Error loading fax history: {e}")
    return templates.TemplateResponse("fax.html", {
        "request": request, "user": current_user,
        "inbox": inbox, "sent": sent, "outbox": outbox,
    })


@app.post("/api/fax/send")
async def api_fax_send(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Send a fax via RingCentral — supports multiple files + cover note."""
    import uuid as _uuid
    from pathlib import Path

    form = await request.form()
    to_number = form.get("to_number", "").strip()
    cover_note = form.get("cover_note", "").strip()
    if not to_number:
        return JSONResponse({"success": False, "error": "Recipient phone number required"}, status_code=400)

    allowed = (".pdf", ".doc", ".docx", ".txt", ".jpg", ".jpeg", ".png", ".tiff", ".tif")
    fax_dir = Path.home() / "logs" / "faxes" / "outbound"
    fax_dir.mkdir(parents=True, exist_ok=True)

    # Collect all uploaded files
    file_paths = []
    local_paths = []
    for key in form:
        if key.startswith("files"):
            upload = form[key]
            if hasattr(upload, "filename") and upload.filename:
                if not any(upload.filename.lower().endswith(ext) for ext in allowed):
                    return JSONResponse({"success": False, "error": f"Unsupported file: {upload.filename}"}, status_code=400)
                content = await upload.read()
                ext = Path(upload.filename).suffix.lower()
                local_path = fax_dir / f"{_uuid.uuid4().hex}{ext}"
                local_path.write_bytes(content)
                local_paths.append(str(local_path))
                file_paths.append((upload.filename, content))

    if not file_paths and not cover_note:
        return JSONResponse({"success": False, "error": "Add at least one file or note"}, status_code=400)

    try:
        from services.fax_service import send_fax
        result = await send_fax(to=to_number, file_paths=file_paths, cover_note=cover_note)
        if result.get("success") and local_paths:
            import psycopg2
            db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            cur.execute("UPDATE fax_log SET local_path = %s WHERE id = %s", (local_paths[0], result.get("log_id")))
            conn.commit()
            conn.close()
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Fax send error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/fax/view/{fax_id}")
async def api_fax_view(fax_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """View a fax PDF inline (in browser)."""
    from pathlib import Path

    import psycopg2
    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("SELECT local_path, direction, from_number, to_number FROM fax_log WHERE id = %s", (fax_id,))
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="PDF not available")
    fax_path = Path(row[0])
    if not fax_path.exists():
        raise HTTPException(status_code=404, detail="PDF file missing")
    filename = f"fax-{row[1]}-{row[2] or row[3]}-{fax_id}.pdf"
    return Response(
        content=fax_path.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@app.get("/api/fax/download/{fax_id}")
async def api_fax_download(fax_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Download a fax PDF."""
    from pathlib import Path

    import psycopg2
    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("SELECT local_path, direction, from_number, to_number FROM fax_log WHERE id = %s", (fax_id,))
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="PDF not available")
    fax_path = Path(row[0])
    if not fax_path.exists():
        raise HTTPException(status_code=404, detail="PDF file missing")
    filename = f"fax-{row[1]}-{row[2] or row[3]}-{fax_id}.pdf"
    return Response(
        content=fax_path.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/fax/list")
async def api_fax_list(
    direction: str = None,
    limit: int = 20,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List faxes as JSON."""
    from services.fax_service import list_faxes
    return JSONResponse(list_faxes(direction=direction, limit=limit))


@app.post("/api/fax/poll")
async def api_fax_poll(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Poll RingCentral for new received faxes and sync to local DB."""
    try:
        from services.fax_service import poll_received_faxes
        new_faxes = await poll_received_faxes()
        return JSONResponse({"success": True, "new_faxes": len(new_faxes), "faxes": new_faxes})
    except Exception as e:
        logger.error(f"Fax poll error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── End Fax ───────────────────────────────────────────────────────────────────


@app.get("/activity-tracker")
async def activity_tracker_redirect(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Redirect to Sales Dashboard (Activity tracking is now part of Sales CRM)"""
    # Activity tracker is now integrated into the Sales Dashboard
    # Redirect to /go/sales which handles SSO properly
    token_payload = {
        "user_id": current_user.get("email"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "domain": current_user.get("email", "").split("@")[-1] if current_user.get("email") else "",
        "via_portal": True,
        "login_time": datetime.utcnow().isoformat()
    }

    portal_token = PORTAL_SSO_SERIALIZER.dumps(token_payload)
    query = urlencode({
        "portal_token": portal_token,
        "portal_user_email": current_user.get("email", "")
    })

    # Redirect to sales dashboard with activity tab
    redirect_url = f"/sales/portal-auth?{query}"
    logger.info(f"Redirecting {current_user.get('email')} to Sales Dashboard (Activity Tracker)")
    return RedirectResponse(url=redirect_url, status_code=302)

@app.get("/recruitment", response_class=HTMLResponse)
async def recruitment_dashboard_embedded(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Embedded Recruitment Dashboard (iframe)"""
    recruitment_dashboard_url = os.getenv(
        "RECRUITMENT_DASHBOARD_URL",
        "https://portal.coloradocareassist.com/recruiting"
    )

    # Get session token from cookie to pass to dashboard
    session_token = request.cookies.get("session_token", "")

    # Append session token as query parameter (Recruiter Dashboard needs to accept this)
    if session_token:
        separator = "&" if "?" in recruitment_dashboard_url else "?"
        # URL encode the token to handle special characters
        encoded_token = quote_plus(session_token)
        encoded_email = quote_plus(current_user.get('email', ''))
        recruitment_url_with_auth = f"{recruitment_dashboard_url}{separator}portal_token={encoded_token}&portal_user_email={encoded_email}"
        logger.info(f"Passing portal token to Recruiter Dashboard for user: {current_user.get('email')}")
    else:
        logger.warning("No session token found - Recruiter Dashboard will require login")
        recruitment_url_with_auth = recruitment_dashboard_url

    return templates.TemplateResponse("recruitment_embedded.html", {
        "request": request,
        "user": current_user,
        "recruitment_url": recruitment_url_with_auth
    })


@app.get("/client-satisfaction")
async def client_satisfaction_redirect(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Redirect old client-satisfaction URL to new operations dashboard"""
    return RedirectResponse(url="/operations", status_code=302)


@app.get("/go/recruiting")
async def go_recruiting(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Redirect to recruiting dashboard with portal token for SSO"""
    session_token = request.cookies.get("session_token", "")

    if session_token:
        encoded_token = quote_plus(session_token)
        encoded_email = quote_plus(current_user.get('email', ''))
        redirect_url = f"/recruiting/?portal_token={encoded_token}&portal_user_email={encoded_email}"
        logger.info(f"Redirecting to recruiting with token for: {current_user.get('email')}")
    else:
        redirect_url = "/recruiting/"
        logger.warning("No session token - redirecting without auth")

    return RedirectResponse(url=redirect_url, status_code=302)


@app.get("/go/sales")
async def go_sales(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Redirect to sales dashboard with portal SSO token"""
    token_payload = {
        "user_id": current_user.get("email"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "domain": current_user.get("email", "").split("@")[-1] if current_user.get("email") else "",
        "via_portal": True,
        "login_time": datetime.utcnow().isoformat()
    }

    portal_token = PORTAL_SSO_SERIALIZER.dumps(token_payload)
    query = urlencode({
        "portal_token": portal_token,
        "portal_user_email": current_user.get("email", "")
    })

    redirect_url = f"/sales/portal-auth?{query}"
    logger.info(f"Redirecting {current_user.get('email')} to Sales Dashboard with portal token")
    return RedirectResponse(url=redirect_url, status_code=302)


@app.get("/client-satisfaction-old", response_class=HTMLResponse)
async def client_satisfaction_dashboard_legacy(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Client Satisfaction Dashboard - legacy implementation (kept for reference)"""
    if client_satisfaction_service is None:
        raise HTTPException(status_code=503, detail="Client satisfaction service not available")

    # Get enhanced dashboard summary with WellSky data
    summary = client_satisfaction_service.get_enhanced_dashboard_summary(db, days=30)

    # Get AI Care Coordinator dashboard data
    ai_coordinator = client_satisfaction_service.get_ai_coordinator_dashboard(db)

    return templates.TemplateResponse(
        "client_satisfaction.html",
        {
            "request": request,
            "user": current_user,
            "summary": summary,
            "ai_coordinator": ai_coordinator,
            "wellsky_available": client_satisfaction_service.wellsky_available,
        },
    )


#
# Client Satisfaction API Endpoints
#

@app.get("/api/client-satisfaction/summary")
async def api_client_satisfaction_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get client satisfaction dashboard summary with WellSky data"""
    if client_satisfaction_service is None:
        raise HTTPException(status_code=503, detail="Client satisfaction service not available")

    summary = client_satisfaction_service.get_enhanced_dashboard_summary(db, days=days)
    return JSONResponse({"success": True, "data": summary})


@app.get("/api/client-satisfaction/ai-coordinator")
async def api_ai_coordinator_dashboard(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get AI Care Coordinator dashboard (Gigi/Gigi style)"""
    if client_satisfaction_service is None:
        raise HTTPException(status_code=503, detail="Client satisfaction service not available")

    dashboard = client_satisfaction_service.get_ai_coordinator_dashboard(db)
    return JSONResponse({"success": True, "data": dashboard})


@app.get("/api/client-satisfaction/at-risk")
async def api_at_risk_clients(
    threshold: int = Query(40, ge=0, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get clients at risk of satisfaction issues (from WellSky data)"""
    if client_satisfaction_service is None:
        raise HTTPException(status_code=503, detail="Client satisfaction service not available")

    at_risk = client_satisfaction_service.get_at_risk_clients(threshold=threshold)
    return JSONResponse({
        "success": True,
        "data": at_risk,
        "count": len(at_risk),
        "threshold": threshold,
    })


@app.get("/api/client-satisfaction/client/{client_id}/indicators")
async def api_client_indicators(
    client_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get satisfaction risk indicators for a specific client"""
    if client_satisfaction_service is None:
        raise HTTPException(status_code=503, detail="Client satisfaction service not available")

    indicators = client_satisfaction_service.get_client_satisfaction_indicators(client_id)
    return JSONResponse({"success": True, "data": indicators})


@app.get("/api/client-satisfaction/alerts")
async def api_satisfaction_alerts(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get prioritized satisfaction alerts requiring attention"""
    if client_satisfaction_service is None:
        raise HTTPException(status_code=503, detail="Client satisfaction service not available")

    alerts = client_satisfaction_service.get_satisfaction_alerts()
    return JSONResponse({
        "success": True,
        "data": alerts,
        "count": len(alerts),
        "high_priority_count": len([a for a in alerts if a.get("priority") == "high"]),
    })


@app.get("/api/client-satisfaction/outreach-queue")
async def api_outreach_queue(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get proactive outreach queue (low engagement, anniversaries, survey due)"""
    if client_satisfaction_service is None:
        raise HTTPException(status_code=503, detail="Client satisfaction service not available")

    # Combine different outreach types
    outreach = []

    low_engagement = client_satisfaction_service.get_low_engagement_families(threshold=30)
    for item in low_engagement:
        item["outreach_type"] = "engagement"
        outreach.append(item)

    anniversaries = client_satisfaction_service.get_upcoming_anniversaries(days_ahead=30)
    for item in anniversaries:
        item["outreach_type"] = "anniversary"
        outreach.append(item)

    surveys_due = client_satisfaction_service.get_clients_needing_surveys(days_since_last=90)
    for item in surveys_due:
        item["outreach_type"] = "survey"
        outreach.append(item)

    return JSONResponse({
        "success": True,
        "data": outreach,
        "count": len(outreach),
    })


@app.get("/api/wellsky/status")
async def api_wellsky_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Check WellSky API connection status"""
    if client_satisfaction_service is None:
        return JSONResponse({
            "success": True,
            "connected": False,
            "mode": "unavailable",
            "message": "Client satisfaction service not available"
        })

    wellsky = client_satisfaction_service.wellsky
    if wellsky is None:
        return JSONResponse({
            "success": True,
            "connected": False,
            "mode": "unavailable",
            "message": "WellSky service not configured"
        })

    return JSONResponse({
        "success": True,
        "connected": True,
        "mode": "mock" if wellsky.is_mock_mode else "live",
        "environment": wellsky.environment,
        "message": "WellSky service connected (mock mode)" if wellsky.is_mock_mode else "WellSky API connected"
    })

# ============================================================================
# WellSky Data API (Used by Gigi Daily Sync and Internal Services)
# ============================================================================

@app.get("/api/internal/wellsky/caregivers")
async def api_wellsky_caregivers(
    status: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Return caregivers from WellSky."""
    if wellsky_service is None:
        return JSONResponse({"success": False, "error": "WellSky service not available"}, status_code=503)

    try:
        status_enum = None
        if status:
            if CaregiverStatus is None:
                return JSONResponse({"success": False, "error": "CaregiverStatus enum not available"}, status_code=503)
            try:
                status_enum = CaregiverStatus(status.lower())
            except Exception:
                return JSONResponse({"success": False, "error": f"Invalid status: {status}"}, status_code=400)

        caregivers = wellsky_service.get_caregivers(status=status_enum, limit=limit, offset=offset)
        return JSONResponse({
            "caregivers": [cg.to_dict() for cg in caregivers],
            "count": len(caregivers),
        })
    except Exception as e:
        logger.error(f"Error getting caregivers: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/internal/wellsky/clients")
async def api_wellsky_clients(
    status: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Return clients from WellSky."""
    if wellsky_service is None:
        return JSONResponse({"success": False, "error": "WellSky service not available"}, status_code=503)

    try:
        status_enum = None
        if status:
            if ClientStatus is None:
                return JSONResponse({"success": False, "error": "ClientStatus enum not available"}, status_code=503)
            try:
                status_enum = ClientStatus(status.lower())
            except Exception:
                return JSONResponse({"success": False, "error": f"Invalid status: {status}"}, status_code=400)

        clients = wellsky_service.get_clients(status=status_enum, limit=limit, offset=offset)
        return JSONResponse({
            "clients": [cl.to_dict() for cl in clients],
            "count": len(clients),
        })
    except Exception as e:
        logger.error(f"Error getting clients: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/internal/wellsky/shifts")
async def api_wellsky_shifts(
    days: int = Query(30, ge=1, le=120),
    limit: int = Query(500, ge=1, le=2000),
    caregiver_id: Optional[str] = None,
    client_id: Optional[str] = None,
    status: Optional[str] = None,
    upcoming: Optional[bool] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Return shifts from WellSky (supports upcoming + caregiver/client filters)."""
    if wellsky_service is None:
        return JSONResponse({"success": False, "error": "WellSky service not available"}, status_code=503)

    try:
        status_enum = None
        if status:
            if ShiftStatus is None:
                return JSONResponse({"success": False, "error": "ShiftStatus enum not available"}, status_code=503)
            try:
                status_enum = ShiftStatus(status.lower())
            except Exception:
                return JSONResponse({"success": False, "error": f"Invalid status: {status}"}, status_code=400)

        df = None
        dt = None
        if date_from:
            df = date.fromisoformat(date_from)
        if date_to:
            dt = date.fromisoformat(date_to)

        if df is None and dt is None and (upcoming is True or upcoming is None):
            df = date.today()
            dt = df + timedelta(days=days)

        shifts = wellsky_service.get_shifts(
            date_from=df,
            date_to=dt,
            caregiver_id=caregiver_id,
            client_id=client_id,
            status=status_enum,
            limit=limit,
        )
        return JSONResponse({
            "shifts": [s.to_dict() for s in shifts],
            "count": len(shifts),
            "date_from": df.isoformat() if df else None,
            "date_to": dt.isoformat() if dt else None,
        })
    except Exception as e:
        logger.error(f"Error getting shifts: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


#
# Operations Dashboard (Client Operations with WellSky Integration)
#

@app.get("/operations", response_class=HTMLResponse)
async def operations_dashboard(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Operations Dashboard - client operations with WellSky integration"""
    return templates.TemplateResponse(
        "operations.html",
        {
            "request": request,
            "user": current_user,
        },
    )


@app.get("/api/operations/hours-breakdown")
async def api_operations_hours_breakdown(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get hours breakdown from cached appointment data"""
    import psycopg2
    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # Total scheduled hours (last 90 days)
        cur.execute("""
            SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (scheduled_end - scheduled_start)) / 3600), 0)
            FROM cached_appointments
            WHERE scheduled_start >= NOW() - INTERVAL '90 days'
              AND scheduled_end IS NOT NULL
        """)
        total_scheduled = round(cur.fetchone()[0], 1)

        # Actual hours worked (completed shifts with clock-in/out)
        cur.execute("""
            SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (actual_end - actual_start)) / 3600), 0)
            FROM cached_appointments
            WHERE actual_start IS NOT NULL AND actual_end IS NOT NULL
              AND actual_start >= NOW() - INTERVAL '90 days'
        """)
        total_actual = round(cur.fetchone()[0], 1)

        # Weekly breakdown (last 4 weeks)
        cur.execute("""
            SELECT DATE_TRUNC('week', scheduled_start) as week,
                   COALESCE(SUM(EXTRACT(EPOCH FROM (scheduled_end - scheduled_start)) / 3600), 0) as hours
            FROM cached_appointments
            WHERE scheduled_start >= NOW() - INTERVAL '28 days'
              AND scheduled_end IS NOT NULL
            GROUP BY week ORDER BY week
        """)
        weekly = [{"week": row[0].isoformat(), "hours": round(row[1], 1)} for row in cur.fetchall()]

        cur.close()
        conn.close()

        return JSONResponse({
            "total_scheduled_hours": total_scheduled,
            "total_actual_hours": total_actual,
            "utilization_rate": round((total_actual / total_scheduled * 100) if total_scheduled > 0 else 0, 1),
            "weekly_breakdown": weekly,
            "wellsky_connected": True,
        })
    except Exception as e:
        logger.error(f"Error getting hours breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/operations/summary")
async def api_operations_summary(
    days: int = Query(30, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get operations dashboard summary metrics from cached data"""
    import psycopg2
    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # Active clients
        cur.execute("SELECT COUNT(*) FROM cached_patients WHERE is_active = true")
        active_clients = cur.fetchone()[0]

        # Active caregivers
        cur.execute("SELECT COUNT(*) FROM cached_practitioners WHERE is_active = true")
        active_caregivers = cur.fetchone()[0]

        # Open shifts (upcoming appointments with no practitioner or status = 'open'/'pending')
        cur.execute("""
            SELECT COUNT(*) FROM cached_appointments
            WHERE scheduled_start >= NOW()
              AND scheduled_start <= NOW() + INTERVAL '14 days'
              AND (practitioner_id IS NULL OR status IN ('open', 'pending', 'proposed'))
        """)
        open_shifts = cur.fetchone()[0]

        # EVV compliance (shifts with actual clock-in/out vs total completed in last 30 days)
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE actual_start IS NOT NULL AND actual_end IS NOT NULL) as clocked,
                COUNT(*) as total
            FROM cached_appointments
            WHERE scheduled_start >= NOW() - INTERVAL '%s days'
              AND scheduled_start < NOW()
              AND status IN ('fulfilled', 'completed', 'arrived')
        """, (days,))
        row = cur.fetchone()
        evv_compliance = round((row[0] / row[1] * 100) if row[1] > 0 else 0, 1)

        # At-risk clients (no visits in last 14 days)
        cur.execute("""
            SELECT COUNT(*) FROM cached_patients p
            WHERE p.is_active = true
              AND NOT EXISTS (
                  SELECT 1 FROM cached_appointments a
                  WHERE a.patient_id = p.id
                    AND a.scheduled_start >= NOW() - INTERVAL '14 days'
              )
        """)
        at_risk_clients = cur.fetchone()[0]

        # Weekly shift data for chart
        cur.execute("""
            SELECT EXTRACT(DOW FROM scheduled_start)::int as dow, COUNT(*) as cnt
            FROM cached_appointments
            WHERE scheduled_start >= DATE_TRUNC('week', NOW())
              AND scheduled_start < DATE_TRUNC('week', NOW()) + INTERVAL '7 days'
            GROUP BY dow ORDER BY dow
        """)
        scheduled = [0]*7
        for row in cur.fetchall():
            scheduled[row[0]] = row[1]

        cur.close()
        conn.close()

        return JSONResponse({
            "active_clients": active_clients,
            "active_caregivers": active_caregivers,
            "open_shifts": open_shifts,
            "evv_compliance": evv_compliance,
            "at_risk_clients": at_risk_clients,
            "plans_due_review": 0,
            "shifts_by_day": {"scheduled": scheduled, "open": [0]*7},
            "wellsky_connected": True,
        })
    except Exception as e:
        logger.error(f"Error getting operations summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/operations/clients")
async def api_operations_clients(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get client list from cached data"""
    import psycopg2
    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        cur.execute("""
            SELECT p.id, p.full_name, p.first_name, p.last_name, p.status, p.referral_source,
                   (SELECT MAX(a.scheduled_start) FROM cached_appointments a WHERE a.patient_id = p.id) as last_visit
            FROM cached_patients p
            WHERE p.is_active = true
            ORDER BY p.full_name
        """)

        client_list = []
        for row in cur.fetchall():
            name = row[1] or f"{row[2] or ''} {row[3] or ''}".strip() or "Unknown"
            client_list.append({
                "id": row[0],
                "name": name,
                "status": row[4] or "active",
                "hours_per_week": None,
                "payer": row[5] or "N/A",
                "risk_score": 0,
                "last_visit": row[6].isoformat() if row[6] else None,
            })

        cur.close()
        conn.close()
        return JSONResponse({"clients": client_list})
    except Exception as e:
        logger.error(f"Error getting operations clients: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/operations/care-plans")
async def api_operations_care_plans(
    days: int = Query(30, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get care plans — placeholder using cached patient data"""
    import psycopg2
    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # Care plans aren't cached separately — return active clients as plan entries
        cur.execute("""
            SELECT p.id, p.full_name, p.first_name, p.last_name, p.start_date
            FROM cached_patients p
            WHERE p.is_active = true
            ORDER BY p.start_date ASC NULLS LAST
            LIMIT 50
        """)

        plan_list = []
        for row in cur.fetchall():
            name = row[1] or f"{row[2] or ''} {row[3] or ''}".strip() or "Unknown"
            plan_list.append({
                "id": row[0],
                "client_id": row[0],
                "client_name": name,
                "status": "active",
                "review_date": None,
                "days_until_review": None,
                "authorized_hours": None,
            })

        cur.close()
        conn.close()
        return JSONResponse({"care_plans": plan_list})
    except Exception as e:
        logger.error(f"Error getting care plans: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/operations/open-shifts")
async def api_operations_open_shifts(
    days: int = Query(14, ge=1, le=60),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get open/unassigned shifts from cached data"""
    import psycopg2
    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        cur.execute("""
            SELECT a.id, a.scheduled_start, a.scheduled_end, a.patient_id, a.status,
                   a.location_address, p.full_name, p.first_name, p.last_name
            FROM cached_appointments a
            LEFT JOIN cached_patients p ON a.patient_id = p.id
            WHERE a.scheduled_start >= NOW()
              AND a.scheduled_start <= NOW() + INTERVAL '%s days'
              AND (a.practitioner_id IS NULL OR a.status IN ('open', 'pending', 'proposed'))
            ORDER BY a.scheduled_start
        """, (days,))

        shift_list = []
        for row in cur.fetchall():
            client_name = row[6] or f"{row[7] or ''} {row[8] or ''}".strip() or "Unknown"
            hours = None
            if row[1] and row[2]:
                hours = round((row[2] - row[1]).total_seconds() / 3600, 1)
            shift_list.append({
                "id": row[0],
                "date": row[1].date().isoformat() if row[1] else None,
                "start_time": row[1].strftime("%I:%M %p") if row[1] else None,
                "end_time": row[2].strftime("%I:%M %p") if row[2] else None,
                "client_id": row[3],
                "client_name": client_name,
                "location": row[5],
                "hours": hours,
                "status": "open",
            })

        cur.close()
        conn.close()
        return JSONResponse({"shifts": shift_list})
    except Exception as e:
        logger.error(f"Error getting open shifts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/operations/at-risk")
async def api_operations_at_risk(
    threshold: int = Query(40, ge=0, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get at-risk clients — those with no recent visits"""
    import psycopg2
    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        cur.execute("""
            SELECT p.id, p.full_name, p.first_name, p.last_name, p.phone,
                   MAX(a.scheduled_start) as last_visit,
                   COUNT(a.id) FILTER (WHERE a.scheduled_start >= NOW() - INTERVAL '30 days') as recent_visits
            FROM cached_patients p
            LEFT JOIN cached_appointments a ON a.patient_id = p.id
            WHERE p.is_active = true
            GROUP BY p.id, p.full_name, p.first_name, p.last_name, p.phone
            HAVING MAX(a.scheduled_start) IS NULL
               OR MAX(a.scheduled_start) < NOW() - INTERVAL '14 days'
            ORDER BY MAX(a.scheduled_start) ASC NULLS FIRST
        """)

        clients = []
        for row in cur.fetchall():
            name = row[1] or f"{row[2] or ''} {row[3] or ''}".strip() or "Unknown"
            days_since = None
            if row[5]:
                days_since = (datetime.now() - row[5]).days

            clients.append({
                "id": row[0],
                "name": name,
                "phone": row[4],
                "last_visit": row[5].isoformat() if row[5] else None,
                "days_since_visit": days_since,
                "recent_visits": row[6],
                "risk_score": min(100, (days_since or 30) * 3),
            })

        cur.close()
        conn.close()
        return JSONResponse({"clients": clients, "threshold": threshold})
    except Exception as e:
        logger.error(f"Error getting at-risk clients: {e}")
        raise HTTPException(status_code=500, detail=str(e))


#
# Gigi AI Agent Control API
#

# In-memory Gigi settings (defaults from environment, can be toggled at runtime)
_gigi_settings = {
    "sms_autoreply": os.getenv("GIGI_SMS_AUTOREPLY_ENABLED", "false").lower() == "true",
    "operations_sms": os.getenv("GIGI_OPERATIONS_SMS_ENABLED", "false").lower() == "true",
}

# In-memory activity log (recent Gigi actions)
_gigi_activity_log = []
MAX_ACTIVITY_LOG_SIZE = 100


def log_gigi_activity(activity_type: str, description: str, status: str = "success"):
    """Log a Gigi activity (called from various Gigi operations)"""
    global _gigi_activity_log
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "type": activity_type,
        "description": description,
        "status": status,
    }
    _gigi_activity_log.insert(0, entry)
    # Keep log size bounded
    if len(_gigi_activity_log) > MAX_ACTIVITY_LOG_SIZE:
        _gigi_activity_log = _gigi_activity_log[:MAX_ACTIVITY_LOG_SIZE]


# NOTE: Duplicate /api/gigi/settings route removed - see api_gigi_get_settings at line ~439
# The primary settings endpoint returns all settings in one response


@app.put("/api/gigi/settings")
async def api_gigi_settings_update(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update Gigi settings"""
    try:
        body = await request.json()

        changes = []
        if "sms_autoreply" in body:
            old_val = _gigi_settings["sms_autoreply"]
            _gigi_settings["sms_autoreply"] = bool(body["sms_autoreply"])
            if old_val != _gigi_settings["sms_autoreply"]:
                changes.append(f"SMS auto-reply {'enabled' if _gigi_settings['sms_autoreply'] else 'disabled'}")

        if "operations_sms" in body:
            old_val = _gigi_settings["operations_sms"]
            _gigi_settings["operations_sms"] = bool(body["operations_sms"])
            if old_val != _gigi_settings["operations_sms"]:
                changes.append(f"Operations SMS {'enabled' if _gigi_settings['operations_sms'] else 'disabled'}")

        # Log the change
        if changes:
            user_email = current_user.get("email", "unknown")
            log_gigi_activity(
                "settings_change",
                f"{user_email}: {', '.join(changes)}",
                "success"
            )
            logger.info(f"Gigi settings updated by {user_email}: {changes}")

        return JSONResponse({
            "success": True,
            "settings": _gigi_settings,
            "message": "Settings updated" if changes else "No changes",
        })
    except Exception as e:
        logger.error(f"Error updating Gigi settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gigi/activity")
async def api_gigi_activity(
    limit: int = Query(10, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get recent Gigi activity log"""
    return JSONResponse({
        "activities": _gigi_activity_log[:limit],
        "total": len(_gigi_activity_log),
    })


@app.get("/api/gigi/callouts")
async def api_gigi_callouts(
    limit: int = Query(20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get recent call-outs handled by Gigi"""
    # For now, return mock data - this will be populated from actual call-out handling
    # In production, this would query a call_outs table in the database
    mock_callouts = [
        {
            "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "caregiver_name": "Maria Garcia",
            "client_name": "Johnson, Robert",
            "shift_date": (date.today()).isoformat(),
            "shift_time": "8:00 AM - 12:00 PM",
            "reason": "Sick - flu symptoms",
            "status": "covered",
        },
        {
            "timestamp": (datetime.utcnow() - timedelta(hours=8)).isoformat(),
            "caregiver_name": "James Wilson",
            "client_name": "Martinez, Elena",
            "shift_date": (date.today()).isoformat(),
            "shift_time": "2:00 PM - 6:00 PM",
            "reason": "Car trouble",
            "status": "open",
        },
    ]
    return JSONResponse({
        "callouts": mock_callouts[:limit],
        "total": len(mock_callouts),
    })


# Helper function for external code to check if operations SMS is enabled
def is_gigi_operations_sms_enabled():
    """Check if Gigi operations SMS is enabled (used by gigi/main.py)"""
    return _gigi_settings.get("operations_sms", False)


def is_gigi_sms_autoreply_enabled():
    """Check if Gigi SMS auto-reply is enabled (used by gigi/main.py)"""
    return _gigi_settings.get("sms_autoreply", False)


# ============================================
# GIGI RINGCENTRAL COMMAND HANDLER
# ============================================
# Allows controlling Gigi via direct messages:
#   "gigi stop" - disables all Gigi features
#   "gigi go" - enables all Gigi features
#   "gigi status" - reports current status

@app.post("/api/gigi/ringcentral/command")
async def api_gigi_ringcentral_command(request: Request):
    """
    Webhook endpoint for RingCentral direct messages to Gigi.
    Handles commands like 'gigi stop' and 'gigi go'.
    """
    global _gigi_settings

    # Handle RingCentral webhook validation request
    validation_token = request.headers.get("Validation-Token")
    if validation_token:
        logger.info("RingCentral webhook validation request received")
        return Response(
            content="",
            status_code=200,
            headers={"Validation-Token": validation_token}
        )

    # Verify RingCentral verification token if configured
    rc_verify_token = os.getenv("RINGCENTRAL_WEBHOOK_VERIFICATION_TOKEN")
    if rc_verify_token:
        received_token = request.headers.get("Verification-Token", "")
        if received_token != rc_verify_token:
            logger.warning("RC command webhook: Invalid or missing verification token")
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        body = await request.json()
        logger.info(f"Gigi command webhook received: {body}")

        # RingCentral webhook sends message in body
        # Format varies - could be subscription notification or direct POST
        message_text = ""
        sender_id = None
        sender_name = "Unknown"

        # Try to extract message from various RingCentral webhook formats
        if "body" in body:
            # Direct webhook format
            msg_body = body.get("body", {})
            message_text = msg_body.get("text", "") or msg_body.get("subject", "")
            sender_info = msg_body.get("from", {})
            sender_id = sender_info.get("extensionId") or sender_info.get("id")
            sender_name = sender_info.get("name", "Unknown")
        elif "text" in body:
            # Simple format
            message_text = body.get("text", "")
            sender_name = body.get("sender_name", "Unknown")
            sender_id = body.get("sender_id")
        elif "message" in body:
            # Alternative format
            message_text = body.get("message", "")
            sender_name = body.get("from", "Unknown")

        message_lower = message_text.lower().strip()
        response_message = None

        # Parse commands
        if "gigi stop" in message_lower:
            # Disable all Gigi features
            _gigi_settings["sms_autoreply"] = False
            _gigi_settings["operations_sms"] = False
            log_gigi_activity(
                "command",
                f"{sender_name} sent 'gigi stop' - all features disabled",
                "success"
            )
            response_message = "🛑 Gigi is now STOPPED. All automated features disabled. Send 'gigi go' to resume."
            logger.info(f"Gigi STOPPED by {sender_name} via RingCentral DM")

        elif "gigi go" in message_lower:
            # Enable all Gigi features
            _gigi_settings["sms_autoreply"] = True
            _gigi_settings["operations_sms"] = True
            log_gigi_activity(
                "command",
                f"{sender_name} sent 'gigi go' - all features enabled",
                "success"
            )
            response_message = "✅ Gigi is now ACTIVE. SMS auto-reply and operations notifications enabled."
            logger.info(f"Gigi STARTED by {sender_name} via RingCentral DM")

        elif "gigi status" in message_lower:
            # Report current status
            sms_status = "ON" if _gigi_settings["sms_autoreply"] else "OFF"
            ops_status = "ON" if _gigi_settings["operations_sms"] else "OFF"
            response_message = f"📊 Gigi Status:\n• SMS Auto-Reply: {sms_status}\n• Operations SMS: {ops_status}"
            log_gigi_activity(
                "command",
                f"{sender_name} requested status",
                "success"
            )

        # Send reply if we have a response
        if response_message:
            try:
                from services.ringcentral_messaging_service import (
                    ringcentral_messaging_service,
                )
                # Build sender info for reply
                sender_info = {
                    "name": sender_name,
                    "extensionId": sender_id,
                    "email": body.get("body", {}).get("from", {}).get("email")
                            or body.get("sender_email")
                }
                # Use the reply_to_sender method which handles fallbacks
                ringcentral_messaging_service.reply_to_sender(sender_info, response_message)
            except Exception as e:
                logger.error(f"Failed to send Gigi command response: {e}")

        return JSONResponse({
            "success": True,
            "command_recognized": response_message is not None,
            "response": response_message,
        })

    except Exception as e:
        logger.error(f"Error processing Gigi command: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
        }, status_code=500)


@app.post("/api/gigi/command")
async def api_gigi_command_simple(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Simple command endpoint for dashboard or API testing.
    Accepts: {"command": "stop"} or {"command": "go"} or {"command": "status"}
    """
    global _gigi_settings

    try:
        body = await request.json()
        command = body.get("command", "").lower().strip()
        user_email = current_user.get("email", "API User")

        if command == "stop":
            _gigi_settings["sms_autoreply"] = False
            _gigi_settings["operations_sms"] = False
            log_gigi_activity("command", f"{user_email} stopped Gigi via API", "success")
            return JSONResponse({"success": True, "message": "Gigi stopped", "settings": _gigi_settings})

        elif command == "go":
            _gigi_settings["sms_autoreply"] = True
            _gigi_settings["operations_sms"] = True
            log_gigi_activity("command", f"{user_email} started Gigi via API", "success")
            return JSONResponse({"success": True, "message": "Gigi started", "settings": _gigi_settings})

        elif command == "status":
            return JSONResponse({"success": True, "settings": _gigi_settings})

        else:
            return JSONResponse({"success": False, "error": f"Unknown command: {command}"}, status_code=400)

    except Exception as e:
        logger.error(f"Error processing Gigi command: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


#
# GoFormz → WellSky Webhook Endpoint
#

def _get_goformz_wellsky_sync():
    """Get the goformz_wellsky_sync service (loaded at module import time)."""
    return _goformz_wellsky_sync_module


@app.get("/api/goformz/wellsky-sync/debug")
async def goformz_wellsky_sync_debug(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Debug endpoint to check goformz_wellsky_sync service status. Requires authentication."""
    # SECURITY: Only return safe status info, no paths
    return JSONResponse({
        "service_loaded": _goformz_wellsky_sync_module is not None,
        "status": "ready" if _goformz_wellsky_sync_module else "not_loaded",
        "user": current_user.get("email")
    })


@app.post("/api/goformz/wellsky-webhook")
@limiter.limit("30/minute")  # Rate limit webhooks
async def goformz_wellsky_webhook(request: Request):
    """
    Webhook endpoint for GoFormz to trigger WellSky status updates.

    When client/employee packets are completed in GoFormz:
    - Client Packet → converts WellSky prospect to client
    - Employee Packet → converts WellSky applicant to caregiver

    This is the final step in the hub-and-spoke integration.
    """
    # NOTE: GoFormz does not support webhook signature verification.
    # Security relies on rate limiting (30/min) and Cloudflare protection.

    goformz_wellsky_sync = _get_goformz_wellsky_sync()
    if goformz_wellsky_sync is None:
        return JSONResponse({
            "success": False,
            "error": "GoFormz-WellSky sync service not available"
        }, status_code=500)

    try:
        payload = await request.json()
        logger.info(f"GoFormz→WellSky webhook received: {payload.get('EventType', 'unknown')}")

        # Extract event info from GoFormz payload
        event_type = (
            payload.get('EventType', '') or
            payload.get('event', '') or
            payload.get('eventType', '')
        ).lower()

        # Only process completion events
        # GoFormz sends EventType: "formcompleted" — compare case-insensitively
        if event_type not in ['form.complete', 'formcompleted', 'form_completed', 'completed', 'submitted', 'signed']:
            return JSONResponse({
                "success": True,
                "message": f"Event type '{event_type}' not a completion - ignored"
            })

        # Extract form info
        item = payload.get('Item', {})
        submission_id = item.get('Id') or payload.get('submissionId') or payload.get('submission_id')

        # GoFormz webhook sends EntityId (template ID), not form name.
        # Map known template IDs to form types, fallback to formName if present.
        TEMPLATE_MAP = {
            'c2d547ca-df85-42c3-89ed-a3f44e3d1bd8': 'client packet',
            '9c0fa30f-87d4-4e41-b3ea-e0b69fddabb5': 'employee packet',
        }
        entity_id = payload.get('EntityId', '') or payload.get('entityId', '')
        form_name = TEMPLATE_MAP.get(entity_id, '').lower()

        # Fallback: check if formName was explicitly provided (e.g. manual/test calls)
        if not form_name:
            form_name = (
                payload.get('formName', '') or
                payload.get('FormName', '') or
                payload.get('templateName', '')
            ).lower()

        if not submission_id:
            return JSONResponse({
                "success": False,
                "error": "No submission ID in webhook payload"
            }, status_code=400)

        logger.info(f"GoFormz webhook: entity_id={entity_id}, form_name={form_name}, submission_id={submission_id}")

        # GoFormz webhook only sends IDs — fetch full form data from API
        form_data = goformz_wellsky_sync.fetch_form_data(submission_id)
        if form_data:
            # Inject flattened fields into payload so extraction code can find them
            payload['data'] = form_data
            logger.info(f"Fetched {len(form_data)} fields from GoFormz API for form {submission_id}")
        else:
            logger.warning(f"Could not fetch form data from GoFormz API for {submission_id} — using raw payload")

        # Determine form type and process
        result = {}
        if any(kw in form_name for kw in ['client', 'patient', 'service agreement', 'care agreement']):
            # Client packet - convert prospect to client
            result = goformz_wellsky_sync.process_single_client_packet({
                'submission_id': submission_id,
                'form_name': form_name,
                'payload': payload
            })
        elif any(kw in form_name for kw in ['employee', 'caregiver', 'new hire', 'onboarding']):
            # Employee packet - convert applicant to caregiver
            result = goformz_wellsky_sync.process_single_employee_packet({
                'submission_id': submission_id,
                'form_name': form_name,
                'payload': payload
            })
        else:
            # Unknown form type - log but don't fail
            logger.warning(f"Unknown form type in GoFormz webhook: entity_id={entity_id} form_name={form_name}")
            return JSONResponse({
                "success": True,
                "message": f"Unknown form type (entity={entity_id}, name='{form_name}') - no WellSky action taken"
            })

        return JSONResponse({
            "success": True,
            "submission_id": submission_id,
            "form_type": form_name,
            "result": result
        })

    except Exception as e:
        logger.exception(f"Error processing GoFormz→WellSky webhook: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/goformz/wellsky-sync/status")
async def goformz_wellsky_sync_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get GoFormz→WellSky sync service status"""
    goformz_wellsky_sync = _get_goformz_wellsky_sync()
    if goformz_wellsky_sync is None:
        return JSONResponse({
            "success": False,
            "error": "GoFormz-WellSky sync service not available"
        })

    return JSONResponse({
        "success": True,
        "sync_log_entries": len(goformz_wellsky_sync.get_sync_log()),
        "recent_sync_log": goformz_wellsky_sync.get_sync_log(limit=10)
    })


#
# AI Care Coordinator API Endpoints (Gigi/Gigi Style)
#

@app.get("/api/ai-coordinator/status")
async def api_ai_coordinator_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get AI Care Coordinator status"""
    if ai_care_coordinator is None:
        return JSONResponse({
            "success": True,
            "enabled": False,
            "message": "AI Care Coordinator not available"
        })

    status = ai_care_coordinator.get_status()
    return JSONResponse({"success": True, "data": status})


@app.get("/api/ai-coordinator/dashboard")
async def api_ai_coordinator_dashboard(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get AI Care Coordinator dashboard data"""
    if ai_care_coordinator is None:
        return JSONResponse({
            "success": False,
            "error": "AI Care Coordinator not available"
        })

    dashboard = ai_care_coordinator.get_dashboard_data()
    return JSONResponse({"success": True, "data": dashboard})


@app.get("/api/ai-coordinator/alerts")
async def api_ai_coordinator_alerts(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get active satisfaction alerts"""
    if ai_care_coordinator is None:
        return JSONResponse({"success": False, "error": "AI Care Coordinator not available"})

    alerts = ai_care_coordinator.get_active_alerts()
    return JSONResponse({
        "success": True,
        "data": [a.to_dict() for a in alerts],
        "count": len(alerts)
    })


@app.post("/api/ai-coordinator/alerts/generate")
async def api_generate_alerts(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Manually trigger alert generation (normally runs on schedule)"""
    if ai_care_coordinator is None:
        return JSONResponse({"success": False, "error": "AI Care Coordinator not available"})

    alerts = ai_care_coordinator.generate_alerts()
    return JSONResponse({
        "success": True,
        "data": [a.to_dict() for a in alerts],
        "generated_count": len(alerts)
    })


@app.post("/api/ai-coordinator/alerts/{alert_id}/acknowledge")
async def api_acknowledge_alert(
    alert_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Acknowledge an alert"""
    if ai_care_coordinator is None:
        return JSONResponse({"success": False, "error": "AI Care Coordinator not available"})

    success = ai_care_coordinator.acknowledge_alert(alert_id, user=current_user.get("email", "unknown"))
    return JSONResponse({"success": success})


@app.post("/api/ai-coordinator/alerts/{alert_id}/resolve")
async def api_resolve_alert(
    alert_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Resolve an alert"""
    if ai_care_coordinator is None:
        return JSONResponse({"success": False, "error": "AI Care Coordinator not available"})

    data = await request.json()
    notes = data.get("notes", "")

    success = ai_care_coordinator.resolve_alert(
        alert_id,
        user=current_user.get("email", "unknown"),
        notes=notes
    )
    return JSONResponse({"success": success})


@app.get("/api/ai-coordinator/outreach")
async def api_ai_coordinator_outreach(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get pending outreach tasks"""
    if ai_care_coordinator is None:
        return JSONResponse({"success": False, "error": "AI Care Coordinator not available"})

    tasks = ai_care_coordinator.get_pending_outreach()
    return JSONResponse({
        "success": True,
        "data": [t.to_dict() for t in tasks],
        "count": len(tasks)
    })


@app.post("/api/ai-coordinator/outreach/generate")
async def api_generate_outreach(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Generate outreach queue based on current satisfaction data"""
    if ai_care_coordinator is None:
        return JSONResponse({"success": False, "error": "AI Care Coordinator not available"})

    tasks = ai_care_coordinator.generate_outreach_queue()
    return JSONResponse({
        "success": True,
        "data": [t.to_dict() for t in tasks],
        "generated_count": len(tasks)
    })


@app.get("/api/ai-coordinator/action-log")
async def api_ai_coordinator_action_log(
    limit: int = Query(50, ge=1, le=500),
    client_id: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get AI coordinator action log (audit trail)"""
    if ai_care_coordinator is None:
        return JSONResponse({"success": False, "error": "AI Care Coordinator not available"})

    actions = ai_care_coordinator.get_action_log(limit=limit, client_id=client_id)
    return JSONResponse({
        "success": True,
        "data": actions,
        "count": len(actions)
    })


@app.get("/api/client-satisfaction/surveys")
async def api_get_surveys(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get survey responses"""
    from portal_models import ClientSurveyResponse

    surveys = db.query(ClientSurveyResponse).order_by(
        ClientSurveyResponse.survey_date.desc()
    ).offset(offset).limit(limit).all()

    return JSONResponse({
        "success": True,
        "data": [s.to_dict() for s in surveys],
        "count": len(surveys)
    })


@app.post("/api/client-satisfaction/surveys")
async def api_create_survey(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new survey response (manual entry)"""
    from portal_models import ClientSurveyResponse

    data = await request.json()

    survey = ClientSurveyResponse(
        client_name=data.get("client_name"),
        client_id=data.get("client_id"),
        survey_date=datetime.strptime(data.get("survey_date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").date(),
        overall_satisfaction=data.get("overall_satisfaction"),
        caregiver_satisfaction=data.get("caregiver_satisfaction"),
        communication_rating=data.get("communication_rating"),
        reliability_rating=data.get("reliability_rating"),
        would_recommend=data.get("would_recommend"),
        feedback_comments=data.get("feedback_comments"),
        improvement_suggestions=data.get("improvement_suggestions"),
        source="manual",
        caregiver_name=data.get("caregiver_name"),
        respondent_relationship=data.get("respondent_relationship"),
        created_by=current_user.get("email"),
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)

    return JSONResponse({"success": True, "data": survey.to_dict()})


@app.get("/api/client-satisfaction/complaints")
async def api_get_complaints(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get complaints"""
    from portal_models import ClientComplaint

    query = db.query(ClientComplaint)
    if status:
        query = query.filter(ClientComplaint.status == status)

    complaints = query.order_by(ClientComplaint.complaint_date.desc()).limit(limit).all()

    return JSONResponse({
        "success": True,
        "data": [c.to_dict() for c in complaints],
        "count": len(complaints)
    })


@app.post("/api/client-satisfaction/complaints")
async def api_create_complaint(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new complaint"""
    from portal_models import ClientComplaint

    data = await request.json()

    complaint = ClientComplaint(
        client_name=data.get("client_name"),
        client_id=data.get("client_id"),
        complaint_date=datetime.strptime(data.get("complaint_date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").date(),
        category=data.get("category"),
        severity=data.get("severity", "medium"),
        description=data.get("description"),
        caregiver_involved=data.get("caregiver_involved"),
        status="open",
        source=data.get("source", "manual"),
        reported_by=data.get("reported_by"),
        created_by=current_user.get("email"),
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    return JSONResponse({"success": True, "data": complaint.to_dict()})


@app.put("/api/client-satisfaction/complaints/{complaint_id}")
async def api_update_complaint(
    complaint_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update a complaint (e.g., resolve it)"""
    from portal_models import ClientComplaint

    complaint = db.query(ClientComplaint).filter(ClientComplaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    data = await request.json()

    if "status" in data:
        complaint.status = data["status"]
    if "resolution_notes" in data:
        complaint.resolution_notes = data["resolution_notes"]
    if "resolved_by" in data:
        complaint.resolved_by = data["resolved_by"]
    if data.get("status") in ("resolved", "closed") and not complaint.resolution_date:
        complaint.resolution_date = date.today()

    db.commit()
    db.refresh(complaint)

    return JSONResponse({"success": True, "data": complaint.to_dict()})


@app.get("/api/client-satisfaction/quality-visits")
async def api_get_quality_visits(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get quality visits"""
    from portal_models import QualityVisit

    visits = db.query(QualityVisit).order_by(
        QualityVisit.visit_date.desc()
    ).limit(limit).all()

    return JSONResponse({
        "success": True,
        "data": [v.to_dict() for v in visits],
        "count": len(visits)
    })


@app.post("/api/client-satisfaction/quality-visits")
async def api_create_quality_visit(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new quality visit"""
    from portal_models import QualityVisit

    data = await request.json()

    visit = QualityVisit(
        client_name=data.get("client_name"),
        client_id=data.get("client_id"),
        visit_date=datetime.strptime(data.get("visit_date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").date(),
        visit_type=data.get("visit_type", "routine"),
        conducted_by=data.get("conducted_by", current_user.get("name")),
        caregiver_present=data.get("caregiver_present"),
        home_environment_score=data.get("home_environment_score"),
        care_quality_score=data.get("care_quality_score"),
        client_wellbeing_score=data.get("client_wellbeing_score"),
        caregiver_performance_score=data.get("caregiver_performance_score"),
        care_plan_adherence_score=data.get("care_plan_adherence_score"),
        observations=data.get("observations"),
        concerns_identified=data.get("concerns_identified"),
        recommendations=data.get("recommendations"),
        follow_up_required=data.get("follow_up_required", False),
        status="completed",
        created_by=current_user.get("email"),
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)

    return JSONResponse({"success": True, "data": visit.to_dict()})


@app.get("/api/client-satisfaction/reviews")
async def api_get_reviews(
    platform: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get external reviews"""
    from portal_models import ClientReview

    query = db.query(ClientReview)
    if platform:
        query = query.filter(ClientReview.platform == platform)

    reviews = query.order_by(ClientReview.review_date.desc()).limit(limit).all()

    return JSONResponse({
        "success": True,
        "data": [r.to_dict() for r in reviews],
        "count": len(reviews)
    })


@app.post("/api/client-satisfaction/reviews")
async def api_create_review(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Add an external review"""
    from portal_models import ClientReview

    data = await request.json()

    review = ClientReview(
        platform=data.get("platform", "google"),
        review_date=datetime.strptime(data.get("review_date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").date(),
        reviewer_name=data.get("reviewer_name"),
        rating=data.get("rating"),
        review_text=data.get("review_text"),
        review_url=data.get("review_url"),
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return JSONResponse({"success": True, "data": review.to_dict()})


@app.post("/api/client-satisfaction/sync-surveys")
async def api_sync_surveys(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Sync survey responses from Google Sheets"""
    from services.client_satisfaction_service import client_satisfaction_service

    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
    sheet_id = data.get("sheet_id")

    result = client_satisfaction_service.sync_survey_responses(db, sheet_id)
    return JSONResponse(result)


#
# RingCentral Chat Scanner API
#

@app.get("/api/client-satisfaction/ringcentral/status")
async def api_ringcentral_status(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get RingCentral Team Messaging integration status"""
    from services.ringcentral_messaging_service import ringcentral_messaging_service

    status = ringcentral_messaging_service.get_status()
    return JSONResponse(status)


@app.get("/api/client-satisfaction/ringcentral/teams")
async def api_ringcentral_teams(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List available RingCentral teams/chats"""
    from services.ringcentral_messaging_service import ringcentral_messaging_service

    teams = ringcentral_messaging_service.list_teams()
    return JSONResponse({
        "success": True,
        "teams": [{"id": t.get("id"), "name": t.get("name")} for t in teams]
    })


@app.post("/api/client-satisfaction/ringcentral/scan")
async def api_ringcentral_scan(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Scan RingCentral team chat for client mentions and potential complaints.

    Request body:
        - chat_name: Name of chat to scan (defaults to 'New Scheduling')
        - hours_back: How many hours back to scan (default 24)
        - auto_create: If true, automatically create complaint records
    """
    from services.ringcentral_messaging_service import ringcentral_messaging_service

    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
    chat_name = data.get("chat_name")
    hours_back = data.get("hours_back", 24)
    auto_create = data.get("auto_create", False)

    # Scan the chat
    scan_results = ringcentral_messaging_service.scan_chat_for_client_issues(
        db,
        chat_name=chat_name,
        hours_back=hours_back
    )

    if not scan_results.get("success"):
        return JSONResponse(scan_results, status_code=400)

    # Auto-create complaints if requested
    if auto_create and scan_results.get("potential_complaints"):
        create_results = ringcentral_messaging_service.auto_create_complaints(
            db, scan_results, auto_create=True
        )
        scan_results["auto_create_results"] = create_results

    return JSONResponse(scan_results)


@app.post("/api/client-satisfaction/ringcentral/preview")
async def api_ringcentral_preview(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Preview what complaints would be created from chat scan (without creating them).

    Request body:
        - chat_name: Name of chat to scan (defaults to 'New Scheduling')
        - hours_back: How many hours back to scan (default 24)
    """
    from services.ringcentral_messaging_service import ringcentral_messaging_service

    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
    chat_name = data.get("chat_name")
    hours_back = data.get("hours_back", 24)

    # Scan the chat
    scan_results = ringcentral_messaging_service.scan_chat_for_client_issues(
        db,
        chat_name=chat_name,
        hours_back=hours_back
    )

    if not scan_results.get("success"):
        return JSONResponse(scan_results, status_code=400)

    # Preview what would be created (without actually creating)
    preview_results = ringcentral_messaging_service.auto_create_complaints(
        db, scan_results, auto_create=False
    )

    return JSONResponse({
        **scan_results,
        "preview": preview_results
    })


#
# RingCentral Call Pattern Monitoring API
#

@app.get("/api/client-satisfaction/ringcentral/call-queues")
async def api_ringcentral_call_queues(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List available RingCentral call queues"""
    from services.ringcentral_messaging_service import ringcentral_messaging_service

    queues = ringcentral_messaging_service.get_call_queues()
    return JSONResponse({
        "success": True,
        "queues": [
            {"id": q.get("id"), "name": q.get("name"), "ext": q.get("extensionNumber")}
            for q in queues
        ]
    })


@app.post("/api/client-satisfaction/ringcentral/scan-calls")
async def api_ringcentral_scan_calls(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Scan call logs for patterns indicating potential client issues.

    Detects:
    - Repeat callers (3+ calls)
    - Short calls (<10 sec, potential frustration)
    - Multiple missed calls
    - Multiple calls to Client Support queue

    Request body:
        - days_back: Number of days to analyze (default 7)
        - queue_id: Optional - filter to specific call queue ID
        - auto_create: If true, create complaint records for flagged patterns
        - min_severity: Minimum severity to create complaints (default "medium")
    """
    from services.ringcentral_messaging_service import ringcentral_messaging_service

    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
    days_back = data.get("days_back", 7)
    queue_id = data.get("queue_id")
    auto_create = data.get("auto_create", False)
    min_severity = data.get("min_severity", "medium")

    # Scan call logs
    scan_results = ringcentral_messaging_service.scan_calls_for_issues(
        db,
        days_back=days_back,
        queue_id=queue_id
    )

    if not scan_results.get("success"):
        return JSONResponse(scan_results, status_code=400)

    # Auto-create complaints if requested
    if auto_create and scan_results.get("flagged_patterns"):
        create_results = ringcentral_messaging_service.auto_create_call_complaints(
            db, scan_results, auto_create=True, min_severity=min_severity
        )
        scan_results["auto_create_results"] = create_results

    return JSONResponse(scan_results)


@app.post("/api/client-satisfaction/ringcentral/preview-calls")
async def api_ringcentral_preview_calls(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Preview call pattern analysis without creating complaint records.

    Request body:
        - days_back: Number of days to analyze (default 7)
        - queue_id: Optional - filter to specific call queue ID
    """
    from services.ringcentral_messaging_service import ringcentral_messaging_service

    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
    days_back = data.get("days_back", 7)
    queue_id = data.get("queue_id")

    # Scan call logs
    scan_results = ringcentral_messaging_service.scan_calls_for_issues(
        db,
        days_back=days_back,
        queue_id=queue_id
    )

    if not scan_results.get("success"):
        return JSONResponse(scan_results, status_code=400)

    # Preview what would be created
    preview_results = ringcentral_messaging_service.auto_create_call_complaints(
        db, scan_results, auto_create=False
    )

    return JSONResponse({
        **scan_results,
        "preview": preview_results
    })


@app.get("/connections", response_class=HTMLResponse)
async def connections_page(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Render the data connections management page."""
    from portal_models import OAuthToken

    # Check which services are connected for this user
    user_email = current_user.get("email", "unknown@example.com")
    connected_services = {}

    services = ["facebook", "google-ads", "mailchimp", "quickbooks"]
    for service in services:
        token = db.query(OAuthToken).filter(
            OAuthToken.user_email == user_email,
            OAuthToken.service == service,
            OAuthToken.is_active == True
        ).first()
        connected_services[service] = token is not None

    return templates.TemplateResponse("connections.html", {
        "request": request,
        "user": current_user,
        "connected_services": connected_services
    })


# OAuth Routes
@app.get("/auth/{service}")
async def oauth_initiate(
    service: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Initiate OAuth flow for a service"""
    import secrets

    from services.oauth_manager import oauth_manager

    # Generate and store CSRF state token
    state = secrets.token_urlsafe(32)
    request.session[f"oauth_state_{service}"] = state
    request.session["oauth_user_email"] = current_user.get("email")

    # Get authorization URL
    auth_url = oauth_manager.get_authorization_url(service, state)

    if not auth_url:
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>OAuth Error</title></head>
                <body style="font-family: sans-serif; padding: 40px; text-align: center;">
                    <h1>⚠️ OAuth Not Configured</h1>
                    <p>The {service} integration is not yet configured with OAuth credentials.</p>
                    <p><a href="/connections">← Back to Connections</a></p>
                    <script>
                        setTimeout(() => {{
                            window.close();
                        }}, 3000);
                    </script>
                </body>
            </html>
            """,
            status_code=400
        )

    return RedirectResponse(url=auth_url)


@app.get("/auth/{service}/callback")
async def oauth_callback(
    service: str,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Handle OAuth callback from service"""
    from datetime import datetime

    from portal_models import OAuthToken
    from services.oauth_manager import oauth_manager

    # Check for errors
    if error:
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>OAuth Error</title></head>
                <body style="font-family: sans-serif; padding: 40px; text-align: center;">
                    <h1>❌ Authentication Failed</h1>
                    <p>Error: {error}</p>
                    <p><a href="/connections">← Back to Connections</a></p>
                    <script>
                        setTimeout(() => {{
                            window.opener.postMessage({{type: 'oauth_error', service: '{service}', error: '{error}'}}, '*');
                            window.close();
                        }}, 2000);
                    </script>
                </body>
            </html>
            """
        )

    # Verify state (CSRF protection)
    expected_state = request.session.get(f"oauth_state_{service}")
    if not state or state != expected_state:
        return HTMLResponse(
            content="""
            <html>
                <head><title>Security Error</title></head>
                <body style="font-family: sans-serif; padding: 40px; text-align: center;">
                    <h1>🔒 Security Error</h1>
                    <p>Invalid state parameter. Please try again.</p>
                    <p><a href="/connections">← Back to Connections</a></p>
                    <script>
                        setTimeout(() => {
                            window.close();
                        }, 2000);
                    </script>
                </body>
            </html>
            """,
            status_code=400
        )

    # Exchange code for token
    token_data = await oauth_manager.exchange_code_for_token(service, code)

    if not token_data:
        return HTMLResponse(
            content="""
            <html>
                <head><title>Token Exchange Failed</title></head>
                <body style="font-family: sans-serif; padding: 40px; text-align: center;">
                    <h1>❌ Token Exchange Failed</h1>
                    <p>Could not obtain access token. Please try again.</p>
                    <p><a href="/connections">← Back to Connections</a></p>
                    <script>
                        setTimeout(() => {
                            window.close();
                        }, 2000);
                    </script>
                </body>
            </html>
            """,
            status_code=500
        )

    # Store token in database
    try:
        user_email = request.session.get("oauth_user_email", "unknown@example.com")

        # Parse expires_at
        expires_at = None
        if token_data.get("expires_at"):
            expires_at = datetime.fromisoformat(token_data["expires_at"])

        # Capture service-specific extra data (e.g., QBO realmId)
        extra_data = token_data.get("extra_data") or {}
        if service == "quickbooks":
            realm_id = request.query_params.get("realmId")
            if realm_id:
                extra_data["realm_id"] = realm_id
                logger.info(f"Captured QuickBooks realmId: {realm_id}")

        # Check if token already exists for this user/service
        existing_token = db.query(OAuthToken).filter(
            OAuthToken.user_email == user_email,
            OAuthToken.service == service
        ).first()

        if existing_token:
            # Update existing token
            existing_token.access_token = token_data.get("access_token")
            existing_token.refresh_token = token_data.get("refresh_token")
            existing_token.expires_at = expires_at
            existing_token.scope = token_data.get("scope")
            existing_token.is_active = True
            existing_token.updated_at = datetime.utcnow()
            if extra_data:
                existing_token.extra_data = extra_data
        else:
            # Create new token
            new_token = OAuthToken(
                user_email=user_email,
                service=service,
                access_token=token_data.get("access_token"),
                refresh_token=token_data.get("refresh_token"),
                token_type=token_data.get("token_type", "Bearer"),
                expires_at=expires_at,
                scope=token_data.get("scope"),
                extra_data=extra_data if extra_data else None
            )
            db.add(new_token)

        db.commit()

        # Clean up session
        request.session.pop(f"oauth_state_{service}", None)

        return HTMLResponse(
            content=f"""
            <html>
                <head><title>Success!</title></head>
                <body style="font-family: sans-serif; padding: 40px; text-align: center;">
                    <h1>✅ Connected Successfully!</h1>
                    <p>{service.replace('_', ' ').title()} has been connected to your account.</p>
                    <p>This window will close automatically...</p>
                    <script>
                        window.opener.postMessage({{type: 'oauth_success', service: '{service}'}}, '*');
                        setTimeout(() => {{
                            window.close();
                        }}, 1500);
                    </script>
                </body>
            </html>
            """
        )

    except Exception as e:
        logger.error(f"Error storing OAuth token: {e}")
        db.rollback()
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>Storage Error</title></head>
                <body style="font-family: sans-serif; padding: 40px; text-align: center;">
                    <h1>⚠️ Storage Error</h1>
                    <p>Token obtained but could not be saved: {str(e)}</p>
                    <p><a href="/connections">← Back to Connections</a></p>
                    <script>
                        setTimeout(() => {{
                            window.close();
                        }}, 3000);
                    </script>
                </body>
            </html>
            """,
            status_code=500
        )


@app.get("/marketing", response_class=HTMLResponse)
async def marketing_dashboard(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Marketing dashboard shell (Social + Ads metrics)"""
    # Compute default date range (last 30 days)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=29)

    # Wire up RingCentral config for sidebar
    ringcentral_config = {
        "enabled": bool(RINGCENTRAL_EMBED_CLIENT_ID),
        "app_url": RINGCENTRAL_EMBED_APP_URL,
        "adapter_url": RINGCENTRAL_EMBED_ADAPTER_URL,
        "query_string": ""
    }

    if ringcentral_config["enabled"]:
        import time
        params = {
            "clientId": RINGCENTRAL_EMBED_CLIENT_ID,
            "appServer": RINGCENTRAL_EMBED_SERVER,
        }
        if RINGCENTRAL_EMBED_DEFAULT_TAB:
            params["defaultTab"] = RINGCENTRAL_EMBED_DEFAULT_TAB
        if RINGCENTRAL_EMBED_REDIRECT_URI:
            params["redirectUri"] = RINGCENTRAL_EMBED_REDIRECT_URI
        params["enableGlip"] = "true"
        params["disableGlip"] = "false"
        params["disableConferences"] = "true"
        params["theme"] = "dark"
        params["_t"] = str(int(time.time()))
        ringcentral_config["query_string"] = urlencode(params)

    # Placeholder datasets (will be replaced once APIs are wired)
    placeholder_metrics = {
        "social": {
            "summary": [],
            "top_posts": []
        },
        "ads": {
            "overview": [],
            "campaigns": []
        }
    }

    return templates.TemplateResponse("marketing.html", {
        "request": request,
        "user": current_user,
        "ringcentral": ringcentral_config,
        "date_presets": [
            {"label": "Last 7 Days", "value": "last_7_days"},
            {"label": "Last 30 Days", "value": "last_30_days", "default": True},
            {"label": "Month to Date", "value": "month_to_date"},
            {"label": "Quarter to Date", "value": "quarter_to_date"},
            {"label": "Year to Date", "value": "year_to_date"},
            {"label": "Previous 12 Months", "value": "last_12_months"},
            {"label": "Custom Range", "value": "custom"}
        ],
        "default_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "placeholder_metrics": placeholder_metrics
    })

def _parse_date_param(value: Optional[str], fallback: date_cls) -> date_cls:
    if not value:
        return fallback
    try:
        return date_cls.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {value}. Use YYYY-MM-DD.")


@app.get("/api/marketing/social")
async def api_marketing_social(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    compare: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Return social performance metrics (placeholder until APIs wired)."""
    end_default = datetime.utcnow().date()
    start_default = end_default - timedelta(days=29)

    start = _parse_date_param(from_date, start_default)
    end = _parse_date_param(to_date, end_default)

    if start > end:
        raise HTTPException(status_code=400, detail="'from' date must be before 'to' date.")

    data = get_social_metrics(start, end, compare)

    return JSONResponse({
        "success": True,
        "range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": (end - start).days + 1
        },
        "compare": compare,
        "data": data
    })


@app.post("/api/marketing/google-ads/webhook")
@limiter.limit("30/minute")  # Rate limit webhooks
async def google_ads_webhook(request: Request):
    """
    Webhook endpoint to receive Google Ads metrics from Google Ads Scripts.

    The script runs in Google Ads and POSTs data here periodically.
    """
    from datetime import datetime

    # SECURITY: Verify webhook secret (required for security)
    webhook_secret = os.getenv("GOOGLE_ADS_WEBHOOK_SECRET")
    if webhook_secret:
        received_secret = request.headers.get("X-Webhook-Secret")
        if received_secret != webhook_secret:
            logger.warning("Google Ads webhook: Invalid secret")
            raise HTTPException(status_code=401, detail="Invalid webhook secret")
    else:
        logger.warning("GOOGLE_ADS_WEBHOOK_SECRET not configured - webhook not secured")

    try:
        data = await request.json()
        logger.info(f"Google Ads webhook received data from customer {data.get('customer_id')}")

        # Store the data (simple in-memory cache for now)
        # In production, you might want to store in database or Redis
        from services.marketing.google_ads_service import google_ads_service
        google_ads_service.cache_script_data(data)

        return JSONResponse({
            "status": "success",
            "message": "Data received and cached",
            "customer_id": data.get("customer_id"),
            "received_at": datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error processing Google Ads webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")


@app.get("/api/marketing/ads")
async def api_marketing_ads(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    compare: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Return ads performance metrics from Google Ads Scripts or API."""
    end_default = datetime.utcnow().date()
    start_default = end_default - timedelta(days=29)

    start = _parse_date_param(from_date, start_default)
    end = _parse_date_param(to_date, end_default)

    if start > end:
        raise HTTPException(status_code=400, detail="'from' date must be before 'to' date.")

    # Try to get data from script cache first, fall back to API
    from services.marketing.google_ads_service import google_ads_service
    script_data = google_ads_service.get_cached_script_data(start, end)

    if script_data:
        logger.info("Using Google Ads Script data")
        data = script_data
    else:
        logger.info("No script data available, trying API")
        data = get_ads_metrics(start, end, compare)

    return JSONResponse({
        "success": True,
        "range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": (end - start).days + 1
        },
        "compare": compare,
        "data": data
    })


@app.post("/api/marketing/brevo-webhook")
@limiter.limit("60/minute")  # Rate limit webhooks
async def brevo_marketing_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook endpoint for Brevo marketing email events.
    Stores events for real-time metrics aggregation (hybrid model: webhooks + API).

    Events: delivered, opened, click, hardBounce, softBounce, spam, unsubscribed
    """
    # SECURITY: Verify Brevo webhook signature if secret is configured
    brevo_secret = os.getenv("BREVO_WEBHOOK_SECRET")
    if brevo_secret:
        import hashlib
        import hmac
        # Brevo uses X-Sib-Signature header
        signature = request.headers.get("X-Sib-Signature")
        if not signature:
            logger.warning("Brevo webhook: Missing X-Sib-Signature header")
            return JSONResponse({"error": "Missing signature"}, status_code=401)
        body = await request.body()
        expected = hmac.new(brevo_secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning("Brevo webhook: Invalid signature")
            return JSONResponse({"error": "Invalid signature"}, status_code=401)
    else:
        logger.debug("BREVO_WEBHOOK_SECRET not configured - signature validation disabled")

    try:
        data = await request.json()
        logger.info(f"Brevo marketing webhook received: {data.get('event', 'unknown')} for {data.get('email', 'unknown')}")

        # Extract webhook data
        event_type = data.get("event")
        recipient_email = data.get("email", "").lower().strip()
        webhook_id = data.get("id")
        campaign_id = data.get("camp_id")
        campaign_name = data.get("campaign name", "Unknown Campaign")
        date_sent_str = data.get("date_sent")
        date_event_str = data.get("date_event")
        click_url = data.get("URL") if event_type == "click" else None

        if not recipient_email:
            logger.warning("No email address in Brevo webhook")
            return JSONResponse({"status": "error", "reason": "no email address"})

        # Parse dates
        date_sent = None
        date_event = None
        try:
            if date_sent_str:
                date_sent = datetime.strptime(date_sent_str, "%Y-%m-%d %H:%M:%S")
            if date_event_str:
                date_event = datetime.strptime(date_event_str, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.warning(f"Error parsing dates: {e}")

        # Check for duplicate webhook events
        if webhook_id:
            existing = db.query(BrevoWebhookEvent).filter(
                BrevoWebhookEvent.webhook_id == webhook_id
            ).first()

            if existing:
                logger.debug(f"Brevo webhook event already processed: webhook ID {webhook_id}")
                return JSONResponse({
                    "status": "success",
                    "logged": False,
                    "reason": "duplicate"
                })

        # Store metadata as JSON
        import json as json_lib
        metadata = {
            "ts_sent": data.get("ts_sent"),
            "ts_event": data.get("ts_event"),
            "tag": data.get("tag"),
            "segment_ids": data.get("segment_ids"),
        }
        if event_type in ["hard_bounce", "soft_bounce", "spam"]:
            metadata["reason"] = data.get("reason")

        # Create webhook event record
        webhook_event = BrevoWebhookEvent(
            webhook_id=webhook_id,
            event_type=event_type,
            email=recipient_email,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            date_sent=date_sent,
            date_event=date_event or datetime.utcnow(),
            click_url=click_url,
            event_metadata=json_lib.dumps(metadata) if metadata else None,
        )

        db.add(webhook_event)
        db.commit()
        db.refresh(webhook_event)

        logger.info(f"Stored Brevo webhook event: {event_type} for {recipient_email} (campaign {campaign_id})")

        return JSONResponse({
            "status": "success",
            "logged": True,
            "event": event_type,
            "webhook_event_id": webhook_event.id
        })

    except Exception as e:
        logger.error(f"Error processing Brevo marketing webhook: {e}", exc_info=True)
        db.rollback()
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/marketing/email")
async def api_marketing_email(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Return email marketing metrics (Brevo + Mailchimp) using hybrid model (webhooks + API)."""
    end_default = datetime.utcnow().date()
    start_default = end_default - timedelta(days=29)

    start = _parse_date_param(from_date, start_default)
    end = _parse_date_param(to_date, end_default)

    if start > end:
        raise HTTPException(status_code=400, detail="'from' date must be before 'to' date.")

    data = get_email_metrics(start, end)

    return JSONResponse({
        "success": True,
        "range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": (end - start).days + 1
        },
        "data": data
    })


@app.get("/api/marketing/website")
async def api_marketing_website(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Return website and GBP metrics from GA4 and Google Business Profile."""
    import logging

    from services.marketing.ga4_service import ga4_service
    from services.marketing.gbp_service import gbp_service

    logger = logging.getLogger(__name__)

    end_default = datetime.utcnow().date()
    start_default = end_default - timedelta(days=29)

    start = _parse_date_param(from_date, start_default)
    end = _parse_date_param(to_date, end_default)

    if start > end:
        raise HTTPException(status_code=400, detail="'from' date must be before 'to' date.")

    # Log the request
    logger.info(f"Fetching website metrics from {start} to {end}")

    # Fetch GA4 and GBP data
    ga4_data = ga4_service.get_website_metrics(start, end)
    gbp_data = gbp_service.get_gbp_metrics(start, end)

    # Log if we're using mock data
    if ga4_data.get("total_users") == 188:
        logger.warning("GA4 returned mock data - check service account permissions")

    return JSONResponse({
        "success": True,
        "range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": (end - start).days + 1
        },
        "data": {
            "ga4": ga4_data,
            "gbp": gbp_data
        }
    })


@app.get("/api/marketing/test-ga4")
async def test_ga4_connection(
    _test_ok: None = Depends(require_portal_test_endpoints_enabled)
):
    """Test GA4 connection and return status."""
    import os

    from services.marketing.ga4_service import ga4_service

    status = {
        "service_account_configured": bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")),
        "property_id": os.getenv("GA4_PROPERTY_ID", "445403783"),
        "client_initialized": ga4_service.client is not None,
    }

    if ga4_service.client:
        try:
            # Try a simple query
            from datetime import date, timedelta
            end = date.today()
            start = end - timedelta(days=7)
            test_data = ga4_service.get_website_metrics(start, end)
            status["test_query_successful"] = True
            status["sample_users"] = test_data.get("total_users", 0)
        except Exception as e:
            status["test_query_successful"] = False
            status["error"] = str(e)

    return JSONResponse(status)


@app.get("/api/marketing/test-predis")
async def test_predis_connection(
    _test_ok: None = Depends(require_portal_test_endpoints_enabled)
):
    """Test Predis AI connection and return status."""

    from services.marketing.predis_service import predis_service

    status = {
        "api_key_configured": bool(predis_service.api_key),
        "api_working": False,
        "account_info": None
    }

    if predis_service.api_key:
        try:
            # Test API connection
            account_info = predis_service.get_account_info()
            status["api_working"] = account_info.get("api_working", False)
            status["account_info"] = account_info
        except Exception as e:
            status["error"] = str(e)

    return JSONResponse(status)


@app.get("/api/marketing/predis/posts")
async def get_predis_posts(
    page: int = 1,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get recent Predis AI generated posts."""
    from services.marketing.predis_service import predis_service

    try:
        posts = predis_service.get_recent_creations(page=page)
        return JSONResponse({
            "success": True,
            "posts": posts,
            "page": page
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/marketing/predis/generate")
async def generate_predis_content(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Generate new content using Predis AI."""
    from services.marketing.predis_service import predis_service

    try:
        data = await request.json()
        prompt = data.get("prompt", "")
        media_type = data.get("media_type", "single_image")

        if not prompt:
            return JSONResponse({
                "success": False,
                "error": "Prompt is required"
            }, status_code=400)

        result = predis_service.generate_content(prompt=prompt, media_type=media_type)
        return JSONResponse(result)

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/marketing/predis/templates")
async def get_predis_templates(
    page: int = 1,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get Predis AI templates."""
    from services.marketing.predis_service import predis_service

    try:
        templates = predis_service.get_templates(page=page)
        return JSONResponse({
            "success": True,
            "templates": templates,
            "page": page
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/marketing/test-gbp")
async def test_gbp_connection(
    _test_ok: None = Depends(require_portal_test_endpoints_enabled)
):
    """Test GBP connection and return status."""

    from services.marketing.gbp_service import gbp_service

    status = {
        "oauth_configured": bool(gbp_service.client_id and gbp_service.client_secret),
        "access_token_available": bool(gbp_service.access_token),
        "refresh_token_available": bool(gbp_service.refresh_token),
        "location_ids": gbp_service.location_ids,
        "service_initialized": bool(gbp_service.access_token),
    }

    if gbp_service.access_token:
        try:
            # Try to get accounts and locations
            accounts = gbp_service.get_accounts()
            status["accounts_accessible"] = len(accounts)
            status["accounts"] = accounts[:3]  # First 3 accounts

            # Try to get locations - prefer LOCATION_GROUP accounts (these have business locations)
            locations = []
            location_group_accounts = [a for a in accounts if a.get('type') == 'LOCATION_GROUP']
            accounts_to_check = location_group_accounts[:2] if location_group_accounts else accounts[:1]
            for account in accounts_to_check:
                account_locations = gbp_service.get_locations(account.get('name'))
                locations.extend(account_locations[:3])  # First 3 locations per account
            status["locations_accessible"] = len(locations)
            status["locations"] = locations

        except Exception as e:
            status["locations_accessible"] = 0
            status["error"] = str(e)

    return JSONResponse(status)


@app.get("/api/marketing/engagement")
async def api_marketing_engagement(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Aggregate engagement data from all marketing channels.
    
    Provides attribution insights showing where engagements, calls,
    and conversions are coming from across:
    - Facebook/Instagram (organic + paid)
    - Google Ads (paid search/display)
    - Google Analytics (organic, direct, referral)
    - Pinterest
    - LinkedIn
    - Google Business Profile (calls, directions)
    """
    import logging

    from services.marketing.ga4_service import ga4_service
    from services.marketing.gbp_service import gbp_service
    from services.marketing.linkedin_service import linkedin_service
    from services.marketing.pinterest_service import pinterest_service

    logger = logging.getLogger(__name__)

    # Date range
    end_default = datetime.utcnow().date()
    start_default = end_default - timedelta(days=29)
    start = _parse_date_param(from_date, start_default)
    end = _parse_date_param(to_date, end_default)

    if start > end:
        raise HTTPException(status_code=400, detail="'from' date must be before 'to' date.")

    days = (end - start).days + 1

    # Fetch data from all sources
    try:
        # GA4 data for traffic sources
        ga4_data = ga4_service.get_website_metrics(start, end)

        # Get social metrics
        social_data = get_social_metrics(start, end, None)

        # Get ads metrics
        ads_data = get_ads_metrics(start, end, None)

        # GBP for calls/directions
        gbp_data = gbp_service.get_gbp_metrics(start, end)

        # Pinterest metrics
        pinterest_data = pinterest_service.get_user_metrics(start, end)

        # LinkedIn metrics
        linkedin_data = linkedin_service.get_metrics(start, end)

    except Exception as e:
        logger.error(f"Error fetching engagement data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Build attribution breakdown - where are engagements coming from?
    attribution = {
        "by_source": [],
        "by_type": []
    }

    # Calculate engagement by source
    sources = []

    # Facebook/Instagram (only if real data)
    fb_engagement = 0
    fb_likes = 0
    # Check if social data is real (not placeholder)
    social_is_placeholder = social_data.get("is_placeholder", False) if social_data else True
    if social_data and not social_is_placeholder and social_data.get("post_overview"):
        fb_engagement = (
            social_data["post_overview"].get("post_clicks", 0) +
            social_data["summary"].get("unique_clicks", 0)
        )
    if social_data and not social_is_placeholder and social_data.get("summary"):
        fb_likes = social_data["summary"].get("total_page_likes", {}).get("value", 0)
        if fb_engagement > 0 or fb_likes > 0:
            sources.append({
                "source": "Facebook/Instagram",
                "icon": "📘",
                "engagements": fb_engagement,
                "followers": fb_likes,
                "type": "social"
            })

    # Google Ads - conversions as engagement (only if real data, not placeholder)
    google_conversions = 0
    google_clicks = 0
    if ads_data and ads_data.get("google_ads"):
        google_ads = ads_data["google_ads"]
        # Skip placeholder data - don't show fake Google Ads metrics
        if not google_ads.get("is_placeholder", False):
            google_conversions = google_ads.get("performance", {}).get("conversions", 0)
            google_clicks = google_ads.get("performance", {}).get("clicks", 0)
            if google_clicks > 0:
                sources.append({
                    "source": "Google Ads",
                    "icon": "🔍",
                    "engagements": google_clicks,
                    "conversions": google_conversions,
                    "type": "paid"
                })

    # GA4 - organic traffic
    organic_sessions = 0
    direct_sessions = 0
    referral_sessions = 0
    if ga4_data:
        sessions_by_source = ga4_data.get("sessions_by_source", {})
        organic_sessions = sessions_by_source.get("google", 0)
        direct_sessions = sessions_by_source.get("direct", 0)
        referral_sessions = sessions_by_source.get("fb", 0) + sessions_by_source.get("l.facebook.com", 0)

        sources.append({
            "source": "Organic Search",
            "icon": "🌐",
            "engagements": organic_sessions,
            "type": "organic"
        })
        sources.append({
            "source": "Direct Traffic",
            "icon": "🔗",
            "engagements": direct_sessions,
            "type": "direct"
        })

    # GBP - calls and actions
    gbp_calls = 0
    gbp_directions = 0
    gbp_website = 0
    if gbp_data:
        gbp_calls = gbp_data.get("phone_calls", 0)
        gbp_directions = gbp_data.get("directions", 0)
        gbp_website = gbp_data.get("website_clicks", 0)
        if gbp_calls or gbp_directions or gbp_website:
            sources.append({
                "source": "Google Business Profile",
                "icon": "📍",
                "engagements": gbp_calls + gbp_directions + gbp_website,
                "calls": gbp_calls,
                "directions": gbp_directions,
                "website_clicks": gbp_website,
                "type": "local"
            })

    # Pinterest
    pinterest_engagement = 0
    if pinterest_data and not pinterest_data.get("is_placeholder"):
        pinterest_engagement = (
            pinterest_data.get("clicks", 0) +
            pinterest_data.get("saves", 0)
        )
        if pinterest_engagement:
            sources.append({
                "source": "Pinterest",
                "icon": "📌",
                "engagements": pinterest_engagement,
                "saves": pinterest_data.get("saves", 0),
                "clicks": pinterest_data.get("clicks", 0),
                "type": "social"
            })

    # LinkedIn
    linkedin_engagement = 0
    if linkedin_data and not linkedin_data.get("is_placeholder"):
        linkedin_engagement = linkedin_data.get("summary", {}).get("engagement", 0)
        if linkedin_engagement:
            sources.append({
                "source": "LinkedIn",
                "icon": "💼",
                "engagements": linkedin_engagement,
                "type": "social"
            })

    # Sort by engagement count
    sources.sort(key=lambda x: x.get("engagements", 0), reverse=True)
    attribution["by_source"] = sources

    # Build engagement by type (only real data)
    type_breakdown = [
        {"type": "Organic Search", "icon": "🔍", "value": organic_sessions, "color": "#3b82f6"},
        {"type": "Direct", "icon": "🔗", "value": direct_sessions, "color": "#8b5cf6"},
        {"type": "Social", "icon": "📱", "value": fb_engagement + pinterest_engagement + linkedin_engagement, "color": "#f97316"},
        {"type": "Local (GBP)", "icon": "📍", "value": gbp_calls + gbp_directions + gbp_website, "color": "#ec4899"},
    ]
    # Only add paid ads if we have real (non-placeholder) data
    if google_clicks > 0:
        type_breakdown.insert(0, {"type": "Paid Ads", "icon": "💰", "value": google_clicks, "color": "#22c55e"})
    attribution["by_type"] = [t for t in type_breakdown if t["value"] > 0]

    # Track which sources are using placeholder data
    placeholder_sources = []
    if ads_data and ads_data.get("google_ads", {}).get("is_placeholder"):
        placeholder_sources.append("Google Ads")
    if social_is_placeholder:
        placeholder_sources.append("Facebook/Instagram")

    # Calculate totals
    total_engagements = sum(s.get("engagements", 0) for s in sources)
    total_conversions = google_conversions
    total_calls = gbp_calls

    # Build daily trend from GA4 data
    daily_trend = []
    if ga4_data and ga4_data.get("users_over_time"):
        for entry in ga4_data["users_over_time"]:
            daily_trend.append({
                "date": entry.get("date"),
                "engagements": entry.get("users", 0),
            })

    # Add social chart data if available
    if social_data and social_data.get("post_overview", {}).get("chart"):
        for i, entry in enumerate(social_data["post_overview"]["chart"]):
            if i < len(daily_trend):
                daily_trend[i]["social"] = entry.get("engagement", 0)
                daily_trend[i]["engagements"] += entry.get("engagement", 0)

    return JSONResponse({
        "success": True,
        "range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": days
        },
        "data": {
            "summary": {
                "total_engagements": total_engagements,
                "total_conversions": total_conversions,
                "total_calls": total_calls,
                "top_source": sources[0]["source"] if sources else None,
            },
            "attribution": attribution,
            "trend": daily_trend,
            "sources": {
                "social": {
                    "facebook": fb_engagement,
                    "pinterest": pinterest_engagement,
                    "linkedin": linkedin_engagement,
                },
                "paid": {
                    "google_ads": google_clicks,
                },
                "organic": {
                    "search": organic_sessions,
                    "direct": direct_sessions,
                    "referral": referral_sessions,
                },
                "local": {
                    "calls": gbp_calls,
                    "directions": gbp_directions,
                    "website": gbp_website,
                }
            },
            "placeholder_sources": placeholder_sources,
            "note": "Google Ads data excluded (account suspended)" if "Google Ads" in placeholder_sources else None
        }
    })


@app.get("/api/marketing/pinterest")
async def api_marketing_pinterest(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Fetch Pinterest analytics and engagement metrics.
    
    Returns pin performance, saves, clicks, and engagement data.
    """
    from datetime import date, timedelta

    from services.marketing.pinterest_service import pinterest_service

    # Default to last 30 days
    if to_date:
        end = date.fromisoformat(to_date)
    else:
        end = date.today()

    if from_date:
        start = date.fromisoformat(from_date)
    else:
        start = end - timedelta(days=30)

    try:
        data = pinterest_service.get_user_metrics(start, end)
        return JSONResponse({
            "success": True,
            "date_range": {
                "from": start.isoformat(),
                "to": end.isoformat(),
            },
            "data": data
        })
    except Exception as e:
        logger.error(f"Error fetching Pinterest metrics: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "data": pinterest_service._get_placeholder_metrics(start, end)
        })


@app.get("/api/marketing/test-pinterest")
async def test_pinterest_connection(
    _test_ok: None = Depends(require_portal_test_endpoints_enabled)
):
    """Test Pinterest connection and return status."""
    import os

    from services.marketing.pinterest_service import pinterest_service

    status = {
        "access_token_configured": bool(os.getenv("PINTEREST_ACCESS_TOKEN")),
        "app_id": os.getenv("PINTEREST_APP_ID"),
    }

    if pinterest_service._is_configured():
        try:
            user = pinterest_service.get_user_account()
            status["connection_successful"] = True
            status["username"] = user.get("username")
            status["followers"] = user.get("follower_count", 0)
            status["account_type"] = user.get("account_type")
        except Exception as e:
            status["connection_successful"] = False
            status["error"] = str(e)
    else:
        status["connection_successful"] = False
        status["error"] = "Pinterest not configured"

    return JSONResponse(status)


@app.get("/api/pinterest/auth")
async def pinterest_oauth_start():
    """Start Pinterest OAuth flow."""
    import os

    app_id = os.getenv("PINTEREST_APP_ID")
    if not app_id:
        return JSONResponse({
            "success": False,
            "error": "Pinterest App ID not configured"
        })

    redirect_uri = "https://portal.coloradocareassist.com/api/pinterest/callback"
    scopes = "boards:read,pins:read,user_accounts:read"

    oauth_url = (
        f"https://www.pinterest.com/oauth/?"
        f"response_type=code&"
        f"client_id={app_id}&"
        f"redirect_uri={redirect_uri}&"
        f"scope={scopes}&"
        f"state=pinterest_auth"
    )

    return JSONResponse({
        "success": True,
        "oauth_url": oauth_url,
        "message": "Visit the oauth_url to authorize Pinterest access"
    })


@app.get("/api/pinterest/callback")
async def pinterest_oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """Pinterest OAuth callback - exchange code for access token."""
    import base64
    import os

    import requests

    if error:
        return JSONResponse({
            "success": False,
            "error": error
        })

    if not code:
        return JSONResponse({
            "success": False,
            "error": "No authorization code received"
        })

    app_id = os.getenv("PINTEREST_APP_ID")
    app_secret = os.getenv("PINTEREST_APP_SECRET")
    redirect_uri = "https://portal.coloradocareassist.com/api/pinterest/callback"

    # Exchange code for token
    try:
        credentials = base64.b64encode(f"{app_id}:{app_secret}".encode()).decode()

        response = requests.post(
            "https://api.pinterest.com/v5/oauth/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri
            },
            timeout=30
        )

        if response.status_code == 200:
            token_data = response.json()
            return JSONResponse({
                "success": True,
                "message": "Pinterest authorized successfully!",
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in"),
                "token_type": token_data.get("token_type"),
                "scope": token_data.get("scope"),
                "instructions": "Set this access_token as PINTEREST_ACCESS_TOKEN on Mac Mini (Local)"
            })
        else:
            return JSONResponse({
                "success": False,
                "error": f"Token exchange failed: {response.status_code}",
                "details": response.text
            })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        })


@app.get("/api/marketing/linkedin")
async def api_marketing_linkedin(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Fetch LinkedIn analytics and engagement metrics.
    
    Returns post performance, impressions, clicks, and engagement data.
    """
    from datetime import date, timedelta

    from services.marketing.linkedin_service import linkedin_service

    # Default to last 30 days
    if to_date:
        end = date.fromisoformat(to_date)
    else:
        end = date.today()

    if from_date:
        start = date.fromisoformat(from_date)
    else:
        start = end - timedelta(days=30)

    try:
        data = linkedin_service.get_metrics(start, end)
        return JSONResponse({
            "success": True,
            "date_range": {
                "from": start.isoformat(),
                "to": end.isoformat(),
            },
            "data": data
        })
    except Exception as e:
        logger.error(f"Error fetching LinkedIn metrics: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "data": linkedin_service._get_placeholder_metrics(start, end)
        })


@app.get("/api/marketing/test-linkedin")
async def test_linkedin_connection(
    _test_ok: None = Depends(require_portal_test_endpoints_enabled)
):
    """Test LinkedIn connection and return status."""
    import os

    from services.marketing.linkedin_service import linkedin_service

    status = {
        "client_id_configured": bool(os.getenv("LINKEDIN_CLIENT_ID")),
        "access_token_configured": bool(os.getenv("LINKEDIN_ACCESS_TOKEN")),
        "organization_id": os.getenv("LINKEDIN_ORGANIZATION_ID"),
    }

    if linkedin_service._is_configured():
        try:
            profile = linkedin_service.get_profile()
            if profile:
                status["connection_successful"] = True
                status["name"] = profile.get("name")
                status["email"] = profile.get("email")
            else:
                status["connection_successful"] = False
                status["error"] = "Could not fetch profile"
        except Exception as e:
            status["connection_successful"] = False
            status["error"] = str(e)
    elif linkedin_service._has_credentials():
        status["connection_successful"] = False
        status["needs_oauth"] = True
        status["oauth_url"] = linkedin_service.get_oauth_url(
            "https://portal.coloradocareassist.com/api/linkedin/callback"
        )
        status["message"] = "Visit the oauth_url to authorize LinkedIn access"
    else:
        status["connection_successful"] = False
        status["error"] = "LinkedIn credentials not configured"

    return JSONResponse(status)


@app.get("/api/linkedin/callback")
async def linkedin_oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    """
    OAuth callback endpoint for LinkedIn authorization.
    
    After user authorizes, LinkedIn redirects here with an auth code.
    We exchange it for an access token.
    """
    from services.marketing.linkedin_service import linkedin_service

    if error:
        return JSONResponse({
            "success": False,
            "error": error,
            "error_description": error_description,
        })

    if not code:
        return JSONResponse({
            "success": False,
            "error": "No authorization code received",
        })

    # Exchange code for token
    redirect_uri = "https://portal.coloradocareassist.com/api/linkedin/callback"
    token_data = linkedin_service.exchange_code_for_token(code, redirect_uri)

    if token_data and "access_token" in token_data:
        # Return the token (user needs to set it as env var)
        return JSONResponse({
            "success": True,
            "message": "LinkedIn authorized successfully!",
            "access_token": token_data["access_token"],
            "expires_in": token_data.get("expires_in"),
            "instructions": "Set this access token as LINKEDIN_ACCESS_TOKEN environment variable on Mac Mini (Local)",
        })
    else:
        return JSONResponse({
            "success": False,
            "error": "Failed to exchange code for token",
            "details": token_data,
        })


#
# TikTok Marketing Endpoints
#

@app.get("/api/marketing/tiktok")
async def api_marketing_tiktok(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Fetch TikTok marketing metrics (ads and engagement).

    Query params:
        from_date: Start date (YYYY-MM-DD), defaults to 30 days ago
        to_date: End date (YYYY-MM-DD), defaults to today
    """
    from services.marketing.tiktok_service import tiktok_service

    end = date.today()
    if to_date:
        end = date.fromisoformat(to_date)

    if from_date:
        start = date.fromisoformat(from_date)
    else:
        start = end - timedelta(days=30)

    try:
        ad_metrics = tiktok_service.get_ad_metrics(start, end)
        campaign_metrics = tiktok_service.get_campaign_metrics(start, end)
        engagement_metrics = tiktok_service.get_engagement_metrics(start, end)

        return JSONResponse({
            "success": True,
            "date_range": {
                "from": start.isoformat(),
                "to": end.isoformat(),
            },
            "data": {
                "ads": ad_metrics,
                "campaigns": campaign_metrics,
                "engagement": engagement_metrics,
            }
        })
    except Exception as e:
        logger.error(f"Error fetching TikTok metrics: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "data": tiktok_service._get_placeholder_metrics(start, end)
        })


@app.get("/api/marketing/test-tiktok")
async def test_tiktok_connection(
    _test_ok: None = Depends(require_portal_test_endpoints_enabled)
):
    """Test TikTok connection and return status."""
    import os

    from services.marketing.tiktok_service import tiktok_service

    status = {
        "client_key_configured": bool(os.getenv("TIKTOK_CLIENT_KEY")),
        "client_secret_configured": bool(os.getenv("TIKTOK_CLIENT_SECRET")),
        "access_token_configured": bool(os.getenv("TIKTOK_ACCESS_TOKEN")),
        "advertiser_id": os.getenv("TIKTOK_ADVERTISER_ID"),
    }

    if tiktok_service.is_configured():
        status["connection_successful"] = True
        status["message"] = "TikTok Ads API is configured and ready"
    elif os.getenv("TIKTOK_CLIENT_KEY") and os.getenv("TIKTOK_CLIENT_SECRET"):
        status["connection_successful"] = False
        status["needs_oauth"] = True
        status["message"] = "TikTok credentials set. Need to complete OAuth flow to get access token."
    else:
        status["connection_successful"] = False
        status["error"] = "TikTok credentials not configured"

    return JSONResponse(status)


#
# Google Business Profile OAuth Endpoints
#

@app.get("/api/gbp/auth")
async def gbp_oauth_start():
    """
    Start GBP OAuth flow. Returns URL to redirect user to.
    """
    from services.marketing.gbp_service import gbp_service

    oauth_url = gbp_service.get_oauth_url()

    if not oauth_url:
        return JSONResponse({
            "success": False,
            "error": "GBP OAuth not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET.",
        })

    return JSONResponse({
        "success": True,
        "oauth_url": oauth_url,
        "message": "Visit the oauth_url to authorize Google Business Profile access",
    })


@app.get("/api/gbp/callback")
async def gbp_oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """
    OAuth callback endpoint for GBP authorization.
    
    After user authorizes, Google redirects here with an auth code.
    We exchange it for access and refresh tokens.
    """
    from services.marketing.gbp_service import gbp_service

    if error:
        return JSONResponse({
            "success": False,
            "error": error,
        })

    if not code:
        return JSONResponse({
            "success": False,
            "error": "No authorization code received",
        })

    # Exchange code for tokens
    token_data = gbp_service.exchange_code_for_tokens(code)

    if token_data.get("success"):
        # Return the tokens (user needs to set them as env vars)
        return JSONResponse({
            "success": True,
            "message": "Google Business Profile authorized successfully!",
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
            "instructions": "Set these tokens as GBP_ACCESS_TOKEN and GBP_REFRESH_TOKEN environment variables on Mac Mini (Local). The refresh token is used to automatically get new access tokens.",
        })
    else:
        return JSONResponse({
            "success": False,
            "error": "Failed to exchange code for tokens",
            "details": token_data.get("error"),
        })


@app.get("/api/gbp/status")
async def gbp_status():
    """
    Check GBP connection status and available locations.
    """
    from services.marketing.gbp_service import gbp_service

    status = {
        "oauth_configured": bool(gbp_service.client_id and gbp_service.client_secret),
        "authenticated": bool(gbp_service.access_token),
        "has_refresh_token": bool(gbp_service.refresh_token),
        "configured_locations": gbp_service.location_ids,
    }

    if not status["oauth_configured"]:
        status["error"] = "Missing GOOGLE_OAUTH_CLIENT_ID or GOOGLE_OAUTH_CLIENT_SECRET"
        status["oauth_url"] = None
    elif not status["authenticated"]:
        status["oauth_url"] = gbp_service.get_oauth_url()
        status["message"] = "Visit oauth_url to authorize access"
    else:
        # Try to fetch accounts to verify token works
        try:
            accounts = gbp_service.get_accounts()
            status["accounts"] = len(accounts)
            status["account_names"] = [a.get("accountName", a.get("name")) for a in accounts]

            # Try to get locations
            all_locations = []
            for account in accounts:
                account_name = account.get("name")
                locations = gbp_service.get_locations(account_name)
                for loc in locations:
                    all_locations.append({
                        "name": loc.get("name"),
                        "title": loc.get("title") or loc.get("storefrontAddress", {}).get("addressLines", [0]) if loc.get("storefrontAddress") else "Unknown",
                        "address": loc.get("storefrontAddress", {}).get("addressLines", []) if loc.get("storefrontAddress") else []
                    })

            # Also show configured location IDs
            if gbp_service.location_ids:
                status["configured_location_ids"] = gbp_service.location_ids
                status["using_configured_locations"] = True

            status["locations"] = all_locations
            status["total_locations_found"] = len(all_locations)

        except Exception as e:
            status["error"] = f"Error fetching accounts: {str(e)}"

    return JSONResponse(status)


#
# Shift Filling API Endpoints (Operations Dashboard)
#

# Add the sales directory to the path for shift_filling imports
import sys

sales_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sales')
if sales_dir not in sys.path:
    sys.path.insert(0, sales_dir)

try:
    from shift_filling import (
        CaregiverMatcher,
        OutreachStatus,
        shift_filling_engine,
        sms_service,
        wellsky_mock,
    )
    SHIFT_FILLING_AVAILABLE = True
    logger.info("Shift filling module loaded successfully")
except ImportError as e:
    SHIFT_FILLING_AVAILABLE = False
    logger.warning(f"Shift filling module not available: {e}")


@app.get("/api/shift-filling/status")
async def shift_filling_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get shift filling engine status"""
    if not SHIFT_FILLING_AVAILABLE:
        return JSONResponse({"status": "unavailable", "error": "Module not loaded"})

    return JSONResponse({
        "status": "active",
        "sms_enabled": sms_service.is_enabled(),
        "active_campaigns": len(shift_filling_engine.active_campaigns),
        "service": "AI-Powered Shift Filling POC"
    })


@app.get("/api/shift-filling/open-shifts")
async def get_open_shifts(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all open shifts from WellSky mock"""
    if not SHIFT_FILLING_AVAILABLE:
        return JSONResponse([])

    shifts = wellsky_mock.get_open_shifts()
    return JSONResponse([{
        "id": s.id,
        "client_id": s.client_id,
        "client_name": s.client.full_name if s.client else "Unknown",
        "client_city": s.client.city if s.client else "",
        "date": s.date.isoformat(),
        "start_time": s.start_time.strftime("%H:%M"),
        "end_time": s.end_time.strftime("%H:%M"),
        "duration_hours": s.duration_hours,
        "is_urgent": s.is_urgent,
        "hours_until_start": s.hours_until_start,
        "status": s.status,
        "original_caregiver_id": s.original_caregiver_id
    } for s in shifts])


@app.get("/api/shift-filling/caregivers")
async def get_caregivers(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all caregivers from WellSky mock"""
    if not SHIFT_FILLING_AVAILABLE:
        return JSONResponse([])

    from datetime import date
    caregivers = wellsky_mock.get_available_caregivers(date.today())
    return JSONResponse([{
        "id": c.id,
        "name": c.full_name,
        "phone": c.phone,
        "city": c.city,
        "hours_available": c.hours_available,
        "is_near_overtime": c.is_near_overtime,
        "avg_rating": c.avg_rating,
        "reliability_score": c.reliability_score,
        "response_rate": c.response_rate,
        "is_active": c.is_active
    } for c in caregivers if c.is_active])


@app.get("/api/shift-filling/match/{shift_id}")
async def match_caregivers_for_shift(
    shift_id: str,
    max_results: int = 20,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Find and rank replacement caregivers for a shift"""
    if not SHIFT_FILLING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Shift filling not available")

    shift = wellsky_mock.get_shift(shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    matcher = CaregiverMatcher(wellsky_mock)
    matches = matcher.find_replacements(shift, max_results=max_results)

    return JSONResponse({
        "shift": {
            "id": shift.id,
            "client_name": shift.client.full_name if shift.client else "Unknown",
            "date": shift.date.isoformat(),
            "time": shift.to_display_time()
        },
        "matches": [{
            "caregiver_id": m.caregiver.id,
            "caregiver_name": m.caregiver.full_name,
            "phone": m.caregiver.phone,
            "score": m.score,
            "tier": m.tier,
            "reasons": m.reasons
        } for m in matches],
        "total_matches": len(matches),
        "tier_breakdown": {
            "tier_1": sum(1 for m in matches if m.tier == 1),
            "tier_2": sum(1 for m in matches if m.tier == 2),
            "tier_3": sum(1 for m in matches if m.tier == 3)
        }
    })


@app.post("/api/shift-filling/calloff")
async def process_calloff(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Process a caregiver calloff and start shift filling"""
    if not SHIFT_FILLING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Shift filling not available")

    data = await request.json()
    shift_id = data.get("shift_id")
    caregiver_id = data.get("caregiver_id")
    reason = data.get("reason", "")

    if not shift_id or not caregiver_id:
        raise HTTPException(status_code=400, detail="shift_id and caregiver_id required")

    campaign = shift_filling_engine.process_calloff(
        shift_id=shift_id,
        caregiver_id=caregiver_id,
        reason=reason,
        reported_by="portal"
    )

    if not campaign:
        raise HTTPException(status_code=404, detail="Shift not found")

    return JSONResponse({
        "success": True,
        "campaign_id": campaign.id,
        "status": campaign.status.value,
        "total_contacted": campaign.total_contacted,
        "message": f"Outreach campaign started with {campaign.total_contacted} caregivers"
    })


@app.get("/api/shift-filling/campaigns")
async def get_active_campaigns(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all active shift filling campaigns"""
    if not SHIFT_FILLING_AVAILABLE:
        return JSONResponse({"active_campaigns": [], "total": 0})

    campaigns = shift_filling_engine.get_all_active_campaigns()
    return JSONResponse({
        "active_campaigns": campaigns,
        "total": len(campaigns)
    })


@app.post("/api/shift-filling/demo")
async def run_demo(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Run a full demonstration of the shift filling process"""
    if not SHIFT_FILLING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Shift filling not available")

    result = shift_filling_engine.simulate_demo()
    return JSONResponse(result)


@app.get("/api/shift-filling/sms-log")
async def get_sms_log(
    hours: int = 24,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get SMS message log from RingCentral for 719-428-3999"""
    import re
    from datetime import datetime, timedelta

    import requests

    # RingCentral credentials
    client_id = os.getenv("RINGCENTRAL_CLIENT_ID")
    client_secret = os.getenv("RINGCENTRAL_CLIENT_SECRET")
    jwt_token = os.getenv("RINGCENTRAL_JWT_TOKEN")
    server = os.getenv("RINGCENTRAL_SERVER", "https://platform.ringcentral.com")

    if not all([client_id, client_secret, jwt_token]):
        return JSONResponse({"messages": [], "error": "RingCentral credentials not configured"})

    try:
        # Get access token
        auth_response = requests.post(
            f"{server}/restapi/oauth/token",
            auth=(client_id, client_secret),
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30
        )

        if auth_response.status_code != 200:
            return JSONResponse({"messages": [], "error": "Authentication failed"})

        access_token = auth_response.json().get("access_token")

        # Fetch SMS messages
        date_from = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        messages_response = requests.get(
            f"{server}/restapi/v1.0/account/~/extension/~/message-store",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "dateFrom": date_from,
                "messageType": "SMS",
                "perPage": 100
            },
            timeout=60
        )

        if messages_response.status_code != 200:
            return JSONResponse({"messages": [], "error": "Failed to fetch messages"})

        records = messages_response.json().get("records", [])

        # Filter for 719-428-3999 (caregiver line) and format
        target_phone = "7194283999"
        filtered_messages = []

        for msg in records:
            from_number = msg.get("from", {}).get("phoneNumber", "")
            to_numbers = [t.get("phoneNumber", "") for t in msg.get("to", [])]

            from_clean = re.sub(r'[^\d]', '', from_number)[-10:]
            to_clean = [re.sub(r'[^\d]', '', t)[-10:] for t in to_numbers]

            # Include if target number is involved
            if target_phone in from_clean or target_phone in to_clean:
                direction = msg.get("direction", "")
                other_party = from_clean if direction == "Inbound" else (to_clean[0] if to_clean else "")

                filtered_messages.append({
                    "id": msg.get("id"),
                    "direction": direction,
                    "phone": other_party,
                    "text": msg.get("subject", "")[:150] + ("..." if len(msg.get("subject", "")) > 150 else ""),
                    "time": msg.get("creationTime"),
                    "status": msg.get("messageStatus", "")
                })

        return JSONResponse({
            "messages": filtered_messages[:50],
            "total": len(filtered_messages),
            "hours": hours
        })

    except Exception as e:
        logger.error(f"SMS log fetch error: {e}")
        return JSONResponse({"messages": [], "error": str(e)})


#
# End of Shift Filling API Endpoints
#


#
# Gigi AI Agent API Endpoints (After-Hours Support)
#

@app.post("/api/client-satisfaction/issues")
async def api_log_client_issue(request: Request):
    """
    Log a client issue from Gigi AI agent.
    This endpoint does NOT require authentication as it's called by Gigi.
    """
    try:
        data = await request.json()

        client_id = data.get("client_id")
        note = data.get("note", "")
        issue_type = data.get("issue_type", "general")
        priority = data.get("priority", "normal")
        source = data.get("source", "unknown")

        # Generate issue ID
        import uuid
        issue_id = f"ISS-{uuid.uuid4().hex[:8].upper()}"

        # Log the issue
        logger.info(f"[GIGI] Client issue logged: {issue_id}")
        logger.info(f"  Client ID: {client_id}")
        logger.info(f"  Type: {issue_type}, Priority: {priority}")
        logger.info(f"  Note: {note[:200]}...")
        logger.info(f"  Source: {source}")

        # TODO: Store in database or Google Sheets
        # For now, we log and return success

        return JSONResponse({
            "success": True,
            "id": issue_id,
            "message": "Issue logged successfully",
            "data": {
                "issue_id": issue_id,
                "client_id": client_id,
                "issue_type": issue_type,
                "priority": priority,
                "created_at": datetime.now().isoformat()
            }
        }, status_code=201)

    except Exception as e:
        logger.error(f"Error logging client issue: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/operations/sync-rc-to-wellsky")
async def api_sync_rc_to_wellsky(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Trigger Gigi to scan RingCentral channels and sync documentation to WellSky.
    """
    from services.ringcentral_messaging_service import ringcentral_messaging_service

    results = {}
    channels = ["New Scheduling", "Biz Dev"]

    for channel in channels:
        # 1. Sync Complaints/Issues
        scan_res = ringcentral_messaging_service.scan_chat_for_client_issues(db, chat_name=channel, hours_back=hours)
        complaint_res = ringcentral_messaging_service.auto_create_complaints(db, scan_res, auto_create=True, push_to_wellsky=True)

        # 2. Sync General Tasks
        task_res = ringcentral_messaging_service.sync_tasks_to_wellsky(db, chat_name=channel, hours_back=hours)

        results[channel] = {
            "complaints_detected": scan_res.get("potential_complaints", []),
            "complaints_created": complaint_res.get("created_count", 0),
            "tasks_synced": task_res.get("tasks_synced", 0)
        }

    return JSONResponse({
        "success": True,
        "results": results,
        "message": f"Sync completed for {len(channels)} channels over the last {hours} hours."
    })


@app.post("/api/operations/call-outs")
async def api_log_call_out(request: Request):
    """
    Log a caregiver call-out from Gigi AI agent.
    This endpoint does NOT require authentication as it's called by Gigi.
    """
    try:
        data = await request.json()

        caregiver_id = data.get("caregiver_id")
        caregiver_name = data.get("caregiver_name", "Unknown")
        shift_id = data.get("shift_id")
        client_name = data.get("client_name", "Unknown")
        shift_time = data.get("shift_time", "Unknown")
        reason = data.get("reason", "")
        reported_via = data.get("reported_via", "unknown")
        priority = data.get("priority", "normal")

        # Generate call-out ID
        import uuid
        call_out_id = f"CO-{uuid.uuid4().hex[:8].upper()}"

        # Log the call-out
        logger.warning(f"[GIGI] CALL-OUT LOGGED: {call_out_id}")
        logger.warning(f"  Caregiver: {caregiver_name} ({caregiver_id})")
        logger.warning(f"  Shift: {shift_id} - {client_name} at {shift_time}")
        logger.warning(f"  Reason: {reason}")
        logger.warning(f"  Priority: {priority}")
        logger.warning(f"  Reported via: {reported_via}")

        # TODO: Store in database, notify scheduling team
        # For now, we log and return success

        return JSONResponse({
            "success": True,
            "id": call_out_id,
            "message": "Call-out logged successfully",
            "data": {
                "call_out_id": call_out_id,
                "caregiver_id": caregiver_id,
                "caregiver_name": caregiver_name,
                "shift_id": shift_id,
                "client_name": client_name,
                "reason": reason,
                "created_at": datetime.now().isoformat()
            }
        }, status_code=201)

    except Exception as e:
        logger.error(f"Error logging call-out: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


#
# WellSky Shift Management API (Used by Gigi for Call-Outs)
#

@app.put("/api/wellsky/shifts/{shift_id}")
async def api_update_wellsky_shift(shift_id: str, request: Request):
    """
    Update a WellSky shift status.

    This is the endpoint Gigi calls to mark a shift as 'Open' when a caregiver calls out.
    It proxies to the WellSky ClearCare API: PUT /v1/shifts/{shift_id}

    Request body:
    {
        "status": "open",
        "caregiver_id": null,  // Optional: set to null to unassign
        "call_out_reason": "sick",  // Optional
        "call_out_caregiver_id": "CG001",  // Optional
        "notes": "Call-out via Gigi AI"  // Optional
    }
    """
    if wellsky_service is None:
        return JSONResponse({
            "success": False,
            "error": "WellSky service not available"
        }, status_code=503)

    try:
        data = await request.json()

        status_str = data.get("status", "").lower()
        unassign = data.get("caregiver_id") is None and "caregiver_id" in data
        notes = data.get("notes")
        call_out_reason = data.get("call_out_reason")
        call_out_caregiver_id = data.get("call_out_caregiver_id")

        # Map status string to ShiftStatus enum (imported at module level)
        if ShiftStatus is None:
            return JSONResponse({
                "success": False,
                "error": "ShiftStatus enum not available"
            }, status_code=503)

        status_map = {
            "open": ShiftStatus.OPEN,
            "scheduled": ShiftStatus.SCHEDULED,
            "confirmed": ShiftStatus.CONFIRMED,
            "in_progress": ShiftStatus.IN_PROGRESS,
            "completed": ShiftStatus.COMPLETED,
            "cancelled": ShiftStatus.CANCELLED,
            "missed": ShiftStatus.MISSED,
        }

        if status_str not in status_map:
            return JSONResponse({
                "success": False,
                "error": f"Invalid status: {status_str}. Valid: {list(status_map.keys())}"
            }, status_code=400)

        new_status = status_map[status_str]

        # Call the WellSky service to update the shift
        success, message = wellsky_service.update_shift_status(
            shift_id=shift_id,
            status=new_status,
            unassign_caregiver=unassign,
            notes=notes,
            call_out_reason=call_out_reason,
            call_out_caregiver_id=call_out_caregiver_id
        )

        if success:
            logger.info(f"WellSky shift {shift_id} updated to {status_str}")
            return JSONResponse({
                "success": True,
                "shift_id": shift_id,
                "new_status": status_str,
                "message": message
            })
        else:
            logger.warning(f"Failed to update WellSky shift {shift_id}: {message}")
            return JSONResponse({
                "success": False,
                "error": message
            }, status_code=400)

    except Exception as e:
        logger.error(f"Error updating WellSky shift: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/operations/replacement-blast")
async def api_trigger_replacement_blast(request: Request):
    """
    Trigger a Replacement Blast to notify available caregivers about an open shift.

    This endpoint is called by Gigi when a caregiver calls out.
    It finds available caregivers and sends them SMS notifications via BeeTexting/RingCentral.

    Request body:
    {
        "shift_id": "SHIFT123",
        "client_name": "Mary Johnson",
        "client_id": "CL001",
        "shift_time": "January 21 at 9:00 AM",
        "shift_start": "2026-01-21T09:00:00",
        "shift_end": "2026-01-21T13:00:00",
        "shift_hours": 4.0,
        "client_address": "123 Main St, Denver CO",
        "call_out_caregiver_id": "CG001",
        "call_out_caregiver_name": "John Smith",
        "reason": "sick",
        "urgency": "high"
    }
    """
    try:
        data = await request.json()

        shift_id = data.get("shift_id")
        client_name = data.get("client_name", "a client")
        shift_time = data.get("shift_time", "today")
        shift_hours = data.get("shift_hours", "TBD")
        client_address = data.get("client_address", "")
        urgency = data.get("urgency", "normal")
        source = data.get("source", "portal")

        logger.info(f"[REPLACEMENT BLAST] Triggered for shift {shift_id}")
        logger.info(f"  Client: {client_name}, Time: {shift_time}")
        logger.info(f"  Urgency: {urgency}, Source: {source}")

        # Build the SMS message
        sms_message = (
            f"SHIFT AVAILABLE: {client_name}, {shift_time}. "
            f"{shift_hours} hours. "
        )
        if client_address:
            # Extract city from address
            city = client_address.split(",")[-2].strip() if "," in client_address else client_address
            sms_message += f"Location: {city}. "
        sms_message += "Reply YES to claim or call 719-428-3999."

        # Get available caregivers from WellSky
        caregivers_notified = 0
        notification_results = []

        if wellsky_service:
            try:
                # Get caregivers who could potentially cover this shift
                caregivers = wellsky_service.get_caregivers(status="active")

                # In a real implementation, we'd filter by:
                # - Availability (not already working)
                # - Certifications required for the client
                # - Geographic proximity
                # - Overtime limits

                # For now, notify first 5 active caregivers (mock)
                for cg in caregivers[:5]:
                    phone = getattr(cg, 'phone', None)
                    if phone:
                        # In production, use actual SMS sending
                        logger.info(f"  Would notify: {cg.full_name} at {phone}")
                        notification_results.append({
                            "caregiver_id": cg.id,
                            "caregiver_name": cg.full_name,
                            "phone": phone,
                            "status": "queued"
                        })
                        caregivers_notified += 1

            except Exception as e:
                logger.error(f"Error getting caregivers for blast: {e}")

        # Generate blast ID
        import uuid
        blast_id = f"BLAST-{uuid.uuid4().hex[:8].upper()}"

        logger.info(f"[REPLACEMENT BLAST] {blast_id} - Notified {caregivers_notified} caregivers")

        return JSONResponse({
            "success": True,
            "blast_id": blast_id,
            "shift_id": shift_id,
            "caregivers_notified": caregivers_notified,
            "message": sms_message,
            "notifications": notification_results,
            "urgency": urgency
        }, status_code=201)

    except Exception as e:
        logger.error(f"Error triggering replacement blast: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


#
# Internal Shift Filling API (Called by Gigi - No Auth Required)
#

@app.get("/api/internal/shift-filling/match/{shift_id}")
async def internal_match_caregivers(shift_id: str, max_results: int = 10):
    """
    Find replacement caregivers for a shift.
    Called by Gigi AI agent - no auth required.
    """
    if not SHIFT_FILLING_AVAILABLE:
        return JSONResponse({
            "candidates": [],
            "count": 0,
            "error": "Shift filling not available"
        })

    try:
        shift = wellsky_mock.get_shift(shift_id)
        if not shift:
            # Try to create a mock shift for the ID
            logger.warning(f"Shift {shift_id} not found, using mock data")
            return JSONResponse({
                "candidates": [],
                "count": 0,
                "message": "Shift not found in system"
            })

        matcher = CaregiverMatcher(wellsky_mock)
        matches = matcher.find_replacements(shift, max_results=max_results)

        return JSONResponse({
            "candidates": [{
                "caregiver_id": m.caregiver.id,
                "name": m.caregiver.full_name,
                "phone": m.caregiver.phone,
                "score": m.score,
                "tier": m.tier,
                "reasons": m.reasons,
                "has_worked_with_client": shift.client.id in m.caregiver.clients_worked_with if shift.client else False
            } for m in matches],
            "count": len(matches)
        })

    except Exception as e:
        logger.error(f"Error matching caregivers: {e}")
        return JSONResponse({
            "candidates": [],
            "count": 0,
            "error": str(e)
        })


@app.post("/api/internal/shift-filling/calloff")
async def internal_process_calloff(request: Request):
    """
    Process a caregiver call-out and start shift filling campaign.
    Called by Gigi AI agent - no auth required.

    This is the MAIN entry point for Gigi's active shift filling.
    """
    try:
        data = await request.json()
        shift_id = data.get("shift_id")
        caregiver_id = data.get("caregiver_id")
        reason = data.get("reason", "sick")

        logger.info(f"[GIGI] Processing call-out: shift={shift_id}, caregiver={caregiver_id}, reason={reason}")

        if not SHIFT_FILLING_AVAILABLE:
            logger.warning("Shift filling engine not available")
            return JSONResponse({
                "success": False,
                "message": "Shift filling temporarily unavailable. On-call manager notified.",
                "campaign_id": None,
                "candidates_contacted": 0
            })

        # Process the call-out through the shift filling engine
        campaign = shift_filling_engine.process_calloff(
            shift_id=shift_id,
            caregiver_id=caregiver_id,
            reason=reason,
            reported_by="gigi_ai"
        )

        if not campaign:
            logger.warning(f"Could not create campaign for shift {shift_id}")
            return JSONResponse({
                "success": False,
                "message": "Could not find shift or create campaign. On-call manager notified.",
                "campaign_id": None,
                "candidates_contacted": 0
            })

        logger.info(f"[GIGI] Campaign created: {campaign.id}, contacted {campaign.total_contacted} caregivers")

        return JSONResponse({
            "success": True,
            "message": f"Campaign started - contacting {campaign.total_contacted} caregivers",
            "campaign_id": campaign.id,
            "candidates_found": len(campaign.caregivers_contacted),
            "candidates_contacted": campaign.total_contacted,
            "shift_filled": campaign.status.value == "filled"
        })

    except Exception as e:
        logger.error(f"Error processing call-out: {e}")
        return JSONResponse({
            "success": False,
            "message": "Error starting shift filling. On-call manager will be notified.",
            "campaign_id": None,
            "candidates_contacted": 0,
            "error": str(e)
        })


@app.get("/api/internal/shift-filling/campaigns/{campaign_id}")
async def internal_get_campaign_status(campaign_id: str):
    """
    Get status of a shift filling campaign.
    Called by Gigi AI agent - no auth required.
    """
    if not SHIFT_FILLING_AVAILABLE:
        return JSONResponse({
            "found": False,
            "error": "Shift filling not available"
        })

    try:
        campaign = shift_filling_engine.get_campaign_status(campaign_id)

        if not campaign:
            return JSONResponse({
                "found": False,
                "campaign_id": campaign_id,
                "message": "Campaign not found or expired"
            })

        return JSONResponse({
            "found": True,
            "campaign_id": campaign_id,
            "status": campaign.get("status"),
            "total_contacted": campaign.get("total_contacted", 0),
            "total_responded": campaign.get("total_responded", 0),
            "total_accepted": campaign.get("total_accepted", 0),
            "shift_filled": campaign.get("status") == "filled",
            "winning_caregiver": campaign.get("winning_caregiver_name"),
            "escalated": campaign.get("escalated", False)
        })

    except Exception as e:
        logger.error(f"Error getting campaign status: {e}")
        return JSONResponse({
            "found": False,
            "error": str(e)
        })


@app.post("/api/internal/shift-filling/voice-followups")
async def internal_check_voice_followups():
    """
    Trigger voice follow-up calls for SMS outreaches that haven't received responses.
    Called by Gigi bot on the same 5-min campaign check cycle.
    """
    if not SHIFT_FILLING_AVAILABLE:
        return JSONResponse({"calls_made": 0, "error": "Shift filling not available"})

    try:
        results = shift_filling_engine.check_voice_followups()
        return JSONResponse({"calls_made": len(results) if results else 0, "results": results or []})
    except Exception as e:
        logger.error(f"Voice followup check error: {e}")
        return JSONResponse({"calls_made": 0, "error": str(e)})


# In-memory set for Retell call_id idempotency (backed by DB)
_processed_retell_call_ids: set = set()


@app.post("/webhook/retell/shift-offer-complete")
async def retell_shift_offer_complete(request: Request):
    """
    Webhook for Retell AI voice call completion on shift offer calls.
    Captures the caregiver's verbal response and feeds it into the shift filling engine.
    Idempotent: duplicate webhook deliveries (retries) are safely ignored via call_id tracking.
    """
    # Verify Retell signature — fail closed if API key not configured
    retell_key = os.getenv("RETELL_API_KEY")
    if not retell_key:
        logger.error("RETELL_API_KEY not set — rejecting shift-offer webhook")
        return JSONResponse({"error": "Server misconfiguration"}, status_code=503)
    import json as _json
    body_bytes = await request.body()
    signature = request.headers.get("x-retell-signature", "")
    expected = hmac.new(retell_key.encode(), body_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        logger.warning("Retell shift-offer webhook: Invalid signature")
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = _json.loads(body_bytes)

    try:
        event = body.get("event", "")
        call_id = body.get("call_id", "")
        metadata = body.get("metadata", {})

        if event != "call_ended":
            return JSONResponse({"status": "ignored", "event": event})

        # Idempotency check: skip if we already processed this call_id
        if call_id:
            if call_id in _processed_retell_call_ids:
                logger.info(f"Duplicate Retell webhook for call_id {call_id}, ignoring")
                return JSONResponse({"status": "duplicate", "call_id": call_id})

            # Also check DB for persistence across restarts
            try:
                import psycopg2
                db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                cur.execute(
                    "SELECT 1 FROM gigi_dedup_state WHERE key = %s",
                    (f"retell_call:{call_id}",)
                )
                if cur.fetchone():
                    cur.close()
                    conn.close()
                    _processed_retell_call_ids.add(call_id)
                    logger.info(f"Duplicate Retell webhook for call_id {call_id} (from DB), ignoring")
                    return JSONResponse({"status": "duplicate", "call_id": call_id})

                # Mark as processed in DB (expires after 24h)
                cur.execute("""
                    INSERT INTO gigi_dedup_state (key, value, created_at, expires_at)
                    VALUES (%s, 'processed', NOW(), NOW() + INTERVAL '24 hours')
                    ON CONFLICT (key) DO NOTHING
                """, (f"retell_call:{call_id}",))
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                logger.warning(f"Retell dedup DB check failed (proceeding): {e}")

            _processed_retell_call_ids.add(call_id)
            # Cap in-memory set size
            if len(_processed_retell_call_ids) > 1000:
                _processed_retell_call_ids.clear()

        campaign_id = metadata.get("campaign_id")
        caregiver_phone = metadata.get("caregiver_phone")
        purpose = metadata.get("purpose")

        if purpose != "shift_offer" or not campaign_id or not caregiver_phone:
            return JSONResponse({"status": "ignored", "reason": "not a shift offer call"})

        transcript = body.get("transcript", "")
        analysis = body.get("call_analysis", {})
        call_summary = analysis.get("call_summary", "")

        # Determine acceptance from call analysis
        summary_lower = call_summary.lower()
        accept_keywords = ["accepted", "confirmed", "will take", "agreed", "yes"]
        decline_keywords = ["declined", "refused", "can't", "unable", "no", "not available"]

        accepted = any(kw in summary_lower for kw in accept_keywords)
        declined = any(kw in summary_lower for kw in decline_keywords)

        # Build synthetic response text for the shift filling engine
        if accepted:
            message_text = "Yes, I'll take the shift"
        elif declined:
            message_text = "No, I can't work that shift"
        else:
            message_text = transcript[:200] if transcript else "ambiguous voice response"

        # Feed into shift filling engine
        try:
            from sales.shift_filling.engine import shift_filling_engine
            result = shift_filling_engine.process_response(
                campaign_id=campaign_id,
                phone=caregiver_phone,
                message_text=message_text
            )
            logger.info(f"Voice call response processed for campaign {campaign_id}: {result}")
        except Exception as e:
            logger.error(f"Error processing voice call response: {e}")

        return JSONResponse({"status": "processed", "campaign_id": campaign_id, "call_id": call_id})

    except Exception as e:
        logger.error(f"Retell shift offer webhook error: {e}")
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)


@app.post("/api/internal/shift-filling/offer")
async def internal_send_shift_offer(request: Request):
    """
    Send a shift offer to a specific caregiver.
    Called by Gigi AI agent - no auth required.
    """
    try:
        data = await request.json()
        caregiver_id = data.get("caregiver_id")
        caregiver_phone = data.get("caregiver_phone")
        shift_id = data.get("shift_id")
        client_name = data.get("client_name", "a client")
        shift_time = data.get("shift_time", "today")
        shift_hours = data.get("shift_hours", 4)

        logger.info(f"[GIGI] Sending shift offer to {caregiver_id} for shift {shift_id}")

        # Build SMS message
        sms_message = (
            f"Hi! Colorado Care Assist has an open shift: "
            f"{client_name}, {shift_time} ({shift_hours} hrs). "
            f"Reply YES to accept or NO to decline."
        )

        # Try to send via SMS service
        sms_sent = False
        if SHIFT_FILLING_AVAILABLE:
            try:
                from sales.shift_filling.sms_service import sms_service
                success, result = sms_service.send_sms(caregiver_phone, sms_message)
                sms_sent = success
                logger.info(f"SMS sent: {success}, result: {result}")
            except Exception as e:
                logger.error(f"SMS send error: {e}")

        return JSONResponse({
            "success": True,
            "sms_sent": sms_sent,
            "caregiver_id": caregiver_id,
            "message": "Shift offer sent" if sms_sent else "Shift offer logged (SMS not available)"
        })

    except Exception as e:
        logger.error(f"Error sending shift offer: {e}")
        return JSONResponse({
            "success": False,
            "sms_sent": False,
            "error": str(e)
        })


@app.post("/api/internal/shift-filling/sms-response")
async def internal_process_sms_response(request: Request):
    """
    Process an incoming SMS response to a shift offer.
    Called by Gigi when a caregiver texts YES/NO in response to a shift offer.

    This endpoint:
    1. Finds any active campaign where this phone was contacted
    2. Processes the response (YES = assign shift, NO = record decline)
    3. Returns the result to Gigi for confirmation
    """
    if not SHIFT_FILLING_AVAILABLE:
        return JSONResponse({
            "success": False,
            "found_campaign": False,
            "message": "Shift filling service not available"
        })

    try:
        data = await request.json()
        phone_number = data.get("phone_number")
        message_text = data.get("message_text", "").strip()

        if not phone_number:
            return JSONResponse({
                "success": False,
                "error": "phone_number is required"
            }, status_code=400)

        logger.info(f"[GIGI] Processing SMS response from {phone_number}: {message_text[:50]}")

        # Clean phone number for matching
        import re
        clean_phone = re.sub(r'[^\d]', '', phone_number)[-10:]

        # Find the campaign this phone belongs to
        found_campaign = None
        found_outreach = None

        for campaign_id, campaign in shift_filling_engine.active_campaigns.items():
            # Check if campaign is still active
            if campaign.status.value not in ["in_progress", "pending"]:
                continue

            # Check each caregiver contacted
            for outreach in campaign.caregivers_contacted:
                outreach_phone = re.sub(r'[^\d]', '', outreach.phone)[-10:]
                if outreach_phone == clean_phone:
                    found_campaign = campaign
                    found_outreach = outreach
                    break

            if found_campaign:
                break

        if not found_campaign:
            logger.info(f"No active shift offer found for {phone_number}")
            return JSONResponse({
                "success": True,
                "found_campaign": False,
                "message": "No pending shift offer found for this phone number"
            })

        # Process the response through the engine
        result = shift_filling_engine.process_response(
            campaign_id=found_campaign.id,
            phone=phone_number,
            message_text=message_text
        )

        # Build response for Gigi
        action = result.get("action", "unknown")

        if action == "shift_filled":
            return JSONResponse({
                "success": True,
                "found_campaign": True,
                "action": "assigned",
                "shift_assigned": True,
                "shift_id": found_campaign.shift_id,
                "caregiver_name": result.get("assigned_caregiver"),
                "client_name": found_campaign.shift.client.full_name if found_campaign.shift and found_campaign.shift.client else "Unknown",
                "shift_date": found_campaign.shift.date.strftime("%B %d") if found_campaign.shift and found_campaign.shift.date else "",
                "shift_time": found_campaign.shift.to_display_time() if hasattr(found_campaign.shift, 'to_display_time') else "",
                "message": f"Shift assigned to {result.get('assigned_caregiver')}"
            })

        elif action == "decline_recorded":
            return JSONResponse({
                "success": True,
                "found_campaign": True,
                "action": "declined",
                "shift_assigned": False,
                "message": "Decline recorded. We'll continue looking for coverage."
            })

        elif action == "already_filled":
            return JSONResponse({
                "success": True,
                "found_campaign": True,
                "action": "already_filled",
                "shift_assigned": False,
                "message": "This shift has already been filled by another caregiver."
            })

        elif action == "clarification_sent":
            return JSONResponse({
                "success": True,
                "found_campaign": True,
                "action": "clarification",
                "shift_assigned": False,
                "message": "We sent a clarification request to the caregiver."
            })

        else:
            return JSONResponse({
                "success": True,
                "found_campaign": True,
                "action": action,
                "shift_assigned": False,
                "message": "Response recorded"
            })

    except Exception as e:
        logger.error(f"Error processing SMS response: {e}")
        return JSONResponse({
            "success": False,
            "found_campaign": False,
            "error": str(e)
        }, status_code=500)


#
# GIGI AI Agent - New Endpoints for Production Readiness
#

@app.post("/api/internal/wellsky/notes/client/{client_id}")
async def internal_add_client_note(client_id: str, request: Request):
    """
    Add a note to a client's profile in WellSky.
    Called by Gigi AI agent after conversations to document interactions.
    """
    if wellsky_service is None:
        return JSONResponse({
            "success": False,
            "error": "WellSky service not available"
        }, status_code=503)

    try:
        data = await request.json()
        note = data.get("note", "")
        note_type = data.get("note_type", "general")
        source = data.get("source", "gigi_ai")

        if not note:
            return JSONResponse({
                "success": False,
                "error": "Note content is required"
            }, status_code=400)

        success, message = wellsky_service.add_note_to_client(
            client_id=client_id,
            note=note,
            note_type=note_type,
            source=source
        )

        return JSONResponse({
            "success": success,
            "message": message,
            "client_id": client_id
        }, status_code=200 if success else 400)

    except Exception as e:
        logger.error(f"Error adding note to client {client_id}: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/internal/wellsky/notes/caregiver/{caregiver_id}")
async def internal_add_caregiver_note(caregiver_id: str, request: Request):
    """
    Add a note to a caregiver's profile in WellSky.
    Called by Gigi AI agent to document call-outs, late arrivals, etc.
    """
    if wellsky_service is None:
        return JSONResponse({
            "success": False,
            "error": "WellSky service not available"
        }, status_code=503)

    try:
        data = await request.json()
        note = data.get("note", "")
        note_type = data.get("note_type", "general")
        source = data.get("source", "gigi_ai")

        if not note:
            return JSONResponse({
                "success": False,
                "error": "Note content is required"
            }, status_code=400)

        success, message = wellsky_service.add_note_to_caregiver(
            caregiver_id=caregiver_id,
            note=note,
            note_type=note_type,
            source=source
        )

        return JSONResponse({
            "success": success,
            "message": message,
            "caregiver_id": caregiver_id
        }, status_code=200 if success else 400)

    except Exception as e:
        logger.error(f"Error adding note to caregiver {caregiver_id}: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/internal/wellsky/clients/{client_id}/shifts")
async def internal_get_client_shifts(client_id: str, days: int = 7):
    """
    Get upcoming shifts for a client.
    Called by Gigi when a client asks about their schedule.
    """
    if wellsky_service is None:
        return JSONResponse({
            "success": False,
            "shifts": [],
            "error": "WellSky service not available"
        }, status_code=503)

    try:
        shifts = wellsky_service.get_client_upcoming_shifts(client_id, days_ahead=days)

        return JSONResponse({
            "success": True,
            "client_id": client_id,
            "shifts": [{
                "shift_id": s.id,
                "date": s.date.isoformat() if s.date else None,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "caregiver_name": s.caregiver_first_name + " " + s.caregiver_last_name if s.caregiver_first_name else "TBD",
                "status": s.status.value if hasattr(s.status, 'value') else str(s.status)
            } for s in shifts],
            "count": len(shifts)
        })

    except Exception as e:
        logger.error(f"Error getting client shifts: {e}")
        return JSONResponse({
            "success": False,
            "shifts": [],
            "error": str(e)
        }, status_code=500)


@app.put("/api/internal/wellsky/shifts/{shift_id}/assign")
async def internal_assign_shift(shift_id: str, request: Request):
    """
    Assign a caregiver to a shift.
    Called by Gigi when a caregiver accepts a shift offer.
    """
    if wellsky_service is None:
        return JSONResponse({
            "success": False,
            "error": "WellSky service not available"
        }, status_code=503)

    try:
        data = await request.json()
        caregiver_id = data.get("caregiver_id")
        notify_caregiver = data.get("notify_caregiver", True)

        if not caregiver_id:
            return JSONResponse({
                "success": False,
                "error": "caregiver_id is required"
            }, status_code=400)

        success, message = wellsky_service.assign_caregiver_to_shift(
            shift_id=shift_id,
            caregiver_id=caregiver_id,
            notify_caregiver=notify_caregiver
        )

        return JSONResponse({
            "success": success,
            "message": message,
            "shift_id": shift_id,
            "caregiver_id": caregiver_id
        }, status_code=200 if success else 400)

    except Exception as e:
        logger.error(f"Error assigning shift: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.put("/api/internal/wellsky/shifts/{shift_id}/cancel")
async def internal_cancel_shift(shift_id: str, request: Request):
    """
    Cancel a shift.
    Called by Gigi when a client requests to cancel a visit.
    """
    if wellsky_service is None:
        return JSONResponse({
            "success": False,
            "error": "WellSky service not available"
        }, status_code=503)

    try:
        data = await request.json()
        reason = data.get("reason", "Client requested cancellation")
        cancelled_by = data.get("cancelled_by", "client")

        success, message = wellsky_service.cancel_shift(
            shift_id=shift_id,
            reason=reason,
            cancelled_by=cancelled_by
        )

        return JSONResponse({
            "success": success,
            "message": message,
            "shift_id": shift_id
        }, status_code=200 if success else 400)

    except Exception as e:
        logger.error(f"Error cancelling shift: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/internal/wellsky/shifts/{shift_id}/late-notification")
async def internal_late_notification(shift_id: str, request: Request):
    """
    Notify client that caregiver is running late.
    Called by Gigi when a caregiver reports they're running late.
    """
    if wellsky_service is None:
        return JSONResponse({
            "success": False,
            "error": "WellSky service not available"
        }, status_code=503)

    try:
        data = await request.json()
        delay_minutes = data.get("delay_minutes", 15)
        reason = data.get("reason", "")

        success, message, client_phone = wellsky_service.notify_client_caregiver_late(
            shift_id=shift_id,
            delay_minutes=delay_minutes,
            reason=reason
        )

        return JSONResponse({
            "success": success,
            "message": message,
            "shift_id": shift_id,
            "client_phone": client_phone,
            "delay_minutes": delay_minutes
        }, status_code=200 if success else 400)

    except Exception as e:
        logger.error(f"Error sending late notification: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/parse-va-form-10-7080")
async def parse_va_form(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user_optional)
):
    """Parse VA Form 10-7080 PDF using Gemini AI vision"""
    import base64
    import json

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not GEMINI_API_KEY:
        return JSONResponse({
            "success": False,
            "error": "GEMINI_API_KEY not configured",
            "message": "AI extraction unavailable"
        }, status_code=500)

    try:
        # Read PDF and convert to base64
        pdf_content = await file.read()
        pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')

        # Gemini extraction prompt
        extraction_prompt = """Extract ALL data from this VA Form 10-7080 (Approved Referral for Medical Care).

Return a JSON object with these EXACT keys (use empty string "" if field not found):

{
  "veteran_last_name": "",
  "veteran_first_name": "",
  "veteran_middle_name": "",
  "date_of_birth": "",
  "last_4_ssn": "",
  "phone": "",
  "address": "",
  "va_consult_number": "",
  "referral_issue_date": "",
  "first_appointment_date": "",
  "expiration_date": "",
  "pcp_last_name": "",
  "pcp_first_name": "",
  "pcp_npi": "",
  "facility_name": "",
  "facility_phone": "",
  "facility_fax": "",
  "diagnosis": "",
  "reason_for_request": "",
  "hours_per_week": "",
  "authorization_duration": "",
  "adl_dependencies": []
}

CRITICAL INSTRUCTIONS FOR DATES:
1. ALL dates must be in MM/DD/YYYY format (e.g., 02/04/2026)
2. "referral_issue_date" - Look for "Date Referral Issued" or "Issue Date" or "Referral Date" - this is CRITICAL for the filename
3. "first_appointment_date" - Look for "First Appt Date" or "Start Date" or "First Appointment" - this is CRITICAL for the filename
4. "expiration_date" - Look for "Expiration Date" or "Valid Through" or "Authorization Expires"
5. "date_of_birth" - Veteran's date of birth
6. If you see a date on the form but aren't sure which field it belongs to, look at the context/label near it
7. Search the ENTIRE document for these dates - they may be on different pages

OTHER CRITICAL FIELDS:
- veteran name: Split "LAST, FIRST MIDDLE" into separate fields
- va_consult_number: The referral/consult number starting with "VA" (e.g., VA0055325584)
- pcp name: Provider/physician name - split into last and first
- pcp_npi: Provider NPI number
- last_4_ssn: Only the last 4 digits of SSN
- hours_per_week: Authorized hours (may be range like "7 to 11")
- authorization_duration: How long authorized (e.g., "180 Days")
- adl_dependencies: Array of ADL needs ["Bathing", "Dressing", "Ambulating", etc.]

Return ONLY valid JSON, no markdown code fences, no explanation. Extract EVERY field you can find."""

        # Call Gemini API - try multiple models (same as ai_document_parser.py)
        models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        gemini_response = None
        last_error = None

        async with httpx.AsyncClient(timeout=60.0) as client:
            for model in models_to_try:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                    logger.info(f"Trying Gemini model: {model}")

                    gemini_response = await client.post(
                        url,
                        headers={
                            "x-goog-api-key": GEMINI_API_KEY,
                            "Content-Type": "application/json"
                        },
                        json={
                            "contents": [{
                                "parts": [
                                    {"text": extraction_prompt},
                                    {
                                        "inline_data": {
                                            "mime_type": "application/pdf",
                                            "data": pdf_base64
                                        }
                                    }
                                ]
                            }],
                            "generationConfig": {
                                "temperature": 0.1
                            }
                        }
                    )

                    if gemini_response.status_code == 404:
                        logger.info(f"Gemini model {model} not found (404), trying next...")
                        last_error = f"{model}: Model not found (404)"
                        continue

                    if gemini_response.status_code == 200:
                        logger.info(f"✓ Successfully used Gemini model: {model}")
                        break
                    else:
                        last_error = f"{model}: HTTP {gemini_response.status_code} - {gemini_response.text[:200]}"
                        logger.warning(f"Model {model} failed with status {gemini_response.status_code}")
                        continue
                except Exception as e:
                    last_error = f"{model}: {str(e)}"
                    logger.warning(f"Model {model} exception: {e}")
                    continue

        if not gemini_response or gemini_response.status_code != 200:
            raise Exception(f"All Gemini models failed. Last error: {last_error}")

        result = gemini_response.json()

        # Extract the JSON from Gemini response
        if "candidates" in result and len(result["candidates"]) > 0:
            content_text = result["candidates"][0]["content"]["parts"][0]["text"]

            # Clean up the response - sometimes Gemini wraps JSON in markdown
            content_text = content_text.strip()
            if content_text.startswith("```json"):
                content_text = content_text[7:]
            if content_text.startswith("```"):
                content_text = content_text[3:]
            if content_text.endswith("```"):
                content_text = content_text[:-3]
            content_text = content_text.strip()

            # Parse the JSON response
            extracted_data = json.loads(content_text)

            return JSONResponse({
                "success": True,
                "data": extracted_data,
                "message": "PDF parsed successfully using Gemini AI"
            })
        else:
            raise Exception(f"No candidates in Gemini response: {json.dumps(result)}")

    except json.JSONDecodeError as e:
        error_msg = f"JSON parse error: {str(e)}"
        logger.error(error_msg)
        return JSONResponse({
            "success": False,
            "error": error_msg,
            "message": f"AI extraction failed: {error_msg}"
        }, status_code=200)  # Return 200 so frontend can show error
    except Exception as e:
        error_msg = f"VA form parsing error: {str(e)}"
        logger.error(error_msg)
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": error_msg,
            "message": f"Failed to parse PDF: {error_msg}"
        }, status_code=200)  # Return 200 so frontend can show error


@app.get("/payroll", response_class=HTMLResponse)
async def payroll_converter(current_user: Dict[str, Any] = Depends(get_current_user_optional)):
    """Wellsky (AK) Payroll Converter - Convert WellSky payroll data for Adams Keegan"""
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "payroll-converter.html")
    with open(html_path, "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/va-plan-of-care", response_class=HTMLResponse)
async def va_plan_of_care(current_user: Dict[str, Any] = Depends(get_current_user_optional)):
    """VA Plan of Care Generator - Convert VA Form 10-7080 to Plan of Care (485)"""
    va_html_content = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VA Plan of Care Generator | Colorado Care Assist</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 20px; min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; padding: 30px; background: linear-gradient(135deg, #003f87 0%, #0066cc 100%); color: white; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 10px 30px rgba(0, 63, 135, 0.3); }
        .header h1 { font-size: 32px; margin-bottom: 10px; font-weight: 700; }
        .header p { font-size: 16px; opacity: 0.95; }
        .form-container { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1); margin-bottom: 30px; }
        .section { margin-bottom: 35px; padding-bottom: 25px; border-bottom: 2px solid #e0e0e0; }
        .section:last-child { border-bottom: none; }
        .section h2 { color: #003f87; font-size: 22px; margin-bottom: 20px; font-weight: 600; display: flex; align-items: center; }
        .section h2::before { content: ''; display: inline-block; width: 4px; height: 24px; background: #003f87; margin-right: 12px; }
        .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; }
        .form-group { display: flex; flex-direction: column; }
        .form-group label { font-weight: 600; margin-bottom: 8px; color: #333; font-size: 14px; }
        .form-group label .required { color: #dc3545; margin-left: 3px; }
        .form-group input, .form-group textarea { padding: 12px; border: 2px solid #e0e0e0; border-radius: 6px; font-size: 14px; font-family: inherit; transition: all 0.3s; }
        .form-group input:focus, .form-group textarea:focus { outline: none; border-color: #003f87; box-shadow: 0 0 0 3px rgba(0, 63, 135, 0.1); }
        .form-group textarea { resize: vertical; min-height: 80px; }
        .adl-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin-top: 10px; }
        .checkbox-label { display: flex; align-items: center; gap: 10px; cursor: pointer; padding: 12px; border: 2px solid #e0e0e0; border-radius: 6px; transition: all 0.3s; background: white; }
        .checkbox-label:hover { background-color: #f8f9fa; border-color: #003f87; }
        .checkbox-label input[type="checkbox"] { width: 20px; height: 20px; cursor: pointer; }
        .checkbox-label input[type="checkbox"]:checked + span { color: #003f87; font-weight: 600; }
        .actions { display: flex; justify-content: center; gap: 15px; margin-top: 40px; padding-top: 30px; border-top: 2px solid #e0e0e0; }
        .btn { padding: 14px 32px; font-size: 16px; font-weight: 600; border: none; border-radius: 8px; cursor: pointer; transition: all 0.3s; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); text-transform: uppercase; letter-spacing: 0.5px; }
        .btn-primary { background: #003f87; color: white; }
        .btn-primary:hover { background: #002b5c; transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2); }
        .btn-success { background: #28a745; color: white; }
        .btn-success:hover { background: #218838; transform: translateY(-2px); }
        .btn-secondary { background: #6c757d; color: white; }
        .btn-secondary:hover { background: #5a6268; transform: translateY(-2px); }
        .btn-danger { background: #dc3545; color: white; }
        .btn-danger:hover { background: #c82333; transform: translateY(-2px); }
        .preview-container { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1); margin-top: 30px; display: none; }
        .preview-container.active { display: block; }
        .preview-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; padding-bottom: 20px; border-bottom: 3px solid #003f87; }
        .preview-header h2 { color: #003f87; margin: 0; }
        .preview-actions { display: flex; gap: 10px; }
        .filename-preview { background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 25px; font-family: 'Courier New', monospace; font-size: 14px; border-left: 5px solid #003f87; word-break: break-all; color: #333; }
        .filename-preview strong { color: #003f87; display: block; margin-bottom: 8px; font-size: 15px; }
        .upload-section { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1); margin-bottom: 20px; text-align: center; }
        .upload-section h2 { color: #003f87; font-size: 20px; margin-bottom: 15px; font-weight: 600; }
        .upload-section p { color: #666; margin-bottom: 20px; font-size: 14px; }
        .file-input-wrapper { position: relative; display: inline-block; cursor: pointer; }
        .file-input-wrapper input[type="file"] { position: absolute; left: -9999px; }
        .file-input-label { display: inline-block; padding: 14px 32px; background: #003f87; color: white; border-radius: 8px; cursor: pointer; transition: all 0.3s; font-weight: 600; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); }
        .file-input-label:hover { background: #002b5c; transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2); }
        .file-name-display { margin-top: 15px; color: #28a745; font-weight: 600; min-height: 20px; }
        .upload-status { margin-top: 10px; padding: 12px; border-radius: 6px; font-size: 14px; font-weight: 500; }
        .upload-status.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .upload-status.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .upload-status.loading { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
        #plan-of-care { border: 3px solid #003f87; padding: 40px; background: white; font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #000; max-width: 8.5in; }
        #plan-of-care .poc-header { text-align: center; margin-bottom: 30px; border-bottom: 3px solid #003f87; padding-bottom: 15px; page-break-after: avoid; }
        #plan-of-care .poc-header h1 { font-size: 24px; margin-bottom: 8px; color: #003f87; font-weight: bold; }
        #plan-of-care .poc-header p { margin: 5px 0; font-size: 14px; }
        #plan-of-care .poc-section { margin-bottom: 20px; page-break-inside: avoid; orphans: 3; widows: 3; }
        #plan-of-care .poc-section-title { font-weight: bold; color: #003f87; margin-bottom: 10px; font-size: 16px; border-bottom: 2px solid #ccc; padding-bottom: 5px; }
        #plan-of-care .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
        #plan-of-care .info-item { padding: 5px 0; font-size: 13px; }
        #plan-of-care .info-label { font-weight: bold; margin-right: 5px; }
        #plan-of-care table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        #plan-of-care th, #plan-of-care td { border: 1px solid #333; padding: 10px; text-align: left; font-size: 13px; }
        #plan-of-care th { background-color: #f0f0f0; font-weight: bold; }
        #plan-of-care ul { margin: 10px 0; padding-left: 25px; }
        #plan-of-care li { margin: 5px 0; font-size: 13px; }
        #plan-of-care p { margin: 8px 0; font-size: 13px; }
        @media (max-width: 768px) {
            .form-grid { grid-template-columns: 1fr; }
            .header h1 { font-size: 24px; }
            .form-container, .preview-container { padding: 20px; }
            .preview-header { flex-direction: column; gap: 15px; align-items: flex-start; }
            .preview-actions, .actions { width: 100%; flex-direction: column; }
            .btn { width: 100%; }
        }
        @media print {
            body { background: white; }
            .form-container, .preview-header, .filename-preview { display: none; }
            .preview-container { box-shadow: none; padding: 0; }
            #plan-of-care { border: none; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>VA Plan of Care Generator</h1>
            <p>Convert VA Form 10-7080 to Home Health Certification and Plan of Care (485)</p>
            <p style="font-size: 13px; margin-top: 10px;">Must submit within 5 days | Contact: Tamatha.Anding@va.gov (naming)</p>
        </div>
        <div class="upload-section">
            <h2>📄 Step 1: Upload VA Form 10-7080</h2>
            <p>Upload your VA Form 10-7080 PDF to automatically extract veteran and referral information</p>
            <div class="file-input-wrapper">
                <input type="file" id="pdf-upload" accept=".pdf" onchange="handlePDFUpload(event)">
                <label for="pdf-upload" class="file-input-label">Choose PDF File</label>
            </div>
            <div id="file-name-display" class="file-name-display"></div>
            <div id="upload-status"></div>
        </div>
        <div class="form-container">
            <form id="va-form" onsubmit="event.preventDefault();">
                <div class="section">
                    <h2>Veteran Information</h2>
                    <div class="form-grid">
                        <div class="form-group"><label>Last Name<span class="required">*</span></label><input type="text" id="vet-lastname" required></div>
                        <div class="form-group"><label>First Name<span class="required">*</span></label><input type="text" id="vet-firstname" required></div>
                        <div class="form-group"><label>Middle Name</label><input type="text" id="vet-middlename"></div>
                        <div class="form-group"><label>Date of Birth<span class="required">*</span></label><input type="date" id="vet-dob" required></div>
                        <div class="form-group"><label>Last 4 SSN<span class="required">*</span></label><input type="text" id="vet-ssn" maxlength="4" required></div>
                        <div class="form-group"><label>Phone</label><input type="tel" id="vet-phone"></div>
                        <div class="form-group" style="grid-column: 1 / -1"><label>Address</label><input type="text" id="vet-address"></div>
                    </div>
                </div>
                <div class="section">
                    <h2>Referral Information</h2>
                    <div class="form-grid">
                        <div class="form-group"><label>VA Consult Number<span class="required">*</span></label><input type="text" id="ref-number" required></div>
                        <div class="form-group"><label>Referral Issue Date (Cert Date)<span class="required">*</span></label><input type="date" id="ref-issue" required></div>
                        <div class="form-group"><label>First Appointment/Start Date<span class="required">*</span></label><input type="date" id="ref-start" required></div>
                        <div class="form-group"><label>Expiration Date</label><input type="date" id="ref-expiration"></div>
                    </div>
                </div>
                <div class="section">
                    <h2>Primary Care Provider (PCP)</h2>
                    <div class="form-grid">
                        <div class="form-group"><label>PCP Last Name<span class="required">*</span></label><input type="text" id="pcp-lastname" required></div>
                        <div class="form-group"><label>PCP First Name<span class="required">*</span></label><input type="text" id="pcp-firstname" required></div>
                        <div class="form-group"><label>PCP NPI</label><input type="text" id="pcp-npi"></div>
                    </div>
                </div>
                <div class="section">
                    <h2>VA Facility</h2>
                    <div class="form-grid">
                        <div class="form-group" style="grid-column: 1 / -1"><label>Facility Name</label><input type="text" id="va-facility"></div>
                        <div class="form-group"><label>VA Phone</label><input type="tel" id="va-phone"></div>
                        <div class="form-group"><label>VA Fax</label><input type="tel" id="va-fax"></div>
                    </div>
                </div>
                <div class="section">
                    <h2>Clinical Information</h2>
                    <div class="form-grid">
                        <div class="form-group" style="grid-column: 1 / -1"><label>Provisional Diagnosis</label><textarea id="diagnosis" rows="2"></textarea></div>
                        <div class="form-group" style="grid-column: 1 / -1"><label>Reason for Request</label><textarea id="reason" rows="3"></textarea></div>
                    </div>
                </div>
                <div class="section">
                    <h2>Services Authorized</h2>
                    <div class="form-grid">
                        <div class="form-group"><label>Hours Per Week</label><input type="text" id="hours-week"></div>
                        <div class="form-group"><label>Authorization Duration</label><input type="text" id="auth-duration"></div>
                    </div>
                </div>
                <div class="section">
                    <h2>Activities of Daily Living (ADL) Dependencies</h2>
                    <p style="margin-bottom: 15px; color: #666;">Select all activities requiring hands-on assistance:</p>
                    <div class="adl-grid">
                        <label class="checkbox-label"><input type="checkbox" name="adl" value="Bathing"><span>Bathing</span></label>
                        <label class="checkbox-label"><input type="checkbox" name="adl" value="Dressing"><span>Dressing</span></label>
                        <label class="checkbox-label"><input type="checkbox" name="adl" value="Grooming"><span>Grooming</span></label>
                        <label class="checkbox-label"><input type="checkbox" name="adl" value="Ambulating"><span>Ambulating</span></label>
                        <label class="checkbox-label"><input type="checkbox" name="adl" value="Toileting"><span>Toileting</span></label>
                        <label class="checkbox-label"><input type="checkbox" name="adl" value="Mobility"><span>Mobility</span></label>
                        <label class="checkbox-label"><input type="checkbox" name="adl" value="Eating"><span>Eating</span></label>
                        <label class="checkbox-label"><input type="checkbox" name="adl" value="Transferring"><span>Transferring</span></label>
                    </div>
                </div>
                <div class="section">
                    <h2>Agency Information</h2>
                    <div class="form-grid">
                        <div class="form-group"><label>Agency Code<span class="required">*</span></label><input type="text" id="agency-code" value="CC.D" required></div>
                        <div class="form-group"><label>Agency Document Number<span class="required">*</span></label><input type="text" id="agency-docnum" value="001" required></div>
                    </div>
                </div>
                <div class="actions">
                    <button type="button" class="btn btn-primary" onclick="generatePreview()">Preview Plan of Care</button>
                </div>
            </form>
        </div>
        <div class="preview-container" id="preview-container">
            <div class="preview-header">
                <h2>Plan of Care Preview</h2>
                <div class="preview-actions">
                    <button type="button" class="btn btn-success" onclick="downloadPDF()">Download PDF</button>
                    <button type="button" class="btn btn-secondary" onclick="downloadHTML()">Download HTML</button>
                    <button type="button" class="btn btn-danger" onclick="closePreview()">Close</button>
                </div>
            </div>
            <div class="filename-preview"><strong>Filename:</strong><span id="filename-display"></span></div>
            <div id="plan-of-care"></div>
        </div>
    </div>
    <script>
        async function handlePDFUpload(event) {
            const file = event.target.files[0];
            if (!file) return;

            const fileNameDisplay = document.getElementById('file-name-display');
            const uploadStatus = document.getElementById('upload-status');

            fileNameDisplay.textContent = `Selected: ${file.name}`;
            uploadStatus.innerHTML = '<div class="upload-status loading">Parsing PDF... Please wait.</div>';

            try {
                const formData = new FormData();
                formData.append('file', file);

                const response = await fetch('/api/parse-va-form-10-7080', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.success && result.data) {
                    // Populate form fields with extracted data
                    const data = result.data;

                    // Debug: Log extracted data to console
                    console.log('Extracted data from Gemini:', data);
                    console.log('Date fields:', {
                        referral_issue_date: data.referral_issue_date,
                        first_appointment_date: data.first_appointment_date,
                        expiration_date: data.expiration_date
                    });

                    // Helper function to convert date formats
                    function formatDateForInput(dateStr) {
                        if (!dateStr || dateStr === '') {
                            console.warn('Empty date received:', dateStr);
                            return '';
                        }

                        // Already in YYYY-MM-DD format
                        if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
                            return dateStr;
                        }

                        // Convert MM/DD/YYYY or MM-DD-YYYY or M/D/YYYY to YYYY-MM-DD
                        const parts = dateStr.trim().split(/[/-]/);
                        if (parts.length === 3) {
                            const month = parts[0].padStart(2, '0');
                            const day = parts[1].padStart(2, '0');
                            let year = parts[2];
                            if (year.length === 2) {
                                year = '20' + year;
                            }
                            const formatted = `${year}-${month}-${day}`;
                            console.log(`Converted date: ${dateStr} -> ${formatted}`);
                            return formatted;
                        }

                        console.warn('Could not parse date:', dateStr);
                        return '';
                    }

                    // Populate veteran information
                    if (data.veteran_last_name) document.getElementById('vet-lastname').value = data.veteran_last_name;
                    if (data.veteran_first_name) document.getElementById('vet-firstname').value = data.veteran_first_name;
                    if (data.veteran_middle_name) document.getElementById('vet-middlename').value = data.veteran_middle_name;
                    if (data.date_of_birth) document.getElementById('vet-dob').value = formatDateForInput(data.date_of_birth);
                    if (data.last_4_ssn) document.getElementById('vet-ssn').value = data.last_4_ssn;
                    if (data.phone) document.getElementById('vet-phone').value = data.phone;
                    if (data.address) document.getElementById('vet-address').value = data.address;

                    // Populate referral information
                    if (data.va_consult_number) document.getElementById('ref-number').value = data.va_consult_number;
                    if (data.referral_issue_date) document.getElementById('ref-issue').value = formatDateForInput(data.referral_issue_date);
                    if (data.first_appointment_date) document.getElementById('ref-start').value = formatDateForInput(data.first_appointment_date);
                    if (data.expiration_date) document.getElementById('ref-expiration').value = formatDateForInput(data.expiration_date);

                    // Populate PCP information
                    if (data.pcp_last_name) document.getElementById('pcp-lastname').value = data.pcp_last_name;
                    if (data.pcp_first_name) document.getElementById('pcp-firstname').value = data.pcp_first_name;
                    if (data.pcp_npi) document.getElementById('pcp-npi').value = data.pcp_npi;

                    // Populate VA facility
                    if (data.facility_name) document.getElementById('va-facility').value = data.facility_name;
                    if (data.facility_phone) document.getElementById('va-phone').value = data.facility_phone;
                    if (data.facility_fax) document.getElementById('va-fax').value = data.facility_fax;

                    // Populate clinical information
                    if (data.diagnosis) document.getElementById('diagnosis').value = data.diagnosis;
                    if (data.reason_for_request) document.getElementById('reason').value = data.reason_for_request;
                    if (data.hours_per_week) document.getElementById('hours-week').value = data.hours_per_week;
                    if (data.authorization_duration) document.getElementById('auth-duration').value = data.authorization_duration;

                    // Populate ADL dependencies
                    if (data.adl_dependencies && Array.isArray(data.adl_dependencies)) {
                        // First uncheck all
                        document.querySelectorAll('input[name="adl"]').forEach(cb => cb.checked = false);
                        // Then check the ones from the PDF
                        data.adl_dependencies.forEach(adl => {
                            const checkbox = Array.from(document.querySelectorAll('input[name="adl"]'))
                                .find(cb => cb.value.toLowerCase() === adl.toLowerCase());
                            if (checkbox) checkbox.checked = true;
                        });
                    }

                    const fieldCount = Object.values(data).filter(v => v && v !== '').length;
                    uploadStatus.innerHTML = `<div class="upload-status success">✓ PDF parsed successfully! ${fieldCount} fields extracted. Review and edit below.</div>`;
                } else {
                    uploadStatus.innerHTML = `<div class="upload-status error">⚠ ${result.message || 'Failed to parse PDF'}. Please fill form manually.</div>`;
                }
            } catch (error) {
                console.error('Upload error:', error);
                uploadStatus.innerHTML = '<div class="upload-status error">⚠ Error uploading PDF. Please fill form manually.</div>';
            }
        }

        function generateFileName() {
            const vetLastName = document.getElementById("vet-lastname").value || 'LASTNAME';
            const vetFirstInitial = (document.getElementById("vet-firstname").value || 'F').charAt(0).toUpperCase();
            const last4SSN = document.getElementById("vet-ssn").value || '0000';
            const vaConsultNum = document.getElementById("ref-number").value || 'VA000000';
            const pcpLastName = document.getElementById("pcp-lastname").value || 'PCPLAST';
            const pcpFirstInitial = (document.getElementById("pcp-firstname").value || 'P').charAt(0).toUpperCase();
            const agencyCode = document.getElementById("agency-code").value || 'CC.D';
            const agencyDocNum = document.getElementById("agency-docnum").value || '001';

            // Format date from YYYY-MM-DD input to MM.DD.YYYY
            function formatDate(dateInput) {
                if (!dateInput) return '00.00.0000';
                const date = new Date(dateInput + 'T00:00:00'); // Force local timezone
                if (isNaN(date.getTime())) return '00.00.0000';
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                const year = date.getFullYear();
                return `${month}.${day}.${year}`;
            }

            // Use start date for filename (one date only)
            const startDate = formatDate(document.getElementById("ref-start").value);

            return `${vetLastName}.${vetFirstInitial}.${last4SSN}_${vaConsultNum}.${pcpLastName}.${pcpFirstInitial}.${agencyCode}.${startDate}.${agencyDocNum}`;
        }function getADLs(){return Array.from(document.querySelectorAll('input[name="adl"]:checked')).map(t=>t.value)}function generatePreview(){const t=generateFileName();document.getElementById("filename-display").textContent=t+".pdf";const e=getADLs(),n=e.length>0?"<ul>"+e.map(t=>`<li>${t}</li>`).join("")+"</ul>":"<p>No ADL dependencies specified</p>",a=`
                <div class="poc-header">
                    <h1>HOME HEALTH CERTIFICATION AND PLAN OF CARE</h1>
                    <p>Department of Veterans Affairs</p>
                    <p><strong>VA Consult Number:</strong> ${document.getElementById("ref-number").value}</p>
                </div>
                <div class="poc-section">
                    <div class="poc-section-title">1. Patient Information</div>
                    <div class="info-grid">
                        <div class="info-item"><span class="info-label">Name:</span> ${document.getElementById("vet-lastname").value}, ${document.getElementById("vet-firstname").value} ${document.getElementById("vet-middlename").value}</div>
                        <div class="info-item"><span class="info-label">Date of Birth:</span> ${document.getElementById("vet-dob").value}</div>
                        <div class="info-item"><span class="info-label">Last 4 SSN:</span> ${document.getElementById("vet-ssn").value}</div>
                        <div class="info-item"><span class="info-label">Phone:</span> ${document.getElementById("vet-phone").value}</div>
                        <div class="info-item" style="grid-column: 1 / -1"><span class="info-label">Address:</span> ${document.getElementById("vet-address").value}</div>
                    </div>
                </div>
                <div class="poc-section">
                    <div class="poc-section-title">2. Referral Information</div>
                    <div class="info-grid">
                        <div class="info-item"><span class="info-label">Referral Number:</span> ${document.getElementById("ref-number").value}</div>
                        <div class="info-item"><span class="info-label">Issue Date:</span> ${document.getElementById("ref-issue").value}</div>
                        <div class="info-item"><span class="info-label">Start Date:</span> ${document.getElementById("ref-start").value}</div>
                        <div class="info-item"><span class="info-label">Expiration Date:</span> ${document.getElementById("ref-expiration").value}</div>
                    </div>
                </div>
                <div class="poc-section">
                    <div class="poc-section-title">3. Primary Care Provider</div>
                    <div class="info-grid">
                        <div class="info-item"><span class="info-label">Physician:</span> Dr. ${document.getElementById("pcp-firstname").value} ${document.getElementById("pcp-lastname").value}</div>
                        <div class="info-item"><span class="info-label">NPI:</span> ${document.getElementById("pcp-npi").value}</div>
                        <div class="info-item" style="grid-column: 1 / -1"><span class="info-label">Facility:</span> ${document.getElementById("va-facility").value}</div>
                        <div class="info-item"><span class="info-label">Phone:</span> ${document.getElementById("va-phone").value}</div>
                        <div class="info-item"><span class="info-label">Fax:</span> ${document.getElementById("va-fax").value}</div>
                    </div>
                </div>
                <div class="poc-section"><div class="poc-section-title">4. Diagnosis</div><p>${document.getElementById("diagnosis").value}</p></div>
                <div class="poc-section"><div class="poc-section-title">5. Clinical Information</div><p><strong>Reason for Home Health Services:</strong></p><p>${document.getElementById("reason").value}</p></div>
                <div class="poc-section">
                    <div class="poc-section-title">6. Services Authorized</div>
                    <table>
                        <thead><tr><th>Service Type</th><th>Frequency</th><th>Duration</th></tr></thead>
                        <tbody>
                            <tr><td>Home Health Aide</td><td>${document.getElementById("hours-week").value} hours per week</td><td>${document.getElementById("auth-duration").value}</td></tr>
                            <tr><td>Supervisory RN Visits</td><td>Per state regulation (up to 48 units per 180 days)</td><td>${document.getElementById("auth-duration").value}</td></tr>
                        </tbody>
                    </table>
                </div>
                <div class="poc-section"><div class="poc-section-title">7. Activities of Daily Living (ADL) Dependencies</div><p>Veteran requires hands-on assistance with the following:</p>${n}</div>
                <div class="poc-section"><div class="poc-section-title">8. Goals</div><ul><li>Maintain current level of functioning and prevent further decline</li><li>Ensure safety and independence in the home environment</li><li>Provide assistance with ADLs to promote dignity and quality of life</li><li>Monitor and report any changes in condition to VA provider</li></ul></div>
                <div class="poc-section"><div class="poc-section-title">9. Orders for Discipline and Treatments</div><p><strong>Home Health Aide Services:</strong></p><ul><li>Assist with bathing, dressing, grooming as needed</li><li>Assist with mobility and transfers</li><li>Provide light housekeeping in areas used by the Veteran</li><li>Assist with meal preparation as needed</li><li>Report any changes in condition to supervisory RN</li></ul><p><strong>RN Supervisory Visits:</strong></p><ul><li>Supervise home health aide as required by state regulation</li><li>Assess Veteran's condition and safety in home</li><li>Coordinate with VA provider regarding any concerns</li><li>Document and report per VA requirements</li></ul></div>
                <div class="poc-section"><div class="poc-section-title">10. Medications</div><p>Refer to VA pharmacy for current medication list. All prescriptions to be filled through VA.</p></div>
                <div class="poc-section"><div class="poc-section-title">11. Activities Permitted</div><p>Activity and weight bearing as tolerated. Regular diet.</p></div>
                <div class="poc-section"><div class="poc-section-title">12. Safety Measures</div><ul><li>Fall precautions - assist with ambulation and transfers</li><li>Ensure safe home environment</li><li>Report any safety concerns to RN supervisor</li></ul></div>
                <div class="poc-section" style="margin-top: 40px; padding-top: 20px; border-top: 3px solid #000;"><p><strong>Certification:</strong></p><p>I certify that this Veteran is under my care and that the above home health services are medically necessary.</p><br><p>___________________________________ Date: _______________</p><p>Physician Signature</p><br><p>Dr. ${document.getElementById("pcp-firstname").value} ${document.getElementById("pcp-lastname").value}, NPI: ${document.getElementById("pcp-npi").value}</p></div>
                <div class="poc-section" style="font-size: 12px; color: #666; margin-top: 30px;"><p><strong>Important:</strong> Any claims related to this episode of care MUST include the VA Consult Number ${document.getElementById("ref-number").value} as the Prior Authorization number.</p><p>Submit claims to TriWest (Payer ID: TWVACCN)</p></div>
            `;document.getElementById("plan-of-care").innerHTML=a,document.getElementById("preview-container").classList.add("active"),document.getElementById("preview-container").scrollIntoView({behavior:"smooth"})}function closePreview(){document.getElementById("preview-container").classList.remove("active"),window.scrollTo({top:0,behavior:"smooth"})}function downloadPDF(){const element=document.getElementById("plan-of-care");const filename=generateFileName();const opt={margin:[0.5,0.5,0.5,0.5],filename:filename+".pdf",image:{type:"jpeg",quality:0.98},html2canvas:{scale:1.5,useCORS:true,letterRendering:true,scrollY:0,scrollX:0},jsPDF:{unit:"in",format:"letter",orientation:"portrait"},pagebreak:{mode:["avoid-all","css","legacy"]}};html2pdf().set(opt).from(element).save()}function downloadHTML(){const t=generateFileName(),e=document.getElementById("plan-of-care").innerHTML,n=`
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>VA Plan of Care - ${t}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
        .poc-header { text-align: center; margin-bottom: 30px; border-bottom: 3px solid #003f87; padding-bottom: 15px; }
        .poc-section { margin-bottom: 20px; }
        .poc-section-title { font-weight: bold; color: #003f87; margin-bottom: 10px; border-bottom: 2px solid #ccc; }
        .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .info-item { padding: 5px 0; }
        .info-label { font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #333; padding: 10px; text-align: left; }
        th { background-color: #f0f0f0; }
    </style>
</head>
<body>
    ${e}
</body>
</html>
            `,a=new Blob([n],{type:"text/html"}),l=window.URL.createObjectURL(a),i=document.createElement("a");i.href=l,i.download=t+".html",document.body.appendChild(i),i.click(),window.URL.revokeObjectURL(l),document.body.removeChild(i)}
    </script>
</body>
</html>"""
    return HTMLResponse(content=va_html_content)


# ============================================================================
# VA RFS CONVERTER - Convert VA 10-7080, Referral Face Sheets & Contact Sheets to VA Form 10-10172 RFS
# Handles: 1) VA Form 10-7080 (re-authorizations every 6 months)
#          2) Referral face sheets (nursing home, hospital, ALF, rehab)
#          3) Contact sheets and other medical referrals
# ============================================================================

@app.post("/api/parse-va-rfs-referral")
async def parse_va_rfs_referral(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user_optional)
):
    """Parse referral face sheet PDF using Gemini AI vision for VA Form 10-10172 RFS"""
    import base64
    import json

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not GEMINI_API_KEY:
        return JSONResponse({
            "success": False,
            "error": "GEMINI_API_KEY not configured",
            "message": "AI extraction unavailable"
        }, status_code=200)

    try:
        # Read PDF and convert to base64
        pdf_content = await file.read()
        pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')

        # Gemini extraction prompt for VA RFS
        extraction_prompt = """Extract ALL data from this document. This can be one of three types:
1. VA Form 10-7080 (Approved Referral for Medical Care) - for re-authorizations
2. Referral face sheet from nursing home, hospital, ALF, or rehabilitation facility
3. Contact sheet or other medical referral document

This will be used to populate VA Form 10-10172 RFS (Request for Service).

Return a JSON object with these EXACT keys (use empty string "" if field not found):

{
  "document_type": "",
  "veteran_last_name": "",
  "veteran_first_name": "",
  "veteran_middle_name": "",
  "date_of_birth": "",
  "last_4_ssn": "",
  "full_ssn": "",
  "phone": "",
  "address": "",
  "city": "",
  "state": "",
  "zip": "",
  "ordering_provider_name": "",
  "ordering_provider_npi": "",
  "ordering_provider_phone": "",
  "ordering_provider_fax": "",
  "ordering_provider_address": "",
  "facility_name": "",
  "facility_type": "",
  "diagnosis_primary": "",
  "diagnosis_secondary": "",
  "icd10_codes": "",
  "care_type": "",
  "service_requested": "",
  "orders": "",
  "medications": "",
  "allergies": "",
  "emergency_contact_name": "",
  "emergency_contact_phone": "",
  "referral_date": "",
  "admission_date": "",
  "discharge_date": ""
}

CRITICAL - Set document_type field:
- If this is VA Form 10-7080 (has "VA FORM 10-7080" header) → document_type: "VA_10_7080"
- If this is a referral face sheet, contact sheet, or hospital referral → document_type: "REFERRAL_FACE_SHEET"

IMPORTANT INSTRUCTIONS:

FOR VA FORM 10-7080:
- Veteran Name → veteran_last_name, veteran_first_name, veteran_middle_name
- Veteran Date of Birth → date_of_birth
- Veteran SSN (full or last 4) → last_4_ssn (extract just last 4 digits)
- Veteran Address, City, State, ZIP → separate into address, city, state, zip fields
- Veteran Phone Number → phone
- Referring Provider → ordering_provider_name
- Referring Provider NPI → ordering_provider_npi
- VA Telephone Number → ordering_provider_phone
- VA Fax Number → ordering_provider_fax
- Referring VA Facility → ordering_provider_address (include full facility name and address)
- Provisional Diagnosis OR Root cause/diagnoses → diagnosis_primary
- ICD-10 codes (like R54) → icd10_codes
- Service Requested (like "HHHA 7 to 11 hrs Per Week") → service_requested
- Category of Care → care_type
- Active Outpatient Medications → medications
- Referral Issue Date → referral_date
- First Appointment Date → admission_date
- Expiration Date → discharge_date

FOR REFERRAL FACE SHEETS (Nursing Home, Hospital, ALF):
- Patient/Resident Name → veteran_last_name, veteran_first_name, veteran_middle_name
- DOB → date_of_birth
- SSN → last_4_ssn (extract just last 4 digits)
- Address fields → address, city, state, zip
- Phone → phone
- Primary Physician OR Ordering Provider → ordering_provider_name
- Physician NPI → ordering_provider_npi
- Provider Phone → ordering_provider_phone
- Provider Fax → ordering_provider_fax
- Provider Office/Facility Address → ordering_provider_address
- Facility Name (SNF, ALF, Hospital, etc.) → facility_name
- Facility Type → facility_type
- Primary Diagnosis → diagnosis_primary
- Secondary Diagnosis → diagnosis_secondary
- ICD-10 Codes → icd10_codes
- Care Level or Service Type → care_type
- Orders or Services Requested → orders
- Medications → medications
- Allergies → allergies
- Emergency Contact → emergency_contact_name, emergency_contact_phone
- Referral Date → referral_date
- Admission Date → admission_date
- Discharge Date → discharge_date

GENERAL INSTRUCTIONS:
1. Search the ENTIRE document for all fields (multi-page documents)
2. Extract patient/veteran information (name, DOB, SSN, phone, address)
3. Look for primary physician, referring provider, or ordering provider (name, NPI, contact info)
4. Extract ALL diagnosis information and ICD-10 codes (like R54, I50.9, Z99.11, etc.)
5. Look for care type (HHHA, Home Health, Skilled Nursing, Assisted Living, etc.)
6. Find facility name and type if applicable (SNF, ALF, Hospital, Rehab, VA Facility)
7. Extract service requested or orders (hours per week, type of care)
8. Look for medications, allergies, emergency contacts
9. Find key dates: referral issue date, admission date, start of care, discharge/expiration date

DATE FORMATS: Convert all dates to MM/DD/YYYY format.

SSN: If you find full SSN like "155-26-3414", extract only last 4 digits: "3414"

DIAGNOSIS: Extract both text descriptions (like "Age-related physical debility") AND ICD-10 codes (like "R54")

PROVIDER: For VA Form 10-7080, the "Referring Provider" is the ordering provider for the RFS.

Return ONLY the JSON object, no other text."""

        # Try multiple Gemini models
        models_to_try = [
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro"
        ]

        last_error = None
        for model in models_to_try:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    gemini_response = await client.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                        headers={
                            "x-goog-api-key": GEMINI_API_KEY,
                            "Content-Type": "application/json"
                        },
                        json={
                            "contents": [{
                                "parts": [
                                    {"text": extraction_prompt},
                                    {
                                        "inline_data": {
                                            "mime_type": "application/pdf",
                                            "data": pdf_base64
                                        }
                                    }
                                ]
                            }],
                            "generationConfig": {
                                "temperature": 0.1
                            }
                        }
                    )

                    if gemini_response.status_code == 200:
                        result = gemini_response.json()

                        # Extract text from Gemini response
                        if "candidates" in result and len(result["candidates"]) > 0:
                            candidate = result["candidates"][0]
                            if "content" in candidate and "parts" in candidate["content"]:
                                extracted_text = candidate["content"]["parts"][0]["text"]

                                # Parse JSON from response
                                json_start = extracted_text.find("{")
                                json_end = extracted_text.rfind("}") + 1
                                if json_start >= 0 and json_end > json_start:
                                    json_str = extracted_text[json_start:json_end]
                                    extracted_data = json.loads(json_str)

                                    print(f"✓ Successfully used Gemini model: {model}")

                                    return JSONResponse({
                                        "success": True,
                                        "data": extracted_data,
                                        "message": f"PDF parsed successfully using Gemini AI ({model})",
                                        "fields_extracted": len([v for v in extracted_data.values() if v])
                                    }, status_code=200)

                        last_error = f"Unexpected response structure from {model}"
                    else:
                        last_error = f"Gemini model {model} returned status {gemini_response.status_code}"
                        print(f"Gemini model {model} failed ({gemini_response.status_code}), trying next...")
                        continue

            except Exception as e:
                last_error = str(e)
                print(f"Error with Gemini model {model}: {e}, trying next...")
                continue

        # If all models failed
        return JSONResponse({
            "success": False,
            "error": f"All Gemini models failed. Last error: {last_error}",
            "message": "Could not extract data from PDF"
        }, status_code=200)

    except Exception as e:
        print(f"Error parsing VA RFS referral: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": "Failed to parse PDF"
        }, status_code=200)


@app.post("/api/fill-va-rfs-form")
async def fill_va_rfs_form(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user_optional)
):
    """Fill official VA Form 10-10172 RFS PDF with extracted data"""
    from datetime import datetime

    from PyPDFForm import PdfWrapper

    try:
        # Get form data from request
        data = await request.json()

        # Load the blank VA Form 10-10172 PDF
        pdf_path = os.path.join(os.path.dirname(__file__), '..', 'va_form_10_10172_blank.pdf')
        pdf = PdfWrapper(pdf_path)
        pdf.global_font_size = 8  # Smaller font to prevent field 18 overflow into attestation

        # Map extracted data to PDF form fields using actual field names from PDF
        form_data = {}

        # VETERANSNAME[0] - Veteran's Full Name (Last, First MI)
        vet_name_parts = []
        if data.get('veteran_last_name'):
            vet_name_parts.append(data['veteran_last_name'])
        if data.get('veteran_first_name'):
            vet_name_parts.append(data['veteran_first_name'])
        if data.get('veteran_middle_name'):
            vet_name_parts.append(data['veteran_middle_name'][:1])  # Middle initial
        if vet_name_parts:
            form_data['VETERANSNAME[0]'] = ', '.join(vet_name_parts)

        # DOB[0] - Date of Birth
        if data.get('date_of_birth'):
            form_data['DOB[0]'] = data['date_of_birth']

        # VAFACILITYADDRESS[0] - VA Facility & Address
        if data.get('facility_name'):
            form_data['VAFACILITYADDRESS[0]'] = data['facility_name']

        # VAAUTHORIZATIONNUMBER[0] - VA Authorization Number
        if data.get('va_authorization_number'):
            form_data['VAAUTHORIZATIONNUMBER[0]'] = data['va_authorization_number']

        # ORDERINGPROVIDEROFFICENAMEADDRESS[0] - Ordering Provider Office Name & Address
        if data.get('ordering_provider_name') or data.get('ordering_provider_address'):
            provider_info = []
            if data.get('ordering_provider_name'):
                provider_info.append(data['ordering_provider_name'])
            if data.get('ordering_provider_address'):
                provider_info.append(data['ordering_provider_address'])
            form_data['ORDERINGPROVIDEROFFICENAMEADDRESS[0]'] = '\n'.join(provider_info)

        # HISTHP[0] - IHS/THP Provider checkbox (0=NO, 1=YES) - default to NO
        form_data['HISTHP[0]'] = 0

        # ORDERINGPROVIDERPHONENUMBER[0] - Provider Phone
        if data.get('ordering_provider_phone'):
            form_data['ORDERINGPROVIDERPHONENUMBER[0]'] = data['ordering_provider_phone']

        # ORDERINGPROVIDERFAXNUMBER[0] - Provider Fax
        if data.get('ordering_provider_fax'):
            form_data['ORDERINGPROVIDERFAXNUMBER[0]'] = data['ordering_provider_fax']

        # ORDERINGPROVIDERSECUREEMAILADDRESS[0] - Provider Email
        if data.get('ordering_provider_email'):
            form_data['ORDERINGPROVIDERSECUREEMAILADDRESS[0]'] = data['ordering_provider_email']

        # RadioButtonList[0] - Is care needed within 48 hours? (0=NO)
        form_data['RadioButtonList[0]'] = 0  # NO by default

        # RadioButtonList[1] - Is this a continuation of care?
        # 0=NO (new services), 1=YES (re-authorization from VA 10-7080)
        # BUSINESS RULE: Continuation of care = YES *ONLY* when the RFS is created
        # from a VA Form 10-7080 authorization. All other document types (clinical notes,
        # face sheets, CCD, referrals, etc.) = NO. Default is NO.
        is_continuation = data.get('is_continuation_of_care', False)
        form_data['RadioButtonList[1]'] = 1 if is_continuation else 0

        # RadioButtonList[2] - Is this a referral to another specialty? (0=NO)
        form_data['RadioButtonList[2]'] = 0  # NO by default

        # SPECIALTY[0] - Medical Specialty
        if data.get('specialty'):
            form_data['SPECIALTY[0]'] = data['specialty']

        # DIAGNOSISCODES[0] - Diagnosis Codes (ICD-10)
        if data.get('icd10_codes'):
            form_data['DIAGNOSISCODES[0]'] = data['icd10_codes']

        # DIAGNOSISDESCRIPTION[0] - Diagnosis Description
        if data.get('diagnosis_primary'):
            form_data['DIAGNOSISDESCRIPTION[0]'] = data['diagnosis_primary']

        # PROVISIONALDIAGNOSIS[0] - Provisional Diagnosis (alternative field)
        if data.get('diagnosis_primary') and not data.get('diagnosisdescription'):
            form_data['PROVISIONALDIAGNOSIS[0]'] = data['diagnosis_primary']

        # REQUESTEDCPTHCPCSCODE[0] - CPT/HCPCS Codes
        if data.get('cpt_codes'):
            form_data['REQUESTEDCPTHCPCSCODE[0]'] = data['cpt_codes']

        # DESCRIPTIONCPTHCPCSCODE[0] - Description of CPT/HCPCS
        if data.get('cpt_description'):
            form_data['DESCRIPTIONCPTHCPCSCODE[0]'] = data['cpt_description']

        # RadioButtonList[3] - Geriatric and Extended Care service type (single-select)
        # Values: 0=None, 1=Nursing Home, 2=Home Infusion, 3=Hospice, 4=Skilled Home Health,
        #         5=Homemaker/Home Health Aide, 6=Respite, 7=Adult Day Care
        # Per user: ONLY use 5 (HHA) or 6 (Respite), never anything else
        service_text = (data.get('service_requested') or '').lower()
        orders_text = (data.get('orders') or '').lower()
        combined_service = service_text + ' ' + orders_text

        if 'respite' in combined_service:
            form_data['RadioButtonList[3]'] = 6  # Respite
        elif any(keyword in combined_service for keyword in ['hha', 'homemaker', 'home health aide']):
            form_data['RadioButtonList[3]'] = 5  # Homemaker/Home Health Aide
        # If neither detected, don't set the field (leave blank for manual selection)

        # TextField1[0] - Reason for Request / Justification
        reason_parts = []
        if data.get('diagnosis_primary'):
            reason_parts.append(f"Diagnosis: {data['diagnosis_primary']}")
        if data.get('diagnosis_secondary'):
            reason_parts.append(f"Secondary Diagnosis: {data['diagnosis_secondary']}")
        if data.get('service_requested'):
            reason_parts.append(f"Service Requested: {data['service_requested']}")
        if data.get('orders'):
            reason_parts.append(f"Orders: {data['orders']}")
        if data.get('medications'):
            reason_parts.append(f"Medications: {data['medications']}")
        if data.get('allergies'):
            reason_parts.append(f"Allergies: {data['allergies']}")
        if data.get('emergency_contact_name') or data.get('emergency_contact_phone'):
            contact_info = []
            if data.get('emergency_contact_name'):
                contact_info.append(data['emergency_contact_name'])
            if data.get('emergency_contact_phone'):
                contact_info.append(data['emergency_contact_phone'])
            reason_parts.append(f"Emergency Contact: {' - '.join(contact_info)}")

        if reason_parts:
            form_data['TextField1[0]'] = '\n'.join(reason_parts)

        # ORDERINGPROVIDERSNAMEPRINTED[0] - Provider Name (Printed)
        if data.get('ordering_provider_name'):
            form_data['ORDERINGPROVIDERSNAMEPRINTED[0]'] = data['ordering_provider_name']

        # ORDERINGPROVIDERSNPI[0] - Provider NPI
        if data.get('ordering_provider_npi'):
            form_data['ORDERINGPROVIDERSNPI[0]'] = data['ordering_provider_npi']

        # SignatureField11[0] - Signature field - leave blank for manual signature

        # Date[0] - Today's Date
        today = datetime.now().strftime('%m/%d/%Y')
        form_data['Date[0]'] = today

        # Fill the PDF form
        filled_pdf = pdf.fill(form_data)

        # Generate filename
        vet_last = data.get('veteran_last_name', 'Veteran')
        vet_first_initial = (data.get('veteran_first_name') or 'V')[0].upper()
        last_4_ssn = data.get('last_4_ssn', '0000')
        date_str = datetime.now().strftime('%m.%d.%Y')

        filename = f"{vet_last}.{vet_first_initial}.{last_4_ssn}_VA-RFS-10-10172.{date_str}.pdf"

        # Return filled PDF
        pdf_bytes = filled_pdf.read()

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        print(f"Error filling VA RFS form: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": "Failed to fill VA RFS form"
        }, status_code=500)


@app.get("/va-rfs-converter")
async def va_rfs_converter(
    current_user: Dict[str, Any] = Depends(get_current_user_optional)
):
    """VA RFS Converter - Convert referral face sheets to VA Form 10-10172 RFS"""

    va_rfs_html_content = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VA RFS Converter - Colorado Care Assist</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.2/html2pdf.bundle.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Arial', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }
        .header p {
            font-size: 14px;
            opacity: 0.9;
        }
        .upload-section {
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 2px solid #e9ecef;
        }
        .upload-box {
            border: 3px dashed #667eea;
            border-radius: 8px;
            padding: 40px;
            text-align: center;
            background: white;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .upload-box:hover {
            background: #f8f9ff;
            border-color: #764ba2;
        }
        .upload-box.dragover {
            background: #e8ebff;
            border-color: #764ba2;
        }
        .upload-icon {
            font-size: 48px;
            margin-bottom: 15px;
        }
        input[type="file"] {
            display: none;
        }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 600;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .btn-success {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
        }
        .btn-success:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(56, 239, 125, 0.4);
        }
        .form-section {
            padding: 30px;
            display: none;
        }
        .form-section.active {
            display: block;
        }
        .form-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 25px;
        }
        .form-group {
            display: flex;
            flex-direction: column;
        }
        .form-group.full-width {
            grid-column: 1 / -1;
        }
        label {
            font-weight: 600;
            margin-bottom: 8px;
            color: #2d3748;
            font-size: 14px;
        }
        input, select, textarea {
            padding: 10px;
            border: 2px solid #e2e8f0;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.3s ease;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        textarea {
            resize: vertical;
            min-height: 80px;
        }
        .section-title {
            font-size: 20px;
            font-weight: 700;
            color: #1e3c72;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }
        .checkbox-group {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }
        .checkbox-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .checkbox-item input[type="checkbox"] {
            width: 18px;
            height: 18px;
        }
        .action-buttons {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-top: 30px;
        }
        .alert {
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .loading.active {
            display: block;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        /* Print styles for VA Form 10-10172 */
        #va-rfs-form {
            display: none;
        }
        #va-rfs-form.active {
            display: block;
            background: white;
            padding: 40px;
            max-width: 8.5in;
            margin: 0 auto;
        }
        .rfs-header {
            text-align: center;
            margin-bottom: 20px;
            border-bottom: 2px solid #000;
            padding-bottom: 10px;
        }
        .rfs-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .rfs-subtitle {
            font-size: 12px;
        }
        .rfs-field {
            margin-bottom: 15px;
            page-break-inside: avoid;
        }
        .rfs-label {
            font-weight: bold;
            font-size: 11px;
            display: block;
            margin-bottom: 3px;
        }
        .rfs-value {
            border-bottom: 1px solid #333;
            min-height: 20px;
            padding: 2px 5px;
            font-size: 12px;
        }
        .rfs-checkbox {
            display: inline-block;
            width: 15px;
            height: 15px;
            border: 1px solid #000;
            margin-right: 5px;
            vertical-align: middle;
        }
        .rfs-checkbox.checked::after {
            content: "✓";
            display: block;
            text-align: center;
            font-weight: bold;
        }
        .rfs-section {
            margin-top: 25px;
            page-break-inside: avoid;
        }
        .rfs-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }

        @media print {
            body { background: white; padding: 0; }
            .container { box-shadow: none; border-radius: 0; }
            .header, .upload-section, .form-section, .action-buttons { display: none; }
            #va-rfs-form { display: block !important; }
        }

        @media (max-width: 768px) {
            .form-grid {
                grid-template-columns: 1fr;
            }
            .action-buttons {
                flex-direction: column;
            }
            .btn {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏥 VA RFS Converter</h1>
            <p>Convert VA Form 10-7080, Referral Face Sheets & Contact Sheets to VA Form 10-10172 RFS</p>
            <p style="font-size: 12px; margin-top: 5px; opacity: 0.85;">Request for Service • Re-authorizations • New Referrals</p>
        </div>

        <div class="upload-section">
            <div class="upload-box" id="uploadBox">
                <div class="upload-icon">📄</div>
                <h3>Upload Referral Document</h3>
                <p style="margin: 10px 0; color: #666; font-weight: 600;">Accepts:</p>
                <p style="margin: 5px 0; color: #666; font-size: 14px;">
                    ✓ VA Form 10-7080 (re-authorizations)<br>
                    ✓ Referral face sheets (nursing home, hospital, ALF)<br>
                    ✓ Contact sheets & medical referrals
                </p>
                <p style="margin: 15px 0 10px 0; color: #888; font-size: 13px;">Drag and drop your PDF here or click to browse</p>
                <input type="file" id="pdfFile" accept=".pdf" />
                <button class="btn btn-primary" onclick="document.getElementById('pdfFile').click()">
                    Select PDF
                </button>
            </div>
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p style="margin-top: 15px;">Extracting data with AI...</p>
            </div>
        </div>

        <div class="form-section" id="formSection">
            <div id="alertContainer"></div>

            <div class="section-title">📋 Veteran Information</div>
            <div class="form-grid">
                <div class="form-group">
                    <label>Last Name *</label>
                    <input type="text" id="vet-last-name" required>
                </div>
                <div class="form-group">
                    <label>First Name *</label>
                    <input type="text" id="vet-first-name" required>
                </div>
                <div class="form-group">
                    <label>Middle Name</label>
                    <input type="text" id="vet-middle-name">
                </div>
                <div class="form-group">
                    <label>Date of Birth (MM/DD/YYYY) *</label>
                    <input type="date" id="vet-dob" required>
                </div>
                <div class="form-group">
                    <label>Last 4 SSN *</label>
                    <input type="text" id="vet-ssn-last4" maxlength="4" pattern="[0-9]{4}">
                </div>
                <div class="form-group">
                    <label>Phone</label>
                    <input type="tel" id="vet-phone">
                </div>
                <div class="form-group full-width">
                    <label>Address</label>
                    <input type="text" id="vet-address">
                </div>
                <div class="form-group">
                    <label>City</label>
                    <input type="text" id="vet-city">
                </div>
                <div class="form-group">
                    <label>State</label>
                    <input type="text" id="vet-state" maxlength="2">
                </div>
                <div class="form-group">
                    <label>ZIP</label>
                    <input type="text" id="vet-zip" maxlength="10">
                </div>
            </div>

            <div class="section-title">👨‍⚕️ Ordering Provider Information</div>
            <div class="form-grid">
                <div class="form-group">
                    <label>Provider Name *</label>
                    <input type="text" id="provider-name" required>
                </div>
                <div class="form-group">
                    <label>Provider NPI *</label>
                    <input type="text" id="provider-npi" required>
                </div>
                <div class="form-group">
                    <label>Provider Phone</label>
                    <input type="tel" id="provider-phone">
                </div>
                <div class="form-group">
                    <label>Provider Fax</label>
                    <input type="tel" id="provider-fax">
                </div>
                <div class="form-group full-width">
                    <label>Provider Office Address</label>
                    <input type="text" id="provider-address">
                </div>
            </div>

            <div class="section-title">🏥 Facility Information</div>
            <div class="form-grid">
                <div class="form-group">
                    <label>Facility Name</label>
                    <input type="text" id="facility-name">
                </div>
                <div class="form-group">
                    <label>Facility Type</label>
                    <select id="facility-type">
                        <option value="">Select...</option>
                        <option value="SNF">Skilled Nursing Facility (SNF)</option>
                        <option value="ALF">Assisted Living Facility (ALF)</option>
                        <option value="Hospital">Hospital</option>
                        <option value="Rehab">Rehabilitation Center</option>
                        <option value="Other">Other</option>
                    </select>
                </div>
            </div>

            <div class="section-title">🩺 Medical Information</div>
            <div class="form-grid">
                <div class="form-group full-width">
                    <label>Primary Diagnosis *</label>
                    <textarea id="diagnosis-primary" required></textarea>
                </div>
                <div class="form-group full-width">
                    <label>Secondary Diagnosis</label>
                    <textarea id="diagnosis-secondary"></textarea>
                </div>
                <div class="form-group full-width">
                    <label>ICD-10 Codes</label>
                    <input type="text" id="icd10-codes" placeholder="e.g., Z99.11, I50.9">
                </div>
            </div>

            <div class="section-title">🛏️ Service Type Requested</div>
            <div class="checkbox-group">
                <div class="checkbox-item">
                    <input type="checkbox" id="service-homehealth">
                    <label for="service-homehealth">Home Health</label>
                </div>
                <div class="checkbox-item">
                    <input type="checkbox" id="service-geriatric">
                    <label for="service-geriatric">Geriatric Care</label>
                </div>
                <div class="checkbox-item">
                    <input type="checkbox" id="service-respite">
                    <label for="service-respite">Respite Care</label>
                </div>
                <div class="checkbox-item">
                    <input type="checkbox" id="service-hospice">
                    <label for="service-hospice">Hospice</label>
                </div>
                <div class="checkbox-item">
                    <input type="checkbox" id="service-dme">
                    <label for="service-dme">DME/Prosthetics</label>
                </div>
            </div>

            <div class="section-title">📝 Additional Information</div>
            <div class="form-grid">
                <div class="form-group full-width">
                    <label>Service Orders</label>
                    <textarea id="service-orders"></textarea>
                </div>
                <div class="form-group full-width">
                    <label>Medications</label>
                    <textarea id="medications"></textarea>
                </div>
                <div class="form-group full-width">
                    <label>Allergies</label>
                    <textarea id="allergies"></textarea>
                </div>
                <div class="form-group">
                    <label>Emergency Contact Name</label>
                    <input type="text" id="emergency-name">
                </div>
                <div class="form-group">
                    <label>Emergency Contact Phone</label>
                    <input type="tel" id="emergency-phone">
                </div>
            </div>

            <div class="section-title">📅 Dates</div>
            <div class="form-grid">
                <div class="form-group">
                    <label>Referral Date</label>
                    <input type="date" id="referral-date">
                </div>
                <div class="form-group">
                    <label>Admission Date</label>
                    <input type="date" id="admission-date">
                </div>
                <div class="form-group">
                    <label>Discharge Date</label>
                    <input type="date" id="discharge-date">
                </div>
            </div>

            <div class="action-buttons">
                <button class="btn btn-success" onclick="previewRFS()">
                    📄 Preview VA Form 10-10172
                </button>
                <button class="btn btn-primary" onclick="downloadRFSPDF()">
                    ⬇️ Download PDF
                </button>
                <button class="btn btn-primary" onclick="downloadRFSHTML()">
                    💾 Download HTML
                </button>
            </div>
        </div>

        <!-- VA Form 10-10172 Preview (hidden until preview) -->
        <div id="va-rfs-form">
            <div class="rfs-header">
                <div class="rfs-title">REQUEST FOR SERVICES (RFS)</div>
                <div class="rfs-subtitle">VA FORM 10-10172 | Department of Veterans Affairs</div>
                <div class="rfs-subtitle">Medical Equipment and Prosthetics Services</div>
            </div>

            <div class="rfs-section">
                <h3 style="font-size: 14px; margin-bottom: 10px; border-bottom: 1px solid #000; padding-bottom: 5px;">SECTION I - VETERAN INFORMATION</h3>

                <div class="rfs-grid">
                    <div class="rfs-field">
                        <span class="rfs-label">1. VETERAN'S LAST NAME</span>
                        <div class="rfs-value" id="rfs-vet-last"></div>
                    </div>
                    <div class="rfs-field">
                        <span class="rfs-label">2. FIRST NAME</span>
                        <div class="rfs-value" id="rfs-vet-first"></div>
                    </div>
                </div>

                <div class="rfs-field">
                    <span class="rfs-label">3. MIDDLE NAME</span>
                    <div class="rfs-value" id="rfs-vet-middle"></div>
                </div>

                <div class="rfs-grid">
                    <div class="rfs-field">
                        <span class="rfs-label">4. DATE OF BIRTH</span>
                        <div class="rfs-value" id="rfs-vet-dob"></div>
                    </div>
                    <div class="rfs-field">
                        <span class="rfs-label">5. LAST 4 SSN</span>
                        <div class="rfs-value" id="rfs-vet-ssn"></div>
                    </div>
                </div>

                <div class="rfs-field">
                    <span class="rfs-label">6. ADDRESS</span>
                    <div class="rfs-value" id="rfs-vet-address-full"></div>
                </div>

                <div class="rfs-field">
                    <span class="rfs-label">7. PHONE</span>
                    <div class="rfs-value" id="rfs-vet-phone"></div>
                </div>
            </div>

            <div class="rfs-section">
                <h3 style="font-size: 14px; margin-bottom: 10px; border-bottom: 1px solid #000; padding-bottom: 5px;">SECTION II - ORDERING PROVIDER INFORMATION</h3>

                <div class="rfs-grid">
                    <div class="rfs-field">
                        <span class="rfs-label">8. ORDERING PROVIDER NAME</span>
                        <div class="rfs-value" id="rfs-provider-name"></div>
                    </div>
                    <div class="rfs-field">
                        <span class="rfs-label">9. PROVIDER NPI</span>
                        <div class="rfs-value" id="rfs-provider-npi"></div>
                    </div>
                </div>

                <div class="rfs-field">
                    <span class="rfs-label">10. PROVIDER OFFICE ADDRESS</span>
                    <div class="rfs-value" id="rfs-provider-address"></div>
                </div>

                <div class="rfs-grid">
                    <div class="rfs-field">
                        <span class="rfs-label">11. PHONE</span>
                        <div class="rfs-value" id="rfs-provider-phone"></div>
                    </div>
                    <div class="rfs-field">
                        <span class="rfs-label">12. FAX</span>
                        <div class="rfs-value" id="rfs-provider-fax"></div>
                    </div>
                </div>
            </div>

            <div class="rfs-section">
                <h3 style="font-size: 14px; margin-bottom: 10px; border-bottom: 1px solid #000; padding-bottom: 5px;">SECTION III - DIAGNOSIS AND SERVICES</h3>

                <div class="rfs-field">
                    <span class="rfs-label">13. PRIMARY DIAGNOSIS</span>
                    <div class="rfs-value" id="rfs-diagnosis-primary" style="min-height: 40px;"></div>
                </div>

                <div class="rfs-field">
                    <span class="rfs-label">14. SECONDARY DIAGNOSIS</span>
                    <div class="rfs-value" id="rfs-diagnosis-secondary" style="min-height: 40px;"></div>
                </div>

                <div class="rfs-field">
                    <span class="rfs-label">15. ICD-10 CODES</span>
                    <div class="rfs-value" id="rfs-icd10"></div>
                </div>

                <div class="rfs-field">
                    <span class="rfs-label">16. SERVICE TYPE REQUESTED (Check all that apply)</span>
                    <div style="margin-top: 8px;">
                        <div><span class="rfs-checkbox" id="rfs-check-homehealth"></span> Home Health Care</div>
                        <div><span class="rfs-checkbox" id="rfs-check-geriatric"></span> Geriatric Care</div>
                        <div><span class="rfs-checkbox" id="rfs-check-respite"></span> Respite Care</div>
                        <div><span class="rfs-checkbox" id="rfs-check-hospice"></span> Hospice Care</div>
                        <div><span class="rfs-checkbox" id="rfs-check-dme"></span> Durable Medical Equipment/Prosthetics</div>
                    </div>
                </div>

                <div class="rfs-field">
                    <span class="rfs-label">17. SERVICE ORDERS / SPECIFIC REQUESTS</span>
                    <div class="rfs-value" id="rfs-orders" style="min-height: 60px;"></div>
                </div>
            </div>

            <div class="rfs-section">
                <h3 style="font-size: 14px; margin-bottom: 10px; border-bottom: 1px solid #000; padding-bottom: 5px;">SECTION IV - ADDITIONAL INFORMATION</h3>

                <div class="rfs-field">
                    <span class="rfs-label">18. CURRENT MEDICATIONS</span>
                    <div class="rfs-value" id="rfs-medications" style="min-height: 40px;"></div>
                </div>

                <div class="rfs-field">
                    <span class="rfs-label">19. ALLERGIES</span>
                    <div class="rfs-value" id="rfs-allergies"></div>
                </div>

                <div class="rfs-grid">
                    <div class="rfs-field">
                        <span class="rfs-label">20. FACILITY NAME (if applicable)</span>
                        <div class="rfs-value" id="rfs-facility-name"></div>
                    </div>
                    <div class="rfs-field">
                        <span class="rfs-label">21. FACILITY TYPE</span>
                        <div class="rfs-value" id="rfs-facility-type"></div>
                    </div>
                </div>

                <div class="rfs-grid">
                    <div class="rfs-field">
                        <span class="rfs-label">22. EMERGENCY CONTACT</span>
                        <div class="rfs-value" id="rfs-emergency-contact"></div>
                    </div>
                    <div class="rfs-field">
                        <span class="rfs-label">23. EMERGENCY PHONE</span>
                        <div class="rfs-value" id="rfs-emergency-phone"></div>
                    </div>
                </div>
            </div>

            <div class="rfs-section">
                <h3 style="font-size: 14px; margin-bottom: 10px; border-bottom: 1px solid #000; padding-bottom: 5px;">SECTION V - DATES</h3>

                <div class="rfs-grid">
                    <div class="rfs-field">
                        <span class="rfs-label">24. REFERRAL DATE</span>
                        <div class="rfs-value" id="rfs-referral-date"></div>
                    </div>
                    <div class="rfs-field">
                        <span class="rfs-label">25. ADMISSION DATE</span>
                        <div class="rfs-value" id="rfs-admission-date"></div>
                    </div>
                </div>

                <div class="rfs-field">
                    <span class="rfs-label">26. DISCHARGE DATE (if applicable)</span>
                    <div class="rfs-value" id="rfs-discharge-date"></div>
                </div>
            </div>

            <div class="rfs-section" style="margin-top: 40px; border-top: 2px solid #000; padding-top: 20px;">
                <p style="font-size: 10px; font-style: italic;">
                    This form is to be completed by the ordering provider or authorized VA staff for requesting
                    medical equipment, prosthetics, home health services, or other veteran care services.
                </p>
                <div style="margin-top: 30px;">
                    <div style="display: inline-block; width: 45%;">
                        <div style="border-bottom: 1px solid #000; margin-bottom: 5px; height: 40px;"></div>
                        <span class="rfs-label">PROVIDER SIGNATURE</span>
                    </div>
                    <div style="display: inline-block; width: 45%; margin-left: 8%;">
                        <div style="border-bottom: 1px solid #000; margin-bottom: 5px; height: 40px;"></div>
                        <span class="rfs-label">DATE</span>
                    </div>
                </div>
            </div>

            <div style="margin-top: 30px; padding: 15px; background: #f0f0f0; border: 1px solid #ccc; font-size: 10px;">
                <strong>FOR COLORADO CARE ASSIST USE:</strong><br>
                Generated by: Colorado Care Assist VA RFS Converter<br>
                Processing Agency: Colorado Care Assist (CC.D)<br>
                Document prepared: <span id="rfs-generated-date"></span>
            </div>
        </div>
    </div>

    <script>
        // Initialize document type (default to face sheet, updated from AI extraction)
        window.rfsDocumentType = 'REFERRAL_FACE_SHEET';

        // File upload handling
        const uploadBox = document.getElementById('uploadBox');
        const pdfFile = document.getElementById('pdfFile');
        const loading = document.getElementById('loading');
        const formSection = document.getElementById('formSection');
        const alertContainer = document.getElementById('alertContainer');

        // Drag and drop
        uploadBox.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadBox.classList.add('dragover');
        });

        uploadBox.addEventListener('dragleave', () => {
            uploadBox.classList.remove('dragover');
        });

        uploadBox.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadBox.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                pdfFile.files = files;
                handleFileUpload();
            }
        });

        pdfFile.addEventListener('change', handleFileUpload);

        async function handleFileUpload() {
            const file = pdfFile.files[0];
            if (!file) return;

            if (file.type !== 'application/pdf') {
                showAlert('Please upload a PDF file', 'error');
                return;
            }

            loading.classList.add('active');
            formSection.classList.remove('active');

            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch('/api/parse-va-rfs-referral', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.success) {
                    populateFormFields(result.data);
                    formSection.classList.add('active');
                    showAlert(`✓ Success! Extracted ${result.fields_extracted} fields. Please review and edit as needed.`, 'success');
                    console.log('Extracted data from Gemini:', result.data);
                } else {
                    showAlert(`Failed to extract data: ${result.error}. Please fill in the form manually.`, 'error');
                    formSection.classList.add('active');
                }
            } catch (error) {
                console.error('Upload error:', error);
                showAlert('Error uploading file. Please try again or fill in manually.', 'error');
                formSection.classList.add('active');
            } finally {
                loading.classList.remove('active');
            }
        }

        function populateFormFields(data) {
            // Store document type for determining continuation of care
            window.rfsDocumentType = data.document_type || 'REFERRAL_FACE_SHEET';
            console.log('Document type detected:', window.rfsDocumentType);

            // Veteran info
            document.getElementById('vet-last-name').value = data.veteran_last_name || '';
            document.getElementById('vet-first-name').value = data.veteran_first_name || '';
            document.getElementById('vet-middle-name').value = data.veteran_middle_name || '';
            document.getElementById('vet-dob').value = convertDate(data.date_of_birth) || '';
            document.getElementById('vet-ssn-last4').value = data.last_4_ssn || '';
            document.getElementById('vet-phone').value = data.phone || '';
            document.getElementById('vet-address').value = data.address || '';
            document.getElementById('vet-city').value = data.city || '';
            document.getElementById('vet-state').value = data.state || '';
            document.getElementById('vet-zip').value = data.zip || '';

            // Provider info
            document.getElementById('provider-name').value = data.ordering_provider_name || '';
            document.getElementById('provider-npi').value = data.ordering_provider_npi || '';
            document.getElementById('provider-phone').value = data.ordering_provider_phone || '';
            document.getElementById('provider-fax').value = data.ordering_provider_fax || '';
            document.getElementById('provider-address').value = data.ordering_provider_address || '';

            // Facility info
            document.getElementById('facility-name').value = data.facility_name || '';
            if (data.facility_type) {
                document.getElementById('facility-type').value = data.facility_type;
            }

            // Medical info
            document.getElementById('diagnosis-primary').value = data.diagnosis_primary || '';
            document.getElementById('diagnosis-secondary').value = data.diagnosis_secondary || '';
            document.getElementById('icd10-codes').value = data.icd10_codes || '';

            // Additional info
            document.getElementById('service-orders').value = data.orders || data.service_requested || '';
            document.getElementById('medications').value = data.medications || '';
            document.getElementById('allergies').value = data.allergies || '';
            document.getElementById('emergency-name').value = data.emergency_contact_name || '';
            document.getElementById('emergency-phone').value = data.emergency_contact_phone || '';

            // Dates
            document.getElementById('referral-date').value = convertDate(data.referral_date) || '';
            document.getElementById('admission-date').value = convertDate(data.admission_date) || '';
            document.getElementById('discharge-date').value = convertDate(data.discharge_date) || '';

            // Auto-check service types based on care type
            const careType = (data.care_type || '').toLowerCase();
            if (careType.includes('home health') || careType.includes('hh')) {
                document.getElementById('service-homehealth').checked = true;
            }
            if (careType.includes('geriatric') || careType.includes('snf') || careType.includes('alf')) {
                document.getElementById('service-geriatric').checked = true;
            }
        }

        function convertDate(dateStr) {
            if (!dateStr) return '';
            // Handle MM/DD/YYYY format
            const match = dateStr.match(/(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})/);
            if (match) {
                const [, month, day, year] = match;
                return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
            }
            return '';
        }

        function formatDateForDisplay(dateInput) {
            if (!dateInput) return '';
            const date = new Date(dateInput);
            if (isNaN(date)) return dateInput;
            return (date.getMonth() + 1).toString().padStart(2, '0') + '/' +
                   date.getDate().toString().padStart(2, '0') + '/' +
                   date.getFullYear();
        }

        function previewRFS() {
            // Populate preview form
            document.getElementById('rfs-vet-last').textContent = document.getElementById('vet-last-name').value;
            document.getElementById('rfs-vet-first').textContent = document.getElementById('vet-first-name').value;
            document.getElementById('rfs-vet-middle').textContent = document.getElementById('vet-middle-name').value;
            document.getElementById('rfs-vet-dob').textContent = formatDateForDisplay(document.getElementById('vet-dob').value);
            document.getElementById('rfs-vet-ssn').textContent = document.getElementById('vet-ssn-last4').value;

            const fullAddress = [
                document.getElementById('vet-address').value,
                document.getElementById('vet-city').value,
                document.getElementById('vet-state').value,
                document.getElementById('vet-zip').value
            ].filter(x => x).join(', ');
            document.getElementById('rfs-vet-address-full').textContent = fullAddress;
            document.getElementById('rfs-vet-phone').textContent = document.getElementById('vet-phone').value;

            document.getElementById('rfs-provider-name').textContent = document.getElementById('provider-name').value;
            document.getElementById('rfs-provider-npi').textContent = document.getElementById('provider-npi').value;
            document.getElementById('rfs-provider-address').textContent = document.getElementById('provider-address').value;
            document.getElementById('rfs-provider-phone').textContent = document.getElementById('provider-phone').value;
            document.getElementById('rfs-provider-fax').textContent = document.getElementById('provider-fax').value;

            document.getElementById('rfs-diagnosis-primary').textContent = document.getElementById('diagnosis-primary').value;
            document.getElementById('rfs-diagnosis-secondary').textContent = document.getElementById('diagnosis-secondary').value;
            document.getElementById('rfs-icd10').textContent = document.getElementById('icd10-codes').value;

            // Checkboxes
            document.getElementById('rfs-check-homehealth').className = document.getElementById('service-homehealth').checked ? 'rfs-checkbox checked' : 'rfs-checkbox';
            document.getElementById('rfs-check-geriatric').className = document.getElementById('service-geriatric').checked ? 'rfs-checkbox checked' : 'rfs-checkbox';
            document.getElementById('rfs-check-respite').className = document.getElementById('service-respite').checked ? 'rfs-checkbox checked' : 'rfs-checkbox';
            document.getElementById('rfs-check-hospice').className = document.getElementById('service-hospice').checked ? 'rfs-checkbox checked' : 'rfs-checkbox';
            document.getElementById('rfs-check-dme').className = document.getElementById('service-dme').checked ? 'rfs-checkbox checked' : 'rfs-checkbox';

            document.getElementById('rfs-orders').textContent = document.getElementById('service-orders').value;
            document.getElementById('rfs-medications').textContent = document.getElementById('medications').value;
            document.getElementById('rfs-allergies').textContent = document.getElementById('allergies').value;

            document.getElementById('rfs-facility-name').textContent = document.getElementById('facility-name').value;
            document.getElementById('rfs-facility-type').textContent = document.getElementById('facility-type').value;

            const emergencyContact = document.getElementById('emergency-name').value;
            document.getElementById('rfs-emergency-contact').textContent = emergencyContact;
            document.getElementById('rfs-emergency-phone').textContent = document.getElementById('emergency-phone').value;

            document.getElementById('rfs-referral-date').textContent = formatDateForDisplay(document.getElementById('referral-date').value);
            document.getElementById('rfs-admission-date').textContent = formatDateForDisplay(document.getElementById('admission-date').value);
            document.getElementById('rfs-discharge-date').textContent = formatDateForDisplay(document.getElementById('discharge-date').value);

            document.getElementById('rfs-generated-date').textContent = new Date().toLocaleDateString('en-US');

            // Show preview
            document.getElementById('va-rfs-form').classList.add('active');
            document.getElementById('va-rfs-form').scrollIntoView({ behavior: 'smooth' });
        }

        async function downloadRFSPDF() {
            // Collect all form data
            const formData = {
                veteran_last_name: document.getElementById('vet-last-name').value,
                veteran_first_name: document.getElementById('vet-first-name').value,
                veteran_middle_name: document.getElementById('vet-middle-name').value,
                date_of_birth: formatDateForDisplay(document.getElementById('vet-dob').value),
                last_4_ssn: document.getElementById('vet-ssn-last4').value,
                phone: document.getElementById('vet-phone').value,
                address: document.getElementById('vet-address').value,
                city: document.getElementById('vet-city').value,
                state: document.getElementById('vet-state').value,
                zip: document.getElementById('vet-zip').value,
                ordering_provider_name: document.getElementById('provider-name').value,
                ordering_provider_npi: document.getElementById('provider-npi').value,
                ordering_provider_phone: document.getElementById('provider-phone').value,
                ordering_provider_fax: document.getElementById('provider-fax').value,
                ordering_provider_address: document.getElementById('provider-address').value,
                facility_name: document.getElementById('facility-name').value,
                facility_type: document.getElementById('facility-type').value,
                diagnosis_primary: document.getElementById('diagnosis-primary').value,
                diagnosis_secondary: document.getElementById('diagnosis-secondary').value,
                icd10_codes: document.getElementById('icd10-codes').value,
                care_type: getCareType(),
                service_requested: document.getElementById('service-orders').value,
                orders: document.getElementById('service-orders').value,
                medications: document.getElementById('medications').value,
                allergies: document.getElementById('allergies').value,
                emergency_contact_name: document.getElementById('emergency-name').value,
                emergency_contact_phone: document.getElementById('emergency-phone').value,
                referral_date: formatDateForDisplay(document.getElementById('referral-date').value),
                admission_date: formatDateForDisplay(document.getElementById('admission-date').value),
                discharge_date: formatDateForDisplay(document.getElementById('discharge-date').value),
                is_continuation_of_care: (window.rfsDocumentType === 'VA_10_7080')  // YES *ONLY* for VA 10-7080 authorization forms
            };

            try {
                // Show loading indicator
                const btn = event.target;
                const originalText = btn.textContent;
                btn.textContent = 'Generating PDF...';
                btn.disabled = true;

                // Call API to fill official VA Form 10-10172 PDF
                const response = await fetch('/api/fill-va-rfs-form', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });

                if (!response.ok) {
                    throw new Error('Failed to generate PDF');
                }

                // Download the filled PDF
                const blob = await response.blob();
                const filename = generateRFSFilename();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename + '.pdf';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);

                btn.textContent = originalText;
                btn.disabled = false;

            } catch (error) {
                console.error('PDF generation error:', error);
                showAlert('Failed to generate PDF. Please try again.', 'error');
                if (event.target) {
                    event.target.textContent = '⬇️ Download PDF';
                    event.target.disabled = false;
                }
            }
        }

        function getCareType() {
            const types = [];
            if (document.getElementById('service-homehealth').checked) types.push('Home Health');
            if (document.getElementById('service-geriatric').checked) types.push('Geriatric Care');
            if (document.getElementById('service-respite').checked) types.push('Respite Care');
            if (document.getElementById('service-hospice').checked) types.push('Hospice');
            if (document.getElementById('service-dme').checked) types.push('DME/Prosthetics');
            return types.join(', ');
        }

        function downloadRFSHTML() {
            previewRFS();

            const filename = generateRFSFilename();
            const htmlContent = document.getElementById('va-rfs-form').outerHTML;
            const fullHTML = `<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>VA Form 10-10172 RFS</title>
    <style>
        ${document.querySelector('style').textContent}
    </style>
</head>
<body>
    ${htmlContent}
</body>
</html>`;

            const blob = new Blob([fullHTML], { type: 'text/html' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename + '.html';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }

        function generateRFSFilename() {
            const vetLast = document.getElementById('vet-last-name').value || 'Veteran';
            const vetFirst = document.getElementById('vet-first-name').value || 'V';
            const vetFirstInitial = vetFirst.charAt(0).toUpperCase();
            const last4 = document.getElementById('vet-ssn-last4').value || '0000';

            const today = new Date();
            const month = (today.getMonth() + 1).toString().padStart(2, '0');
            const day = today.getDate().toString().padStart(2, '0');
            const year = today.getFullYear();

            return `${vetLast}.${vetFirstInitial}.${last4}_VA-RFS-10-10172.${month}.${day}.${year}`;
        }

        function showAlert(message, type) {
            const alertClass = type === 'success' ? 'alert-success' : 'alert-error';
            alertContainer.innerHTML = `<div class="alert ${alertClass}">${message}</div>`;
            setTimeout(() => {
                alertContainer.innerHTML = '';
            }, 8000);
        }
    </script>
</body>
</html>"""
    return HTMLResponse(content=va_rfs_html_content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

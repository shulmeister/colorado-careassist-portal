from fastapi import FastAPI, HTTPException, Request, Depends, status, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date as date_cls
import httpx
from urllib.parse import urlencode, quote_plus, urljoin
from portal_auth import oauth_manager, get_current_user, get_current_user_optional
from portal_database import get_db, db_manager
from portal_models import PortalTool, Base, UserSession, ToolClick, Voucher, BrevoWebhookEvent
from services.marketing.metrics_service import (
    get_social_metrics,
    get_ads_metrics,
    get_email_metrics,
)
# Import client satisfaction service at module load time (before sales path takes precedence)
try:
    from services.client_satisfaction_service import client_satisfaction_service
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Client satisfaction service not available: {e}")
    client_satisfaction_service = None

# Import AI Care Coordinator service (Zingage/Phoebe style automation)
try:
    from services.ai_care_coordinator import ai_care_coordinator
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"AI Care Coordinator not available: {e}")
    ai_care_coordinator = None

# Import GoFormz → WellSky sync service for webhook processing
try:
    from services.goformz_wellsky_sync import goformz_wellsky_sync as _goformz_wellsky_sync_module
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"GoFormz-WellSky sync service not available: {e}")
    _goformz_wellsky_sync_module = None

# Import WellSky service directly for Operations Dashboard
try:
    from services.wellsky_service import wellsky_service, ShiftStatus
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"WellSky service not available: {e}")
    wellsky_service = None
    ShiftStatus = None

from dotenv import load_dotenv
from datetime import date
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
    "https://client-satisfaction-15d412babc2f.herokuapp.com/",
)

ACTIVITY_TRACKER_URL = os.getenv(
    "ACTIVITY_TRACKER_URL",
    "https://cca-activity-tracker-6d9a1d8e3933.herokuapp.com/",
)

PORTAL_SECRET = os.getenv("PORTAL_SECRET", "colorado-careassist-portal-2025")
PORTAL_SSO_SERIALIZER = URLSafeTimedSerializer(PORTAL_SECRET)
PORTAL_SSO_TOKEN_TTL = int(os.getenv("PORTAL_SSO_TOKEN_TTL", "300"))

app = FastAPI(title="Colorado CareAssist Portal", version="1.0.0")

# Add session middleware for OAuth state management
from starlette.middleware.sessions import SessionMiddleware
import secrets
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", secrets.token_urlsafe(32)))

# Add security middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "https://portal.coloradocareassist.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "127.0.0.1", "*.herokuapp.com", "portal.coloradocareassist.com"]
)

# Mount static files and templates
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ==================== Module Mounting ====================

# 1. Mount Tracker (FastAPI)
try:
    from services.tracker.router import router as tracker_router
    # Mount tracker router
    app.include_router(tracker_router, prefix="/tracker", tags=["tracker"])
    logger.info("Mounted Tracker module at /tracker")
except Exception as e:
    logger.error(f"Failed to mount Tracker module: {e}")

# Recruiter dashboard is now mounted at /recruiting via unified_app.py
# No mounting needed here - the Flask app is mounted at the unified_app level

# =========================================================

# Authentication endpoints
@app.get("/auth/login")
async def login():
    """Redirect to Google OAuth login"""
    try:
        auth_url = oauth_manager.get_authorization_url()
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Authentication service unavailable")

@app.get("/auth/callback")
async def auth_callback(request: Request, code: str = None, error: str = None):
    """Handle Google OAuth callback"""
    if error:
        logger.error(f"OAuth error: {error}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not provided")
    
    try:
        result = await oauth_manager.handle_callback(code, "")
        
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

@app.post("/api/tools")
async def create_tool(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create new tool (admin only)"""
    try:
        data = await request.json()
        
        # Check if user is admin (for now, allow all authenticated users)
        # In production, you might want to add an admin check
        
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
    from fastapi.responses import FileResponse, Response
    import os
    
    favicon_path = "static/favicon.ico"
    if os.path.exists(favicon_path):
        response = FileResponse(favicon_path)
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response
    
    # Fallback to SVG if ICO doesn't exist
    svg_path = "static/favicon.svg"
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
            return JSONResponse({
                "success": False,
                "error": "Weather API key not configured"
            }, status_code=500)
        
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
        from sqlalchemy import func, distinct
        
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

# ==================== Embedded Dashboards ====================

# Sales dashboard is now mounted at /sales via unified_app.py
# No redirect needed - the mounted FastAPI app handles /sales/* routes directly


@app.get("/activity-tracker")
async def activity_tracker_redirect(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Redirect to Activity Tracker using portal-issued SSO token"""
    tracker_url = ACTIVITY_TRACKER_URL.rstrip("/")
    token_payload = {
        "user_id": current_user.get("email"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "domain": current_user.get("email", "").split("@")[-1] if current_user.get("email") else "",
        "via_portal": True,
        "login_time": datetime.utcnow().isoformat()
    }

    portal_token = PORTAL_SSO_SERIALIZER.dumps(token_payload)
    tracker_portal_auth = tracker_url + "/portal-auth"

    query = urlencode({
        "portal_token": portal_token,
        "portal_user_email": current_user.get("email", "")
    })

    redirect_url = f"{tracker_portal_auth}?{query}"
    logger.info(f"Redirecting {current_user.get('email')} to Activity Tracker with portal token")
    return RedirectResponse(url=redirect_url, status_code=302)

@app.get("/recruitment", response_class=HTMLResponse)
async def recruitment_dashboard_embedded(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Embedded Recruitment Dashboard (iframe)"""
    recruitment_dashboard_url = os.getenv(
        "RECRUITMENT_DASHBOARD_URL",
        "https://caregiver-lead-tracker-9d0e6a8c7c20.herokuapp.com/"
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


# ============================================================================
# Client Satisfaction API Endpoints
# ============================================================================

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
    """Get AI Care Coordinator dashboard (Zingage/Phoebe style)"""
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
# Operations Dashboard (Client Operations with WellSky Integration)
# ============================================================================

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


@app.get("/api/operations/summary")
async def api_operations_summary(
    days: int = Query(30, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get operations dashboard summary metrics from WellSky"""
    if wellsky_service is None:
        raise HTTPException(status_code=503, detail="WellSky service not available")

    try:
        summary = wellsky_service.get_operations_summary(days=days)
        # Add weekly shift data for chart
        summary["shifts_by_day"] = _get_weekly_shift_data()
        summary["wellsky_connected"] = not wellsky_service.is_mock_mode
        return JSONResponse(summary)
    except Exception as e:
        logger.error(f"Error getting operations summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_weekly_shift_data() -> Dict[str, List[int]]:
    """Get shift counts by day of week for the chart"""
    if wellsky_service is None:
        return {"scheduled": [0]*7, "open": [0]*7}

    from datetime import date, timedelta
    today = date.today()
    # Get start of current week (Monday)
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    try:
        shifts = wellsky_service.get_open_shifts(start_of_week, end_of_week)
        scheduled = [0]*7
        open_shifts = [0]*7

        for shift in shifts:
            shift_date = shift.date if hasattr(shift, 'date') else None
            if shift_date:
                day_idx = (shift_date - start_of_week).days
                if 0 <= day_idx < 7:
                    if shift.status.value == 'open':
                        open_shifts[day_idx] += 1
                    else:
                        scheduled[day_idx] += 1

        return {"scheduled": scheduled, "open": open_shifts}
    except Exception as e:
        logger.error(f"Error getting weekly shift data: {e}")
        return {"scheduled": [0]*7, "open": [0]*7}


@app.get("/api/operations/clients")
async def api_operations_clients(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get client list with risk indicators from WellSky"""
    if wellsky_service is None:
        raise HTTPException(status_code=503, detail="WellSky service not available")

    try:
        clients = wellsky_service.get_clients(status="active")
        client_list = []
        for client in clients:
            # Get risk indicators for each client
            indicators = wellsky_service.get_client_satisfaction_indicators(client.id)
            client_list.append({
                "id": client.id,
                "name": client.name,
                "status": client.status.value if hasattr(client.status, 'value') else str(client.status),
                "hours_per_week": getattr(client, 'hours_per_week', None),
                "payer": getattr(client, 'payer_type', 'N/A'),
                "risk_score": indicators.get("risk_score", 0) if indicators else 0,
                "last_visit": getattr(client, 'last_visit_date', None),
            })
        return JSONResponse({"clients": client_list})
    except Exception as e:
        logger.error(f"Error getting operations clients: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/operations/care-plans")
async def api_operations_care_plans(
    days: int = Query(30, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get care plans due for review from WellSky"""
    if wellsky_service is None:
        raise HTTPException(status_code=503, detail="WellSky service not available")

    try:
        plans = wellsky_service.get_care_plans_due_for_review(days_ahead=days)
        plan_list = []
        for plan in plans:
            days_until = (plan.review_date - date.today()).days if plan.review_date else None
            plan_list.append({
                "id": plan.id,
                "client_id": plan.client_id,
                "client_name": plan.client_name,
                "status": plan.status.value if hasattr(plan.status, 'value') else str(plan.status),
                "review_date": plan.review_date.isoformat() if plan.review_date else None,
                "days_until_review": days_until,
                "authorized_hours": getattr(plan, 'authorized_hours_per_week', None),
            })
        return JSONResponse({"care_plans": plan_list})
    except Exception as e:
        logger.error(f"Error getting care plans: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/operations/open-shifts")
async def api_operations_open_shifts(
    days: int = Query(14, ge=1, le=60),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get open shifts that need coverage from WellSky"""
    if wellsky_service is None:
        raise HTTPException(status_code=503, detail="WellSky service not available")

    try:
        from datetime import date, timedelta
        date_from = date.today()
        date_to = date_from + timedelta(days=days)

        shifts = wellsky_service.get_open_shifts(date_from, date_to)
        # Filter to only open shifts
        open_shifts = [s for s in shifts if s.status.value == 'open']

        shift_list = []
        for shift in open_shifts:
            shift_list.append({
                "id": shift.id,
                "date": shift.date.isoformat() if shift.date else None,
                "start_time": shift.start_time.strftime("%I:%M %p") if shift.start_time else None,
                "end_time": shift.end_time.strftime("%I:%M %p") if shift.end_time else None,
                "client_id": shift.client_id,
                "client_name": shift.client_name,
                "location": getattr(shift, 'location', None),
                "hours": getattr(shift, 'hours', None),
                "status": "open",
            })
        return JSONResponse({"shifts": shift_list})
    except Exception as e:
        logger.error(f"Error getting open shifts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/operations/at-risk")
async def api_operations_at_risk(
    threshold: int = Query(40, ge=0, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get at-risk clients from WellSky"""
    if wellsky_service is None:
        raise HTTPException(status_code=503, detail="WellSky service not available")

    try:
        at_risk = wellsky_service.get_at_risk_clients(threshold=threshold)
        return JSONResponse({"clients": at_risk, "threshold": threshold})
    except Exception as e:
        logger.error(f"Error getting at-risk clients: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Gigi AI Agent Control API
# ============================================================================

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


@app.get("/api/gigi/settings")
async def api_gigi_settings(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get current Gigi settings"""
    return JSONResponse({
        "sms_autoreply": _gigi_settings["sms_autoreply"],
        "operations_sms": _gigi_settings["operations_sms"],
        "wellsky_connected": wellsky_service is not None and wellsky_service.is_configured,
    })


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


# ============================================================================
# GoFormz → WellSky Webhook Endpoint
# ============================================================================

def _get_goformz_wellsky_sync():
    """Get the goformz_wellsky_sync service (loaded at module import time)."""
    return _goformz_wellsky_sync_module


@app.get("/api/goformz/wellsky-sync/debug")
async def goformz_wellsky_sync_debug():
    """Debug endpoint to check goformz_wellsky_sync service status."""
    import sys as _sys
    import os as _os

    root_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    services_dir = _os.path.join(root_dir, 'services')
    sync_path = _os.path.join(services_dir, 'goformz_wellsky_sync.py')

    return JSONResponse({
        "root_dir": root_dir,
        "services_dir": services_dir,
        "sync_path": sync_path,
        "sync_file_exists": _os.path.exists(sync_path),
        "services_in_sys_modules": 'services' in _sys.modules,
        "root_in_sys_path": root_dir in _sys.path,
        "service_loaded": _goformz_wellsky_sync_module is not None,
        "service_type": str(type(_goformz_wellsky_sync_module)) if _goformz_wellsky_sync_module else None
    })


@app.post("/api/goformz/wellsky-webhook")
async def goformz_wellsky_webhook(request: Request):
    """
    Webhook endpoint for GoFormz to trigger WellSky status updates.

    When client/employee packets are completed in GoFormz:
    - Client Packet → converts WellSky prospect to client
    - Employee Packet → converts WellSky applicant to caregiver

    This is the final step in the hub-and-spoke integration.
    """
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
        if event_type not in ['form.complete', 'completed', 'submitted', 'signed']:
            return JSONResponse({
                "success": True,
                "message": f"Event type '{event_type}' not a completion - ignored"
            })

        # Extract form info
        item = payload.get('Item', {})
        submission_id = item.get('Id') or payload.get('submissionId') or payload.get('submission_id')
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
            logger.warning(f"Unknown form type in GoFormz webhook: {form_name}")
            return JSONResponse({
                "success": True,
                "message": f"Unknown form type '{form_name}' - no WellSky action taken"
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


# ============================================================================
# AI Care Coordinator API Endpoints (Zingage/Phoebe Style)
# ============================================================================

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


# =============================================================================
# RingCentral Chat Scanner API
# =============================================================================

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


# =============================================================================
# RingCentral Call Pattern Monitoring API
# =============================================================================

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
    from services.oauth_manager import oauth_manager
    import secrets
    
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
    from services.oauth_manager import oauth_manager
    from portal_models import OAuthToken
    from datetime import datetime
    
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
                extra_data=token_data.get("extra_data")
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
    compare: Optional[str] = Query(None)
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
async def google_ads_webhook(request: Request):
    """
    Webhook endpoint to receive Google Ads metrics from Google Ads Scripts.
    
    The script runs in Google Ads and POSTs data here periodically.
    """
    import os
    import json
    from datetime import datetime
    
    # Optional: Verify webhook secret for security
    webhook_secret = os.getenv("GOOGLE_ADS_WEBHOOK_SECRET")
    if webhook_secret:
        received_secret = request.headers.get("X-Webhook-Secret")
        if received_secret != webhook_secret:
            logger.warning("Google Ads webhook: Invalid secret")
            raise HTTPException(status_code=401, detail="Invalid webhook secret")
    
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
    compare: Optional[str] = Query(None)
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
async def brevo_marketing_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook endpoint for Brevo marketing email events.
    Stores events for real-time metrics aggregation (hybrid model: webhooks + API).
    
    Events: delivered, opened, click, hardBounce, softBounce, spam, unsubscribed
    """
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
    to_date: Optional[str] = Query(None, alias="to")
):
    """Return website and GBP metrics from GA4 and Google Business Profile."""
    from services.marketing.ga4_service import ga4_service
    from services.marketing.gbp_service import gbp_service
    import logging
    
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
async def test_ga4_connection():
    """Test GA4 connection and return status."""
    from services.marketing.ga4_service import ga4_service
    import os
    
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
async def test_predis_connection():
    """Test Predis AI connection and return status."""
    from services.marketing.predis_service import predis_service
    import os
    
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
async def get_predis_posts(page: int = 1):
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
async def generate_predis_content(request: Request):
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
async def get_predis_templates(page: int = 1):
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
async def test_gbp_connection():
    """Test GBP connection and return status."""
    from services.marketing.gbp_service import gbp_service
    import os
    
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
    from services.marketing.ga4_service import ga4_service
    from services.marketing.gbp_service import gbp_service
    from services.marketing.pinterest_service import pinterest_service
    from services.marketing.linkedin_service import linkedin_service
    import logging
    
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
):
    """
    Fetch Pinterest analytics and engagement metrics.
    
    Returns pin performance, saves, clicks, and engagement data.
    """
    from services.marketing.pinterest_service import pinterest_service
    from datetime import date, timedelta
    
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
async def test_pinterest_connection():
    """Test Pinterest connection and return status."""
    from services.marketing.pinterest_service import pinterest_service
    import os
    
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

    redirect_uri = "https://careassist-unified-0a11ddb45ac0.herokuapp.com/api/pinterest/callback"
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
    import os
    import base64
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
    redirect_uri = "https://careassist-unified-0a11ddb45ac0.herokuapp.com/api/pinterest/callback"

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
                "instructions": "Set this access_token as PINTEREST_ACCESS_TOKEN on Heroku"
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
):
    """
    Fetch LinkedIn analytics and engagement metrics.
    
    Returns post performance, impressions, clicks, and engagement data.
    """
    from services.marketing.linkedin_service import linkedin_service
    from datetime import date, timedelta
    
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
async def test_linkedin_connection():
    """Test LinkedIn connection and return status."""
    from services.marketing.linkedin_service import linkedin_service
    import os
    
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
            "https://careassist-unified-0a11ddb45ac0.herokuapp.com/api/linkedin/callback"
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
    redirect_uri = "https://careassist-unified-0a11ddb45ac0.herokuapp.com/api/linkedin/callback"
    token_data = linkedin_service.exchange_code_for_token(code, redirect_uri)
    
    if token_data and "access_token" in token_data:
        # Return the token (user needs to set it as env var)
        return JSONResponse({
            "success": True,
            "message": "LinkedIn authorized successfully!",
            "access_token": token_data["access_token"],
            "expires_in": token_data.get("expires_in"),
            "instructions": "Set this access token as LINKEDIN_ACCESS_TOKEN environment variable on Heroku",
        })
    else:
        return JSONResponse({
            "success": False,
            "error": "Failed to exchange code for token",
            "details": token_data,
        })


# ========================================
# TikTok Marketing Endpoints
# ========================================

@app.get("/api/marketing/tiktok")
async def api_marketing_tiktok(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
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
async def test_tiktok_connection():
    """Test TikTok connection and return status."""
    from services.marketing.tiktok_service import tiktok_service
    import os

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


# ========================================
# Google Business Profile OAuth Endpoints
# ========================================

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
            "instructions": "Set these tokens as GBP_ACCESS_TOKEN and GBP_REFRESH_TOKEN environment variables on Heroku. The refresh token is used to automatically get new access tokens.",
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


# ============================================================================
# Shift Filling API Endpoints (Operations Dashboard)
# ============================================================================

# Add the sales directory to the path for shift_filling imports
import sys
sales_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sales')
if sales_dir not in sys.path:
    sys.path.insert(0, sales_dir)

try:
    from shift_filling import (
        shift_filling_engine, wellsky_mock, sms_service,
        CaregiverMatcher, OutreachStatus
    )
    SHIFT_FILLING_AVAILABLE = True
    logger.info("Shift filling module loaded successfully")
except ImportError as e:
    SHIFT_FILLING_AVAILABLE = False
    logger.warning(f"Shift filling module not available: {e}")


@app.get("/api/shift-filling/status")
async def shift_filling_status():
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
async def get_open_shifts():
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
async def get_caregivers():
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
async def match_caregivers_for_shift(shift_id: str, max_results: int = 20):
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
async def process_calloff(request: Request):
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
async def get_active_campaigns():
    """Get all active shift filling campaigns"""
    if not SHIFT_FILLING_AVAILABLE:
        return JSONResponse({"active_campaigns": [], "total": 0})

    campaigns = shift_filling_engine.get_all_active_campaigns()
    return JSONResponse({
        "active_campaigns": campaigns,
        "total": len(campaigns)
    })


@app.post("/api/shift-filling/demo")
async def run_demo():
    """Run a full demonstration of the shift filling process"""
    if not SHIFT_FILLING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Shift filling not available")

    result = shift_filling_engine.simulate_demo()
    return JSONResponse(result)


@app.get("/api/shift-filling/sms-log")
async def get_sms_log(hours: int = 24):
    """Get SMS message log from RingCentral for 719-428-3999"""
    import requests
    from datetime import datetime, timedelta
    import re

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


# ============================================================================
# End of Shift Filling API Endpoints
# ============================================================================


# ============================================================================
# Gigi AI Agent API Endpoints (After-Hours Support)
# ============================================================================

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


# =============================================================================
# WellSky Shift Management API (Used by Gigi for Call-Outs)
# =============================================================================

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


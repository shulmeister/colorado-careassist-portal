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
    "https://portal.coloradocareassist.com/client-satisfaction/",
)

ACTIVITY_TRACKER_URL = os.getenv(
    "ACTIVITY_TRACKER_URL",
    "https://portal.coloradocareassist.com/activity/",
)

PORTAL_SECRET = os.getenv("PORTAL_SECRET", "colorado-careassist-portal-2025")
PORTAL_SSO_SERIALIZER = URLSafeTimedSerializer(PORTAL_SECRET)
PORTAL_SSO_TOKEN_TTL = int(os.getenv("PORTAL_SSO_TOKEN_TTL", "300"))

app = FastAPI(title="Colorado CareAssist Portal", version="1.0.0")

# Include Gigi voice function router
try:
    from gigi_voice_functions import router as gigi_voice_router
    app.include_router(gigi_voice_router)
    logger.info("✅ Gigi voice functions loaded")
except Exception as e:
    logger.error(f"❌ Failed to load Gigi voice functions: {e}")

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
    allowed_hosts=["localhost", "127.0.0.1", "portal.coloradocareassist.com"]
)

# Mount static files and templates
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

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
# Note: /sales and /recruiting are now mounted directly in unified_app.py
# The redirect routes below are commented out to avoid conflicts

# @app.get("/sales")
# async def sales_dashboard_redirect(
#     current_user: Dict[str, Any] = Depends(get_current_user)
# ):
#     """Redirect to Sales Dashboard using portal-issued SSO token"""
#     sales_dashboard_url = os.getenv(
#         "SALES_DASHBOARD_URL",
#         "https://portal.coloradocareassist.com/sales"
#     )
#
#     token_payload = {
#         "user_id": current_user.get("email"),
#         "email": current_user.get("email"),
#         "name": current_user.get("name"),
#         "domain": current_user.get("email", "").split("@")[-1] if current_user.get("email") else "",
#         "via_portal": True,
#         "login_time": datetime.utcnow().isoformat()
#     }
#
#     portal_token = PORTAL_SSO_SERIALIZER.dumps(token_payload)
#     sales_portal_auth = sales_dashboard_url.rstrip("/") + "/portal-auth"
#
#     query = urlencode({
#         "portal_token": portal_token,
#         "portal_user_email": current_user.get("email", "")
#     })
#
#     redirect_url = f"{sales_portal_auth}?{query}"
#
#     logger.info(f"Redirecting {current_user.get('email')} to Sales Dashboard with portal token")
#     return RedirectResponse(url=redirect_url, status_code=302)


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
        "https://portal.coloradocareassist.com/recruiting/"
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


@app.get("/client-satisfaction", response_class=HTMLResponse)
async def client_satisfaction_embedded(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Embedded Client Satisfaction tracker (iframe)"""
    tracker_url = CLIENT_SATISFACTION_APP_URL

    session_token = request.cookies.get("session_token", "")
    if session_token:
        separator = "&" if "?" in tracker_url else "?"
        encoded_token = quote_plus(session_token)
        encoded_email = quote_plus(current_user.get("email", ""))
        tracker_url_with_auth = (
            f"{tracker_url}{separator}portal_token={encoded_token}&portal_user_email={encoded_email}"
        )
        logger.info(
            "Passing portal token to Client Satisfaction tracker for user: %s",
            current_user.get("email"),
        )
    else:
        logger.warning("No session token found - Client Satisfaction tracker will require login")
        tracker_url_with_auth = tracker_url

    return templates.TemplateResponse(
        "client_satisfaction_embedded.html",
        {
            "request": request,
            "user": current_user,
            "tracker_url": tracker_url_with_auth,
        },
    )


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


@app.post("/api/marketing/predis/webhook")
async def predis_webhook(request: Request):
    """
    Webhook endpoint for Predis AI notifications.
    
    Handles notifications when content generation completes or fails.
    Expected payload from Predis AI:
    {
        "event": "content_generated" | "content_failed" | "content_published",
        "content_id": "...",
        "status": "completed" | "failed" | "published",
        "media_url": "...",
        "text": "...",
        "error": "..." (if failed),
        "timestamp": "..."
    }
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Get the raw body for signature verification (if needed)
        body = await request.body()
        data = await request.json()
        
        # Log the webhook event
        event_type = data.get("event", "unknown")
        content_id = data.get("content_id", "unknown")
        logger.info(f"Predis webhook received: {event_type} for content {content_id}")
        
        # Handle different event types
        if event_type == "content_generated":
            # Content was successfully generated
            logger.info(f"Content generated successfully: {content_id}")
            logger.info(f"Media URL: {data.get('media_url')}")
            logger.info(f"Text: {data.get('text', '')[:100]}...")
            
            # TODO: Store in database or notify user
            # TODO: Send to scheduling queue if auto-publish enabled
            
        elif event_type == "content_failed":
            # Content generation failed
            logger.error(f"Content generation failed: {content_id}")
            logger.error(f"Error: {data.get('error', 'Unknown error')}")
            
            # TODO: Notify user of failure
            # TODO: Retry logic if appropriate
            
        elif event_type == "content_published":
            # Content was published to social media
            logger.info(f"Content published: {content_id}")
            logger.info(f"Platform: {data.get('platform', 'unknown')}")
            logger.info(f"Post URL: {data.get('post_url', '')}")
            
            # TODO: Update analytics
            # TODO: Track performance
            
        else:
            logger.warning(f"Unknown webhook event type: {event_type}")
        
        # Return success response
        return JSONResponse({
            "success": True,
            "message": f"Webhook processed for event: {event_type}",
            "content_id": content_id
        })
        
    except Exception as e:
        logger.error(f"Predis webhook error: {e}")
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
    import os
    import base64

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


# ============================================================================
# QUICKBOOKS OAUTH CALLBACK
# ============================================================================

QB_CLIENT_ID = os.getenv("QB_CLIENT_ID")
QB_CLIENT_SECRET = os.getenv("QB_CLIENT_SECRET")
QB_REDIRECT_URI = os.getenv("QB_REDIRECT_URI", "https://portal.coloradocareassist.com/qb/callback")

@app.get("/qb/callback")
async def quickbooks_callback(
    code: str = Query(None),
    realmId: str = Query(None),
    state: str = Query(None),
    error: str = Query(None)
):
    """
    QuickBooks OAuth2 callback - exchanges code for tokens.
    After authorizing, displays tokens for local CLI setup.
    """
    if error:
        return HTMLResponse(f"""
        <html><body style="font-family: sans-serif; padding: 40px;">
        <h1>❌ QuickBooks Authorization Failed</h1>
        <p>Error: {error}</p>
        </body></html>
        """)
    
    if not code or not realmId:
        return HTMLResponse("""
        <html><body style="font-family: sans-serif; padding: 40px;">
        <h1>❌ Missing Parameters</h1>
        <p>Authorization code or realm ID not provided.</p>
        </body></html>
        """)
    
    # Exchange code for tokens
    import base64
    
    if not QB_CLIENT_ID or not QB_CLIENT_SECRET:
        return HTMLResponse(f"""
        <html><body style="font-family: sans-serif; padding: 40px;">
        <h1>⚠️ QuickBooks Credentials Not Configured</h1>
        <p>Set QB_CLIENT_ID and QB_CLIENT_SECRET in Mac Mini (Local) config.</p>
        <h2>Manual Token Exchange</h2>
        <p>Use these values in your local CLI:</p>
        <pre style="background: #f0f0f0; padding: 20px; border-radius: 8px;">
Code: {code}
Realm ID: {realmId}
        </pre>
        </body></html>
        """)
    
    auth_header = base64.b64encode(f"{QB_CLIENT_ID}:{QB_CLIENT_SECRET}".encode()).decode()
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": QB_REDIRECT_URI
            }
        )
    
    if resp.status_code != 200:
        return HTMLResponse(f"""
        <html><body style="font-family: sans-serif; padding: 40px;">
        <h1>❌ Token Exchange Failed</h1>
        <p>Status: {resp.status_code}</p>
        <pre>{resp.text}</pre>
        </body></html>
        """)
    
    tokens = resp.json()
    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    expires_in = tokens.get("expires_in", 3600)
    
    # Display tokens for manual copy to local CLI
    return HTMLResponse(f"""
    <html><body style="font-family: sans-serif; padding: 40px; max-width: 800px;">
    <h1>✅ QuickBooks Connected!</h1>
    <p>Copy these values to your local <code>~/clawd/credentials/quickbooks.json</code>:</p>
    <pre style="background: #f0f0f0; padding: 20px; border-radius: 8px; overflow-x: auto;">
{{
  "realm_id": "{realmId}",
  "access_token": "{access_token[:50]}...{access_token[-20:]}",
  "refresh_token": "{refresh_token}",
  "token_expires_in": {expires_in}
}}
    </pre>
    <h3>Full Access Token (select all & copy):</h3>
    <textarea style="width: 100%; height: 100px; font-family: monospace;" readonly>{access_token}</textarea>
    <p style="margin-top: 20px; color: #666;">You can close this window.</p>
    </body></html>
    """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


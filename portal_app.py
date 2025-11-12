from fastapi import FastAPI, HTTPException, Request, Depends, status, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
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
from urllib.parse import urlencode
from portal_auth import oauth_manager, get_current_user, get_current_user_optional
from portal_database import get_db, db_manager
from portal_models import PortalTool, Base, UserSession, ToolClick, Voucher
from services.marketing.metrics_service import get_social_metrics, get_ads_metrics
from dotenv import load_dotenv
from datetime import date

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

@app.get("/sales")
async def sales_dashboard_redirect(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Redirect to Sales Dashboard (shares same OAuth, so already authenticated)"""
    sales_dashboard_url = os.getenv(
        "SALES_DASHBOARD_URL",
        "https://careassist-tracker-0fcf2cecdb22.herokuapp.com"
    )
    
    return RedirectResponse(url=sales_dashboard_url, status_code=302)

@app.get("/recruitment")
async def recruitment_dashboard_redirect(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Redirect to Recruitment Dashboard"""
    recruitment_dashboard_url = os.getenv(
        "RECRUITMENT_DASHBOARD_URL",
        "https://caregiver-lead-tracker-9d0e6a8c7c20.herokuapp.com/"
    )
    
    return RedirectResponse(url=recruitment_dashboard_url, status_code=302)


@app.get("/connections", response_class=HTMLResponse)
async def connections_page(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Render the data connections management page."""
    return templates.TemplateResponse("connections.html", {
        "request": request,
        "user": current_user
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
    request: Request = None
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


@app.get("/api/marketing/ads")
async def api_marketing_ads(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    compare: Optional[str] = Query(None)
):
    """Return ads performance metrics (placeholder until APIs wired)."""
    end_default = datetime.utcnow().date()
    start_default = end_default - timedelta(days=29)
    
    start = _parse_date_param(from_date, start_default)
    end = _parse_date_param(to_date, end_default)
    
    if start > end:
        raise HTTPException(status_code=400, detail="'from' date must be before 'to' date.")
    
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


@app.get("/api/marketing/test-gbp")
async def test_gbp_connection():
    """Test GBP connection and return status."""
    from services.marketing.gbp_service import gbp_service
    import os
    
    status = {
        "service_account_configured": bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")),
        "location_ids": os.getenv("GBP_LOCATION_IDS", "").split(","),
        "service_initialized": gbp_service.service is not None,
    }
    
    if gbp_service.service:
        try:
            # Try to get location info
            locations = gbp_service.get_location_info()
            status["locations_accessible"] = len(locations)
            status["locations"] = locations
        except Exception as e:
            status["locations_accessible"] = 0
            status["error"] = str(e)
    
    return JSONResponse(status)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
from urllib.parse import urlencode
from portal_auth import oauth_manager, get_current_user, get_current_user_optional
from portal_database import get_db, db_manager
from portal_models import PortalTool, Base, UserSession, ToolClick
from dotenv import load_dotenv

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
        params["theme"] = "dark"             # Set dark theme to match dashboard
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


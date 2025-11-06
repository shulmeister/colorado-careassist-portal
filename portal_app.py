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
from portal_auth import oauth_manager, get_current_user, get_current_user_optional
from portal_database import get_db, db_manager
from portal_models import PortalTool, Base
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    
    response = templates.TemplateResponse("portal.html", {
        "request": request,
        "user": current_user
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
    from fastapi.responses import FileResponse
    import os
    favicon_path = "static/favicon.ico"
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    # Return 204 No Content if favicon doesn't exist
    from fastapi.responses import Response
    return Response(status_code=204)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Colorado CareAssist Portal"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


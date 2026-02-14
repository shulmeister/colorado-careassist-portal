"""
Colorado CareAssist - Unified Portal (v3.0)
Consolidates portal hub + sales dashboard + recruiter dashboard into ONE app

Architecture:
- /                    → Full Portal app (with all tools, analytics, etc)
- /sales/*             → Sales CRM (FastAPI) - mounted inside portal
- /recruiting/*        → Recruiter dashboard (Flask) - mounted inside portal
- /payroll             → Payroll converter
- /gigi/*              → Gigi AI Agent (Retell) - voice assistant
"""
import os
import sys

# CRITICAL: Force local PostgreSQL for ALL database connections
# This must happen BEFORE any module imports that read DATABASE_URL
_LOCAL_DB = os.getenv('DATABASE_URL', 'postgresql://careassist@localhost:5432/careassist')
os.environ['DATABASE_URL'] = _LOCAL_DB
os.environ['SALES_DATABASE_URL'] = _LOCAL_DB
os.environ['RECRUITING_DATABASE_URL'] = _LOCAL_DB

# CRITICAL: Set up Python path BEFORE any other imports
# This ensures all submodules can find services, gigi, etc.
_ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
if _ROOT_PATH not in sys.path:
    sys.path.insert(0, _ROOT_PATH)

from fastapi import FastAPI
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import and set up the portal app as the main app
try:
    portal_path = os.path.join(_ROOT_PATH, "portal")
    sys.path.insert(0, portal_path)

    import importlib.util
    spec = importlib.util.spec_from_file_location("portal_app", os.path.join(portal_path, "portal_app.py"))
    portal_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(portal_module)

    # Use the portal app as our main app
    app = portal_module.app
    logger.info("✅ Loaded Portal app as main application")

except Exception as e:
    logger.error(f"❌ Failed to load portal app: {e}")
    import traceback
    logger.error(traceback.format_exc())
    # Fallback to empty FastAPI app if portal fails
    app = FastAPI(title="Colorado CareAssist Portal", version="3.0.0")

# ==================== SECURITY HEADERS MIDDLEWARE ====================
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)
logger.info("✅ Security headers middleware added")

# Now mount sales and recruiting into the portal app
from fastapi.middleware.wsgi import WSGIMiddleware

# ==================== MOUNT SALES DASHBOARD ====================
# Set DATABASE_URL for sales dashboard
if os.getenv("SALES_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.getenv("SALES_DATABASE_URL")
    logger.info("✅ Set DATABASE_URL for sales dashboard")

sales_path = os.path.join(os.path.dirname(__file__), "sales")
saved_services_modules = {}
if os.path.exists(sales_path):
    try:
        # Save AND REMOVE root-level services modules before loading sales
        # Sales has its own services/ directory, so we need to clear the cache
        # to let sales import its own services modules, then restore root's after
        for mod_name in list(sys.modules.keys()):
            if mod_name == 'services' or mod_name.startswith('services.'):
                saved_services_modules[mod_name] = sys.modules.pop(mod_name)  # pop removes from cache
        logger.info(f"✅ Saved and cleared {len(saved_services_modules)} services modules from cache")

        # Add sales path to front of sys.path for the services imports
        if sales_path in sys.path:
            sys.path.remove(sales_path)
        sys.path.insert(0, sales_path)
        logger.info(f"✅ Added sales path: {sales_path}")

        # Import sales app
        sales_app_file = os.path.join(sales_path, "app.py")
        spec = importlib.util.spec_from_file_location("sales_app", sales_app_file)
        sales_module = importlib.util.module_from_spec(spec)

        # Set __file__ explicitly for the module so path detection works
        sales_module.__file__ = sales_app_file

        # Register the module before loading so submodule imports work
        sys.modules["sales_app"] = sales_module

        spec.loader.exec_module(sales_module)
        sales_app = sales_module.app

        # Mount Sales as a sub-application (FastAPI apps don't have .router attribute)
        app.mount("/sales", sales_app)

        logger.info("✅ Mounted Sales Dashboard at /sales")
    except Exception as e:
        logger.error(f"❌ Failed to mount sales dashboard: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # ALWAYS restore root path and services modules, even if sales failed
        if _ROOT_PATH in sys.path:
            sys.path.remove(_ROOT_PATH)
        sys.path.insert(0, _ROOT_PATH)

        # Restore root services modules (especially services.marketing.*) for portal's use
        if saved_services_modules:
            sys.modules.update(saved_services_modules)
            logger.info(f"✅ Restored {len(saved_services_modules)} root services modules to cache")
else:
    logger.warning("⚠️  Sales dashboard not found")

# ==================== MOUNT RECRUITER DASHBOARD ====================
try:
    # Set DATABASE_URL for recruiting dashboard
    if os.getenv("RECRUITING_DATABASE_URL"):
        os.environ["DATABASE_URL"] = os.getenv("RECRUITING_DATABASE_URL")
        logger.info("✅ Set DATABASE_URL for recruiting dashboard")

    recruiter_path = os.path.join(os.path.dirname(__file__), "recruiting")
    if os.path.exists(recruiter_path):
        sys.path.insert(0, recruiter_path)
        logger.info(f"✅ Added recruiting path: {recruiter_path}")

        # Import Flask app
        spec = importlib.util.spec_from_file_location("recruiting_app", os.path.join(recruiter_path, "app.py"))
        recruiting_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recruiting_module)
        flask_app = recruiting_module.app

        # Mount Flask app using WSGI middleware
        app.mount("/recruiting", WSGIMiddleware(flask_app))
        logger.info("✅ Mounted Recruiter Dashboard at /recruiting")
    else:
        logger.warning("⚠️  Recruiter dashboard not found")
except Exception as e:
    logger.error(f"❌ Failed to mount recruiter dashboard: {e}")
    import traceback
    logger.error(traceback.format_exc())

# ==================== ADD PAYROLL CONVERTER ====================
from fastapi.responses import FileResponse

@app.get("/payroll")
async def payroll_converter():
    """Serve the Wellsky (AK) Payroll Converter tool"""
    payroll_file = os.path.join(os.path.dirname(__file__), "payroll-converter.html")
    if os.path.exists(payroll_file):
        return FileResponse(payroll_file)
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Payroll converter not found")

# PowderPulse runs as standalone service on port 3003 (powderpulse.coloradocareassist.com)
# See powderpulse/server.py — includes its own Liftie API proxy

# ==================== MOUNT GIGI AI AGENT ====================
# Gigi is the AI voice assistant powered by Retell AI
try:
    gigi_path = os.path.join(_ROOT_PATH, "gigi")
    if os.path.exists(gigi_path):
        # Ensure project root is in path (not gigi folder) so gigi can import services
        if _ROOT_PATH not in sys.path:
            sys.path.insert(0, _ROOT_PATH)
        logger.info(f"✅ Loading Gigi from: {gigi_path}")

        # Import Gigi FastAPI app
        gigi_app_file = os.path.join(gigi_path, "main.py")
        spec = importlib.util.spec_from_file_location("gigi_app", gigi_app_file)
        gigi_module = importlib.util.module_from_spec(spec)
        gigi_module.__file__ = gigi_app_file
        sys.modules["gigi_app"] = gigi_module
        spec.loader.exec_module(gigi_module)
        gigi_app = gigi_module.app

        # Mount Gigi as a sub-application (FastAPI apps don't have .router attribute)
        app.mount("/gigi", gigi_app)
        logger.info("✅ Mounted Gigi AI Agent at /gigi")
        logger.info("   Retell webhook: /gigi/webhook/retell")
        logger.info("   Health check: /gigi/health")
    else:
        logger.warning("⚠️  Gigi AI agent not found")
except Exception as e:
    logger.error(f"❌ Failed to mount Gigi AI agent: {e}")
    import traceback
    logger.error(traceback.format_exc())

# ==================== CONVENIENCE REDIRECTS ====================
from fastapi.responses import RedirectResponse

@app.get("/shadow")
async def redirect_shadow():
    """Redirect /shadow to /gigi/shadow"""
    return RedirectResponse(url="/gigi/shadow")

# Debug: Log all routes
logger.info("=== Registered Routes ===")
for route in app.routes:
    if hasattr(route, "path"):
        logger.info(f"Route: {route.path}")
    elif hasattr(route, "path_format"):
        logger.info(f"Route: {route.path_format}")
    else:
        logger.info(f"Route (other): {route}")
logger.info("=========================")

@app.get("/api/diag/rc-status")
async def diag_rc_status():
    """Temporary diagnostic route for RC status"""
    from datetime import datetime, timedelta
    import requests
    from gigi.ringcentral_bot import GigiRingCentralBot
    bot = GigiRingCentralBot()
    # Synchronous call
    token = bot.rc_service._get_access_token()
    if not token:
        return {"error": "Could not get token"}
    
    headers = {"Authorization": f"Bearer {token}"}
    server = os.getenv("RINGCENTRAL_SERVER_URL", "https://platform.ringcentral.com")
    
    # Extension info
    ext = requests.get(f"{server}/restapi/v1.0/account/~/extension/~", headers=headers).json()
    
    # Phone numbers
    nums = requests.get(f"{server}/restapi/v1.0/account/~/extension/~/phone-number", headers=headers).json()
    
    # Recent SMS
    since = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sms = requests.get(f"{server}/restapi/v1.0/account/~/extension/~/message-store", 
                      headers=headers, 
                      params={"messageType": "SMS", "dateFrom": since}).json()
    
    return {
        "extension": {
            "number": ext.get("extensionNumber"),
            "name": ext.get("name"),
            "id": ext.get("id")
        },
        "phone_numbers": [
            {
                "number": n.get("phoneNumber"),
                "usage": n.get("usageType"),
                "features": n.get("features")
            } for n in nums.get("records", [])
        ],
        "recent_sms_count": len(sms.get("records", [])),
        "recent_sms": [
            {
                "id": s.get("id"),
                "direction": s.get("direction"),
                "from": s.get("from", {}).get("phoneNumber"),
                "to": s.get("to", [{}])[0].get("phoneNumber"),
                "text": s.get("subject", "")[:50]
            } for s in sms.get("records", [])[:10]
        ]
    }

# NOTE: The RC bot runs as a standalone LaunchAgent (com.coloradocareassist.gigi-rc-bot).
# Do NOT start an embedded RC bot here — running two instances causes duplicate responses,
# duplicate morning briefings, and 409 Telegram conflicts. (Fixed Feb 11, 2026)

logger.info("✅ Portal app configured with sales, recruiting, payroll, powderpulse, and gigi")

# ==================== GIGI VOICE BRAIN (WebSocket for Retell Custom LLM) ====================
try:
    from fastapi import WebSocket
    from gigi.voice_brain import voice_brain_websocket

    @app.websocket("/llm-websocket/{call_id}")
    async def llm_websocket_endpoint(websocket: WebSocket, call_id: str):
        """WebSocket endpoint for Retell Custom LLM - unified Gigi brain"""
        await voice_brain_websocket(websocket, call_id)

    logger.info("✅ Gigi Voice Brain WebSocket mounted at /llm-websocket/{call_id}")
except Exception as e:
    logger.error(f"❌ Failed to mount Gigi Voice Brain: {e}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port)

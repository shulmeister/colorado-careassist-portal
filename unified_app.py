"""
Colorado CareAssist - Portal (v4.0)
Portal only. Sales, Recruiting, and Gigi run as independent services.

Architecture:
- /                    → Full Portal app (with all tools, analytics, etc)
- /payroll             → Payroll converter
- /gigi/dashboard/*    → Gigi admin dashboard (portal auth, reads Gigi DB)
- /api/gigi/*          → Gigi admin API (portal auth)

Independent services (own ports, own LaunchAgents):
- gigi_app.py          → Gigi AI (8767/8768)
- sales_app.py         → Sales CRM (8769/8770)
- recruiting_app.py    → Recruiting (8771/8772)

Cloudflare path-based routing handles the split transparently.
"""
import os
import sys

# CRITICAL: Force local PostgreSQL before any module imports
_LOCAL_DB = os.getenv('DATABASE_URL', 'postgresql://careassist@localhost:5432/careassist')
os.environ['DATABASE_URL'] = _LOCAL_DB

# CRITICAL: Set up Python path BEFORE any other imports
# This ensures all submodules can find services, gigi, etc.
_ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
if _ROOT_PATH not in sys.path:
    sys.path.insert(0, _ROOT_PATH)

# GlitchTip error tracking
import sentry_sdk

_GLITCHTIP_DSNS = {
    "staging": "https://37c62d8eda734aeda7049112ab33229d@glitchtip.coloradocareassist.com/2",
    "production": "https://dd14b02adf014f13988b2053dfd91d20@glitchtip.coloradocareassist.com/1",
}
_ENV = "staging" if os.getenv("STAGING") else "production"
sentry_sdk.init(dsn=_GLITCHTIP_DSNS[_ENV], traces_sample_rate=0.1, environment=_ENV)

import logging

from fastapi import FastAPI

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

# NOTE: Sales and Recruiting now run as independent services:
# - sales_app.py on port 8769 (prod) / 8770 (staging)
# - recruiting_app.py on port 8771 (prod) / 8772 (staging)
# Cloudflare path-based routing handles /sales/* and /recruiting/* transparently.

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
from fastapi.responses import RedirectResponse as _RedirectResponse


@app.get("/powderpulse")
@app.get("/powderpulse/{path:path}")
async def redirect_powderpulse(path: str = ""):
    """Redirect old /powderpulse URLs to standalone subdomain."""
    return _RedirectResponse(url="https://powderpulse.coloradocareassist.com", status_code=302)

# NOTE: Gigi AI now runs as a standalone service (gigi_app.py) on port 8767.
# Cloudflare path-based routing sends /gigi/* and /llm-websocket/* to port 8767.
# Portal's /gigi/dashboard/* and /api/gigi/* routes stay here (registered in portal_app.py).

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

logger.info("✅ Portal app configured (sales + recruiting run as independent services)")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port)

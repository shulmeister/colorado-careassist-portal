"""
Sales Dashboard — Standalone Service
Runs independently from the portal on its own port.

Routes:
- /sales/*  → All Sales CRM routes (deals, contacts, companies, analytics)
- /health   → Service health check
"""
import os
import sys

# Force local PostgreSQL before any imports
_LOCAL_DB = os.getenv('DATABASE_URL', 'postgresql://careassist@localhost:5432/careassist')
os.environ['DATABASE_URL'] = _LOCAL_DB
os.environ['SALES_DATABASE_URL'] = _LOCAL_DB

# Set up Python path so sales can import root services (wellsky, etc.)
_ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
if _ROOT_PATH not in sys.path:
    sys.path.insert(0, _ROOT_PATH)

# GlitchTip error tracking
import sentry_sdk

_GLITCHTIP_DSNS = {
    "staging": "https://8bd3aa017e064238a0613f2e94452bb6@glitchtip.coloradocareassist.com/6",
    "production": "https://d711a88a64564398a2bbe14abba08edb@glitchtip.coloradocareassist.com/5",
}
_ENV = "staging" if os.getenv("STAGING") else "production"
sentry_sdk.init(dsn=_GLITCHTIP_DSNS[_ENV], traces_sample_rate=0.1, environment=_ENV)

import logging

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== APP ====================
app = FastAPI(title="Sales Dashboard", version="1.0.0")

# ==================== SECURITY HEADERS ====================
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

# ==================== MOUNT SALES ====================
try:
    import importlib.util

    sales_path = os.path.join(_ROOT_PATH, "sales")
    if sales_path not in sys.path:
        sys.path.insert(0, sales_path)

    sales_app_file = os.path.join(sales_path, "app.py")
    spec = importlib.util.spec_from_file_location("sales_app_module", sales_app_file)
    sales_module = importlib.util.module_from_spec(spec)
    sales_module.__file__ = sales_app_file
    sys.modules["sales_app_module"] = sales_module
    spec.loader.exec_module(sales_module)
    sales_sub_app = sales_module.app

    app.mount("/sales", sales_sub_app)
    logger.info("Mounted Sales Dashboard at /sales")
except Exception as e:
    logger.error(f"Failed to mount Sales Dashboard: {e}")
    import traceback
    logger.error(traceback.format_exc())

# ==================== CONVENIENCE ====================
@app.get("/health")
async def health():
    return {"status": "ok", "service": "sales-dashboard"}

logger.info("Sales Dashboard standalone service ready")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8769))
    uvicorn.run(app, host="127.0.0.1", port=port)

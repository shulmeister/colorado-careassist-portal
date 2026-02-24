"""
Recruiting Dashboard — Standalone Service
Runs independently from the portal on its own port.

Routes:
- /recruiting/*  → All Recruiting routes (Flask via WSGI middleware)
- /health        → Service health check
"""
import os
import sys

# Force local PostgreSQL before any imports
_LOCAL_DB = os.getenv('DATABASE_URL', 'postgresql://careassist@localhost:5432/careassist')
os.environ['DATABASE_URL'] = _LOCAL_DB
os.environ['RECRUITING_DATABASE_URL'] = _LOCAL_DB

# Set up Python path so recruiting can import root services (wellsky, etc.)
_ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
if _ROOT_PATH not in sys.path:
    sys.path.insert(0, _ROOT_PATH)

# GlitchTip error tracking
import sentry_sdk

_GLITCHTIP_DSNS = {
    "staging": "https://26476d2016194221a2b8b955d23c3eb0@glitchtip.coloradocareassist.com/8",
    "production": "https://c28afe19f1444473b6fb2cae1803db30@glitchtip.coloradocareassist.com/7",
}
_ENV = "staging" if os.getenv("STAGING") else "production"
sentry_sdk.init(dsn=_GLITCHTIP_DSNS[_ENV], traces_sample_rate=0.1, environment=_ENV)

import logging

from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== APP ====================
app = FastAPI(title="Recruiting Dashboard", version="1.0.0")

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

# ==================== MOUNT RECRUITING ====================
try:
    import importlib.util

    recruiter_path = os.path.join(_ROOT_PATH, "recruiting")
    if recruiter_path not in sys.path:
        sys.path.insert(0, recruiter_path)

    spec = importlib.util.spec_from_file_location(
        "recruiting_app_module", os.path.join(recruiter_path, "app.py")
    )
    recruiting_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recruiting_module)
    flask_app = recruiting_module.app

    app.mount("/recruiting", WSGIMiddleware(flask_app))
    logger.info("Mounted Recruiting Dashboard at /recruiting")
except Exception as e:
    logger.error(f"Failed to mount Recruiting Dashboard: {e}")
    import traceback
    logger.error(traceback.format_exc())

# ==================== CONVENIENCE ====================
@app.get("/health")
async def health():
    return {"status": "ok", "service": "recruiting-dashboard"}

logger.info("Recruiting Dashboard standalone service ready")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8771))
    uvicorn.run(app, host="127.0.0.1", port=port)

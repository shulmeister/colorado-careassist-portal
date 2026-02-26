"""
Gigi AI — Standalone Service
Runs independently from the portal on its own port.

Routes:
- /gigi/*              → All Gigi routes (webhooks, API, shadow, health)
- /llm-websocket/{id}  → Retell voice brain WebSocket
"""
import os
import sys

# Force local PostgreSQL before any imports
_LOCAL_DB = os.getenv('DATABASE_URL', 'postgresql://careassist@localhost:5432/careassist')
os.environ['DATABASE_URL'] = _LOCAL_DB

# Set up Python path so gigi can import services, etc.
_ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
if _ROOT_PATH not in sys.path:
    sys.path.insert(0, _ROOT_PATH)

# GlitchTip error tracking
import sentry_sdk

_GLITCHTIP_DSNS = {
    "staging": "https://96ddd9f19326418d93ee050f5002cca8@glitchtip.coloradocareassist.com/4",
    "production": "https://7dae58e430164ba2810f99f6e329d1f2@glitchtip.coloradocareassist.com/3",
}
_ENV = "staging" if os.getenv("STAGING") else "production"
sentry_sdk.init(dsn=_GLITCHTIP_DSNS[_ENV], traces_sample_rate=0.1, environment=_ENV)

import logging

from fastapi import FastAPI, Header, HTTPException, WebSocket
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== APP ====================
app = FastAPI(title="Gigi AI Service", version="1.0.0")

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

# ==================== MOUNT GIGI ====================
try:
    import importlib.util
    gigi_app_file = os.path.join(_ROOT_PATH, "gigi", "main.py")
    spec = importlib.util.spec_from_file_location("gigi_main", gigi_app_file)
    gigi_module = importlib.util.module_from_spec(spec)
    gigi_module.__file__ = gigi_app_file
    sys.modules["gigi_main"] = gigi_module
    spec.loader.exec_module(gigi_module)
    gigi_sub_app = gigi_module.app

    app.mount("/gigi", gigi_sub_app)
    logger.info("Mounted Gigi at /gigi")
except Exception as e:
    logger.error(f"Failed to mount Gigi: {e}")
    import traceback
    logger.error(traceback.format_exc())

# ==================== VOICE BRAIN WEBSOCKET ====================
try:
    from gigi.voice_brain import voice_brain_websocket

    @app.websocket("/llm-websocket/{call_id}")
    async def llm_websocket_endpoint(websocket: WebSocket, call_id: str):
        """Retell Custom LLM WebSocket"""
        await voice_brain_websocket(websocket, call_id)

    logger.info("Voice Brain WebSocket at /llm-websocket/{call_id}")
except Exception as e:
    logger.error(f"Failed to mount Voice Brain: {e}")

# ==================== CONVENIENCE ====================
from fastapi.responses import RedirectResponse


@app.get("/shadow")
async def redirect_shadow():
    return RedirectResponse(url="/gigi/shadow")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "gigi"}

# ==================== RC DIAGNOSTIC ====================
@app.get("/api/diag/rc-status")
async def diag_rc_status(authorization: str = Header(None)):
    """RC status diagnostic (requires Bearer token)"""
    _gigi_token = os.getenv("GIGI_API_TOKEN", "")
    if not _gigi_token:
        raise HTTPException(status_code=503, detail="GIGI_API_TOKEN not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    if authorization[7:] != _gigi_token:
        raise HTTPException(status_code=403, detail="Invalid API token")
    from datetime import datetime, timedelta

    import httpx
    from services.ringcentral_messaging_service import ringcentral_messaging_service
    token = ringcentral_messaging_service._get_access_token()
    if not token:
        return {"error": "Could not get token"}

    headers = {"Authorization": f"Bearer {token}"}
    server = os.getenv("RINGCENTRAL_SERVER_URL", "https://platform.ringcentral.com")

    since = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    async with httpx.AsyncClient() as client:
        ext_resp = await client.get(f"{server}/restapi/v1.0/account/~/extension/~", headers=headers)
        ext = ext_resp.json()
        nums_resp = await client.get(f"{server}/restapi/v1.0/account/~/extension/~/phone-number", headers=headers)
        nums = nums_resp.json()
        sms_resp = await client.get(
            f"{server}/restapi/v1.0/account/~/extension/~/message-store",
            headers=headers,
            params={"messageType": "SMS", "dateFrom": since},
        )
        sms = sms_resp.json()

    return {
        "extension": {"number": ext.get("extensionNumber"), "name": ext.get("name"), "id": ext.get("id")},
        "phone_numbers": [
            {"number": n.get("phoneNumber"), "usage": n.get("usageType"), "features": n.get("features")}
            for n in nums.get("records", [])
        ],
        "recent_sms_count": len(sms.get("records", [])),
        "recent_sms": [
            {"id": s.get("id"), "direction": s.get("direction"),
             "from": s.get("from", {}).get("phoneNumber"),
             "to": s.get("to", [{}])[0].get("phoneNumber"),
             "text": s.get("subject", "")[:50]}
            for s in sms.get("records", [])[:10]
        ]
    }

logger.info("Gigi standalone service ready")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8767))
    uvicorn.run(app, host="127.0.0.1", port=port)

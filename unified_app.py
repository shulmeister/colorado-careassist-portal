"""
Colorado CareAssist - Unified Portal (v3.0)
Consolidates portal hub + sales dashboard + recruiter dashboard into ONE app

Architecture:
- /                    → Full Portal app (with all tools, analytics, etc)
- /sales/*             → Sales CRM (FastAPI) - mounted inside portal
- /recruiting/*        → Recruiter dashboard (Flask) - mounted inside portal
- /payroll             → Payroll converter
- /gigi/*              → Gigi AI Agent (Retell) - voice assistant
- /powderpulse/*       → PowderPulse ski weather app
"""
import os
import sys
from fastapi import FastAPI
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import and set up the portal app as the main app
try:
    # Ensure root path is in sys.path first so portal can import root-level services
    root_path = os.path.dirname(__file__)
    if root_path not in sys.path:
        sys.path.insert(0, root_path)

    portal_path = os.path.join(os.path.dirname(__file__), "portal")
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

# Now mount sales and recruiting into the portal app
from fastapi.middleware.wsgi import WSGIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# ==================== MOUNT SALES DASHBOARD ====================
try:
    # Set DATABASE_URL for sales dashboard
    if os.getenv("SALES_DATABASE_URL"):
        os.environ["DATABASE_URL"] = os.getenv("SALES_DATABASE_URL")
        logger.info("✅ Set DATABASE_URL for sales dashboard")

    sales_path = os.path.join(os.path.dirname(__file__), "sales")
    if os.path.exists(sales_path):
        # Save AND REMOVE root-level services modules before loading sales
        # Sales has its own services/ directory, so we need to clear the cache
        # to let sales import its own services modules, then restore root's after
        saved_services_modules = {}
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

        # Restore root path to front of sys.path so portal's services.marketing imports work
        if root_path in sys.path:
            sys.path.remove(root_path)
        sys.path.insert(0, root_path)

        # Restore root services modules (especially services.marketing.*) for portal's use
        # This overwrites sales' services in sys.modules, but sales already has references to its modules
        sys.modules.update(saved_services_modules)
        logger.info(f"✅ Restored {len(saved_services_modules)} root services modules to cache")
    else:
        logger.warning("⚠️  Sales dashboard not found")
except Exception as e:
    logger.error(f"❌ Failed to mount sales dashboard: {e}")
    import traceback
    logger.error(traceback.format_exc())

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

# ==================== MOUNT POWDERPULSE SKI WEATHER ====================
try:
    from fastapi.staticfiles import StaticFiles

    powderpulse_dist = os.path.join(os.path.dirname(__file__), "powderpulse", "dist")
    if os.path.exists(powderpulse_dist):
        # Serve static assets (js, css, etc)
        app.mount("/powderpulse/assets", StaticFiles(directory=os.path.join(powderpulse_dist, "assets")), name="powderpulse-assets")

        # Serve index.html for the main route and any SPA routes
        @app.get("/powderpulse")
        @app.get("/powderpulse/{path:path}")
        async def serve_powderpulse(path: str = ""):
            index_file = os.path.join(powderpulse_dist, "index.html")
            if os.path.exists(index_file):
                return FileResponse(index_file)
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="PowderPulse not built. Run: cd powderpulse && npm run build")

        logger.info("✅ Mounted PowderPulse at /powderpulse")
    else:
        logger.warning("⚠️  PowderPulse dist not found - run 'cd powderpulse && npm run build'")
except Exception as e:
    logger.error(f"❌ Failed to mount PowderPulse: {e}")

# ==================== LIFTIE API PROXY FOR POWDERPULSE ====================
# Liftie API doesn't support CORS, so we proxy requests through our backend
try:
    import httpx

    @app.get("/api/liftie/{resort_id}")
    async def proxy_liftie(resort_id: str):
        """Proxy requests to Liftie API to bypass CORS"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://liftie.info/api/resort/{resort_id}",
                    timeout=10.0
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": f"Liftie API returned {response.status_code}"}
        except Exception as e:
            logger.error(f"Liftie proxy error for {resort_id}: {e}")
            return {"error": str(e)}

    logger.info("✅ Added Liftie API proxy at /api/liftie/{resort_id}")
except Exception as e:
    logger.error(f"❌ Failed to set up Liftie proxy: {e}")

# ==================== MOUNT GIGI AI AGENT ====================
# Gigi is the AI voice assistant powered by Retell AI
try:
    gigi_path = os.path.join(os.path.dirname(__file__), "gigi")
    if os.path.exists(gigi_path):
        sys.path.insert(0, gigi_path)
        logger.info(f"✅ Added gigi path: {gigi_path}")

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

@app.on_event("startup")
async def start_gigi_bot_from_unified():
    """Ensure Gigi's background bot starts when the unified app starts"""
    try:
        import os
        import asyncio
        
        logger.info("🚀 Starting Gigi RingCentral Bot (via Unified App Startup)")
                bot = GigiRingCentralBot()
                await bot.initialize()
                
                async def run_bot_loop():
                    await asyncio.sleep(15) # Wait for app to stabilize
                    logger.info("🤖 Gigi RC Bot loop starting (Unified)...")
                    while True:
                        try:
                            await bot.check_and_act()
                        except Exception as e:
                            logger.error(f"Unified RC Bot Loop Error: {e}")
                        await asyncio.sleep(60) # Standardize on 60s
                
                asyncio.create_task(run_bot_loop())
    except Exception as e:
        logger.error(f"❌ Failed to start Gigi Bot from Unified: {e}")

logger.info("✅ Portal app configured with sales, recruiting, payroll, powderpulse, and gigi")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

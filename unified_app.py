"""
Colorado CareAssist - Unified Portal (v3.0)
Consolidates portal hub + sales dashboard + recruiter dashboard into ONE app

Architecture:
- /                    → Full Portal app (with all tools, analytics, etc)
- /sales/*             → Sales CRM (FastAPI) - mounted inside portal
- /recruiting/*        → Recruiter dashboard (Flask) - mounted inside portal
- /payroll             → Payroll converter
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
        # Add sales path to front of sys.path for the services imports
        if sales_path in sys.path:
            sys.path.remove(sales_path)
        sys.path.insert(0, sales_path)
        logger.info(f"✅ Added sales path: {sales_path}")

        # Pre-import services modules before loading sales app
        # This ensures they're in sys.modules when the import statements run
        try:
            import services.activity_service
            import services.ai_enrichment_service
            import services.auth_service
            logger.info("✅ Pre-imported sales services modules")
        except ImportError as e:
            logger.warning(f"⚠️  Could not pre-import services: {e}")

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

        # Create middleware to rewrite redirect URLs
        class PrefixRedirectMiddleware(BaseHTTPMiddleware):
            """Middleware to add /sales prefix to relative redirects"""
            async def dispatch(self, request, call_next):
                response = await call_next(request)
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location", "")
                    if location.startswith("/") and not location.startswith("/sales"):
                        response.headers["location"] = f"/sales{location}"
                        logger.info(f"🔄 Rewrote redirect: {location} -> /sales{location}")
                return response

        sales_app.add_middleware(PrefixRedirectMiddleware)
        app.mount("/sales", sales_app)
        logger.info("✅ Mounted Sales Dashboard at /sales")
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

logger.info("✅ Portal app configured with sales, recruiting, payroll, and powderpulse")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

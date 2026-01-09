"""
Colorado CareAssist - Unified Portal (v3.0)
Consolidates portal hub + sales dashboard + recruiter dashboard into ONE app

Architecture:
- /                    → Portal homepage (dashboard selector)
- /sales/*             → Sales CRM (FastAPI)
- /recruiting/*        → Recruiter dashboard (Flask)
- /auth/*              → Unified Google OAuth
"""
import os
import sys
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.wsgi import WSGIMiddleware
from starlette.routing import Mount
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize main FastAPI app
app = FastAPI(
    title="Colorado CareAssist Portal",
    description="Unified portal with sales CRM and recruiter dashboard",
    version="3.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files from portal
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("✅ Mounted portal static files")

# ==================== MOUNT SALES DASHBOARD ====================
try:
    # Set DATABASE_URL for sales dashboard (from SALES_DATABASE_URL)
    if os.getenv("SALES_DATABASE_URL"):
        os.environ["DATABASE_URL"] = os.getenv("SALES_DATABASE_URL")
        logger.info("✅ Set DATABASE_URL for sales dashboard")

    # Add sales dashboard to path
    sales_path = os.path.join(os.path.dirname(__file__), "sales")
    if os.path.exists(sales_path):
        sys.path.insert(0, sales_path)
        logger.info(f"✅ Added sales path: {sales_path}")

        # Import sales app
        import importlib.util
        spec = importlib.util.spec_from_file_location("sales_app", os.path.join(sales_path, "app.py"))
        sales_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sales_module)
        sales_app = sales_module.app

        # Mount sales dashboard at /sales
        app.mount("/sales", sales_app)
        logger.info("✅ Mounted Sales Dashboard at /sales")
    else:
        logger.warning("⚠️  Sales dashboard not found at " + sales_path)
except Exception as e:
    logger.error(f"❌ Failed to mount sales dashboard: {e}")
    import traceback
    logger.error(traceback.format_exc())

# ==================== MOUNT RECRUITER DASHBOARD ====================
try:
    # Set DATABASE_URL for recruiting dashboard (from RECRUITING_DATABASE_URL)
    if os.getenv("RECRUITING_DATABASE_URL"):
        os.environ["DATABASE_URL"] = os.getenv("RECRUITING_DATABASE_URL")
        logger.info("✅ Set DATABASE_URL for recruiting dashboard")

    # Add recruiter dashboard to path
    recruiter_path = os.path.join(os.path.dirname(__file__), "recruiting")
    if os.path.exists(recruiter_path):
        sys.path.insert(0, recruiter_path)
        logger.info(f"✅ Added recruiting path: {recruiter_path}")

        # Import Flask app
        import importlib.util
        spec = importlib.util.spec_from_file_location("recruiting_app", os.path.join(recruiter_path, "app.py"))
        recruiting_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recruiting_module)
        flask_app = recruiting_module.app

        # Mount Flask app using WSGI middleware
        app.mount("/recruiting", WSGIMiddleware(flask_app))
        logger.info("✅ Mounted Recruiter Dashboard at /recruiting")
    else:
        logger.warning("⚠️  Recruiter dashboard not found at " + recruiter_path)
except Exception as e:
    logger.error(f"❌ Failed to mount recruiter dashboard: {e}")
    import traceback
    logger.error(traceback.format_exc())

# ==================== PORTAL HOMEPAGE ====================
@app.get("/", response_class=HTMLResponse)
async def portal_home(request: Request):
    """Portal homepage with dashboard selector"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Colorado CareAssist Portal</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container { max-width: 1200px; width: 100%; }
            .header {
                text-align: center;
                color: white;
                margin-bottom: 60px;
            }
            .header h1 {
                font-size: 3rem;
                font-weight: 700;
                margin-bottom: 10px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
            }
            .header p { font-size: 1.2rem; opacity: 0.9; }
            .dashboard-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 30px;
                margin-bottom: 40px;
            }
            .dashboard-card {
                background: white;
                border-radius: 20px;
                padding: 40px 30px;
                text-align: center;
                transition: transform 0.3s ease, box-shadow 0.3s ease;
                cursor: pointer;
                text-decoration: none;
                color: inherit;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }
            .dashboard-card:hover {
                transform: translateY(-10px);
                box-shadow: 0 20px 40px rgba(0,0,0,0.2);
            }
            .dashboard-card .icon { font-size: 4rem; margin-bottom: 20px; }
            .dashboard-card h2 {
                font-size: 1.8rem;
                margin-bottom: 15px;
                color: #333;
            }
            .dashboard-card p {
                color: #666;
                line-height: 1.6;
                margin-bottom: 20px;
            }
            .dashboard-card .btn {
                display: inline-block;
                padding: 12px 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-radius: 25px;
                text-decoration: none;
                font-weight: 600;
                transition: opacity 0.3s ease;
            }
            .dashboard-card .btn:hover { opacity: 0.9; }
            .sales-card { border-top: 4px solid #667eea; }
            .recruiting-card { border-top: 4px solid #f093fb; }
            .footer {
                text-align: center;
                color: white;
                opacity: 0.8;
                margin-top: 40px;
            }
            @media (max-width: 768px) {
                .header h1 { font-size: 2rem; }
                .dashboard-grid { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏥 Colorado CareAssist</h1>
                <p>Select Your Dashboard</p>
            </div>

            <div class="dashboard-grid">
                <a href="/sales" class="dashboard-card sales-card">
                    <div class="icon">📊</div>
                    <h2>Sales Dashboard</h2>
                    <p>Manage contacts, companies, deals, and track sales performance. Full CRM with Brevo integration.</p>
                    <span class="btn">Open Sales CRM</span>
                </a>

                <a href="/recruiting" class="dashboard-card recruiting-card">
                    <div class="icon">👥</div>
                    <h2>Recruiter Dashboard</h2>
                    <p>Track caregiver leads from Facebook, manage applications, and monitor recruiting pipeline.</p>
                    <span class="btn">Open Recruiting</span>
                </a>
            </div>

            <div class="footer">
                <p>Colorado CareAssist Portal v3.0 • Unified Edition • Cost Optimized</p>
                <p style="font-size: 0.9rem; margin-top: 10px;">Saves $228/year vs 3-app architecture</p>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "version": "3.0.0",
        "services": {
            "sales": "mounted at /sales",
            "recruiting": "mounted at /recruiting"
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

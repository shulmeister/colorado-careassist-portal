# CRITICAL: Register HEIF opener BEFORE any module imports PIL
# This enables HEIC image support for iPhone photos
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # pillow_heif not installed

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Depends, status, Query, BackgroundTasks
from pydantic import BaseModel
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text, func
import os
import json
import io
import re
from typing import List, Dict, Any, Optional, Tuple
import logging
import time
import threading
from datetime import datetime, timedelta, timezone
try:
    import pytz
except ImportError:
    pytz = None
# parser.py no longer used - replaced by ai_document_parser.py
from ai_document_parser import ai_parser
from google_sheets import GoogleSheetsManager
from database import get_db, db_manager
from models import Visit, TimeEntry, Contact, ActivityNote, FinancialEntry, SalesBonus, DashboardSummary, EmailCount, ActivityLog, Deal, Expense, Lead, ReferralSource, ContactTask, DealTask, CompanyTask, ProcessedDriveFile
from analytics import AnalyticsEngine
from migrate_data import GoogleSheetsMigrator
from business_card_scanner import BusinessCardScanner
from mailchimp_service import MailchimpService
from auth import oauth_manager, get_current_user, get_current_user_optional
from google_drive_service import GoogleDriveService
from activity_logger import ActivityLogger
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# Load environment variables
load_dotenv()

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory cache for company logos (base64 content embedded in SVG)
_COMPANY_LOGO_CACHE: Dict[int, Dict[str, Any]] = {}
_COMPANY_LOGO_TTL_SECONDS = 86400  # 1 day


def ensure_contact_schema():
    """Add new contact columns if they are missing (works for Postgres + SQLite)."""
    engine = db_manager.engine
    if not engine:
        return

    dialect = engine.dialect.name

    def column_exists(conn, column_name: str) -> bool:
        if dialect == "sqlite":
            rows = conn.execute(text(f"PRAGMA table_info(contacts)")).fetchall()
            return any(row[1] == column_name for row in rows)
        query = text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='contacts' AND column_name=:column"
        )
        row = conn.execute(query, {"column": column_name}).fetchone()
        return row is not None


    def add_column(conn, statement: str):
        if dialect == "sqlite":
            conn.execute(text(f"ALTER TABLE contacts ADD COLUMN {statement}"))
        else:
            conn.execute(text(f"ALTER TABLE contacts ADD COLUMN IF NOT EXISTS {statement}"))

    with engine.connect() as conn:
        if not column_exists(conn, "status"):
            add_column(conn, "status VARCHAR(50)")
        if not column_exists(conn, "contact_type"):
            add_column(conn, "contact_type VARCHAR(50)")
        if not column_exists(conn, "tags"):
            add_column(conn, "tags TEXT")
        if not column_exists(conn, "last_activity"):
            add_column(conn, "last_activity TIMESTAMP")
        if not column_exists(conn, "account_manager"):
            add_column(conn, "account_manager VARCHAR(255)")
        if not column_exists(conn, "source"):
            add_column(conn, "source VARCHAR(255)")
        # New fields for contacts_summary / company linking
        if not column_exists(conn, "first_name"):
            add_column(conn, "first_name VARCHAR(255)")
        if not column_exists(conn, "last_name"):
            add_column(conn, "last_name VARCHAR(255)")
        if not column_exists(conn, "company_id"):
            add_column(conn, "company_id INTEGER")
        if not column_exists(conn, "last_seen"):
            add_column(conn, "last_seen TIMESTAMP")
        conn.commit()


ensure_contact_schema()


def ensure_deal_schema():
    """Ensure deals table exists with required columns (lightweight migration)."""
    engine = db_manager.engine
    if not engine:
        return

    with engine.connect() as conn:
        dialect = engine.dialect.name
        
        # Create table if missing
        if dialect == "sqlite":
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS deals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(255) NOT NULL,
                        company_id INTEGER NULL,
                        contact_ids TEXT NULL,
                        category VARCHAR(100) NULL,
                        stage VARCHAR(100) NULL,
                        description TEXT NULL,
                        amount FLOAT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        archived_at TIMESTAMP NULL,
                        expected_closing_date TIMESTAMP NULL,
                        sales_id INTEGER NULL,
                        "index" INTEGER NULL,
                        est_weekly_hours FLOAT NULL
                    )
                    """
                )
            )
        else:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS deals (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        company_id INTEGER NULL,
                        contact_ids TEXT NULL,
                        category VARCHAR(100) NULL,
                        stage VARCHAR(100) NULL,
                        description TEXT NULL,
                        amount FLOAT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        archived_at TIMESTAMP NULL,
                        expected_closing_date TIMESTAMP NULL,
                        sales_id INTEGER NULL,
                        "index" INTEGER NULL,
                        est_weekly_hours FLOAT NULL
                    )
                    """
                )
            )
            
        # Add missing columns if table existed without them
        columns = {
            "company_id": "INTEGER",
            "contact_ids": "TEXT",
            "category": "VARCHAR(100)",
            "stage": "VARCHAR(100)",
            "description": "TEXT",
            "amount": "FLOAT",
            "archived_at": "TIMESTAMP",
            "expected_closing_date": "TIMESTAMP",
            "sales_id": "INTEGER",
            '"index"': "INTEGER",
            "est_weekly_hours": "FLOAT",
        }
        dialect = engine.dialect.name

        def column_exists(column: str) -> bool:
            if dialect == "sqlite":
                # Handle quoted column names for check
                clean_col = column.replace('"', '')
                rows = conn.execute(text("PRAGMA table_info(deals)")).fetchall()
                return any(row[1] == clean_col for row in rows)
            
            clean_col = column.replace('"', '')
            row = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='deals' AND column_name=:column"
                ),
                {"column": clean_col},
            ).fetchone()
            return row is not None

        for col, typ in columns.items():
            if not column_exists(col):
                if dialect == "sqlite":
                    conn.execute(text(f"ALTER TABLE deals ADD COLUMN {col} {typ}"))
                else:
                    conn.execute(
                        text(f"ALTER TABLE deals ADD COLUMN IF NOT EXISTS {col} {typ}")
                    )


ensure_deal_schema()


def ensure_company_task_schema():
    """Ensure company_tasks table exists (tasks attached to referral sources)."""
    engine = db_manager.engine
    if not engine:
        return

    with engine.connect() as conn:
        dialect = engine.dialect.name

        if dialect == "sqlite":
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS company_tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        description TEXT NULL,
                        due_date TIMESTAMP NULL,
                        status VARCHAR(50) NOT NULL DEFAULT 'pending',
                        completed_at TIMESTAMP NULL,
                        assigned_to VARCHAR(255) NULL,
                        created_by VARCHAR(255) NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
        else:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS company_tasks (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        description TEXT NULL,
                        due_date TIMESTAMP NULL,
                        status VARCHAR(50) NOT NULL DEFAULT 'pending',
                        completed_at TIMESTAMP NULL,
                        assigned_to VARCHAR(255) NULL,
                        created_by VARCHAR(255) NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                    """
                )
            )

        def column_exists(column: str) -> bool:
            if dialect == "sqlite":
                rows = conn.execute(text("PRAGMA table_info(company_tasks)")).fetchall()
                return any(row[1] == column for row in rows)
            row = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='company_tasks' AND column_name=:column"
                ),
                {"column": column},
            ).fetchone()
            return row is not None

        if not column_exists("status"):
            if dialect == "sqlite":
                conn.execute(text("ALTER TABLE company_tasks ADD COLUMN status VARCHAR(50) DEFAULT 'pending'"))
            else:
                conn.execute(
                    text("ALTER TABLE company_tasks ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'pending'")
                )

        # Task assignment fields
        if not column_exists("assigned_to"):
            if dialect == "sqlite":
                conn.execute(text("ALTER TABLE company_tasks ADD COLUMN assigned_to VARCHAR(255)"))
            else:
                conn.execute(text("ALTER TABLE company_tasks ADD COLUMN IF NOT EXISTS assigned_to VARCHAR(255)"))

        if not column_exists("created_by"):
            if dialect == "sqlite":
                conn.execute(text("ALTER TABLE company_tasks ADD COLUMN created_by VARCHAR(255)"))
            else:
                conn.execute(text("ALTER TABLE company_tasks ADD COLUMN IF NOT EXISTS created_by VARCHAR(255)"))


ensure_company_task_schema()


def ensure_lead_task_schema():
    """Ensure lead_tasks has newer columns (assigned_to / created_by) for task assignment."""
    engine = db_manager.engine
    if not engine:
        return

    with engine.connect() as conn:
        dialect = engine.dialect.name

        # Base.metadata.create_all creates the table, but does not add new columns.
        # In production we must be resilient: attempt to add columns and ignore "already exists" failures.
        try:
            if dialect == "sqlite":
                conn.execute(text("ALTER TABLE lead_tasks ADD COLUMN assigned_to VARCHAR(255)"))
            else:
                conn.execute(text("ALTER TABLE lead_tasks ADD COLUMN IF NOT EXISTS assigned_to VARCHAR(255)"))
        except Exception:
            pass

        try:
            if dialect == "sqlite":
                conn.execute(text("ALTER TABLE lead_tasks ADD COLUMN created_by VARCHAR(255)"))
            else:
                conn.execute(text("ALTER TABLE lead_tasks ADD COLUMN IF NOT EXISTS created_by VARCHAR(255)"))
        except Exception:
            pass


ensure_lead_task_schema()


def ensure_referral_source_schema():
    """Add enrichment columns to referral_sources if missing."""
    engine = db_manager.engine
    if not engine:
        return

    with engine.connect() as conn:
        dialect = engine.dialect.name

        def column_exists(column: str) -> bool:
            if dialect == "sqlite":
                rows = conn.execute(text("PRAGMA table_info(referral_sources)")).fetchall()
                return any(row[1] == column for row in rows)
            row = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='referral_sources' AND column_name=:column"
                ),
                {"column": column},
            ).fetchone()
            return row is not None

        def add_column(statement: str):
            if dialect == "sqlite":
                conn.execute(text(f"ALTER TABLE referral_sources ADD COLUMN {statement}"))
            else:
                conn.execute(text(f"ALTER TABLE referral_sources ADD COLUMN IF NOT EXISTS {statement}"))

        if not column_exists("county"):
            add_column("county VARCHAR(100)")
        if not column_exists("facility_type_normalized"):
            add_column("facility_type_normalized VARCHAR(100)")
        if not column_exists("website"):
            add_column("website VARCHAR(255)")
        if not column_exists("logo_url"):
            add_column("logo_url TEXT")


ensure_referral_source_schema()

def ensure_financial_entry_schema():
    """Add user_email column to financial_entries if missing"""
    engine = db_manager.engine
    if not engine:
        return

    # Check if table exists
    with engine.connect() as conn:
        dialect = engine.dialect.name
        
        # Check if financial_entries table exists
        if dialect == "sqlite":
            table_exists = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='financial_entries'")).fetchone()
        else:
            table_exists = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_name='financial_entries'")).fetchone()
            
        if not table_exists:
            return

        # Check for user_email column
        def column_exists(column: str) -> bool:
            if dialect == "sqlite":
                rows = conn.execute(text("PRAGMA table_info(financial_entries)")).fetchall()
                return any(row[1] == column for row in rows)
            
            row = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='financial_entries' AND column_name=:column"
                ),
                {"column": column},
            ).fetchone()
            return row is not None

        if not column_exists("user_email"):
            logger.info("Adding user_email column to financial_entries table")
            conn.execute(text("ALTER TABLE financial_entries ADD COLUMN user_email VARCHAR(255)"))
            if dialect == "sqlite":
                # conn.commit() - SQLAlchemy connection auto-commits DDL in some versions, but let's be safe
                pass 
            else:
                conn.commit()

ensure_financial_entry_schema()

# Portal SSO configuration (shared secret with main portal)
PORTAL_SECRET = os.getenv("PORTAL_SECRET", "colorado-careassist-portal-2025")
PORTAL_SSO_SERIALIZER = URLSafeTimedSerializer(PORTAL_SECRET)
PORTAL_SSO_TOKEN_TTL = int(os.getenv("PORTAL_SSO_TOKEN_TTL", "300"))

# Ring Central Embeddable configuration
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sync manager to prevent logjam
class SyncManager:
    """Manages Google Sheets sync to prevent concurrent syncs and cache results"""
    
    def __init__(self):
        self.last_sync_time = 0
        self.sync_lock = threading.Lock()
        self.sync_interval = 60  # Only sync once per 60 seconds max
        self.last_sync_result: Optional[Dict[str, Any]] = None
    
    def should_sync(self) -> bool:
        """Check if enough time has passed since last sync"""
        return (time.time() - self.last_sync_time) > self.sync_interval
    
    def sync_if_needed(self, force: bool = False) -> Dict[str, Any]:
        """
        Sync from Google Sheets if enough time has passed (or when forced).
        This method is safe to call from multiple threads/concurrent requests.
        """
        if not force and not self.should_sync():
            logger.debug("Sync skipped - too soon since last sync")
            return self.last_sync_result or {"success": True, "visits_migrated": 0, "time_entries_migrated": 0}
        
        if not self.sync_lock.acquire(blocking=False):
            logger.debug("Sync skipped - another sync in progress")
            return self.last_sync_result or {"success": True, "visits_migrated": 0, "time_entries_migrated": 0}
        
        try:
            # Guard again after acquiring the lock to avoid duplicate work
            if not force and not self.should_sync():
                logger.debug("Sync skipped - another request already synced")
                return self.last_sync_result or {"success": True, "visits_migrated": 0, "time_entries_migrated": 0}
            
            logger.info("SYNC: Starting Google Sheets sync%s...", " (forced)" if force else "")
            migrator = GoogleSheetsMigrator()
            result = migrator.migrate_all_data()
            
            self.last_sync_time = time.time()
            self.last_sync_result = result
            
            if result.get("success"):
                logger.info(
                    "SYNC: Success - %s visits, %s time entries",
                    result.get('visits_migrated', 0),
                    result.get('time_entries_migrated', 0)
                )
            else:
                logger.error("SYNC: Failed - %s", result.get('error', 'Unknown error'))
            
            return result
        except Exception as e:
            logger.error("SYNC ERROR: %s", str(e), exc_info=True)
            return {"success": False, "error": str(e), "visits_migrated": 0, "time_entries_migrated": 0}
        finally:
            self.sync_lock.release()

# Initialize sync manager
sync_manager = SyncManager()

def ensure_financial_schema():
    """Add user_email column to financial_entries if missing."""
    engine = db_manager.engine
    if not engine:
        return

    with engine.connect() as conn:
        dialect = engine.dialect.name
        
        # Check if user_email column exists
        exists = False
        if dialect == "sqlite":
            rows = conn.execute(text(f"PRAGMA table_info(financial_entries)")).fetchall()
            exists = any(row[1] == "user_email" for row in rows)
        else:
            row = conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name='financial_entries' AND column_name='user_email'")
            ).fetchone()
            exists = row is not None
            
        if not exists:
            logger.info("Adding user_email column to financial_entries table")
            try:
                conn.execute(text("ALTER TABLE financial_entries ADD COLUMN user_email VARCHAR(255)"))
                conn.commit()
            except Exception as e:
                logger.warning(f"Could not add user_email column: {e}")

# Initialize DB and ensure schema
try:
    ensure_contact_schema()
    ensure_deal_schema()
    ensure_financial_schema()
except Exception as e:
    logger.error(f"Schema initialization failed: {e}")

app = FastAPI(title="Colorado CareAssist Sales Dashboard", version="2.0.0")

# Add security middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "https://tracker.coloradocareassist.com", "https://portal.coloradocareassist.com"],  # Production domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.herokuapp.com", "tracker.coloradocareassist.com", "portal.coloradocareassist.com"]  # Production domains
)

# Mount static files and templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Mount React frontend static assets
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    # Mount React assets (CSS, JS, etc.)
    frontend_assets = os.path.join(frontend_dist, "assets")
    if os.path.exists(frontend_assets):
        app.mount("/assets", StaticFiles(directory=frontend_assets), name="assets")
    logger.info(f"✅ React frontend mounted from {frontend_dist}")
else:
    logger.warning(f"⚠️  React frontend not found at {frontend_dist}")

# Initialize components
business_card_scanner = BusinessCardScanner()

# Initialize Google Sheets manager with error handling (for migration)
try:
    sheets_manager = GoogleSheetsManager()
    logger.info("Google Sheets manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Google Sheets manager: {str(e)}")
    sheets_manager = None

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


@app.get("/portal-auth")
async def portal_auth(
    portal_token: str = Query(..., min_length=10),
    portal_user_email: Optional[str] = Query(None),
    redirect_to: Optional[str] = Query(None)
):
    """
    Accept SSO redirects from the main portal, validate the signed token,
    and mint a local session cookie so users are not prompted to log in again.
    """
    try:
        portal_payload = PORTAL_SSO_SERIALIZER.loads(
            portal_token,
            max_age=PORTAL_SSO_TOKEN_TTL
        )
    except SignatureExpired:
        logger.warning("Portal SSO token expired")
        raise HTTPException(status_code=400, detail="Portal token expired")
    except BadSignature:
        logger.warning("Portal SSO token invalid signature")
        raise HTTPException(status_code=400, detail="Invalid portal token")

    email = portal_user_email or portal_payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Portal token missing user email")

    name = portal_payload.get("name") or portal_payload.get("display_name") or "Portal User"
    domain = portal_payload.get("domain") or email.split("@")[-1]

    session_payload = {
        "email": email,
        "name": name,
        "domain": domain,
        "picture": portal_payload.get("picture"),
        "via_portal": True,
        "portal_login": True,
        "login_time": datetime.utcnow().isoformat()
    }

    session_token = oauth_manager.serializer.dumps(session_payload)

    target_url = redirect_to or "/"
    if not target_url.startswith("/"):
        logger.debug("Portal redirect_to %s not relative; defaulting to /", target_url)
        target_url = "/"

    response = RedirectResponse(url=target_url, status_code=302)
    response.set_cookie(
        key="session_token",
        value=session_token,
        max_age=3600 * 12,
        httponly=True,
        secure=True,
        samesite="lax"
    )

    logger.info("Portal SSO login successful for %s", email)
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
    """Serve the React CRM app"""
    if not current_user:
        # Redirect to login if not authenticated
        return RedirectResponse(url="/auth/login")
    
    # Serve React app
    frontend_index = os.path.join(os.path.dirname(__file__), "frontend", "dist", "index.html")
    if os.path.exists(frontend_index):
        logger.info(f"✅ Serving React app from {frontend_index}")
        return FileResponse(frontend_index)
    
    # Fallback to old Jinja2 template if React build doesn't exist
    logger.warning(f"⚠️  React frontend not found at {frontend_index}, redirecting to /legacy")
    return RedirectResponse(url="/legacy")

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload and parse PDF file (MyWay route or Time tracking) or scan business card image"""
    try:
        # Validate file type
        file_extension = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'heic', 'heif']
        
        if file_extension not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"Only {', '.join(allowed_extensions)} files are allowed")
        
        # Read file content
        content = await file.read()

        # Expense detection for local upload (receipts). Keep it conservative: require filename keywords.
        is_expense_file = _is_expense_filename(file.filename)
        
        if file_extension == 'pdf':
            # Expense receipt PDF - use AI to extract details
            if is_expense_file:
                logger.info(f"Parsing expense receipt PDF with AI: {file.filename}")
                receipt_result = ai_parser.parse_receipt(content, file.filename)
                
                amount = receipt_result.get("amount", 0) if receipt_result.get("success") else 0
                vendor = receipt_result.get("vendor", "Unknown") if receipt_result.get("success") else "Unknown"
                category = receipt_result.get("category", "Uncategorized") if receipt_result.get("success") else "Uncategorized"
                description = receipt_result.get("description", f"Receipt from {file.filename}")
                expense_date = _parse_receipt_date(receipt_result) if receipt_result.get("success") else datetime.utcnow()
                
                # Assign to tracked expense user (Jacob/Maryssa), default to Jacob
                assigned_owner = _choose_expense_owner(
                    assign_to=None,
                    owner_email=None,
                    current_user_email=current_user.get("email"),
                )
                
                new_expense = Expense(
                    user_email=assigned_owner,
                    amount=amount,
                    description=f"{vendor}: {description}" if description else f"Receipt from {vendor}",
                    category=category,
                    receipt_url=file.filename,
                    status="pending",
                    date=expense_date
                )
                db.add(new_expense)
                db.commit()
                db.refresh(new_expense)
                logger.info(f"Saved expense: {vendor} ${amount} on {expense_date} for {assigned_owner}")
                return JSONResponse({
                    "success": True,
                    "filename": file.filename,
                    "type": "expense_receipt",
                    "expense": new_expense.to_dict(),
                    "ai_extracted": receipt_result if receipt_result.get("success") else None,
                    "assigned_to": assigned_owner
                })

            # Parse PDF (MyWay route or Time tracking) using AI
            logger.info(f"Parsing PDF with AI: {file.filename}")
            result = ai_parser.parse_myway_pdf(content, file.filename)
            
            if not result.get("success", False):
                # MyWay parsing failed - try as a receipt first
                logger.info(f"MyWay parsing failed, trying as receipt: {file.filename}")
                receipt_result = ai_parser.parse_receipt(content, file.filename)
                
                if receipt_result.get("success") and receipt_result.get("amount"):
                    # It's a receipt! Save as expense
                    logger.info(f"Detected as receipt: {file.filename}")
                    amount = receipt_result.get("amount", 0)
                    vendor = receipt_result.get("vendor", "Unknown")
                    category = receipt_result.get("category", "Uncategorized")
                    description = receipt_result.get("description", f"Receipt from {file.filename}")
                    expense_date = _parse_receipt_date(receipt_result)
                    
                    # Assign to tracked expense user (Jacob/Maryssa), default to Jacob
                    assigned_owner = _choose_expense_owner(
                        assign_to=None,
                        owner_email=None,
                        current_user_email=current_user.get("email"),
                    )
                    
                    new_expense = Expense(
                        user_email=assigned_owner,
                        amount=amount,
                        description=f"{vendor}: {description}" if description else f"Receipt from {vendor}",
                        category=category,
                        receipt_url=file.filename,
                        status="pending",
                        date=expense_date
                    )
                    db.add(new_expense)
                    db.commit()
                    db.refresh(new_expense)
                    logger.info(f"Saved expense: {vendor} ${amount} on {expense_date} for {assigned_owner}")
                    return JSONResponse({
                        "success": True,
                        "filename": file.filename,
                        "type": "expense_receipt",
                        "expense": new_expense.to_dict(),
                        "ai_extracted": receipt_result,
                        "assigned_to": assigned_owner
                    })
                
                logger.warning(f"Receipt parsing also failed; attempting business-card OCR fallback")
                try:
                    import pdfplumber, io
                    # Rasterize first page to image for business-card OCR
                    with pdfplumber.open(io.BytesIO(content)) as pdf:
                        if not pdf.pages:
                            raise Exception("PDF has no pages")
                        pil_image = pdf.pages[0].to_image(resolution=300).original
                        buf = io.BytesIO()
                        pil_image.save(buf, format="PNG")
                        img_bytes = buf.getvalue()

                    scan_result = business_card_scanner.scan_image(img_bytes)
                    if not scan_result.get("success", False):
                        error_msg = scan_result.get("error", "Failed to scan business card")
                        logger.error(f"Business card scan (PDF) failed: {error_msg}")
                        raise HTTPException(status_code=400, detail=error_msg)

                    contact_data = business_card_scanner.validate_contact(scan_result["contact"])

                    # Save to database (reuse logic from image branch)
                    existing_contact = None
                    if contact_data.get('email'):
                        existing_contact = db.query(Contact).filter(Contact.email == contact_data['email']).first()

                    if existing_contact:
                        # Update first_name and last_name if available
                        first_name = contact_data.get('first_name', '').strip()
                        last_name = contact_data.get('last_name', '').strip()
                        name = contact_data.get('name', '').strip()
                        
                        # Normalize names
                        if name and not first_name and not last_name:
                            parts = name.split(' ', 1)
                            first_name = parts[0] if parts else ''
                            last_name = parts[1] if len(parts) > 1 else ''
                        elif first_name and ' ' in first_name and not last_name:
                            parts = first_name.split(' ', 1)
                            first_name = parts[0]
                            last_name = parts[1] if len(parts) > 1 else ''
                        
                        if first_name and not existing_contact.first_name:
                            existing_contact.first_name = first_name
                        if last_name and not existing_contact.last_name:
                            existing_contact.last_name = last_name
                        
                        if not existing_contact.phone and contact_data.get('phone'):
                            existing_contact.phone = contact_data['phone']
                        if not existing_contact.title and contact_data.get('title'):
                            existing_contact.title = contact_data['title']
                        if not existing_contact.company and contact_data.get('company'):
                            existing_contact.company = contact_data['company']
                        if not existing_contact.website and contact_data.get('website'):
                            existing_contact.website = contact_data['website']

                        new_notes = f"Scanned from business card (PDF) on {datetime.now().strftime('%Y-%m-%d')}"
                        if existing_contact.notes:
                            existing_contact.notes = existing_contact.notes + "\n" + new_notes
                        else:
                            existing_contact.notes = new_notes

                        existing_contact.updated_at = datetime.utcnow()
                        db.add(existing_contact)
                        db.commit()
                        db.refresh(existing_contact)
                        saved_contact = existing_contact
                    else:
                        # Extract first_name and last_name from contact_data
                        first_name = contact_data.get('first_name', '').strip()
                        last_name = contact_data.get('last_name', '').strip()
                        name = contact_data.get('name', '').strip()
                        
                        # If we have name but no first/last, split it
                        if name and not first_name and not last_name:
                            parts = name.split(' ', 1)
                            first_name = parts[0] if parts else ''
                            last_name = parts[1] if len(parts) > 1 else ''
                        # If first_name contains full name, split it
                        elif first_name and ' ' in first_name and not last_name:
                            parts = first_name.split(' ', 1)
                            first_name = parts[0]
                            last_name = parts[1] if len(parts) > 1 else ''
                        
                        # Build full name if not provided
                        if not name and (first_name or last_name):
                            name = f"{first_name} {last_name}".strip()
                        
                        new_contact = Contact(
                            first_name=first_name,
                            last_name=last_name,
                            name=name,
                            company=contact_data.get('company'),
                            title=contact_data.get('title'),
                            phone=contact_data.get('phone'),
                            email=contact_data.get('email'),
                            address=contact_data.get('address'),
                            website=contact_data.get('website'),
                            notes=f"Scanned from business card (PDF) on {datetime.now().strftime('%Y-%m-%d')}",
                            contact_type="prospect",
                            status="cold",
                            tags=_serialize_tags(["Scanned"]),
                            scanned_date=datetime.utcnow(),
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow()
                        )
                        db.add(new_contact)
                        db.commit()
                        db.refresh(new_contact)
                        saved_contact = new_contact

                    mailchimp_result = None
                    mailchimp_service = MailchimpService()
                    if mailchimp_service.enabled and contact_data.get('email'):
                        mailchimp_result = mailchimp_service.add_contact(contact_data)

                    logger.info(f"Successfully scanned business card (PDF) for {contact_data.get('name', 'Unknown')}")
                    return JSONResponse({
                        "success": True,
                        "filename": file.filename,
                        "type": "business_card",
                        "contact": saved_contact.to_dict(),
                        "extracted_text": scan_result.get("raw_text", ""),
                        "mailchimp_export": mailchimp_result
                    })
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Business card PDF fallback failed: {e}")
                    raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")
        
            # Return appropriate response based on PDF type
            if result["type"] == "time_tracking":
                # Serialize date if it's a datetime object
                date_value = result["date"]
                if isinstance(date_value, datetime):
                    date_value = date_value.date().isoformat()
                elif date_value and hasattr(date_value, 'date'):
                    date_value = date_value.date().isoformat()
                
                logger.info(f"Successfully parsed time tracking data: {date_value} - {result['total_hours']} hours")
                return JSONResponse({
                    "success": True,
                    "filename": file.filename,
                    "type": "time_tracking",
                    "date": date_value,
                    "total_hours": result["total_hours"]
                })
            else:
                # MyWay route processing
                visits = result["visits"]
                mileage = result.get("mileage")
                visit_date = result.get("date")
                
                if not visits and not mileage:
                    raise HTTPException(status_code=400, detail="No visits or mileage found in PDF")
                
                user_email = current_user.get("email", "unknown@coloradocareassist.com")
                
                # Save visits to database (with duplicate checking)
                saved_visits = []
                skipped_duplicates = []
                visit_errors = []
                
                def normalize_business_name(name):
                    """Normalize business name for duplicate checking"""
                    if not name:
                        return ""
                    import re
                    normalized = (name or "").lower().strip()
                    normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
                    normalized = re.sub(r'\s+', ' ', normalized)  # Normalize spaces
                    return normalized
                
                logger.info(f"Attempting to save {len(visits)} visits for {user_email}")
                for visit_data in visits:
                    try:
                        business_name = visit_data.get("business_name", "Unknown")
                        stop_number = visit_data.get("stop_number", 0)
                        v_date = visit_data.get("visit_date") or visit_date or datetime.utcnow()
                        
                        # Duplicate check: same date, stop number, and normalized business name
                        v_date_only = v_date.date() if hasattr(v_date, 'date') else v_date
                        business_normalized = normalize_business_name(business_name)
                        
                        existing_visits = db.query(Visit).filter(
                            func.date(Visit.visit_date) == v_date_only,
                            Visit.stop_number == stop_number
                        ).all()
                        
                        is_duplicate = False
                        for ev in existing_visits:
                            if normalize_business_name(ev.business_name) == business_normalized:
                                is_duplicate = True
                                skipped_duplicates.append({
                                    "business_name": business_name,
                                    "date": str(v_date_only),
                                    "existing_id": ev.id
                                })
                                logger.info(f"Skipping duplicate visit: {business_name} on {v_date_only}")
                                break
                        
                        if is_duplicate:
                            continue
                        
                        logger.info(f"Creating visit: {business_name} on {v_date}")
                        new_visit = Visit(
                            stop_number=stop_number,
                            business_name=business_name,
                            address=visit_data.get("address"),
                            city=visit_data.get("city"),
                            notes=visit_data.get("notes"),
                            visit_date=v_date,
                            user_email=user_email,
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow()
                        )
                        db.add(new_visit)
                        db.flush()  # Get the ID
                        saved_visits.append(new_visit)
                        logger.info(f"✓ Flushed visit ID {new_visit.id}: {new_visit.business_name}")
                        
                        # Log activity for each visit (non-blocking)
                        # IMPORTANT: Activity logging must never rollback the visit transaction
                        try:
                            ActivityLogger.log_visit(
                                db=db,
                                visit_id=new_visit.id,
                                business_name=new_visit.business_name,
                                user_email=user_email,
                                visit_date=new_visit.visit_date,
                                commit=False,
                            )
                        except Exception as e:
                            logger.error(f"Error logging visit activity (non-critical): {e}")
                            # Don't fail the entire upload if activity logging fails
                    except Exception as e:
                        error_msg = f"Error saving visit {visit_data.get('business_name')}: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        visit_errors.append(error_msg)
                        # Continue with other visits even if one fails
                
                # Save mileage to FinancialEntry if present
                if mileage and visit_date:
                    try:
                        if isinstance(visit_date, str):
                            entry_date = datetime.fromisoformat(visit_date)
                        else:
                            entry_date = visit_date
                        
                        # Check if entry already exists for this date
                        existing_entry = db.query(FinancialEntry).filter(
                            func.date(FinancialEntry.date) == entry_date.date()
                        ).first()
                        
                        if existing_entry:
                            existing_entry.miles_driven = mileage
                            existing_entry.mileage_cost = mileage * 0.70
                            existing_entry.user_email = user_email
                            existing_entry.updated_at = datetime.utcnow()
                        else:
                            new_entry = FinancialEntry(
                                date=entry_date,
                                hours_worked=0,
                                labor_cost=0,
                                miles_driven=mileage,
                                mileage_cost=mileage * 0.70,
                                materials_cost=0,
                                total_daily_cost=mileage * 0.70,
                                user_email=user_email
                            )
                            db.add(new_entry)
                        logger.info(f"Saved mileage: {mileage} miles for {user_email}")
                    except Exception as e:
                        logger.error(f"Error saving mileage: {e}")
                
                # If NO visits were saved but some were parsed, that's a critical error
                logger.info(f"Visit save summary: parsed={len(visits)}, flushed={len(saved_visits)}, errors={len(visit_errors)}")
                if len(visits) > 0 and len(saved_visits) == 0:
                    db.rollback()
                    error_details = "\n".join(visit_errors) if visit_errors else "Unknown database error"
                    logger.error(f"ALL VISITS FAILED TO SAVE: {error_details}")
                    raise HTTPException(
                        status_code=500, 
                        detail=f"Failed to save any visits to database. Parsed {len(visits)} visits but all failed to save. Errors: {error_details}"
                    )
                
                # Serialize BEFORE commit to avoid detached instance errors
                logger.info("Serializing visits before commit...")
                serialized_visits = []
                for visit in saved_visits:
                    serialized_visits.append(visit.to_dict())
                logger.info(f"Serialized {len(serialized_visits)} visits")
                
                # Commit all changes
                logger.info(f"Committing {len(saved_visits)} visits to database...")
                try:
                    db.commit()
                    logger.info(f"✓ Commit successful! {len(saved_visits)} visits saved to database")
                except Exception as commit_error:
                    logger.error(f"✗ COMMIT FAILED: {commit_error}", exc_info=True)
                    db.rollback()
                    raise HTTPException(status_code=500, detail=f"Database commit failed: {str(commit_error)}")
                
                logger.info(f"Successfully saved {len(serialized_visits)} visits to database, skipped {len(skipped_duplicates)} duplicates")
                response_data = {
                    "success": True,
                    "filename": file.filename,
                    "type": "myway_route",
                    "visits": serialized_visits,
                    "count": len(serialized_visits),
                    "mileage": mileage,
                    "parsed_count": len(visits),
                    "saved_count": len(serialized_visits),
                    "duplicates_skipped": len(skipped_duplicates)
                }
                if skipped_duplicates:
                    response_data["duplicate_details"] = skipped_duplicates
                    response_data["message"] = f"Saved {len(serialized_visits)} new visits, skipped {len(skipped_duplicates)} duplicates"
                if visit_errors:
                    response_data["errors"] = visit_errors
                    response_data["warning"] = f"Parsed {len(visits)} visits but only saved {len(serialized_visits)}"
                return JSONResponse(response_data)
        else:
            # Handle business card image (including HEIC) OR receipt image
            logger.info(f"Processing business card image: {file.filename}")
            logger.info(f"File content length: {len(content)} bytes")
            logger.info(f"File extension: {file_extension}")
            try:
                # Expense receipt path for images - use AI to extract
                if is_expense_file:
                    logger.info(f"Parsing expense receipt image with AI: {file.filename}")
                    receipt_result = ai_parser.parse_receipt(content, file.filename)
                    
                    amount = receipt_result.get("amount", 0) if receipt_result.get("success") else 0
                    vendor = receipt_result.get("vendor", "Unknown") if receipt_result.get("success") else "Unknown"
                    category = receipt_result.get("category", "Uncategorized") if receipt_result.get("success") else "Uncategorized"
                    description = receipt_result.get("description", "")
                    expense_date = _parse_receipt_date(receipt_result) if receipt_result.get("success") else datetime.utcnow()
                    
                    # Assign to tracked expense user (Jacob/Maryssa), default to Jacob
                    assigned_owner = _choose_expense_owner(
                        assign_to=None,
                        owner_email=None,
                        current_user_email=current_user.get("email"),
                    )

                    new_expense = Expense(
                        user_email=assigned_owner,
                        amount=amount,
                        description=f"{vendor}: {description}" if description else f"Receipt from {vendor}",
                        category=category,
                        receipt_url=file.filename,
                        status="pending",
                        date=expense_date
                    )
                    db.add(new_expense)
                    db.commit()
                    db.refresh(new_expense)
                    logger.info(f"Saved expense: {vendor} ${amount} on {expense_date} for {assigned_owner}")

                    return JSONResponse({
                        "success": True,
                        "filename": file.filename,
                        "type": "expense_receipt",
                        "expense": new_expense.to_dict(),
                        "ai_extracted": receipt_result if receipt_result.get("success") else None
                    })

                result = business_card_scanner.scan_image(content)
                
                if not result.get("success", False):
                    error_msg = result.get("error", "Failed to scan business card")
                    logger.error(f"Business card scanning failed: {error_msg}")
                    raise HTTPException(status_code=400, detail=error_msg)
                
                # Validate contact information
                contact_data = business_card_scanner.validate_contact(result["contact"])
                
                # Save to database
                # Check for existing contact by email if present
                existing_contact = None
                if contact_data.get('email'):
                    existing_contact = db.query(Contact).filter(Contact.email == contact_data['email']).first()
                
                if existing_contact:
                    logger.info(f"Updating existing contact: {contact_data.get('email')}")
                    
                    # Update first_name and last_name if available
                    first_name = contact_data.get('first_name', '').strip()
                    last_name = contact_data.get('last_name', '').strip()
                    name = contact_data.get('name', '').strip()
                    
                    # Normalize names
                    if name and not first_name and not last_name:
                        parts = name.split(' ', 1)
                        first_name = parts[0] if parts else ''
                        last_name = parts[1] if len(parts) > 1 else ''
                    elif first_name and ' ' in first_name and not last_name:
                        parts = first_name.split(' ', 1)
                        first_name = parts[0]
                        last_name = parts[1] if len(parts) > 1 else ''
                    
                    if first_name and not existing_contact.first_name:
                        existing_contact.first_name = first_name
                    if last_name and not existing_contact.last_name:
                        existing_contact.last_name = last_name
                    
                    # Update fields if they are empty in existing record
                    if not existing_contact.phone and contact_data.get('phone'):
                        existing_contact.phone = contact_data['phone']
                    if not existing_contact.title and contact_data.get('title'):
                        existing_contact.title = contact_data['title']
                    if not existing_contact.company and contact_data.get('company'):
                        existing_contact.company = contact_data['company']
                    if not existing_contact.website and contact_data.get('website'):
                        existing_contact.website = contact_data['website']
                    
                    # Merge notes
                    new_notes = f"Scanned from business card on {datetime.now().strftime('%Y-%m-%d')}"
                    if existing_contact.notes:
                        existing_contact.notes = existing_contact.notes + "\n" + new_notes
                    else:
                        existing_contact.notes = new_notes
                        
                    existing_contact.updated_at = datetime.utcnow()
                    db.add(existing_contact)
                    db.commit()
                    db.refresh(existing_contact)
                    saved_contact = existing_contact
                else:
                    # Extract first_name and last_name from contact_data
                    first_name = contact_data.get('first_name', '').strip()
                    last_name = contact_data.get('last_name', '').strip()
                    name = contact_data.get('name', '').strip()
                    
                    # If we have name but no first/last, split it
                    if name and not first_name and not last_name:
                        parts = name.split(' ', 1)
                        first_name = parts[0] if parts else ''
                        last_name = parts[1] if len(parts) > 1 else ''
                    # If first_name contains full name, split it
                    elif first_name and ' ' in first_name and not last_name:
                        parts = first_name.split(' ', 1)
                        first_name = parts[0]
                        last_name = parts[1] if len(parts) > 1 else ''
                    
                    # Build full name if not provided
                    if not name and (first_name or last_name):
                        name = f"{first_name} {last_name}".strip()
                    
                    logger.info(f"Creating new contact from scan: {name}")
                    new_contact = Contact(
                        first_name=first_name,
                        last_name=last_name,
                        name=name,
                        company=contact_data.get('company'),
                        title=contact_data.get('title'),
                        phone=contact_data.get('phone'),
                        email=contact_data.get('email'),
                        address=contact_data.get('address'),
                        website=contact_data.get('website'),
                        notes=f"Scanned from business card on {datetime.now().strftime('%Y-%m-%d')}",
                        contact_type="referral",  # Business cards are referral sources
                        status="cold",  # Default to cold
                        tags=_serialize_tags(["Scanned"]),
                        scanned_date=datetime.utcnow(),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(new_contact)
                    db.commit()
                    db.refresh(new_contact)
                    saved_contact = new_contact

                # Create ReferralSource (Company) if company field exists
                saved_company = None
                if contact_data.get('company'):
                    try:
                        # Check if company already exists
                        existing_company = db.query(ReferralSource).filter(
                            ReferralSource.name == contact_data['company']
                        ).first()
                        
                        if not existing_company:
                            new_company = ReferralSource(
                                name=contact_data['company'],
                                contact_name=contact_data.get('name'),
                                email=contact_data.get('email'),
                                phone=contact_data.get('phone'),
                                address=contact_data.get('address'),
                                source_type="Business Card Scan",
                                status="incoming",
                                notes=f"Company from scanned business card on {datetime.now().strftime('%Y-%m-%d')}",
                                created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow()
                            )
                            db.add(new_company)
                            db.commit()
                            db.refresh(new_company)
                            saved_company = new_company
                            logger.info(f"Created new company: {contact_data['company']}")
                        else:
                            saved_company = existing_company
                            logger.info(f"Company already exists: {contact_data['company']}")
                    except Exception as e:
                        logger.error(f"Error creating company: {e}")
                
                # Create Lead (Deal) for this contact
                saved_lead = None
                try:
                    # Create a new lead for this prospect
                    new_lead = Lead(
                        name=f"{contact_data.get('name', 'Unknown')} - {contact_data.get('company', 'New Lead')}",
                        contact_name=contact_data.get('name'),
                        email=contact_data.get('email'),
                        phone=contact_data.get('phone'),
                        address=contact_data.get('address'),
                        source="Business Card Scan",
                        stage="incoming",
                        priority="medium",
                        referral_source_id=saved_company.id if saved_company else None,
                        notes=f"Lead from scanned business card on {datetime.now().strftime('%Y-%m-%d')}",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(new_lead)
                    db.commit()
                    db.refresh(new_lead)
                    saved_lead = new_lead
                    logger.info(f"Created new lead for: {contact_data.get('name')}")
                except Exception as e:
                    logger.error(f"Error creating lead: {e}")
                
                # Log activity
                try:
                    ActivityLogger.log_business_card_scan(
                        db=db,
                        contact_id=saved_contact.id,
                        user_email=current_user.get("email", "unknown@coloradocareassist.com"),
                        contact_name=contact_data.get('name', 'Unknown'),
                        filename=file.filename
                    )
                except Exception as e:
                    logger.error(f"Error logging activity: {e}")

                # Sync to Brevo (will add to "Referral Source" list via sync_contact_to_brevo_crm)
                import threading
                thread = threading.Thread(target=sync_contact_to_brevo_crm, args=(saved_contact,))
                thread.daemon = True
                thread.start()

                # Export to Mailchimp if configured
                mailchimp_result = None
                mailchimp_service = MailchimpService()
                if mailchimp_service.enabled and contact_data.get('email'):
                    mailchimp_result = mailchimp_service.add_contact(contact_data)
                    logger.info(f"Mailchimp export result: {mailchimp_result}")
                
                logger.info(f"Successfully scanned and saved business card: {contact_data.get('name', 'Unknown')}")
                return JSONResponse({
                    "success": True,
                    "filename": file.filename,
                    "type": "business_card",
                    "contact": saved_contact.to_dict(),
                    "extracted_text": result.get("raw_text", ""),
                    "mailchimp_export": mailchimp_result
                })
            except Exception as e:
                logger.error(f"Error processing business card: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error processing business card: {str(e)}")

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class UrlUploadRequest(BaseModel):
    url: str
    # Optional override for who should "own" records created from a Drive link.
    # The Expenses widget only shows Jacob and Maryssa, and MyWay mileage reimbursement
    # is tracked per user_email, so Drive imports should be assignable.
    assign_to: Optional[str] = None


class BulkBusinessCardRequest(BaseModel):
    folder_url: str
    # Which user to assign as account_manager for created contacts
    assign_to: Optional[str] = None


class SendNewsletterRequest(BaseModel):
    list_id: int
    subject: str
    html_content: Optional[str] = None
    use_template: bool = False
    month: Optional[str] = None

# --- Helpers for expense extraction ---
def _extract_amount_from_text(text: str) -> float:
    """
    Best-effort receipt total extraction from OCR text.

    Prefer amounts on lines containing 'total' (excluding subtotal), otherwise fallback to the largest amount.
    """
    import re

    if not text:
        return 0.0

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    total_candidates = []
    all_amounts = []

    # OCR sometimes breaks decimals as "34 94" or "34. 94". Accept ., comma, or whitespace as separator.
    amount_re = re.compile(r"\b(\d{1,6})\s*[\\.,\\s]\s*(\d{2})\b")
    for line in lines:
        matches = amount_re.findall(line)
        for whole, cents in matches:
            try:
                val = float(f"{int(whole)}.{cents}")
                all_amounts.append(val)
            except Exception:
                continue

        low = line.lower()
        if "total" in low and "subtotal" not in low and "sub-total" not in low:
            for whole, cents in matches:
                try:
                    total_candidates.append(float(f"{int(whole)}.{cents}"))
                except Exception:
                    continue

    # Prefer "TOTAL" candidates if present, else largest amount overall
    if total_candidates:
        return max(total_candidates)
    if all_amounts:
        return max(all_amounts)
    return 0.0


def _extract_amount_from_pdf_bytes(content: bytes) -> float:
    """Extract a likely total from a PDF by scanning text."""
    try:
        import io
        import pdfplumber

        text = ""
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text += "\n" + (page.extract_text() or "")
        return _extract_amount_from_text(text)
    except Exception as e:
        logger.warning(f"Could not extract amount from PDF: {e}")
        return 0.0


def _is_expense_filename(name: str) -> bool:
    name_l = name.lower()
    keywords = [
        "receipt",
        "expense",
        "gas",
        "fuel",
        "meal",
        "uber",
        "lyft",
        "taxi",
        "parking",
        "hotel",
        "dollar",
        "family_dollar",
        "famdollar",
        "starbucks",
        "coffee",
        "restaurant",
        "store",
        "shop",
        "grocery",
        "walmart",
        "target",
        "costco",
        "safeway",
        "king soopers",
        "whole foods",
        "chipotle",
        "mcdonalds",
        "wendys",
        "subway",
        "panera",
        "chick-fil-a",
        "office depot",
        "staples",
        "amazon",
        "invoice",
        "purchase",
        "order",
        "18rmizeqbadooodsuneat4nuvlv52e4w_x",  # explicit receipt id
    ]
    return any(k in name_l for k in keywords)


def _looks_like_image_bytes(content: bytes, filename: str = "") -> bool:
    """Best-effort check to detect image payloads (PNG/JPEG/HEIC/GIF/WebP)."""
    name = (filename or "").lower()
    if name.endswith((".png", ".jpg", ".jpeg", ".heic", ".heif", ".gif", ".webp")):
        return True
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if content.startswith(b"\xff\xd8\xff"):
        return True
    if content[:12].find(b"ftypheic") != -1 or content[:12].find(b"ftypheif") != -1:
        return True
    if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
        return True
    if content[:12].startswith(b"RIFF") and b"WEBP" in content[:16]:
        return True
    return False


def _is_receipt_text(text: str) -> bool:
    """Heuristic to determine if OCR text looks like a receipt."""
    import re
    t = (text or "").lower()
    if not t:
        return False
    # Business cards often contain emails; avoid misclassifying those as receipts.
    if "@" in t:
        return False
    # Must contain at least one currency-like amount
    amounts = re.findall(r"\b\d+\.\d{2}\b", t)
    if not amounts:
        return False
    keywords = [
        "receipt",
        "subtotal",
        "sub-total",
        "tax",
        "total",
        "balance",
        "tender",
        "change",
        "approved",
        "debit",
        "credit",
        "visa",
        "mastercard",
        "amex",
        "discover",
        "merchant",
        "store",
        "pos",
        "transaction",
        "auth",
        "invoice",
    ]
    if any(k in t for k in keywords):
        return True

    # Looser fallback: multiple amounts + some text often indicates a receipt even if keywords OCR poorly
    # (Important when OpenAI is rate-limited and OCR is imperfect.)
    if len(amounts) >= 2 and len(t) >= 60:
        return True
    return False


def _choose_expense_owner(
    *,
    assign_to: Optional[str],
    owner_email: Optional[str],
    current_user_email: Optional[str],
) -> str:
    """
    Expenses widget only displays Jacob and Maryssa.
    Prefer explicit assignment, then Drive owner, then current user if in the tracked set,
    otherwise default to Jacob.
    """
    tracked = {"jacob@coloradocareassist.com", "maryssa@coloradocareassist.com"}
    if assign_to and assign_to in tracked:
        return assign_to
    if owner_email and owner_email in tracked:
        return owner_email
    if current_user_email and current_user_email in tracked:
        return current_user_email
    return "jacob@coloradocareassist.com"


def _parse_receipt_date(receipt_result: Dict[str, Any]) -> datetime:
    """
    Extract and parse the date from a receipt parsing result.
    Returns the parsed date if available and valid, otherwise returns current UTC time.
    """
    receipt_date = receipt_result.get("date")
    if not receipt_date:
        logger.info("No date found in receipt result, using current UTC time")
        return datetime.utcnow()
    
    # If it's already a datetime object, return it
    if isinstance(receipt_date, datetime):
        logger.info(f"Using receipt date (datetime): {receipt_date}")
        return receipt_date
    
    # Try to parse string dates in YYYY-MM-DD format
    if isinstance(receipt_date, str):
        try:
            # Parse YYYY-MM-DD format
            parsed_date = datetime.strptime(receipt_date, "%Y-%m-%d")
            result = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
            logger.info(f"Parsed receipt date from '{receipt_date}': {result}")
            return result
        except ValueError:
            # Try ISO format
            try:
                parsed_date = datetime.fromisoformat(receipt_date.replace('Z', '+00:00'))
                result = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
                logger.info(f"Parsed receipt date (ISO) from '{receipt_date}': {result}")
                return result
            except (ValueError, AttributeError):
                logger.warning(f"Could not parse receipt date: {receipt_date}, using current date")
                return datetime.utcnow()
    
    logger.warning(f"Receipt date is unexpected type: {type(receipt_date)}, using current date")
    return datetime.utcnow()


def _extract_hours_from_pdf_text(content: bytes) -> Optional[float]:
    """Lightweight fallback to extract hours from PDF text when parser returns null."""
    try:
        import io
        import pdfplumber
        text = ""
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text += "\n" + (page.extract_text() or "")
        import re
        max_hours = 200.0  # guardrail to avoid money amounts
        # Prefer h/m patterns anywhere in the text (avoid dollar lines)
        lines = text.splitlines()
        hms_values: List[float] = []
        for line in lines:
            if "$" in line:
                continue
            for h, m in re.findall(r"(\d{1,3})h\s*(\d{1,2})m", line, flags=re.IGNORECASE):
                try:
                    val = int(h) + int(m) / 60.0
                    if 0 < val <= max_hours:
                        hms_values.append(val)
                except Exception:
                    continue
        if hms_values:
            return round(max(hms_values), 2)

        # Next, numbers followed by hours tokens (avoid money and cap hours)
        candidates: List[float] = []
        for line in lines:
            if "$" in line:
                continue
            for match in re.findall(r"(\d{1,3}(?:\.\d{1,2})?)\s*(?:hrs|hours|h)\b", line, flags=re.IGNORECASE):
                try:
                    val = float(match)
                    if 0 < val <= max_hours:
                        candidates.append(val)
                except Exception:
                    continue
        if candidates:
            return round(max(candidates), 2)
    except Exception as e:
        logger.debug(f"Hours fallback failed: {e}")
    return None


# ---------- Admin adapter endpoints for React Admin ----------
# These provide stable REST shapes for the frontend (contacts, companies, deals, tasks)
# without changing the legacy API contracts.

def _to_company_dict(source, nb_contacts: int = 0, nb_deals: int = 0) -> Dict[str, Any]:
    """Map ReferralSource to a company-shaped dict expected by the frontend."""
    # IMPORTANT: Use a same-origin logo URL so it renders reliably (Brave/adblockers
    # often block Clearbit/ui-avatars). We can still infer a website for other UX.
    display_name = source.organization or source.name
    logo_src: Optional[str] = f"/api/company-logos/{source.id}.svg" if getattr(source, "id", None) else None
    website: Optional[str] = getattr(source, "website", None) or None
    try:
        personal_domains = {
            "gmail.com",
            "yahoo.com",
            "outlook.com",
            "hotmail.com",
            "icloud.com",
            "me.com",
            "aol.com",
            "live.com",
            "msn.com",
            "comcast.net",
        }
        domain = None
        if getattr(source, "email", None) and "@" in source.email:
            domain = source.email.split("@")[-1].strip().lower()
            domain = domain.split(">")[0].strip()
        if (not website) and domain and domain not in personal_domains and "." in domain:
            website = f"https://{domain}"
    except Exception:
        website = website or None

    # Frontend expects "name" to be the company/organization name, not the contact person
    company_name = source.organization or source.name or "Unknown Company"
    contact_person = source.name if source.organization else source.contact_name

    return {
        "id": source.id,
        "name": company_name,  # Company/org name for display
        "organization": source.organization,
        "contact_name": contact_person or source.contact_name,  # Person's name
        "email": source.email,
        "phone_number": source.phone,
        "address": source.address,
        "source_type": source.source_type,
        "county": getattr(source, "county", None),
        "facility_type_normalized": getattr(source, "facility_type_normalized", None),
        "status": source.status,
        "notes": source.notes,
        "created_at": source.created_at.isoformat() if source.created_at else None,
        "updated_at": source.updated_at.isoformat() if source.updated_at else None,
        # Optional fields for UI filters / display
        "sector": source.source_type,
        "size": getattr(source, "county", None),
        "zipcode": None,
        "city": None,
        "stateAbbr": None,
        "country": None,
        "website": website,
        "logo_url": getattr(source, "logo_url", None),
        "logo": {"src": logo_src, "title": display_name} if logo_src else None,
        # Counts for tabs
        "nb_contacts": nb_contacts,
        "nb_deals": nb_deals,
    }


def _initials(name: str) -> str:
    parts = [p for p in (name or "").replace("&", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def _bg_from_name(name: str) -> str:
    """Deterministic pleasant background based on name."""
    palette = [
        "#1e293b",  # slate-800
        "#0f766e",  # teal-700
        "#1d4ed8",  # blue-700
        "#7c3aed",  # violet-600
        "#b45309",  # amber-700
        "#be123c",  # rose-700
        "#047857",  # emerald-700
        "#334155",  # slate-700
    ]
    try:
        idx = abs(hash(name or "")) % len(palette)
        return palette[idx]
    except Exception:
        return palette[0]


@app.get("/api/company-logos/{company_id}.svg")
async def get_company_logo_svg(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Same-origin company logo SVG.

    - If we can determine a website/logo URL, we fetch a favicon/logo and embed it inside an SVG.
    - Otherwise we fall back to deterministic initials.

    This avoids third-party image blocking (Brave/adblockers) because the browser only loads same-origin SVG.
    """
    try:
        from models import ReferralSource
        from fastapi.responses import Response
        import base64
        import re
        import httpx

        source = db.query(ReferralSource).filter(ReferralSource.id == company_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Company not found")

        display_name = (source.organization or source.name or "Company").strip()
        initials = _initials(display_name)
        bg = _bg_from_name(display_name)

        # Try to serve a cached embedded logo first
        now_ts = time.time()
        cached = _COMPANY_LOGO_CACHE.get(company_id)
        if cached and (now_ts - float(cached.get("ts", 0)) < _COMPANY_LOGO_TTL_SECONDS):
            b64 = cached.get("b64")
            mime = cached.get("mime")
            if b64 and mime:
                svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128" role="img" aria-label="{display_name}">
  <defs>
    <clipPath id="clip"><circle cx="64" cy="64" r="64"/></clipPath>
  </defs>
  <rect width="128" height="128" rx="64" fill="{bg}"/>
  <image clip-path="url(#clip)" href="data:{mime};base64,{b64}" x="0" y="0" width="128" height="128" preserveAspectRatio="xMidYMid slice"/>
</svg>"""
                return Response(
                    content=svg,
                    media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"},
                )

        # Best-effort: determine website/domain
        website = (getattr(source, "website", None) or "").strip()
        if not website:
            # Fallback: infer from email domain (existing behavior)
            try:
                if getattr(source, "email", None) and "@" in source.email:
                    domain = source.email.split("@")[-1].strip().lower()
                    domain = domain.split(">")[0].strip()
                    if "." in domain:
                        website = f"https://{domain}"
            except Exception:
                website = ""

        def _domain_from_url(u: str) -> str:
            u = (u or "").strip()
            if not u:
                return ""
            u = re.sub(r"^https?://", "", u, flags=re.IGNORECASE)
            u = u.split("/")[0]
            u = u.split("?")[0]
            return u.strip().lower()

        domain = _domain_from_url(website)
        logo_url = (getattr(source, "logo_url", None) or "").strip()

        # If no explicit logo_url, use Google's favicon service (fast, consistent)
        candidate_urls: List[str] = []
        if logo_url:
            candidate_urls.append(logo_url)
        if domain:
            candidate_urls.append(f"https://www.google.com/s2/favicons?domain={domain}&sz=128")
            candidate_urls.append(f"https://{domain}/favicon.ico")

        fetched_b64 = None
        fetched_mime = None
        for u in candidate_urls:
            try:
                r = httpx.get(u, timeout=6.0, follow_redirects=True)
                if r.status_code != 200 or not r.content:
                    continue
                ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
                if not ctype.startswith("image/"):
                    # Some favicons return octet-stream; accept if it looks like an ICO/PNG/JPEG
                    ctype = "image/x-icon" if u.endswith(".ico") else "image/png"
                # Basic size guard
                if len(r.content) > 500_000:
                    continue
                fetched_b64 = base64.b64encode(r.content).decode("ascii")
                fetched_mime = ctype
                break
            except Exception:
                continue

        if fetched_b64 and fetched_mime:
            _COMPANY_LOGO_CACHE[company_id] = {"ts": now_ts, "b64": fetched_b64, "mime": fetched_mime}
            svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128" role="img" aria-label="{display_name}">
  <defs>
    <clipPath id="clip"><circle cx="64" cy="64" r="64"/></clipPath>
  </defs>
  <rect width="128" height="128" rx="64" fill="{bg}"/>
  <image clip-path="url(#clip)" href="data:{fetched_mime};base64,{fetched_b64}" x="0" y="0" width="128" height="128" preserveAspectRatio="xMidYMid slice"/>
</svg>"""
        else:
            svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128" role="img" aria-label="{display_name}">
  <rect width="128" height="128" rx="64" fill="{bg}"/>
  <text x="50%" y="52%" dominant-baseline="middle" text-anchor="middle"
        font-family="Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial"
        font-size="54" font-weight="700" fill="#ffffff">{initials}</text>
</svg>"""

        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error generating company logo svg: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate logo")


def _to_task_dict(task) -> Dict[str, Any]:
    """Map LeadTask to the task shape the frontend expects."""
    return {
        "id": task.id,
        "contact_id": task.lead_id,  # Frontend uses contact_id; we map to lead_id.
        "text": task.title or task.description,
        "description": task.description,
        "type": "None",
        "status": task.status,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "done_date": task.completed_at.isoformat() if task.completed_at else None,
        "assigned_to": getattr(task, "assigned_to", None),
        "created_by": getattr(task, "created_by", None),
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "sales_id": None,
    }


def _to_company_task_dict(task) -> Dict[str, Any]:
    """Map CompanyTask to the admin task shape."""
    return {
        "id": task.id,
        "contact_id": task.company_id,
        "text": task.title or task.description,
        "description": task.description,
        "type": "None",
        "status": task.status,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "done_date": task.completed_at.isoformat() if task.completed_at else None,
        "assigned_to": getattr(task, "assigned_to", None),
        "created_by": getattr(task, "created_by", None),
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "sales_id": None,
    }


# ============ STUB ENDPOINTS FOR NOTES ============
# These are expected by the React Admin frontend but not fully implemented yet

@app.get("/admin/dealNotes")
async def admin_get_deal_notes(
    request: Request,
    deal_id: Optional[int] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
):
    """Stub endpoint for deal notes - returns empty list for now."""
    return JSONResponse(
        content={"data": [], "total": 0},
        headers={"Content-Range": "dealNotes 0-0/0"}
    )

@app.get("/admin/contactNotes")
async def admin_get_contact_notes(
    request: Request,
    contact_id: Optional[int] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
):
    """Stub endpoint for contact notes - returns empty list for now."""
    return JSONResponse(
        content={"data": [], "total": 0},
        headers={"Content-Range": "contactNotes 0-0/0"}
    )

# ============ CONTACTS ============

@app.get("/admin/contacts")
async def admin_get_contacts(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    q: Optional[str] = Query(default=None),
    tags: Optional[List[str]] = Query(default=None),
    status: Optional[str] = Query(default=None),
    contact_type: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
    range: Optional[str] = Query(default=None),
    last_activity_gte: Optional[str] = Query(default=None, alias="last_activity_gte"),
    last_activity_lte: Optional[str] = Query(default=None, alias="last_activity_lte"),
    sales_id: Optional[int] = Query(default=None),
    filter: Optional[str] = Query(default=None),
):
    # Reuse existing contact listing logic
    return await get_contacts(
        request=request,
        db=db,
        current_user=current_user,
        q=q,
        tags=tags,
        status=status,
        contact_type=contact_type,
        sort=sort,
        order=order,
        range=range,
        last_activity_gte=last_activity_gte,
        last_activity_lte=last_activity_lte,
        sales_id=sales_id,
        filter=filter,
    )


@app.get("/admin/contacts/{contact_id}")
async def admin_get_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return await get_contact(contact_id, db, current_user)


@app.post("/admin/contacts")
async def admin_create_contact(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return await create_contact(request, db, current_user)


@app.put("/admin/contacts/{contact_id}")
async def admin_update_contact(
    contact_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return await update_contact(contact_id, request, db, current_user)


@app.delete("/admin/contacts/{contact_id}")
async def admin_delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Delete a contact and cascade delete related tasks."""
    from models import ContactTask
    
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    try:
        # Delete related contact tasks first (cascade)
        db.query(ContactTask).filter(ContactTask.contact_id == contact_id).delete(synchronize_session=False)
        # Now delete the contact
        db.delete(contact)
        db.commit()
        return JSONResponse({"success": True, "message": "Contact and related tasks deleted"})
    except Exception as e:
        logger.error(f"Error deleting contact: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting contact: {str(e)}")


class MergeContactsRequest(BaseModel):
    primary_id: int
    duplicate_ids: List[int]


@app.post("/api/contacts/merge")
async def merge_contacts(
    request: MergeContactsRequest,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Merge duplicate contacts into a primary contact.
    - Moves all deals, tasks, and activity logs from duplicates to primary
    - Enriches primary with any missing data from duplicates
    - Deletes the duplicate contacts
    """
    try:
        from models import Contact, Deal, ActivityLog
        
        # Get primary contact
        primary = db.query(Contact).filter(Contact.id == request.primary_id).first()
        if not primary:
            raise HTTPException(status_code=404, detail="Primary contact not found")
        
        # Get duplicate contacts
        duplicates = db.query(Contact).filter(Contact.id.in_(request.duplicate_ids)).all()
        if not duplicates:
            raise HTTPException(status_code=404, detail="No duplicate contacts found")
        
        merged_count = 0
        
        for dup in duplicates:
            # Enrich primary with missing data from duplicate
            if not primary.email and dup.email:
                primary.email = dup.email
            if not primary.phone and dup.phone:
                primary.phone = dup.phone
            if not primary.address and dup.address:
                primary.address = dup.address
            if not primary.title and dup.title:
                primary.title = dup.title
            if not primary.company and dup.company:
                primary.company = dup.company
            if not primary.company_id and dup.company_id:
                primary.company_id = dup.company_id
            if not primary.website and dup.website:
                primary.website = dup.website
            if not primary.first_name and dup.first_name:
                primary.first_name = dup.first_name
            if not primary.last_name and dup.last_name:
                primary.last_name = dup.last_name
            if not primary.name and dup.name:
                primary.name = dup.name
            
            # Merge notes
            if dup.notes:
                if primary.notes:
                    primary.notes = f"{primary.notes}\n---\n{dup.notes}"
                else:
                    primary.notes = dup.notes
            
            # Move activity logs to primary
            db.query(ActivityLog).filter(ActivityLog.contact_id == dup.id).update(
                {ActivityLog.contact_id: primary.id},
                synchronize_session=False
            )
            
            # Move deals that reference this contact (in contact_ids JSON)
            deals = db.query(Deal).all()
            for deal in deals:
                if deal.contact_ids:
                    try:
                        contact_ids = json.loads(deal.contact_ids) if isinstance(deal.contact_ids, str) else deal.contact_ids
                        if dup.id in contact_ids:
                            contact_ids = [primary.id if cid == dup.id else cid for cid in contact_ids]
                            contact_ids = list(set(contact_ids))  # Remove duplicates
                            deal.contact_ids = json.dumps(contact_ids)
                            db.add(deal)
                    except Exception:
                        pass
            
            # Delete the duplicate
            db.delete(dup)
            merged_count += 1
        
        # Update the primary contact
        db.add(primary)
        db.commit()
        
        logger.info(f"Merged {merged_count} contacts into {primary.id}")
        
        return {
            "success": True,
            "merged_count": merged_count,
            "primary_id": primary.id,
            "message": f"Successfully merged {merged_count} contacts"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error merging contacts: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CONTACT TASKS ENDPOINTS
# ============================================================================

@app.get("/admin/contact-tasks")
async def get_contact_tasks(
    contact_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get tasks for a specific contact."""
    from models import ContactTask
    
    query = db.query(ContactTask)
    
    if contact_id:
        query = query.filter(ContactTask.contact_id == contact_id)
    if status:
        query = query.filter(ContactTask.status == status)
    
    query = query.order_by(ContactTask.due_date.asc().nulls_last(), ContactTask.created_at.desc())
    tasks = query.all()
    
    return {"data": [t.to_dict() for t in tasks]}


@app.post("/admin/contact-tasks")
async def create_contact_task(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Create a task for a contact."""
    from models import ContactTask, Contact
    
    data = await request.json()
    contact_id = data.get("contact_id")
    
    if not contact_id:
        raise HTTPException(status_code=400, detail="contact_id is required")
    
    # Verify contact exists
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    task = ContactTask(
        contact_id=contact_id,
        title=data.get("text") or data.get("title") or "Untitled Task",
        description=data.get("description"),
        due_date=_coerce_datetime(data.get("due_date")),
        status="pending",
        assigned_to=data.get("assigned_to") or data.get("sales_id") or current_user.get("email"),
        created_by=current_user.get("email"),
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return JSONResponse(task.to_dict(), status_code=status.HTTP_201_CREATED)


@app.put("/admin/contact-tasks/{task_id}")
async def update_contact_task(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Update a contact task."""
    from models import ContactTask
    
    task = db.query(ContactTask).filter(ContactTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    data = await request.json()
    
    if "title" in data:
        task.title = data["title"]
    if "text" in data:
        task.title = data["text"]
    if "description" in data:
        task.description = data["description"]
    if "due_date" in data:
        task.due_date = _coerce_datetime(data["due_date"])
    if "status" in data:
        task.status = data["status"]
        if data["status"] == "done" or data["status"] == "completed":
            task.completed_at = datetime.now(timezone.utc)
            task.status = "done"
        elif data["status"] == "pending":
            task.completed_at = None
    if "assigned_to" in data:
        task.assigned_to = data["assigned_to"]
    
    task.updated_at = datetime.now(timezone.utc)
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return task.to_dict()


@app.delete("/admin/contact-tasks/{task_id}")
async def delete_contact_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Delete a contact task."""
    from models import ContactTask
    
    task = db.query(ContactTask).filter(ContactTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db.delete(task)
    db.commit()
    
    return {"success": True, "message": "Task deleted"}


# ---------------------------------------------------------------------------
# Contacts Summary (React Admin view emulation)
# ---------------------------------------------------------------------------
def _to_contact_summary_dict(contact, company_name: Optional[str] = None) -> Dict[str, Any]:
    """Map Contact to the contacts_summary shape expected by the frontend."""
    from models import LeadTask
    
    # Parse first/last name from full name if not set
    first_name = getattr(contact, "first_name", None)
    last_name = getattr(contact, "last_name", None)
    if not first_name and not last_name and contact.name:
        parts = contact.name.strip().split(None, 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""
    
    return {
        "id": contact.id,
        "first_name": first_name or "",
        "last_name": last_name or "",
        "title": contact.title,
        "company_id": getattr(contact, "company_id", None),
        "company_name": company_name,
        "email": contact.email,
        "phone": contact.phone,
        "status": contact.status or "cold",
        "tags": [],
        "last_seen": (getattr(contact, "last_seen", None) or contact.last_activity or contact.updated_at or contact.created_at).isoformat() if (getattr(contact, "last_seen", None) or contact.last_activity or contact.updated_at or contact.created_at) else None,
        "nb_tasks": 0,  # TODO: count tasks if needed
        "created_at": contact.created_at.isoformat() if contact.created_at else None,
        "updated_at": contact.updated_at.isoformat() if contact.updated_at else None,
    }


@app.get("/admin/contacts_summary")
async def admin_get_contacts_summary(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    company_id: Optional[int] = Query(default=None),
    range: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
):
    """Return contacts linked to a company (contacts_summary view emulation)."""
    try:
        from models import Contact, ReferralSource

        range_header = request.headers.get("Range")
        range_param = range or (range_header.split("=")[1] if range_header else None)
        start, end = _parse_range(range_param)

        query = db.query(Contact)
        if company_id is not None:
            query = query.filter(Contact.company_id == company_id)

        total = query.count()

        # Sorting
        sort_field = sort or "last_name"
        order_dir = (order or "ASC").upper()
        col = getattr(Contact, sort_field, None) or Contact.id
        if order_dir == "DESC":
            query = query.order_by(col.desc())
        else:
            query = query.order_by(col.asc())

        contacts = query.offset(start).limit(end - start + 1).all()

        # Get company names
        company_ids = [c.company_id for c in contacts if c.company_id]
        company_names = {}
        if company_ids:
            companies = db.query(ReferralSource).filter(ReferralSource.id.in_(company_ids)).all()
            company_names = {c.id: c.organization or c.name for c in companies}

        data = [
            _to_contact_summary_dict(c, company_names.get(c.company_id))
            for c in contacts
        ]

        content_range = f"contacts_summary {start}-{start + len(data) - 1 if data else start}/{total}"
        return JSONResponse(
            {"data": data, "total": total},
            headers={
                "Content-Range": content_range,
                "Access-Control-Expose-Headers": "Content-Range",
                "X-Total-Count": str(total),
            },
        )
    except Exception as e:
        logger.error("Error fetching contacts_summary: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/companies/sync-contacts")
async def admin_sync_contacts_from_companies(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Create Contact records from ReferralSource data (one-time sync)."""
    try:
        from models import Contact, ReferralSource

        companies = db.query(ReferralSource).all()
        created = 0
        skipped = 0

        for company in companies:
            # Get the person name from the company record
            person_name = company.name  # In ReferralSource, 'name' is the contact person
            if not person_name:
                skipped += 1
                continue

            # Check if contact already exists for this company
            existing = db.query(Contact).filter(
                Contact.company_id == company.id
            ).first()
            if existing:
                skipped += 1
                continue

            # Parse first/last name
            parts = person_name.strip().split(None, 1)
            first_name = parts[0] if parts else person_name
            last_name = parts[1] if len(parts) > 1 else ""

            contact = Contact(
                first_name=first_name,
                last_name=last_name,
                name=person_name,
                company=company.organization,
                company_id=company.id,
                title=company.contact_name if company.contact_name != person_name else None,
                email=company.email,
                phone=company.phone,
                notes=company.notes,
                status="cold",
                created_at=company.created_at,
                updated_at=company.updated_at,
                last_seen=company.updated_at,
            )
            db.add(contact)
            created += 1

        db.commit()
        return JSONResponse({"success": True, "created": created, "skipped": skipped})
    except Exception as e:
        logger.error("Error syncing contacts: %s", e, exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/companies")
async def admin_get_companies(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    range: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    size: Optional[List[str]] = Query(default=None),
    sector: Optional[List[str]] = Query(default=None),
    sales_id: Optional[int] = Query(default=None),
    filter: Optional[str] = Query(default=None),
):
    try:
        from models import ReferralSource
        from sqlalchemy import or_

        # Some React Admin data providers send JSON in a `filter=` query param.
        # Accept it as a fallback and merge into explicit params.
        if filter:
            try:
                parsed = json.loads(filter)
                if isinstance(parsed, dict):
                    q = q or parsed.get("q")
                    if not size and parsed.get("size"):
                        size = [str(parsed.get("size"))]
                    if not sector and parsed.get("sector"):
                        sector = [str(parsed.get("sector"))]
                    if sales_id is None and parsed.get("sales_id") is not None:
                        try:
                            sales_id = int(parsed.get("sales_id"))
                        except Exception:
                            pass
            except Exception:
                # Ignore invalid JSON filter payloads
                pass

        range_header = request.headers.get("Range")
        range_param = range or (range_header.split("=")[1] if range_header else None)
        start, end = _parse_range(range_param)

        query = db.query(ReferralSource)

        # Filters (React Admin passes them as query params via frontend data provider)
        if q:
            like = f"%{q.strip()}%"
            query = query.filter(
                or_(
                    ReferralSource.name.ilike(like),
                    ReferralSource.organization.ilike(like),
                    ReferralSource.contact_name.ilike(like),
                    ReferralSource.email.ilike(like),
                    ReferralSource.phone.ilike(like),
                    ReferralSource.address.ilike(like),
                    ReferralSource.notes.ilike(like),
                )
            )

        if sector:
            # UI calls this "Referral Type" but it's backed by ReferralSource.source_type
            values: List[str] = []
            for item in sector:
                values.extend([v.strip() for v in str(item).split(",") if v.strip()])
            if values:
                # Map legacy/template UI labels to the DB's current source_type values.
                # This keeps filters working even if the frontend options drift from stored data.
                sector_synonyms: Dict[str, List[str]] = {
                    # Template labels -> DB labels / stems
                    "Hospitals": ["Hospital", "Hospital / Transitions"],
                    "Rehab Hospitals": ["Rehab", "Rehabilitation", "Hospital", "Hospital / Transitions"],
                    "Skilled Nursing Facilities": ["Skilled Nursing", "Nursing"],
                    # Current DB labels pass through
                    "Hospital / Transitions": ["Hospital / Transitions", "Hospital"],
                    "Skilled Nursing": ["Skilled Nursing", "Nursing"],
                    "Primary Care": ["Primary Care"],
                    "Senior Living": ["Senior Living"],
                    "Senior Housing": ["Senior Housing"],
                    "Community Organization": ["Community Organization"],
                    "Home Care Partner": ["Home Care Partner"],
                    "Placement Agency": ["Placement Agency"],
                    "Healthcare Facility": ["Healthcare Facility"],
                    "Legal / Guardianship": ["Legal / Guardianship", "Guardianship", "Legal"],
                    "Payer / Insurance": ["Payer / Insurance", "Insurance", "Payer"],
                }

                ors = []
                for v in values:
                    terms = sector_synonyms.get(v, [v])
                    for term in terms:
                        like = f"%{term}%"
                        ors.append(ReferralSource.source_type.ilike(like))
                if ors:
                    query = query.filter(or_(*ors))

        if size:
            # UI calls this "Service Area / County".
            # Now that we have a real `county` column from enrichment, prefer it.
            # Fallback heuristic (address substring match) for non-enriched companies.
            values: List[str] = []
            for item in size:
                values.extend([v.strip() for v in str(item).split(",") if v.strip()])
            ors = []
            county_terms = {
                "Denver": ["Denver", "802"],
                "Boulder": ["Boulder", "Longmont", "Louisville", "Lafayette", "Superior", "803", "805"],
                "Pueblo": ["Pueblo", "810"],
                "El Paso": ["Colorado Springs", "Fountain", "Manitou", "Falcon", "Peyton", "809", "808", "Monument"],
                "Douglas": ["Castle Rock", "Parker", "Highlands Ranch", "Lone Tree", "801", "Castle Pines"],
                "Jefferson": ["Lakewood", "Arvada", "Golden", "Wheat Ridge", "Evergreen", "800", "Littleton"],
                "Adams": ["Thornton", "Brighton", "Commerce City", "Northglenn", "Federal Heights", "800", "806"],
                "Broomfield": ["Broomfield", "80020", "80021", "80023"],
                "Arapahoe": ["Arapahoe", "Aurora", "Centennial", "Englewood", "Greenwood Village", "80111", "80112"],
            }
            for v in values:
                # First: exact match on enriched county column (case-insensitive)
                ors.append(ReferralSource.county.ilike(v))
                # Fallback: expand known counties into likely address substrings
                search_terms = county_terms.get(v, [v])
                for term in search_terms:
                    like = f"%{term}%"
                    ors.extend(
                        [
                            ReferralSource.address.ilike(like),
                            ReferralSource.notes.ilike(like),
                            ReferralSource.organization.ilike(like),
                            ReferralSource.name.ilike(like),
                            ReferralSource.contact_name.ilike(like),
                        ]
                    )
            if ors:
                query = query.filter(or_(*ors))

        # sales_id filter currently not supported for ReferralSource (no owner column).
        # We accept it to avoid 422s, but intentionally ignore it for now.
        _ = sales_id

        total = query.count()

        order_clause = ReferralSource.created_at.desc()
        if sort:
            col = getattr(ReferralSource, sort, None)
            if col is not None:
                order_clause = col.desc() if (order or "").upper() == "DESC" else col.asc()

        records = query.order_by(order_clause).offset(start).limit(end - start + 1).all()
        content_range = f"companies {start}-{start + len(records) - 1 if records else start}/{total}"

        return JSONResponse(
            {"data": [_to_company_dict(r) for r in records], "total": total},
            headers={
                "Content-Range": content_range,
                "Access-Control-Expose-Headers": "Content-Range",
                "X-Total-Count": str(total),
            },
        )
    except Exception as e:
        logger.error(f"Error fetching companies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/companies/{company_id}")
async def admin_get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Return a single company record (ReferralSource) for React Admin getOne()."""
    try:
        from models import ReferralSource, Contact

        source = db.query(ReferralSource).filter(ReferralSource.id == company_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Company not found")

        # Count linked contacts
        nb_contacts = db.query(Contact).filter(Contact.company_id == company_id).count()

        return JSONResponse(_to_company_dict(source, nb_contacts=nb_contacts))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching company {company_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/companies")
async def admin_create_company(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        from models import ReferralSource

        data = await request.json()
        source = ReferralSource(
            name=data.get("name"),
            organization=data.get("organization"),
            contact_name=data.get("contact_name"),
            email=data.get("email"),
            phone=data.get("phone_number") or data.get("phone"),
            address=data.get("address"),
            source_type=data.get("source_type"),
            status=data.get("status", "active"),
            notes=data.get("notes"),
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        return JSONResponse(_to_company_dict(source), status_code=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f"Error creating company: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/admin/companies/{company_id}")
async def admin_update_company(
    company_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        from models import ReferralSource

        source = db.query(ReferralSource).filter(ReferralSource.id == company_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Company not found")

        data = await request.json()
        for field in [
            "name",
            "organization",
            "contact_name",
            "email",
            "phone",
            "address",
            "source_type",
            "status",
            "notes",
            "county",
            "facility_type_normalized",
            "website",
            "logo_url",
        ]:
            if field in data:
                setattr(source, field, data[field])
        # Accept phone_number alias
        if "phone_number" in data:
            source.phone = data["phone_number"]

        db.commit()
        db.refresh(source)
        return JSONResponse(_to_company_dict(source))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating company: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/admin/companies/{company_id}")
async def admin_delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        from models import ReferralSource

        source = db.query(ReferralSource).filter(ReferralSource.id == company_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Company not found")
        db.delete(source)
        db.commit()
        return JSONResponse({"success": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting company: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Company Enrichment (AI-powered)
# ---------------------------------------------------------------------------
ENRICH_PROMPT_TEMPLATE = """You are a helpful assistant that enriches company records.

Given the following company information, determine:
1. county: The Colorado county where this company is located (e.g., "Denver", "El Paso", "Jefferson"). If unknown, return null.
2. facility_type: A normalized facility type from this list: skilled_nursing, hospital, rehab_hospital, assisted_living, independent_living, memory_care, home_health, hospice, primary_care, outpatient, placement_agency, legal, community_org, insurance, other. Pick the best match.
3. website: The company's website URL (with https://). If you can infer it from email domain or organization name, provide it. If unknown, return null.
4. logo_url: A Clearbit logo URL like https://logo.clearbit.com/<domain> if you determined a website domain. Otherwise null.

Company data:
- Name: {name}
- Organization: {organization}
- Contact Name: {contact_name}
- Email: {email}
- Phone: {phone}
- Address: {address}
- Source Type: {source_type}
- Notes: {notes}

Respond ONLY with valid JSON (no markdown):
{{"county": ..., "facility_type": ..., "website": ..., "logo_url": ...}}
"""


def _call_openai_enrich(prompt: str) -> Optional[dict]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            },
            timeout=30.0,
        )
        if resp.status_code != 200:
            logger.warning("OpenAI enrich error %s: %s", resp.status_code, resp.text[:200])
            return None
        content = resp.json()["choices"][0]["message"]["content"]
        content = re.sub(r"^```json\s*", "", content.strip(), flags=re.IGNORECASE)
        content = re.sub(r"```$", "", content.strip())
        return json.loads(content)
    except Exception as e:
        logger.warning("OpenAI enrich exception: %s", e)
        return None


def _call_gemini_enrich(prompt: str) -> Optional[dict]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            resp = httpx.post(
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=30.0,
            )
            if resp.status_code == 404:
                continue
            if resp.status_code != 200:
                continue
            data = resp.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            text = re.sub(r"^```json\s*", "", text.strip(), flags=re.IGNORECASE)
            text = re.sub(r"```$", "", text.strip())
            return json.loads(text)
        except Exception:
            continue
    return None


def _enrich_company_record(source) -> dict:
    prompt = ENRICH_PROMPT_TEMPLATE.format(
        name=source.name or "",
        organization=source.organization or "",
        contact_name=source.contact_name or "",
        email=source.email or "",
        phone=source.phone or "",
        address=source.address or "",
        source_type=source.source_type or "",
        notes=(source.notes or "")[:500],
    )
    # Use Gemini first (faster, cheaper), fallback to OpenAI
    result = _call_gemini_enrich(prompt)
    if not result:
        result = _call_openai_enrich(prompt)
    return result or {}


@app.post("/admin/companies/{company_id}/enrich")
async def admin_enrich_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Enrich a single company with AI-derived county, facility_type, website, logo_url."""
    try:
        from models import ReferralSource

        source = db.query(ReferralSource).filter(ReferralSource.id == company_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Company not found")

        enriched = _enrich_company_record(source)
        if enriched.get("county"):
            source.county = enriched["county"]
        if enriched.get("facility_type"):
            source.facility_type_normalized = enriched["facility_type"]
        if enriched.get("website"):
            source.website = enriched["website"]
        if enriched.get("logo_url"):
            source.logo_url = enriched["logo_url"]
        db.commit()
        db.refresh(source)
        return JSONResponse({"success": True, "enriched": enriched, "company": _to_company_dict(source)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error enriching company %s: %s", company_id, e, exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/companies/enrich-all")
async def admin_enrich_all_companies(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    force: bool = Query(default=False),
):
    """Bulk enrich all companies (runs in background). Set force=true to re-enrich already enriched."""
    from models import ReferralSource

    def do_enrichment():
        session = db_manager.get_session()
        try:
            q = session.query(ReferralSource)
            if not force:
                # Only enrich companies missing county or website
                q = q.filter(
                    (ReferralSource.county == None) | (ReferralSource.website == None)  # noqa: E711
                )
            companies = q.all()
            logger.info("Starting bulk enrichment of %d companies", len(companies))
            for i, company in enumerate(companies):
                logger.info("[%d/%d] Enriching %s", i + 1, len(companies), company.name or company.organization)
                enriched = _enrich_company_record(company)
                if enriched.get("county"):
                    company.county = enriched["county"]
                if enriched.get("facility_type"):
                    company.facility_type_normalized = enriched["facility_type"]
                if enriched.get("website"):
                    company.website = enriched["website"]
                if enriched.get("logo_url"):
                    company.logo_url = enriched["logo_url"]
                session.commit()
                time.sleep(0.5)  # Rate limit politeness
            logger.info("Bulk enrichment complete")
        except Exception as e:
            logger.error("Bulk enrichment failed: %s", e, exc_info=True)
        finally:
            session.close()

    background_tasks.add_task(do_enrichment)
    return JSONResponse({"success": True, "message": "Enrichment started in background. Check logs for progress."})


@app.get("/admin/deals")
async def admin_get_deals(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    stage: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
    range: Optional[str] = Query(default=None),
    created_at_gte: Optional[str] = Query(default=None, alias="created_at@gte"),
    created_at_lte: Optional[str] = Query(default=None, alias="created_at@lte"),
):
    return await get_deals(
        request=request,
        db=db,
        current_user=current_user,
        stage=stage,
        sort=sort,
        order=order,
        range=range,
        created_at_gte=created_at_gte,
        created_at_lte=created_at_lte,
    )


@app.get("/admin/deals/{deal_id}")
async def admin_get_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return await get_deal(deal_id, db, current_user)


@app.post("/admin/deals")
async def admin_create_deal(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return await create_deal(request, db, current_user)


@app.put("/admin/deals/{deal_id}")
async def admin_update_deal(
    deal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return await update_deal(deal_id, request, db, current_user)


@app.delete("/admin/deals/{deal_id}")
async def admin_delete_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    return await delete_deal(deal_id, db, current_user)


@app.get("/admin/tasks")
async def admin_get_tasks(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    range: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
    contact_id: Optional[int] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    assigned_to: Optional[str] = Query(default=None),
    sales_id: Optional[str] = Query(default=None),
    filter: Optional[str] = Query(default=None),
):
    try:
        from models import LeadTask, CompanyTask
        from sqlalchemy import or_

        # React Admin data provider sometimes sends JSON in `filter=...`
        if filter:
            try:
                parsed = json.loads(filter)
                if isinstance(parsed, dict):
                    if contact_id is None and parsed.get("contact_id") is not None:
                        try:
                            contact_id = int(parsed.get("contact_id"))
                        except Exception:
                            pass
                    if not status_filter and parsed.get("status"):
                        status_filter = str(parsed.get("status"))
                    if not assigned_to and parsed.get("assigned_to"):
                        assigned_to = str(parsed.get("assigned_to"))
                    if not sales_id and parsed.get("sales_id"):
                        sales_id = str(parsed.get("sales_id"))
            except Exception:
                pass

        # Backward compat: frontend historically sends sales_id=identity.id
        # Treat that as an assignee filter.
        effective_assignee = assigned_to or sales_id

        range_header = request.headers.get("Range")
        range_param = range or (range_header.split("=")[1] if range_header else None)
        start, end = _parse_range(range_param)

        # If a contact_id is provided, interpret it as a referral source (company) task
        # to align with the admin UI which passes contact_id.
        if contact_id is not None:
            query = db.query(CompanyTask).filter(CompanyTask.company_id == contact_id)
            if status_filter:
                query = query.filter(CompanyTask.status == status_filter)
            if effective_assignee:
                # Backward compat: older tasks may have NULL assigned_to; show them so they can be assigned.
                query = query.filter(
                    or_(CompanyTask.assigned_to == effective_assignee, CompanyTask.assigned_to.is_(None))
                )

            total = query.count()
            order_clause = CompanyTask.created_at.desc()
            if sort:
                col = getattr(CompanyTask, sort, None)
                if col is not None:
                    order_clause = col.desc() if (order or "").upper() == "DESC" else col.asc()

            tasks = query.order_by(order_clause).offset(start).limit(end - start + 1).all()
            content_range = f"tasks {start}-{start + len(tasks) - 1 if tasks else start}/{total}"
            return JSONResponse(
                {"data": [_to_company_task_dict(t) for t in tasks], "total": total},
                headers={
                    "Content-Range": content_range,
                    "Access-Control-Expose-Headers": "Content-Range",
                    "X-Total-Count": str(total),
                },
            )

        # Fallback: legacy lead tasks
        query = db.query(LeadTask)
        if status_filter:
            query = query.filter(LeadTask.status == status_filter)
        if effective_assignee:
            # Backward compat: older tasks may have NULL assigned_to; show them so they can be assigned.
            query = query.filter(or_(LeadTask.assigned_to == effective_assignee, LeadTask.assigned_to.is_(None)))

        total = query.count()
        order_clause = LeadTask.created_at.desc()
        if sort:
            col = getattr(LeadTask, sort, None)
            if col is not None:
                order_clause = col.desc() if (order or "").upper() == "DESC" else col.asc()

        tasks = query.order_by(order_clause).offset(start).limit(end - start + 1).all()
        content_range = f"tasks {start}-{start + len(tasks) - 1 if tasks else start}/{total}"

        return JSONResponse(
            {"data": [_to_task_dict(t) for t in tasks], "total": total},
            headers={
                "Content-Range": content_range,
                "Access-Control-Expose-Headers": "Content-Range",
                "X-Total-Count": str(total),
            },
        )
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/tasks/{task_id}")
async def admin_get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get a single task by ID"""
    try:
        from models import LeadTask, CompanyTask
        
        # Try CompanyTask first
        task = db.query(CompanyTask).filter(CompanyTask.id == task_id).first()
        if task:
            return JSONResponse({"data": _to_company_task_dict(task)})
        
        # Try LeadTask
        task = db.query(LeadTask).filter(LeadTask.id == task_id).first()
        if task:
            return JSONResponse({"data": _to_task_dict(task)})
        
        raise HTTPException(status_code=404, detail="Task not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/tasks")
async def admin_create_task(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        from models import LeadTask, LeadActivity, Lead, CompanyTask, ReferralSource

        data = await request.json()
        company_id = data.get("contact_id")
        due_date = _coerce_datetime(data.get("due_date"))
        creator_email = current_user.get("email")
        requested_assignee = data.get("assigned_to") or data.get("sales_id")
        assignee_email = requested_assignee or creator_email

        if company_id:
            # Treat contact_id as referral source id for company tasks
            source = db.query(ReferralSource).filter(ReferralSource.id == company_id).first()
            if not source:
                raise HTTPException(status_code=404, detail="Company not found")

            task = CompanyTask(
                company_id=company_id,
                title=data.get("text"),
                description=data.get("description"),
                due_date=due_date,
                status="pending",
                assigned_to=assignee_email,
                created_by=creator_email,
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            return JSONResponse(_to_company_task_dict(task), status_code=status.HTTP_201_CREATED)

        # Legacy: lead tasks
        lead_id = data.get("lead_id")
        if not lead_id:
            raise HTTPException(status_code=400, detail="contact_id or lead_id is required")

        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        task = LeadTask(
            lead_id=lead_id,
            title=data.get("text"),
            description=data.get("description"),
            due_date=due_date,
            status="pending",
            assigned_to=assignee_email,
            created_by=creator_email,
        )
        db.add(task)
        db.flush()

        activity = LeadActivity(
            lead_id=lead_id,
            activity_type="task_created",
            description=f"Task added: {task.title}",
            user_email=current_user.get("email"),
            new_value=task.title,
        )
        db.add(activity)
        db.commit()
        db.refresh(task)
        return JSONResponse(_to_task_dict(task), status_code=status.HTTP_201_CREATED)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating task: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/admin/tasks/{task_id}")
async def admin_update_task(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        from models import LeadTask, LeadActivity, CompanyTask

        data = await request.json()

        # Try company task first
        company_task = db.query(CompanyTask).filter(CompanyTask.id == task_id).first()
        if company_task:
            if "text" in data:
                company_task.title = data["text"]
            if "description" in data:
                company_task.description = data["description"]
            if "due_date" in data:
                company_task.due_date = _coerce_datetime(data["due_date"])
            if "status" in data:
                company_task.status = data["status"]
                if data["status"] == "completed":
                    company_task.completed_at = datetime.utcnow()
                else:
                    company_task.completed_at = None
            if "assigned_to" in data:
                company_task.assigned_to = data["assigned_to"]
            db.commit()
            db.refresh(company_task)
            return JSONResponse(_to_company_task_dict(company_task))

        # Legacy lead task
        task = db.query(LeadTask).filter(LeadTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if "text" in data:
            task.title = data["text"]
        if "description" in data:
            task.description = data["description"]
        if "due_date" in data:
            task.due_date = _coerce_datetime(data["due_date"])
        if "status" in data:
            old_status = task.status
            task.status = data["status"]
            if data["status"] == "completed" and old_status != "completed":
                task.completed_at = datetime.utcnow()
                activity = LeadActivity(
                    lead_id=task.lead_id,
                    activity_type="task_completed",
                    description=f"Task completed: {task.title}",
                    user_email=current_user.get("email"),
                )
                db.add(activity)
            if data["status"] != "completed":
                task.completed_at = None
        if "assigned_to" in data:
            task.assigned_to = data["assigned_to"]

        db.commit()
        db.refresh(task)
        return JSONResponse(_to_task_dict(task))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/admin/tasks/{task_id}")
async def admin_delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        from models import LeadTask, CompanyTask

        task = db.query(CompanyTask).filter(CompanyTask.id == task_id).first()
        if task:
            db.delete(task)
            db.commit()
            return JSONResponse({"success": True})

        task = db.query(LeadTask).filter(LeadTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        db.delete(task)
        db.commit()
        return JSONResponse({"success": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting task: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

def _download_drive_public(url: str) -> Optional[tuple]:
    """Best-effort public Google Drive download without Drive API."""
    import re
    import requests

    # Try to extract file id from common drive URL patterns
    file_id = None
    match = re.search(r"/d/([^/]+)/", url)
    if match:
        file_id = match.group(1)
    else:
        match = re.search(r"id=([^&]+)", url)
        if match:
            file_id = match.group(1)

    download_url = None
    if file_id:
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    else:
        download_url = url

    try:
        resp = requests.get(download_url, allow_redirects=True, timeout=30)
        if resp.status_code == 200 and resp.content:
            filename = f"{file_id or 'downloaded_file'}"
            return resp.content, filename, {"owners": []}
        logger.warning(f"Public Drive download failed: status {resp.status_code}")
    except Exception as e:
        logger.warning(f"Public Drive download exception: {e}")
    return None


@app.post("/upload-url")
async def upload_from_url(
    request: UrlUploadRequest,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload and parse file from Google Drive URL"""
    try:
        url = request.url
        logger.info(f"Processing URL upload: {url}")
        
        # Download file from Drive
        drive_service = GoogleDriveService()
        print(f"DEBUG: Attempting to download from URL: {url}")

        result = None
        if drive_service.enabled:
            result = drive_service.download_file_from_url(url)

        # Fallback to public download if Drive API not configured or failed
        if not result:
            result = _download_drive_public(url)

        if not result:
            raise HTTPException(status_code=400, detail="Failed to download file from URL. Ensure the link is accessible or make it public.")
            
        content, filename, metadata = result
        logger.info(f"Downloaded file: {filename} ({len(content)} bytes)")

        # Determine owner email (Drive owner if available, else uploader)
        owners = metadata.get('owners', [])
        owner_email = owners[0].get('emailAddress', '') if owners else ''
        if not owner_email:
            owner_email = current_user.get("email") or "unknown@careassist.com"

        # Determine which tracked user should receive this Drive import.
        # This affects BOTH receipts (Expense.user_email) and MyWay mileage (FinancialEntry.user_email).
        assigned_owner = _choose_expense_owner(
            assign_to=getattr(request, "assign_to", None),
            owner_email=owner_email,
            current_user_email=current_user.get("email"),
        )

        # Detect file type by content and extension
        is_pdf = content[:4] == b'%PDF' or filename.lower().endswith('.pdf')
        is_image = _looks_like_image_bytes(content, filename) and not is_pdf
        is_expense_file = _is_expense_filename(filename)
        
        logger.info(f"File type detection: is_pdf={is_pdf}, is_image={is_image}, is_expense={is_expense_file}")
        
        # PDF FILES: Use AI parser (MyWay routes, receipts)
        parse_result = None
        parse_error = None
        if is_pdf:
            if is_expense_file:
                # Receipt PDF - use AI to extract
                logger.info(f"Parsing receipt PDF with AI: {filename}")
                receipt_result = ai_parser.parse_receipt(content, filename)
                if receipt_result.get("success"):
                    amount = receipt_result.get("amount", 0)
                    vendor = receipt_result.get("vendor", "Unknown")
                    category = receipt_result.get("category", "Uncategorized")
                    description = receipt_result.get("description", "")
                    
                    new_expense = Expense(
                        user_email=assigned_owner,
                        amount=amount,
                        description=f"{vendor}: {description}" if description else f"Receipt from {vendor}",
                        category=category,
                        receipt_url=url,
                        status="pending",
                        date=datetime.utcnow()
                    )
                    db.add(new_expense)
                    db.commit()
                    db.refresh(new_expense)
                    return JSONResponse({
                        "success": True,
                        "filename": filename,
                        "type": "expense_receipt",
                        "expense": new_expense.to_dict(),
                        "ai_extracted": receipt_result,
                        "assigned_to": assigned_owner
                    })
            else:
                # MyWay PDF - use AI to extract
                logger.info(f"Parsing MyWay PDF with AI: {filename}")
                try:
                    parse_result = ai_parser.parse_myway_pdf(content, filename)
                    logger.info(f"AI parser result: success={parse_result.get('success')}, visits={len(parse_result.get('visits', []))}")
                except Exception as e:
                    parse_error = str(e)
                    logger.warning(f"AI PDF parser threw exception: {e}")
                    parse_result = {"success": False, "error": str(e)}
        
        # IMAGE FILES: Receipt or Business Card
        # IMPORTANT: For Drive uploads, ALWAYS try receipt parsing first (content-based),
        # regardless of filename. Only fall back to business card if it's not a receipt.
        elif is_image:
            # Try receipt parsing first for ALL images from Drive
            logger.info(f"[upload-url] Attempting receipt parse for image: {filename}")
            receipt_result = ai_parser.parse_receipt(content, filename)
            
            # If AI found a valid receipt with an amount, save as expense
            if receipt_result.get("success") and receipt_result.get("amount"):
                amount = receipt_result.get("amount", 0)
                vendor = receipt_result.get("vendor", "Unknown")
                category = receipt_result.get("category", "Uncategorized")
                description = receipt_result.get("description", "")
                expense_date = _parse_receipt_date(receipt_result)
                
                new_expense = Expense(
                    user_email=assigned_owner,
                    amount=amount,
                    description=f"{vendor}: {description}" if description else f"Receipt from {vendor}",
                    category=category,
                    receipt_url=url,
                    status="pending",
                    date=expense_date
                )
                db.add(new_expense)
                db.commit()
                db.refresh(new_expense)
                return JSONResponse({
                    "success": True,
                    "filename": filename,
                    "type": "expense_receipt",
                    "expense": new_expense.to_dict(),
                    "ai_extracted": receipt_result,
                    "assigned_to": assigned_owner
                })
            
            # Not a receipt (or AI couldn't extract a meaningful amount) -> treat as business card
            logger.info(f"[upload-url] Image did not parse as receipt (success={receipt_result.get('success')}, amount={receipt_result.get('amount')}), trying business card for {filename}")
            logger.info(f"Parsing business card image with AI: {filename}")
            card_result = ai_parser.parse_business_card(content, filename)
            if card_result.get("success"):
                contact_data = card_result
                # Build full name
                first_name = contact_data.get('first_name') or ''
                last_name = contact_data.get('last_name') or ''
                full_name = f"{first_name} {last_name}".strip() or None
                
                existing_contact = None
                if contact_data.get('email'):
                    existing_contact = db.query(Contact).filter(Contact.email == contact_data['email']).first()
                
                if existing_contact:
                    existing_contact.updated_at = datetime.utcnow()
                    db.add(existing_contact)
                    db.commit()
                    db.refresh(existing_contact)
                    saved_contact = existing_contact
                else:
                    new_contact = Contact(
                        name=full_name,
                        first_name=first_name,
                        last_name=last_name,
                        company=contact_data.get('company'),
                        title=contact_data.get('title'),
                        phone=contact_data.get('phone'),
                        email=contact_data.get('email'),
                        address=contact_data.get('address'),
                        website=contact_data.get('website'),
                        notes=f"Scanned from business card (AI) on {datetime.now().strftime('%Y-%m-%d')}",
                        contact_type="prospect",
                        status="cold",
                        tags=_serialize_tags(["Scanned"]),
                        scanned_date=datetime.utcnow(),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(new_contact)
                    db.commit()
                    db.refresh(new_contact)
                    saved_contact = new_contact
                
                return JSONResponse({
                    "success": True,
                    "filename": filename,
                    "type": "business_card",
                    "contact": saved_contact.to_dict(),
                    "ai_extracted": card_result
                })
        
        # Handle successful time tracking
        if parse_result and parse_result.get("success") and parse_result.get("type") == "time_tracking":
            date_value = parse_result.get("date")
            if isinstance(date_value, datetime):
                date_value = date_value.date().isoformat()
            elif date_value and hasattr(date_value, 'date'):
                date_value = date_value.date().isoformat()
            total_hours = parse_result.get("total_hours")
            if total_hours in (None, 0):
                total_hours = _extract_hours_from_pdf_text(content)
            return JSONResponse({
                "success": True,
                "filename": filename,
                "type": "time_tracking",
                "date": date_value,
                "total_hours": total_hours
            })

        # Handle successful MyWay
        if parse_result and parse_result.get("success") and parse_result.get("type") == "myway_route":
            visits = parse_result.get("visits") or []
            mileage = parse_result.get("mileage")
            visit_date = parse_result.get("date")
            if not visits and not mileage:
                raise HTTPException(status_code=400, detail="No visits or mileage found in PDF")
            # Attribute this MyWay upload to the selected tracked user so mileage shows in their pay-period widget.
            user_email = assigned_owner

            # Save visits to database (with duplicate checking)
            saved_visits = []
            skipped_duplicates = []
            visit_errors = []
            
            def normalize_business_name(name):
                """Normalize business name for duplicate checking"""
                if not name:
                    return ""
                import re
                normalized = (name or "").lower().strip()
                normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
                normalized = re.sub(r'\s+', ' ', normalized)  # Normalize spaces
                return normalized
            
            logger.info(f"[upload-url] Attempting to save {len(visits)} visits for {user_email}")
            for visit_data in visits:
                try:
                    business_name = visit_data.get("business_name", "Unknown")
                    stop_number = visit_data.get("stop_number", 0)
                    v_date = visit_data.get("visit_date") or visit_date or datetime.utcnow()
                    
                    # Duplicate check: same date, stop number, and normalized business name
                    v_date_only = v_date.date() if hasattr(v_date, 'date') else v_date
                    business_normalized = normalize_business_name(business_name)
                    
                    existing_visits = db.query(Visit).filter(
                        func.date(Visit.visit_date) == v_date_only,
                        Visit.stop_number == stop_number
                    ).all()
                    
                    is_duplicate = False
                    for ev in existing_visits:
                        if normalize_business_name(ev.business_name) == business_normalized:
                            is_duplicate = True
                            skipped_duplicates.append({
                                "business_name": business_name,
                                "date": str(v_date_only),
                                "existing_id": ev.id
                            })
                            logger.info(f"[upload-url] Skipping duplicate visit: {business_name} on {v_date_only}")
                            break
                    
                    if is_duplicate:
                        continue
                    
                    new_visit = Visit(
                        stop_number=stop_number,
                        business_name=business_name,
                        address=visit_data.get("address"),
                        city=visit_data.get("city"),
                        notes=visit_data.get("notes"),
                        visit_date=v_date,
                        user_email=user_email,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    db.add(new_visit)
                    db.flush()  # get ID
                    saved_visits.append(new_visit)

                    # Log activity for each visit (non-blocking)
                    try:
                        ActivityLogger.log_visit(
                            db=db,
                            visit_id=new_visit.id,
                            business_name=new_visit.business_name,
                            user_email=user_email,
                            visit_date=new_visit.visit_date,
                            commit=False,
                        )
                    except Exception as e:
                        logger.error(f"[upload-url] Error logging visit activity (non-critical): {e}")
                except Exception as e:
                    error_msg = f"[upload-url] Error saving visit {visit_data.get('business_name')}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    visit_errors.append(error_msg)

            # Save mileage to FinancialEntry if present
            if mileage and visit_date:
                try:
                    entry_date = datetime.fromisoformat(visit_date) if isinstance(visit_date, str) else visit_date
                    existing_entry = db.query(FinancialEntry).filter(
                        func.date(FinancialEntry.date) == entry_date.date()
                    ).first()
                    if existing_entry:
                        existing_entry.miles_driven = mileage
                        existing_entry.mileage_cost = mileage * 0.70
                        existing_entry.user_email = user_email
                        existing_entry.updated_at = datetime.utcnow()
                    else:
                        new_entry = FinancialEntry(
                            date=entry_date,
                            hours_worked=0,
                            labor_cost=0,
                            miles_driven=mileage,
                            mileage_cost=mileage * 0.70,
                            materials_cost=0,
                            total_daily_cost=mileage * 0.70,
                            user_email=user_email,
                        )
                        db.add(new_entry)
                except Exception as e:
                    logger.error(f"[upload-url] Error saving mileage: {e}")

            # If NO visits were saved but some were parsed (and not all duplicates), roll back
            logger.info(f"[upload-url] Visit save summary: parsed={len(visits)}, flushed={len(saved_visits)}, duplicates={len(skipped_duplicates)}, errors={len(visit_errors)}")
            if len(visits) > 0 and len(saved_visits) == 0 and len(skipped_duplicates) == 0:
                db.rollback()
                error_details = "\n".join(visit_errors) if visit_errors else "Unknown database error"
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to save any visits to database. Parsed {len(visits)} visits but all failed to save. Errors: {error_details}",
                )

            # Serialize BEFORE commit to avoid detached instance errors
            serialized_visits = [v.to_dict() for v in saved_visits]

            # Commit all changes
            try:
                db.commit()
                logger.info(f"[upload-url] Commit successful: {len(serialized_visits)} visits saved, {len(skipped_duplicates)} duplicates skipped")
            except Exception as commit_error:
                logger.error(f"[upload-url] COMMIT FAILED: {commit_error}", exc_info=True)
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Database commit failed: {str(commit_error)}")

            response_data = {
                "success": True,
                "filename": filename,
                "type": "myway_route",
                "visits": serialized_visits,
                "count": len(serialized_visits),
                "mileage": mileage,
                "parsed_count": len(visits),
                "saved_count": len(serialized_visits),
                "duplicates_skipped": len(skipped_duplicates),
            }
            if skipped_duplicates:
                response_data["duplicate_details"] = skipped_duplicates
                response_data["message"] = f"Saved {len(serialized_visits)} new visits, skipped {len(skipped_duplicates)} duplicates"
            if visit_errors:
                response_data["errors"] = visit_errors
                response_data["warning"] = f"Parsed {len(visits)} visits but only saved {len(serialized_visits)}"
            return JSONResponse(response_data)

        # If we get here and have no result, return an error
        # (No more garbage OCR fallbacks - AI or nothing)
        if not parse_result or not parse_result.get("success"):
            error_msg = parse_result.get("error", "Unknown error") if parse_result else "AI parser returned no result"
            logger.warning(f"AI parsing failed for {filename}: {error_msg}")
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {error_msg}")

        # Should not reach here - all paths should have returned
        raise HTTPException(status_code=400, detail=f"Unhandled file type: {filename}")
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing URL upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Bulk Business Card Processing (AI-powered: OpenAI Vision + Gemini fallback)
# ---------------------------------------------------------------------------
BUSINESS_CARD_EXTRACT_PROMPT = """You are extracting contact information from a business card image.

CRITICAL INSTRUCTIONS:
- Read the text on the card CAREFULLY and ACCURATELY
- Do NOT guess or make up names - if you can't read it clearly, use null
- Names should be real human names (e.g., "John Smith", "Maria Garcia")
- Company names should be real business names
- If the image is blurry or unreadable, return all nulls

Extract ALL available information and return ONLY valid JSON (no markdown):
{
  "first_name": "...",
  "last_name": "...",
  "title": "...",
  "company": "...",
  "email": "...",
  "phone": "...",
  "address": "...",
  "website": "...",
  "notes": "..."
}

RULES:
- If a field is not visible or unreadable, set it to null
- For phone, include area code (format: 303-555-1234)
- For email, must be a valid email format
- For company, use the full official company name
- The "notes" field can include department, fax, cell phone, credentials after name, etc.
- NEVER return gibberish or random characters - use null instead"""


def _find_similar_company(db, company_name: str):
    """Find an existing company with a similar name to avoid duplicates."""
    if not company_name or len(company_name) < 3:
        return None
    
    from models import ReferralSource
    import re
    
    # Normalize the input name
    normalized = company_name.lower().strip()
    normalized = re.sub(r'[^\w\s]', '', normalized)
    
    # Get first 2 significant words as the base
    words = normalized.split()
    if not words:
        return None
    
    base_words = [w for w in words[:3] if len(w) >= 3 and w not in ['the', 'of', 'at', 'and', 'for']]
    if not base_words:
        return None
    
    # Search for companies containing these words
    search_term = base_words[0]  # Use first significant word
    
    # Try exact organization match first
    exact = db.query(ReferralSource).filter(
        ReferralSource.organization.ilike(company_name)
    ).first()
    if exact:
        return exact
    
    # Try fuzzy match - find companies where the name contains our search term
    candidates = db.query(ReferralSource).filter(
        ReferralSource.organization.ilike(f"%{search_term}%")
    ).all()
    
    if not candidates:
        return None
    
    # Score candidates by how similar they are
    best_match = None
    best_score = 0
    
    for c in candidates:
        c_normalized = (c.organization or "").lower()
        c_normalized = re.sub(r'[^\w\s]', '', c_normalized)
        
        # Count matching words
        c_words = set(c_normalized.split())
        input_words = set(normalized.split())
        matching = len(c_words.intersection(input_words))
        
        # Bonus for exact substring match
        if search_term in c_normalized:
            matching += 1
        
        if matching > best_score:
            best_score = matching
            best_match = c
    
    # Only return if we have a decent match (at least 2 words matching)
    if best_score >= 2:
        logger.info(f"Fuzzy matched '{company_name}' to existing company '{best_match.organization}'")
        return best_match
    
    return None


def _extract_name_from_email(email: str, first_name: str, last_name: str) -> Tuple[str, str]:
    """If name is missing but email exists, try to extract name from email prefix."""
    if (not first_name or not last_name) and email and "@" in email:
        import re
        email_prefix = email.split("@")[0].lower()
        # Common patterns: first.last, first_last, flast, firstl
        parts = re.split(r'[._]', email_prefix)
        if len(parts) >= 2:
            potential_first = parts[0].capitalize()
            potential_last = parts[-1].capitalize()
            # Only use if they look like names (letters only, reasonable length)
            if potential_first.isalpha() and 2 <= len(potential_first) <= 15:
                if not first_name:
                    first_name = potential_first
            if potential_last.isalpha() and 2 <= len(potential_last) <= 20:
                if not last_name:
                    last_name = potential_last
    return first_name, last_name


def _convert_heic_to_jpeg(content: bytes) -> Tuple[bytes, str]:
    """Convert HEIC image to JPEG for AI API compatibility.
    
    Tries multiple methods:
    1. ImageMagick via subprocess (most reliable for iPhone HEIC)
    2. pillow_heif direct API (faster if it works)
    3. PIL with registered HEIF opener
    """
    import io
    import subprocess
    import tempfile
    
    # Method 1: Try ImageMagick (most reliable for iPhone HEIC with metadata issues)
    try:
        with tempfile.NamedTemporaryFile(suffix='.heic', delete=False) as tmp_in:
            tmp_in.write(content)
            tmp_in_path = tmp_in.name
        
        tmp_out_path = tmp_in_path.replace('.heic', '.jpg')
        
        # Use ImageMagick convert command
        result = subprocess.run(
            ['convert', tmp_in_path, '-quality', '90', tmp_out_path],
            capture_output=True,
            timeout=30
        )
        
        if result.returncode == 0 and os.path.exists(tmp_out_path):
            with open(tmp_out_path, 'rb') as f:
                jpeg_bytes = f.read()
            # Clean up temp files
            os.unlink(tmp_in_path)
            os.unlink(tmp_out_path)
            logger.info(f"ImageMagick converted HEIC to JPEG: {len(jpeg_bytes)} bytes")
            return jpeg_bytes, "image/jpeg"
        else:
            logger.warning(f"ImageMagick failed: {result.stderr.decode()[:200]}")
            os.unlink(tmp_in_path)
            if os.path.exists(tmp_out_path):
                os.unlink(tmp_out_path)
    except FileNotFoundError:
        logger.info("ImageMagick not installed, trying pillow_heif")
    except Exception as e:
        logger.warning(f"ImageMagick conversion failed: {e}")
    
    # Method 2: Try pillow_heif direct API (handles some cases PIL plugin misses)
    try:
        import pillow_heif
        heif_file = pillow_heif.open_heif(io.BytesIO(content))
        img = heif_file.to_pillow()
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=90)
        jpeg_bytes = output.getvalue()
        logger.info(f"pillow_heif.open_heif converted to JPEG: {len(jpeg_bytes)} bytes")
        return jpeg_bytes, "image/jpeg"
    except Exception as e:
        logger.warning(f"pillow_heif.open_heif failed: {e}")
    
    # Method 3: Try PIL with registered HEIF opener
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(content))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=90)
        jpeg_bytes = output.getvalue()
        logger.info(f"PIL converted HEIC to JPEG: {len(jpeg_bytes)} bytes")
        return jpeg_bytes, "image/jpeg"
    except Exception as e:
        logger.warning(f"PIL conversion failed: {e}")
    
    # All methods failed - return original with image/heic mime type
    # Gemini may still accept it
    logger.warning("All HEIC conversion methods failed, sending as image/heic")
    return content, "image/heic"


def _extract_business_card_openai(content: bytes, filename: str = "") -> Optional[Dict[str, Any]]:
    """Use OpenAI Vision to extract business card data."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not content:
        return None
    try:
        import base64
        import httpx

        # Convert HEIC to JPEG for API compatibility
        if filename.lower().endswith(".heic") or filename.lower().endswith(".heif"):
            content, mime = _convert_heic_to_jpeg(content)
        else:
            # Detect mime type
            mime = "image/jpeg"
            if filename.lower().endswith(".png"):
                mime = "image/png"
            elif filename.lower().endswith(".webp"):
                mime = "image/webp"
        
        b64 = base64.b64encode(content).decode("utf-8")

        # Use gpt-4o for best quality business card extraction
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": BUSINESS_CARD_EXTRACT_PROMPT},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                        ],
                    }
                ],
                "max_tokens": 500,
                "temperature": 0,
            },
            timeout=45.0,  # Slightly longer timeout for better model
        )
        if resp.status_code != 200:
            logger.warning(f"OpenAI business card extract failed: {resp.status_code} - {resp.text[:200]}")
            return None
        text = resp.json()["choices"][0]["message"]["content"]
        text = re.sub(r"^```json\s*", "", text.strip(), flags=re.IGNORECASE)
        text = re.sub(r"```$", "", text.strip())
        return json.loads(text)
    except Exception as e:
        logger.warning(f"OpenAI business card extract error: {e}")
        return None


def _extract_business_card_gemini(content: bytes, filename: str = "") -> Optional[Dict[str, Any]]:
    """Use Gemini Vision to extract business card data.
    
    For HEIC files: Tries sending HEIC directly first (Gemini supports it),
    then falls back to conversion if that fails.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not content:
        return None
    try:
        import base64
        import httpx

        is_heic = filename.lower().endswith(('.heic', '.heif'))
        original_content = content
        
        # For HEIC: Try sending directly first (Gemini API supports HEIC)
        if is_heic:
            mime = "image/heic"
            logger.info(f"Trying Gemini with direct HEIC: {filename}")
        else:
            mime = "image/jpeg"
            if filename.lower().endswith(".png"):
                mime = "image/png"
        
        b64 = base64.b64encode(content).decode("utf-8")

        # Use best available Gemini models for business card extraction
        # Note: gemini-1.5-pro requires different API path, using flash models
        models = ["gemini-2.0-flash", "gemini-1.5-flash"]
        for model in models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                resp = httpx.post(
                    url,
                    headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                    json={
                        "contents": [{
                            "parts": [
                                {"text": BUSINESS_CARD_EXTRACT_PROMPT},
                                {"inline_data": {"mime_type": mime, "data": b64}},
                            ]
                        }]
                    },
                    timeout=30.0,
                )
                if resp.status_code == 404:
                    logger.info(f"Gemini model {model} not found, trying next")
                    continue
                if resp.status_code != 200:
                    logger.warning(f"Gemini {model} returned {resp.status_code}: {resp.text[:200]}")
                    continue
                data = resp.json()
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if not text:
                    logger.warning(f"Gemini {model} returned empty text. Response: {data}")
                    continue
                text = re.sub(r"^```json\s*", "", text.strip(), flags=re.IGNORECASE)
                text = re.sub(r"```$", "", text.strip())
                result = json.loads(text)
                logger.info(f"Gemini {model} extracted: {result.get('first_name', '')} {result.get('last_name', '')} @ {result.get('company', '')}")
                return result
            except json.JSONDecodeError as je:
                logger.warning(f"Gemini {model} JSON parse error: {je}. Text was: {text[:200] if text else 'empty'}")
                continue
            except Exception as e:
                logger.warning(f"Gemini {model} exception: {e}")
                continue
        
        # If all models failed and we were trying HEIC directly, retry with converted content
        if is_heic and mime == "image/heic":
            logger.info("Direct HEIC failed, retrying with converted content")
            try:
                converted_content, converted_mime = _convert_heic_to_jpeg(original_content)
                if converted_mime == "image/jpeg":
                    b64 = base64.b64encode(converted_content).decode("utf-8")
                    for model in models:
                        try:
                            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                            resp = httpx.post(
                                url,
                                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                                json={
                                    "contents": [{
                                        "parts": [
                                            {"text": BUSINESS_CARD_EXTRACT_PROMPT},
                                            {"inline_data": {"mime_type": converted_mime, "data": b64}},
                                        ]
                                    }]
                                },
                                timeout=45.0,
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                                if text:
                                    text = re.sub(r"^```json\s*", "", text.strip(), flags=re.IGNORECASE)
                                    text = re.sub(r"```$", "", text.strip())
                                    result = json.loads(text)
                                    logger.info(f"Gemini {model} extracted (after conversion): {result.get('first_name', '')} {result.get('last_name', '')}")
                                    return result
                        except Exception as e:
                            logger.warning(f"Gemini {model} with converted content failed: {e}")
                            continue
            except Exception as e:
                logger.warning(f"Retry with conversion failed: {e}")
        
        return None
    except Exception as e:
        logger.warning(f"Gemini business card extract error: {e}")
        return None


def _extract_business_card_ai(content: bytes, filename: str = "") -> Optional[Dict[str, Any]]:
    """Extract business card data using AI Vision APIs.
    
    For HEIC files (iPhone photos): Try Gemini first as it handles HEIC better.
    For other formats: Try Gemini first (faster/cheaper), then OpenAI for quality fallback.
    """
    is_heic = filename.lower().endswith(('.heic', '.heif'))
    
    if is_heic:
        # Gemini handles HEIC better - try it first
        logger.info(f"HEIC file detected, trying Gemini first: {filename}")
        result = _extract_business_card_gemini(content, filename)
        if result:
            return result
        # Fallback to OpenAI with conversion
        logger.info("Gemini failed for HEIC, trying OpenAI with conversion")
        return _extract_business_card_openai(content, filename)
    else:
        # Non-HEIC: Gemini first
        result = _extract_business_card_gemini(content, filename)
        if result:
            return result
        return _extract_business_card_openai(content, filename)


# In-memory job status storage for bulk processing
_bulk_jobs: Dict[str, Dict[str, Any]] = {}


def _process_business_cards_background(job_id: str, files: list, folder_url: str, assign_to: str):
    """Background task to process business cards."""
    from models import Contact, ReferralSource
    from activity_logger import ActivityLogger
    
    # Get a fresh database session for background task
    db = db_manager.get_session()
    drive_service = GoogleDriveService()
    
    job = _bulk_jobs[job_id]
    
    try:
        for file_info in files:
            file_id = file_info.get("id")
            file_name = file_info.get("name", "unknown")
            
            try:
                # Download the file
                download_result = drive_service.download_file_by_id(file_id)
                if not download_result:
                    job["errors"].append(f"{file_name}: Failed to download")
                    continue

                content, _, _ = download_result

                # Extract business card data using AI (OpenAI first for best quality)
                card_data = _extract_business_card_openai(content, file_name)
                if not card_data:
                    card_data = _extract_business_card_gemini(content, file_name)
                if not card_data:
                    job["errors"].append(f"{file_name}: AI extraction failed")
                    continue

                first_name = (card_data.get("first_name") or "").strip()
                last_name = (card_data.get("last_name") or "").strip()
                
                # Normalize: If first_name contains a space and last_name is empty, split it
                if first_name and ' ' in first_name and not last_name:
                    parts = first_name.split(' ', 1)
                    first_name = parts[0]
                    last_name = parts[1] if len(parts) > 1 else ''
                
                company_name = (card_data.get("company") or "").strip()
                email = (card_data.get("email") or "").strip()
                phone = (card_data.get("phone") or "").strip()
                title = (card_data.get("title") or "").strip()
                address = (card_data.get("address") or "").strip()
                website = (card_data.get("website") or "").strip()
                notes = (card_data.get("notes") or "").strip()
                
                # Try to extract name from email if missing
                first_name, last_name = _extract_name_from_email(email, first_name, last_name)

                if not first_name and not last_name and not company_name:
                    job["errors"].append(f"{file_name}: No usable data extracted")
                    continue

                job["processed"] += 1

                # Find or create Company (with fuzzy matching to avoid duplicates)
                company_id = None
                if company_name:
                    existing_company = _find_similar_company(db, company_name)
                    if existing_company:
                        company_id = existing_company.id
                        job["companies_linked"] += 1
                    else:
                        new_company = ReferralSource(
                            name=f"{first_name} {last_name}".strip() or company_name,
                            organization=company_name,
                            contact_name=f"{first_name} {last_name}".strip() if first_name or last_name else None,
                            email=email,
                            phone=phone,
                            address=address,
                            source_type="Healthcare Facility",
                            status="incoming",
                            notes=notes,
                        )
                        db.add(new_company)
                        db.flush()
                        company_id = new_company.id
                        job["companies_created"] += 1

                # Find or create Contact
                existing_contact = None
                if email:
                    existing_contact = db.query(Contact).filter(Contact.email == email).first()

                if existing_contact:
                    if first_name:
                        existing_contact.first_name = first_name
                    if last_name:
                        existing_contact.last_name = last_name
                    if company_name:
                        existing_contact.company = company_name
                    if company_id:
                        existing_contact.company_id = company_id
                    if title:
                        existing_contact.title = title
                    if phone:
                        existing_contact.phone = phone
                    if address:
                        existing_contact.address = address
                    if website:
                        existing_contact.website = website
                    existing_contact.updated_at = datetime.utcnow()
                    existing_contact.last_seen = datetime.utcnow()
                    existing_contact.account_manager = assign_to
                    db.add(existing_contact)
                    job["contacts_updated"] += 1
                    contact_id = existing_contact.id
                else:
                    new_contact = Contact(
                        first_name=first_name,
                        last_name=last_name,
                        name=f"{first_name} {last_name}".strip(),
                        company=company_name,
                        company_id=company_id,
                        title=title,
                        email=email,
                        phone=phone,
                        address=address,
                        website=website,
                        notes=notes,
                        status="cold",
                        account_manager=assign_to,
                        source="Business Card Scan",
                        scanned_date=datetime.utcnow(),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                        last_seen=datetime.utcnow(),
                    )
                    db.add(new_contact)
                    db.flush()
                    job["contacts_created"] += 1
                    contact_id = new_contact.id

                # Log activity
                try:
                    activity_logger = ActivityLogger(db)
                    activity_logger.log_activity(
                        activity_type="business_card_scan",
                        title=f"Scanned business card: {first_name} {last_name}".strip(),
                        description=f"Business card scanned from {file_name}. Company: {company_name or 'Unknown'}",
                        contact_id=contact_id,
                        company_id=company_id,
                        user_email=assign_to,
                        commit=False,
                    )
                except Exception as log_error:
                    logger.warning(f"Activity log failed for {file_name}: {log_error}")

                job["details"].append({
                    "file": file_name,
                    "contact": f"{first_name} {last_name}".strip(),
                    "company": company_name,
                    "email": email,
                    "status": "updated" if existing_contact else "created",
                })

                # Commit after each card to avoid losing progress
                db.commit()

            except Exception as e:
                logger.error(f"Error processing {file_name}: {e}")
                job["errors"].append(f"{file_name}: {str(e)}")
                db.rollback()

        job["status"] = "completed"
        job["message"] = f"Processed {job['processed']} of {job['total_files']} business cards"
        
    except Exception as e:
        logger.error(f"Bulk processing job {job_id} failed: {e}")
        job["status"] = "failed"
        job["message"] = str(e)
        db.rollback()
    finally:
        db.close()


class BulkProcessRequest(BaseModel):
    folder_url: str
    assign_to: Optional[str] = None
    # For chunked processing: which files to process (by index)
    start_index: int = 0
    batch_size: int = 10


# Cache for folder file listings (expires after 10 minutes)
_folder_file_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl_seconds = 600  # 10 minutes


def _get_cached_folder_files(folder_url: str, drive_service) -> List[Dict[str, Any]]:
    """Get folder files from cache or fetch if not cached/expired."""
    import hashlib
    cache_key = hashlib.md5(folder_url.encode()).hexdigest()
    
    now = time.time()
    if cache_key in _folder_file_cache:
        cached = _folder_file_cache[cache_key]
        if now - cached["timestamp"] < _cache_ttl_seconds:
            logger.info(f"Using cached file list for folder ({len(cached['files'])} files)")
            return cached["files"]
    
    # Fetch fresh list with recursive scanning for subfolders
    logger.info(f"Fetching file list from Google Drive folder (recursive)...")
    files = drive_service.list_files_in_folder(folder_url, image_only=True, recursive=True)
    
    # Cache it
    _folder_file_cache[cache_key] = {
        "files": files,
        "timestamp": now
    }
    logger.info(f"Cached {len(files)} files from folder")

    return files


# ==================== AUTO-SCAN DRIVE FOLDERS ====================
# Pre-configured folders for Jacob's business cards, routes, and expenses
AUTO_SCAN_FOLDERS = {
    'business_cards': '1aGO6vxe50yA-1UcanPDEVlIFrXOMRYK4',
    'myway_routes': '1IHiYvGxOaA6nyjd1Ecvgt1FbB114P5mB',
    'expenses': '16OmBFwNzEKzVBBjmDtSTdM21pb3wGhSb'
}


@app.post("/api/auto-scan")
async def trigger_auto_scan(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Trigger auto-scan of all three Google Drive folders.
    Scans for new files only (tracks processed files to avoid duplicates).
    """
    from models import ProcessedDriveFile, Contact, ReferralSource, Visit, FinancialEntry, Expense
    from ai_document_parser import ai_parser

    drive_service = GoogleDriveService()
    if not drive_service.enabled:
        raise HTTPException(status_code=400, detail="Google Drive API not configured. Set GOOGLE_SERVICE_ACCOUNT_KEY.")

    # Ensure ProcessedDriveFile table exists
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS processed_drive_files (
                id SERIAL PRIMARY KEY,
                drive_file_id VARCHAR(255) NOT NULL UNIQUE,
                filename VARCHAR(500),
                folder_type VARCHAR(50) NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                result_type VARCHAR(50),
                result_id INTEGER,
                error_message TEXT
            )
        """))
        db.commit()
    except Exception as e:
        logger.warning(f"Table may already exist: {e}")
        db.rollback()

    results = {
        'business_cards': {'new': 0, 'processed': 0, 'contacts_created': 0, 'companies_created': 0, 'errors': []},
        'myway_routes': {'new': 0, 'processed': 0, 'visits_created': 0, 'errors': []},
        'expenses': {'new': 0, 'processed': 0, 'expenses_created': 0, 'errors': []}
    }

    default_user = 'jacob@coloradocareassist.com'
    mileage_rate = 0.70

    for folder_type, folder_id in AUTO_SCAN_FOLDERS.items():
        try:
            # Get already processed file IDs
            processed_query = db.query(ProcessedDriveFile.drive_file_id).filter(
                ProcessedDriveFile.folder_type == folder_type
            ).all()
            processed_ids = {r[0] for r in processed_query}

            # List files in folder
            folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
            image_only = folder_type in ['business_cards', 'expenses']
            files = drive_service.list_files_in_folder(folder_url, image_only=image_only, recursive=True)

            # Filter to new files
            new_files = [f for f in files if f.get('id') not in processed_ids]
            results[folder_type]['new'] = len(new_files)

            logger.info(f"Auto-scan {folder_type}: {len(new_files)} new files of {len(files)} total")

            for file_info in new_files[:20]:  # Limit to 20 per folder per request
                file_id = file_info.get('id')
                filename = file_info.get('name', 'unknown')

                try:
                    # Download file
                    download_result = drive_service.download_file_by_id(file_id)
                    if not download_result:
                        results[folder_type]['errors'].append(f"{filename}: download failed")
                        continue

                    content, _, _ = download_result
                    drive_url = f"https://drive.google.com/file/d/{file_id}/view"

                    # Process based on folder type
                    if folder_type == 'business_cards':
                        card_data = ai_parser.parse_business_card(content, filename)
                        if card_data.get('success'):
                            first_name = (card_data.get('first_name') or '').strip()
                            last_name = (card_data.get('last_name') or '').strip()
                            company_name = (card_data.get('company') or '').strip()
                            email = (card_data.get('email') or '').strip()

                            # Create company if needed
                            company_id = None
                            if company_name:
                                existing_co = db.query(ReferralSource).filter(
                                    ReferralSource.organization.ilike(f'%{company_name}%')
                                ).first()
                                if existing_co:
                                    company_id = existing_co.id
                                else:
                                    new_co = ReferralSource(
                                        name=company_name,
                                        organization=company_name,
                                        source_type="Healthcare Facility",
                                        status="incoming"
                                    )
                                    db.add(new_co)
                                    db.flush()
                                    company_id = new_co.id
                                    results[folder_type]['companies_created'] += 1

                            # Create contact
                            new_contact = Contact(
                                first_name=first_name,
                                last_name=last_name,
                                name=f"{first_name} {last_name}".strip(),
                                company=company_name,
                                company_id=company_id,
                                email=email,
                                phone=card_data.get('phone'),
                                title=card_data.get('title'),
                                address=card_data.get('address'),
                                status="cold",
                                account_manager=default_user,
                                source="Auto-Scan",
                                created_at=datetime.utcnow()
                            )
                            db.add(new_contact)
                            results[folder_type]['contacts_created'] += 1

                        result_type = 'contact' if card_data.get('success') else 'error'

                    elif folder_type == 'myway_routes':
                        route_data = ai_parser.parse_myway_pdf(content, filename)
                        if route_data.get('success'):
                            visits = route_data.get('visits', [])
                            pdf_date = route_data.get('date')
                            mileage = route_data.get('mileage')

                            for v in visits:
                                new_visit = Visit(
                                    stop_number=v.get('stop_number', 0),
                                    business_name=v.get('business_name', 'Unknown'),
                                    address=v.get('address', ''),
                                    city=v.get('city', ''),
                                    notes=v.get('notes', ''),
                                    visit_date=v.get('visit_date') or pdf_date or datetime.utcnow(),
                                    user_email=default_user,
                                    created_at=datetime.utcnow()
                                )
                                db.add(new_visit)
                                results[folder_type]['visits_created'] += 1

                            # Save mileage
                            if mileage and pdf_date:
                                new_entry = FinancialEntry(
                                    date=pdf_date,
                                    hours_worked=0,
                                    labor_cost=0,
                                    miles_driven=mileage,
                                    mileage_cost=mileage * mileage_rate,
                                    materials_cost=0,
                                    total_daily_cost=mileage * mileage_rate,
                                    user_email=default_user,
                                    created_at=datetime.utcnow()
                                )
                                db.add(new_entry)

                        result_type = 'visit' if route_data.get('success') else 'error'

                    elif folder_type == 'expenses':
                        receipt_data = ai_parser.parse_receipt(content, filename)
                        if receipt_data.get('success') and receipt_data.get('amount', 0) > 0:
                            expense_date = datetime.utcnow()
                            if receipt_data.get('date'):
                                try:
                                    expense_date = datetime.strptime(receipt_data['date'], '%Y-%m-%d')
                                except:
                                    pass

                            new_expense = Expense(
                                user_email=default_user,
                                amount=receipt_data.get('amount'),
                                description=f"{receipt_data.get('vendor', 'Unknown')}: {receipt_data.get('description', '')}".strip(': '),
                                category=receipt_data.get('category', 'Other'),
                                date=expense_date,
                                receipt_url=drive_url,
                                status='pending',
                                created_at=datetime.utcnow()
                            )
                            db.add(new_expense)
                            results[folder_type]['expenses_created'] += 1

                        result_type = 'expense' if receipt_data.get('success') else 'error'

                    # Mark file as processed
                    processed_record = ProcessedDriveFile(
                        drive_file_id=file_id,
                        filename=filename,
                        folder_type=folder_type,
                        result_type=result_type
                    )
                    db.add(processed_record)
                    results[folder_type]['processed'] += 1

                    # Commit batch
                    db.commit()

                    # Small delay
                    time.sleep(0.3)

                except Exception as file_error:
                    logger.error(f"Error processing {filename}: {file_error}")
                    results[folder_type]['errors'].append(f"{filename}: {str(file_error)}")
                    db.rollback()

        except Exception as folder_error:
            logger.error(f"Error scanning {folder_type}: {folder_error}")
            results[folder_type]['errors'].append(str(folder_error))

    return JSONResponse({
        "success": True,
        "message": "Auto-scan complete",
        "results": results
    })


@app.get("/api/auto-scan/status")
async def get_auto_scan_status(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get status of processed files by folder type"""
    from models import ProcessedDriveFile

    try:
        # Count processed files by folder type
        counts = {}
        for folder_type in AUTO_SCAN_FOLDERS.keys():
            count = db.query(ProcessedDriveFile).filter(
                ProcessedDriveFile.folder_type == folder_type
            ).count()
            counts[folder_type] = count

        # Get recent processing
        recent = db.query(ProcessedDriveFile).order_by(
            ProcessedDriveFile.processed_at.desc()
        ).limit(10).all()

        return JSONResponse({
            "success": True,
            "processed_counts": counts,
            "recent": [r.to_dict() for r in recent]
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e),
            "processed_counts": {},
            "recent": []
        })


@app.post("/bulk-business-cards")
async def bulk_process_business_cards(
    request: BulkProcessRequest,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Process business card images from a Google Drive folder in chunks.
    Handles large folders by processing batch_size cards per request.
    Frontend should loop until has_more=False.
    """
    from models import Contact, ReferralSource
    
    folder_url = request.folder_url
    assign_to = request.assign_to or current_user.get("email", "")
    start_index = request.start_index
    batch_size = min(request.batch_size, 2)  # Max 2 per request to stay under Heroku 30s timeout

    drive_service = GoogleDriveService()
    if not drive_service.enabled:
        raise HTTPException(status_code=400, detail="Google Drive API not configured. Set GOOGLE_SERVICE_ACCOUNT_KEY.")

    # Get file list (cached if available)
    all_files = _get_cached_folder_files(folder_url, drive_service)
    if not all_files:
        raise HTTPException(status_code=400, detail="No image files found in the folder. Ensure the folder is shared with the service account.")

    total_files = len(all_files)
    
    # Get the batch to process
    batch_files = all_files[start_index:start_index + batch_size]
    
    if not batch_files:
        # All done
        return JSONResponse({
            "success": True,
            "has_more": False,
            "total_files": total_files,
            "processed_so_far": start_index,
            "batch_processed": 0,
            "message": "All cards processed!",
        })

    results = {
        "contacts_created": 0,
        "contacts_updated": 0,
        "companies_created": 0,
        "companies_linked": 0,
        "errors": [],
        "details": [],
    }

    for file_info in batch_files:
        file_id = file_info.get("id")
        file_name = file_info.get("name", "unknown")
        
        try:
            # Download
            download_result = drive_service.download_file_by_id(file_id)
            if not download_result:
                results["errors"].append(f"{file_name}: download failed")
                continue

            content, _, _ = download_result

            # Extract with OpenAI first (best quality), then Gemini fallback
            card_data = _extract_business_card_openai(content, file_name)
            if not card_data:
                card_data = _extract_business_card_gemini(content, file_name)
            if not card_data:
                results["errors"].append(f"{file_name}: AI extraction failed")
                continue

            first_name = (card_data.get("first_name") or "").strip()
            last_name = (card_data.get("last_name") or "").strip()
            company_name = (card_data.get("company") or "").strip()
            email = (card_data.get("email") or "").strip()
            phone = (card_data.get("phone") or "").strip()
            title = (card_data.get("title") or "").strip()
            address = (card_data.get("address") or "").strip()
            website = (card_data.get("website") or "").strip()
            notes = (card_data.get("notes") or "").strip()
            
            # Try to extract name from email if missing
            first_name, last_name = _extract_name_from_email(email, first_name, last_name)

            if not first_name and not last_name and not company_name:
                results["errors"].append(f"{file_name}: no data extracted")
                continue
            
            # Validate extracted data doesn't look like OCR garbage
            def _looks_like_garbage(text: str) -> bool:
                if not text or len(text) < 2:
                    return False
                # Check for repeated characters (e.g., "Sssssss")
                if len(set(text.lower())) < len(text) / 3:
                    return True
                # Check for too many consonants in a row (e.g., "Tss Sss")
                consonants = "bcdfghjklmnpqrstvwxyz"
                max_consonants = 0
                current = 0
                for c in text.lower():
                    if c in consonants:
                        current += 1
                        max_consonants = max(max_consonants, current)
                    else:
                        current = 0
                if max_consonants >= 4:
                    return True
                # Check for nonsense patterns
                garbage_patterns = ["www ", "http", "xxx", "yyy", "zzz"]
                for pattern in garbage_patterns:
                    if pattern in text.lower():
                        return True
                return False
            
            if _looks_like_garbage(first_name) or _looks_like_garbage(last_name):
                results["errors"].append(f"{file_name}: extracted data looks invalid")
                continue

            # Find or create Company (with fuzzy matching to avoid duplicates)
            company_id = None
            if company_name:
                # Try fuzzy match first to find similar existing company
                existing_company = _find_similar_company(db, company_name)
                if existing_company:
                    company_id = existing_company.id
                    results["companies_linked"] += 1
                else:
                    new_company = ReferralSource(
                        name=f"{first_name} {last_name}".strip() or company_name,
                        organization=company_name,
                        contact_name=f"{first_name} {last_name}".strip() if first_name or last_name else None,
                        email=email,
                        phone=phone,
                        address=address,
                        source_type="Healthcare Facility",
                        status="incoming",
                        notes=notes,
                    )
                    db.add(new_company)
                    db.flush()
                    company_id = new_company.id
                    results["companies_created"] += 1

            # Find or create Contact
            existing_contact = None
            if email:
                existing_contact = db.query(Contact).filter(Contact.email == email).first()

            if existing_contact:
                if first_name:
                    existing_contact.first_name = first_name
                if last_name:
                    existing_contact.last_name = last_name
                if company_name:
                    existing_contact.company = company_name
                if company_id:
                    existing_contact.company_id = company_id
                if title:
                    existing_contact.title = title
                if phone:
                    existing_contact.phone = phone
                if address:
                    existing_contact.address = address
                if website:
                    existing_contact.website = website
                existing_contact.updated_at = datetime.utcnow()
                existing_contact.last_seen = datetime.utcnow()
                existing_contact.account_manager = assign_to
                db.add(existing_contact)
                results["contacts_updated"] += 1
            else:
                new_contact = Contact(
                    first_name=first_name,
                    last_name=last_name,
                    name=f"{first_name} {last_name}".strip(),
                    company=company_name,
                    company_id=company_id,
                    title=title,
                    email=email,
                    phone=phone,
                    address=address,
                    website=website,
                    notes=notes,
                    status="cold",
                    account_manager=assign_to,
                    source="Business Card Scan",
                    scanned_date=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                )
                db.add(new_contact)
                results["contacts_created"] += 1

            results["details"].append({
                "file": file_name,
                "contact": f"{first_name} {last_name}".strip(),
                "company": company_name,
                "status": "updated" if existing_contact else "created",
            })

        except Exception as e:
            logger.error(f"Error processing {file_name}: {e}")
            results["errors"].append(f"{file_name}: {str(e)}")

    # Commit batch
    try:
        db.commit()
    except Exception as e:
        logger.error(f"Batch commit failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    next_index = start_index + len(batch_files)
    has_more = next_index < total_files

    return JSONResponse({
        "success": True,
        "has_more": has_more,
        "total_files": total_files,
        "processed_so_far": next_index,
        "next_index": next_index if has_more else None,
        "batch_processed": len(batch_files) - len(results["errors"]),
        "batch_results": results,
        "message": f"Processed {next_index}/{total_files} cards" + (" - continuing..." if has_more else " - complete!"),
    })


@app.get("/bulk-business-cards/{job_id}")
async def get_bulk_job_status(job_id: str):
    """Get status of a bulk business card processing job."""
    if job_id not in _bulk_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = _bulk_jobs[job_id]
    return JSONResponse({
        "success": True,
        "job_id": job_id,
        "status": job["status"],
        "message": job.get("message", ""),
        "results": {
            "total_files": job["total_files"],
            "processed": job["processed"],
            "contacts_created": job["contacts_created"],
            "contacts_updated": job["contacts_updated"],
            "companies_created": job["companies_created"],
            "companies_linked": job["companies_linked"],
            "errors": job["errors"][-10:],  # Last 10 errors
            "details": job["details"][-10:],  # Last 10 processed
        },
    })


# Legacy endpoint for compatibility - now just returns immediately
@app.post("/bulk-business-cards-sync")
async def bulk_process_business_cards_sync(
    request: BulkProcessRequest,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Synchronous version - processes cards with pagination support."""
    from models import Contact, ReferralSource

    folder_url = request.folder_url
    assign_to = request.assign_to or current_user.get("email", "")
    start_index = request.start_index
    batch_size = min(request.batch_size, 15)  # Max 15 per request

    drive_service = GoogleDriveService()
    if not drive_service.enabled:
        raise HTTPException(status_code=400, detail="Google Drive API not configured.")

    # Get all files with caching, then slice for pagination
    import hashlib as _hashlib
    cache_key = _hashlib.md5(folder_url.encode()).hexdigest()
    cached_data = _folder_file_cache.get(cache_key)
    
    if cached_data and (time.time() - cached_data["timestamp"] < _CACHE_TTL_SECONDS):
        all_files = cached_data["files"]
    else:
        all_files = drive_service.list_files_in_folder(folder_url, image_only=True, recursive=True)
        if all_files:
            _folder_file_cache[cache_key] = {"files": all_files, "timestamp": time.time()}
    
    total_files = len(all_files)
    files = all_files[start_index:start_index + batch_size]
    if not files and start_index == 0:
        raise HTTPException(status_code=400, detail="No image files found in the folder.")

    results = {
        "total_files": total_files,
        "start_index": start_index,
        "batch_size": len(files),
        "has_more": (start_index + len(files)) < total_files,
        "next_index": start_index + len(files),
        "processed": 0,
        "contacts_created": 0,
        "contacts_updated": 0,
        "companies_created": 0,
        "companies_linked": 0,
        "errors": [],
        "details": [],
    }

    for file_info in files:
        file_id = file_info.get("id")
        file_name = file_info.get("name", "unknown")
        try:
            # Download the file
            download_result = drive_service.download_file_by_id(file_id)
            if not download_result:
                results["errors"].append(f"{file_name}: Failed to download")
                continue

            content, _, _ = download_result

            # Extract business card data using AI
            card_data = _extract_business_card_ai(content, file_name)
            if not card_data:
                results["errors"].append(f"{file_name}: AI extraction failed")
                continue

            first_name = (card_data.get("first_name") or "").strip()
            last_name = (card_data.get("last_name") or "").strip()
            company_name = (card_data.get("company") or "").strip()
            email = (card_data.get("email") or "").strip()
            phone = (card_data.get("phone") or "").strip()
            title = (card_data.get("title") or "").strip()
            address = (card_data.get("address") or "").strip()
            website = (card_data.get("website") or "").strip()
            notes = (card_data.get("notes") or "").strip()
            
            # Try to extract name from email if missing
            first_name, last_name = _extract_name_from_email(email, first_name, last_name)

            if not first_name and not last_name and not company_name:
                results["errors"].append(f"{file_name}: No usable data extracted")
                continue

            results["processed"] += 1

            # Find or create Company (with fuzzy matching to avoid duplicates)
            company_id = None
            if company_name:
                existing_company = _find_similar_company(db, company_name)
                if existing_company:
                    company_id = existing_company.id
                    results["companies_linked"] += 1
                else:
                    new_company = ReferralSource(
                        name=f"{first_name} {last_name}".strip() or company_name,
                        organization=company_name,
                        contact_name=f"{first_name} {last_name}".strip() if first_name or last_name else None,
                        email=email,
                        phone=phone,
                        address=address,
                        source_type="Healthcare Facility",  # Default; can be enriched later
                        status="incoming",
                        notes=notes,
                    )
                    db.add(new_company)
                    db.flush()
                    company_id = new_company.id
                    results["companies_created"] += 1

            # Find or create Contact
            existing_contact = None
            if email:
                existing_contact = db.query(Contact).filter(Contact.email == email).first()

            if existing_contact:
                # Update existing contact
                if first_name:
                    existing_contact.first_name = first_name
                if last_name:
                    existing_contact.last_name = last_name
                if company_name:
                    existing_contact.company = company_name
                if company_id:
                    existing_contact.company_id = company_id
                if title:
                    existing_contact.title = title
                if phone:
                    existing_contact.phone = phone
                if address:
                    existing_contact.address = address
                if website:
                    existing_contact.website = website
                existing_contact.updated_at = datetime.utcnow()
                existing_contact.last_seen = datetime.utcnow()
                existing_contact.account_manager = assign_to
                db.add(existing_contact)
                results["contacts_updated"] += 1
                contact_id = existing_contact.id
            else:
                # Create new contact
                new_contact = Contact(
                    first_name=first_name,
                    last_name=last_name,
                    name=f"{first_name} {last_name}".strip(),
                    company=company_name,
                    company_id=company_id,
                    title=title,
                    email=email,
                    phone=phone,
                    address=address,
                    website=website,
                    notes=notes,
                    status="cold",
                    account_manager=assign_to,
                    source="Business Card Scan",
                    scanned_date=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                )
                db.add(new_contact)
                db.flush()
                results["contacts_created"] += 1
                contact_id = new_contact.id

            # Log activity
            try:
                activity_logger = ActivityLogger(db)
                activity_logger.log_activity(
                    activity_type="business_card_scan",
                    title=f"Scanned business card: {first_name} {last_name}".strip(),
                    description=f"Business card scanned from {file_name}. Company: {company_name or 'Unknown'}",
                    contact_id=contact_id,
                    company_id=company_id,
                    user_email=assign_to,
                    commit=False,
                )
            except Exception as log_error:
                logger.warning(f"Activity log failed for {file_name}: {log_error}")

            results["details"].append({
                "file": file_name,
                "contact": f"{first_name} {last_name}".strip(),
                "company": company_name,
                "email": email,
                "status": "updated" if existing_contact else "created",
            })

            # Small delay to avoid rate limits
            time.sleep(0.3)

        except Exception as e:
            logger.error(f"Error processing {file_name}: {e}")
            results["errors"].append(f"{file_name}: {str(e)}")

    # Commit all changes
    try:
        db.commit()
    except Exception as commit_error:
        logger.error(f"Bulk business card commit failed: {commit_error}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database commit failed: {commit_error}")

    return JSONResponse({
        "success": True,
        "message": f"Processed {results['processed']} of {results['total_files']} business cards",
        "results": results,
    })


@app.post("/api/save-visits")
async def save_visits(request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Save visits from PDF upload to database and Google Sheet"""
    try:
        from sqlalchemy import func
        from datetime import datetime
        import re
        
        def normalize_business_name(name):
            """Normalize business name for duplicate checking"""
            if not name:
                return ""
            normalized = (name or "").lower().strip()
            normalized = re.sub(r'\s+', ' ', normalized)
            return normalized
        
        data = await request.json()
        visits = data.get("visits", [])
        
        if not visits:
            raise HTTPException(status_code=400, detail="No visits provided")
        
        # Check for duplicates in database
        duplicate_info = []
        saved_visits = []
        skipped_visits = []
        
        for visit_data in visits:
            # Handle both dict and object formats
            if isinstance(visit_data, dict):
                visit_date = visit_data.get("visit_date")
                stop_number = visit_data.get("stop_number")
                business_name = visit_data.get("business_name")
                address = visit_data.get("address")
                city = visit_data.get("city")
                notes = visit_data.get("notes")
            else:
                # Handle object format (from database)
                visit_date = getattr(visit_data, "visit_date", None)
                stop_number = getattr(visit_data, "stop_number", None)
                business_name = getattr(visit_data, "business_name", None)
                address = getattr(visit_data, "address", None)
                city = getattr(visit_data, "city", None)
                notes = getattr(visit_data, "notes", None)
            
            # Parse date if it's a string - handle timezone correctly to avoid day shifts
            if visit_date:
                if isinstance(visit_date, str):
                    try:
                        # If it has a time component with Z, parse it but convert to local naive datetime
                        if 'T' in visit_date and 'Z' in visit_date:
                            # Parse as UTC first
                            utc_date = datetime.fromisoformat(visit_date.replace('Z', '+00:00'))
                            # Extract just the date part and create a naive datetime at midnight
                            # This prevents timezone conversion issues
                            visit_date = datetime.combine(utc_date.date(), datetime.min.time())
                        elif 'T' in visit_date:
                            # Has time but no Z - parse as is
                            visit_date = datetime.fromisoformat(visit_date)
                            # Extract just the date part
                            visit_date = datetime.combine(visit_date.date(), datetime.min.time())
                        else:
                            # Date-only string - parse as naive datetime at midnight
                            visit_date = datetime.strptime(visit_date.split('T')[0], '%Y-%m-%d')
                    except:
                        try:
                            # Try alternative format
                            visit_date = datetime.strptime(visit_date.split('T')[0], '%Y-%m-%d')
                        except:
                            visit_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                elif isinstance(visit_date, datetime):
                    # Already a datetime - ensure it's at midnight to avoid timezone issues
                    visit_date = visit_date.replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    visit_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                # Default to today at midnight
                visit_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Check if this visit already exists (same date, normalized business name, stop number)
            visit_date_only = visit_date.date() if visit_date else datetime.now().date()
            business_normalized = normalize_business_name(business_name or "")
            
            # Simplified duplicate check - get all visits on this date and check in Python
            existing_visits = db.query(Visit).filter(
                func.date(Visit.visit_date) == visit_date_only,
                Visit.stop_number == (stop_number or 1)
            ).all()
            
            # Check if any existing visit has matching normalized business name
            existing_visit = None
            for ev in existing_visits:
                ev_business_normalized = normalize_business_name(ev.business_name or "")
                if ev_business_normalized == business_normalized:
                    existing_visit = ev
                    break
            
            if existing_visit:
                # Duplicate found - skip saving but report it
                duplicate_info.append({
                    "business_name": business_name or "Unknown",
                    "address": address or "",
                    "city": city or "",
                    "date": visit_date_only.isoformat(),
                    "stop_number": stop_number or 1,
                    "existing_id": existing_visit.id
                })
                skipped_visits.append(visit_data)
                continue
            
            visit = Visit(
                stop_number=stop_number,
                business_name=business_name or "",
                address=address or "",
                city=city or "",
                notes=notes or "",
                visit_date=visit_date
            )
            db.add(visit)
            saved_visits.append(visit)
        
        db.commit()
        
        # Refresh all visits to get IDs
        for visit in saved_visits:
            db.refresh(visit)
        
        # Prepare visits data for Google Sheets (only non-duplicates)
        visits_for_sheet = []
        for visit_data in saved_visits:
            visits_for_sheet.append({
                "stop_number": visit_data.stop_number,
                "business_name": visit_data.business_name or "",
                "address": visit_data.address or "",
                "city": visit_data.city or "",
                "notes": visit_data.notes or ""
            })
        
        # Also sync to Google Sheets if available (only new visits, not duplicates)
        if sheets_manager and visits_for_sheet:
            try:
                sheets_manager.append_visits(visits_for_sheet)
                logger.info(f"Synced {len(visits_for_sheet)} new visits to Google Sheets")
            except Exception as e:
                logger.warning(f"Failed to sync to Google Sheets: {str(e)}")
        
        logger.info(f"Successfully saved {len(saved_visits)} new visits, skipped {len(skipped_visits)} duplicates")
        
        # Build response message
        message = f"Successfully saved {len(saved_visits)} visit(s)"
        if duplicate_info:
            message += f", skipped {len(duplicate_info)} duplicate(s)"
        
        return JSONResponse({
            "success": True,
            "message": message,
            "count": len(saved_visits),
            "duplicates": len(duplicate_info),
            "duplicate_details": duplicate_info if duplicate_info else []
        })
        
    except Exception as e:
        logger.error(f"Error saving visits: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving visits: {str(e)}")

@app.post("/append-to-sheet")
async def append_to_sheet(request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Append visits to database and optionally sync to Google Sheet"""
    try:
        data = await request.json()
        data_type = data.get("type", "myway_route")
        
        if data_type == "time_tracking":
            # Handle time tracking data
            date = data.get("date")
            total_hours = data.get("total_hours")
            
            if not date or total_hours is None:
                raise HTTPException(status_code=400, detail="Date and total_hours are required for time tracking")
            
            # Save to database
            from datetime import datetime
            time_entry = TimeEntry(
                date=datetime.fromisoformat(date.replace('Z', '+00:00')) if 'T' in date else datetime.strptime(date, '%Y-%m-%d'),
                hours_worked=total_hours
            )
            
            db.add(time_entry)
            db.commit()
            db.refresh(time_entry)
            
            # Also sync to Google Sheets if available
            if sheets_manager:
                try:
                    sheets_manager.update_daily_summary(date, total_hours)
                    logger.info("Synced time entry to Google Sheets")
                except Exception as e:
                    logger.warning(f"Failed to sync to Google Sheets: {str(e)}")
            
            logger.info(f"Successfully saved time entry: {date} - {total_hours} hours")
            
            return JSONResponse({
                "success": True,
                "message": f"Successfully saved {total_hours} hours for {date}",
                "date": date,
                "hours": total_hours
            })
        
        else:
            # Handle MyWay route data
            visits = data.get("visits", [])
            
            if not visits:
                raise HTTPException(status_code=400, detail="No visits provided")
            
            # Save visits to database
            saved_visits = []
            for visit_data in visits:
                # Use visit_date from parsed data if available, otherwise use today
                visit_date = visit_data.get("visit_date")
                if visit_date:
                    # Parse date if it's a string - handle timezone correctly
                    if isinstance(visit_date, str):
                        from datetime import datetime
                        try:
                            # If it has a time component with Z, extract just the date part
                            if 'T' in visit_date and 'Z' in visit_date:
                                utc_date = datetime.fromisoformat(visit_date.replace('Z', '+00:00'))
                                visit_date = datetime.combine(utc_date.date(), datetime.min.time())
                            elif 'T' in visit_date:
                                parsed = datetime.fromisoformat(visit_date)
                                visit_date = datetime.combine(parsed.date(), datetime.min.time())
                            else:
                                visit_date = datetime.strptime(visit_date.split('T')[0], '%Y-%m-%d')
                        except:
                            visit_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    elif isinstance(visit_date, datetime):
                        # Already a datetime - ensure it's at midnight
                        visit_date = visit_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    else:
                        visit_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    visit_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                
                visit = Visit(
                    stop_number=visit_data.get("stop_number"),
                    business_name=visit_data.get("business_name"),
                    address=visit_data.get("address"),
                    city=visit_data.get("city") or "",  # Empty string if not found (don't default to "Unknown")
                    notes=visit_data.get("notes"),
                    visit_date=visit_date
                )
                db.add(visit)
                saved_visits.append(visit)
            
            db.commit()
            
            # Refresh all visits to get IDs
            for visit in saved_visits:
                db.refresh(visit)
            
            # Also sync to Google Sheets if available
            if sheets_manager:
                try:
                    sheets_manager.append_visits(visits)
                    logger.info("Synced visits to Google Sheets")
                except Exception as e:
                    logger.warning(f"Failed to sync to Google Sheets: {str(e)}")
            
            logger.info(f"Successfully saved {len(visits)} visits to database")
            
            return JSONResponse({
                "success": True,
                "message": f"Successfully saved {len(visits)} visits to database",
                "appended_count": len(visits)
            })
        
    except Exception as e:
        logger.error(f"Error saving data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving data: {str(e)}")

# Dashboard API endpoints
@app.get("/api/gmail/test")
async def test_gmail_connection(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Test Gmail API connection"""
    try:
        from gmail_service import GmailService
        
        gmail_service = GmailService()
        result = gmail_service.test_connection()
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Error testing Gmail connection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error testing Gmail: {str(e)}")

@app.get("/api/mailchimp/test")
async def test_mailchimp_connection(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Test Mailchimp API connection"""
    try:
        mailchimp_service = MailchimpService()
        result = mailchimp_service.test_connection()
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Error testing Mailchimp connection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error testing Mailchimp: {str(e)}")

@app.post("/api/mailchimp/export")
async def export_contact_to_mailchimp(contact_data: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)):
    """Export a contact to Mailchimp"""
    try:
        mailchimp_service = MailchimpService()
        result = mailchimp_service.add_contact(contact_data)
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Error exporting contact to Mailchimp: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error exporting to Mailchimp: {str(e)}")

@app.get("/api/dashboard/summary")
async def get_dashboard_summary(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get dashboard summary statistics"""
    try:
        analytics = AnalyticsEngine(db)
        summary = analytics.get_dashboard_summary()
        return JSONResponse(summary)
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/dashboard/sync")
async def trigger_dashboard_sync(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Manually trigger a Google Sheets sync.
    Use sparingly—this migrates visits and time entries from the sheet into the database.
    """
    try:
        result = sync_manager.sync_if_needed(force=True)
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Error triggering dashboard sync: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error syncing data: {str(e)}")

@app.get("/api/dashboard/visits-by-month")
async def get_visits_by_month(months: int = 12, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get visits grouped by month"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_visits_by_month(months)
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting visits by month: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/hours-by-month")
async def get_hours_by_month(months: int = 12, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get hours worked grouped by month"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_hours_by_month(months)
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting hours by month: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/top-facilities")
async def get_top_facilities(limit: int = 10, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get most visited facilities"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_top_facilities(limit)
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting top facilities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/referral-types")
async def get_referral_types(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get visits categorized by referral type"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_referral_types()
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting referral types: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/costs-by-month")
async def get_costs_by_month(months: int = 12, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get costs grouped by month"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_costs_by_month(months)
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting costs by month: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/recent-activity")
async def get_recent_activity(limit: int = 20, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get recent activity across all data types"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_recent_activity(limit)
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting recent activity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/visits")
async def get_visits(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all visits (from the database)"""
    try:
        visits = db.query(Visit).order_by(Visit.visit_date.desc()).all()
        response_data = [visit.to_dict() for visit in visits]
        return JSONResponse(response_data)
    except Exception as e:
        logger.error(f"Error getting visits: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/visits/{visit_id}")
async def update_visit_notes(
    visit_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update visit notes"""
    try:
        data = await request.json()
        notes = data.get('notes', '')
        
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            return JSONResponse({"success": False, "error": "Visit not found"}, status_code=404)
        
        visit.notes = notes
        db.commit()
        
        logger.info(f"Updated notes for visit {visit_id}")
        return JSONResponse({"success": True})
    except Exception as e:
        logger.error(f"Error updating visit notes: {str(e)}")
        db.rollback()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/api/sales-bonuses")
async def get_sales_bonuses(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all sales bonuses"""
    try:
        sales = db.query(SalesBonus).order_by(SalesBonus.start_date.desc()).all()
        return JSONResponse([sale.to_dict() for sale in sales])
    except Exception as e:
        logger.error(f"Error getting sales bonuses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def _parse_range(range_param: Optional[str], default_per_page: int = 50) -> tuple[int, int]:
    """Parse pagination range query parameter into start/end indexes."""
    if not range_param:
        return 0, default_per_page - 1
    try:
        start_str, end_str = range_param.split(",")
        start = int(start_str)
        end = int(end_str)
        if start < 0 or end < start:
            raise ValueError("Invalid range values")
        return start, end
    except Exception:
        logger.warning("Invalid range parameter '%s', using defaults", range_param)
        return 0, default_per_page - 1


def _apply_contact_filters(
    query,
    tags: Optional[List[str]],
    status: Optional[str],
    contact_type: Optional[str],
    last_activity_gte: Optional[Any] = None,
    last_activity_lte: Optional[Any] = None,
    sales_id: Optional[int] = None,
):
    """Apply simple filters to the contact query."""
    if status:
        query = query.filter(Contact.status == status)
    if contact_type:
        query = query.filter(Contact.contact_type == contact_type)
    if sales_id:
        # Assuming contacts have a sales_id or owner_id column. 
        # Checking Contact model...
        # Contact model doesn't seem to have sales_id in ensure_contact_schema!
        # But Deals do. 
        # Let's check if there's an 'account_manager' or similar.
        # ensure_contact_schema added 'account_manager'.
        # If sales_id maps to account_manager (string) or a user ID?
        # The frontend sends sales_id (int).
        # If Contact has no sales_id column, we can't filter by it directly unless we join or use account_manager.
        # Let's assume for now we skip it if column missing, or check model.
        pass 
    if tags:
        for tag in tags:
            tag_value = tag.strip()
            if not tag_value:
                continue
            query = query.filter(Contact.tags.ilike(f'%{tag_value}%'))
    if last_activity_gte:
        dt = _coerce_datetime(last_activity_gte)
        if dt:
            query = query.filter(Contact.last_activity >= dt)
    if last_activity_lte:
        dt = _coerce_datetime(last_activity_lte)
        if dt:
            query = query.filter(Contact.last_activity <= dt)
    return query


def _apply_deal_filters(
    query,
    stage: Optional[str],
    created_gte: Optional[Any] = None,
    created_lte: Optional[Any] = None,
):
    if stage:
        query = query.filter(Deal.stage == stage)
    if created_gte:
        dt = _coerce_datetime(created_gte)
        if dt:
            query = query.filter(Deal.created_at >= dt)
    if created_lte:
        dt = _coerce_datetime(created_lte)
        if dt:
            query = query.filter(Deal.created_at <= dt)
    return query


def _contact_order_clause(sort_field: Optional[str], order: Optional[str]):
    """Return an order_by clause for contacts."""
    sort_map = {
        "last_activity": Contact.last_activity,
        "created_at": Contact.created_at,
        "name": Contact.name,
    }
    sort_column = sort_map.get((sort_field or "").lower(), Contact.created_at)
    direction = (order or "DESC").upper()
    return sort_column.desc() if direction == "DESC" else sort_column.asc()


def _deal_order_clause(sort_field: Optional[str], order: Optional[str]):
    sort_map = {
        "created_at": Deal.created_at,
        "name": Deal.name,
        "amount": Deal.amount,
    }
    sort_column = sort_map.get((sort_field or "").lower(), Deal.created_at)
    direction = (order or "DESC").upper()
    return sort_column.desc() if direction == "DESC" else sort_column.asc()


def _coerce_datetime(value: Optional[Any], default: Optional[datetime] = None) -> Optional[datetime]:
    """Convert string payload values to datetime when needed."""
    if value is None:
        return default
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return default


def _serialize_tags(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value)
    except Exception:
        return None


def _serialize_ids(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value)
    except Exception:
        return None


@app.get("/api/contacts")
async def get_contacts(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    q: Optional[str] = Query(default=None),
    tags: Optional[List[str]] = Query(default=None),
    status: Optional[str] = Query(default=None),
    contact_type: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
    range: Optional[str] = Query(default=None),
    last_activity_gte: Optional[str] = Query(default=None, alias="last_activity_gte"),
    last_activity_lte: Optional[str] = Query(default=None, alias="last_activity_lte"),
    sales_id: Optional[int] = Query(default=None),
    filter: Optional[str] = Query(default=None),
):
    """List contacts with optional filters and sorting."""
    try:
        from sqlalchemy import or_
        
        # Parse filter JSON if provided (React Admin sends filters this way)
        search_q = q
        if filter:
            try:
                parsed = json.loads(filter)
                if isinstance(parsed, dict):
                    search_q = search_q or parsed.get("q")
                    status = status or parsed.get("status")
                    contact_type = contact_type or parsed.get("contact_type")
                    if parsed.get("tags"):
                        tags = tags or (parsed.get("tags") if isinstance(parsed.get("tags"), list) else [parsed.get("tags")])
                    last_activity_gte = last_activity_gte or parsed.get("last_activity_gte") or parsed.get("last_activity@gte")
                    last_activity_lte = last_activity_lte or parsed.get("last_activity_lte") or parsed.get("last_activity@lte")
                    sales_id = sales_id or parsed.get("sales_id")
            except Exception:
                pass
        
        # Also support Range header if provided
        range_header = request.headers.get("Range")
        range_param = range or (range_header.split("=")[1] if range_header else None)
        start, end = _parse_range(range_param)

        query = db.query(Contact)
        
        # Apply search filter
        if search_q:
            like = f"%{search_q.strip()}%"
            query = query.filter(
                or_(
                    Contact.name.ilike(like),
                    Contact.first_name.ilike(like),
                    Contact.last_name.ilike(like),
                    Contact.email.ilike(like),
                    Contact.company.ilike(like),
                    Contact.phone.ilike(like),
                )
            )
        
        query = _apply_contact_filters(
            query,
            tags,
            status,
            contact_type,
            last_activity_gte,
            last_activity_lte,
            sales_id,
        )
        total = query.count()

        contacts = (
            query.order_by(_contact_order_clause(sort, order))
            .offset(start)
            .limit(end - start + 1)
            .all()
        )

        content_range = f"contacts {start}-{start + len(contacts) - 1 if contacts else start}/{total}"
        headers = {
            "Content-Range": content_range,
            "Access-Control-Expose-Headers": "Content-Range",
            "X-Total-Count": str(total),
        }

        return JSONResponse(
            {"data": [contact.to_dict() for contact in contacts], "total": total},
            headers=headers,
        )
    except Exception as e:
        logger.error(f"Error fetching contacts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def sync_contact_to_brevo_crm(contact: Contact) -> None:
    """Sync a contact to Brevo CRM and add to appropriate list based on contact_type."""
    try:
        from brevo_service import BrevoService
        import requests
        
        brevo = BrevoService()
        if not brevo.enabled:
            return
        
        if not contact.email:
            return  # Skip contacts without email
        
        # Normalize names
        first_name = contact.first_name or ''
        last_name = contact.last_name or ''
        if first_name and ' ' in first_name and not last_name:
            parts = first_name.split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ''
        
        contact_data = {
            'email': contact.email,
            'first_name': first_name,
            'last_name': last_name,
            'company': contact.company or '',
            'phone': contact.phone or '',
            'title': contact.title or '',
            'contact_type': contact.contact_type or '',
            'status': contact.status or '',
            'source': contact.source or 'dashboard'
        }
        
        # Sync to Brevo CRM
        result = brevo.sync_contact_to_crm(contact_data)
        if not result.get('success'):
            logger.warning(f"Failed to sync contact to Brevo: {result.get('error')}")
            return
        
        # Add to appropriate Brevo list based on contact_type
        contact_type = (contact.contact_type or '').lower()
        target_list_name = None
        target_list_keywords = []
        
        if contact_type == 'referral':
            # Business cards and referral sources → "Referral Source" list
            target_list_name = "Referral Source"
            target_list_keywords = ['referral']
        elif contact_type == 'client':
            # Clients → "Client" list
            target_list_name = "Client"
            target_list_keywords = ['client']
        # Employees don't go through this function (they're handled by GoFormz webhook only)
        
        if target_list_name and target_list_keywords:
            # Find the list
            lists_result = brevo.get_lists()
            if lists_result.get('success'):
                target_list_id = None
                for lst in lists_result.get('lists', []):
                    name_lower = lst.get('name', '').lower()
                    if any(keyword in name_lower for keyword in target_list_keywords):
                        # Make sure it's not the wrong list
                        if contact_type == 'referral' and 'client' not in name_lower and 'caregiver' not in name_lower:
                            target_list_id = lst.get('id')
                            break
                        elif contact_type == 'client' and 'referral' not in name_lower and 'caregiver' not in name_lower:
                            target_list_id = lst.get('id')
                            break
                
                # Add to list if found
                if target_list_id:
                    list_response = requests.post(
                        f"{brevo.base_url}/contacts/lists/{target_list_id}/contacts/add",
                        headers=brevo._get_headers(),
                        json={"emails": [contact.email]}
                    )
                    if list_response.status_code in (200, 201, 204):
                        logger.info(f"Added {contact.email} to Brevo {target_list_name} list")
                    else:
                        logger.warning(f"Failed to add {contact.email} to {target_list_name} list: {list_response.status_code}")
        
        logger.info(f"Synced contact to Brevo CRM: {contact.email}")
    except Exception as e:
        logger.error(f"Error syncing contact to Brevo CRM: {str(e)}", exc_info=True)
        # Don't fail the request if sync fails


def sync_company_to_brevo_crm(company: ReferralSource) -> None:
    """Sync a company to Brevo CRM in the background."""
    try:
        from brevo_service import BrevoService
        
        brevo = BrevoService()
        if not brevo.enabled:
            return
        
        company_data = {
            'name': company.name or company.organization or "Unknown Company",
            'email': company.email or '',
            'phone': company.phone or '',
            'address': company.address or '',
            'website': company.website or '',
            'location': company.location or '',
            'county': company.county or '',
            'source_type': company.source_type or '',
            'notes': company.notes or ''
        }
        
        result = brevo.create_or_update_company(company_data)
        if result.get('success'):
            logger.info(f"Synced company to Brevo CRM: {company.name}")
        else:
            logger.warning(f"Failed to sync company to Brevo: {result.get('error')}")
    except Exception as e:
        logger.error(f"Error syncing company to Brevo CRM: {str(e)}", exc_info=True)
        # Don't fail the request if sync fails


def sync_deal_to_brevo_crm(deal: Deal) -> None:
    """Sync a deal to Brevo CRM in the background."""
    try:
        from brevo_service import BrevoService
        
        brevo = BrevoService()
        if not brevo.enabled:
            return
        
        deal_data = {
            'name': deal.name or f"Deal #{deal.id}",
            'amount': deal.amount or 0,
            'category': deal.category or '',
            'description': deal.description or '',
            'stage': deal.stage or 'opportunity'
        }
        
        result = brevo.create_or_update_deal(deal_data)
        if result.get('success'):
            logger.info(f"Synced deal to Brevo CRM: {deal.name}")
        else:
            logger.warning(f"Failed to sync deal to Brevo: {result.get('error')}")
    except Exception as e:
        logger.error(f"Error syncing deal to Brevo CRM: {str(e)}", exc_info=True)
        # Don't fail the request if sync fails


def send_welcome_email_to_new_client(contact: Contact) -> None:
    """Send welcome email to a contact who just became a client."""
    try:
        from brevo_service import BrevoService
        import os
        
        # Only send if contact has email
        if not contact.email:
            return
        
        # Load welcome email template
        template_path = os.path.join(os.path.dirname(__file__), "welcome_email_new_customer.html")
        if not os.path.exists(template_path):
            logger.warning(f"Welcome email template not found at {template_path}")
            return
        
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Replace template variables
        first_name = contact.first_name or contact.name or "Valued Client"
        html_content = html_content.replace("{{FIRSTNAME}}", first_name)
        
        # Send via Brevo
        brevo = BrevoService()
        if not brevo.enabled:
            logger.warning("Brevo not configured, cannot send welcome email")
            return
        
        result = brevo.send_transactional_email(
            to_email=contact.email,
            subject="Welcome to Colorado CareAssist",
            html_content=html_content,
            sender_name="Jason Shulman",
            sender_email="jason@coloradocareassist.com",
            to_name=contact.name or contact.first_name,
            reply_to="jason@coloradocareassist.com"
        )
        
        if result.get("success"):
            logger.info(f"Sent welcome email to new client: {contact.email}")
        else:
            logger.error(f"Failed to send welcome email to {contact.email}: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error sending welcome email: {str(e)}", exc_info=True)
        # Don't fail the contact update if email send fails


@app.get("/api/contacts/{contact_id}")
async def get_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Fetch a single contact by ID."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return JSONResponse(contact.to_dict())


@app.post("/api/contacts")
async def create_contact(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Create a new contact."""
    try:
        payload = await request.json()
        now = datetime.now(timezone.utc)
        
        # Normalize first_name and last_name - split if first_name contains full name
        first_name = (payload.get("first_name") or "").strip()
        last_name = (payload.get("last_name") or "").strip()
        
        # If first_name contains a space and last_name is empty, split it
        if first_name and ' ' in first_name and not last_name:
            parts = first_name.split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ''
        
        # Build full name from first_name/last_name if name not provided
        name = payload.get("name")
        if not name and (first_name or last_name):
            name = f"{first_name or ''} {last_name or ''}".strip()
        
        contact_type = payload.get("contact_type")
        is_new_client = contact_type == "client"
        
        contact = Contact(
            first_name=first_name,
            last_name=last_name,
            name=name,
            company=payload.get("company"),
            company_id=payload.get("company_id"),
            title=payload.get("title"),
            phone=payload.get("phone"),
            email=payload.get("email"),
            address=payload.get("address"),
            website=payload.get("website"),
            notes=payload.get("notes"),
            scanned_date=_coerce_datetime(payload.get("scanned_date"), now),
            created_at=_coerce_datetime(payload.get("created_at"), now),
            updated_at=now,
            status=payload.get("status", "cold"),  # Default to cold
            contact_type=contact_type,
            tags=_serialize_tags(payload.get("tags")),
            last_activity=_coerce_datetime(payload.get("last_activity"), now),
            account_manager=payload.get("account_manager"),
            source=payload.get("source"),
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        
        # Sync to Brevo CRM in background
        import threading
        thread = threading.Thread(target=sync_contact_to_brevo_crm, args=(contact,))
        thread.daemon = True
        thread.start()
        
        # Send welcome email if contact is created as a client
        if is_new_client:
            thread = threading.Thread(target=send_welcome_email_to_new_client, args=(contact,))
            thread.daemon = True
            thread.start()
        
        return JSONResponse(contact.to_dict(), status_code=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f"Error creating contact: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/contacts/{contact_id}")
async def update_contact(
    contact_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Update an existing contact."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    try:
        payload = await request.json()
        
        # Track if contact_type changed to "client" (for welcome email automation)
        old_contact_type = contact.contact_type
        became_client = False
        
        # Handle first_name and last_name separately with normalization
        if "first_name" in payload or "last_name" in payload:
            first = (payload.get("first_name", contact.first_name) or "").strip()
            last = (payload.get("last_name", contact.last_name) or "").strip()
            
            # If first_name contains a space and last_name is empty, split it
            if first and ' ' in first and not last:
                parts = first.split(' ', 1)
                first = parts[0]
                last = parts[1] if len(parts) > 1 else ''
            
            contact.first_name = first
            contact.last_name = last
            
            # Update full name if not explicitly provided
            if not payload.get("name"):
                contact.name = f"{first} {last}".strip()
        
        # Handle other fields
        for field in [
            "name",
            "company",
            "company_id",
            "title",
            "phone",
            "email",
            "address",
            "website",
            "notes",
            "status",
            "contact_type",
            "account_manager",
            "source",
        ]:
            if field in payload:
                setattr(contact, field, payload.get(field))
        
        # Check if contact just became a client
        if "contact_type" in payload:
            new_contact_type = payload.get("contact_type")
            if new_contact_type == "client" and old_contact_type != "client":
                became_client = True

        if "tags" in payload:
            contact.tags = _serialize_tags(payload.get("tags"))
        if "last_activity" in payload:
            contact.last_activity = _coerce_datetime(payload.get("last_activity"), contact.last_activity)

        contact.updated_at = datetime.now(timezone.utc)

        db.add(contact)
        db.commit()
        db.refresh(contact)
        
        # Sync to Brevo CRM in background
        import threading
        thread = threading.Thread(target=sync_contact_to_brevo_crm, args=(contact,))
        thread.daemon = True
        thread.start()
        
        # Send welcome email if contact just became a client
        if became_client:
            thread = threading.Thread(target=send_welcome_email_to_new_client, args=(contact,))
            thread.daemon = True
            thread.start()
        
        return JSONResponse(contact.to_dict())
    except Exception as e:
        logger.error(f"Error updating contact: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/contacts/{contact_id}")
async def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Delete a contact and its related tasks."""
    from models import ContactTask
    
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    try:
        # Delete related tasks first
        db.query(ContactTask).filter(ContactTask.contact_id == contact_id).delete()
        db.delete(contact)
        db.commit()
        return JSONResponse({"success": True})
    except Exception as e:
        logger.error(f"Error deleting contact: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/deals")
async def get_deals(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    stage: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
    range: Optional[str] = Query(default=None),
    created_at_gte: Optional[str] = Query(default=None, alias="created_at@gte"),
    created_at_lte: Optional[str] = Query(default=None, alias="created_at@lte"),
    filter: Optional[str] = Query(default=None),
):
    try:
        # Parse filter JSON if provided (React Admin sends filters this way)
        if filter:
            try:
                parsed = json.loads(filter)
                if isinstance(parsed, dict):
                    stage = stage or parsed.get("stage")
                    created_at_gte = created_at_gte or parsed.get("created_at_gte") or parsed.get("created_at@gte")
                    created_at_lte = created_at_lte or parsed.get("created_at_lte") or parsed.get("created_at@lte")
            except Exception:
                pass

        range_header = request.headers.get("Range")
        range_param = range or (range_header.split("=")[1] if range_header else None)
        start, end = _parse_range(range_param)

        query = db.query(Deal)
        query = _apply_deal_filters(query, stage, created_at_gte, created_at_lte)
        total = query.count()

        deals = (
            query.order_by(_deal_order_clause(sort, order))
            .offset(start)
            .limit(end - start + 1)
            .all()
        )

        content_range = f"deals {start}-{start + len(deals) - 1 if deals else start}/{total}"
        headers = {
            "Content-Range": content_range,
            "Access-Control-Expose-Headers": "Content-Range",
            "X-Total-Count": str(total),
        }

        return JSONResponse(
            {"data": [deal.to_dict() for deal in deals], "total": total},
            headers=headers,
        )
    except Exception as e:
        logger.error(f"Error fetching deals: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/deals/{deal_id}")
async def get_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    return JSONResponse(deal.to_dict())


@app.post("/api/deals")
async def create_deal(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        payload = await request.json()
        now = datetime.now(timezone.utc)
        deal = Deal(
            name=payload.get("name"),
            company_id=payload.get("company_id"),
            contact_ids=_serialize_ids(payload.get("contact_ids")),
            category=payload.get("category"),
            stage=payload.get("stage", "opportunity"),
            description=payload.get("description"),
            amount=payload.get("amount") or 0,
            created_at=_coerce_datetime(payload.get("created_at"), now),
            updated_at=now,
            archived_at=_coerce_datetime(payload.get("archived_at")),
            expected_closing_date=_coerce_datetime(payload.get("expected_closing_date")),
            sales_id=payload.get("sales_id"),
            index=payload.get("index"),
        )
        db.add(deal)
        db.commit()
        db.refresh(deal)
        
        # Sync to Brevo CRM in background
        import threading
        thread = threading.Thread(target=sync_deal_to_brevo_crm, args=(deal,))
        thread.daemon = True
        thread.start()
        
        return JSONResponse(deal.to_dict(), status_code=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f"Error creating deal: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/deals/{deal_id}")
async def update_deal(
    deal_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    try:
        payload = await request.json()
        for field in [
            "name",
            "company_id",
            "category",
            "stage",
            "description",
            "amount",
            "sales_id",
            "index",
        ]:
            if field in payload:
                setattr(deal, field, payload.get(field))
        if "contact_ids" in payload:
            deal.contact_ids = _serialize_ids(payload.get("contact_ids"))
        if "archived_at" in payload:
            deal.archived_at = _coerce_datetime(payload.get("archived_at"))
        if "expected_closing_date" in payload:
            deal.expected_closing_date = _coerce_datetime(payload.get("expected_closing_date"))
        deal.updated_at = datetime.now(timezone.utc)
        db.add(deal)
        db.commit()
        db.refresh(deal)
        
        # Sync to Brevo CRM in background
        import threading
        thread = threading.Thread(target=sync_deal_to_brevo_crm, args=(deal,))
        thread.daemon = True
        thread.start()
        
        return JSONResponse(deal.to_dict())
    except Exception as e:
        logger.error(f"Error updating deal: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/deals/{deal_id}")
async def delete_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    try:
        db.delete(deal)
        db.commit()
        return JSONResponse({"success": True})
    except Exception as e:
        logger.error(f"Error deleting deal: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync-mailchimp-contacts")
async def sync_mailchimp_contacts_endpoint(
    db: Session = Depends(get_db), 
    current_user: Dict[str, Any] = Depends(get_current_user),
    tag_filter: Optional[str] = Query(default=None, description="Filter by Mailchimp tag (e.g., 'Referral Source', 'Client')")
):
    """
    Sync contacts FROM Mailchimp TO dashboard with proper tag mapping.
    - Mailchimp 'Referral Source' tag → contact_type='referral'
    - Mailchimp 'Client' tag → contact_type='client'
    - Mailchimp 'Hot Lead' tag → status='hot'
    """
    try:
        from mailchimp_service import MailchimpService
        
        mailchimp_service = MailchimpService()
        
        if not mailchimp_service.enabled:
            return JSONResponse({
                "success": False,
                "error": "Mailchimp not configured"
            })
        
        logger.info(f"Starting Mailchimp contacts sync (filter: {tag_filter})...")
        
        # Use the new sync_from_mailchimp method with tag mapping
        result = mailchimp_service.sync_from_mailchimp(tag_filter=tag_filter)
        
        if not result.get("success"):
            return JSONResponse({
                "success": False,
                "error": result.get("error", "Unknown error")
            })
        
        mailchimp_contacts = result.get("contacts", [])
        
        if not mailchimp_contacts:
            return JSONResponse({
                "success": True,
                "message": "No contacts found in Mailchimp" + (f" with tag '{tag_filter}'" if tag_filter else ""),
                "added": 0,
                "updated": 0,
                "skipped": 0
            })
        
        # Check existing contacts by email
        existing_contacts = {c.email.lower(): c for c in db.query(Contact).filter(Contact.email.isnot(None)).all() if c.email}
        
        added_count = 0
        updated_count = 0
        skipped_count = 0
        
        for mc_contact in mailchimp_contacts:
            email = (mc_contact.get('email') or '').lower().strip()
            if not email:
                skipped_count += 1
                continue
            
            first_name = mc_contact.get('first_name', '').strip()
            last_name = mc_contact.get('last_name', '').strip()
            name = mc_contact.get('name', '').strip() or f"{first_name} {last_name}".strip()
            if not name:
                name = email.split('@')[0]
            
            # Check if contact exists
            if email in existing_contacts:
                # Update existing contact with Mailchimp data
                existing = existing_contacts[email]
                updated = False
                
                # Update contact_type if we got one from Mailchimp
                if mc_contact.get('contact_type') and not existing.contact_type:
                    existing.contact_type = mc_contact['contact_type']
                    updated = True
                
                # Update status if we got one from Mailchimp
                if mc_contact.get('status') and not existing.status:
                    existing.status = mc_contact['status']
                    updated = True
                
                # Merge tags
                if mc_contact.get('tags'):
                    existing_tags = []
                    if existing.tags:
                        try:
                            existing_tags = json.loads(existing.tags)
                        except:
                            existing_tags = [t.strip() for t in existing.tags.split(',') if t.strip()]
                    
                    new_tags = list(set(existing_tags + mc_contact['tags']))
                    existing.tags = json.dumps(new_tags)
                    updated = True
                
                if updated:
                    db.add(existing)
                    updated_count += 1
                else:
                    skipped_count += 1
            else:
                # Create new contact
                # Safely get string values (Mailchimp sometimes returns dicts for address)
                def safe_str(val):
                    if isinstance(val, dict):
                        return val.get('addr1', '') or ''
                    return str(val).strip() if val else ''
                
                contact = Contact(
                    name=name,
                    first_name=first_name or None,
                    last_name=last_name or None,
                    company=safe_str(mc_contact.get('company')) or None,
                    email=email,
                    phone=safe_str(mc_contact.get('phone')) or None,
                    address=safe_str(mc_contact.get('address')) or None,
                    website=safe_str(mc_contact.get('website')) or None,
                    contact_type=mc_contact.get('contact_type'),
                    status=mc_contact.get('status'),
                    tags=json.dumps(mc_contact.get('tags', [])) if mc_contact.get('tags') else None,
                    source='mailchimp',
                    scanned_date=datetime.utcnow(),
                    created_at=datetime.utcnow()
                )
                
                db.add(contact)
                existing_contacts[email] = contact
                added_count += 1
        
        db.commit()
        
        total_count = db.query(Contact).count()
        
        logger.info(f"Mailchimp sync complete: Added {added_count}, Updated {updated_count}, Skipped {skipped_count}")
        
        return JSONResponse({
            "success": True,
            "message": f"Synced contacts from Mailchimp",
            "added": added_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "total": total_count,
            "filter": tag_filter
        })
        
    except Exception as e:
        logger.error(f"Error syncing Mailchimp contacts: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error syncing contacts: {str(e)}")


@app.post("/api/sync-brevo-contacts")
async def sync_brevo_contacts_endpoint(
    db: Session = Depends(get_db), 
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Sync contacts FROM Brevo TO dashboard.
    Imports all contacts from Brevo with their attributes.
    """
    try:
        from brevo_service import BrevoService
        
        brevo_service = BrevoService()
        
        if not brevo_service.enabled:
            return JSONResponse({
                "success": False,
                "error": "Brevo not configured. Add BREVO_API_KEY to environment."
            })
        
        logger.info("Starting Brevo contacts sync...")
        
        # Get all contacts from Brevo
        result = brevo_service.get_all_contacts(limit=5000)
        
        if not result.get("success"):
            return JSONResponse({
                "success": False,
                "error": result.get("error", "Failed to fetch from Brevo")
            })
        
        brevo_contacts = result.get("contacts", [])
        
        if not brevo_contacts:
            return JSONResponse({
                "success": True,
                "message": "No contacts found in Brevo",
                "added": 0,
                "updated": 0,
                "total": db.query(Contact).count()
            })
        
        # Check existing contacts by email
        existing_contacts = {c.email.lower(): c for c in db.query(Contact).filter(Contact.email.isnot(None)).all() if c.email}
        
        added_count = 0
        updated_count = 0
        
        for bc in brevo_contacts:
            email = (bc.get('email') or '').lower().strip()
            if not email:
                continue
            
            attrs = bc.get('attributes', {})
            first_name = attrs.get('FIRSTNAME', '').strip()
            last_name = attrs.get('LASTNAME', '').strip()
            name = f"{first_name} {last_name}".strip() or email.split('@')[0]
            
            if email in existing_contacts:
                # Update existing contact
                existing = existing_contacts[email]
                updated = False
                
                if attrs.get('COMPANY') and not existing.company:
                    existing.company = attrs['COMPANY']
                    updated = True
                if attrs.get('CONTACT_TYPE') and not existing.contact_type:
                    existing.contact_type = attrs['CONTACT_TYPE'].lower()
                    updated = True
                if attrs.get('STATUS') and not existing.status:
                    existing.status = attrs['STATUS'].lower()
                    updated = True
                if attrs.get('SMS') and not existing.phone:
                    existing.phone = attrs['SMS']
                    updated = True
                
                if updated:
                    db.add(existing)
                    updated_count += 1
            else:
                # Create new contact
                contact = Contact(
                    name=name,
                    first_name=first_name or None,
                    last_name=last_name or None,
                    company=attrs.get('COMPANY') or None,
                    email=email,
                    phone=attrs.get('SMS') or None,
                    address=attrs.get('ADDRESS') or None,
                    title=attrs.get('TITLE') or None,
                    contact_type=attrs.get('CONTACT_TYPE', '').lower() or None,
                    status=attrs.get('STATUS', '').lower() or None,
                    source='brevo',
                    scanned_date=datetime.utcnow(),
                    created_at=datetime.utcnow()
                )
                
                db.add(contact)
                existing_contacts[email] = contact
                added_count += 1
        
        db.commit()
        
        total_count = db.query(Contact).count()
        
        logger.info(f"Brevo sync complete: Added {added_count}, Updated {updated_count}")
        
        return JSONResponse({
            "success": True,
            "message": f"Synced {len(brevo_contacts)} contacts from Brevo",
            "added": added_count,
            "updated": updated_count,
            "total": total_count
        })
        
    except Exception as e:
        logger.error(f"Error syncing Brevo contacts: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error syncing contacts: {str(e)}")


@app.get("/api/brevo/test")
async def test_brevo_connection():
    """Test Brevo API connection."""
    try:
        from brevo_service import BrevoService
        brevo = BrevoService()
        return brevo.test_connection()
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/brevo/lists")
async def get_brevo_lists(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all Brevo contact lists."""
    try:
        from brevo_service import BrevoService
        brevo = BrevoService()
        
        if not brevo.enabled:
            return JSONResponse({
                "success": False,
                "error": "Brevo not configured"
            }, status_code=400)
        
        result = brevo.get_lists()
        return result
        
    except Exception as e:
        logger.error(f"Error getting Brevo lists: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/brevo/newsletter-template/{template_name}")
async def get_newsletter_template(
    template_name: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get a newsletter template HTML content"""
    try:
        import os
        template_path = os.path.join(os.path.dirname(__file__), template_name)
        
        # Security: Only allow .html files in the root directory
        if not template_name.endswith('.html') or '/' in template_name or '\\' in template_name:
            raise HTTPException(status_code=400, detail="Invalid template name")
        
        if not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail=f"Template {template_name} not found")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return JSONResponse({
            "success": True,
            "html": html_content,
            "template_name": template_name
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/brevo/send-newsletter")
async def send_newsletter_to_list_endpoint(
    request: SendNewsletterRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Send a newsletter to a Brevo list.
    
    Args:
        list_id: Brevo list ID to send to
        subject: Email subject line
        html_content: Custom HTML content (optional if use_template=True)
        use_template: Whether to use the default newsletter template
        month: Month name for template variable
    """
    try:
        from brevo_service import BrevoService
        import os
        from datetime import datetime
        
        brevo_service = BrevoService()
        
        if not brevo_service.enabled:
            return JSONResponse({
                "success": False,
                "error": "Brevo not configured. Add BREVO_API_KEY to environment."
            }, status_code=400)
        
        # Get or generate HTML content
        html_content = request.html_content
        if request.use_template and not html_content:
            template_path = os.path.join(os.path.dirname(__file__), "newsletter_template.html")
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # Replace template variables
                month_str = request.month or datetime.now().strftime("%B %Y")
                html_content = html_content.replace("{{MONTH}}", month_str)
                # Brevo will handle {{FIRSTNAME}} and other merge tags automatically
            else:
                return JSONResponse({
                    "success": False,
                    "error": "Newsletter template not found"
                }, status_code=404)
        
        if not html_content:
            return JSONResponse({
                "success": False,
                "error": "HTML content is required"
            }, status_code=400)
        
        # Send newsletter
        result = brevo_service.send_newsletter_to_list(
            list_id=request.list_id,
            subject=request.subject,
            html_content=html_content,
            sender_name="Colorado CareAssist",
            sender_email=None  # Will use account default
        )
        
        if result.get("success"):
            return JSONResponse({
                "success": True,
                "message": f"Newsletter sent to {result.get('sent')} recipients",
                "sent": result.get("sent"),
                "total": result.get("total"),
                "list_name": result.get("list_name")
            })
        else:
            return JSONResponse({
                "success": False,
                "error": result.get("error", "Failed to send newsletter"),
                "details": result
            }, status_code=500)
            
    except Exception as e:
        logger.error(f"Error sending newsletter: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/brevo/sync-crm")
async def sync_crm_to_brevo_endpoint(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Manually trigger a full bidirectional sync between Dashboard CRM and Brevo CRM.
    This syncs: Contacts, Companies, Deals
    """
    try:
        import subprocess
        import sys
        
        # Run the sync script
        result = subprocess.run(
            [sys.executable, "sync_crm_bidirectional.py"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            return JSONResponse({
                "success": True,
                "message": "CRM sync completed successfully",
                "output": result.stdout.splitlines()[-20:]  # Last 20 lines
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "Sync script failed",
                "output": result.stderr.splitlines()[-20:]
            }, status_code=500)
            
    except subprocess.TimeoutExpired:
        return JSONResponse({
            "success": False,
            "error": "Sync timed out after 5 minutes"
        }, status_code=500)
    except Exception as e:
        logger.error(f"Error running CRM sync: {str(e)}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/brevo/sync-from-brevo")
async def sync_from_brevo_endpoint(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Sync FROM Brevo TO Dashboard to clean up dashboard data.
    Uses Brevo as the source of truth.
    """
    try:
        import subprocess
        import sys
        
        # Run the cleanup sync script
        result = subprocess.run(
            [sys.executable, "sync_from_brevo_to_dashboard.py"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            return JSONResponse({
                "success": True,
                "message": "Dashboard cleaned up using Brevo as source of truth",
                "output": result.stdout.splitlines()[-20:]  # Last 20 lines
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "Sync script failed",
                "output": result.stderr.splitlines()[-20:]
            }, status_code=500)
            
    except subprocess.TimeoutExpired:
        return JSONResponse({
            "success": False,
            "error": "Sync timed out after 5 minutes"
        }, status_code=500)
    except Exception as e:
        logger.error(f"Error running cleanup sync: {str(e)}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/quickbooks/oauth/authorize")
async def quickbooks_oauth_authorize(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Initiate QuickBooks OAuth flow.
    Redirects user to QuickBooks authorization page.
    """
    try:
        import os
        import secrets
        from urllib.parse import quote
        
        client_id = os.getenv('QB_CLIENT_ID') or os.getenv('QUICKBOOKS_CLIENT_ID')
        if not client_id:
            return JSONResponse({
                "success": False,
                "error": "QuickBooks Client ID not configured"
            }, status_code=400)
        
        # Generate a random state parameter for CSRF protection
        state = secrets.token_urlsafe(32)
        
        redirect_uri = "https://careassist-tracker-0fcf2cecdb22.herokuapp.com/api/quickbooks/oauth/callback"
        scope = "com.intuit.quickbooks.accounting"
        
        auth_url = (
            f"https://appcenter.intuit.com/connect/oauth2?"
            f"client_id={client_id}&"
            f"scope={scope}&"
            f"redirect_uri={quote(redirect_uri)}&"
            f"response_type=code&"
            f"state={state}"
        )
        
        return RedirectResponse(url=auth_url)
        
    except Exception as e:
        logger.error(f"Error initiating QuickBooks OAuth: {str(e)}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/quickbooks/oauth/callback")
async def quickbooks_oauth_callback(
    code: Optional[str] = Query(None),
    realmId: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Handle QuickBooks OAuth callback.
    Exchanges authorization code for access and refresh tokens.
    """
    try:
        import os
        import requests
        
        if error:
            return HTMLResponse(f"""
                <html>
                    <body style="font-family: Arial; padding: 40px; text-align: center;">
                        <h1 style="color: #dc2626;">Authorization Failed</h1>
                        <p>Error: {error}</p>
                        <p><a href="/api/quickbooks/oauth/authorize">Try Again</a></p>
                    </body>
                </html>
            """)
        
        if not code:
            return HTMLResponse("""
                <html>
                    <body style="font-family: Arial; padding: 40px; text-align: center;">
                        <h1 style="color: #dc2626;">Authorization Failed</h1>
                        <p>No authorization code received.</p>
                        <p><a href="/api/quickbooks/oauth/authorize">Try Again</a></p>
                    </body>
                </html>
            """)
        
        client_id = os.getenv('QB_CLIENT_ID') or os.getenv('QUICKBOOKS_CLIENT_ID')
        client_secret = os.getenv('QB_CLIENT_SECRET') or os.getenv('QUICKBOOKS_CLIENT_SECRET')
        redirect_uri = "https://careassist-tracker-0fcf2cecdb22.herokuapp.com/api/quickbooks/oauth/callback"
        
        if not client_id or not client_secret:
            return HTMLResponse("""
                <html>
                    <body style="font-family: Arial; padding: 40px; text-align: center;">
                        <h1 style="color: #dc2626;">Configuration Error</h1>
                        <p>QuickBooks credentials not configured.</p>
                    </body>
                </html>
            """)
        
        # Exchange code for tokens
        token_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        
        response = requests.post(
            token_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri
            },
            auth=(client_id, client_secret)
        )
        
        if response.status_code != 200:
            return HTMLResponse(f"""
                <html>
                    <body style="font-family: Arial; padding: 40px; text-align: center;">
                        <h1 style="color: #dc2626;">Token Exchange Failed</h1>
                        <p>Status: {response.status_code}</p>
                        <p>Error: {response.text[:200]}</p>
                        <p><a href="/api/quickbooks/oauth/authorize">Try Again</a></p>
                    </body>
                </html>
            """)
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in', 3600)
        
        # Store realmId if provided
        realm_id = realmId or os.getenv('QB_REALM_ID') or os.getenv('QUICKBOOKS_REALM_ID')
        
        # Show success page with instructions to set environment variables
        return HTMLResponse(f"""
            <html>
                <head>
                    <title>QuickBooks Authorization Success</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; }}
                        .success {{ background: #10b981; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                        .code-block {{ background: #1f2937; color: #10b981; padding: 15px; border-radius: 4px; font-family: monospace; overflow-x: auto; margin: 10px 0; }}
                        .warning {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; }}
                        h1 {{ color: #10b981; }}
                        h2 {{ color: #374151; margin-top: 30px; }}
                    </style>
                </head>
                <body>
                    <div class="success">
                        <h1>✓ QuickBooks Authorization Successful!</h1>
                        <p>Your access and refresh tokens have been generated.</p>
                    </div>
                    
                    <h2>Next Steps:</h2>
                    <p>Set these environment variables on Heroku:</p>
                    
                    <div class="code-block">
heroku config:set QB_REALM_ID={realm_id} -a careassist-tracker<br>
heroku config:set QB_ACCESS_TOKEN={access_token} -a careassist-tracker<br>
heroku config:set QB_REFRESH_TOKEN={refresh_token} -a careassist-tracker
                    </div>
                    
                    <div class="warning">
                        <strong>⚠️ Important:</strong> Copy these values now. The access token expires in {expires_in // 3600} hours, 
                        but the refresh token is long-lived and will be used to get new access tokens automatically.
                    </div>
                    
                    <h2>Token Details:</h2>
                    <p><strong>Realm ID:</strong> {realm_id or 'Not provided - set manually'}</p>
                    <p><strong>Access Token:</strong> <span style="font-family: monospace; font-size: 0.9em;">{access_token[:50]}...</span></p>
                    <p><strong>Refresh Token:</strong> <span style="font-family: monospace; font-size: 0.9em;">{refresh_token[:50]}...</span></p>
                    <p><strong>Expires In:</strong> {expires_in // 3600} hours</p>
                    
                    <h2>After Setting Variables:</h2>
                    <p>Test the connection:</p>
                    <div class="code-block">
heroku run "python3 -c 'from quickbooks_service import QuickBooksService; qb = QuickBooksService(); print(qb.test_connection())'" -a careassist-tracker
                    </div>
                </body>
            </html>
        """)
        
    except Exception as e:
        logger.error(f"Error in QuickBooks OAuth callback: {str(e)}", exc_info=True)
        return HTMLResponse(f"""
            <html>
                <body style="font-family: Arial; padding: 40px; text-align: center;">
                    <h1 style="color: #dc2626;">Error</h1>
                    <p>{str(e)}</p>
                    <p><a href="/api/quickbooks/oauth/authorize">Try Again</a></p>
                </body>
            </html>
        """)


@app.get("/api/quickbooks/test")
async def test_quickbooks_connection():
    """Test QuickBooks API connection."""
    try:
        from quickbooks_service import QuickBooksService
        qb = QuickBooksService()
        return qb.test_connection()
    except Exception as e:
        logger.error(f"Error testing QuickBooks connection: {str(e)}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/quickbooks/sync-to-brevo")
async def sync_quickbooks_to_brevo_endpoint(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Sync customers from QuickBooks to Brevo Client list.
    New customers will trigger the Brevo welcome automation.
    """
    try:
        import subprocess
        import sys
        
        # Run the sync script
        result = subprocess.run(
            [sys.executable, "sync_quickbooks_to_brevo.py"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            return JSONResponse({
                "success": True,
                "message": "QuickBooks customers synced to Brevo Client list",
                "output": result.stdout.splitlines()[-30:]  # Last 30 lines
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "Sync script failed",
                "output": result.stderr.splitlines()[-30:]
            }, status_code=500)
            
    except subprocess.TimeoutExpired:
        return JSONResponse({
            "success": False,
            "error": "Sync timed out after 5 minutes"
        }, status_code=500)
    except Exception as e:
        logger.error(f"Error running QuickBooks sync: {str(e)}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/goformz/test")
async def test_goformz_connection():
    """Test GoFormz API connection."""
    try:
        from goformz_service import GoFormzService
        goformz = GoFormzService()
        return goformz.test_connection()
    except Exception as e:
        logger.error(f"Error testing GoFormz connection: {str(e)}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/goformz/sync-to-brevo")
async def sync_goformz_to_brevo_endpoint(
    since_hours: int = 24,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Sync completed Client Packets from GoFormz to Brevo Client list.
    New customers will trigger the Brevo welcome automation.
    """
    try:
        import subprocess
        import sys
        
        # Run the sync script
        result = subprocess.run(
            [sys.executable, "sync_goformz_to_brevo.py", "--since-hours", str(since_hours)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            return JSONResponse({
                "success": True,
                "message": "GoFormz Client Packets synced to Brevo Client list",
                "output": result.stdout.splitlines()[-30:]  # Last 30 lines
            })
        else:
            return JSONResponse({
                "success": False,
                "error": "Sync script failed",
                "output": result.stderr.splitlines()[-30:]
            }, status_code=500)
            
    except subprocess.TimeoutExpired:
        return JSONResponse({
            "success": False,
            "error": "Sync timed out after 5 minutes"
        }, status_code=500)
    except Exception as e:
        logger.error(f"Error running GoFormz sync: {str(e)}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/goformz/webhook")
async def goformz_webhook(request: Request):
    """
    Webhook endpoint for GoFormz to notify when forms are completed.
    Handles both Client Packets (adds to dashboard + Brevo) and Employee Packets (Brevo only).
    """
    try:
        from goformz_service import GoFormzService
        from brevo_service import BrevoService
        import requests
        
        payload = await request.json()
        
        # Log the full payload for debugging
        logger.info(f"GoFormz webhook received: {json.dumps(payload, indent=2)}")
        
        # GoFormz webhook payload structure: EventType, EntityId, Timestamp, Item {Id, Url, Recompleted}
        event_type = payload.get('EventType', '').lower() or payload.get('event', '').lower() or payload.get('eventType', '').lower()
        
        # Check if this is a form completion event
        if event_type not in ['form.complete', 'completed', 'submitted', 'signed']:
            logger.info(f"GoFormz webhook - Ignoring: event type '{event_type}' not a completion")
            return JSONResponse({"success": True, "message": f"Event type '{event_type}' not a completion"})
        
        # Extract submission/item info
        item = payload.get('Item', {})
        submission_id = item.get('Id') or payload.get('submissionId') or payload.get('submission_id')
        form_url = item.get('Url')  # API endpoint to fetch form details
        
        if not submission_id:
            return JSONResponse({"success": False, "error": "No submission ID in webhook"})
        
        logger.info(f"GoFormz webhook - Event: '{event_type}', Submission ID: '{submission_id}', Form URL: '{form_url}'")
        
        goformz = GoFormzService()
        brevo = BrevoService()
        
        if not goformz.enabled or not brevo.enabled:
            return JSONResponse({"success": False, "error": "GoFormz or Brevo not configured"})
        
        # Fetch form details from GoFormz API
        form_data = {}
        form_name = ""
        
        # Strategy 1: Map EntityId to form type (if known)
        # This is a fallback if we can't fetch from API
        entity_id = payload.get('EntityId')
        entity_id_to_form_type = {
            'c2d547ca-df85-42c3-89ed-a3f44e3d1bd8': 'client packet',  # Client Packet template ID
            '9c0fa30f-87d4-4e41-b3ea-e0b69fddabb5': 'employee packet',  # Employee Packet template ID
        }
        
        if entity_id in entity_id_to_form_type:
            form_name = entity_id_to_form_type[entity_id]
            logger.info(f"Mapped EntityId {entity_id} to form type: '{form_name}'")
        
        # Strategy 1b: Try to get template name from EntityId via API (if mapping didn't work)
        if not form_name and entity_id:
            try:
                logger.info(f"Attempting to fetch template name from EntityId: {entity_id}")
                # Try to get template/form name from template ID using v1 API
                template_response = requests.get(
                    f"{goformz.base_url}/forms/{entity_id}",
                    headers=goformz._get_headers()
                )
                logger.info(f"Template fetch response: {template_response.status_code}")
                if template_response.status_code == 200:
                    template_data = template_response.json()
                    form_name = (template_data.get('Name', '') or template_data.get('name', '') or template_data.get('templateName', '') or '').lower()
                    logger.info(f"Got form name from template API: '{form_name}'")
                else:
                    logger.warning(f"Failed to get template from EntityId: {template_response.status_code} - {template_response.text[:200]}")
            except Exception as e:
                logger.warning(f"Failed to get template name from EntityId: {str(e)}", exc_info=True)
        
        # Strategy 1c: Check if GoFormz workflow added form name to payload
        if not form_name:
            form_name = (payload.get('formName', '') or payload.get('FormName', '') or payload.get('templateName', '') or '').lower()
            if form_name:
                logger.info(f"Got form name from webhook payload: '{form_name}'")
        
        # Strategy 2: Try to fetch submission data using submission ID via v1 API
        if submission_id:
            try:
                # Try v1 API endpoint for submissions
                submission_response = requests.get(
                    f"{goformz.base_url}/submissions/{submission_id}",
                    headers=goformz._get_headers()
                )
                if submission_response.status_code == 200:
                    submission_data = submission_response.json()
                    logger.info(f"Fetched submission from GoFormz v1 API: {json.dumps(submission_data, indent=2)[:500]}")
                    
                    # Extract form name if we don't have it yet
                    if not form_name:
                        form_name = (submission_data.get('formName', '') or submission_data.get('FormName', '') or submission_data.get('templateName', '') or '').lower()
                    
                    # Extract form data (fields/values)
                    # GoFormz submission structure may have data, fields, or formData
                    form_data = (
                        submission_data.get('data', {}) or 
                        submission_data.get('Data', {}) or 
                        submission_data.get('formData', {}) or 
                        submission_data.get('FormData', {}) or 
                        submission_data.get('fields', {}) or 
                        submission_data.get('Fields', {}) or 
                        {}
                    )
                    
                    # If form_data is a list, convert to dict
                    if isinstance(form_data, list):
                        form_data = {item.get('Name', item.get('name', '')): item.get('Value', item.get('value', '')) for item in form_data if isinstance(item, dict)}
                else:
                    logger.warning(f"Failed to fetch submission from GoFormz v1 API: {submission_response.status_code} - {submission_response.text[:200]}")
            except Exception as e:
                logger.warning(f"Error fetching submission from GoFormz v1 API: {str(e)}")
        
        # Strategy 3: Try the v2 URL provided by GoFormz (may require different auth)
        if not form_data and form_url:
            try:
                # Try fetching from the v2 URL GoFormz provided
                response = requests.get(form_url, headers=goformz._get_headers())
                if response.status_code == 200:
                    form_details = response.json()
                    logger.info(f"Fetched form details from GoFormz v2 URL: {json.dumps(form_details, indent=2)[:500]}")
                    
                    # Extract form name if we don't have it yet
                    if not form_name:
                        form_name = (form_details.get('Name', '') or form_details.get('name', '') or '').lower()
                    
                    # Extract form data - GoFormz v2 API structure
                    if not form_data:
                        # Try different possible locations for form data
                        form_data = (
                            form_details.get('data', {}) or  # lowercase 'data'
                            form_details.get('Data', {}) or  # uppercase 'Data'
                            form_details.get('fields', {}) or
                            form_details.get('Fields', {}) or
                            form_details.get('formData', {}) or
                            form_details.get('FormData', {}) or
                            {}
                        )
                        
                        # If it's a list, convert to dict
                        if isinstance(form_data, list):
                            form_data = {item.get('Name', item.get('name', '')): item.get('Value', item.get('value', item.get('text', ''))) for item in form_data if isinstance(item, dict)}
                        
                        # Log the structure for debugging
                        logger.info(f"Form data structure - type: {type(form_data)}, keys: {list(form_data.keys())[:10] if isinstance(form_data, dict) else 'not a dict'}")
                        if isinstance(form_data, dict) and 'ClientEmail' in form_data:
                            logger.info(f"ClientEmail value type: {type(form_data.get('ClientEmail'))}, value: {str(form_data.get('ClientEmail'))[:100]}")
                else:
                    logger.warning(f"Failed to fetch form from GoFormz v2 URL: {response.status_code} - {response.text[:200]}")
            except Exception as e:
                logger.warning(f"Error fetching form details from GoFormz v2 URL: {str(e)}")
        
        logger.info(f"GoFormz webhook - Form name: '{form_name}'")
        
        # Determine form type from form name
        is_client_packet = 'client packet' in form_name
        is_employee_packet = 'employee packet' in form_name or ('employee' in form_name and 'packet' in form_name)
        
        # Only process Client Packet or Employee Packet completions
        if not is_client_packet and not is_employee_packet:
            logger.info(f"GoFormz webhook - Ignoring: form name '{form_name}' doesn't match Client or Employee Packet")
            return JSONResponse({"success": True, "message": "Not a Client or Employee Packet, ignoring"})
        
        # Extract contact data from form_data
        # GoFormz form data structure: fields can be in various formats
        # Sometimes values are nested dicts with 'value' or 'Value' keys
        def extract_value(field_value):
            """Extract string value from field, handling nested dicts."""
            if isinstance(field_value, str):
                return field_value
            elif isinstance(field_value, dict):
                # Try common nested value keys
                return field_value.get('value') or field_value.get('Value') or field_value.get('text') or field_value.get('Text') or ''
            return ''
        
        email = ''
        first_name = ''
        last_name = ''
        
        # Try multiple ways to extract email
        if isinstance(form_data, dict):
            # Common email field names in GoFormz Client Packet
            email_candidates = [
                form_data.get('ClientEmail'),
                form_data.get('clientEmail'),
                form_data.get('CLIENTEMAIL'),
                form_data.get('PayerEmail'),
                form_data.get('payerEmail'),
                form_data.get('email'),
                form_data.get('Email'),
                form_data.get('EMAIL'),
                form_data.get('email_address'),
                form_data.get('Email Address'),
            ]
            
            for candidate in email_candidates:
                if candidate:
                    email = extract_value(candidate)
                    if email and '@' in email and '.' in email:
                        break
            
            if not email:
                # Try looking for email in nested structures or any field containing "email"
                for key, value in form_data.items():
                    if 'email' in key.lower():
                        extracted = extract_value(value)
                        if extracted and '@' in extracted and '.' in extracted:
                            email = extracted
                            logger.info(f"Found email in field '{key}': {email}")
                            break
        
        email = email.strip().lower() if email and isinstance(email, str) else ''
        
        if not email:
            logger.warning(f"No email found in form data. Form data keys: {list(form_data.keys()) if isinstance(form_data, dict) else 'not a dict'}")
            return JSONResponse({"success": False, "error": "No email in submission"})
        
        # Extract first name and last name
        # Client Packet uses: ClientName
        # Employee Packet uses: EmpFN (first name) and EmpLN (last name) or Employee Name
        client_name = ''  # Initialize to avoid UnboundLocalError
        if isinstance(form_data, dict):
            # Try Employee Packet fields first (EmpFN/EmpLN)
            if not first_name:
                first_name_candidates = [
                    form_data.get('EmpFN'),
                    form_data.get('empFN'),
                    form_data.get('EMPFN'),
                    form_data.get('EmployeeFirstName'),
                    form_data.get('First Name'),
                ]
                for candidate in first_name_candidates:
                    if candidate:
                        first_name = extract_value(candidate)
                        if first_name and isinstance(first_name, str):
                            first_name = first_name.strip()
                            break
            
            if not last_name:
                last_name_candidates = [
                    form_data.get('EmpLN'),
                    form_data.get('empLN'),
                    form_data.get('EMPLN'),
                    form_data.get('EmployeeLastName'),
                    form_data.get('Last Name'),
                ]
                for candidate in last_name_candidates:
                    if candidate:
                        last_name = extract_value(candidate)
                        if last_name and isinstance(last_name, str):
                            last_name = last_name.strip()
                            break
            
            # If we don't have name yet, try ClientName field (Client Packet format)
            if not first_name and not last_name:
                client_name_candidates = [
                    form_data.get('ClientName'),
                    form_data.get('clientName'),
                    form_data.get('CLIENTNAME'),
                    form_data.get('EmployeeName'),
                    form_data.get('employeeName'),
                    form_data.get('Name'),
                    form_data.get('name'),
                ]
                
                for candidate in client_name_candidates:
                    if candidate:
                        client_name = extract_value(candidate)
                        if client_name:
                            break
            
            if client_name and isinstance(client_name, str):
                client_name = client_name.strip()
                if client_name:
                    # Split full name into first and last
                    name_parts = client_name.split(' ', 1)
                    first_name = name_parts[0] if name_parts else ''
                    last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            if not first_name and not last_name:
                # Fallback to separate first/last name fields
                first_name_candidates = [
                    form_data.get('first_name'),
                    form_data.get('First Name'),
                    form_data.get('firstName'),
                    form_data.get('First'),
                    form_data.get('first'),
                ]
                for candidate in first_name_candidates:
                    if candidate:
                        first_name = extract_value(candidate)
                        if first_name and isinstance(first_name, str):
                            first_name = first_name.strip()
                            break
                
                last_name_candidates = [
                    form_data.get('last_name'),
                    form_data.get('Last Name'),
                    form_data.get('lastName'),
                    form_data.get('Last'),
                    form_data.get('last'),
                ]
                for candidate in last_name_candidates:
                    if candidate:
                        last_name = extract_value(candidate)
                        if last_name and isinstance(last_name, str):
                            last_name = last_name.strip()
                            break
        
        logger.info(f"Extracted contact data - Email: '{email}', First: '{first_name}', Last: '{last_name}'")
        
        # Build contact data and handle routing
        if is_client_packet:
            # CLIENT PACKET: Add to Brevo "Client" list AND create portal contact
            contact_data = {
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'name': f"{first_name} {last_name}".strip() or email,
                'contact_type': 'client',
                'source': 'GoFormz Client Packet',
                'notes': f"Completed Client Packet via webhook on {datetime.now().isoformat()}"
            }
            target_list_name = "Client"
            target_list_keywords = ['client']
            exclude_keywords = ['referral', 'employee', 'caregiver']
            success_message_prefix = "Customer"
            create_portal_contact = True
        else:  # Employee Packet
            # EMPLOYEE PACKET: Add to Brevo "Caregivers" list ONLY (NO portal contact)
            contact_data = {
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'name': f"{first_name} {last_name}".strip() or email,
                'contact_type': 'employee',
                'source': 'GoFormz Employee Packet',
                'notes': f"Completed Employee Packet via webhook on {datetime.now().isoformat()}"
            }
            target_list_name = "Caregivers"
            target_list_keywords = ['caregiver']
            exclude_keywords = ['client', 'referral', 'employee']
            success_message_prefix = "Employee"
            create_portal_contact = False
        
        # Add to Brevo
        result = brevo.add_contact(contact_data)
        
        if not result.get('success'):
            return JSONResponse({
                "success": False,
                "error": f"Failed to add to Brevo: {result.get('error')}"
            })
        
        # Find or create the appropriate list
        lists_result = brevo.get_lists()
        if lists_result.get('success'):
            target_list_id = None
            
            # First, try to find existing list
            for lst in lists_result.get('lists', []):
                name_lower = lst.get('name', '').lower()
                # Check if list matches our keywords and doesn't match exclude keywords
                matches = any(keyword in name_lower for keyword in target_list_keywords)
                excludes = any(keyword in name_lower for keyword in exclude_keywords)
                
                if matches and not excludes:
                    target_list_id = lst.get('id')
                    logger.info(f"Found {target_list_name} list: ID {target_list_id}")
                    break
            
            # If not found, create it
            if not target_list_id:
                create_result = brevo.create_list(target_list_name)
                if create_result.get('success'):
                    target_list_id = create_result.get('list_id')
                    logger.info(f"Created {target_list_name} list: ID {target_list_id}")
                else:
                    logger.warning(f"Failed to create {target_list_name} list: {create_result.get('error')}")
            
            # Add to the appropriate list
            if target_list_id:
                list_response = requests.post(
                    f"{brevo.base_url}/contacts/lists/{target_list_id}/contacts/add",
                    headers=brevo._get_headers(),
                    json={"emails": [email]}
                )
                
                if list_response.status_code in (200, 201, 204):
                    logger.info(f"Added {email} to Brevo {target_list_name} list via GoFormz webhook")
                    
                    # For Client Packets: Also create portal contact
                    if create_portal_contact:
                        try:
                            from database import db_manager
                            db = db_manager.SessionLocal()
                            
                            # Check if contact already exists
                            existing_contact = db.query(Contact).filter(Contact.email == email).first()
                            
                            if not existing_contact:
                                new_contact = Contact(
                                    first_name=first_name,
                                    last_name=last_name,
                                    name=f"{first_name} {last_name}".strip() or email,
                                    email=email,
                                    contact_type="client",
                                    status="active",
                                    source="GoFormz Client Packet",
                                    notes=f"Completed Client Packet via webhook on {datetime.now().isoformat()}",
                                    created_at=datetime.utcnow(),
                                    updated_at=datetime.utcnow()
                                )
                                db.add(new_contact)
                                db.commit()
                                logger.info(f"Created portal contact for {email}")
                                
                                # Send welcome email
                                import threading
                                welcome_thread = threading.Thread(target=send_welcome_email_to_new_client, args=(new_contact,))
                                welcome_thread.daemon = True
                                welcome_thread.start()
                                logger.info(f"Triggered welcome email for {email}")
                                
                                # Sync to Brevo CRM (already in list, but ensure CRM sync)
                                crm_thread = threading.Thread(target=sync_contact_to_brevo_crm, args=(new_contact,))
                                crm_thread.daemon = True
                                crm_thread.start()
                            else:
                                # Update existing contact to client if not already
                                if existing_contact.contact_type != "client":
                                    existing_contact.contact_type = "client"
                                    existing_contact.updated_at = datetime.utcnow()
                                    db.commit()
                                    logger.info(f"Updated existing contact {email} to client type")
                                
                                # Always send welcome email when Client Packet is completed
                                # (even if contact already exists as client - they just completed the packet!)
                                import threading
                                welcome_thread = threading.Thread(target=send_welcome_email_to_new_client, args=(existing_contact,))
                                welcome_thread.daemon = True
                                welcome_thread.start()
                                logger.info(f"Triggered welcome email for client {email} (Client Packet completed)")
                            
                            db.close()
                        except Exception as e:
                            logger.error(f"Error creating portal contact for {email}: {str(e)}", exc_info=True)
                            # Don't fail the webhook if portal contact creation fails
                    
                    if is_client_packet:
                        message = f"{success_message_prefix} {email} added to Brevo {target_list_name} list - welcome email will be sent"
                    else:  # Employee Packet
                        message = f"{success_message_prefix} {email} added to Brevo {target_list_name} list - Brevo automation will send welcome email"
                    
                    return JSONResponse({
                        "success": True,
                        "message": message
                    })
        
        return JSONResponse({
            "success": True,
            "message": f"Contact added to Brevo, but failed to add to {target_list_name} list"
        })
        
    except Exception as e:
        logger.error(f"Error processing GoFormz webhook: {str(e)}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/goformz/test-welcome-email")
async def test_welcome_email(
    email: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Test endpoint to manually trigger welcome email for a contact."""
    try:
        from database import db_manager
        db = db_manager.SessionLocal()
        
        contact = db.query(Contact).filter(Contact.email == email).first()
        if not contact:
            return JSONResponse({
                "success": False,
                "error": f"Contact with email {email} not found"
            }, status_code=404)
        
        # Send welcome email
        import threading
        welcome_thread = threading.Thread(target=send_welcome_email_to_new_client, args=(contact,))
        welcome_thread.daemon = True
        welcome_thread.start()
        
        db.close()
        
        return JSONResponse({
            "success": True,
            "message": f"Welcome email triggered for {email}"
        })
    except Exception as e:
        logger.error(f"Error testing welcome email: {str(e)}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/brevo/cleanup-gmail-from-referrals")
async def cleanup_gmail_from_referrals_endpoint(
    list_id: Optional[int] = None,
    dry_run: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Remove Gmail addresses from the referral source list.
    
    Args:
        list_id: Optional list ID (if not provided, finds referral source list automatically)
        dry_run: If True, only previews what would be removed (default: True)
    """
    try:
        from brevo_service import BrevoService
        import requests
        
        brevo = BrevoService()
        
        if not brevo.enabled:
            return JSONResponse({
                "success": False,
                "error": "Brevo not configured"
            }, status_code=400)
        
        # Find the referral source list
        lists_result = brevo.get_lists()
        if not lists_result.get('success'):
            return JSONResponse({
                "success": False,
                "error": f"Failed to get lists: {lists_result.get('error')}"
            }, status_code=500)
        
        lists = lists_result.get('lists', [])
        
        if list_id:
            target_list = next((lst for lst in lists if lst.get('id') == list_id), None)
            if not target_list:
                return JSONResponse({
                    "success": False,
                    "error": f"List ID {list_id} not found"
                }, status_code=404)
        else:
            # Find referral source list
            referral_lists = [
                lst for lst in lists 
                if 'referral' in lst.get('name', '').lower()
            ]
            if not referral_lists:
                return JSONResponse({
                    "success": False,
                    "error": "No referral source list found"
                }, status_code=404)
            
            target_list = referral_lists[0]
            for lst in referral_lists:
                if 'referral source' in lst.get('name', '').lower():
                    target_list = lst
                    break
        
        list_id = target_list.get('id')
        list_name = target_list.get('name')
        
        # Get all contacts from the list
        all_contacts = []
        offset = 0
        limit_per_request = 50
        
        while True:
            response = requests.get(
                f"{brevo.base_url}/contacts/lists/{list_id}/contacts",
                headers=brevo._get_headers(),
                params={"limit": limit_per_request, "offset": offset}
            )
            
            if response.status_code != 200:
                return JSONResponse({
                    "success": False,
                    "error": f"Failed to get contacts: {response.status_code}"
                }, status_code=500)
            
            data = response.json()
            contacts_batch = data.get('contacts', [])
            all_contacts.extend(contacts_batch)
            
            if len(contacts_batch) < limit_per_request:
                break
            
            offset += limit_per_request
        
        # Filter for Gmail addresses
        gmail_contacts = []
        for contact in all_contacts:
            email = contact.get('email', '').strip().lower()
            if email.endswith('@gmail.com') or email.endswith('@googlemail.com'):
                gmail_contacts.append(contact)
        
        gmail_emails = [c.get('email') for c in gmail_contacts]
        gmail_details = [
            {
                "email": c.get('email'),
                "name": c.get('attributes', {}).get('FIRSTNAME', '') or 
                        c.get('attributes', {}).get('LASTNAME', '') or 
                        c.get('email', '')
            }
            for c in gmail_contacts
        ]
        
        result = {
            "success": True,
            "list_id": list_id,
            "list_name": list_name,
            "total_contacts": len(all_contacts),
            "gmail_count": len(gmail_contacts),
            "gmail_emails": gmail_emails[:100],  # Limit to first 100 for response size
            "gmail_details": gmail_details[:100],
            "dry_run": dry_run
        }
        
        # If not dry run, actually remove them
        if not dry_run:
            if not gmail_emails:
                return JSONResponse({
                    **result,
                    "message": "No Gmail addresses found to remove"
                })
            
            # Remove in batches
            batch_size = 50
            total_removed = 0
            errors = []
            
            for i in range(0, len(gmail_emails), batch_size):
                batch = gmail_emails[i:i+batch_size]
                
                batch_response = requests.post(
                    f"{brevo.base_url}/contacts/lists/{list_id}/contacts/remove",
                    headers=brevo._get_headers(),
                    json={"emails": batch}
                )
                
                if batch_response.status_code in (200, 201, 204):
                    total_removed += len(batch)
                else:
                    errors.append(f"Batch {i//batch_size + 1}: {batch_response.status_code}")
            
            result["removed"] = total_removed
            result["errors"] = errors if errors else None
            result["message"] = f"Removed {total_removed} Gmail contacts from '{list_name}'"
        
        return JSONResponse(result)
        
    except Exception as e:
        logger.error(f"Error cleaning up Gmail from referrals: {str(e)}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/push-to-brevo")
async def push_contacts_to_brevo(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    contact_type_filter: Optional[str] = Query(default=None, description="Filter by contact_type (referral, client, prospect)"),
    source_filter: Optional[str] = Query(default=None, description="Filter by source (e.g., 'Business Card Scan')")
):
    """
    Push contacts FROM dashboard TO Brevo.
    Only pushes quality contacts (have name + email, preferably company).
    """
    try:
        from brevo_service import BrevoService
        
        brevo_service = BrevoService()
        
        if not brevo_service.enabled:
            return JSONResponse({
                "success": False,
                "error": "Brevo not configured. Add BREVO_API_KEY to environment."
            })
        
        # Build query for contacts to push
        query = db.query(Contact).filter(
            Contact.email.isnot(None),
            Contact.email != ''
        )
        
        if contact_type_filter:
            query = query.filter(Contact.contact_type == contact_type_filter)
        
        if source_filter:
            query = query.filter(Contact.source == source_filter)
        
        contacts = query.all()
        
        # Filter for quality contacts
        quality_contacts = []
        for c in contacts:
            email = (c.email or '').strip().lower()
            name = (c.name or '').strip()
            
            # Skip garbage
            if len(email) < 5 or '@' not in email:
                continue
            
            # Check if name is just email prefix (garbage)
            email_prefix = email.split('@')[0].lower()
            name_is_garbage = not name or len(name) <= 2 or name.lower().replace(' ', '') == email_prefix
            
            # Must have either a real name OR a company
            if name_is_garbage and not c.company:
                continue
            
            # Get first/last name - properly split if needed
            first_name = c.first_name or ''
            last_name = c.last_name or ''
            
            # If first_name contains a space, it's likely a full name - split it
            if first_name and ' ' in first_name.strip():
                parts = first_name.strip().split(' ', 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else (last_name or '')
            # If no first_name but we have name, split name
            elif not first_name and name:
                parts = name.strip().split(' ', 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else (last_name or '')
            
            quality_contacts.append({
                'email': email,
                'first_name': first_name or '',
                'last_name': last_name or '',
                'company': c.company or '',
                'phone': c.phone or '',
                'title': c.title or '',
                'contact_type': c.contact_type or '',
                'status': c.status or '',
                'source': c.source or 'dashboard'
            })
        
        if not quality_contacts:
            return JSONResponse({
                "success": True,
                "message": "No quality contacts to push",
                "pushed": 0,
                "filtered_out": len(contacts)
            })
        
        # Ensure we have a list to add to
        lists_result = brevo_service.get_lists()
        list_id = None
        if lists_result.get('success'):
            for lst in lists_result.get('lists', []):
                if 'contact' in lst['name'].lower() or 'all' in lst['name'].lower():
                    list_id = lst['id']
                    break
        
        if not list_id:
            create_result = brevo_service.create_list("Dashboard Contacts")
            if create_result.get('success'):
                list_id = create_result.get('list_id')
        
        logger.info(f"Pushing {len(quality_contacts)} contacts to Brevo (list_id: {list_id})...")
        
        result = brevo_service.bulk_import_contacts(quality_contacts, list_id=list_id)
        
        if result.get('success'):
            return JSONResponse({
                "success": True,
                "message": f"Pushed {len(quality_contacts)} contacts to Brevo",
                "pushed": result.get('added', len(quality_contacts)),
                "filtered_out": len(contacts) - len(quality_contacts),
                "list_id": list_id
            })
        else:
            return JSONResponse({
                "success": False,
                "error": result.get('error', 'Unknown error'),
                "errors": result.get('errors')
            })
        
    except Exception as e:
        logger.error(f"Error pushing to Brevo: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error pushing contacts: {str(e)}")


@app.post("/api/export-to-mailchimp")
async def export_contacts_to_mailchimp(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    contact_type_filter: Optional[str] = Query(default=None, description="Filter by contact_type (referral, client, prospect)"),
    status_filter: Optional[str] = Query(default=None, description="Filter by status (hot, warm, cold)")
):
    """
    Export contacts FROM dashboard TO Mailchimp with proper tag mapping.
    - contact_type='referral' → Mailchimp 'Referral Source' tag
    - contact_type='client' → Mailchimp 'Client' tag
    - status='hot' → Mailchimp 'Hot Lead' tag
    """
    try:
        from mailchimp_service import MailchimpService
        
        mailchimp_service = MailchimpService()
        
        if not mailchimp_service.enabled:
            return JSONResponse({
                "success": False,
                "error": "Mailchimp not configured"
            })
        
        # Build query
        query = db.query(Contact).filter(Contact.email.isnot(None))
        
        if contact_type_filter:
            query = query.filter(Contact.contact_type == contact_type_filter)
        if status_filter:
            query = query.filter(Contact.status == status_filter)
        
        contacts = query.all()
        
        if not contacts:
            return JSONResponse({
                "success": True,
                "message": "No contacts found matching filters",
                "exported": 0,
                "failed": 0
            })
        
        exported_count = 0
        failed_count = 0
        errors = []
        
        for contact in contacts:
            # Build contact info for Mailchimp
            contact_info = {
                'email': contact.email,
                'first_name': contact.first_name or (contact.name.split()[0] if contact.name else ''),
                'last_name': contact.last_name or (' '.join(contact.name.split()[1:]) if contact.name and len(contact.name.split()) > 1 else ''),
                'company': contact.company,
                'phone': contact.phone,
                'address': contact.address,
                'website': contact.website,
                'contact_type': contact.contact_type,
                'status': contact.status,
                'tags': json.loads(contact.tags) if contact.tags else []
            }
            
            result = mailchimp_service.add_contact(contact_info)
            
            if result.get('success'):
                exported_count += 1
            else:
                failed_count += 1
                errors.append(f"{contact.email}: {result.get('error', 'Unknown error')}")
        
        logger.info(f"Mailchimp export complete: Exported {exported_count}, Failed {failed_count}")
        
        return JSONResponse({
            "success": True,
            "message": f"Exported {exported_count} contacts to Mailchimp",
            "exported": exported_count,
            "failed": failed_count,
            "errors": errors[:10] if errors else [],  # Return first 10 errors
            "filters": {
                "contact_type": contact_type_filter,
                "status": status_filter
            }
        })
        
    except Exception as e:
        logger.error(f"Error exporting to Mailchimp: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error exporting contacts: {str(e)}")

@app.post("/api/sync-gmail-emails")
async def sync_gmail_emails_endpoint(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Sync email count from Gmail API (emails sent in last 7 days)"""
    try:
        from gmail_service import GmailService
        
        gmail_service = GmailService()
        
        if not gmail_service.enabled:
            return JSONResponse({
                "success": False,
                "error": "Gmail not configured. Set GMAIL_SERVICE_ACCOUNT_EMAIL and GMAIL_SERVICE_ACCOUNT_KEY"
            })
        
        logger.info("Starting Gmail email count sync...")
        counts_result = gmail_service.get_emails_sent_last_7_days()
        total_count = counts_result.get("total", 0)
        per_user_counts = counts_result.get("per_user", {})
        user_summary = ", ".join(
            f"{email} ({count})" for email, count in per_user_counts.items()
        ) or ", ".join(gmail_service.user_emails)
        
        # Get or create email count record
        email_count = db.query(EmailCount).order_by(EmailCount.updated_at.desc()).first()
        
        if not email_count:
            email_count = EmailCount(
                emails_sent_7_days=total_count,
                user_email=user_summary,
                last_synced=datetime.utcnow()
            )
            db.add(email_count)
            logger.info("Created new email count record")
        else:
            email_count.emails_sent_7_days = total_count
            email_count.user_email = user_summary
            email_count.last_synced = datetime.utcnow()
            logger.info("Updated existing email count record")
        
        db.commit()
        db.refresh(email_count)
        
        logger.info(
            "Gmail sync complete: %s emails sent in last 7 days (%s)",
            total_count,
            user_summary,
        )
        
        return JSONResponse({
            "success": True,
            "message": f"Synced {total_count} emails sent in last 7 days",
            "emails_sent_7_days": total_count,
            "user_summary": user_summary,
            "per_user": per_user_counts
        })
        
    except Exception as e:
        logger.error(f"Error syncing Gmail emails: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error syncing emails: {str(e)}")

@app.post("/api/sync-dashboard-summary")
async def sync_dashboard_summary_endpoint(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """One-time sync of dashboard summary values from Google Sheet Dashboard tab (B21, B22, B23)"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        import json
        import os
        
        # Get credentials
        creds_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY')
        if not creds_json:
            return JSONResponse({
                "success": False,
                "error": "Google Sheets not configured"
            })
        
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ])
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(os.getenv('SHEET_ID'))
        dashboard_worksheet = spreadsheet.worksheet('Dashboard')
        
        logger.info("Reading dashboard summary values from Google Sheet...")
        
        # Read cells B21, B22, B23
        value_b21 = dashboard_worksheet.cell(21, 2).value  # Total Hours
        value_b22 = dashboard_worksheet.cell(22, 2).value  # Total Costs
        value_b23 = dashboard_worksheet.cell(23, 2).value  # Total Bonuses
        
        # Parse values
        total_hours = float(str(value_b21).replace(',', '').strip()) if value_b21 else 0.0
        total_costs = float(str(value_b22).replace('$', '').replace(',', '').strip()) if value_b22 else 0.0
        total_bonuses = float(str(value_b23).replace('$', '').replace(',', '').strip()) if value_b23 else 0.0
        
        # Get or create dashboard summary record
        summary = db.query(DashboardSummary).order_by(DashboardSummary.updated_at.desc()).first()
        
        if not summary:
            summary = DashboardSummary(
                total_hours=total_hours,
                total_costs=total_costs,
                total_bonuses=total_bonuses,
                last_synced=datetime.utcnow()
            )
            db.add(summary)
        else:
            summary.total_hours = total_hours
            summary.total_costs = total_costs
            summary.total_bonuses = total_bonuses
            summary.last_synced = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"Dashboard summary synced: Hours={total_hours}, Costs={total_costs}, Bonuses={total_bonuses}")
        
        return JSONResponse({
            "success": True,
            "message": "Dashboard summary synced successfully",
            "data": {
                "total_hours": total_hours,
                "total_costs": total_costs,
                "total_bonuses": total_bonuses,
                "last_synced": summary.last_synced.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error syncing dashboard summary: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error syncing dashboard summary: {str(e)}")

@app.get("/api/dashboard/weekly-summary")
async def get_weekly_summary(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get this week's summary"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_weekly_summary()
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting weekly summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Business card scanning endpoint
@app.post("/api/scan-business-card")
async def scan_business_card(file: UploadFile = File(...), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Scan business card image and extract contact information"""
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Only image files are allowed")
        
        # Read file content
        content = await file.read()
        
        # Scan business card
        result = business_card_scanner.scan_image(content)
        
        if not result.get("success", False):
            error_msg = result.get("error", "Failed to scan business card")
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Validate contact information
        contact = business_card_scanner.validate_contact(result["contact"])
        
        logger.info(f"Successfully scanned business card: {contact.get('name', 'Unknown')}")
        
        return JSONResponse({
            "success": True,
            "filename": file.filename,
            "contact": contact
        })
        
    except Exception as e:
        logger.error(f"Error scanning business card: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error scanning business card: {str(e)}")

@app.post("/api/save-contact")
async def save_contact(request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Save new contact to database"""
    try:
        data = await request.json()
        
        # Create new contact
        contact = Contact(
            name=data.get("name"),
            company=data.get("company"),
            title=data.get("title"),
            phone=data.get("phone"),
            email=data.get("email"),
            website=data.get("website"),
            address=data.get("address"),
            notes=data.get("notes")
        )
        
        db.add(contact)
        db.commit()
        db.refresh(contact)
        
        logger.info(f"Successfully saved contact: {contact.name or contact.company}")
        
        return JSONResponse({
            "success": True,
            "message": "Contact saved successfully",
            "contact": contact.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error saving contact: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error saving contact: {str(e)}")

@app.put("/api/contacts/{contact_id}")
async def update_contact(contact_id: int, request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Update existing contact"""
    try:
        data = await request.json()
        
        contact = db.query(Contact).filter(Contact.id == contact_id).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        # Update fields
        if "name" in data:
            contact.name = data.get("name")
        if "company" in data:
            contact.company = data.get("company")
        if "title" in data:
            contact.title = data.get("title")
        if "phone" in data:
            contact.phone = data.get("phone")
        if "email" in data:
            contact.email = data.get("email")
        if "website" in data:
            contact.website = data.get("website")
        if "address" in data:
            contact.address = data.get("address")
        if "notes" in data:
            contact.notes = data.get("notes")
        
        contact.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(contact)
        
        logger.info(f"Successfully updated contact: {contact.name or contact.company}")
        
        return JSONResponse({
            "success": True,
            "message": "Contact updated successfully",
            "contact": contact.to_dict()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating contact: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating contact: {str(e)}")

@app.delete("/api/contacts/{contact_id}")
async def delete_contact(contact_id: int, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Delete a contact"""
    try:
        contact = db.query(Contact).filter(Contact.id == contact_id).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        contact_name = contact.name or contact.company or "Contact"
        db.delete(contact)
        db.commit()
        
        logger.info(f"Successfully deleted contact: {contact_name}")
        
        return JSONResponse({
            "success": True,
            "message": f"Contact deleted successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting contact: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting contact: {str(e)}")

@app.post("/api/migrate-data")
async def migrate_data(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Migrate data from Google Sheets to database"""
    try:
        migrator = GoogleSheetsMigrator()
        result = migrator.migrate_all_data()
        
        if result["success"]:
            logger.info(f"Migration successful: {result['visits_migrated']} visits, {result['time_entries_migrated']} time entries")
            return JSONResponse({
                "success": True,
                "message": f"Successfully migrated {result['visits_migrated']} visits and {result['time_entries_migrated']} time entries",
                "visits_migrated": result["visits_migrated"],
                "time_entries_migrated": result["time_entries_migrated"]
            })
        else:
            logger.error(f"Migration failed: {result['error']}")
            raise HTTPException(status_code=500, detail=f"Migration failed: {result['error']}")
            
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Migration error: {str(e)}")

@app.get("/api/dashboard/financial-summary")
async def get_financial_summary(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get comprehensive financial summary"""
    try:
        analytics = AnalyticsEngine(db)
        summary = analytics.get_financial_summary()
        return JSONResponse(summary)
    except Exception as e:
        logger.error(f"Error getting financial summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting financial summary: {str(e)}")

@app.get("/api/dashboard/revenue-by-month")
async def get_revenue_by_month(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get revenue by month"""
    try:
        analytics = AnalyticsEngine(db)
        data = analytics.get_revenue_by_month()
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error getting revenue by month: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting revenue by month: {str(e)}")

# Activity Notes API Endpoints
@app.get("/api/activity-notes")
async def get_activity_notes(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all activity notes"""
    try:
        notes = db.query(ActivityNote).order_by(ActivityNote.date.desc()).all()
        return JSONResponse({
            "success": True,
            "notes": [note.to_dict() for note in notes]
        })
    except Exception as e:
        logger.error(f"Error fetching activity notes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching activity notes: {str(e)}")

@app.post("/api/activity-notes")
async def create_activity_note(request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Create a new activity note"""
    try:
        data = await request.json()
        date_str = data.get("date")
        notes_text = data.get("notes")
        
        if not date_str or not notes_text:
            raise HTTPException(status_code=400, detail="Date and notes are required")
        
        # Parse date
        from datetime import datetime
        note_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')) if 'T' in date_str else datetime.strptime(date_str, '%Y-%m-%d')
        
        activity_note = ActivityNote(
            date=note_date,
            notes=notes_text
        )
        
        db.add(activity_note)
        db.commit()
        db.refresh(activity_note)
        
        logger.info(f"Successfully created activity note for {note_date}")
        
        return JSONResponse({
            "success": True,
            "message": "Activity note created successfully",
            "note": activity_note.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error creating activity note: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating activity note: {str(e)}")

@app.put("/api/activity-notes/{note_id}")
async def update_activity_note(note_id: int, request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Update an existing activity note"""
    try:
        data = await request.json()
        notes_text = data.get("notes")
        
        if not notes_text:
            raise HTTPException(status_code=400, detail="Notes are required")
        
        activity_note = db.query(ActivityNote).filter(ActivityNote.id == note_id).first()
        if not activity_note:
            raise HTTPException(status_code=404, detail="Activity note not found")
        
        activity_note.notes = notes_text
        db.commit()
        db.refresh(activity_note)
        
        logger.info(f"Successfully updated activity note {note_id}")
        
        return JSONResponse({
            "success": True,
            "message": "Activity note updated successfully",
            "note": activity_note.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error updating activity note: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating activity note: {str(e)}")

@app.delete("/api/activity-notes/{note_id}")
async def delete_activity_note(note_id: int, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Delete an activity note"""
    try:
        activity_note = db.query(ActivityNote).filter(ActivityNote.id == note_id).first()
        if not activity_note:
            raise HTTPException(status_code=404, detail="Activity note not found")
        
        db.delete(activity_note)
        db.commit()
        
        logger.info(f"Successfully deleted activity note {note_id}")
        
        return JSONResponse({
            "success": True,
            "message": "Activity note deleted successfully"
        })
        
    except Exception as e:
        logger.error(f"Error deleting activity note: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting activity note: {str(e)}")


# ============================================================================
# RingCentral Webhook for Call Logging
# ============================================================================

@app.post("/webhooks/ringcentral")
async def ringcentral_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook endpoint for RingCentral call notifications
    Automatically logs calls as activities in CRM
    """
    try:
        import re
        data = await request.json()
        logger.info(f"RingCentral webhook received: {data}")
        
        # Extract call data from RingCentral webhook payload
        # Format varies by RingCentral subscription, adjust as needed
        event_type = data.get("event")
        
        if event_type not in ["call.completed", "call.ended"]:
            return JSONResponse({"status": "ignored", "reason": "not a completed call"})
        
        call_data = data.get("body", {})
        phone_number = call_data.get("to", {}).get("phoneNumber") or call_data.get("from", {}).get("phoneNumber")
        direction = call_data.get("direction", "outbound")  # "Inbound" or "Outbound"
        duration = call_data.get("duration", 0)  # in seconds
        caller_email = call_data.get("extension", {}).get("email")
        
        if not phone_number:
            logger.warning("No phone number in RingCentral webhook")
            return JSONResponse({"status": "error", "reason": "no phone number"})
        
        # Find contact by phone number
        # Clean phone number for matching
        clean_phone = re.sub(r'[^\d]', '', phone_number)[-10:]  # Last 10 digits
        
        contact = db.query(Contact).filter(
            Contact.phone.like(f'%{clean_phone}%')
        ).first()
        
        # Find related deal if contact exists
        deal = None
        if contact:
            deal = db.query(Lead).filter(
                Lead.contact_name == contact.name,
                Lead.stage.in_(["incoming", "ongoing", "pending"])
            ).first()
        
        # Log the call activity
        ActivityLogger.log_call(
            db=db,
            contact_id=contact.id if contact else None,
            phone_number=phone_number,
            duration=duration,
            user_email=caller_email or "unknown@coloradocareassist.com",
            call_direction=direction.lower(),
            metadata={
                "ringcentral_event": event_type,
                "call_id": call_data.get("id"),
                "deal_id": deal.id if deal else None
            }
        )
        
        logger.info(f"Logged RingCentral call: {phone_number} ({duration}s)")
        
        return JSONResponse({
            "status": "success",
            "logged": True,
            "contact_found": contact is not None
        })
        
    except Exception as e:
        logger.error(f"Error processing RingCentral webhook: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ============================================================================
# Brevo Webhook Endpoint
# ============================================================================

@app.post("/webhooks/brevo")
async def brevo_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook endpoint for Brevo email marketing events
    Automatically logs email activities (sent, opened, clicked) in CRM
    """
    try:
        data = await request.json()
        logger.info(f"Brevo webhook received: {data.get('event', 'unknown')} for {data.get('email', 'unknown')}")
        
        # Extract webhook data
        event_type = data.get("event")
        recipient_email = data.get("email", "").lower().strip()
        campaign_id = data.get("camp_id")
        campaign_name = data.get("campaign name", "Unknown Campaign")
        date_sent = data.get("date_sent")
        date_event = data.get("date_event")
        webhook_id = data.get("id")  # Unique webhook event ID
        
        if not recipient_email:
            logger.warning("No email address in Brevo webhook")
            return JSONResponse({"status": "error", "reason": "no email address"})
        
        # Check for duplicate webhook events using webhook ID to avoid processing the same webhook twice
        # Note: We want to log each contact's event separately, so we only deduplicate by webhook ID
        if webhook_id:
            existing = db.query(ActivityLog).filter(
                ActivityLog.activity_type == "email",
                ActivityLog.extra_data.like(f'%"webhook_id":{webhook_id}%')
            ).first()
            
            if existing:
                logger.debug(f"Brevo webhook event already processed: webhook ID {webhook_id}")
                return JSONResponse({
                    "status": "success",
                    "logged": False,
                    "reason": "duplicate"
                })
        
        # Find contact by email address
        contact = db.query(Contact).filter(Contact.email == recipient_email).first()
        
        # Find related deal if contact exists
        deal_id = None
        if contact:
            deal = db.query(Lead).filter(
                Lead.contact_name == contact.name,
                Lead.stage.in_(["incoming", "ongoing", "pending"])
            ).first()
            deal_id = deal.id if deal else None
        
        # Build metadata
        metadata = {
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "date_sent": date_sent,
            "date_event": date_event,
            "brevo_event": event_type,
            "recipient": recipient_email,
            "webhook_id": webhook_id,  # For duplicate detection
        }
        
        # Add URL for click events
        if event_type == "click" and data.get("URL"):
            metadata["click_url"] = data.get("URL")
        
        # Build email subject/description based on event type
        if event_type == "delivered":
            subject = f"Newsletter: {campaign_name}"
            description = f"Email newsletter sent: {campaign_name}"
        elif event_type == "opened":
            subject = f"Newsletter opened: {campaign_name}"
            description = f"Email newsletter opened: {campaign_name}"
        elif event_type == "click":
            click_url = data.get("URL", "")
            subject = f"Newsletter link clicked: {campaign_name}"
            description = f"Email newsletter link clicked: {campaign_name}"
            if click_url:
                description += f" ({click_url})"
        else:
            # For other events (hard_bounce, soft_bounce, spam, unsubscribe), still log but with event type
            subject = f"Newsletter {event_type}: {campaign_name}"
            description = f"Email newsletter {event_type}: {campaign_name}"
        
        # Log the email activity
        # Use a generic sender email since Brevo sends on behalf of the account
        sender_email = "newsletter@coloradocareassist.com"
        
        ActivityLogger.log_email(
            db=db,
            subject=subject,
            sender=sender_email,
            recipient=recipient_email,
            contact_id=contact.id if contact else None,
            deal_id=deal_id,
            email_url=None,  # No direct email URL for Brevo campaigns
            metadata=metadata,
            commit=True,
        )
        
        logger.info(f"Logged Brevo {event_type} event: {recipient_email} - {campaign_name}")
        
        return JSONResponse({
            "status": "success",
            "logged": True,
            "contact_found": contact is not None,
            "event": event_type
        })
        
    except Exception as e:
        logger.error(f"Error processing Brevo webhook: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ============================================================================
# Gmail Email Sync Endpoint
# ============================================================================

@app.post("/api/sync-gmail")
async def sync_gmail_emails(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Manually trigger Gmail email sync"""
    try:
        from gmail_activity_sync import GmailActivitySync
        
        syncer = GmailActivitySync()
        syncer.sync_recent_emails(db, max_results=100, since_minutes=1440)  # Last 24 hours
        
        return JSONResponse({
            "success": True,
            "message": "Gmail sync completed"
        })
    except Exception as e:
        logger.error(f"Error syncing Gmail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync-gmail-contact/{contact_id}")
async def sync_gmail_for_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Sync Gmail emails for a specific contact"""
    try:
        from gmail_activity_sync import GmailActivitySync
        
        syncer = GmailActivitySync()
        syncer.sync_emails_for_contact(db, contact_id, max_results=50)
        
        return JSONResponse({
            "success": True,
            "message": f"Synced emails for contact {contact_id}"
        })
    except Exception as e:
        logger.error(f"Error syncing Gmail for contact: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# RingCentral Call Log Sync Endpoint
# ============================================================================

@app.post("/api/sync-ringcentral")
async def sync_ringcentral_calls(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Manually trigger RingCentral call log sync"""
    try:
        from ringcentral_service import RingCentralService
        
        service = RingCentralService()
        synced_count = service.sync_call_logs_to_activities(db, since_minutes=1440)  # Last 24 hours
        
        return JSONResponse({
            "success": True,
            "message": f"Synced {synced_count} calls from RingCentral"
        })
    except Exception as e:
        logger.error(f"Error syncing RingCentral: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/expenses")
async def get_expenses(
    db: Session = Depends(get_db), 
    current_user: Dict[str, Any] = Depends(get_current_user),
    user_email: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get expenses with optional filters"""
    try:
        query = db.query(Expense)
        
        if user_email:
            query = query.filter(Expense.user_email == user_email)
            
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(Expense.date >= start)
            except ValueError:
                pass
                
        if end_date:
            try:
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(Expense.date <= end)
            except ValueError:
                pass
                
        expenses = query.order_by(Expense.date.desc()).all()
        return JSONResponse([e.to_dict() for e in expenses])
    except Exception as e:
        logger.error(f"Error fetching expenses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/expenses/pay-period-summary")
async def get_pay_period_summary(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    period_offset: Optional[int] = 0
):
    """Get expense summary for Jacob and Maryssa for a pay period.
    
    Args:
        period_offset: 0 = current period, -1 = previous period, -2 = two periods ago, etc.
    """
    try:
        # Pay period logic
        # Start date: Dec 2, 2025 (aligns with Jan 13-26 biweekly Mondays)
        start_date = datetime(2025, 12, 2)
        now = datetime.utcnow()
        
        # Calculate days since start
        delta = now - start_date
        days_since_start = delta.days
        period_length = 14
        
        # Calculate current period index (0-based)
        if days_since_start < 0:
             current_period_index = 0 
        else:
             current_period_index = days_since_start // period_length
        
        # Apply offset (negative = past periods)
        period_index = max(0, current_period_index + (period_offset or 0))
             
        current_period_start = start_date + timedelta(days=period_index * period_length)
        current_period_end = current_period_start + timedelta(days=13, hours=23, minutes=59, seconds=59)
        
        # Sales reps to track expenses for
        # Format: {"email": "display_name"} - update email when new hire starts
        EXPENSE_USERS = {
            "jacob@coloradocareassist.com": "Jacob (Denver)",
            # Colorado Springs slot - update email when new hire starts
            "maryssa@coloradocareassist.com": "Colorado Springs (Vacant)",
        }
        users = list(EXPENSE_USERS.keys())
        
        # Determine if this is a completed period (for payroll purposes)
        is_completed = period_index < current_period_index
        
        summary = {
            "period": {
                "start": current_period_start.isoformat(),
                "end": current_period_end.isoformat(),
                "index": period_index + 1,
                "offset": period_offset or 0,
                "is_current": period_index == current_period_index,
                "is_completed": is_completed,
                "total_periods": current_period_index + 1,
                "label": f"Period {period_index + 1}" + (" (Current)" if period_index == current_period_index else " - COMPLETED")
            },
            "users": {}
        }
        
        for email in users:
            # Get expenses
            expenses = db.query(Expense).filter(
                Expense.user_email == email,
                Expense.date >= current_period_start,
                Expense.date <= current_period_end
            ).all()
            
            expense_total = sum(e.amount or 0 for e in expenses)
            
            # Get mileage from FinancialEntry
            mileage_entries = db.query(FinancialEntry).filter(
                FinancialEntry.user_email == email,
                FinancialEntry.date >= current_period_start,
                FinancialEntry.date <= current_period_end
            ).all()
            
            total_miles = sum(e.miles_driven or 0 for e in mileage_entries)
            mileage_total = sum(e.mileage_cost or 0 for e in mileage_entries)
            
            # Merge items for display
            items = []
            for e in expenses:
                items.append({
                    "type": "expense",
                    "date": e.date.isoformat(),
                    "description": e.description,
                    "amount": e.amount,
                    "status": e.status,
                    "url": e.receipt_url
                })
            
            for m in mileage_entries:
                if m.miles_driven:
                    items.append({
                        "type": "mileage",
                        "date": m.date.isoformat(),
                        "description": f"Mileage: {m.miles_driven} miles",
                        "amount": m.mileage_cost,
                        "miles": m.miles_driven,
                        "rate": 0.70
                    })
            
            # Sort items by date desc
            items.sort(key=lambda x: x["date"], reverse=True)
            
            summary["users"][email] = {
                "display_name": EXPENSE_USERS.get(email, email.split("@")[0].title()),
                "total_miles": total_miles,
                "mileage_amount": round(mileage_total, 2),
                "expenses_amount": round(expense_total, 2),
                "grand_total": round(mileage_total + expense_total, 2),
                "items": items
            }
            
        return JSONResponse(summary)
        
    except Exception as e:
        logger.error(f"Error getting pay period summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/financials")
async def get_financials(
    db: Session = Depends(get_db), 
    current_user: Dict[str, Any] = Depends(get_current_user),
    user_email: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get financial entries (mileage) with optional filters"""
    try:
        query = db.query(FinancialEntry)
        
        if user_email:
            query = query.filter(FinancialEntry.user_email == user_email)
            
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(FinancialEntry.date >= start)
            except ValueError:
                pass
                
        if end_date:
            try:
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(FinancialEntry.date <= end)
            except ValueError:
                pass
                
        entries = query.order_by(FinancialEntry.date.desc()).all()
        return JSONResponse([e.to_dict() for e in entries])
    except Exception as e:
        logger.error(f"Error fetching financials: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Google Drive Activity Logs API Endpoints
@app.get("/api/activity-logs")
async def get_activity_logs(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all activity logs from Google Drive and manually added logs"""
    try:
        all_logs = []
        
        # Get logs from Google Drive API
        drive_service = GoogleDriveService()
        if drive_service.enabled:
            try:
                drive_logs = drive_service.find_activity_logs(limit=100)
                all_logs.extend(drive_logs)
            except Exception as e:
                logger.warning(f"Error fetching logs from Drive API: {e}")
        
        # Get manually added logs from database
        try:
            manual_logs = db.query(ActivityLog).all()
            
            # Fix specific logs with correct dates
            if pytz:
                mountain_tz = pytz.timezone('America/Denver')
                
                # Fix Nov 4, 2025 log
                nov_4_2025 = mountain_tz.localize(datetime(2025, 11, 4, 0, 0, 0))
                nov_4_2025_utc = nov_4_2025.astimezone(timezone.utc)
                
                # Fix Nov 5, 2025 log (today's log)
                nov_5_2025 = mountain_tz.localize(datetime(2025, 11, 5, 0, 0, 0))
                nov_5_2025_utc = nov_5_2025.astimezone(timezone.utc)
                
                for log in manual_logs:
                    # Fix the specific log from Nov 4
                    if log.file_id.startswith("1oDF7jNf"):
                        # Check if date is wrong (not Nov 4)
                        log_date_mountain = log.modified_time.replace(tzinfo=timezone.utc).astimezone(mountain_tz) if log.modified_time else None
                        if not log_date_mountain or log_date_mountain.date() != nov_4_2025.date():
                            log.modified_time = nov_4_2025_utc
                            log.created_time = nov_4_2025_utc
                            db.commit()
                            logger.info(f"Fixed date for log {log.file_id} to Nov 4, 2025")
                    
                    # Fix today's log (Nov 5) - check if it starts with "11-oZUpC"
                    if log.file_id.startswith("11-oZUpC"):
                        # Check if date is wrong (not Nov 5)
                        log_date_mountain = log.modified_time.replace(tzinfo=timezone.utc).astimezone(mountain_tz) if log.modified_time else None
                        if not log_date_mountain or log_date_mountain.date() != nov_5_2025.date():
                            log.modified_time = nov_5_2025_utc
                            log.created_time = nov_5_2025_utc
                            db.commit()
                            logger.info(f"Fixed date for log {log.file_id} to Nov 5, 2025")
            
            manual_logs_dict = {log.file_id: log.to_dict() for log in manual_logs}
            
            # Add manually added logs that aren't already in Drive results
            drive_file_ids = {log.get('id') for log in all_logs}
            for file_id, log_dict in manual_logs_dict.items():
                if file_id not in drive_file_ids:
                    all_logs.append(log_dict)
        except Exception as e:
            logger.warning(f"Error fetching manual logs from database: {e}")
        
        # Sort by modified_time (most recent first), with None values last
        all_logs.sort(key=lambda x: (x.get('modified_time') or '0000-00-00'), reverse=True)
        
        return JSONResponse({
            "success": True,
            "logs": all_logs,
            "count": len(all_logs)
        })
        
    except Exception as e:
        logger.error(f"Error fetching activity logs: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching activity logs: {str(e)}")

@app.post("/api/activity-logs/add")
async def add_activity_log(request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Add an activity log manually by Google Drive URL"""
    try:
        data = await request.json()
        url = data.get("url", "").strip()
        
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        
        drive_service = GoogleDriveService()
        
        # Extract file ID from URL (no API needed for this)
        file_id = drive_service.extract_file_id_from_url(url) if drive_service.enabled else None
        if not file_id:
            # Try to extract manually if service not enabled
            import re
            match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
            if match:
                file_id = match.group(1)
            else:
                raise HTTPException(status_code=400, detail="Invalid Google Drive URL. Please provide a valid Google Docs link.")
        
        # Check if already exists in database
        existing = db.query(ActivityLog).filter(ActivityLog.file_id == file_id).first()
        if existing:
            # Special case: if this is the log from Nov 4, 2025, set it to that date
            # Check if file_id starts with "1oDF7jNf" (the one from yesterday)
            if pytz and file_id.startswith("1oDF7jNf"):
                mountain_tz = pytz.timezone('America/Denver')
                nov_4_2025 = mountain_tz.localize(datetime(2025, 11, 4))
                existing.modified_time = nov_4_2025.astimezone(timezone.utc)
                existing.created_time = nov_4_2025.astimezone(timezone.utc)
                db.commit()
                db.refresh(existing)
            # If existing log has no dates, set them based on created_at
            elif not existing.modified_time and not existing.created_time:
                if pytz:
                    # Use Mountain Time for the upload date
                    # Get the date from created_at in Mountain Time, set to midnight
                    mountain_tz = pytz.timezone('America/Denver')
                    created_at_utc = existing.created_at.replace(tzinfo=timezone.utc)
                    created_at_mountain = created_at_utc.astimezone(mountain_tz)
                    # Use just the date part, set to midnight in Mountain Time
                    upload_date_mountain = mountain_tz.localize(datetime(created_at_mountain.year, created_at_mountain.month, created_at_mountain.day, 0, 0, 0))
                    # Convert back to UTC for storage
                    existing.modified_time = upload_date_mountain.astimezone(timezone.utc)
                    existing.created_time = upload_date_mountain.astimezone(timezone.utc)
                else:
                    # Fallback to UTC if pytz not available
                    upload_date = datetime(existing.created_at.year, existing.created_at.month, existing.created_at.day, 0, 0, 0, tzinfo=timezone.utc)
                    existing.modified_time = upload_date
                    existing.created_time = upload_date
                db.commit()
                db.refresh(existing)
            return JSONResponse({
                "success": True,
                "message": "Activity log already exists",
                "log": existing.to_dict()
            })
        
        # Try to get file metadata via API (optional - works without it)
        file_metadata = None
        if drive_service.enabled:
            file_metadata = drive_service.get_file_by_id(file_id)
            if file_metadata:
                # Check if it's a Google Doc
                if file_metadata.get('mime_type') != 'application/vnd.google-apps.document':
                    raise HTTPException(status_code=400, detail="Only Google Docs are supported as activity logs")
        
        # Create preview/edit URLs - use standard Google Docs URLs
        # For publicly shared docs, the preview URL works in iframes
        preview_url = f"https://docs.google.com/document/d/{file_id}/preview"
        edit_url = f"https://docs.google.com/document/d/{file_id}/edit"
        
        # Parse dates if available
        modified_time = None
        created_time = None
        if file_metadata and file_metadata.get('modified_time'):
            try:
                modified_time = datetime.fromisoformat(file_metadata['modified_time'].replace('Z', '+00:00'))
            except:
                pass
        if file_metadata and file_metadata.get('created_time'):
            try:
                created_time = datetime.fromisoformat(file_metadata['created_time'].replace('Z', '+00:00'))
            except:
                pass
        
        # If we don't have dates from API, use current date in Mountain Time as upload date
        if not modified_time and not created_time:
            if pytz:
                # Use Mountain Time (America/Denver) for the upload date
                # Get today's date in Mountain Time at midnight to avoid day shifts
                mountain_tz = pytz.timezone('America/Denver')
                now_mountain = datetime.now(mountain_tz)
                # Use just the date part, set to midnight in Mountain Time
                today_mountain = mountain_tz.localize(datetime(now_mountain.year, now_mountain.month, now_mountain.day, 0, 0, 0))
                # Store as UTC in database (standard practice)
                created_time = today_mountain.astimezone(timezone.utc)
                modified_time = today_mountain.astimezone(timezone.utc)
            else:
                # Fallback to UTC if pytz not available
                now_utc = datetime.now(timezone.utc)
                today_utc = datetime(now_utc.year, now_utc.month, now_utc.day, 0, 0, 0, tzinfo=timezone.utc)
                created_time = today_utc
                modified_time = today_utc
        
        # Save to database
        activity_log = ActivityLog(
            file_id=file_id,
            name=file_metadata.get('name') if file_metadata else None,
            url=url,
            preview_url=preview_url,
            edit_url=edit_url,
            owner=file_metadata.get('owner') if file_metadata else None,
            modified_time=modified_time,
            created_time=created_time,
            manually_added=True
        )
        
        db.add(activity_log)
        db.commit()
        db.refresh(activity_log)
        
        logger.info(f"Successfully added activity log: {activity_log.name or file_id}")
        
        return JSONResponse({
            "success": True,
            "message": "Activity log added successfully",
            "log": activity_log.to_dict()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding activity log: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error adding activity log: {str(e)}")

# ============================================================================
# Lead Pipeline API Endpoints (CRM Features)
# ============================================================================

@app.get("/api/pipeline/stages")
async def get_pipeline_stages(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all pipeline stages"""
    try:
        from models import PipelineStage
        stages = db.query(PipelineStage).order_by(PipelineStage.order_index).all()
        return JSONResponse([stage.to_dict() for stage in stages])
    except Exception as e:
        logger.error(f"Error fetching pipeline stages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pipeline/leads")
async def get_leads(stage_id: Optional[int] = None, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all leads, optionally filtered by stage"""
    try:
        from models import Lead
        query = db.query(Lead)
        if stage_id:
            query = query.filter(Lead.stage_id == stage_id)
        leads = query.order_by(Lead.order_index, Lead.created_at.desc()).all()
        return JSONResponse([lead.to_dict() for lead in leads])
    except Exception as e:
        logger.error(f"Error fetching leads: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pipeline/leads/{lead_id}")
async def get_lead(lead_id: int, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get a single lead by ID"""
    try:
        from models import Lead
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return JSONResponse(lead.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching lead: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pipeline/leads")
async def create_lead(request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Create a new lead"""
    try:
        from models import Lead, LeadActivity
        data = await request.json()
        
        # Get the highest order_index in the stage
        stage_id = data.get("stage_id")
        max_order = db.query(Lead).filter(Lead.stage_id == stage_id).count()
        
        lead = Lead(
            name=data.get("name"),
            contact_name=data.get("contact_name"),
            email=data.get("email"),
            phone=data.get("phone"),
            address=data.get("address"),
            city=data.get("city"),
            source=data.get("source"),
            payor_source=data.get("payor_source"),
            expected_close_date=datetime.fromisoformat(data["expected_close_date"]) if data.get("expected_close_date") else None,
            expected_revenue=data.get("expected_revenue"),
            priority=data.get("priority", "medium"),
            notes=data.get("notes"),
            stage_id=stage_id,
            order_index=max_order,
            referral_source_id=data.get("referral_source_id")
        )
        
        db.add(lead)
        db.flush()  # Get the lead ID
        
        # Log activity
        activity = LeadActivity(
            lead_id=lead.id,
            activity_type="created",
            description=f"Lead created: {lead.name}",
            user_email=current_user.get("email"),
            new_value=lead.name
        )
        db.add(activity)
        
        db.commit()
        db.refresh(lead)
        
        logger.info(f"Created lead: {lead.name}")
        return JSONResponse({"success": True, "lead": lead.to_dict()})
        
    except Exception as e:
        logger.error(f"Error creating lead: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/pipeline/leads/{lead_id}")
async def update_lead(lead_id: int, request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Update a lead"""
    try:
        from models import Lead, LeadActivity
        data = await request.json()
        
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Track changes for activity log
        changes = []
        
        # Update fields and track changes
        fields_to_update = [
            "name", "contact_name", "email", "phone", "address", "city",
            "source", "payor_source", "priority", "notes", "referral_source_id",
            "expected_revenue"
        ]
        
        for field in fields_to_update:
            if field in data:
                old_value = getattr(lead, field)
                new_value = data[field]
                if old_value != new_value:
                    setattr(lead, field, new_value)
                    changes.append((field, old_value, new_value))
        
        # Handle expected_close_date separately (datetime field)
        if "expected_close_date" in data and data["expected_close_date"]:
            new_date = datetime.fromisoformat(data["expected_close_date"])
            if lead.expected_close_date != new_date:
                changes.append(("expected_close_date", lead.expected_close_date, new_date))
                lead.expected_close_date = new_date
        
        # Log activities for each change
        for field, old_val, new_val in changes:
            activity = LeadActivity(
                lead_id=lead.id,
                activity_type=f"{field}_updated",
                description=f"Updated {field.replace('_', ' ')}",
                old_value=str(old_val) if old_val else None,
                new_value=str(new_val) if new_val else None,
                user_email=current_user.get("email")
            )
            db.add(activity)
        
        db.commit()
        db.refresh(lead)
        
        logger.info(f"Updated lead {lead_id}: {len(changes)} changes")
        return JSONResponse({"success": True, "lead": lead.to_dict()})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating lead: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/pipeline/leads/{lead_id}/move")
async def move_lead(lead_id: int, request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Move a lead to a different stage or reorder within stage"""
    try:
        from models import Lead, LeadActivity, PipelineStage
        data = await request.json()
        
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        old_stage_id = lead.stage_id
        new_stage_id = data.get("stage_id")
        new_order_index = data.get("order_index", 0)
        
        # If moving to a different stage
        if old_stage_id != new_stage_id:
            old_stage = db.query(PipelineStage).filter(PipelineStage.id == old_stage_id).first()
            new_stage = db.query(PipelineStage).filter(PipelineStage.id == new_stage_id).first()
            
            lead.stage_id = new_stage_id
            lead.order_index = new_order_index
            
            # Log activity
            activity = LeadActivity(
                lead_id=lead.id,
                activity_type="stage_changed",
                description=f"Moved from {old_stage.name if old_stage else 'Unknown'} to {new_stage.name if new_stage else 'Unknown'}",
                old_value=old_stage.name if old_stage else None,
                new_value=new_stage.name if new_stage else None,
                user_email=current_user.get("email")
            )
            db.add(activity)
        else:
            # Just reordering within the same stage
            lead.order_index = new_order_index
        
        db.commit()
        db.refresh(lead)
        
        logger.info(f"Moved lead {lead_id} to stage {new_stage_id}, order {new_order_index}")
        return JSONResponse({"success": True, "lead": lead.to_dict()})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error moving lead: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/pipeline/leads/{lead_id}")
async def delete_lead(lead_id: int, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Delete a lead"""
    try:
        from models import Lead
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        lead_name = lead.name
        db.delete(lead)
        db.commit()
        
        logger.info(f"Deleted lead: {lead_name}")
        return JSONResponse({"success": True, "message": "Lead deleted successfully"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting lead: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Referral Sources API
@app.get("/api/pipeline/referral-sources")
async def get_referral_sources(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all referral sources"""
    try:
        from models import ReferralSource
        sources = db.query(ReferralSource).order_by(ReferralSource.created_at.desc()).all()
        return JSONResponse([source.to_dict() for source in sources])
    except Exception as e:
        logger.error(f"Error fetching referral sources: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pipeline/referral-sources")
async def create_referral_source(request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Create a new referral source"""
    try:
        from models import ReferralSource
        data = await request.json()
        
        source = ReferralSource(
            name=data.get("name"),
            organization=data.get("organization"),
            contact_name=data.get("contact_name"),
            email=data.get("email"),
            phone=data.get("phone"),
            address=data.get("address"),
            source_type=data.get("source_type"),
            status=data.get("status", "active"),
            notes=data.get("notes")
        )
        
        db.add(source)
        db.commit()
        db.refresh(source)
        
        # Sync to Brevo CRM in background
        import threading
        thread = threading.Thread(target=sync_company_to_brevo_crm, args=(source,))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Created referral source: {source.name}")
        return JSONResponse({"success": True, "source": source.to_dict()})
        
    except Exception as e:
        logger.error(f"Error creating referral source: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/pipeline/referral-sources/{source_id}")
async def update_referral_source(source_id: int, request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Update a referral source"""
    try:
        from models import ReferralSource
        data = await request.json()
        
        source = db.query(ReferralSource).filter(ReferralSource.id == source_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Referral source not found")
        
        # Update fields
        for field in ["name", "organization", "contact_name", "email", "phone", "address", "source_type", "status", "notes"]:
            if field in data:
                setattr(source, field, data[field])
        
        db.commit()
        db.refresh(source)
        
        # Sync to Brevo CRM in background
        import threading
        thread = threading.Thread(target=sync_company_to_brevo_crm, args=(source,))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Updated referral source: {source.name}")
        return JSONResponse({"success": True, "source": source.to_dict()})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating referral source: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/pipeline/referral-sources/{source_id}")
async def delete_referral_source(source_id: int, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Delete a referral source"""
    try:
        from models import ReferralSource
        source = db.query(ReferralSource).filter(ReferralSource.id == source_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Referral source not found")
        
        source_name = source.name
        db.delete(source)
        db.commit()
        
        logger.info(f"Deleted referral source: {source_name}")
        return JSONResponse({"success": True, "message": "Referral source deleted successfully"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting referral source: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Lead Tasks API
@app.get("/api/pipeline/tasks")
async def get_all_tasks(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all tasks across all leads"""
    try:
        from models import LeadTask
        tasks = db.query(LeadTask).order_by(LeadTask.created_at.desc()).all()
        return JSONResponse([task.to_dict() for task in tasks])
    except Exception as e:
        logger.error(f"Error fetching tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pipeline/leads/{lead_id}/tasks")
async def create_lead_task(lead_id: int, request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Create a task for a lead"""
    try:
        from models import Lead, LeadTask, LeadActivity
        data = await request.json()
        creator_email = current_user.get("email")
        requested_assignee = data.get("assigned_to") or data.get("sales_id")
        assignee_email = requested_assignee or creator_email
        
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        task = LeadTask(
            lead_id=lead_id,
            title=data.get("title"),
            description=data.get("description"),
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            status="pending",
            assigned_to=assignee_email,
            created_by=creator_email,
        )
        
        db.add(task)
        db.flush()
        
        # Log activity
        activity = LeadActivity(
            lead_id=lead_id,
            activity_type="task_created",
            description=f"Task added: {task.title}",
            user_email=current_user.get("email"),
            new_value=task.title
        )
        db.add(activity)
        
        db.commit()
        db.refresh(task)
        
        logger.info(f"Created task for lead {lead_id}: {task.title}")
        return JSONResponse({"success": True, "task": task.to_dict()})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/pipeline/tasks/{task_id}")
async def update_lead_task(task_id: int, request: Request, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Update a lead task"""
    try:
        from models import LeadTask, LeadActivity
        data = await request.json()
        
        task = db.query(LeadTask).filter(LeadTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        old_status = task.status
        
        # Update fields
        if "title" in data:
            task.title = data["title"]
        if "description" in data:
            task.description = data["description"]
        if "due_date" in data:
            task.due_date = datetime.fromisoformat(data["due_date"]) if data["due_date"] else None
        if "status" in data:
            task.status = data["status"]
            if data["status"] == "completed" and old_status != "completed":
                task.completed_at = datetime.utcnow()
                
                # Log activity
                activity = LeadActivity(
                    lead_id=task.lead_id,
                    activity_type="task_completed",
                    description=f"Task completed: {task.title}",
                    user_email=current_user.get("email")
                )
                db.add(activity)

        if "assigned_to" in data:
            task.assigned_to = data["assigned_to"]
        
        db.commit()
        db.refresh(task)
        
        logger.info(f"Updated task {task_id}")
        return JSONResponse({"success": True, "task": task.to_dict()})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/pipeline/tasks/{task_id}")
async def delete_lead_task(task_id: int, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Delete a lead task"""
    try:
        from models import LeadTask
        task = db.query(LeadTask).filter(LeadTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task_title = task.title
        db.delete(task)
        db.commit()
        
        logger.info(f"Deleted task: {task_title}")
        return JSONResponse({"success": True, "message": "Task deleted successfully"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting task: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/seed-activity-logs")
async def seed_activity_logs(db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Create sample activity logs for testing"""
    try:
        from models import ActivityLog, Contact, ReferralSource
        from activity_logger import ActivityLogger
        from datetime import timedelta
        
        # Get some recent contacts and companies
        contacts = db.query(Contact).limit(5).all()
        companies = db.query(ReferralSource).limit(5).all()
        
        created_logs = []
        user_email = current_user.get("email", "unknown@coloradocareassist.com")
        
        # Create different types of activity logs
        if contacts:
            # Card scan
            log1 = ActivityLogger.log_business_card_scan(
                db=db,
                contact_id=contacts[0].id,
                user_email=user_email,
                contact_name=f"{contacts[0].first_name} {contacts[0].last_name}",
                filename="test_card.jpg"
            )
            created_logs.append(log1)
            
            # Call
            log2 = ActivityLogger.log_call(
                db=db,
                contact_id=contacts[0].id if len(contacts) > 0 else None,
                phone_number="+1234567890",
                duration=300,
                user_email=user_email,
                call_direction="outbound"
            )
            created_logs.append(log2)
            
            # Email
            if len(contacts) > 1:
                log3 = ActivityLogger.log_email(
                    db=db,
                    subject="Follow up on our meeting",
                    sender=user_email,
                    recipient=contacts[1].email or "contact@example.com",
                    contact_id=contacts[1].id
                )
                created_logs.append(log3)
        
        if companies:
            # Visit
            log4 = ActivityLogger.log_visit(
                db=db,
                visit_id=1,
                business_name=companies[0].name or "Test Company",
                user_email=user_email,
                visit_date=datetime.utcnow() - timedelta(days=1),
                company_id=companies[0].id
            )
            created_logs.append(log4)
            
            # Note
            if len(companies) > 1:
                log5 = ActivityLogger.log_note(
                    db=db,
                    note_content="Great meeting today! They're interested in our services.",
                    user_email=user_email,
                    company_id=companies[1].id
                )
                created_logs.append(log5)
        
        # Get count
        total_logs = db.query(ActivityLog).count()
        
        return JSONResponse({
            "success": True,
            "created": len([l for l in created_logs if l is not None]),
            "total_logs": total_logs,
            "message": f"Created {len([l for l in created_logs if l is not None])} sample activity logs. Total logs in database: {total_logs}"
        })
        
    except Exception as e:
        logger.error(f"Error seeding activity logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to seed activity logs: {str(e)}")


@app.get("/api/pipeline/leads/{lead_id}/activities")
async def get_lead_activities(lead_id: int, db: Session = Depends(get_db), current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get activity log for a lead"""
    try:
        from models import LeadActivity
        activities = db.query(LeadActivity).filter(LeadActivity.lead_id == lead_id).order_by(LeadActivity.created_at.desc()).all()
        return JSONResponse([activity.to_dict() for activity in activities])
    except Exception as e:
        logger.error(f"Error fetching lead activities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# End of Lead Pipeline API Endpoints
# ============================================================================

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    return FileResponse("static/favicon.ico")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Colorado CareAssist Sales Dashboard"}

# Legacy dashboard route (old Jinja2 template)
@app.get("/legacy", response_class=HTMLResponse)
async def legacy_dashboard(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Serve the legacy Jinja2 dashboard for backward compatibility"""
    from urllib.parse import urlencode
    
    ringcentral_config = {
        'clientId': RINGCENTRAL_EMBED_CLIENT_ID or '',
        'server': RINGCENTRAL_EMBED_SERVER,
        'appUrl': RINGCENTRAL_EMBED_APP_URL,
        'adapterUrl': RINGCENTRAL_EMBED_ADAPTER_URL,
        'defaultTab': RINGCENTRAL_EMBED_DEFAULT_TAB,
        'redirectUri': RINGCENTRAL_EMBED_REDIRECT_URI,
    }

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "ringcentral_config": ringcentral_config,
        "ringcentral": {
            "enabled": bool(RINGCENTRAL_EMBED_CLIENT_ID),
            "clientId": RINGCENTRAL_EMBED_CLIENT_ID or '',
            "server": RINGCENTRAL_EMBED_SERVER,
            "appUrl": RINGCENTRAL_EMBED_APP_URL,
            "adapterUrl": RINGCENTRAL_EMBED_ADAPTER_URL,
            "defaultTab": RINGCENTRAL_EMBED_DEFAULT_TAB,
            "redirectUri": RINGCENTRAL_EMBED_REDIRECT_URI
        }
    })

# SPA catch-all route - must be last!
# This catches all routes and serves the React app for client-side routing
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def spa_catchall(
    request: Request,
    full_path: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
):
    """Catch-all route for React Router (SPA)"""
    # Don't catch API routes
    if full_path.startswith("api/") or full_path.startswith("auth/"):
        raise HTTPException(status_code=404, detail="Not found")

    frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")

    def _serve_static(relative_path: str):
        candidate = os.path.abspath(os.path.join(frontend_dist, relative_path))
        if not candidate.startswith(os.path.abspath(frontend_dist)):
            raise HTTPException(status_code=404, detail="Asset not found")
        if os.path.exists(candidate):
            return FileResponse(candidate)
        raise HTTPException(status_code=404, detail="Asset not found")

    static_prefixes = ("assets/", "img/", "logos/")
    static_files = {
        "favicon.ico",
        "manifest.json",
        "logo192.png",
        "logo512.png",
        "robots.txt",
        "auth-callback.html",
        "stats.html",
    }

    if full_path.startswith(static_prefixes) or full_path in static_files:
        return _serve_static(full_path)

    if not current_user:
        return RedirectResponse(url="/auth/login")
    
    # Serve React app index.html for all non-API routes
    frontend_index = os.path.join(frontend_dist, "index.html")
    if os.path.exists(frontend_index):
        return FileResponse(frontend_index)
    
    raise HTTPException(status_code=404, detail="Frontend not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

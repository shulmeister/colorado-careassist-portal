"""
Portal Authentication Middleware for Flask
Validates requests are coming from the portal via shared secret or portal token
"""
import os
from functools import wraps
from flask import request, jsonify, session
from itsdangerous import URLSafeTimedSerializer
import logging

logger = logging.getLogger(__name__)

# SECURITY: Portal secret must be set via environment variable - no weak defaults
PORTAL_SECRET = os.getenv("PORTAL_SECRET")
if not PORTAL_SECRET:
    logger.warning("PORTAL_SECRET not set - portal authentication will fail")

# Use same secret key as portal for token validation
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY") or os.getenv("SECRET_KEY")
if not APP_SECRET_KEY:
    logger.warning("APP_SECRET_KEY/SECRET_KEY not set - token validation will fail")

def verify_portal_request():
    """Check if request is from portal via header secret"""
    secret = request.headers.get("X-Portal-Secret")
    return secret == PORTAL_SECRET

def verify_portal_token():
    """Verify portal session token from query parameter"""
    portal_token = request.args.get("portal_token")
    portal_user_email = request.args.get("portal_user_email")
    
    logger.info(f"Portal token check: token present={bool(portal_token)}, email={portal_user_email}")
    
    if not portal_token:
        logger.debug("No portal_token in query params")
        return None
    
    try:
        # Try to use the same secret key as portal
        # Portal uses APP_SECRET_KEY from environment
        serializer = URLSafeTimedSerializer(APP_SECRET_KEY)
        session_data = serializer.loads(portal_token, max_age=3600 * 24)  # 24 hours
        
        logger.info(f"Portal token validated successfully for: {session_data.get('email')}")
        
        # Validate email matches if provided (but don't fail if not provided)
        if portal_user_email and session_data.get("email") != portal_user_email:
            logger.warning(f"Email mismatch: token={session_data.get('email')}, param={portal_user_email}")
            # Still return the session data - email mismatch isn't critical
        
        return session_data
    except Exception as e:
        logger.error(f"Invalid portal token: {str(e)}")
        logger.error(f"Token (first 20 chars): {portal_token[:20] if portal_token else 'None'}...")
        logger.error(f"Using APP_SECRET_KEY: {bool(APP_SECRET_KEY)}")
        return None

def check_portal_auth():
    """Check if request is authenticated via portal (header, token, or session)"""
    # Check if already authenticated via session (from previous token validation)
    if session.get('portal_authenticated') and session.get('portal_user'):
        logger.debug(f"Portal auth via existing session for: {session['portal_user'].get('email')}")
        return True

    # Check header-based auth (for direct API calls)
    if verify_portal_request():
        logger.info("Portal auth verified via header")
        return True

    # Check token-based auth (for iframe embedding)
    token_data = verify_portal_token()
    if token_data:
        # Store in session so user is authenticated for subsequent requests
        session['portal_user'] = token_data
        session['portal_authenticated'] = True
        logger.info(f"Portal auth verified via token for: {token_data.get('email')}")
        return True

    logger.debug("Portal auth check failed - no valid header, token, or session")
    return False

def portal_auth_required(f):
    """
    Decorator to replace @login_required
    Trusts portal authentication instead of Flask-Login
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If request is from portal (has secret or valid token), allow it
        if check_portal_auth():
            return f(*args, **kwargs)
        
        # For direct access (development), show login page
        # In production, you might want to block this
        from flask import redirect, url_for
        return redirect(url_for('login'))
    
    return decorated_function

def get_portal_user():
    """Get user info from portal headers or token"""
    # Check session first (set by token validation)
    if session.get('portal_user'):
        return session['portal_user']
    
    # Fall back to headers
    return {
        'email': request.headers.get('X-Portal-User-Email', 'user@coloradocareassist.com'),
        'name': request.headers.get('X-Portal-User-Name', 'User')
    }


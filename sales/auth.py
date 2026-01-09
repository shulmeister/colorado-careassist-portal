import os
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Request, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleRequest
import httpx
import logging
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Security scheme for API documentation
security = HTTPBearer(auto_error=False)

class GoogleOAuthManager:
    """Manage Google OAuth authentication for Colorado CareAssist"""
    
    def __init__(self):
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("SALES_GOOGLE_REDIRECT_URI", os.getenv("GOOGLE_REDIRECT_URI", "https://portal.coloradocareassist.com/sales/auth/callback"))
        self.scopes = [
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/business.manage",
            "openid"
        ]
        
        # Session management
        self.secret_key = os.getenv("APP_SECRET_KEY", secrets.token_urlsafe(32))
        self.serializer = URLSafeTimedSerializer(self.secret_key)
        
        # Allowed domains (your Google Workspace domain)
        self.allowed_domains = os.getenv("ALLOWED_DOMAINS", "coloradocareassist.com").split(",")
        
        if not self.client_id or not self.client_secret:
            logger.warning("Google OAuth credentials not configured. Authentication will be disabled.")
    
    def get_authorization_url(self) -> str:
        """Get Google OAuth authorization URL"""
        if not self.client_id or not self.client_secret:
            raise HTTPException(
                status_code=503, 
                detail="Google OAuth not configured"
            )
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = self.redirect_uri
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        return authorization_url
    
    async def handle_callback(self, code: str, state: str) -> Dict[str, Any]:
        """Handle OAuth callback and create session"""
        if not self.client_id or not self.client_secret:
            raise HTTPException(
                status_code=503, 
                detail="Google OAuth not configured"
            )
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = self.redirect_uri
        
        try:
            # Exchange code for token
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Get user info
            user_info = await self._get_user_info(credentials.token)
            
            # Validate domain
            email = user_info.get("email", "")
            domain = email.split("@")[-1] if "@" in email else ""
            
            if domain not in self.allowed_domains:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied. Only {', '.join(self.allowed_domains)} domains are allowed."
                )
            
            # Create session token
            session_data = {
                "user_id": user_info.get("id"),
                "email": user_info.get("email"),
                "name": user_info.get("name"),
                "picture": user_info.get("picture"),
                "domain": domain,
                "login_time": datetime.utcnow().isoformat()
            }
            
            session_token = self.serializer.dumps(session_data)
            
            logger.info(f"User authenticated: {user_info.get('email')}")
            
            return {
                "success": True,
                "user": user_info,
                "session_token": session_token,
                "expires_in": 3600 * 24  # 24 hours
            }
            
        except Exception as e:
            logger.error(f"OAuth callback error: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Authentication failed: {str(e)}"
            )
    
    async def _get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Google"""
        async with httpx.AsyncClient() as client:
            # Use Google Identity API instead of deprecated Google+ API
            response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.json()
    
    def verify_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Verify session token and return user data"""
        try:
            session_data = self.serializer.loads(session_token, max_age=3600 * 24)  # 24 hours
            return session_data
        except Exception as e:
            logger.warning(f"Invalid session token: {str(e)}")
            return None
    
    def logout(self, session_token: str) -> bool:
        """Logout user (invalidate session)"""
        try:
            # In a production app, you'd store invalidated tokens
            # For now, we rely on token expiration
            return True
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return False

# Global OAuth manager
oauth_manager = GoogleOAuthManager()
DEMO_BYPASS = os.getenv("DEMO_BYPASS", "false").lower() == "true"

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """Dependency to get current authenticated user"""
    
    if DEMO_BYPASS:
        return {
            "email": "demo@careassist.local",
            "name": "Demo User",
            "domain": "demo",
            "via_portal": False
        }
    
    # CHECK PORTAL AUTHENTICATION FIRST (highest priority)
    # When accessed through portal proxy, trust portal's authentication
    PORTAL_SECRET = os.getenv("PORTAL_SECRET", "colorado-careassist-portal-2025")
    portal_secret = request.headers.get("X-Portal-Secret")
    
    if portal_secret and portal_secret == PORTAL_SECRET:
        # Valid portal request - return user info from portal headers
        return {
            "email": request.headers.get("X-Portal-User-Email", "portal-user@coloradocareassist.com"),
            "name": request.headers.get("X-Portal-User-Name", "Portal User"),
            "domain": "coloradocareassist.com",
            "via_portal": True
        }
    
    # Check for session token in Authorization header
    if credentials and credentials.scheme == "Bearer":
        user_data = oauth_manager.verify_session(credentials.credentials)
        if user_data:
            return user_data
    
    # Check for session token in cookies (for web interface)
    session_token = request.cookies.get("session_token")
    if session_token:
        user_data = oauth_manager.verify_session(session_token)
        if user_data:
            return user_data
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """Optional dependency to get current user (returns None if not authenticated)"""
    
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None

def require_domain(allowed_domains: list) -> callable:
    """Decorator to require specific domain access"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            user = kwargs.get('current_user')
            if not user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            user_domain = user.get('domain', '')
            if user_domain not in allowed_domains:
                raise HTTPException(
                    status_code=403, 
                    detail=f"Access denied. Required domain: {', '.join(allowed_domains)}"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator

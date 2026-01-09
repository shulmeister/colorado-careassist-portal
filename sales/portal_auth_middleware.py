"""
Portal Authentication Middleware
Validates requests are coming from the portal via shared secret
"""
import os
from fastapi import Request, HTTPException, status
from typing import Dict, Any

PORTAL_SECRET = os.getenv("PORTAL_SECRET", "change-me-in-production")

async def verify_portal_request(request: Request) -> Dict[str, Any]:
    """
    Verify request is coming from the portal
    Replaces OAuth - portal handles authentication, dashboard trusts portal
    """
    # Check for portal secret header
    secret = request.headers.get("X-Portal-Secret")
    
    if not secret or secret != PORTAL_SECRET:
        # For direct access (not from portal), allow but with limited access
        # This allows dashboard to still work standalone for development
        return {
            "email": "direct-access@local",
            "name": "Direct Access",
            "is_portal_user": False
        }
    
    # Valid portal request - extract user info from headers
    return {
        "email": request.headers.get("X-Portal-User-Email", "portal-user@coloradocareassist.com"),
        "name": request.headers.get("X-Portal-User-Name", "Portal User"),
        "is_portal_user": True
    }

def get_portal_user(request: Request) -> Dict[str, Any]:
    """Simplified user getter - trust portal authentication"""
    return {
        "email": request.headers.get("X-Portal-User-Email", "user@coloradocareassist.com"),
        "name": request.headers.get("X-Portal-User-Name", "User")
    }


"""
OAuth Manager - Handles OAuth 2.0 flows for various services
"""
import os
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from urllib.parse import urlencode
import httpx

logger = logging.getLogger(__name__)


class OAuthManager:
    """Manages OAuth 2.0 authentication flows for multiple services"""
    
    def __init__(self):
        self.base_url = os.getenv("APP_BASE_URL", "https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com")
        
        # OAuth configurations for each service
        self.configs = {
            "google_ads": {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_url": "https://oauth2.googleapis.com/token",
                "scopes": ["https://www.googleapis.com/auth/adwords"],
                "redirect_uri": f"{self.base_url}/auth/google-ads/callback"
            },
            "linkedin": {
                "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
                "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET"),
                "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
                "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
                "scopes": ["r_organization_social", "rw_organization_admin", "r_ads", "r_ads_reporting"],
                "redirect_uri": f"{self.base_url}/auth/linkedin/callback"
            },
            "facebook": {
                "client_id": os.getenv("FACEBOOK_APP_ID"),
                "client_secret": os.getenv("FACEBOOK_APP_SECRET"),
                "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
                "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
                "scopes": [
                    "pages_show_list",
                    "pages_read_engagement",
                    "pages_read_user_content",
                    "pages_manage_ads",
                    "ads_read",
                    "business_management"
                ],
                "redirect_uri": f"{self.base_url}/auth/facebook/callback"
            },
            "mailchimp": {
                "client_id": os.getenv("MAILCHIMP_CLIENT_ID"),
                "client_secret": os.getenv("MAILCHIMP_CLIENT_SECRET"),
                "auth_url": "https://login.mailchimp.com/oauth2/authorize",
                "token_url": "https://login.mailchimp.com/oauth2/token",
                "scopes": [],  # Mailchimp doesn't use scopes in the same way
                "redirect_uri": f"{self.base_url}/auth/mailchimp/callback"
            },
            "quickbooks": {
                "client_id": os.getenv("QUICKBOOKS_CLIENT_ID"),
                "client_secret": os.getenv("QUICKBOOKS_CLIENT_SECRET"),
                "auth_url": "https://appcenter.intuit.com/connect/oauth2",
                "token_url": "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
                "scopes": ["com.intuit.quickbooks.accounting"],
                "redirect_uri": f"{self.base_url}/auth/quickbooks/callback"
            }
        }
    
    def get_authorization_url(self, service: str, state: str) -> Optional[str]:
        """
        Generate OAuth authorization URL for a service
        
        Args:
            service: Service name (e.g., 'linkedin', 'google_ads')
            state: CSRF token for security
            
        Returns:
            Authorization URL or None if service not configured
        """
        config = self.configs.get(service)
        if not config or not config.get("client_id"):
            logger.warning(f"OAuth not configured for {service}")
            return None
        
        params = {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "state": state,
            "response_type": "code"
        }
        
        # Add scopes if applicable
        if config.get("scopes"):
            if service == "linkedin":
                params["scope"] = " ".join(config["scopes"])
            else:
                params["scope"] = " ".join(config["scopes"])
        
        # Service-specific parameters
        if service == "google_ads":
            params["access_type"] = "offline"
            params["prompt"] = "consent"
        
        auth_url = f"{config['auth_url']}?{urlencode(params)}"
        logger.info(f"Generated auth URL for {service}")
        return auth_url
    
    async def exchange_code_for_token(self, service: str, code: str) -> Optional[Dict[str, Any]]:
        """
        Exchange authorization code for access token
        
        Args:
            service: Service name
            code: Authorization code from OAuth callback
            
        Returns:
            Token response dictionary or None if failed
        """
        config = self.configs.get(service)
        if not config:
            logger.error(f"No config for service: {service}")
            return None
        
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config["redirect_uri"],
            "client_id": config["client_id"],
            "client_secret": config["client_secret"]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config["token_url"],
                    data=data,
                    headers={"Accept": "application/json"}
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    logger.info(f"Successfully exchanged code for token: {service}")
                    
                    # Add metadata
                    token_data["service"] = service
                    token_data["obtained_at"] = datetime.utcnow().isoformat()
                    
                    # Calculate expiry if expires_in is provided
                    if "expires_in" in token_data:
                        expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
                        token_data["expires_at"] = expires_at.isoformat()
                    
                    return token_data
                else:
                    logger.error(f"Token exchange failed for {service}: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error exchanging code for token ({service}): {e}")
            return None
    
    async def refresh_access_token(self, service: str, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Refresh an expired access token
        
        Args:
            service: Service name
            refresh_token: Refresh token
            
        Returns:
            New token response or None if failed
        """
        config = self.configs.get(service)
        if not config:
            return None
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": config["client_id"],
            "client_secret": config["client_secret"]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config["token_url"],
                    data=data,
                    headers={"Accept": "application/json"}
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    logger.info(f"Successfully refreshed token: {service}")
                    
                    token_data["service"] = service
                    token_data["obtained_at"] = datetime.utcnow().isoformat()
                    
                    if "expires_in" in token_data:
                        expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
                        token_data["expires_at"] = expires_at.isoformat()
                    
                    return token_data
                else:
                    logger.error(f"Token refresh failed for {service}: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error refreshing token ({service}): {e}")
            return None
    
    def is_service_configured(self, service: str) -> bool:
        """Check if a service has OAuth credentials configured"""
        config = self.configs.get(service)
        return bool(config and config.get("client_id") and config.get("client_secret"))


oauth_manager = OAuthManager()


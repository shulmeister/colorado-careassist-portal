"""
LinkedIn API integration for marketing dashboard social metrics.

Fetches post analytics, engagement data, and company page metrics from LinkedIn API.
Requires OAuth 2.0 access token for authentication.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"
LINKEDIN_OAUTH_URL = "https://www.linkedin.com/oauth/v2"


class LinkedInService:
    """Service for fetching LinkedIn analytics and engagement metrics."""

    def __init__(self) -> None:
        self.client_id = os.getenv("LINKEDIN_CLIENT_ID")
        self.client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
        self.access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        self.organization_id = os.getenv("LINKEDIN_ORGANIZATION_ID")  # Company page ID
        
        self.session = requests.Session()
        if self.access_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
                "LinkedIn-Version": "202401",
            })
            logger.info("LinkedIn service initialized with access token")
        else:
            logger.warning("LinkedIn access token not configured - OAuth flow required")

    def _is_configured(self) -> bool:
        """Check if LinkedIn API is fully configured with access token."""
        return bool(self.access_token)

    def _has_credentials(self) -> bool:
        """Check if OAuth credentials are available (for initiating OAuth flow)."""
        return bool(self.client_id and self.client_secret)

    def get_oauth_url(self, redirect_uri: str, state: str = "linkedin_auth") -> str:
        """
        Generate the OAuth authorization URL for LinkedIn.
        
        User must visit this URL to authorize the app and get an auth code.
        """
        scopes = "openid profile email w_member_social r_organization_social rw_organization_admin"
        return (
            f"{LINKEDIN_OAUTH_URL}/authorization?"
            f"response_type=code&"
            f"client_id={self.client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"state={state}&"
            f"scope={scopes}"
        )

    def exchange_code_for_token(self, code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
        """
        Exchange an authorization code for an access token.
        
        Returns token info including access_token and expires_in.
        """
        if not self._has_credentials():
            logger.error("LinkedIn credentials not configured")
            return None
        
        try:
            response = requests.post(
                f"{LINKEDIN_OAUTH_URL}/accessToken",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            logger.error(f"Error exchanging LinkedIn code for token: {e}")
            return None

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Make a request to the LinkedIn API."""
        if not self._is_configured():
            return None
            
        url = f"{LINKEDIN_API_BASE}{path}"
        try:
            response = self.session.request(method, url, params=params, timeout=30)
            
            if response.status_code >= 400:
                logger.error(f"LinkedIn API error {response.status_code}: {response.text}")
                return None
                
            return response.json()
        except requests.RequestException as e:
            logger.error(f"LinkedIn API request error: {e}")
            return None

    def get_profile(self) -> Optional[Dict[str, Any]]:
        """Get the authenticated user's LinkedIn profile."""
        if not self._is_configured():
            return None
        
        try:
            response = self.session.get(
                f"{LINKEDIN_API_BASE}/userinfo",
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            logger.error(f"Error fetching LinkedIn profile: {e}")
            return None

    def get_organization_info(self) -> Optional[Dict[str, Any]]:
        """Get organization/company page information."""
        if not self._is_configured() or not self.organization_id:
            return None
        
        return self._request("GET", f"/organizations/{self.organization_id}")

    def get_organization_followers(self) -> int:
        """Get the follower count for the organization."""
        if not self._is_configured() or not self.organization_id:
            return 0
        
        result = self._request(
            "GET", 
            f"/organizationalEntityFollowerStatistics",
            params={"q": "organizationalEntity", "organizationalEntity": f"urn:li:organization:{self.organization_id}"}
        )
        
        if result and "elements" in result and len(result["elements"]) > 0:
            return result["elements"][0].get("followerCounts", {}).get("organicFollowerCount", 0)
        return 0

    def get_share_statistics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Get share/post statistics for the organization.
        
        Returns impressions, clicks, engagement metrics.
        """
        if not self._is_configured() or not self.organization_id:
            return {}
        
        # Convert dates to milliseconds timestamp
        start_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
        end_ts = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)
        
        result = self._request(
            "GET",
            "/organizationalEntityShareStatistics",
            params={
                "q": "organizationalEntity",
                "organizationalEntity": f"urn:li:organization:{self.organization_id}",
                "timeIntervals.timeGranularityType": "DAY",
                "timeIntervals.timeRange.start": start_ts,
                "timeIntervals.timeRange.end": end_ts,
            }
        )
        
        if not result or "elements" not in result:
            return {}
        
        # Aggregate statistics
        total_impressions = 0
        total_clicks = 0
        total_likes = 0
        total_comments = 0
        total_shares = 0
        total_engagement = 0
        
        for element in result.get("elements", []):
            stats = element.get("totalShareStatistics", {})
            total_impressions += stats.get("impressionCount", 0) or 0
            total_clicks += stats.get("clickCount", 0) or 0
            total_likes += stats.get("likeCount", 0) or 0
            total_comments += stats.get("commentCount", 0) or 0
            total_shares += stats.get("shareCount", 0) or 0
            total_engagement += stats.get("engagement", 0) or 0
        
        return {
            "impressions": total_impressions,
            "clicks": total_clicks,
            "likes": total_likes,
            "comments": total_comments,
            "shares": total_shares,
            "engagement": total_engagement,
            "engagement_rate": round((total_engagement / total_impressions * 100) if total_impressions > 0 else 0, 2),
        }

    def get_posts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent posts from the organization page."""
        if not self._is_configured() or not self.organization_id:
            return []
        
        result = self._request(
            "GET",
            "/shares",
            params={
                "q": "owners",
                "owners": f"urn:li:organization:{self.organization_id}",
                "count": limit,
            }
        )
        
        if not result or "elements" not in result:
            return []
        
        posts = []
        for element in result.get("elements", []):
            content = element.get("content", {}) or {}
            text_content = element.get("text", {}) or {}
            
            posts.append({
                "id": element.get("id"),
                "text": text_content.get("text", "")[:100] if text_content.get("text") else "No text",
                "created_at": element.get("created", {}).get("time"),
                "visibility": element.get("distribution", {}).get("linkedInDistributionTarget", {}).get("visibleToGuest", False),
            })
        
        return posts

    def get_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch all LinkedIn metrics for the Marketing Dashboard.
        
        Returns data in a format compatible with the social metrics display.
        """
        if not self._is_configured():
            logger.info("LinkedIn not configured - returning placeholder")
            return self._get_placeholder_metrics(start_date, end_date)

        try:
            # Get profile info
            profile = self.get_profile() or {}
            name = profile.get("name", "Unknown")
            
            logger.info(f"LinkedIn profile: {name}")
            
            # Get organization stats if available
            followers = 0
            share_stats = {}
            posts = []
            
            if self.organization_id:
                followers = self.get_organization_followers()
                share_stats = self.get_share_statistics(start_date, end_date)
                posts = self.get_posts(limit=10)
            
            return {
                "account": {
                    "name": name,
                    "email": profile.get("email"),
                    "followers": followers,
                    "has_organization": bool(self.organization_id),
                },
                "summary": {
                    "impressions": share_stats.get("impressions", 0),
                    "clicks": share_stats.get("clicks", 0),
                    "likes": share_stats.get("likes", 0),
                    "comments": share_stats.get("comments", 0),
                    "shares": share_stats.get("shares", 0),
                    "engagement": share_stats.get("engagement", 0),
                    "engagement_rate": share_stats.get("engagement_rate", 0),
                },
                "posts": [
                    {
                        "id": post.get("id"),
                        "text": post.get("text"),
                        "created_at": post.get("created_at"),
                    }
                    for post in posts[:5]
                ],
                "is_placeholder": False,
                "source": "linkedin_api",
                "fetched_at": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error fetching LinkedIn metrics: {e}")
            return self._get_placeholder_metrics(start_date, end_date)

    def _get_placeholder_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return placeholder metrics when LinkedIn is not configured."""
        needs_oauth = self._has_credentials() and not self._is_configured()
        
        return {
            "account": {
                "name": "Not connected",
                "email": None,
                "followers": 0,
                "has_organization": False,
            },
            "summary": {
                "impressions": 0,
                "clicks": 0,
                "likes": 0,
                "comments": 0,
                "shares": 0,
                "engagement": 0,
                "engagement_rate": 0,
            },
            "posts": [],
            "is_placeholder": True,
            "source": "placeholder",
            "needs_oauth": needs_oauth,
            "oauth_url": self.get_oauth_url("https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/api/linkedin/callback") if needs_oauth else None,
            "fetched_at": datetime.utcnow().isoformat(),
        }


# Singleton instance
linkedin_service = LinkedInService()


"""
Pinterest API integration for marketing dashboard social metrics.

Fetches pin analytics, board metrics, and engagement data from Pinterest API v5.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

PINTEREST_API_BASE = "https://api.pinterest.com/v5"


class PinterestService:
    """Service for fetching Pinterest analytics and engagement metrics."""

    def __init__(self) -> None:
        self.access_token = os.getenv("PINTEREST_ACCESS_TOKEN")
        self.app_id = os.getenv("PINTEREST_APP_ID")
        self.session = requests.Session()
        
        if self.access_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            })
            logger.info("Pinterest service initialized successfully")
        else:
            logger.warning("Pinterest access token not configured")

    def _is_configured(self) -> bool:
        return bool(self.access_token)

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a request to the Pinterest API."""
        url = f"{PINTEREST_API_BASE}{path}"
        response = self.session.request(method, url, params=params, timeout=30)
        
        if response.status_code >= 400:
            logger.error(f"Pinterest API error {response.status_code}: {response.text}")
            raise requests.HTTPError(
                f"Pinterest API error {response.status_code}: {response.text}",
                response=response,
            )
        return response.json()

    def get_user_account(self) -> Dict[str, Any]:
        """Get the authenticated user's account info."""
        if not self._is_configured():
            return {}
        
        try:
            return self._request("GET", "/user_account")
        except requests.HTTPError as e:
            logger.error(f"Error fetching Pinterest user account: {e}")
            return {}

    def get_pins(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get the user's pins."""
        if not self._is_configured():
            return []
        
        try:
            params = {"page_size": min(limit, 100)}
            response = self._request("GET", "/pins", params)
            return response.get("items", [])
        except requests.HTTPError as e:
            logger.error(f"Error fetching Pinterest pins: {e}")
            return []

    def get_boards(self) -> List[Dict[str, Any]]:
        """Get the user's boards."""
        if not self._is_configured():
            return []
        
        try:
            response = self._request("GET", "/boards")
            return response.get("items", [])
        except requests.HTTPError as e:
            logger.error(f"Error fetching Pinterest boards: {e}")
            return []

    def get_pin_analytics(self, pin_id: str, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get analytics for a specific pin."""
        if not self._is_configured():
            return {}
        
        try:
            params = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "metric_types": "IMPRESSION,SAVE,PIN_CLICK,OUTBOUND_CLICK",
            }
            return self._request("GET", f"/pins/{pin_id}/analytics", params)
        except requests.HTTPError as e:
            logger.error(f"Error fetching Pinterest pin analytics for {pin_id}: {e}")
            return {}

    def get_user_analytics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Get overall user account analytics.
        
        Note: This requires a business account with analytics access.
        """
        if not self._is_configured():
            return {}
        
        try:
            params = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "metric_types": "IMPRESSION,ENGAGEMENT,PIN_CLICK,OUTBOUND_CLICK,SAVE",
                "from_claimed_content": "BOTH",
                "pin_format": "ALL",
                "app_types": "ALL",
                "content_type": "ALL",
                "source": "ALL",
            }
            return self._request("GET", "/user_account/analytics", params)
        except requests.HTTPError as e:
            logger.error(f"Error fetching Pinterest user analytics: {e}")
            return {}

    def get_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch all Pinterest metrics for the Marketing Dashboard.
        
        Returns data in a format compatible with the social metrics display.
        """
        if not self._is_configured():
            logger.info("Pinterest not configured - returning placeholder")
            return self._get_placeholder_metrics(start_date, end_date)

        try:
            # Get user account info
            user = self.get_user_account() or {}
            username = user.get("username", "unknown")
            followers = user.get("follower_count", 0)
            following = user.get("following_count", 0)
            
            logger.info(f"Pinterest user: {username}, followers: {followers}")
            
            # Get boards
            boards = self.get_boards() or []
            
            # Get pins
            pins = self.get_pins(limit=50) or []
            
            # Try to get user analytics (requires business account)
            analytics = self.get_user_analytics(start_date, end_date) or {}
            
            # Process analytics data
            total_impressions = 0
            total_engagements = 0
            total_saves = 0
            total_clicks = 0
            total_outbound_clicks = 0
            
            # Pinterest analytics returns daily data (if available)
            all_data = analytics.get("all", {}) if analytics else {}
            daily_metrics = all_data.get("daily_metrics", []) if all_data else []
            
            for day in daily_metrics:
                metrics = day.get("data_status") == "READY"
                if metrics:
                    total_impressions += day.get("metrics", {}).get("IMPRESSION", 0)
                    total_engagements += day.get("metrics", {}).get("ENGAGEMENT", 0)
                    total_saves += day.get("metrics", {}).get("SAVE", 0)
                    total_clicks += day.get("metrics", {}).get("PIN_CLICK", 0)
                    total_outbound_clicks += day.get("metrics", {}).get("OUTBOUND_CLICK", 0)
            
            # If no analytics available, estimate from pins
            if total_impressions == 0 and pins:
                # Sum up pin-level stats if available
                for pin in pins:
                    pin_stats = pin.get("pin_metrics", {})
                    total_impressions += pin_stats.get("lifetime", {}).get("impression", 0)
                    total_saves += pin_stats.get("lifetime", {}).get("save", 0)
                    total_clicks += pin_stats.get("lifetime", {}).get("pin_click", 0)
                    total_outbound_clicks += pin_stats.get("lifetime", {}).get("outbound_click", 0)
            
            # Build top pins list
            top_pins = []
            for pin in pins[:10]:
                pin_metrics = pin.get("pin_metrics", {}).get("lifetime", {})
                top_pins.append({
                    "id": pin.get("id"),
                    "title": pin.get("title") or pin.get("description", "")[:50] or "Untitled Pin",
                    "impressions": pin_metrics.get("impression", 0),
                    "saves": pin_metrics.get("save", 0),
                    "clicks": pin_metrics.get("pin_click", 0),
                    "outbound_clicks": pin_metrics.get("outbound_click", 0),
                    "link": pin.get("link"),
                    "created_at": pin.get("created_at"),
                })
            
            # Sort by impressions
            top_pins.sort(key=lambda x: x.get("impressions", 0), reverse=True)
            
            return {
                "account": {
                    "username": username,
                    "followers": followers,
                    "following": following,
                    "board_count": len(boards),
                    "pin_count": len(pins),
                },
                "summary": {
                    "impressions": total_impressions,
                    "engagements": total_engagements,
                    "saves": total_saves,
                    "pin_clicks": total_clicks,
                    "outbound_clicks": total_outbound_clicks,
                    "engagement_rate": round((total_engagements / total_impressions * 100) if total_impressions > 0 else 0, 2),
                },
                "top_pins": top_pins[:5],
                "boards": [
                    {
                        "id": board.get("id"),
                        "name": board.get("name"),
                        "pin_count": board.get("pin_count", 0),
                    }
                    for board in boards[:10]
                ],
                "is_placeholder": False,
                "source": "pinterest_api",
                "fetched_at": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error fetching Pinterest metrics: {e}")
            return self._get_placeholder_metrics(start_date, end_date)

    def _get_placeholder_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return placeholder metrics when Pinterest is not configured."""
        return {
            "account": {
                "username": "not_configured",
                "followers": 0,
                "following": 0,
                "board_count": 0,
                "pin_count": 0,
            },
            "summary": {
                "impressions": 0,
                "engagements": 0,
                "saves": 0,
                "pin_clicks": 0,
                "outbound_clicks": 0,
                "engagement_rate": 0,
            },
            "top_pins": [],
            "boards": [],
            "is_placeholder": True,
            "source": "placeholder",
            "fetched_at": datetime.utcnow().isoformat(),
        }


# Singleton instance
pinterest_service = PinterestService()


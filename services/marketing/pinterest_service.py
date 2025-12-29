"""
Pinterest API integration for fetching pins, boards, and engagement metrics.
Supports both organic pins and Pinterest Ads (if configured).
"""
from __future__ import annotations

import os
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)

PINTEREST_ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN")
PINTEREST_AD_ACCOUNT_ID = os.getenv("PINTEREST_AD_ACCOUNT_ID")
PINTEREST_API_BASE = "https://api.pinterest.com/v5"


class PinterestService:
    """Service for fetching Pinterest metrics via API"""
    
    def __init__(self, access_token: str = None):
        self.access_token = access_token or PINTEREST_ACCESS_TOKEN
        self.ad_account_id = PINTEREST_AD_ACCOUNT_ID
        
        if not self.access_token:
            logger.warning("Pinterest access token not configured")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Pinterest API requests"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    def get_user_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch user account metrics including pins, followers, engagement.
        
        Args:
            start_date: Start date for metrics
            end_date: End date for metrics
        
        Returns:
            Dictionary containing user/account metrics
        """
        if not self.access_token:
            logger.info("Pinterest access token not configured - using placeholder data")
            return self._get_placeholder_metrics(start_date, end_date)
        
        try:
            metrics = {}
            
            # Get user account info
            user_url = f"{PINTEREST_API_BASE}/user_account"
            user_response = requests.get(user_url, headers=self._get_headers(), timeout=30)
            
            if user_response.status_code == 200:
                user_data = user_response.json()
                metrics["username"] = user_data.get("username", "Unknown")
                metrics["account_type"] = user_data.get("account_type", "Unknown")
                metrics["profile_image"] = user_data.get("profile_image", "")
            else:
                logger.warning(f"Pinterest user request failed: {user_response.status_code}")
            
            # Get user analytics
            analytics_url = f"{PINTEREST_API_BASE}/user_account/analytics"
            params = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "metric_types": "IMPRESSION,PIN_CLICK,OUTBOUND_CLICK,SAVE,ENGAGEMENT",
            }
            analytics_response = requests.get(analytics_url, headers=self._get_headers(), params=params, timeout=30)
            
            if analytics_response.status_code == 200:
                analytics_data = analytics_response.json()
                
                # Sum up daily metrics
                daily_metrics = analytics_data.get("all", {}).get("daily_metrics", [])
                
                total_impressions = 0
                total_pin_clicks = 0
                total_outbound_clicks = 0
                total_saves = 0
                total_engagement = 0
                
                for day in daily_metrics:
                    total_impressions += day.get("IMPRESSION", 0)
                    total_pin_clicks += day.get("PIN_CLICK", 0)
                    total_outbound_clicks += day.get("OUTBOUND_CLICK", 0)
                    total_saves += day.get("SAVE", 0)
                    total_engagement += day.get("ENGAGEMENT", 0)
                
                metrics["impressions"] = total_impressions
                metrics["pin_clicks"] = total_pin_clicks
                metrics["outbound_clicks"] = total_outbound_clicks
                metrics["saves"] = total_saves
                metrics["engagement"] = total_engagement
                metrics["engagement_rate"] = round((total_engagement / max(total_impressions, 1)) * 100, 2)
            
            # Get top pins
            pins_url = f"{PINTEREST_API_BASE}/pins"
            pins_params = {"page_size": 10}
            pins_response = requests.get(pins_url, headers=self._get_headers(), params=pins_params, timeout=30)
            
            if pins_response.status_code == 200:
                pins_data = pins_response.json()
                top_pins = []
                for pin in pins_data.get("items", [])[:5]:
                    top_pins.append({
                        "id": pin.get("id"),
                        "title": pin.get("title", "Untitled Pin"),
                        "description": pin.get("description", "")[:100],
                        "link": pin.get("link", ""),
                    })
                metrics["top_pins"] = top_pins
            
            # If we got data, return it
            if metrics.get("impressions") is not None:
                metrics["is_placeholder"] = False
                metrics["source"] = "pinterest_api"
                metrics["fetched_at"] = datetime.utcnow().isoformat()
                return metrics
            
            return self._get_placeholder_metrics(start_date, end_date)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Pinterest metrics: {e}")
            return self._get_placeholder_metrics(start_date, end_date)
        except Exception as e:
            logger.error(f"Unexpected error fetching Pinterest metrics: {e}")
            return self._get_placeholder_metrics(start_date, end_date)
    
    def get_ad_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch Pinterest Ads metrics (if ad account is configured).
        
        Args:
            start_date: Start date for metrics
            end_date: End date for metrics
        
        Returns:
            Dictionary containing ad metrics
        """
        if not self.access_token or not self.ad_account_id:
            logger.info("Pinterest Ads not configured - using placeholder data")
            return self._get_placeholder_ad_metrics(start_date, end_date)
        
        try:
            # Pinterest Ads analytics endpoint
            analytics_url = f"{PINTEREST_API_BASE}/ad_accounts/{self.ad_account_id}/analytics"
            params = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "granularity": "TOTAL",
                "columns": "SPEND_IN_DOLLAR,IMPRESSION,PIN_CLICK,OUTBOUND_CLICK,TOTAL_CONVERSIONS,TOTAL_CONVERSION_VALUE",
            }
            
            response = requests.get(analytics_url, headers=self._get_headers(), params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Aggregate metrics
                total_spend = 0
                total_impressions = 0
                total_clicks = 0
                total_outbound_clicks = 0
                total_conversions = 0
                total_conversion_value = 0
                
                for row in data:
                    total_spend += float(row.get("SPEND_IN_DOLLAR", 0))
                    total_impressions += row.get("IMPRESSION", 0)
                    total_clicks += row.get("PIN_CLICK", 0)
                    total_outbound_clicks += row.get("OUTBOUND_CLICK", 0)
                    total_conversions += row.get("TOTAL_CONVERSIONS", 0)
                    total_conversion_value += float(row.get("TOTAL_CONVERSION_VALUE", 0))
                
                return {
                    "spend": round(total_spend, 2),
                    "impressions": total_impressions,
                    "pin_clicks": total_clicks,
                    "outbound_clicks": total_outbound_clicks,
                    "conversions": total_conversions,
                    "conversion_value": round(total_conversion_value, 2),
                    "cpc": round(total_spend / max(total_clicks, 1), 2),
                    "ctr": round((total_clicks / max(total_impressions, 1)) * 100, 2),
                    "roas": round(total_conversion_value / max(total_spend, 1), 2),
                    "is_placeholder": False,
                    "source": "pinterest_ads_api",
                    "fetched_at": datetime.utcnow().isoformat()
                }
            
            return self._get_placeholder_ad_metrics(start_date, end_date)
            
        except Exception as e:
            logger.error(f"Error fetching Pinterest Ads metrics: {e}")
            return self._get_placeholder_ad_metrics(start_date, end_date)
    
    def _get_placeholder_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return placeholder user/organic metrics"""
        days = (end_date - start_date).days + 1
        
        return {
            "username": "coloradocareassist",
            "account_type": "BUSINESS",
            "followers": 892,
            "following": 156,
            "monthly_views": int(days * 180),
            "impressions": int(days * 520),
            "pin_clicks": int(days * 45),
            "outbound_clicks": int(days * 18),
            "saves": int(days * 32),
            "engagement": int(days * 95),
            "engagement_rate": 4.2,
            "top_pins": [
                {"title": "Caregiver Tips Infographic", "saves": 156, "clicks": 89},
                {"title": "Home Care Checklist", "saves": 124, "clicks": 67},
                {"title": "Senior Safety Guide", "saves": 98, "clicks": 52},
            ],
            "is_placeholder": True,
            "source": "placeholder",
            "fetched_at": datetime.utcnow().isoformat()
        }
    
    def _get_placeholder_ad_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return placeholder ad metrics (Pinterest Ads not configured)"""
        return {
            "configured": False,
            "message": "Pinterest Ads account not configured",
            "spend": 0,
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "is_placeholder": True,
            "source": "placeholder",
            "fetched_at": datetime.utcnow().isoformat()
        }


# Singleton instance
pinterest_service = PinterestService()


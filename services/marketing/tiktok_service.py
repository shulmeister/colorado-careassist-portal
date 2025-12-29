"""
TikTok Marketing API integration for fetching ads and engagement metrics.
Supports TikTok Business Center and TikTok Ads Manager.
"""
from __future__ import annotations

import os
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)

TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN")
TIKTOK_ADVERTISER_ID = os.getenv("TIKTOK_ADVERTISER_ID")
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
TIKTOK_API_BASE = "https://business-api.tiktok.com/open_api/v1.3"


class TikTokService:
    """Service for fetching TikTok ads and engagement metrics"""
    
    def __init__(self, access_token: str = None):
        self.access_token = access_token or TIKTOK_ACCESS_TOKEN
        self.advertiser_id = TIKTOK_ADVERTISER_ID
        self.client_key = TIKTOK_CLIENT_KEY
        self.client_secret = TIKTOK_CLIENT_SECRET
        
        if not self.access_token and not (self.client_key and self.client_secret):
            logger.warning("TikTok credentials not fully configured")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for TikTok API requests"""
        return {
            "Access-Token": self.access_token or "",
            "Content-Type": "application/json",
        }
    
    def is_configured(self) -> bool:
        """Check if TikTok API is properly configured"""
        return bool(self.access_token and self.advertiser_id)
    
    def get_ad_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch TikTok Ads metrics for the specified date range.
        
        Args:
            start_date: Start date for metrics
            end_date: End date for metrics
        
        Returns:
            Dictionary containing ad metrics
        """
        if not self.is_configured():
            logger.info("TikTok Ads not configured - using placeholder data")
            return self._get_placeholder_metrics(start_date, end_date)
        
        try:
            # TikTok Ads reporting endpoint
            report_url = f"{TIKTOK_API_BASE}/report/integrated/get/"
            
            payload = {
                "advertiser_id": self.advertiser_id,
                "report_type": "BASIC",
                "dimensions": ["advertiser_id"],
                "data_level": "AUCTION_ADVERTISER",
                "metrics": [
                    "spend", "impressions", "clicks", "ctr", "cpc",
                    "conversion", "cost_per_conversion", "conversion_rate"
                ],
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
            
            response = requests.post(
                report_url, 
                headers=self._get_headers(), 
                json=payload, 
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("code") == 0:  # Success
                    report_data = data.get("data", {}).get("list", [])
                    
                    if report_data:
                        metrics = report_data[0].get("metrics", {})
                        
                        return {
                            "spend": float(metrics.get("spend", 0)),
                            "impressions": int(metrics.get("impressions", 0)),
                            "clicks": int(metrics.get("clicks", 0)),
                            "ctr": float(metrics.get("ctr", 0)),
                            "cpc": float(metrics.get("cpc", 0)),
                            "conversions": int(metrics.get("conversion", 0)),
                            "cost_per_conversion": float(metrics.get("cost_per_conversion", 0)),
                            "conversion_rate": float(metrics.get("conversion_rate", 0)),
                            "is_placeholder": False,
                            "source": "tiktok_ads_api",
                            "fetched_at": datetime.utcnow().isoformat()
                        }
                else:
                    logger.warning(f"TikTok API error: {data.get('message')}")
            
            return self._get_placeholder_metrics(start_date, end_date)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching TikTok metrics: {e}")
            return self._get_placeholder_metrics(start_date, end_date)
        except Exception as e:
            logger.error(f"Unexpected error fetching TikTok metrics: {e}")
            return self._get_placeholder_metrics(start_date, end_date)
    
    def get_campaign_metrics(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Fetch metrics broken down by campaign.
        
        Args:
            start_date: Start date for metrics
            end_date: End date for metrics
        
        Returns:
            List of campaign metrics
        """
        if not self.is_configured():
            return self._get_placeholder_campaigns(start_date, end_date)
        
        try:
            report_url = f"{TIKTOK_API_BASE}/report/integrated/get/"
            
            payload = {
                "advertiser_id": self.advertiser_id,
                "report_type": "BASIC",
                "dimensions": ["campaign_id"],
                "data_level": "AUCTION_CAMPAIGN",
                "metrics": [
                    "campaign_name", "spend", "impressions", "clicks", 
                    "ctr", "cpc", "conversion", "cost_per_conversion"
                ],
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "page_size": 20,
            }
            
            response = requests.post(
                report_url, 
                headers=self._get_headers(), 
                json=payload, 
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("code") == 0:
                    campaigns = []
                    for row in data.get("data", {}).get("list", []):
                        dimensions = row.get("dimensions", {})
                        metrics = row.get("metrics", {})
                        
                        campaigns.append({
                            "campaign_id": dimensions.get("campaign_id"),
                            "campaign_name": metrics.get("campaign_name", "Unknown"),
                            "spend": float(metrics.get("spend", 0)),
                            "impressions": int(metrics.get("impressions", 0)),
                            "clicks": int(metrics.get("clicks", 0)),
                            "ctr": float(metrics.get("ctr", 0)),
                            "cpc": float(metrics.get("cpc", 0)),
                            "conversions": int(metrics.get("conversion", 0)),
                            "cost_per_conversion": float(metrics.get("cost_per_conversion", 0)),
                        })
                    
                    return campaigns
            
            return self._get_placeholder_campaigns(start_date, end_date)
            
        except Exception as e:
            logger.error(f"Error fetching TikTok campaign metrics: {e}")
            return self._get_placeholder_campaigns(start_date, end_date)
    
    def get_engagement_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch organic engagement metrics (if available via TikTok Business API).
        Note: TikTok organic metrics require different API access.
        
        Args:
            start_date: Start date for metrics
            end_date: End date for metrics
        
        Returns:
            Dictionary containing engagement metrics
        """
        # TikTok organic metrics require separate Creator/Business API access
        # For now, return placeholder data
        return self._get_placeholder_engagement(start_date, end_date)
    
    def _get_placeholder_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return placeholder ad metrics"""
        days = (end_date - start_date).days + 1
        
        # Note: TikTok may not be actively used for this business
        return {
            "spend": 0.0,
            "impressions": 0,
            "clicks": 0,
            "ctr": 0.0,
            "cpc": 0.0,
            "conversions": 0,
            "cost_per_conversion": 0.0,
            "conversion_rate": 0.0,
            "note": "TikTok Ads not currently active. Configure TIKTOK_ACCESS_TOKEN and TIKTOK_ADVERTISER_ID to enable.",
            "is_placeholder": True,
            "source": "placeholder",
            "fetched_at": datetime.utcnow().isoformat()
        }
    
    def _get_placeholder_campaigns(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Return placeholder campaign data"""
        return []
    
    def _get_placeholder_engagement(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return placeholder organic engagement metrics"""
        return {
            "followers": 0,
            "profile_views": 0,
            "video_views": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "note": "TikTok organic metrics require separate Creator API access.",
            "is_placeholder": True,
            "source": "placeholder",
            "fetched_at": datetime.utcnow().isoformat()
        }


# Singleton instance
tiktok_service = TikTokService()

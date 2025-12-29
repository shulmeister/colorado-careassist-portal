"""
LinkedIn Marketing API integration for fetching company page and advertising metrics.
Supports organic posts/engagement and LinkedIn Ads (if configured).
"""
from __future__ import annotations

import os
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)

LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN")
LINKEDIN_ORGANIZATION_ID = os.getenv("LINKEDIN_ORGANIZATION_ID")  # Company page ID
LINKEDIN_AD_ACCOUNT_ID = os.getenv("LINKEDIN_AD_ACCOUNT_ID")  # For LinkedIn Ads
LINKEDIN_API_VERSION = "202312"  # LinkedIn API version
LINKEDIN_API_BASE = "https://api.linkedin.com/v2"
LINKEDIN_REST_BASE = "https://api.linkedin.com/rest"


class LinkedInService:
    """Service for fetching LinkedIn company page and ads metrics"""
    
    def __init__(self, access_token: str = None):
        self.access_token = access_token or LINKEDIN_ACCESS_TOKEN
        self.organization_id = LINKEDIN_ORGANIZATION_ID
        self.ad_account_id = LINKEDIN_AD_ACCOUNT_ID
        
        if not self.access_token:
            logger.warning("LinkedIn access token not configured")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for LinkedIn API requests"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": LINKEDIN_API_VERSION,
        }
    
    def get_organization_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch organization (company page) metrics including followers, engagement.
        
        Args:
            start_date: Start date for metrics
            end_date: End date for metrics
        
        Returns:
            Dictionary containing organization metrics
        """
        if not self.access_token:
            logger.info("LinkedIn access token not configured - using placeholder data")
            return self._get_placeholder_metrics(start_date, end_date)
        
        try:
            metrics = {}
            
            # Get organization info (followers count)
            if self.organization_id:
                org_url = f"{LINKEDIN_API_BASE}/organizations/{self.organization_id}"
                response = requests.get(org_url, headers=self._get_headers(), timeout=30)
                
                if response.status_code == 200:
                    org_data = response.json()
                    metrics["organization_name"] = org_data.get("localizedName", "Unknown")
                else:
                    logger.warning(f"LinkedIn org request failed: {response.status_code}")
            
            # Get follower statistics
            if self.organization_id:
                stats_url = f"{LINKEDIN_API_BASE}/organizationalEntityFollowerStatistics"
                params = {
                    "q": "organizationalEntity",
                    "organizationalEntity": f"urn:li:organization:{self.organization_id}"
                }
                stats_response = requests.get(stats_url, headers=self._get_headers(), params=params, timeout=30)
                
                if stats_response.status_code == 200:
                    stats_data = stats_response.json()
                    elements = stats_data.get("elements", [])
                    if elements:
                        follower_data = elements[0]
                        metrics["total_followers"] = follower_data.get("followerCounts", {}).get("organicFollowerCount", 0)
                        metrics["total_followers"] += follower_data.get("followerCounts", {}).get("paidFollowerCount", 0)
            
            # Get share statistics (posts/engagement)
            if self.organization_id:
                share_url = f"{LINKEDIN_API_BASE}/organizationalEntityShareStatistics"
                params = {
                    "q": "organizationalEntity",
                    "organizationalEntity": f"urn:li:organization:{self.organization_id}",
                    "timeIntervals.timeGranularityType": "DAY",
                    "timeIntervals.timeRange.start": int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000),
                    "timeIntervals.timeRange.end": int(datetime.combine(end_date, datetime.min.time()).timestamp() * 1000),
                }
                share_response = requests.get(share_url, headers=self._get_headers(), params=params, timeout=30)
                
                if share_response.status_code == 200:
                    share_data = share_response.json()
                    elements = share_data.get("elements", [])
                    
                    total_impressions = 0
                    total_clicks = 0
                    total_likes = 0
                    total_comments = 0
                    total_shares = 0
                    total_engagement = 0
                    
                    for element in elements:
                        stats = element.get("totalShareStatistics", {})
                        total_impressions += stats.get("impressionCount", 0)
                        total_clicks += stats.get("clickCount", 0)
                        total_likes += stats.get("likeCount", 0)
                        total_comments += stats.get("commentCount", 0)
                        total_shares += stats.get("shareCount", 0)
                        total_engagement += stats.get("engagement", 0)
                    
                    metrics["impressions"] = total_impressions
                    metrics["clicks"] = total_clicks
                    metrics["likes"] = total_likes
                    metrics["comments"] = total_comments
                    metrics["shares"] = total_shares
                    metrics["engagement"] = total_engagement
                    metrics["engagement_rate"] = round((total_engagement / max(total_impressions, 1)) * 100, 2)
            
            # If we got data, return it; otherwise fallback to placeholder
            if metrics.get("total_followers") or metrics.get("impressions"):
                metrics["is_placeholder"] = False
                metrics["source"] = "linkedin_api"
                metrics["fetched_at"] = datetime.utcnow().isoformat()
                return metrics
            
            return self._get_placeholder_metrics(start_date, end_date)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching LinkedIn metrics: {e}")
            return self._get_placeholder_metrics(start_date, end_date)
        except Exception as e:
            logger.error(f"Unexpected error fetching LinkedIn metrics: {e}")
            return self._get_placeholder_metrics(start_date, end_date)
    
    def get_ad_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch LinkedIn Ads metrics (if ad account is configured).
        
        Args:
            start_date: Start date for metrics
            end_date: End date for metrics
        
        Returns:
            Dictionary containing ad metrics
        """
        if not self.access_token or not self.ad_account_id:
            logger.info("LinkedIn Ads not configured - using placeholder data")
            return self._get_placeholder_ad_metrics(start_date, end_date)
        
        try:
            # LinkedIn Ads API endpoint
            analytics_url = f"{LINKEDIN_REST_BASE}/adAnalytics"
            params = {
                "q": "analytics",
                "pivot": "CAMPAIGN",
                "dateRange.start.day": start_date.day,
                "dateRange.start.month": start_date.month,
                "dateRange.start.year": start_date.year,
                "dateRange.end.day": end_date.day,
                "dateRange.end.month": end_date.month,
                "dateRange.end.year": end_date.year,
                "timeGranularity": "ALL",
                "accounts": f"urn:li:sponsoredAccount:{self.ad_account_id}",
                "fields": "impressions,clicks,costInLocalCurrency,conversionValueInLocalCurrency,conversions",
            }
            
            response = requests.get(analytics_url, headers=self._get_headers(), params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                elements = data.get("elements", [])
                
                total_spend = 0
                total_impressions = 0
                total_clicks = 0
                total_conversions = 0
                total_conversion_value = 0
                
                for element in elements:
                    total_spend += float(element.get("costInLocalCurrency", 0))
                    total_impressions += element.get("impressions", 0)
                    total_clicks += element.get("clicks", 0)
                    total_conversions += element.get("conversions", 0)
                    total_conversion_value += float(element.get("conversionValueInLocalCurrency", 0))
                
                return {
                    "spend": round(total_spend, 2),
                    "impressions": total_impressions,
                    "clicks": total_clicks,
                    "conversions": total_conversions,
                    "conversion_value": round(total_conversion_value, 2),
                    "cpc": round(total_spend / max(total_clicks, 1), 2),
                    "ctr": round((total_clicks / max(total_impressions, 1)) * 100, 2),
                    "roas": round(total_conversion_value / max(total_spend, 1), 2),
                    "is_placeholder": False,
                    "source": "linkedin_ads_api",
                    "fetched_at": datetime.utcnow().isoformat()
                }
            
            return self._get_placeholder_ad_metrics(start_date, end_date)
            
        except Exception as e:
            logger.error(f"Error fetching LinkedIn Ads metrics: {e}")
            return self._get_placeholder_ad_metrics(start_date, end_date)
    
    def _get_placeholder_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return placeholder organization metrics"""
        days = (end_date - start_date).days + 1
        
        return {
            "organization_name": "Colorado CareAssist",
            "total_followers": 1847,
            "new_followers": int(days * 2.5),
            "impressions": int(days * 450),
            "clicks": int(days * 28),
            "likes": int(days * 35),
            "comments": int(days * 8),
            "shares": int(days * 12),
            "engagement": int(days * 55),
            "engagement_rate": 3.8,
            "top_posts": [
                {"title": "Caregiver appreciation post", "impressions": 1250, "engagement": 89},
                {"title": "Job opening announcement", "impressions": 980, "engagement": 67},
                {"title": "Company culture spotlight", "impressions": 756, "engagement": 52},
            ],
            "is_placeholder": True,
            "source": "placeholder",
            "fetched_at": datetime.utcnow().isoformat()
        }
    
    def _get_placeholder_ad_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return placeholder ad metrics (LinkedIn Ads not configured)"""
        return {
            "configured": False,
            "message": "LinkedIn Ads account not configured",
            "spend": 0,
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "is_placeholder": True,
            "source": "placeholder",
            "fetched_at": datetime.utcnow().isoformat()
        }


# Singleton instance
linkedin_service = LinkedInService()


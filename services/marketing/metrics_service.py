"""
Marketing metrics service layer.

Integrates with Facebook Graph API and Google Ads API to fetch real metrics.
Falls back to placeholder data if APIs are not configured or fail.
"""
from __future__ import annotations

import os
import logging
from datetime import date, timedelta
from typing import Dict, Any, Optional

from .facebook_service import facebook_service
from .google_ads_service import google_ads_service

logger = logging.getLogger(__name__)

# Configuration
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
USE_REAL_DATA = os.getenv("MARKETING_USE_REAL_DATA", "true").lower() == "true"


def get_social_metrics(start: date, end: date, compare: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch social media metrics from Facebook/Instagram.
    
    Args:
        start: Start date
        end: End date
        compare: Optional comparison type (e.g., "previous_period", "yoy")
    
    Returns:
        Dictionary containing social media metrics
    """
    if not USE_REAL_DATA or not FACEBOOK_PAGE_ID:
        logger.info("Using placeholder social metrics (real data disabled or no page ID)")
        return _get_placeholder_social_metrics(start, end)
    
    try:
        # Fetch real data from Facebook
        page_metrics = facebook_service.get_page_metrics(FACEBOOK_PAGE_ID, start, end)
        posts = facebook_service.get_posts_metrics(FACEBOOK_PAGE_ID, start, end, limit=50)
        click_actions = facebook_service.get_click_actions(FACEBOOK_PAGE_ID, start, end)
        
        # Calculate comparison if requested
        comparison_data = {}
        if compare == "previous_period":
            days_diff = (end - start).days + 1
            prev_start = start - timedelta(days=days_diff)
            prev_end = start - timedelta(days=1)
            prev_metrics = facebook_service.get_page_metrics(FACEBOOK_PAGE_ID, prev_start, prev_end)
            comparison_data = _calculate_comparison(page_metrics, prev_metrics)
        
        # Structure the response
        total_days = (end - start).days + 1
        
        return {
            "summary": {
                "total_page_likes": {
                    "value": page_metrics.get("current_page_likes", 0),
                    "change": comparison_data.get("total_page_likes_change", 0),
                    "trend": "up" if comparison_data.get("total_page_likes_change", 0) > 0 else "down",
                },
                "reach": {
                    "organic": page_metrics.get("unique_impressions", 0),
                    "paid": 0,  # Would need separate ads API call
                    "total": page_metrics.get("unique_impressions", 0),
                    "change": comparison_data.get("reach_change", 0),
                    "trend": "up" if comparison_data.get("reach_change", 0) > 0 else "down",
                },
                "impressions": page_metrics.get("impressions", 0),
                "page_visits": page_metrics.get("page_visits", 0),
                "unique_clicks": page_metrics.get("post_engagements", 0),
                "video_views_3s": page_metrics.get("video_views", 0),
            },
            "click_actions": {
                "get_directions": click_actions.get("get_directions", 0),
                "phone_clicks": click_actions.get("link", 0),
                "website_clicks": click_actions.get("other", 0),
                "action_button": click_actions.get("action_button", 0),
            },
            "post_overview": {
                "posts_published": len(posts),
                "post_reach": sum(p.get("reach", 0) for p in posts),
                "post_clicks": sum(p.get("clicks", 0) for p in posts),
                "engagement_by_post": sum(p.get("likes", 0) + p.get("comments", 0) + p.get("shares", 0) for p in posts),
                "chart": [
                    {"date": (start + timedelta(days=idx)).isoformat(), "reach": 420 + idx * 15, "engagement": 180 + idx * 7}
                    for idx in range(total_days)
                ],
            },
            "top_posts": [
                {
                    "title": post["title"],
                    "reach": post["reach"],
                    "clicks": post["clicks"],
                    "platform": post["platform"]
                }
                for post in posts[:10]  # Top 10 posts
            ],
        }
        
    except Exception as e:
        logger.error(f"Error fetching real social metrics, falling back to placeholder: {e}")
        return _get_placeholder_social_metrics(start, end)


def get_ads_metrics(start: date, end: date, compare: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch advertising metrics from Google Ads.
    
    Args:
        start: Start date
        end: End date
        compare: Optional comparison type (e.g., "previous_period", "yoy")
    
    Returns:
        Dictionary containing advertising metrics
    """
    if not USE_REAL_DATA:
        logger.info("Using placeholder ads metrics (real data disabled)")
        return _get_placeholder_ads_metrics(start, end)
    
    try:
        # Fetch real data from Google Ads
        metrics = google_ads_service.get_campaign_metrics(start, end)
        return metrics
        
    except Exception as e:
        logger.error(f"Error fetching real ads metrics, falling back to placeholder: {e}")
        return _get_placeholder_ads_metrics(start, end)


def _calculate_comparison(current: Dict, previous: Dict) -> Dict[str, float]:
    """Calculate percentage changes between current and previous periods"""
    comparison = {}
    
    current_likes = current.get("current_page_likes", 0)
    prev_likes = previous.get("current_page_likes", 0)
    if prev_likes > 0:
        comparison["total_page_likes_change"] = ((current_likes - prev_likes) / prev_likes) * 100
    
    current_reach = current.get("unique_impressions", 0)
    prev_reach = previous.get("unique_impressions", 0)
    if prev_reach > 0:
        comparison["reach_change"] = ((current_reach - prev_reach) / prev_reach) * 100
    
    return comparison


def _get_placeholder_social_metrics(start: date, end: date) -> Dict[str, Any]:
    """Return placeholder social metrics"""
    total_days = (end - start).days + 1
    
    return {
        "summary": {
            "total_page_likes": {
                "value": 2785,
                "change": 4.6,
                "trend": "up",
            },
            "reach": {
                "organic": 18340,
                "paid": 8640,
                "total": 26980,
                "change": -2.1,
                "trend": "down",
            },
            "impressions": 38950,
            "page_visits": 2946,
            "unique_clicks": 4834,
            "video_views_3s": 5190,
        },
        "click_actions": {
            "get_directions": 37,
            "phone_clicks": 34,
            "website_clicks": 91,
            "action_button": 99,
        },
        "post_overview": {
            "posts_published": 18,
            "post_reach": 8735,
            "post_clicks": 3690,
            "engagement_by_post": 1468,
            "chart": [
                {"date": (start + timedelta(days=idx)).isoformat(), "reach": 420 + idx * 15, "engagement": 180 + idx * 7}
                for idx in range(total_days)
            ],
        },
        "top_posts": [
            {"title": "Announcing fall caregiver event", "reach": 1250, "clicks": 210, "platform": "Facebook"},
            {"title": "Meet the team: spotlight", "reach": 980, "clicks": 162, "platform": "Instagram"},
            {"title": "Client success story", "reach": 860, "clicks": 131, "platform": "LinkedIn"},
        ],
    }


def _get_placeholder_ads_metrics(start: date, end: date) -> Dict[str, Any]:
    """Return placeholder ads metrics"""
    total_days = (end - start).days + 1
    
    return {
        "spend": {
            "total": 4183.00,
            "change": 38.0,
            "trend": "up",
            "daily": [
                {"date": (start + timedelta(days=idx)).isoformat(), "spend": 110 + idx * 8}
                for idx in range(min(total_days, 30))
            ],
        },
        "efficiency": {
            "cpc": 2.0,
            "cpm": 12.5,
            "ctr": 3.8,
            "conversion_rate": 4.6,
        },
        "performance": {
            "clicks": 322,
            "impressions": 7816,
            "conversion_value": 2550,
            "conversions": 98,
        },
        "campaigns": [
            {"name": "Fall caregiver recruitment", "spend": 763.0, "clicks": 181, "conversions": 32, "cpa": 23.84},
            {"name": "Home care awareness", "spend": 653.0, "clicks": 149, "conversions": 27, "cpa": 24.18},
            {"name": "Respite services remarketing", "spend": 705.0, "clicks": 173, "conversions": 24, "cpa": 29.38},
        ],
        "ad_sets": [
            {"name": "Lookalike caregivers", "impressions": 11562, "spend": 870.0, "conversions": 28},
            {"name": "Warm audience retargeting", "impressions": 8920, "spend": 640.0, "conversions": 21},
            {"name": "Cold outreach - seniors", "impressions": 7560, "spend": 520.0, "conversions": 17},
        ],
        "geo": [
            {"country": "United States", "spend": 3820.0},
            {"country": "Canada", "spend": 210.0},
            {"country": "Mexico", "spend": 153.0},
        ],
    }


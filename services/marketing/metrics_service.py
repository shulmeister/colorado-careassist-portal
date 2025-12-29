"""
Marketing metrics service layer.

Integrates with Facebook, Instagram, LinkedIn, Pinterest, TikTok,
Google Ads API, and more to fetch real marketing metrics.
Falls back to placeholder data if APIs are not configured or fail.
"""
from __future__ import annotations

import os
import logging
from datetime import date, timedelta
from typing import Dict, Any, Optional

from .facebook_service import facebook_service
from .facebook_ads_service import facebook_ads_service
from .google_ads_service import google_ads_service
from .mailchimp_service import mailchimp_marketing_service
from .instagram_service import instagram_service
from .linkedin_service import linkedin_service
from .pinterest_service import pinterest_service
from .tiktok_service import tiktok_service

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
    Fetch advertising metrics from Google Ads and Facebook Ads.
    
    Args:
        start: Start date
        end: End date
        compare: Optional comparison type (e.g., "previous_period", "yoy")
    
    Returns:
        Dictionary containing advertising metrics from both platforms
    """
    if not USE_REAL_DATA:
        logger.info("Using placeholder ads metrics (real data disabled)")
        return _get_placeholder_ads_metrics(start, end)
    
    try:
        google_metrics = google_ads_service.get_metrics(start, end)
        facebook_account = facebook_ads_service.get_account_metrics(start, end)
        facebook_campaigns = facebook_ads_service.get_campaign_metrics(start, end)

        return {
            "google_ads": google_metrics,
            "facebook_ads": {
                "account": facebook_account,
                "campaigns": facebook_campaigns,
            },
        }
        
    except Exception as e:
        logger.error(f"Error fetching real ads metrics, falling back to placeholder: {e}")
        return _get_placeholder_ads_metrics(start, end)


def get_email_metrics(start: date, end: date) -> Dict[str, Any]:
    """
    Fetch email marketing metrics from Mailchimp.
    """
    if not USE_REAL_DATA:
        logger.info("Using placeholder email metrics (real data disabled)")
        return mailchimp_marketing_service.get_placeholder_metrics(start, end)

    try:
        return mailchimp_marketing_service.get_email_metrics(start, end)
    except Exception as exc:
        logger.error("Error fetching email metrics: %s", exc)
        return mailchimp_marketing_service.get_placeholder_metrics(start, end)


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
    """Return placeholder ads metrics for both Google and Facebook"""
    return {
        "google_ads": google_ads_service.get_placeholder_metrics(start, end),
        "facebook_ads": {
            "account": facebook_ads_service.get_placeholder_account_metrics(start, end),
            "campaigns": [
                {"name": "October 2025 PMax Lead Gen Denver", "spend": 1190.78, "clicks": 280, "impressions": 8930, "conversions": 35},
                {"name": "October 2025 PMax Lead Gen - Springs", "spend": 1195.14, "clicks": 249, "impressions": 7530, "conversions": 25},
            ],
        },
    }


def get_instagram_metrics(start: date, end: date) -> Dict[str, Any]:
    """
    Fetch Instagram Business account metrics.
    
    Args:
        start: Start date
        end: End date
    
    Returns:
        Dictionary containing Instagram metrics
    """
    if not USE_REAL_DATA:
        logger.info("Using placeholder Instagram metrics (real data disabled)")
        return instagram_service._get_placeholder_metrics(start, end)
    
    try:
        return instagram_service.get_account_metrics(start, end)
    except Exception as e:
        logger.error(f"Error fetching Instagram metrics: {e}")
        return instagram_service._get_placeholder_metrics(start, end)


def get_linkedin_metrics(start: date, end: date) -> Dict[str, Any]:
    """
    Fetch LinkedIn company page and ads metrics.
    
    Args:
        start: Start date
        end: End date
    
    Returns:
        Dictionary containing LinkedIn organic and ads metrics
    """
    if not USE_REAL_DATA:
        logger.info("Using placeholder LinkedIn metrics (real data disabled)")
        return linkedin_service._get_placeholder_metrics(start, end)
    
    try:
        organic = linkedin_service.get_organization_metrics(start, end)
        ads = linkedin_service.get_ad_metrics(start, end)
        return {
            "organic": organic,
            "ads": ads,
        }
    except Exception as e:
        logger.error(f"Error fetching LinkedIn metrics: {e}")
        return {
            "organic": linkedin_service._get_placeholder_metrics(start, end),
            "ads": linkedin_service._get_placeholder_ad_metrics(start, end),
        }


def get_pinterest_metrics(start: date, end: date) -> Dict[str, Any]:
    """
    Fetch Pinterest user account and ads metrics.
    
    Args:
        start: Start date
        end: End date
    
    Returns:
        Dictionary containing Pinterest organic and ads metrics
    """
    if not USE_REAL_DATA:
        logger.info("Using placeholder Pinterest metrics (real data disabled)")
        return pinterest_service._get_placeholder_metrics(start, end)
    
    try:
        organic = pinterest_service.get_user_metrics(start, end)
        ads = pinterest_service.get_ad_metrics(start, end)
        return {
            "organic": organic,
            "ads": ads,
        }
    except Exception as e:
        logger.error(f"Error fetching Pinterest metrics: {e}")
        return {
            "organic": pinterest_service._get_placeholder_metrics(start, end),
            "ads": pinterest_service._get_placeholder_ad_metrics(start, end),
        }


def get_tiktok_metrics(start: date, end: date) -> Dict[str, Any]:
    """
    Fetch TikTok ads and engagement metrics.
    
    Args:
        start: Start date
        end: End date
    
    Returns:
        Dictionary containing TikTok ads and engagement metrics
    """
    if not USE_REAL_DATA:
        logger.info("Using placeholder TikTok metrics (real data disabled)")
        return tiktok_service._get_placeholder_metrics(start, end)
    
    try:
        ads = tiktok_service.get_ad_metrics(start, end)
        campaigns = tiktok_service.get_campaign_metrics(start, end)
        engagement = tiktok_service.get_engagement_metrics(start, end)
        return {
            "ads": ads,
            "campaigns": campaigns,
            "engagement": engagement,
        }
    except Exception as e:
        logger.error(f"Error fetching TikTok metrics: {e}")
        return {
            "ads": tiktok_service._get_placeholder_metrics(start, end),
            "campaigns": [],
            "engagement": tiktok_service._get_placeholder_engagement(start, end),
        }


def get_all_social_metrics(start: date, end: date) -> Dict[str, Any]:
    """
    Fetch social media metrics from ALL platforms.
    
    Args:
        start: Start date
        end: End date
    
    Returns:
        Dictionary containing metrics from Facebook, Instagram, LinkedIn, Pinterest, TikTok
    """
    return {
        "facebook": get_social_metrics(start, end),
        "instagram": get_instagram_metrics(start, end),
        "linkedin": get_linkedin_metrics(start, end),
        "pinterest": get_pinterest_metrics(start, end),
        "tiktok": get_tiktok_metrics(start, end),
        "fetched_at": date.today().isoformat(),
    }


"""
Marketing metrics service layer.

For now this returns structured placeholder data so the front-end
can be wired up immediately. Later we will swap in real API calls
to Facebook/Instagram and Google Ads.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, Any, Optional


def get_social_metrics(start: date, end: date, compare: Optional[str] = None) -> Dict[str, Any]:
    """
    Return placeholder social metrics. Structure mirrors the intended real payload.
    """
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
                {"date": _format_day(start, idx), "reach": 420 + idx * 15, "engagement": 180 + idx * 7}
                for idx in range(total_days)
            ],
        },
        "top_posts": [
            {"title": "Announcing fall caregiver event", "reach": 1250, "clicks": 210, "platform": "Facebook"},
            {"title": "Meet the team: spotlight", "reach": 980, "clicks": 162, "platform": "Instagram"},
            {"title": "Client success story", "reach": 860, "clicks": 131, "platform": "LinkedIn"},
        ],
    }


def get_ads_metrics(start: date, end: date, compare: Optional[str] = None) -> Dict[str, Any]:
    """
    Return placeholder ads metrics.
    """
    total_days = (end - start).days + 1
    
    return {
        "spend": {
            "total": 4183.00,
            "change": 38.0,
            "trend": "up",
            "chart": [
                {"date": _format_day(start, idx), "spend": 110 + idx * 8}
                for idx in range(total_days)
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


def _format_day(start: date, offset: int) -> str:
    return (start + timedelta(days=offset)).isoformat()


from datetime import timedelta  # noqa E402 (import after function definitions for clarity)


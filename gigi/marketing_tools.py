"""
Marketing tools for Gigi — shared business logic.
Called by telegram_bot.py, voice_brain.py, ringcentral_bot.py.
All functions are SYNCHRONOUS — callers wrap in asyncio.to_thread() / run_sync().
All functions return dicts — callers json.dumps() the result.
"""
import logging
from datetime import date, timedelta
from typing import Any, Dict

logger = logging.getLogger(__name__)


def parse_date_range(date_range: str = "7d") -> tuple:
    """Parse a date_range string into (start_date, end_date) tuple.

    Supported: "today", "7d", "30d", "mtd", "ytd", "last_month"
    """
    today = date.today()
    dr = (date_range or "7d").lower().strip()

    if dr == "today":
        return today, today
    elif dr == "30d":
        return today - timedelta(days=30), today
    elif dr == "mtd":
        return today.replace(day=1), today
    elif dr == "ytd":
        return today.replace(month=1, day=1), today
    elif dr == "last_month":
        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start, last_month_end
    else:
        # "7d" default, or parse "Nd" pattern
        if dr.endswith("d") and dr[:-1].isdigit():
            days = int(dr[:-1])
            return today - timedelta(days=days), today
        return today - timedelta(days=7), today


def get_marketing_dashboard(date_range: str = "7d") -> Dict[str, Any]:
    """Aggregated marketing snapshot from all channels."""
    start, end = parse_date_range(date_range)
    result = {"date_range": f"{start.isoformat()} to {end.isoformat()}"}

    try:
        from services.marketing.metrics_service import get_social_metrics
        result["social"] = get_social_metrics(start, end)
    except Exception as e:
        result["social"] = {"error": str(e)}

    try:
        from services.marketing.metrics_service import get_ads_metrics
        result["ads"] = get_ads_metrics(start, end)
    except Exception as e:
        result["ads"] = {"error": str(e)}

    try:
        from services.marketing.metrics_service import get_email_metrics
        result["email"] = get_email_metrics(start, end)
    except Exception as e:
        result["email"] = {"error": str(e)}

    return result


def get_google_ads_report(date_range: str = "30d") -> Dict[str, Any]:
    """Google Ads performance report."""
    start, end = parse_date_range(date_range)
    try:
        from services.marketing.google_ads_service import google_ads_service
        return google_ads_service.get_metrics(start, end)
    except Exception as e:
        logger.error(f"Google Ads report failed: {e}")
        return {"error": f"Google Ads unavailable: {str(e)}"}


def get_website_analytics(date_range: str = "7d") -> Dict[str, Any]:
    """GA4 website traffic and conversions."""
    start, end = parse_date_range(date_range)
    try:
        from services.marketing.ga4_service import ga4_service
        return ga4_service.get_website_metrics(start, end)
    except Exception as e:
        logger.error(f"Website analytics failed: {e}")
        return {"error": f"Website analytics unavailable: {str(e)}"}


def get_social_media_report(date_range: str = "7d", platform: str = "") -> Dict[str, Any]:
    """Social media report across Facebook, Instagram, LinkedIn, Pinterest."""
    import os
    start, end = parse_date_range(date_range)
    results = {}
    platform_lower = (platform or "").lower().strip()

    if not platform_lower or "facebook" in platform_lower:
        try:
            from services.marketing.facebook_service import facebook_service
            page_id = os.getenv("FACEBOOK_PAGE_ID")
            if page_id:
                results["facebook"] = facebook_service.get_page_metrics(page_id, start, end)
            else:
                results["facebook"] = {"not_configured": True}
        except Exception as e:
            results["facebook"] = {"error": str(e)}

    if not platform_lower or "instagram" in platform_lower:
        try:
            from services.marketing.instagram_service import instagram_service
            results["instagram"] = instagram_service.get_metrics(start, end)
        except Exception as e:
            results["instagram"] = {"error": str(e)}

    if not platform_lower or "linkedin" in platform_lower:
        try:
            from services.marketing.linkedin_service import linkedin_service
            results["linkedin"] = linkedin_service.get_metrics(start, end)
        except Exception as e:
            results["linkedin"] = {"error": str(e)}

    if not platform_lower or "pinterest" in platform_lower:
        try:
            from services.marketing.pinterest_service import pinterest_service
            results["pinterest"] = pinterest_service.get_user_metrics(start, end)
        except Exception as e:
            results["pinterest"] = {"error": str(e)}

    return {"date_range": f"{start.isoformat()} to {end.isoformat()}", "platforms": results}


def get_gbp_report(date_range: str = "30d") -> Dict[str, Any]:
    """Google Business Profile metrics."""
    start, end = parse_date_range(date_range)
    try:
        from services.marketing.gbp_service import gbp_service
        return gbp_service.get_gbp_metrics(start, end)
    except Exception as e:
        logger.error(f"GBP report failed: {e}")
        return {"error": f"Google Business Profile unavailable: {str(e)}"}


def get_email_campaign_report(date_range: str = "30d") -> Dict[str, Any]:
    """Brevo email campaign metrics."""
    start, end = parse_date_range(date_range)
    try:
        from services.marketing.metrics_service import get_email_metrics
        return get_email_metrics(start, end)
    except Exception as e:
        logger.error(f"Email campaign report failed: {e}")
        return {"error": f"Email metrics unavailable: {str(e)}"}


def generate_social_content(prompt: str, media_type: str = "single_image") -> Dict[str, Any]:
    """Generate social media content via Predis AI."""
    if not prompt:
        return {"error": "No prompt provided"}
    try:
        from services.marketing.predis_service import predis_service
        return predis_service.generate_content(prompt, media_type)
    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        return {"error": f"Content generation unavailable: {str(e)}"}

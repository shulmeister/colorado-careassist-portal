"""
Brevo (formerly Sendinblue) API integration for marketing dashboard email metrics.

This service fetches email campaign metrics from Brevo and returns them in
the same format as the Mailchimp service for seamless integration.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class BrevoMarketingService:
    """Fetches campaign and contact metrics from Brevo API v3."""

    def __init__(self) -> None:
        self.api_key = os.getenv("BREVO_API_KEY")
        self.base_url = "https://api.brevo.com/v3"
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            })

        if not self._is_configured():
            logger.warning("Brevo service not fully configured – using placeholder data")
        else:
            logger.info("Brevo service initialized successfully")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_email_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch email marketing metrics from Brevo for the given date range.
        
        Returns data in the same format as MailchimpMarketingService for compatibility.
        """
        if not self._is_configured():
            return self._placeholder_metrics(start_date, end_date)

        try:
            account_info = self._get_account_info()
            campaigns = self._get_campaign_reports(start_date, end_date)
            contacts_info = self._get_contacts_info()

            metrics = self._build_metrics(account_info, campaigns, contacts_info, start_date, end_date)
            metrics["is_placeholder"] = False
            metrics["source"] = "brevo_api"
            metrics["fetched_at"] = datetime.utcnow().isoformat()
            return metrics
        except requests.RequestException as exc:
            logger.error("Brevo API error: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Unexpected Brevo error: %s", exc)

        return self._placeholder_metrics(start_date, end_date)

    def get_placeholder_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Expose placeholder data for callers that need deterministic mocks."""
        return self._placeholder_metrics(start_date, end_date)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _is_configured(self) -> bool:
        return bool(self.api_key)

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = self.session.request(method, url, params=params, timeout=30)
        if response.status_code >= 400:
            raise requests.HTTPError(
                f"Brevo API error {response.status_code}: {response.text}",
                response=response,
            )
        return response.json()

    def _get_account_info(self) -> Dict[str, Any]:
        """Get account information including plan details."""
        try:
            return self._request("GET", "/account")
        except requests.HTTPError as exc:
            logger.warning("Unable to fetch Brevo account info: %s", exc)
            return {}

    def _get_contacts_info(self) -> Dict[str, Any]:
        """Get contact/subscriber statistics."""
        try:
            return self._request("GET", "/contacts")
        except requests.HTTPError as exc:
            logger.warning("Unable to fetch Brevo contacts info: %s", exc)
            return {"count": 0}

    def _get_campaign_reports(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Fetch email campaigns sent within the date range.
        
        Brevo API uses different date format and parameters than Mailchimp.
        """
        # Format dates for Brevo API (YYYY-MM-DD)
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()

        params = {
            "type": "classic",  # Regular email campaigns
            "status": "sent",
            "startDate": start_str,
            "endDate": end_str,
            "limit": 100,
            "offset": 0,
            "sort": "desc",
        }

        try:
            campaigns_resp = self._request("GET", "/emailCampaigns", params)
        except requests.HTTPError as exc:
            logger.warning("Unable to fetch Brevo campaigns: %s", exc)
            return []

        campaigns = campaigns_resp.get("campaigns", [])
        reports: List[Dict[str, Any]] = []

        for campaign in campaigns:
            campaign_id = campaign.get("id")
            if not campaign_id:
                continue

            # Brevo includes stats in the campaign response
            stats = campaign.get("statistics", {}).get("globalStats", {})
            
            emails_sent = stats.get("sent", 0) or campaign.get("recipients", {}).get("totalRecipients", 0)
            opens = stats.get("uniqueOpens", 0)
            clicks = stats.get("uniqueClicks", 0)
            bounces = (stats.get("hardBounces", 0) or 0) + (stats.get("softBounces", 0) or 0)

            report_entry = {
                "id": str(campaign_id),
                "title": campaign.get("name") or campaign.get("subject") or f"Campaign {campaign_id}",
                "send_time": campaign.get("sentDate") or campaign.get("scheduledAt"),
                "emails_sent": emails_sent,
                "opens_total": opens,
                "open_rate": self._safe_percent(opens, emails_sent),
                "click_rate": self._safe_percent(clicks, emails_sent),
                "clicks_total": clicks,
                "unique_clicks": clicks,  # Brevo reports unique clicks
                "bounces": bounces,
            }
            reports.append(report_entry)

        return reports

    def _build_metrics(
        self,
        account_info: Dict[str, Any],
        campaigns: List[Dict[str, Any]],
        contacts_info: Dict[str, Any],
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        total_contacts = contacts_info.get("count", 0)
        campaigns_sent = len(campaigns)

        total_emails_sent = sum(campaign["emails_sent"] for campaign in campaigns)
        total_opens = sum(campaign["opens_total"] for campaign in campaigns)
        total_clicks = sum(campaign["clicks_total"] for campaign in campaigns)
        total_unique_clicks = sum(campaign["unique_clicks"] for campaign in campaigns)
        total_bounces = sum(campaign["bounces"] for campaign in campaigns)

        avg_open_rate = self._safe_percent(total_opens, total_emails_sent)
        avg_click_rate = self._safe_percent(total_clicks, total_emails_sent)
        delivery_rate = self._safe_percent(total_emails_sent - total_bounces, total_emails_sent)

        # Build trend from campaign send times
        trend = []
        for campaign in campaigns:
            if not campaign.get("send_time"):
                continue
            try:
                send_time = campaign["send_time"]
                if isinstance(send_time, str):
                    # Handle ISO format
                    send_date = datetime.fromisoformat(send_time.replace("Z", "+00:00")).date()
                else:
                    continue
            except (ValueError, TypeError):
                continue
            trend.append(
                {
                    "date": send_date.isoformat(),
                    "opens": campaign["opens_total"],
                    "clicks": campaign["clicks_total"],
                }
            )

        # Sort campaigns by open rate for top performers
        top_campaigns = sorted(campaigns, key=lambda c: c.get("open_rate", 0), reverse=True)[:3]

        # For subscriber growth, we'd need to make additional API calls
        # For now, return empty list (Brevo doesn't have same growth history endpoint)
        growth: List[Dict[str, Any]] = []

        metrics = {
            "summary": {
                "campaigns_sent": campaigns_sent,
                "emails_sent": total_emails_sent,
                "total_contacts": total_contacts,
                "open_rate": round(avg_open_rate, 2),
                "click_rate": round(avg_click_rate, 2),
                "delivery_rate": round(delivery_rate, 2),
                "conversions": total_unique_clicks,
            },
            "top_campaigns": [
                {
                    "title": campaign["title"],
                    "open_rate": round(campaign.get("open_rate", 0), 2),
                    "click_rate": round(campaign.get("click_rate", 0), 2),
                }
                for campaign in top_campaigns
            ],
            "trend": trend,
            "subscriber_growth": growth,
        }

        return metrics

    @staticmethod
    def _safe_percent(numerator: float, denominator: float) -> float:
        if not denominator:
            return 0.0
        return (numerator / denominator) * 100

    def _placeholder_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return placeholder metrics when Brevo is not configured."""
        days = max((end_date - start_date).days + 1, 1)
        campaigns = [
            {"title": "Welcome Series", "open_rate": 45.2, "click_rate": 6.1},
            {"title": "Monthly Newsletter", "open_rate": 38.8, "click_rate": 4.5},
            {"title": "Service Update", "open_rate": 32.4, "click_rate": 3.2},
        ]

        trend = []
        for i in range(min(days, 12)):
            current_date = (start_date + timedelta(days=i * max(days // 12, 1))).isoformat()
            trend.append({"date": current_date, "opens": 280 + i * 12, "clicks": 58 + i * 4})

        growth = []
        subscribers = 2800
        for i in range(6):
            subscribers += 22
            growth.append(
                {
                    "date": (start_date - timedelta(days=(6 - i) * 7)).isoformat(),
                    "subscribers": subscribers,
                }
            )

        return {
            "summary": {
                "campaigns_sent": 0,
                "emails_sent": 0,
                "total_contacts": 0,
                "open_rate": 0.0,
                "click_rate": 0.0,
                "delivery_rate": 0.0,
                "conversions": 0,
            },
            "top_campaigns": [],
            "trend": [],
            "subscriber_growth": [],
            "is_placeholder": True,
            "source": "brevo_placeholder",
            "fetched_at": datetime.utcnow().isoformat(),
            "note": "No Brevo campaigns sent yet. Data will appear after first campaign.",
        }


# Singleton instance
brevo_marketing_service = BrevoMarketingService()




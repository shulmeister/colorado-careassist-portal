"""
Mailchimp API integration for marketing dashboard email metrics.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class MailchimpMarketingService:
    """Fetches campaign and audience metrics from Mailchimp."""

    def __init__(self) -> None:
        self.api_key = os.getenv("MAILCHIMP_API_KEY")
        self.server_prefix = os.getenv("MAILCHIMP_SERVER_PREFIX")
        self.list_id = os.getenv("MAILCHIMP_LIST_ID")
        self.base_url = (
            f"https://{self.server_prefix}.api.mailchimp.com/3.0" if self.server_prefix else None
        )
        self.session = requests.Session()
        if self.api_key:
            # Mailchimp uses HTTP basic auth. Username can be any string.
            self.session.auth = ("anystring", self.api_key)

        if not self._is_configured():
            logger.warning("Mailchimp service not fully configured – using placeholder data")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_email_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        if not self._is_configured():
            return self._placeholder_metrics(start_date, end_date)

        try:
            list_info = self._get_list_info()
            campaigns = self._get_campaign_reports(start_date, end_date)
            growth = self._get_list_growth_history()

            metrics = self._build_metrics(list_info, campaigns, growth, start_date, end_date)
            metrics["is_placeholder"] = False
            metrics["source"] = "mailchimp_api"
            metrics["fetched_at"] = datetime.utcnow().isoformat()
            return metrics
        except requests.RequestException as exc:
            logger.error("Mailchimp API error: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Unexpected Mailchimp error: %s", exc)

        return self._placeholder_metrics(start_date, end_date)

    def get_placeholder_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Expose placeholder data for callers that need deterministic mocks."""
        return self._placeholder_metrics(start_date, end_date)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _is_configured(self) -> bool:
        return bool(self.api_key and self.server_prefix and self.base_url)

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.base_url:
            raise RuntimeError("Mailchimp base URL not configured")

        url = f"{self.base_url}{path}"
        response = self.session.request(method, url, params=params, timeout=30)
        if response.status_code >= 400:
            raise requests.HTTPError(
                f"Mailchimp API error {response.status_code}: {response.text}",
                response=response,
            )
        return response.json()

    def _get_list_info(self) -> Dict[str, Any]:
        if not self.list_id:
            logger.warning("MAILCHIMP_LIST_ID not configured – subscriber metrics unavailable")
            return {}

        return self._request("GET", f"/lists/{self.list_id}")

    def _get_campaign_reports(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        since = datetime.combine(start_date, datetime.min.time()).isoformat()
        # Mailchimp before time is exclusive, so add one day to include the end date.
        before = datetime.combine(end_date + timedelta(days=1), datetime.min.time()).isoformat()

        params = {
            "status": "sent",
            "since_send_time": since,
            "before_send_time": before,
            "sort_field": "send_time",
            "sort_dir": "DESC",
            "count": 100,
        }

        campaigns_resp = self._request("GET", "/campaigns", params)
        campaigns = campaigns_resp.get("campaigns", [])
        reports: List[Dict[str, Any]] = []

        for campaign in campaigns:
            campaign_id = campaign.get("id")
            if not campaign_id:
                continue
            try:
                report = self._request("GET", f"/reports/{campaign_id}")
            except requests.HTTPError as exc:
                logger.warning("Unable to fetch Mailchimp report for campaign %s: %s", campaign_id, exc)
                continue

            report_entry = {
                "id": campaign_id,
                "title": self._campaign_title(campaign),
                "send_time": campaign.get("send_time"),
                "emails_sent": report.get("emails_sent", 0),
                "opens_total": report.get("opens", {}).get("opens_total", 0),
                "open_rate": self._ratio_to_percent(report.get("opens", {}).get("open_rate")),
                "click_rate": self._ratio_to_percent(report.get("clicks", {}).get("click_rate")),
                "clicks_total": report.get("clicks", {}).get("clicks_total", 0),
                "unique_clicks": report.get("clicks", {}).get("unique_subscriber_clicks", 0),
                "bounces": (
                    report.get("bounces", {}).get("hard_bounces", 0)
                    + report.get("bounces", {}).get("soft_bounces", 0)
                ),
            }
            reports.append(report_entry)

        return reports

    def _get_list_growth_history(self) -> List[Dict[str, Any]]:
        if not self.list_id:
            return []

        params = {"count": 15, "sort_dir": "DESC"}
        try:
            response = self._request("GET", f"/reports/list-growth-history/{self.list_id}", params=params)
        except requests.HTTPError as exc:
            logger.warning("Unable to fetch Mailchimp growth history: %s", exc)
            return []

        history = response.get("history", [])
        growth_data: List[Dict[str, Any]] = []
        for entry in history:
            month = entry.get("month")
            if not month:
                continue
            try:
                # Mailchimp returns YYYY-MM
                parsed = datetime.strptime(month, "%Y-%m")
                growth_data.append({"date": parsed.date().isoformat(), "subscribers": entry.get("existing", 0)})
            except ValueError:
                continue

        return list(reversed(growth_data))

    def _build_metrics(
        self,
        list_info: Dict[str, Any],
        campaigns: List[Dict[str, Any]],
        growth: List[Dict[str, Any]],
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        total_contacts = list_info.get("stats", {}).get("member_count")
        campaigns_sent = len(campaigns)

        total_emails_sent = sum(campaign["emails_sent"] for campaign in campaigns)
        total_opens = sum(campaign["opens_total"] for campaign in campaigns)
        total_clicks = sum(campaign["clicks_total"] for campaign in campaigns)
        total_unique_clicks = sum(campaign["unique_clicks"] for campaign in campaigns)
        total_bounces = sum(campaign["bounces"] for campaign in campaigns)

        avg_open_rate = self._safe_percent(total_opens, total_emails_sent)
        avg_click_rate = self._safe_percent(total_clicks, total_emails_sent)
        delivery_rate = self._safe_percent(total_emails_sent - total_bounces, total_emails_sent)

        trend = []
        for campaign in campaigns:
            if not campaign.get("send_time"):
                continue
            try:
                send_date = datetime.fromisoformat(campaign["send_time"].replace("Z", "+00:00")).date()
            except ValueError:
                continue
            trend.append(
                {
                    "date": send_date.isoformat(),
                    "opens": campaign["opens_total"],
                    "clicks": campaign["clicks_total"],
                }
            )

        top_campaigns = sorted(campaigns, key=lambda c: c.get("open_rate", 0), reverse=True)[:3]

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
    def _campaign_title(campaign: Dict[str, Any]) -> str:
        settings = campaign.get("settings") or {}
        return settings.get("title") or settings.get("subject_line") or campaign.get("id", "Campaign")

    @staticmethod
    def _ratio_to_percent(value: Optional[float]) -> float:
        if value is None:
            return 0.0
        return float(value) * 100

    @staticmethod
    def _safe_percent(numerator: float, denominator: float) -> float:
        if not denominator:
            return 0.0
        return (numerator / denominator) * 100

    def _placeholder_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        days = max((end_date - start_date).days + 1, 1)
        campaigns = [
            {"title": "Fall Newsletter", "open_rate": 42.1, "click_rate": 5.8},
            {"title": "Care Tips Weekly", "open_rate": 38.6, "click_rate": 4.1},
            {"title": "Event Invitation", "open_rate": 35.2, "click_rate": 3.5},
        ]

        trend = []
        for i in range(min(days, 12)):
            current_date = (start_date + timedelta(days=i * max(days // 12, 1))).isoformat()
            trend.append({"date": current_date, "opens": 320 + i * 15, "clicks": 64 + i * 5})

        growth = []
        subscribers = 3300
        for i in range(6):
            subscribers += 15
            growth.append(
                {
                    "date": (start_date - timedelta(days=(6 - i) * 7)).isoformat(),
                    "subscribers": subscribers,
                }
            )

        return {
            "summary": {
                "campaigns_sent": 12,
                "emails_sent": 12000,
                "total_contacts": 3428,
                "open_rate": 28.4,
                "click_rate": 4.2,
                "delivery_rate": 98.6,
                "conversions": 67,
            },
            "top_campaigns": campaigns,
            "trend": trend,
            "subscriber_growth": growth,
            "is_placeholder": True,
            "source": "placeholder",
            "fetched_at": datetime.utcnow().isoformat(),
        }


# Singleton instance
mailchimp_marketing_service = MailchimpMarketingService()


"""
Google Ads API integration for fetching advertising metrics.

Provides real spend, clicks, impressions, conversions, ROAS, and campaign detail.
Falls back to realistic placeholder data when credentials or tokens are missing.
"""
from __future__ import annotations

import os
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy import desc

try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
except ImportError:  # pragma: no cover - handled at runtime if library missing
    GoogleAdsClient = None  # type: ignore
    GoogleAdsException = Exception  # type: ignore

from portal_database import db_manager
from portal_models import OAuthToken

logger = logging.getLogger(__name__)

MICROS_IN_CURRENCY = 1_000_000


class GoogleAdsService:
    """Service wrapper for Google Ads metrics."""

    def __init__(self) -> None:
        self.developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
        self.customer_id = self._normalize_customer_id(os.getenv("GOOGLE_ADS_CUSTOMER_ID"))
        self.login_customer_id = self._normalize_customer_id(os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID"))
        self.client_id = os.getenv("GOOGLE_ADS_OAUTH_CLIENT_ID", os.getenv("GOOGLE_CLIENT_ID"))
        self.client_secret = os.getenv("GOOGLE_ADS_OAUTH_CLIENT_SECRET", os.getenv("GOOGLE_CLIENT_SECRET"))
        self.currency_code = os.getenv("GOOGLE_ADS_CURRENCY", "USD")
        self._cached_refresh_token: Optional[str] = None

        if not self._is_configured():
            logger.warning("Google Ads service not fully configured – using placeholder data")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch Google Ads metrics for the requested date range.

        Returns a dictionary shaped for the marketing dashboard.
        """
        if not self._is_configured():
            return self._get_placeholder_metrics(start_date, end_date)

        client = self._build_client()
        if not client:
            logger.warning("Google Ads client unavailable – returning placeholder metrics")
            return self._get_placeholder_metrics(start_date, end_date)

        start_str = start_date.isoformat()
        end_str = end_date.isoformat()

        try:
            ga_service = client.get_service("GoogleAdsService")

            daily, currency_code = self._fetch_daily_breakdown(ga_service, start_str, end_str)
            if not daily:
                logger.warning("Google Ads daily breakdown returned no rows")
                return self._get_placeholder_metrics(start_date, end_date)

            overview = self._build_overview_from_daily(daily, start_date, end_date)
            campaigns = self._fetch_campaigns(ga_service, start_str, end_str)

            overview["spend"]["daily"] = daily
            overview["campaigns"] = campaigns
            overview["currency_code"] = currency_code or overview.get("currency_code") or self.currency_code
            overview["is_placeholder"] = False
            overview["source"] = "google_ads_api"
            overview["fetched_at"] = datetime.utcnow().isoformat()

            return overview

        except GoogleAdsException as exc:  # pragma: no cover - network/system error
            logger.error("Google Ads API error: %s", getattr(exc, "failure", exc))
            return self._get_placeholder_metrics(start_date, end_date)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Unexpected Google Ads error: %s", exc)
            return self._get_placeholder_metrics(start_date, end_date)

    def get_placeholder_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Expose placeholder metrics for other modules (tests, fallbacks)."""
        return self._get_placeholder_metrics(start_date, end_date)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _is_configured(self) -> bool:
        return bool(
            self.developer_token
            and self.customer_id
            and self.client_id
            and self.client_secret
            and GoogleAdsClient is not None
        )

    def _build_client(self):
        refresh_token = self._get_refresh_token()
        if not refresh_token:
            logger.warning("No Google Ads refresh token found – cannot build client")
            return None

        config = {
            "developer_token": self.developer_token,
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "use_proto_plus": True,
        }

        if self.login_customer_id:
            config["login_customer_id"] = self.login_customer_id

        return GoogleAdsClient.load_from_dict(config)

    def _get_refresh_token(self) -> Optional[str]:
        env_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
        if env_token:
            return env_token.strip()

        if self._cached_refresh_token:
            return self._cached_refresh_token

        session = None
        try:
            session = db_manager.get_session()
            token = (
                session.query(OAuthToken)
                .filter(
                    OAuthToken.service == "google-ads",
                    OAuthToken.is_active == True,  # noqa: E712
                )
                .order_by(desc(OAuthToken.updated_at))
                .first()
            )
            if token and token.refresh_token:
                self._cached_refresh_token = token.refresh_token
                return token.refresh_token
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Unable to read Google Ads refresh token from DB: %s", exc)
        finally:
            if session:
                session.close()

        return None

    def _fetch_daily_breakdown(self, ga_service, start: str, end: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        query = f"""
            SELECT
              customer.currency_code,
              segments.date,
              metrics.cost_micros,
              metrics.clicks,
              metrics.impressions,
              metrics.conversions,
              metrics.conversions_value
            FROM customer
            WHERE segments.date BETWEEN '{start}' AND '{end}'
            ORDER BY segments.date
        """

        breakdown: List[Dict[str, Any]] = []
        currency_code: Optional[str] = None
        response = ga_service.search_stream(customer_id=self.customer_id, query=query)

        for batch in response:
            for row in batch.results:
                if not currency_code:
                    currency_code = getattr(row.customer, "currency_code", None)
                spend = self._micros_to_currency(getattr(row.metrics, "cost_micros", 0))
                clicks = self._safe_int(getattr(row.metrics, "clicks", 0))
                impressions = self._safe_int(getattr(row.metrics, "impressions", 0))
                conversions = self._safe_float(getattr(row.metrics, "conversions", 0.0))
                conversion_value = self._safe_float(getattr(row.metrics, "conversions_value", 0.0))

                breakdown.append(
                    {
                        "date": row.segments.date,
                        "spend": round(spend, 2),
                        "clicks": clicks,
                        "impressions": impressions,
                        "conversions": conversions,
                        "conversion_value": round(conversion_value, 2),
                        "roas": round(self._safe_divide(conversion_value, spend), 2),
                        "cost_per_conversion": round(self._safe_divide(spend, conversions), 2),
                    }
                )

        return breakdown, currency_code

    def _fetch_campaigns(self, ga_service, start: str, end: str, limit: int = 12) -> List[Dict[str, Any]]:
        query = f"""
            SELECT
              campaign.id,
              campaign.name,
              campaign.status,
              campaign.advertising_channel_type,
              metrics.cost_micros,
              metrics.clicks,
              metrics.impressions,
              metrics.conversions,
              metrics.conversions_value,
              metrics.ctr
            FROM campaign
            WHERE segments.date BETWEEN '{start}' AND '{end}'
              AND campaign.status != 'REMOVED'
            ORDER BY metrics.cost_micros DESC
            LIMIT {limit}
        """

        response = ga_service.search_stream(customer_id=self.customer_id, query=query)
        campaigns: List[Dict[str, Any]] = []

        for batch in response:
            for row in batch.results:
                spend = self._micros_to_currency(getattr(row.metrics, "cost_micros", 0))
                clicks = self._safe_int(getattr(row.metrics, "clicks", 0))
                conversions = self._safe_float(getattr(row.metrics, "conversions", 0.0))
                conversion_value = self._safe_float(getattr(row.metrics, "conversions_value", 0.0))
                ctr = self._safe_float(getattr(row.metrics, "ctr", 0.0))

                campaigns.append(
                    {
                        "id": str(getattr(row.campaign, "id", "")),
                        "name": getattr(row.campaign, "name", "Unnamed Campaign"),
                        "status": getattr(getattr(row.campaign, "status", None), "name", "UNKNOWN"),
                        "channel": getattr(
                            getattr(row.campaign, "advertising_channel_type", None), "name", "UNKNOWN"
                        ),
                        "spend": round(spend, 2),
                        "clicks": clicks,
                        "impressions": self._safe_int(getattr(row.metrics, "impressions", 0)),
                        "conversions": conversions,
                        "conversion_value": round(conversion_value, 2),
                        "ctr": round(ctr, 2),
                        "cpc": round(self._safe_divide(spend, clicks), 2),
                        "roas": round(self._safe_divide(conversion_value, spend), 2),
                        "cost_per_conversion": round(self._safe_divide(spend, conversions), 2),
                    }
                )

        return campaigns

    def _build_overview_from_daily(
        self, daily: List[Dict[str, Any]], start_date: date, end_date: date
    ) -> Dict[str, Any]:
        days = max((end_date - start_date).days + 1, 1)
        totals = {
            "spend": 0.0,
            "clicks": 0,
            "impressions": 0,
            "conversions": 0.0,
            "conversion_value": 0.0,
        }

        for entry in daily:
            totals["spend"] += entry.get("spend", 0.0)
            totals["clicks"] += entry.get("clicks", 0)
            totals["impressions"] += entry.get("impressions", 0)
            totals["conversions"] += entry.get("conversions", 0.0)
            totals["conversion_value"] += entry.get("conversion_value", 0.0)

        cost = totals["spend"]
        clicks = totals["clicks"]
        impressions = totals["impressions"]
        conversions = totals["conversions"]
        conversion_value = totals["conversion_value"]

        per_day = self._safe_divide(cost, days)
        ctr = self._safe_divide(clicks, impressions) * 100
        avg_cpc = self._safe_divide(cost, clicks)
        avg_cpm = self._safe_divide(cost, impressions) * 1000
        cost_per_conversion = self._safe_divide(cost, conversions)
        roas = self._safe_divide(conversion_value, cost)
        conversion_rate = self._safe_divide(conversions, clicks) * 100

        return {
            "currency_code": self.currency_code,
            "spend": {
                "total": round(cost, 2),
                "per_day": round(per_day, 2),
                "daily": [],
            },
            "performance": {
                "clicks": clicks,
                "impressions": impressions,
                "conversions": round(conversions, 2),
                "conversion_value": round(conversion_value, 2),
            },
            "efficiency": {
                "ctr": round(ctr, 2),
                "cpc": round(avg_cpc, 2),
                "cpm": round(avg_cpm, 2),
                "cost_per_conversion": round(cost_per_conversion, 2),
                "roas": round(roas, 2),
                "conversion_rate": round(conversion_rate, 2),
            },
            "campaigns": [],
        }

    def _get_placeholder_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return empty metrics when Google Ads is not configured - NO FAKE DATA."""
        return {
            "currency_code": self.currency_code,
            "spend": {
                "total": 0,
                "per_day": 0,
                "daily": [],
            },
            "performance": {
                "clicks": 0,
                "impressions": 0,
                "conversions": 0,
                "conversion_value": 0,
            },
            "efficiency": {
                "ctr": 0,
                "cpc": 0,
                "cpm": 0,
                "cost_per_conversion": 0,
                "roas": 0,
                "conversion_rate": 0,
            },
            "campaigns": [],
            "is_placeholder": True,
            "not_configured": True,
            "message": "Google Ads API not configured or account suspended",
            "source": "not_connected",
            "fetched_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _normalize_customer_id(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return value.replace("-", "").strip()

    @staticmethod
    def _micros_to_currency(value: Optional[int]) -> float:
        return (int(value) / MICROS_IN_CURRENCY) if value else 0.0

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_divide(numerator: float, denominator: float) -> float:
        if not denominator:
            return 0.0
        return numerator / denominator

    @staticmethod
    def _range_days_str(start: str, end: str) -> int:
        try:
            start_date = date.fromisoformat(start)
            end_date = date.fromisoformat(end)
            return (end_date - start_date).days + 1
        except ValueError:
            return 1

    @staticmethod
    def _first_result(response):
        for batch in response:
            for row in batch.results:
                return row
        return None


# Singleton instance
google_ads_service = GoogleAdsService()

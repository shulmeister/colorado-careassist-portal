import json
import logging
import os
from datetime import date, timedelta
from typing import Any, Dict, List

from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# GSC API dimensions
DIM_QUERY = "query"
DIM_PAGE = "page"
DIM_DATE = "date"
DIM_DEVICE = "device"
DIM_COUNTRY = "country"


class GSCService:
    """Google Search Console API integration for organic search metrics."""

    def __init__(self):
        self.site_url = os.getenv("GSC_SITE_URL", "https://coloradocareassist.com")
        self.service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

        if not self.service_account_json:
            logger.warning(
                "GOOGLE_SERVICE_ACCOUNT_JSON not set. GSC will use empty data."
            )
            self.client = None
        else:
            try:
                credentials_dict = json.loads(self.service_account_json)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict,
                    scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
                )
                self.client = build("searchconsole", "v1", credentials=credentials)
                logger.info(f"GSC service initialized for {self.site_url}")
            except Exception as e:
                logger.error(f"Failed to initialize GSC client: {e}")
                self.client = None

    def get_search_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Fetch organic search metrics from Google Search Console."""
        if not self.client:
            return self._get_mock_data(start_date, end_date)

        # GSC data has a 2-3 day lag — clamp end_date
        max_end = date.today() - timedelta(days=3)
        if end_date > max_end:
            end_date = max_end
        if start_date > end_date:
            start_date = end_date - timedelta(days=7)

        try:
            totals = self._get_totals(start_date, end_date)
            daily = self._get_daily_trend(start_date, end_date)
            top_queries = self._get_top_queries(start_date, end_date)
            top_pages = self._get_top_pages(start_date, end_date)
            device_breakdown = self._get_device_breakdown(start_date, end_date)

            return {
                **totals,
                "daily_trend": daily,
                "top_queries": top_queries,
                "top_pages": top_pages,
                "device_breakdown": device_breakdown,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
            }
        except Exception as e:
            logger.error(f"Error fetching GSC metrics: {e}")
            return self._get_mock_data(start_date, end_date)

    # ── Private helpers ──────────────────────────────────────────

    def _query(
        self,
        start_date: date,
        end_date: date,
        dimensions: List[str] | None = None,
        row_limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Execute a searchAnalytics.query request."""
        body: Dict[str, Any] = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "rowLimit": row_limit,
        }
        if dimensions:
            body["dimensions"] = dimensions

        response = (
            self.client.searchanalytics()
            .query(siteUrl=self.site_url, body=body)
            .execute()
        )
        return response.get("rows", [])

    def _get_totals(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Fetch aggregate clicks, impressions, CTR, position."""
        rows = self._query(start_date, end_date, dimensions=None, row_limit=1)
        if not rows:
            return {
                "total_clicks": 0,
                "total_impressions": 0,
                "avg_ctr": 0,
                "avg_position": 0,
            }
        row = rows[0]
        return {
            "total_clicks": int(row.get("clicks", 0)),
            "total_impressions": int(row.get("impressions", 0)),
            "avg_ctr": round(row.get("ctr", 0) * 100, 2),
            "avg_position": round(row.get("position", 0), 1),
        }

    def _get_daily_trend(
        self, start_date: date, end_date: date
    ) -> List[Dict[str, Any]]:
        """Fetch daily clicks + impressions."""
        rows = self._query(start_date, end_date, dimensions=[DIM_DATE], row_limit=90)
        return [
            {
                "date": r["keys"][0],
                "clicks": int(r.get("clicks", 0)),
                "impressions": int(r.get("impressions", 0)),
                "ctr": round(r.get("ctr", 0) * 100, 2),
                "position": round(r.get("position", 0), 1),
            }
            for r in sorted(rows, key=lambda x: x["keys"][0])
        ]

    def _get_top_queries(
        self, start_date: date, end_date: date
    ) -> List[Dict[str, Any]]:
        """Top search queries by clicks."""
        rows = self._query(start_date, end_date, dimensions=[DIM_QUERY], row_limit=25)
        return [
            {
                "query": r["keys"][0],
                "clicks": int(r.get("clicks", 0)),
                "impressions": int(r.get("impressions", 0)),
                "ctr": round(r.get("ctr", 0) * 100, 2),
                "position": round(r.get("position", 0), 1),
            }
            for r in rows
        ]

    def _get_top_pages(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Top landing pages by clicks."""
        rows = self._query(start_date, end_date, dimensions=[DIM_PAGE], row_limit=25)
        return [
            {
                "page": r["keys"][0],
                "clicks": int(r.get("clicks", 0)),
                "impressions": int(r.get("impressions", 0)),
                "ctr": round(r.get("ctr", 0) * 100, 2),
                "position": round(r.get("position", 0), 1),
            }
            for r in rows
        ]

    def _get_device_breakdown(
        self, start_date: date, end_date: date
    ) -> List[Dict[str, Any]]:
        """Clicks + impressions by device type (DESKTOP, MOBILE, TABLET)."""
        rows = self._query(start_date, end_date, dimensions=[DIM_DEVICE], row_limit=5)
        return [
            {
                "device": r["keys"][0],
                "clicks": int(r.get("clicks", 0)),
                "impressions": int(r.get("impressions", 0)),
                "ctr": round(r.get("ctr", 0) * 100, 2),
            }
            for r in rows
        ]

    def _get_mock_data(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return empty data when GSC is not configured."""
        return {
            "total_clicks": 0,
            "total_impressions": 0,
            "avg_ctr": 0,
            "avg_position": 0,
            "daily_trend": [],
            "top_queries": [],
            "top_pages": [],
            "device_breakdown": [],
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "not_configured": True,
            "message": "Google Search Console not configured. Add service account as a verified owner in GSC.",
        }


gsc_service = GSCService()

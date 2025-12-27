import os
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


class GA4Service:
    def __init__(self):
        self.property_id = os.getenv("GA4_PROPERTY_ID", "445403783")
        self.service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        
        if not self.service_account_json:
            logger.warning("GOOGLE_SERVICE_ACCOUNT_JSON not set. GA4 API calls will use mock data.")
            self.client = None
        else:
            try:
                import json
                credentials_dict = json.loads(self.service_account_json)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict,
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"]
                )
                self.client = BetaAnalyticsDataClient(credentials=credentials)
                logger.info("GA4 service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize GA4 client: {e}")
                self.client = None

    def get_website_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch website metrics from GA4.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Dictionary containing GA4 metrics
        """
        if not self.client:
            logger.warning("GA4 client not configured, returning mock data")
            return self._get_mock_data(start_date, end_date)
        
        logger.info(f"Fetching GA4 metrics for property {self.property_id} from {start_date} to {end_date}")
        
        try:
            # Fetch main metrics
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                date_ranges=[DateRange(
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d")
                )],
                dimensions=[],
                metrics=[
                    Metric(name="totalUsers"),
                    Metric(name="sessions"),
                    Metric(name="conversions"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="engagementRate"),
                    Metric(name="bounceRate"),
                ]
            )
            
            response = self.client.run_report(request)
            
            if not response.rows:
                logger.warning("No data returned from GA4")
                return self._get_mock_data(start_date, end_date)
            
            row = response.rows[0]
            total_users = int(row.metric_values[0].value)
            sessions = int(row.metric_values[1].value)
            conversions = int(float(row.metric_values[2].value))
            avg_session_duration = float(row.metric_values[3].value)
            engagement_rate = float(row.metric_values[4].value) * 100
            bounce_rate = float(row.metric_values[5].value) * 100
            
            # Format session duration as MM:SS
            minutes = int(avg_session_duration // 60)
            seconds = int(avg_session_duration % 60)
            avg_session_duration_str = f"{minutes}:{seconds:02d}"
            
            # Calculate conversion rate
            conversion_rate = (conversions / total_users * 100) if total_users > 0 else 0
            
            # Fetch users over time
            users_over_time = self._get_users_over_time(start_date, end_date)
            
            # Fetch sessions by source
            sessions_by_source = self._get_sessions_by_source(start_date, end_date)
            
            # Fetch conversions by source
            conversions_by_source = self._get_conversions_by_source(start_date, end_date)
            
            # Fetch sessions by medium over time
            sessions_by_medium = self._get_sessions_by_medium(start_date, end_date)
            
            # Fetch top pages
            top_pages = self._get_top_pages(start_date, end_date)
            
            return {
                "total_users": total_users,
                "sessions": sessions,
                "conversions": conversions,
                "conversion_rate": conversion_rate,
                "avg_session_duration": avg_session_duration_str,
                "engagement_rate": engagement_rate,
                "bounce_rate": bounce_rate,
                "users_over_time": users_over_time,
                "sessions_by_source": sessions_by_source,
                "conversions_by_source": conversions_by_source,
                "conversion_paths": self._build_conversion_paths(conversions_by_source),
                "sessions_by_medium": sessions_by_medium,
                "top_pages": top_pages,
            }
            
        except Exception as e:
            logger.error(f"Error fetching GA4 metrics: {e}")
            return self._get_mock_data(start_date, end_date)

    def _get_users_over_time(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Fetch daily users over time."""
        try:
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                date_ranges=[DateRange(
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d")
                )],
                dimensions=[Dimension(name="date")],
                metrics=[Metric(name="totalUsers")],
                order_bys=[{"dimension": {"dimension_name": "date"}}]
            )
            
            response = self.client.run_report(request)
            
            users_data = []
            for row in response.rows:
                date_str = row.dimension_values[0].value
                users = int(row.metric_values[0].value)
                # Convert YYYYMMDD to YYYY-MM-DD
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                users_data.append({"date": formatted_date, "users": users})
            
            return users_data
        except Exception as e:
            logger.error(f"Error fetching users over time: {e}")
            return []

    def _get_sessions_by_source(self, start_date: date, end_date: date) -> Dict[str, int]:
        """Fetch sessions grouped by source."""
        try:
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                date_ranges=[DateRange(
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d")
                )],
                dimensions=[Dimension(name="sessionSource")],
                metrics=[Metric(name="sessions")],
                order_bys=[{"metric": {"metric_name": "sessions"}, "desc": True}],
                limit=10
            )
            
            response = self.client.run_report(request)
            
            sessions_by_source = {}
            for row in response.rows:
                source = row.dimension_values[0].value
                sessions = int(row.metric_values[0].value)
                sessions_by_source[source] = sessions
            
            return sessions_by_source
        except Exception as e:
            logger.error(f"Error fetching sessions by source: {e}")
            return {}

    def _get_conversions_by_source(self, start_date: date, end_date: date) -> Dict[str, int]:
        """Fetch conversions grouped by source."""
        try:
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                date_ranges=[DateRange(
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d")
                )],
                dimensions=[Dimension(name="sessionSource")],
                metrics=[Metric(name="conversions")],
                order_bys=[{"metric": {"metric_name": "conversions"}, "desc": True}],
                limit=10
            )
            
            response = self.client.run_report(request)
            
            conversions_by_source = {}
            for row in response.rows:
                source = row.dimension_values[0].value
                conversions = int(float(row.metric_values[0].value))
                conversions_by_source[source] = conversions
            
            return conversions_by_source
        except Exception as e:
            logger.error(f"Error fetching conversions by source: {e}")
            return {}

    def _get_sessions_by_medium(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Fetch sessions by medium over time."""
        try:
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                date_ranges=[DateRange(
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d")
                )],
                dimensions=[
                    Dimension(name="date"),
                    Dimension(name="sessionMedium")
                ],
                metrics=[Metric(name="sessions")],
                order_bys=[{"dimension": {"dimension_name": "date"}}]
            )
            
            response = self.client.run_report(request)
            
            # Group by date
            sessions_by_date = {}
            for row in response.rows:
                date_str = row.dimension_values[0].value
                medium = row.dimension_values[1].value
                sessions = int(row.metric_values[0].value)
                
                # Convert YYYYMMDD to YYYY-MM-DD
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                
                if formatted_date not in sessions_by_date:
                    sessions_by_date[formatted_date] = {
                        "date": formatted_date,
                        "none": 0,
                        "cpc": 0,
                        "paid": 0,
                        "referral": 0,
                        "organic": 0
                    }
                
                # Map medium to our categories
                if medium == "(none)":
                    sessions_by_date[formatted_date]["none"] += sessions
                elif medium == "cpc":
                    sessions_by_date[formatted_date]["cpc"] += sessions
                elif "paid" in medium.lower():
                    sessions_by_date[formatted_date]["paid"] += sessions
                elif medium == "referral":
                    sessions_by_date[formatted_date]["referral"] += sessions
                elif medium == "organic":
                    sessions_by_date[formatted_date]["organic"] += sessions
                else:
                    # Default to referral for unknown mediums
                    sessions_by_date[formatted_date]["referral"] += sessions
            
            return list(sessions_by_date.values())
        except Exception as e:
            logger.error(f"Error fetching sessions by medium: {e}")
            return []

    def _get_top_pages(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Fetch top pages by views."""
        try:
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                date_ranges=[DateRange(
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d")
                )],
                dimensions=[Dimension(name="pagePath")],
                metrics=[
                    Metric(name="screenPageViews"),
                    Metric(name="engagementRate")
                ],
                order_bys=[{"metric": {"metric_name": "screenPageViews"}, "desc": True}],
                limit=10
            )
            
            response = self.client.run_report(request)
            
            top_pages = []
            for row in response.rows:
                path = row.dimension_values[0].value
                views = int(row.metric_values[0].value)
                engagement_rate = float(row.metric_values[1].value) * 100
                
                top_pages.append({
                    "path": path,
                    "views": views,
                    "engagement_rate": engagement_rate
                })
            
            return top_pages
        except Exception as e:
            logger.error(f"Error fetching top pages: {e}")
            return []

    @staticmethod
    def _build_conversion_paths(conversions_by_source: Dict[str, int]) -> List[Dict[str, Any]]:
        """Build simple conversion-path snippets from source data."""
        if not conversions_by_source:
            return []
        sorted_sources = sorted(
            conversions_by_source.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        paths = []
        for source, value in sorted_sources[:5]:
            path_label = f"{source} → conversion"
            paths.append({"path": path_label, "conversions": value})
        return paths

    def _get_mock_data(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return empty data when GA4 is not configured - NO FAKE DATA."""
        return {
            "total_users": 0,
            "sessions": 0,
            "conversions": 0,
            "conversion_rate": 0,
            "avg_session_duration": "0:00",
            "engagement_rate": 0,
            "bounce_rate": 0,
            "users_over_time": [],
            "sessions_by_source": {},
            "conversions_by_source": {},
            "conversion_paths": [],
            "sessions_by_medium": [],
            "top_pages": [],
            "not_configured": True,
            "message": "GA4 not configured. Add service account to your GA4 property."
        }


ga4_service = GA4Service()


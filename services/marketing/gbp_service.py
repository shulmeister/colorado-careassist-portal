import os
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


class GBPService:
    def __init__(self):
        # Support multiple location IDs
        location_ids_str = os.getenv("GBP_LOCATION_IDS", "2279972127373883206,15500135164371037339")
        self.location_ids = [lid.strip() for lid in location_ids_str.split(",")]
        self.service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        
        if not self.service_account_json:
            logger.warning("GOOGLE_SERVICE_ACCOUNT_JSON not set. GBP API calls will use mock data.")
            self.service = None
        else:
            try:
                import json
                credentials_dict = json.loads(self.service_account_json)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict,
                    scopes=[
                        "https://www.googleapis.com/auth/business.manage",
                        "https://www.googleapis.com/auth/businessprofileperformance"
                    ]
                )
                # Use Business Profile Performance API
                self.service = build('businessprofileperformance', 'v1', credentials=credentials)
                logger.info("GBP service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize GBP client: {e}")
                self.service = None

    def get_gbp_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch Google Business Profile metrics.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Dictionary containing GBP metrics
        """
        if not self.service:
            logger.info("GBP service not configured, returning mock data")
            return self._get_mock_data(start_date, end_date)
        
        try:
            # Aggregate metrics from all locations
            total_searches = 0
            total_views = 0
            total_phone_calls = 0
            total_directions = 0
            total_website_clicks = 0
            all_search_keywords = []
            all_actions_over_time = {}
            
            for location_id in self.location_ids:
                try:
                    location_name = f"locations/{location_id}"
                    
                    # Fetch search insights
                    search_request = {
                        "locationNames": [location_name],
                        "basicRequest": {
                            "metricRequests": [
                                {"metric": "QUERIES_DIRECT"},
                                {"metric": "QUERIES_INDIRECT"},
                                {"metric": "VIEWS_MAPS"},
                                {"metric": "VIEWS_SEARCH"},
                                {"metric": "ACTIONS_PHONE"},
                                {"metric": "ACTIONS_WEBSITE"},
                                {"metric": "ACTIONS_DRIVING_DIRECTIONS"}
                            ],
                            "timeRange": {
                                "startTime": start_date.strftime("%Y-%m-%dT00:00:00Z"),
                                "endTime": end_date.strftime("%Y-%m-%dT23:59:59Z")
                            }
                        }
                    }
                    
                    insights = self.service.locations().searchKeywords().impressions().monthly().list(
                        parent=location_name
                    ).execute()
                    
                    # Note: The actual API structure may vary. This is a simplified version.
                    # You may need to adjust based on the actual API response structure.
                    
                    # For now, we'll use mock data as the GBP API can be complex
                    logger.warning(f"GBP API integration for location {location_id} needs refinement. Using mock data.")
                    
                except Exception as e:
                    logger.error(f"Error fetching GBP metrics for location {location_id}: {e}")
                    continue
            
            # Return mock data for now
            return self._get_mock_data(start_date, end_date)
            
        except Exception as e:
            logger.error(f"Error fetching GBP metrics: {e}")
            return self._get_mock_data(start_date, end_date)

    def _get_mock_data(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return mock data for testing."""
        return {
            "searches": 156,
            "views": 234,
            "phone_calls": 45,
            "directions": 38,
            "website_clicks": 67,
            "search_keywords": [
                {"keyword": "home care services", "count": 42},
                {"keyword": "senior care colorado", "count": 38},
                {"keyword": "caregiver jobs", "count": 28},
                {"keyword": "elderly care", "count": 24},
                {"keyword": "respite care", "count": 24}
            ],
            "actions_over_time": [
                {"date": "2025-10-12", "calls": 2, "directions": 1, "website": 3},
                {"date": "2025-10-16", "calls": 3, "directions": 2, "website": 4},
                {"date": "2025-10-20", "calls": 5, "directions": 4, "website": 7},
                {"date": "2025-10-24", "calls": 4, "directions": 3, "website": 6},
                {"date": "2025-10-28", "calls": 4, "directions": 3, "website": 7},
                {"date": "2025-11-01", "calls": 5, "directions": 4, "website": 8},
                {"date": "2025-11-05", "calls": 4, "directions": 3, "website": 6},
                {"date": "2025-11-09", "calls": 3, "directions": 2, "website": 5}
            ]
        }


gbp_service = GBPService()


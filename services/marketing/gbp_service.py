import os
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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
                        "https://www.googleapis.com/auth/business.manage"
                    ]
                )
                # Use My Business Business Information API v1
                self.service = build('mybusinessbusinessinformation', 'v1', credentials=credentials)
                # Also initialize the Account Management API to get accounts
                self.account_service = build('mybusinessaccountmanagement', 'v1', credentials=credentials)
                logger.info("GBP service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize GBP client: {e}")
                self.service = None
                self.account_service = None

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
            logger.warning("GBP service not configured, returning mock data")
            return self._get_mock_data(start_date, end_date)
        
        logger.info(f"Fetching GBP metrics for locations {self.location_ids} from {start_date} to {end_date}")
        
        try:
            # Aggregate metrics from all locations
            total_searches = 0
            total_views = 0
            total_phone_calls = 0
            total_directions = 0
            total_website_clicks = 0
            all_search_keywords = {}
            actions_by_date = {}
            
            for location_id in self.location_ids:
                try:
                    location_name = f"locations/{location_id}"
                    
                    # Try to get location info first to verify access
                    try:
                        location_info = self.service.locations().get(name=location_name).execute()
                        logger.info(f"Successfully accessed location: {location_info.get('title', location_id)}")
                    except HttpError as e:
                        if e.resp.status == 403:
                            logger.error(f"Access denied to location {location_id}. Service account may not have permission.")
                        elif e.resp.status == 404:
                            logger.error(f"Location {location_id} not found. Check if the ID is correct.")
                        else:
                            logger.error(f"Error accessing location {location_id}: {e}")
                        continue
                    
                    # Note: The Business Profile Performance API (for metrics like views, searches, actions)
                    # requires a separate API and has limited availability. It's primarily available through
                    # the Google Business Profile dashboard or requires special access.
                    
                    # For now, we'll use mock data with a note that real metrics require
                    # either the Performance API (limited access) or Google Analytics integration
                    logger.warning(f"GBP Performance metrics require special API access. Using mock data for location {location_id}.")
                    
                except Exception as e:
                    logger.error(f"Error fetching GBP metrics for location {location_id}: {e}")
                    continue
            
            # Return mock data with a note
            logger.info("GBP API accessed successfully, but performance metrics require additional setup. Returning mock data.")
            return self._get_mock_data(start_date, end_date)
            
        except Exception as e:
            logger.error(f"Error fetching GBP metrics: {e}")
            return self._get_mock_data(start_date, end_date)

    def get_location_info(self) -> List[Dict[str, Any]]:
        """
        Get basic information about the configured locations.
        
        Returns:
            List of location information dictionaries
        """
        if not self.service:
            return []
        
        locations = []
        for location_id in self.location_ids:
            try:
                location_name = f"locations/{location_id}"
                location_info = self.service.locations().get(name=location_name).execute()
                locations.append({
                    "id": location_id,
                    "name": location_info.get("title", "Unknown"),
                    "address": location_info.get("storefrontAddress", {}),
                    "phone": location_info.get("phoneNumbers", {}).get("primaryPhone", ""),
                    "website": location_info.get("websiteUri", "")
                })
            except Exception as e:
                logger.error(f"Error getting info for location {location_id}: {e}")
                continue
        
        return locations

    def _get_mock_data(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return empty data when GBP is not configured - NO FAKE DATA."""
        return {
            "searches": 0,
            "views": 0,
            "phone_calls": 0,
            "directions": 0,
            "website_clicks": 0,
            "search_keywords": [],
            "actions_over_time": [],
            "not_configured": True,
            "message": "Google Business Profile not connected. Add service account to your GBP location for real data."
        }


gbp_service = GBPService()

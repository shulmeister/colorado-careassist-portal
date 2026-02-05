"""
Google Business Profile Performance API integration.
Supports both Service Account and OAuth 2.0 authentication.
Service Account is preferred if GOOGLE_SERVICE_ACCOUNT_JSON is set.
"""
import os
import json
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)

# Service Account Configuration (preferred)
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

# OAuth 2.0 Configuration (fallback)
GBP_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
GBP_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
GBP_REDIRECT_URI = os.getenv("GBP_REDIRECT_URI", "https://portal.coloradocareassist.com/api/gbp/callback")

# Stored OAuth tokens (in production, store in database)
GBP_ACCESS_TOKEN = os.getenv("GBP_ACCESS_TOKEN")
GBP_REFRESH_TOKEN = os.getenv("GBP_REFRESH_TOKEN")

# Location IDs
GBP_LOCATION_IDS = os.getenv("GBP_LOCATION_IDS", "").split(",") if os.getenv("GBP_LOCATION_IDS") else []

# API Base URLs
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GBP_PERFORMANCE_API = "https://businessprofileperformance.googleapis.com/v1"
GBP_ACCOUNT_MGMT_API = "https://mybusinessaccountmanagement.googleapis.com/v1"
GBP_BUSINESS_INFO_API = "https://mybusinessbusinessinformation.googleapis.com/v1"

# Required OAuth/API scopes
OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/business.manage"
]


class GBPService:
    """Google Business Profile service supporting Service Account and OAuth 2.0"""

    def __init__(self):
        self.credentials = None
        self.use_service_account = False
        self.access_token = GBP_ACCESS_TOKEN
        self.refresh_token = GBP_REFRESH_TOKEN
        self.client_id = GBP_CLIENT_ID
        self.client_secret = GBP_CLIENT_SECRET
        self.location_ids = [lid.strip() for lid in GBP_LOCATION_IDS if lid.strip()]

        # Try OAuth first if tokens are available (user-authenticated, has direct GBP access)
        if self.access_token and self.refresh_token:
            logger.info("GBP service initialized with OAuth authentication (user tokens available)")
            self.use_service_account = False
        # Fall back to Service Account if no OAuth tokens
        elif GOOGLE_SERVICE_ACCOUNT_JSON:
            try:
                from google.oauth2 import service_account
                credentials_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
                self.credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict,
                    scopes=OAUTH_SCOPES
                )
                self.use_service_account = True
                logger.info("GBP service initialized with Service Account authentication")
            except Exception as e:
                logger.error(f"Failed to initialize GBP with service account: {e}")
                self.credentials = None
        else:
            if not self.client_id or not self.client_secret:
                logger.warning("GBP OAuth not configured: Missing GOOGLE_OAUTH_CLIENT_ID or GOOGLE_OAUTH_CLIENT_SECRET")

            if not self.access_token:
                logger.warning("GBP not authenticated: No GBP_ACCESS_TOKEN. User needs to complete OAuth flow.")
    
    def get_oauth_url(self, state: str = "gbp_auth") -> str:
        """
        Generate OAuth authorization URL for user to authenticate.
        
        Args:
            state: State parameter for CSRF protection
            
        Returns:
            Authorization URL
        """
        if not self.client_id:
            return ""
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": GBP_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(OAUTH_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state
        }
        
        query_string = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
        return f"{OAUTH_AUTH_URL}?{query_string}"
    
    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            code: Authorization code from OAuth callback
            
        Returns:
            Token response with access_token, refresh_token, expires_in
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": GBP_REDIRECT_URI
        }
        
        response = requests.post(OAUTH_TOKEN_URL, data=data, timeout=30)
        
        if response.status_code == 200:
            tokens = response.json()
            self.access_token = tokens.get("access_token")
            self.refresh_token = tokens.get("refresh_token")
            logger.info("GBP OAuth tokens obtained successfully")
            return {
                "success": True,
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "expires_in": tokens.get("expires_in")
            }
        else:
            logger.error(f"Failed to exchange code for tokens: {response.text}")
            return {"success": False, "error": response.text}
    
    def refresh_access_token(self) -> bool:
        """
        Refresh the access token using the refresh token.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.refresh_token:
            logger.error("Cannot refresh: No refresh token available")
            return False
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token"
        }
        
        response = requests.post(OAUTH_TOKEN_URL, data=data, timeout=30)
        
        if response.status_code == 200:
            tokens = response.json()
            self.access_token = tokens.get("access_token")
            logger.info("GBP access token refreshed successfully")
            return True
        else:
            logger.error(f"Failed to refresh token: {response.text}")
            return False
    
    def _get_access_token(self) -> Optional[str]:
        """Get a valid access token from service account or OAuth."""
        if self.use_service_account and self.credentials:
            try:
                # Refresh credentials if needed
                if not self.credentials.valid:
                    from google.auth.transport.requests import Request
                    self.credentials.refresh(Request())
                return self.credentials.token
            except Exception as e:
                logger.error(f"Failed to get service account token: {e}")
                return None
        else:
            return self.access_token

    def _make_api_request(self, url: str, method: str = "GET", retry: bool = True) -> Optional[Dict]:
        """
        Make an authenticated API request.

        Args:
            url: API endpoint URL
            method: HTTP method
            retry: Whether to retry with token refresh on 401

        Returns:
            Response JSON or None
        """
        access_token = self._get_access_token()
        if not access_token:
            logger.error("No access token available")
            return None

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            else:
                response = requests.request(method, url, headers=headers, timeout=30)

            if response.status_code == 401 and retry:
                # Token expired, try to refresh
                if self.use_service_account:
                    # Force refresh service account credentials
                    self.credentials = None
                    if GOOGLE_SERVICE_ACCOUNT_JSON:
                        from google.oauth2 import service_account
                        credentials_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
                        self.credentials = service_account.Credentials.from_service_account_info(
                            credentials_dict,
                            scopes=OAUTH_SCOPES
                        )
                    return self._make_api_request(url, method, retry=False)
                elif self.refresh_access_token():
                    return self._make_api_request(url, method, retry=False)
                return None

            if response.status_code == 403:
                logger.error(f"Permission denied for {url}. Service account may need to be added to GBP. Response: {response.text}")
                return None

            if response.status_code == 400:
                logger.error(f"Bad Request for {url}. Response: {response.text}")
                return None

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
    
    def get_accounts(self) -> List[Dict[str, Any]]:
        """
        Get list of GBP accounts the user has access to.
        
        Returns:
            List of account dictionaries
        """
        url = f"{GBP_ACCOUNT_MGMT_API}/accounts"
        data = self._make_api_request(url)
        
        if data and "accounts" in data:
            return data["accounts"]
        return []
    
    def get_locations(self, account_name: str = None) -> List[Dict[str, Any]]:
        """
        Get list of locations for an account.

        Args:
            account_name: Account resource name (e.g., "accounts/123456789")

        Returns:
            List of location dictionaries
        """
        if not account_name:
            # Try to get a LOCATION_GROUP account first (these have business locations)
            accounts = self.get_accounts()
            location_group_accounts = [a for a in accounts if a.get("type") == "LOCATION_GROUP"]
            if location_group_accounts:
                account_name = location_group_accounts[0].get("name")
                logger.info(f"Using LOCATION_GROUP account: {account_name}")
            elif accounts:
                account_name = accounts[0].get("name")
            else:
                return []

        # The Business Information API requires a readMask parameter
        url = f"{GBP_BUSINESS_INFO_API}/{account_name}/locations?readMask=name,title,storefrontAddress,phoneNumbers,websiteUri"
        data = self._make_api_request(url)
        
        if data and "locations" in data:
            locations = data["locations"]
            logger.info(f"Found {len(locations)} locations for account {account_name}")
            return locations
        elif data:
            logger.warning(f"Unexpected response format from locations API: {data}")
        else:
            logger.warning(f"No data returned from locations API for {account_name}")
        return []
    
    def get_daily_metrics(self, location_name: str, metric: str, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Get daily metrics for a location using Business Profile Performance API.
        
        Args:
            location_name: Location resource name (e.g., "locations/123456789")
            metric: Metric to fetch (e.g., "WEBSITE_CLICKS", "CALL_CLICKS", etc.)
            start_date: Start date
            end_date: End date
            
        Returns:
            Metrics data
        """
        # Build the API URL
        url = (
            f"{GBP_PERFORMANCE_API}/{location_name}:getDailyMetricsTimeSeries"
            f"?dailyMetric={metric}"
            f"&dailyRange.startDate.year={start_date.year}"
            f"&dailyRange.startDate.month={start_date.month}"
            f"&dailyRange.startDate.day={start_date.day}"
            f"&dailyRange.endDate.year={end_date.year}"
            f"&dailyRange.endDate.month={end_date.month}"
            f"&dailyRange.endDate.day={end_date.day}"
        )
        
        return self._make_api_request(url) or {}
    
    def get_reviews(self, location_name: str) -> Dict[str, Any]:
        """
        Get reviews for a location.
        
        Args:
            location_name: Location resource name (e.g., "locations/123456789")
            
        Returns:
            Review metrics including count, average rating, and recent reviews
        """
        url = f"{GBP_BUSINESS_INFO_API}/{location_name}/reviews"
        data = self._make_api_request(url)
        
        if not data:
            return {
                "total_reviews": 0,
                "average_rating": 0,
                "rating_distribution": {},
                "recent_reviews": []
            }
        
        reviews = data.get("reviews", [])
        total_reviews = len(reviews)
        
        if total_reviews == 0:
            return {
                "total_reviews": 0,
                "average_rating": 0,
                "rating_distribution": {},
                "recent_reviews": []
            }
        
        # Calculate average rating
        ratings = [review.get("starRating", {}).get("rating", 0) for review in reviews if review.get("starRating")]
        average_rating = sum(ratings) / len(ratings) if ratings else 0
        
        # Rating distribution
        rating_distribution = {}
        for rating in ratings:
            rating_distribution[rating] = rating_distribution.get(rating, 0) + 1
        
        # Get recent reviews (last 10)
        recent_reviews = []
        for review in reviews[:10]:
            recent_reviews.append({
                "author": review.get("reviewer", {}).get("displayName", "Anonymous"),
                "rating": review.get("starRating", {}).get("rating", 0),
                "comment": review.get("comment", ""),
                "create_time": review.get("createTime", ""),
            })
        
        return {
            "total_reviews": total_reviews,
            "average_rating": round(average_rating, 1),
            "rating_distribution": rating_distribution,
            "recent_reviews": recent_reviews
        }
    
    def get_search_keywords(self, location_name: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Get search keywords that led to business discovery.
        
        Note: This may require additional API permissions or may not be available
        in all GBP API versions. Returns empty list if not available.
        
        Args:
            location_name: Location resource name
            start_date: Start date
            end_date: End date
            
        Returns:
            List of search keywords with impression counts
        """
        # Note: Search keywords may not be directly available in GBP Performance API
        # This is a placeholder implementation - actual endpoint may differ
        url = (
            f"{GBP_PERFORMANCE_API}/{location_name}:getSearchKeywordImpressions"
            f"?startDate.year={start_date.year}"
            f"&startDate.month={start_date.month}"
            f"&startDate.day={start_date.day}"
            f"&endDate.year={end_date.year}"
            f"&endDate.month={end_date.month}"
            f"&endDate.day={end_date.day}"
        )
        
        data = self._make_api_request(url)
        
        if data and "searchKeywordImpressions" in data:
            keywords = []
            for keyword_data in data.get("searchKeywordImpressions", []):
                keywords.append({
                    "keyword": keyword_data.get("keyword", ""),
                    "impressions": keyword_data.get("impressions", 0),
                })
            return sorted(keywords, key=lambda x: x["impressions"], reverse=True)
        
        # If endpoint not available, return empty list
        return []

    def get_gbp_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch all GBP metrics for configured locations.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Aggregated GBP metrics
        """
        # Check if authentication is configured
        if self.use_service_account:
            if not self.credentials:
                return self._get_not_configured_data("Service account credentials failed to initialize. Check GOOGLE_SERVICE_ACCOUNT_JSON.")
        else:
            if not self.access_token:
                return self._get_not_configured_data("GBP not authenticated. Complete OAuth flow to connect.")

            if not self.client_id or not self.client_secret:
                return self._get_not_configured_data("GBP OAuth not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET.")
        
        logger.info(f"Fetching GBP metrics from {start_date} to {end_date}")
        
        # Get locations if not configured
        location_names = []
        if self.location_ids:
            location_names = [f"locations/{lid}" for lid in self.location_ids]
        else:
            # Try to discover locations from accounts
            accounts = self.get_accounts()
            for account in accounts:
                locations = self.get_locations(account.get("name"))
                for loc in locations:
                    location_names.append(loc.get("name"))
        
        if not location_names:
            return self._get_not_configured_data("No GBP locations found. Check account permissions.")
        
        # Metrics to fetch - Core actions (always available)
        core_metrics = [
            "WEBSITE_CLICKS",
            "CALL_CLICKS", 
            "BUSINESS_DIRECTION_REQUESTS",
            "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
            "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
            "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
            "BUSINESS_IMPRESSIONS_MOBILE_SEARCH"
        ]
        
        # Additional insights (may not be available in all API versions)
        # These will be tried but errors will be logged if unavailable
        additional_metrics = [
            # Search query types (direct vs indirect discovery)
            "QUERIES_DIRECT",
            "QUERIES_INDIRECT", 
            "QUERIES_CHAIN",
            # Photo engagement
            "PHOTOS_VIEWS_MERCHANT",
            "PHOTOS_VIEWS_CUSTOMER",
            "PHOTOS_COUNT_MERCHANT",
            "PHOTOS_COUNT_CUSTOMER",
            # Post engagement (if using GBP posts)
            "POST_VIEWS_SEARCH",
            "POST_ENGAGEMENT"
        ]
        
        metrics_to_fetch = core_metrics + additional_metrics
        
        # Aggregate metrics from all locations
        totals = {
            "website_clicks": 0,
            "phone_calls": 0,
            "directions": 0,
            "views": 0,
            "searches": 0,
            # Search query types
            "queries_direct": 0,
            "queries_indirect": 0,
            "queries_chain": 0,
            # Photo engagement
            "photo_views_merchant": 0,
            "photo_views_customer": 0,
            "photo_count_merchant": 0,
            "photo_count_customer": 0,
            # Post engagement
            "post_views": 0,
            "post_engagement": 0,
            # Platform breakdown
            "views_search": 0,
            "views_maps": 0
        }
        actions_over_time = {}
        
        for location_name in location_names:
            for metric in metrics_to_fetch:
                try:
                    data = self.get_daily_metrics(location_name, metric, start_date, end_date)
                    
                    if "timeSeries" in data:
                        time_series = data["timeSeries"]
                        daily_metrics = time_series.get("datedValues", [])
                        
                        for entry in daily_metrics:
                            date_obj = entry.get("date", {})
                            date_str = f"{date_obj.get('year')}-{date_obj.get('month'):02d}-{date_obj.get('day'):02d}"
                            value = int(entry.get("value", 0))
                            
                            # Aggregate by metric type
                            if metric == "WEBSITE_CLICKS":
                                totals["website_clicks"] += value
                            elif metric == "CALL_CLICKS":
                                totals["phone_calls"] += value
                            elif metric == "BUSINESS_DIRECTION_REQUESTS":
                                totals["directions"] += value
                            elif metric in ["BUSINESS_IMPRESSIONS_DESKTOP_MAPS", "BUSINESS_IMPRESSIONS_MOBILE_MAPS"]:
                                totals["views"] += value
                                totals["views_maps"] += value
                            elif metric in ["BUSINESS_IMPRESSIONS_DESKTOP_SEARCH", "BUSINESS_IMPRESSIONS_MOBILE_SEARCH"]:
                                totals["searches"] += value
                                totals["views_search"] += value
                            # Search query types
                            elif metric == "QUERIES_DIRECT":
                                totals["queries_direct"] += value
                            elif metric == "QUERIES_INDIRECT":
                                totals["queries_indirect"] += value
                            elif metric == "QUERIES_CHAIN":
                                totals["queries_chain"] += value
                            # Photo engagement
                            elif metric == "PHOTOS_VIEWS_MERCHANT":
                                totals["photo_views_merchant"] += value
                            elif metric == "PHOTOS_VIEWS_CUSTOMER":
                                totals["photo_views_customer"] += value
                            elif metric == "PHOTOS_COUNT_MERCHANT":
                                totals["photo_count_merchant"] = max(totals["photo_count_merchant"], value)  # Use max, not sum
                            elif metric == "PHOTOS_COUNT_CUSTOMER":
                                totals["photo_count_customer"] = max(totals["photo_count_customer"], value)  # Use max, not sum
                            # Post engagement
                            elif metric == "POST_VIEWS_SEARCH":
                                totals["post_views"] += value
                            elif metric == "POST_ENGAGEMENT":
                                totals["post_engagement"] += value
                            
                            # Track over time for charts
                            if date_str not in actions_over_time:
                                actions_over_time[date_str] = {"date": date_str, "website": 0, "calls": 0, "directions": 0}
                            
                            if metric == "WEBSITE_CLICKS":
                                actions_over_time[date_str]["website"] += value
                            elif metric == "CALL_CLICKS":
                                actions_over_time[date_str]["calls"] += value
                            elif metric == "BUSINESS_DIRECTION_REQUESTS":
                                actions_over_time[date_str]["directions"] += value
                                
                except Exception as e:
                    logger.warning(f"Error fetching {metric} for {location_name}: {e}")
                    continue
        
        # Sort actions over time
        sorted_actions = sorted(actions_over_time.values(), key=lambda x: x["date"])
        
        # Get reviews and search keywords from first location (or aggregate if multiple)
        reviews_data = {}
        all_search_keywords = []
        
        if location_names:
            # Get reviews from first location (or aggregate if needed)
            reviews_data = self.get_reviews(location_names[0])
            
            # Aggregate search keywords from all locations
            for location_name in location_names:
                keywords = self.get_search_keywords(location_name, start_date, end_date)
                all_search_keywords.extend(keywords)
            
            # Deduplicate and aggregate keywords
            keyword_dict = {}
            for kw in all_search_keywords:
                keyword = kw.get("keyword", "")
                if keyword:
                    keyword_dict[keyword] = keyword_dict.get(keyword, 0) + kw.get("impressions", 0)
            
            # Convert back to list and sort
            all_search_keywords = [
                {"keyword": k, "impressions": v}
                for k, v in sorted(keyword_dict.items(), key=lambda x: x[1], reverse=True)
            ][:20]  # Top 20 keywords
        
        # Calculate derived insights
        total_queries = totals["queries_direct"] + totals["queries_indirect"] + totals["queries_chain"]
        query_breakdown = {
            "direct": totals["queries_direct"],
            "indirect": totals["queries_indirect"],
            "chain": totals["queries_chain"],
            "direct_percentage": (totals["queries_direct"] / total_queries * 100) if total_queries > 0 else 0,
            "indirect_percentage": (totals["queries_indirect"] / total_queries * 100) if total_queries > 0 else 0
        }
        
        total_photo_views = totals["photo_views_merchant"] + totals["photo_views_customer"]
        photo_engagement = {
            "merchant_views": totals["photo_views_merchant"],
            "customer_views": totals["photo_views_customer"],
            "merchant_photo_count": totals["photo_count_merchant"],
            "customer_photo_count": totals["photo_count_customer"],
            "total_views": total_photo_views,
            "views_per_photo": total_photo_views / max(totals["photo_count_merchant"] + totals["photo_count_customer"], 1)
        }
        
        logger.info(f"GBP metrics: {totals['phone_calls']} calls, {totals['website_clicks']} clicks, {totals['directions']} directions, {total_queries} queries")
        
        return {
            "searches": totals["searches"],
            "views": totals["views"],
            "views_search": totals["views_search"],
            "views_maps": totals["views_maps"],
            "phone_calls": totals["phone_calls"],
            "directions": totals["directions"],
            "website_clicks": totals["website_clicks"],
            "actions_over_time": sorted_actions,
            "reviews": reviews_data,
            "search_keywords": all_search_keywords,
            # New insights
            "search_query_types": query_breakdown,
            "photo_engagement": photo_engagement,
            "post_engagement": {
                "post_views": totals["post_views"],
                "post_engagement": totals["post_engagement"]
            },
            "is_placeholder": False,
            "source": "gbp_performance_api",
            "locations_count": len(location_names)
        }
    
    def _get_not_configured_data(self, message: str) -> Dict[str, Any]:
        """Return zero data when GBP is not configured."""
        return {
            "searches": 0,
            "views": 0,
            "phone_calls": 0,
            "directions": 0,
            "website_clicks": 0,
            "reviews": {
                "total_reviews": 0,
                "average_rating": 0,
                "rating_distribution": {},
                "recent_reviews": []
            },
            "search_keywords": [],
            "actions_over_time": [],
            "is_placeholder": True,
            "not_configured": True,
            "message": message,
            "oauth_url": self.get_oauth_url() if self.client_id else None
        }


# Singleton instance
gbp_service = GBPService()

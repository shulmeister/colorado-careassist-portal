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

# Simple in-memory cache for script data (in production, use Redis or database)
_script_data_cache: Optional[Dict[str, Any]] = None
_cache_timestamp: Optional[datetime] = None

# Singleton instance
_google_ads_service_instance: Optional['GoogleAdsService'] = None


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
            # First, try to get the correct customer ID if we're using a Manager Account
            actual_customer_id = self._get_actual_customer_id(client)
            if not actual_customer_id:
                logger.warning("Could not determine actual customer ID, using configured ID")
                actual_customer_id = self.customer_id
            else:
                logger.info(f"Using customer ID: {actual_customer_id}")
            
            ga_service = client.get_service("GoogleAdsService")

            daily, currency_code = self._fetch_daily_breakdown(ga_service, start_str, end_str, actual_customer_id)
            if not daily:
                logger.warning("Google Ads daily breakdown returned no rows")
                return self._get_placeholder_metrics(start_date, end_date)

            overview = self._build_overview_from_daily(daily, start_date, end_date)
            campaigns = self._fetch_campaigns(ga_service, start_str, end_str, actual_customer_id)
            quality_scores = self._fetch_quality_scores(ga_service, start_str, end_str, actual_customer_id)
            search_terms = self._fetch_search_terms(ga_service, start_str, end_str, actual_customer_id)
            device_performance = self._fetch_device_performance(ga_service, start_str, end_str, actual_customer_id)

            overview["spend"]["daily"] = daily
            overview["campaigns"] = campaigns
            overview["quality_scores"] = quality_scores
            overview["search_terms"] = search_terms
            overview["device_performance"] = device_performance
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
    
    def cache_script_data(self, data: Dict[str, Any]) -> None:
        """Cache data received from Google Ads Script webhook."""
        global _script_data_cache, _cache_timestamp
        _script_data_cache = data
        _cache_timestamp = datetime.utcnow()
        logger.info("Google Ads Script data cached")
    
    def get_cached_script_data(self, start_date: date, end_date: date) -> Optional[Dict[str, Any]]:
        """
        Get cached data from Google Ads Script if available and recent (within 24 hours).
        
        Transforms script data format to match API format for compatibility.
        """
        global _script_data_cache, _cache_timestamp
        
        if not _script_data_cache or not _cache_timestamp:
            return None
        
        # Check if cache is recent (within 24 hours)
        cache_age = datetime.utcnow() - _cache_timestamp
        if cache_age.total_seconds() > 24 * 3600:
            logger.info("Google Ads Script cache expired")
            return None
        
        try:
            # Transform script data format to API format
            script_data = _script_data_cache
            
            # Check if date range matches (roughly)
            cache_range = script_data.get("date_range", {})
            cache_start = datetime.fromisoformat(cache_range.get("start", "")).date() if cache_range.get("start") else None
            cache_end = datetime.fromisoformat(cache_range.get("end", "")).date() if cache_range.get("end") else None
            
            # Use cached data if date range overlaps or is close
            if cache_start and cache_end:
                if start_date > cache_end or end_date < cache_start:
                    logger.info("Google Ads Script cache date range doesn't match request")
                    return None
            
            account = script_data.get("account", {})
            campaigns = script_data.get("campaigns", [])
            quality_scores = script_data.get("quality_scores", {})
            search_terms = script_data.get("search_terms", [])
            device_performance = script_data.get("device_performance", {})
            daily = script_data.get("daily_breakdown", [])
            
            # Build overview in API format
            overview = {
                "spend": {
                    "total": account.get("spend", 0),
                    "per_day": account.get("spend", 0) / max((end_date - start_date).days, 1),
                    "daily": daily
                },
                "performance": {
                    "clicks": account.get("clicks", 0),
                    "impressions": account.get("impressions", 0),
                    "conversions": account.get("conversions", 0),
                    "conversion_value": account.get("conversion_value", 0)
                },
                "efficiency": {
                    "ctr": account.get("ctr", 0),
                    "cpc": account.get("cpc", 0),
                    "roas": account.get("roas", 0),
                    "cost_per_conversion": account.get("cost_per_conversion", 0),
                    "conversion_rate": account.get("conversion_rate", 0)
                },
                "campaigns": campaigns,
                "quality_scores": quality_scores,
                "search_terms": search_terms,
                "device_performance": device_performance,
                "currency_code": script_data.get("currency_code", "USD"),
                "is_placeholder": False,
                "source": "google_ads_script",
                "fetched_at": script_data.get("fetched_at", datetime.utcnow().isoformat())
            }
            
            logger.info("Returning cached Google Ads Script data")
            return overview
            
        except Exception as e:
            logger.error(f"Error processing cached script data: {e}")
            return None

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

    def _get_actual_customer_id(self, client) -> Optional[str]:
        """
        If using a Manager Account, list accessible accounts and use the first one.
        Otherwise, return the configured customer_id.
        """
        # If we have a login_customer_id, we're using a Manager Account
        # In that case, we need to list accessible customers to get the actual account ID
        if self.login_customer_id:
            try:
                # List accessible accounts from Manager Account
                customer_service = client.get_service("CustomerService")
                accessible_customers = customer_service.list_accessible_customers()
                
                if accessible_customers.resource_names:
                    # Get the first accessible account ID (remove 'customers/' prefix and dashes)
                    first_account = accessible_customers.resource_names[0]
                    account_id = first_account.replace('customers/', '').replace('-', '')
                    logger.info(f"Found accessible account from Manager Account: {account_id}")
                    return account_id
            except Exception as e:
                logger.warning(f"Could not list accessible customers: {e}")
        
        # If no login_customer_id, check if customer_id is actually a Manager Account ID
        # Manager Account IDs are typically 16 digits, regular accounts are 10 digits
        if self.customer_id and len(self.customer_id) == 16:
            logger.info(f"Customer ID {self.customer_id} appears to be a Manager Account ID. Using it as login_customer_id and listing accessible accounts.")
            # Use customer_id as login_customer_id and rebuild client
            try:
                original_login = self.login_customer_id
                self.login_customer_id = self.customer_id
                
                # Rebuild client with login_customer_id
                new_client = self._build_client()
                if new_client:
                    customer_service = new_client.get_service("CustomerService")
                    accessible_customers = customer_service.list_accessible_customers()
                    
                    if accessible_customers.resource_names:
                        first_account = accessible_customers.resource_names[0]
                        account_id = first_account.replace('customers/', '').replace('-', '')
                        logger.info(f"Found accessible account: {account_id}")
                        # Keep login_customer_id set
                        return account_id
                    else:
                        logger.warning("No accessible accounts found")
                        self.login_customer_id = original_login
                else:
                    self.login_customer_id = original_login
            except Exception as e:
                logger.error(f"Could not list accounts using customer_id as Manager Account: {e}")
                if 'original_login' in locals():
                    self.login_customer_id = original_login
        
        # Fallback to configured customer_id (might be a regular 10-digit account ID)
        return self.customer_id
    
    def _fetch_daily_breakdown(self, ga_service, start: str, end: str, customer_id: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        if not customer_id:
            customer_id = self.customer_id
        # Query from customer_performance_view to get date-segmented metrics at account level
        # Include all important search KPIs
        query = f"""
            SELECT
              customer.currency_code,
              segments.date,
              metrics.cost_micros,
              metrics.clicks,
              metrics.impressions,
              metrics.conversions,
              metrics.conversions_value,
              metrics.ctr,
              metrics.average_cpc,
              metrics.conversion_rate,
              metrics.search_impression_share,
              metrics.search_rank_lost_impression_share,
              metrics.search_budget_lost_impression_share
            FROM customer_performance_view
            WHERE segments.date BETWEEN '{start}' AND '{end}'
            ORDER BY segments.date
        """

        breakdown: List[Dict[str, Any]] = []
        currency_code: Optional[str] = None
        
        try:
            # Try search_stream first (preferred for large datasets)
            response = ga_service.search_stream(customer_id=customer_id, query=query)
            response_type = 'stream'
        except Exception as e:
            logger.warning(f"search_stream failed, trying search: {e}")
            try:
                # Fallback to search method
                response = ga_service.search(customer_id=customer_id, query=query)
                response_type = 'search'
            except Exception as e2:
                logger.error(f"Both search_stream and search failed: {e2}")
                # Try alternative query from campaign
                query_alt = f"""
                    SELECT
                      customer.currency_code,
                      segments.date,
                      metrics.cost_micros,
                      metrics.clicks,
                      metrics.impressions,
                      metrics.conversions,
                      metrics.conversions_value
                    FROM campaign
                    WHERE segments.date BETWEEN '{start}' AND '{end}'
                    ORDER BY segments.date
                """
                try:
                    response = ga_service.search(customer_id=customer_id, query=query_alt)
                    response_type = 'search'
                except Exception as e3:
                    logger.error(f"Alternative query also failed: {e3}")
                    return [], None

        # Handle both search_stream (iterable) and search (single response) formats
        if response_type == 'stream':
            for batch in response:
                for row in batch.results:
                    if not currency_code:
                        currency_code = getattr(row.customer, "currency_code", None)
                    spend = self._micros_to_currency(getattr(row.metrics, "cost_micros", 0))
                    clicks = self._safe_int(getattr(row.metrics, "clicks", 0))
                    impressions = self._safe_int(getattr(row.metrics, "impressions", 0))
                    conversions = self._safe_float(getattr(row.metrics, "conversions", 0.0))
                    conversion_value = self._safe_float(getattr(row.metrics, "conversions_value", 0.0))

                    breakdown.append({
                        "date": row.segments.date,
                        "spend": round(spend, 2),
                        "clicks": clicks,
                        "impressions": impressions,
                        "conversions": conversions,
                        "conversion_value": round(conversion_value, 2),
                        "roas": round(self._safe_divide(conversion_value, spend), 2),
                        "cost_per_conversion": round(self._safe_divide(spend, conversions), 2),
                    })
        else:
            # search method returns results directly
            for row in response.results:
                if not currency_code:
                    currency_code = getattr(row.customer, "currency_code", None)
                spend = self._micros_to_currency(getattr(row.metrics, "cost_micros", 0))
                clicks = self._safe_int(getattr(row.metrics, "clicks", 0))
                impressions = self._safe_int(getattr(row.metrics, "impressions", 0))
                conversions = self._safe_float(getattr(row.metrics, "conversions", 0.0))
                conversion_value = self._safe_float(getattr(row.metrics, "conversions_value", 0.0))
                ctr = self._safe_float(getattr(row.metrics, "ctr", 0.0))
                avg_cpc = self._safe_float(getattr(row.metrics, "average_cpc", 0.0))
                conversion_rate = self._safe_float(getattr(row.metrics, "conversion_rate", 0.0))
                search_impression_share = self._safe_float(getattr(row.metrics, "search_impression_share", 0.0))
                search_rank_lost_is = self._safe_float(getattr(row.metrics, "search_rank_lost_impression_share", 0.0))
                search_budget_lost_is = self._safe_float(getattr(row.metrics, "search_budget_lost_impression_share", 0.0))

                breakdown.append({
                    "date": row.segments.date,
                    "spend": round(spend, 2),
                    "clicks": clicks,
                    "impressions": impressions,
                    "conversions": conversions,
                    "conversion_value": round(conversion_value, 2),
                    "roas": round(self._safe_divide(conversion_value, spend), 2),
                    "cost_per_conversion": round(self._safe_divide(spend, conversions), 2),
                    "ctr": round(ctr * 100, 2),
                    "cpc": round(avg_cpc, 2) if avg_cpc > 0 else round(self._safe_divide(spend, clicks), 2),
                    "conversion_rate": round(conversion_rate * 100, 2),
                    "search_impression_share": round(search_impression_share * 100, 2),
                    "search_rank_lost_is": round(search_rank_lost_is * 100, 2),
                    "search_budget_lost_is": round(search_budget_lost_is * 100, 2),
                })

        return breakdown, currency_code

    def _fetch_quality_scores(self, ga_service, start: str, end: str, customer_id: Optional[str] = None) -> Dict[str, Any]:
        if not customer_id:
            customer_id = self.customer_id
        """
        Fetch Quality Score metrics for the account.
        
        Returns average quality score and breakdown by component.
        """
        query = f"""
            SELECT
              campaign.advertising_channel_type,
              ad_group_criterion.quality_info.quality_score,
              ad_group_criterion.quality_info.creative_quality_score,
              ad_group_criterion.quality_info.post_click_quality_score,
              ad_group_criterion.quality_info.search_predicted_ctr,
              ad_group_criterion.quality_info.landing_page_experience_score
            FROM keyword_view
            WHERE segments.date BETWEEN '{start}' AND '{end}'
              AND ad_group_criterion.quality_info.quality_score IS NOT NULL
            LIMIT 1000
        """
        
        quality_scores = []
        creative_scores = []
        landing_page_scores = []
        ctr_scores = []
        
        try:
            response = ga_service.search_stream(customer_id=customer_id, query=query)
            
            for batch in response:
                for row in batch.results:
                    quality_info = getattr(row.ad_group_criterion, "quality_info", None)
                    if quality_info:
                        qs = getattr(quality_info, "quality_score", None)
                        if qs:
                            quality_scores.append(int(qs))
                        
                        creative = getattr(quality_info, "creative_quality_score", None)
                        if creative:
                            creative_scores.append(int(creative))
                        
                        landing = getattr(quality_info, "landing_page_experience_score", None)
                        if landing:
                            landing_page_scores.append(int(landing))
                        
                        ctr = getattr(quality_info, "search_predicted_ctr", None)
                        if ctr:
                            ctr_scores.append(int(ctr))
        except Exception as e:
            logger.warning(f"Could not fetch quality scores: {e}")
            return {}
        
        def avg(lst):
            return round(sum(lst) / len(lst), 2) if lst else 0
        
        return {
            "average_quality_score": avg(quality_scores),
            "average_creative_score": avg(creative_scores),
            "average_landing_page_score": avg(landing_page_scores),
            "average_predicted_ctr": avg(ctr_scores),
            "keywords_analyzed": len(quality_scores)
        }
    
    def _fetch_device_performance(self, ga_service, start: str, end: str, customer_id: Optional[str] = None) -> Dict[str, Any]:
        if not customer_id:
            customer_id = self.customer_id
        """
        Fetch performance metrics broken down by device type.
        
        Returns performance by Desktop, Mobile, Tablet.
        """
        query = f"""
            SELECT
              segments.device,
              metrics.cost_micros,
              metrics.clicks,
              metrics.impressions,
              metrics.conversions,
              metrics.conversions_value
            FROM campaign
            WHERE segments.date BETWEEN '{start}' AND '{end}'
            ORDER BY metrics.cost_micros DESC
        """
        
        device_stats = {
            "DESKTOP": {"spend": 0, "clicks": 0, "impressions": 0, "conversions": 0, "conversion_value": 0},
            "MOBILE": {"spend": 0, "clicks": 0, "impressions": 0, "conversions": 0, "conversion_value": 0},
            "TABLET": {"spend": 0, "clicks": 0, "impressions": 0, "conversions": 0, "conversion_value": 0},
        }
        
        try:
            response = ga_service.search_stream(customer_id=customer_id, query=query)
            
            for batch in response:
                for row in batch.results:
                    device = getattr(row.segments, "device", None)
                    device_name = getattr(device, "name", "UNKNOWN") if device else "UNKNOWN"
                    
                    if device_name in device_stats:
                        spend = self._micros_to_currency(getattr(row.metrics, "cost_micros", 0))
                        clicks = self._safe_int(getattr(row.metrics, "clicks", 0))
                        impressions = self._safe_int(getattr(row.metrics, "impressions", 0))
                        conversions = self._safe_float(getattr(row.metrics, "conversions", 0.0))
                        conversion_value = self._safe_float(getattr(row.metrics, "conversions_value", 0.0))
                        
                        device_stats[device_name]["spend"] += spend
                        device_stats[device_name]["clicks"] += clicks
                        device_stats[device_name]["impressions"] += impressions
                        device_stats[device_name]["conversions"] += conversions
                        device_stats[device_name]["conversion_value"] += conversion_value
        except Exception as e:
            logger.warning(f"Could not fetch device performance: {e}")
            return {}
        
        # Calculate rates and format
        result = {}
        for device, stats in device_stats.items():
            spend = stats["spend"]
            clicks = stats["clicks"]
            impressions = stats["impressions"]
            conversions = stats["conversions"]
            
            result[device.lower()] = {
                "spend": round(spend, 2),
                "clicks": clicks,
                "impressions": impressions,
                "conversions": round(conversions, 2),
                "conversion_value": round(stats["conversion_value"], 2),
                "ctr": round(self._safe_divide(clicks, impressions) * 100, 2),
                "cpc": round(self._safe_divide(spend, clicks), 2),
                "conversion_rate": round(self._safe_divide(conversions, clicks) * 100, 2),
            }
        
        return result

    def _fetch_search_terms(self, ga_service, start: str, end: str, customer_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if not customer_id:
            customer_id = self.customer_id
        """
        Fetch search terms report showing what people actually searched for.
        
        Returns top search terms with spend, clicks, and conversions.
        """
        query = f"""
            SELECT
              search_term_view.search_term,
              metrics.cost_micros,
              metrics.clicks,
              metrics.impressions,
              metrics.conversions,
              metrics.conversions_value
            FROM search_term_view
            WHERE segments.date BETWEEN '{start}' AND '{end}'
              AND search_term_view.search_term IS NOT NULL
            ORDER BY metrics.cost_micros DESC
            LIMIT {limit}
        """
        
        search_terms = []
        
        try:
            response = ga_service.search_stream(customer_id=customer_id, query=query)
            
            for batch in response:
                for row in batch.results:
                    search_term = getattr(row.search_term_view, "search_term", "")
                    if search_term:
                        spend = self._micros_to_currency(getattr(row.metrics, "cost_micros", 0))
                        clicks = self._safe_int(getattr(row.metrics, "clicks", 0))
                        impressions = self._safe_int(getattr(row.metrics, "impressions", 0))
                        conversions = self._safe_float(getattr(row.metrics, "conversions", 0.0))
                        conversion_value = self._safe_float(getattr(row.metrics, "conversions_value", 0.0))
                        
                        search_terms.append({
                            "search_term": search_term,
                            "spend": round(spend, 2),
                            "clicks": clicks,
                            "impressions": impressions,
                            "conversions": conversions,
                            "conversion_value": round(conversion_value, 2),
                            "cpc": round(self._safe_divide(spend, clicks), 2),
                            "ctr": round(self._safe_divide(clicks, impressions) * 100, 2),
                            "cost_per_conversion": round(self._safe_divide(spend, conversions), 2),
                        })
        except Exception as e:
            logger.warning(f"Could not fetch search terms: {e}")
            return []
        
        return search_terms

    def _fetch_campaigns(self, ga_service, start: str, end: str, customer_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if not customer_id:
            customer_id = self.customer_id
        # Fetch only ACTIVE/ENABLED campaigns by default - prioritize active campaigns
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
              metrics.ctr,
              metrics.average_cpc,
              metrics.conversion_rate,
              metrics.search_impression_share,
              metrics.search_rank_lost_impression_share,
              metrics.search_budget_lost_impression_share
            FROM campaign
            WHERE segments.date BETWEEN '{start}' AND '{end}'
              AND campaign.status = 'ENABLED'
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
                avg_cpc = self._safe_float(getattr(row.metrics, "average_cpc", 0.0))
                conversion_rate = self._safe_float(getattr(row.metrics, "conversion_rate", 0.0))
                search_impression_share = self._safe_float(getattr(row.metrics, "search_impression_share", 0.0))
                search_rank_lost_is = self._safe_float(getattr(row.metrics, "search_rank_lost_impression_share", 0.0))
                search_budget_lost_is = self._safe_float(getattr(row.metrics, "search_budget_lost_impression_share", 0.0))

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
                        "cpc": round(self._safe_divide(spend, clicks), 2) if clicks > 0 else round(avg_cpc, 2),
                        "roas": round(self._safe_divide(conversion_value, spend), 2),
                        "cost_per_conversion": round(self._safe_divide(spend, conversions), 2),
                        "conversion_rate": round(conversion_rate * 100, 2),
                        "search_impression_share": round(search_impression_share * 100, 2),
                        "search_rank_lost_is": round(search_rank_lost_is * 100, 2),
                        "search_budget_lost_is": round(search_budget_lost_is * 100, 2),
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
            "search_impression_share": 0.0,
            "search_rank_lost_is": 0.0,
            "search_budget_lost_is": 0.0,
        }
        daily_count = 0

        for entry in daily:
            totals["spend"] += entry.get("spend", 0.0)
            totals["clicks"] += entry.get("clicks", 0)
            totals["impressions"] += entry.get("impressions", 0)
            totals["conversions"] += entry.get("conversions", 0.0)
            totals["conversion_value"] += entry.get("conversion_value", 0.0)
            # Average impression share metrics across days
            if entry.get("search_impression_share") is not None:
                totals["search_impression_share"] += entry.get("search_impression_share", 0.0)
                totals["search_rank_lost_is"] += entry.get("search_rank_lost_is", 0.0)
                totals["search_budget_lost_is"] += entry.get("search_budget_lost_is", 0.0)
                daily_count += 1

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
        
        # Average impression share metrics
        avg_search_is = self._safe_divide(totals["search_impression_share"], daily_count) if daily_count > 0 else 0.0
        avg_rank_lost_is = self._safe_divide(totals["search_rank_lost_is"], daily_count) if daily_count > 0 else 0.0
        avg_budget_lost_is = self._safe_divide(totals["search_budget_lost_is"], daily_count) if daily_count > 0 else 0.0

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
                "search_impression_share": round(avg_search_is, 2),
                "search_rank_lost_impression_share": round(avg_rank_lost_is, 2),
                "search_budget_lost_impression_share": round(avg_budget_lost_is, 2),
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
            "quality_scores": {},
            "search_terms": [],
            "device_performance": {},
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

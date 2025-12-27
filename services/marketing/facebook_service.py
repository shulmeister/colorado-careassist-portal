"""
Facebook Graph API integration for fetching social media metrics.
Supports Facebook, Instagram, and LinkedIn (via Facebook Business).
"""
from __future__ import annotations

import os
import logging
from datetime import date, timedelta
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)

FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
FACEBOOK_AD_ACCOUNT_ID = os.getenv("FACEBOOK_AD_ACCOUNT_ID", "2228418524061660")
GRAPH_API_VERSION = "v18.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class FacebookMetricsService:
    """Service for fetching Facebook/Instagram metrics via Graph API"""
    
    def __init__(self, access_token: str = None):
        self.access_token = access_token or FACEBOOK_ACCESS_TOKEN
        if not self.access_token:
            logger.warning("Facebook access token not configured")
    
    def get_page_metrics(self, page_id: str, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch page-level metrics (likes, reach, impressions, etc.)
        
        For New Page Experience pages, the old insights API is deprecated.
        We get engagement from posts instead.
        
        Args:
            page_id: Facebook Page ID
            start_date: Start date for metrics
            end_date: End date for metrics
        
        Returns:
            Dictionary containing page metrics
        """
        if not self.access_token:
            logger.error("Cannot fetch metrics: No access token")
            return {}
        
        metrics = {
            "impressions": 0,
            "unique_impressions": 0,
            "engaged_users": 0,
            "post_engagements": 0,
            "total_page_likes": 0,
            "page_visits": 0,
            "video_views": 0,
            "fan_adds": 0,
            "fan_removes": 0,
            "current_page_likes": 0,
            "page_name": "Unknown Page",
            "is_new_page_experience": False,
            "posts_count": 0,
            "total_reactions": 0,
            "total_comments": 0,
            "total_shares": 0,
        }
        
        # First, get basic page info (always works)
        try:
            page_info_url = f"{GRAPH_API_BASE}/{page_id}"
            page_info_params = {
                "access_token": self.access_token,
                "fields": "fan_count,followers_count,name,about,category,engagement,has_transitioned_to_new_page_experience"
            }
            page_info_response = requests.get(page_info_url, params=page_info_params, timeout=30)
            page_info_response.raise_for_status()
            page_info = page_info_response.json()
            
            metrics["current_page_likes"] = page_info.get("fan_count", 0)
            metrics["total_page_likes"] = page_info.get("fan_count", 0)
            metrics["page_name"] = page_info.get("name", "Unknown Page")
            metrics["is_new_page_experience"] = page_info.get("has_transitioned_to_new_page_experience", False)
            
            # Engagement data if available
            engagement = page_info.get("engagement", {})
            if engagement:
                metrics["engaged_users"] = engagement.get("count", 0)
                
            logger.info(f"Facebook page info: {page_info.get('name')} - {page_info.get('fan_count')} fans (NPE: {metrics['is_new_page_experience']})")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Facebook page info: {e}")
            return metrics
        
        # For New Page Experience pages, skip insights API (deprecated) and aggregate from posts
        if metrics["is_new_page_experience"]:
            logger.info("New Page Experience detected - aggregating engagement from posts")
            try:
                # Get posts with engagement metrics
                posts_url = f"{GRAPH_API_BASE}/{page_id}/posts"
                posts_params = {
                    "access_token": self.access_token,
                    "fields": "id,message,created_time,shares,likes.summary(true),comments.summary(true),reactions.summary(true)",
                    "since": start_date.isoformat(),
                    "until": end_date.isoformat(),
                    "limit": 100
                }
                posts_response = requests.get(posts_url, params=posts_params, timeout=30)
                posts_response.raise_for_status()
                posts_data = posts_response.json()
                
                total_reactions = 0
                total_comments = 0
                total_shares = 0
                posts_count = 0
                
                for post in posts_data.get("data", []):
                    posts_count += 1
                    total_reactions += post.get("reactions", {}).get("summary", {}).get("total_count", 0)
                    total_comments += post.get("comments", {}).get("summary", {}).get("total_count", 0)
                    total_shares += post.get("shares", {}).get("count", 0)
                
                metrics["posts_count"] = posts_count
                metrics["total_reactions"] = total_reactions
                metrics["total_comments"] = total_comments
                metrics["total_shares"] = total_shares
                metrics["post_engagements"] = total_reactions + total_comments + total_shares
                
                logger.info(f"Aggregated from {posts_count} posts: {total_reactions} reactions, {total_comments} comments, {total_shares} shares")
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Could not fetch posts for engagement aggregation: {e}")
        else:
            # Old Page - try insights API
            since = int(start_date.strftime("%s"))
            until = int(end_date.strftime("%s"))
            try:
                url = f"{GRAPH_API_BASE}/{page_id}/insights"
                params = {
                    "access_token": self.access_token,
                    "metric": ",".join([
                        "page_impressions",
                        "page_impressions_unique",
                        "page_engaged_users",
                        "page_post_engagements",
                        "page_fans",
                        "page_views_total",
                        "page_video_views",
                        "page_fan_adds",
                        "page_fan_removes",
                    ]),
                    "since": since,
                    "until": until,
                    "period": "day"
                }
                
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                # Process insights data
                insights = self._process_insights(data.get("data", []))
                metrics.update(insights)
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Could not fetch page insights: {e}")
        
        return metrics
    
    def get_posts_metrics(self, page_id: str, start_date: date, end_date: date, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch posts and their engagement metrics
        
        Args:
            page_id: Facebook Page ID
            start_date: Start date for posts
            end_date: End date for posts
            limit: Maximum number of posts to fetch
        
        Returns:
            List of post metrics
        """
        if not self.access_token:
            logger.error("Cannot fetch posts: No access token")
            return []
        
        try:
            url = f"{GRAPH_API_BASE}/{page_id}/posts"
            params = {
                "access_token": self.access_token,
                "fields": "id,message,created_time,shares,likes.summary(true),comments.summary(true),reactions.summary(true)",
                "since": start_date.isoformat(),
                "until": end_date.isoformat(),
                "limit": limit
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            posts = []
            for post in data.get("data", []):
                # Fetch post insights (reach, impressions)
                post_insights = self._get_post_insights(post["id"])
                
                posts.append({
                    "id": post["id"],
                    "title": post.get("message", "")[:100] + "..." if len(post.get("message", "")) > 100 else post.get("message", "(No text)"),
                    "created_time": post["created_time"],
                    "likes": post.get("likes", {}).get("summary", {}).get("total_count", 0),
                    "comments": post.get("comments", {}).get("summary", {}).get("total_count", 0),
                    "shares": post.get("shares", {}).get("count", 0),
                    "reactions": post.get("reactions", {}).get("summary", {}).get("total_count", 0),
                    "reach": post_insights.get("reach", 0),
                    "impressions": post_insights.get("impressions", 0),
                    "clicks": post_insights.get("clicks", 0),
                    "platform": "Facebook"
                })
            
            # Sort by reach (descending)
            posts.sort(key=lambda x: x.get("reach", 0), reverse=True)
            
            return posts
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Facebook posts: {e}")
            return []
    
    def get_click_actions(self, page_id: str, start_date: date, end_date: date) -> Dict[str, int]:
        """
        Fetch click actions (get directions, phone, website, etc.)
        
        Args:
            page_id: Facebook Page ID
            start_date: Start date
            end_date: End date
        
        Returns:
            Dictionary of click action counts
        """
        if not self.access_token:
            logger.error("Cannot fetch click actions: No access token")
            return {}
        
        since = int(start_date.strftime("%s"))
        until = int(end_date.strftime("%s"))
        
        try:
            url = f"{GRAPH_API_BASE}/{page_id}/insights"
            params = {
                "access_token": self.access_token,
                "metric": ",".join([
                    "page_total_actions",
                    "page_cta_clicks_logged_in_total",
                    "page_get_directions_clicks_logged_in_unique"
                ]),
                "since": since,
                "until": until,
                "period": "day"
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Process click actions
            actions = {}
            for metric in data.get("data", []):
                metric_name = metric.get("name", "")
                values = metric.get("values", [])
                
                if metric_name == "page_total_actions":
                    # This contains breakdowns by action type
                    for value_entry in values:
                        for action_type, count in value_entry.get("value", {}).items():
                            actions[action_type] = actions.get(action_type, 0) + count
                elif metric_name == "page_get_directions_clicks_logged_in_unique":
                    total = sum(v.get("value", 0) for v in values)
                    actions["get_directions"] = total
                elif metric_name == "page_cta_clicks_logged_in_total":
                    total = sum(v.get("value", 0) for v in values)
                    actions["action_button"] = total
            
            return actions
            
        except requests.exceptions.RequestException as e:
            # Click actions require insights permission - fail silently
            logger.debug(f"Could not fetch click actions (may need read_insights permission): {e}")
            return {}
    
    def _get_post_insights(self, post_id: str) -> Dict[str, int]:
        """Fetch insights for a specific post (requires read_insights permission)"""
        try:
            url = f"{GRAPH_API_BASE}/{post_id}/insights"
            params = {
                "access_token": self.access_token,
                "metric": "post_impressions,post_impressions_unique,post_clicks"
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            insights = {}
            for metric in data.get("data", []):
                metric_name = metric.get("name", "")
                values = metric.get("values", [])
                
                if values:
                    if metric_name == "post_impressions":
                        insights["impressions"] = values[0].get("value", 0)
                    elif metric_name == "post_impressions_unique":
                        insights["reach"] = values[0].get("value", 0)
                    elif metric_name == "post_clicks":
                        insights["clicks"] = values[0].get("value", 0)
            
            return insights
            
        except requests.exceptions.RequestException:
            # This is expected to fail without read_insights permission - silently return empty
            return {}
    
    def _process_insights(self, insights_data: List[Dict]) -> Dict[str, Any]:
        """Process raw insights data into structured metrics"""
        metrics = {
            "impressions": 0,
            "unique_impressions": 0,
            "engaged_users": 0,
            "post_engagements": 0,
            "total_page_likes": 0,
            "page_visits": 0,
            "video_views": 0,
            "fan_adds": 0,
            "fan_removes": 0,
        }
        
        for metric in insights_data:
            metric_name = metric.get("name", "")
            values = metric.get("values", [])
            
            # Sum up values across the period
            total = sum(v.get("value", 0) for v in values if isinstance(v.get("value"), (int, float)))
            
            if metric_name == "page_impressions":
                metrics["impressions"] = total
            elif metric_name == "page_impressions_unique":
                metrics["unique_impressions"] = total
            elif metric_name == "page_engaged_users":
                metrics["engaged_users"] = total
            elif metric_name == "page_post_engagements":
                metrics["post_engagements"] = total
            elif metric_name == "page_fans":
                # For page_fans, take the most recent value
                metrics["total_page_likes"] = values[-1].get("value", 0) if values else 0
            elif metric_name == "page_views_total":
                metrics["page_visits"] = total
            elif metric_name == "page_video_views":
                metrics["video_views"] = total
            elif metric_name == "page_fan_adds":
                metrics["fan_adds"] = total
            elif metric_name == "page_fan_removes":
                metrics["fan_removes"] = total
        
        return metrics


# Singleton instance
facebook_service = FacebookMetricsService()


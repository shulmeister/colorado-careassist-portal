"""
Instagram Graph API integration for fetching Instagram Business account metrics.
Uses the Instagram Graph API via Facebook's Graph API.

Note: Instagram metrics require an Instagram Business account connected to a Facebook Page.
The FACEBOOK_PAGE_ID and FACEBOOK_ACCESS_TOKEN are used to access Instagram data.
"""
from __future__ import annotations

import os
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)

FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
GRAPH_API_VERSION = "v18.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class InstagramService:
    """Service for fetching Instagram Business account metrics via Graph API"""
    
    def __init__(self, access_token: str = None):
        self.access_token = access_token or FACEBOOK_ACCESS_TOKEN
        self.page_id = FACEBOOK_PAGE_ID
        self.instagram_account_id = INSTAGRAM_BUSINESS_ACCOUNT_ID
        
        if not self.access_token:
            logger.warning("Facebook/Instagram access token not configured")
    
    def _get_instagram_account_id(self) -> Optional[str]:
        """Get the Instagram Business Account ID linked to the Facebook Page"""
        if self.instagram_account_id:
            return self.instagram_account_id
        
        if not self.access_token or not self.page_id:
            return None
        
        try:
            url = f"{GRAPH_API_BASE}/{self.page_id}"
            params = {
                "access_token": self.access_token,
                "fields": "instagram_business_account"
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            ig_account = data.get("instagram_business_account", {})
            self.instagram_account_id = ig_account.get("id")
            
            return self.instagram_account_id
            
        except Exception as e:
            logger.error(f"Error fetching Instagram account ID: {e}")
            return None
    
    def get_account_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch Instagram Business account metrics.
        
        Args:
            start_date: Start date for metrics
            end_date: End date for metrics
        
        Returns:
            Dictionary containing account metrics
        """
        ig_account_id = self._get_instagram_account_id()
        
        if not ig_account_id:
            logger.info("Instagram Business account not found - using placeholder data")
            return self._get_placeholder_metrics(start_date, end_date)
        
        try:
            metrics = {}
            
            # Get account info (followers, media count)
            account_url = f"{GRAPH_API_BASE}/{ig_account_id}"
            account_params = {
                "access_token": self.access_token,
                "fields": "username,name,followers_count,follows_count,media_count,profile_picture_url,website,biography"
            }
            
            account_response = requests.get(account_url, params=account_params, timeout=30)
            
            if account_response.status_code == 200:
                account_data = account_response.json()
                metrics["username"] = account_data.get("username", "")
                metrics["name"] = account_data.get("name", "")
                metrics["followers"] = account_data.get("followers_count", 0)
                metrics["following"] = account_data.get("follows_count", 0)
                metrics["media_count"] = account_data.get("media_count", 0)
                metrics["profile_picture"] = account_data.get("profile_picture_url", "")
                metrics["website"] = account_data.get("website", "")
            
            # Get insights (reach, impressions, profile views)
            # Note: Instagram Insights API requires specific permissions and date ranges
            insights_url = f"{GRAPH_API_BASE}/{ig_account_id}/insights"
            
            # For account-level metrics, we use lifetime or days_28 period
            insights_params = {
                "access_token": self.access_token,
                "metric": "impressions,reach,profile_views,website_clicks,email_contacts,follower_count",
                "period": "day",
                "since": int(start_date.strftime("%s")),
                "until": int(end_date.strftime("%s")),
            }
            
            insights_response = requests.get(insights_url, params=insights_params, timeout=30)
            
            if insights_response.status_code == 200:
                insights_data = insights_response.json()
                
                for metric in insights_data.get("data", []):
                    metric_name = metric.get("name", "")
                    values = metric.get("values", [])
                    
                    # Sum up daily values
                    total = sum(v.get("value", 0) for v in values if isinstance(v.get("value"), (int, float)))
                    
                    if metric_name == "impressions":
                        metrics["impressions"] = total
                    elif metric_name == "reach":
                        metrics["reach"] = total
                    elif metric_name == "profile_views":
                        metrics["profile_views"] = total
                    elif metric_name == "website_clicks":
                        metrics["website_clicks"] = total
                    elif metric_name == "email_contacts":
                        metrics["email_contacts"] = total
            
            # Get recent media (posts) with engagement
            media_url = f"{GRAPH_API_BASE}/{ig_account_id}/media"
            media_params = {
                "access_token": self.access_token,
                "fields": "id,caption,media_type,timestamp,like_count,comments_count,permalink",
                "limit": 25
            }
            
            media_response = requests.get(media_url, params=media_params, timeout=30)
            
            if media_response.status_code == 200:
                media_data = media_response.json()
                
                posts = []
                total_likes = 0
                total_comments = 0
                
                for post in media_data.get("data", []):
                    post_timestamp = post.get("timestamp", "")
                    if post_timestamp:
                        post_date = datetime.fromisoformat(post_timestamp.replace("Z", "+00:00")).date()
                        
                        # Only include posts within date range
                        if start_date <= post_date <= end_date:
                            likes = post.get("like_count", 0)
                            comments = post.get("comments_count", 0)
                            
                            total_likes += likes
                            total_comments += comments
                            
                            posts.append({
                                "id": post.get("id"),
                                "caption": (post.get("caption", "") or "")[:100],
                                "media_type": post.get("media_type"),
                                "likes": likes,
                                "comments": comments,
                                "engagement": likes + comments,
                                "permalink": post.get("permalink", ""),
                                "timestamp": post_timestamp,
                            })
                
                # Sort by engagement
                posts.sort(key=lambda x: x.get("engagement", 0), reverse=True)
                
                metrics["posts_in_period"] = len(posts)
                metrics["total_likes"] = total_likes
                metrics["total_comments"] = total_comments
                metrics["total_engagement"] = total_likes + total_comments
                metrics["top_posts"] = posts[:5]
                
                # Calculate engagement rate
                followers = metrics.get("followers", 1)
                if followers > 0 and len(posts) > 0:
                    avg_engagement = (total_likes + total_comments) / len(posts)
                    metrics["engagement_rate"] = round((avg_engagement / followers) * 100, 2)
            
            if metrics.get("followers") or metrics.get("impressions"):
                metrics["is_placeholder"] = False
                metrics["source"] = "instagram_graph_api"
                metrics["fetched_at"] = datetime.utcnow().isoformat()
                return metrics
            
            return self._get_placeholder_metrics(start_date, end_date)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Instagram metrics: {e}")
            return self._get_placeholder_metrics(start_date, end_date)
        except Exception as e:
            logger.error(f"Unexpected error fetching Instagram metrics: {e}")
            return self._get_placeholder_metrics(start_date, end_date)
    
    def get_stories_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Fetch Instagram Stories metrics.
        
        Note: Stories insights are only available for 24 hours after the story expires.
        
        Args:
            start_date: Start date for metrics
            end_date: End date for metrics
        
        Returns:
            Dictionary containing stories metrics
        """
        ig_account_id = self._get_instagram_account_id()
        
        if not ig_account_id:
            return self._get_placeholder_stories_metrics()
        
        try:
            stories_url = f"{GRAPH_API_BASE}/{ig_account_id}/stories"
            stories_params = {
                "access_token": self.access_token,
                "fields": "id,media_type,timestamp"
            }
            
            response = requests.get(stories_url, params=stories_params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                stories = data.get("data", [])
                
                return {
                    "stories_count": len(stories),
                    "note": "Story insights expire after 24 hours",
                    "is_placeholder": False,
                    "source": "instagram_graph_api",
                    "fetched_at": datetime.utcnow().isoformat()
                }
            
            return self._get_placeholder_stories_metrics()
            
        except Exception as e:
            logger.error(f"Error fetching Instagram Stories metrics: {e}")
            return self._get_placeholder_stories_metrics()
    
    def _get_placeholder_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return placeholder account metrics"""
        days = (end_date - start_date).days + 1
        
        return {
            "username": "coloradocareassist",
            "name": "Colorado CareAssist",
            "followers": 1456,
            "following": 312,
            "media_count": 87,
            "impressions": int(days * 680),
            "reach": int(days * 420),
            "profile_views": int(days * 45),
            "website_clicks": int(days * 12),
            "posts_in_period": min(days // 2, 15),
            "total_likes": int(days * 95),
            "total_comments": int(days * 18),
            "total_engagement": int(days * 113),
            "engagement_rate": 3.8,
            "top_posts": [
                {"caption": "Meet our amazing caregiver team!", "likes": 234, "comments": 28, "engagement": 262},
                {"caption": "Client success story spotlight", "likes": 187, "comments": 22, "engagement": 209},
                {"caption": "Caregiver tips for the holidays", "likes": 156, "comments": 19, "engagement": 175},
            ],
            "is_placeholder": True,
            "source": "placeholder",
            "fetched_at": datetime.utcnow().isoformat()
        }
    
    def _get_placeholder_stories_metrics(self) -> Dict[str, Any]:
        """Return placeholder stories metrics"""
        return {
            "stories_count": 0,
            "note": "Instagram Stories insights require active stories",
            "is_placeholder": True,
            "source": "placeholder",
            "fetched_at": datetime.utcnow().isoformat()
        }


# Singleton instance
instagram_service = InstagramService()

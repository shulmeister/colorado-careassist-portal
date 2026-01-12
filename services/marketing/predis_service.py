"""
Predis AI API integration for social content creation and management.
Provides access to AI-powered social media content generation and scheduling.
"""
from __future__ import annotations

import os
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)

PREDIS_AI_API_KEY = os.getenv("PREDIS_AI_API_KEY")
PREDIS_AI_BASE_URL = "https://brain.predis.ai/predis_api/v1"
PREDIS_BRAND_ID = os.getenv("PREDIS_BRAND_ID")


class PredisAIService:
    """Service for interacting with Predis AI API"""

    def __init__(self, api_key: str = None, brand_id: str = None):
        self.api_key = api_key or PREDIS_AI_API_KEY
        self.brand_id = brand_id or PREDIS_BRAND_ID
        self.base_url = PREDIS_AI_BASE_URL

        if not self.api_key:
            logger.warning("Predis AI API key not configured")
    
    def _make_api_request(self, endpoint: str, method: str = "GET", data: Dict = None) -> Optional[Dict]:
        """
        Make an authenticated API request to Predis AI.
        
        Args:
            endpoint: API endpoint (e.g., "/content/generate")
            method: HTTP method
            data: Request data for POST requests
            
        Returns:
            Response JSON or None
        """
        if not self.api_key:
            logger.error("No Predis AI API key available")
            return None
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            else:
                response = requests.request(method, url, headers=headers, json=data, timeout=30)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Predis AI API request failed: {e}")
            return None
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get Predis AI account information by testing API connectivity.

        Returns:
            Account information dictionary
        """
        # Test API connectivity by getting brands
        data = self._make_api_request("/get_brands/")

        if data and data.get("message") == "ok":
            brands = data.get("brand_details", [])
            brand_name = None
            if brands and self.brand_id:
                for b in brands:
                    if b.get("brand_id") == self.brand_id:
                        brand_name = b.get("brand_name")
                        break
            return {
                "account_id": "Connected",
                "brand_id": self.brand_id,
                "brand_name": brand_name or (brands[0].get("brand_name") if brands else None),
                "total_brands": len(brands),
                "plan": "Active",
                "status": "connected",
                "api_working": True
            }

        return {
            "account_id": None,
            "plan": "Not connected",
            "credits_remaining": 0,
            "status": "error",
            "api_working": False,
            "message": "Failed to connect to Predis AI"
        }
    
    def generate_content(self, prompt: str, media_type: str = "single_image") -> Dict[str, Any]:
        """
        Generate social media content using Predis AI create_content endpoint.

        Args:
            prompt: Content generation prompt
            media_type: Type of content (single_image, carousel, video, quote, meme)

        Returns:
            Generated content data
        """
        data = {
            "text": prompt,
            "media_type": media_type,
            "brand_id": self.brand_id,
            "model_version": "4"
        }
        
        result = self._make_api_request("/create_content/", method="POST", data=data)
        
        if result:
            return {
                "success": True,
                "content_id": result.get("id"),
                "text": result.get("text", ""),
                "image_url": result.get("media_url"),
                "media_type": media_type,
                "status": result.get("status", "generated"),
                "created_at": result.get("created_at", datetime.now().isoformat())
            }
        
        return {
            "success": False,
            "error": "Failed to generate content",
            "media_type": media_type
        }
    
    def get_templates(self, page: int = 1) -> List[Dict[str, Any]]:
        """
        Get available content templates from Predis AI.
        
        Args:
            page: Page number for pagination
            
        Returns:
            List of template dictionaries
        """
        endpoint = f"/get_all_templates/?page={page}"
        
        data = self._make_api_request(endpoint)
        
        if data and "templates" in data:
            templates = []
            for template in data["templates"]:
                templates.append({
                    "id": template.get("id"),
                    "name": template.get("name"),
                    "description": template.get("description"),
                    "category": template.get("category"),
                    "preview_url": template.get("preview_url"),
                    "tags": template.get("tags", [])
                })
            return templates
        
        return []
    
    def get_recent_creations(self, page: int = 1) -> List[Dict[str, Any]]:
        """
        Get recently created content from Predis AI using get_posts endpoint.

        Args:
            page: Page number for pagination

        Returns:
            List of recent content items
        """
        endpoint = f"/get_posts/?page={page}"
        if self.brand_id:
            endpoint = f"/get_posts/?brand_id={self.brand_id}&page={page}"

        data = self._make_api_request(endpoint)

        if data and "posts" in data:
            recent = []
            for item in data["posts"]:
                text = item.get("text", "") or ""
                recent.append({
                    "id": item.get("id") or item.get("post_id"),
                    "text": text[:100] + "..." if len(text) > 100 else text,
                    "media_type": item.get("media_type"),
                    "created_at": item.get("created_at") or item.get("createdAt"),
                    "status": item.get("status"),
                    "media_url": item.get("media_url") or item.get("output", [{}])[0].get("url") if item.get("output") else None,
                    "brand_id": item.get("brand_id")
                })
            return recent

        return []
    
    def schedule_content(self, content_id: str, platform: str, scheduled_time: datetime) -> Dict[str, Any]:
        """
        Schedule content for publishing via Predis AI.
        
        Args:
            content_id: ID of the generated content
            platform: Target platform for publishing
            scheduled_time: When to publish the content
            
        Returns:
            Scheduling result
        """
        data = {
            "content_id": content_id,
            "platform": platform,
            "scheduled_time": scheduled_time.isoformat(),
            "auto_publish": True
        }
        
        result = self._make_api_request("/content/schedule", method="POST", data=data)
        
        if result:
            return {
                "success": True,
                "schedule_id": result.get("schedule_id"),
                "scheduled_time": scheduled_time.isoformat(),
                "platform": platform,
                "status": result.get("status", "scheduled")
            }
        
        return {
            "success": False,
            "error": "Failed to schedule content"
        }
    
    def get_analytics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Get analytics for Predis AI generated content.
        
        Args:
            start_date: Start date for analytics
            end_date: End date for analytics
            
        Returns:
            Analytics data
        """
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
        
        data = self._make_api_request(f"/analytics?start_date={params['start_date']}&end_date={params['end_date']}")
        
        if data:
            return {
                "total_posts": data.get("total_posts", 0),
                "total_engagement": data.get("total_engagement", 0),
                "avg_engagement_rate": data.get("avg_engagement_rate", 0),
                "top_performing_post": data.get("top_performing_post"),
                "platform_breakdown": data.get("platform_breakdown", {}),
                "content_type_performance": data.get("content_type_performance", {}),
                "growth_metrics": data.get("growth_metrics", {})
            }
        
        return {
            "total_posts": 0,
            "total_engagement": 0,
            "avg_engagement_rate": 0,
            "top_performing_post": None,
            "platform_breakdown": {},
            "content_type_performance": {},
            "growth_metrics": {}
        }
    
    def get_placeholder_data(self, message: str = "Predis AI not configured") -> Dict[str, Any]:
        """Return placeholder data when Predis AI is not configured."""
        return {
            "account_info": {
                "plan": "Not connected",
                "credits_remaining": 0,
                "status": "not_configured"
            },
            "recent_creations": [],
            "analytics": {
                "total_posts": 0,
                "total_engagement": 0,
                "avg_engagement_rate": 0
            },
            "not_configured": True,
            "message": message
        }


# Singleton instance
predis_service = PredisAIService()
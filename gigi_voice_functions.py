"""
Gigi Voice Functions - Webhook endpoints for Retell voice agent
Gives voice Gigi access to all the same data as text Gigi
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gigi/voice", tags=["gigi-voice"])

class FunctionRequest(BaseModel):
    arguments: dict = {}

@router.post("/weather")
async def get_weather(req: FunctionRequest):
    """Get current weather"""
    try:
        location = req.arguments.get("location", "Boulder CO")
        
        # Map locations to coords
        coords_map = {
            "eldora": (39.94, -105.58),
            "boulder": (40.01, -105.27),
            "vail": (39.64, -106.37),
            "breckenridge": (39.48, -106.04),
            "keystone": (39.60, -105.95),
            "arapahoe basin": (39.64, -105.87),
            "a basin": (39.64, -105.87),
            "loveland": (39.68, -105.90),
            "copper": (39.50, -106.15),
            "winter park": (39.89, -105.76)
        }
        
        loc_lower = location.lower()
        lat, lon = None, None
        
        for key, coords in coords_map.items():
            if key in loc_lower:
                lat, lon = coords
                break
        
        if not lat:
            lat, lon = 40.01, -105.27  # Default to Boulder
        
        # Fetch weather from Open-Meteo
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weathercode,windspeed_10m&temperature_unit=fahrenheit&windspeed_unit=mph&timezone=America%2FDenver"
        
        resp = requests.get(url, timeout=5)
        data = resp.json()
        current = data['current']
        
        temp = int(current['temperature_2m'])
        wind = int(current['windspeed_10m'])
        
        conditions_map = {
            0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
            45: "foggy", 71: "light snow", 73: "snow", 75: "heavy snow", 
            95: "thunderstorm"
        }
        weather = conditions_map.get(current['weathercode'], "partly cloudy")
        
        summary = f"{temp} degrees with {weather}, winds at {wind} miles per hour"
        
        return {
            "result": summary,
            "temperature": temp,
            "conditions": weather,
            "wind_mph": wind
        }
    except Exception as e:
        logger.error(f"Weather error: {e}")
        return {"result": "I couldn't get the weather right now", "error": str(e)}

@router.post("/calendar")
async def get_calendar(req: FunctionRequest):
    """Get calendar events - placeholder for now"""
    try:
        when = req.arguments.get("when", "today").lower()
        
        # TODO: Integrate with Google Calendar API directly
        # For now, return a friendly message
        
        return {
            "result": f"I can't check your calendar right now, but I'm working on it",
            "count": 0
        }
    except Exception as e:
        logger.error(f"Calendar error: {e}")
        return {"result": "I couldn't check your calendar", "error": str(e)}

@router.post("/email")
async def get_email_summary(req: FunctionRequest):
    """Get unread email count - placeholder"""
    try:
        # TODO: Integrate with Gmail API directly
        return {
            "result": "I can't check email via voice yet, but I'm working on it",
            "count": 0
        }
    except Exception as e:
        logger.error(f"Email error: {e}")
        return {"result": "I couldn't check email", "error": str(e)}

@router.get("/health")
async def health():
    return {"status": "healthy", "service": "gigi-voice-functions", "timestamp": datetime.now().isoformat()}

"""
Gigi Voice Functions - Webhook endpoints for Retell voice agent
Gives voice Gigi access to all the same data as text Gigi
"""

from fastapi import APIRouter
from pydantic import BaseModel
import subprocess
import json
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/gigi/voice", tags=["gigi-voice"])

ACCOUNT = "jason@coloradocareassist.com"

class FunctionRequest(BaseModel):
    arguments: dict = {}

def run_command(cmd: list, timeout=10):
    """Run shell command and return output"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip() if result.returncode == 0 else None
    except:
        return None

@router.post("/weather")
async def get_weather(req: FunctionRequest):
    """Get current weather"""
    try:
        location = req.arguments.get("location", "Boulder CO")
        
        # Map locations to coords
        coords_map = {
            "eldora": (39.94, -105.58), "boulder": (40.01, -105.27),
            "vail": (39.64, -106.37), "breckenridge": (39.48, -106.04),
            "keystone": (39.60, -105.95), "arapahoe basin": (39.64, -105.87),
            "loveland": (39.68, -105.90)
        }
        
        loc_lower = location.lower()
        lat, lon = coords_map.get(next((k for k in coords_map if k in loc_lower), None), (40.01, -105.27))
        
        import requests
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weathercode,windspeed_10m&temperature_unit=fahrenheit&windspeed_unit=mph&timezone=America%2FDenver"
        
        resp = requests.get(url, timeout=5)
        data = resp.json()
        current = data['current']
        
        temp = int(current['temperature_2m'])
        wind = int(current['windspeed_10m'])
        
        conditions_map = {
            0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
            71: "light snow", 73: "snow", 75: "heavy snow", 95: "thunderstorm"
        }
        weather = conditions_map.get(current['weathercode'], "unknown")
        
        return {
            "result": f"{temp} degrees with {weather}, winds at {wind} miles per hour",
            "temperature": temp,
            "conditions": weather,
            "wind_mph": wind
        }
    except Exception as e:
        return {"result": "I couldn't get the weather right now", "error": str(e)}

@router.post("/calendar")
async def get_calendar(req: FunctionRequest):
    """Get calendar events"""
    try:
        when = req.arguments.get("when", "today").lower()
        now = datetime.now()
        date_str = (now + timedelta(days=1 if when == "tomorrow" else 0)).strftime("%Y-%m-%d")
        
        cmd = ["gog", "calendar", "events", ACCOUNT, "--account", ACCOUNT, "--from", date_str, "--to", date_str, "--json"]
        result = run_command(cmd)
        
        if not result:
            return {"result": f"No events {when}", "count": 0}
        
        events = json.loads(result).get('events', [])
        if not events:
            return {"result": f"You have no events {when}", "count": 0}
        
        summaries = []
        for e in events:
            start = e['start'].get('dateTime', '')
            if start:
                time = datetime.fromisoformat(start).strftime("%I:%M %p")
                summaries.append(f"{e['summary']} at {time}")
        
        return {
            "result": f"{len(events)} event{'s' if len(events) != 1 else ''} {when}: " + ", ".join(summaries),
            "count": len(events),
            "events": summaries
        }
    except Exception as e:
        return {"result": "I couldn't check your calendar", "error": str(e)}

@router.post("/email")
async def get_email_summary(req: FunctionRequest):
    """Get unread email count"""
    try:
        cmd = ["gog", "gmail", "search", "is:unread", "--account", ACCOUNT, "--max", "5", "--json"]
        result = run_command(cmd)
        
        if not result:
            return {"result": "No unread emails", "count": 0}
        
        threads = json.loads(result).get('threads', [])
        if not threads:
            return {"result": "No unread emails", "count": 0}
        
        subjects = [t['subject'][:50] for t in threads[:3]]
        return {
            "result": f"{len(threads)} unread emails. Most recent: {subjects[0]}",
            "count": len(threads),
            "recent": subjects
        }
    except Exception as e:
        return {"result": "I couldn't check email", "error": str(e)}

@router.post("/contacts")
async def search_contacts(req: FunctionRequest):
    """Search contacts"""
    try:
        name = req.arguments.get("name", "")
        script = f'tell application "Contacts" to get name of every person whose name contains "{name}"'
        result = run_command(['osascript', '-e', script])
        
        if result and result != "missing value":
            return {"result": f"Found {name} in your contacts", "found": True}
        return {"result": f"Couldn't find {name}", "found": False}
    except Exception as e:
        return {"result": "I couldn't search contacts", "error": str(e)}

@router.get("/health")
async def health():
    return {"status": "healthy", "service": "gigi-voice-functions"}

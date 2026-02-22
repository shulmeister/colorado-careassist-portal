"""
Fitness tools for Gigi — Strava dashboard data.
Called by telegram_bot.py, voice_brain.py, ringcentral_bot.py.
All functions are SYNCHRONOUS — callers wrap in asyncio.to_thread() / run_sync().
All functions return dicts — callers json.dumps() the result.

Reads from the Fitness Dashboard API at localhost:3040 (zero Strava API calls).
"""
import logging
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

FD_BASE = "http://localhost:3040/api"
TIMEOUT = 10


def _fd_get(path: str) -> Dict[str, Any]:
    """GET request to the fitness dashboard API."""
    try:
        resp = requests.get(f"{FD_BASE}{path}", timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Fitness dashboard not running. Check port 3040."}
    except Exception as e:
        return {"error": f"Fitness API error: {str(e)}"}


def get_fitness_summary(period: str = "ytd") -> Dict[str, Any]:
    """Get fitness summary — weekly/monthly/YTD/all-time stats.

    Args:
        period: 'this_week', 'ytd', or 'all_time' (default: 'ytd')
    """
    data = _fd_get("/stats/overview")
    if "error" in data:
        return data

    period_key = period if period in ("this_week", "ytd", "all_time") else "ytd"
    stats = data.get(period_key, {})
    streaks = data.get("streaks", {})

    # Convert meters to miles/feet for readability
    distance_miles = round(stats.get("distance", 0) / 1609.344, 1)
    elevation_feet = round(stats.get("elevation", 0) * 3.28084)
    hours = round(stats.get("time", 0) / 3600, 1)

    result = {
        "period": period_key,
        "distance_miles": distance_miles,
        "time_hours": hours,
        "elevation_feet": elevation_feet,
        "activity_count": stats.get("count", 0),
        "current_streak_days": streaks.get("current", 0),
        "longest_streak_days": streaks.get("longest", 0),
    }

    # Add week-over-week comparison for this_week
    if period_key == "this_week":
        last = data.get("last_week", {})
        if last.get("distance", 0) > 0:
            result["vs_last_week_pct"] = round(
                ((stats.get("distance", 0) - last["distance"]) / last["distance"]) * 100, 1
            )

    return result


def get_recent_activities(count: int = 5) -> Dict[str, Any]:
    """Get the most recent N activities.

    Args:
        count: Number of activities (default: 5, max: 20)
    """
    count = min(max(1, count), 20)
    data = _fd_get(f"/activities/recent?count={count}")
    if isinstance(data, dict) and "error" in data:
        return data

    activities = []
    for a in (data if isinstance(data, list) else []):
        distance_miles = round(a.get("distance", 0) / 1609.344, 2)
        moving_time = a.get("moving_time", 0)
        pace_str = ""
        if a.get("average_speed") and a["average_speed"] > 0:
            sec_per_mile = 1609.344 / a["average_speed"]
            m, s = divmod(int(sec_per_mile), 60)
            pace_str = f"{m}:{s:02d}/mi"

        activities.append({
            "name": a.get("name", ""),
            "sport_type": a.get("sport_type", ""),
            "date": a.get("start_date_local", "")[:10],
            "distance_miles": distance_miles,
            "time": f"{moving_time // 3600}:{(moving_time % 3600) // 60:02d}:{moving_time % 60:02d}" if moving_time >= 3600 else f"{moving_time // 60}:{moving_time % 60:02d}",
            "pace": pace_str,
            "avg_hr": round(a["average_heartrate"]) if a.get("average_heartrate") else None,
            "elevation_ft": round(a.get("total_elevation_gain", 0) * 3.28084),
        })

    return {"activities": activities, "count": len(activities)}


def get_personal_records() -> Dict[str, Any]:
    """Get personal records — fastest 5K/10K/half/marathon, biggest climb."""
    data = _fd_get("/stats/records")
    if "error" in data:
        return data

    records = {}
    for effort in data.get("best_efforts", []):
        name = effort.get("name", "")
        moving_time = effort.get("moving_time", 0)
        m, s = divmod(int(moving_time), 60)
        h, m = divmod(m, 60)
        time_str = f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"
        records[name] = {
            "time": time_str,
            "date": (effort.get("start_date_local") or "")[:10],
        }

    result: Dict[str, Any] = {"best_efforts": records}

    if data.get("biggest_climb"):
        climb = data["biggest_climb"]
        result["biggest_climb"] = {
            "name": climb.get("name", ""),
            "elevation_ft": round(climb.get("total_elevation_gain", 0) * 3.28084),
            "date": (climb.get("start_date_local") or "")[:10],
        }

    return result


def get_activity_streak() -> Dict[str, Any]:
    """Get current and longest activity streaks."""
    data = _fd_get("/stats/streaks")
    if "error" in data:
        return data
    return data


def get_gear_status() -> Dict[str, Any]:
    """Get gear mileage and retirement warnings for shoes/bikes."""
    data = _fd_get("/stats/gear")
    if isinstance(data, dict) and "error" in data:
        return data

    gear_items = []
    for g in (data if isinstance(data, list) else []):
        if g.get("retired"):
            continue
        miles = round(g.get("distance", 0) / 1609.344)
        is_shoe = g.get("gear_type") == "shoe" or "shoe" in (g.get("name") or "").lower() or miles < 1000
        status = "ok"
        if is_shoe:
            if miles >= 500:
                status = "REPLACE NOW"
            elif miles >= 400:
                status = "warning — nearing retirement"

        gear_items.append({
            "name": g.get("name", "Unknown"),
            "miles": miles,
            "type": g.get("gear_type", "unknown"),
            "primary": g.get("primary_gear", False),
            "status": status,
        })

    return {"gear": gear_items, "count": len(gear_items)}

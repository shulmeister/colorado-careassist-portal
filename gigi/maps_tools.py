"""
Google Maps tools for Gigi — geocoding, directions, nearby places.

Uses Google Maps REST APIs directly (Geocoding, Directions, Places).
All functions are ASYNC. All functions return dicts.

API key: GOOGLE_MAPS_API_KEY env var (restricted to Maps/Geocoding/Places/Directions/Elevation).
"""

import asyncio
import json
import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger("gigi.maps")

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
PLACES_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


def _api_get(url: str, params: dict) -> dict:
    """Synchronous HTTP GET to Google Maps API. Returns parsed JSON."""
    params["key"] = API_KEY
    qs = urllib.parse.urlencode(params)
    full_url = f"{url}?{qs}"
    req = urllib.request.Request(full_url)
    req.add_header("User-Agent", "Gigi/1.0")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def _geocode(address: str) -> dict:
    """Geocode a single address. Returns dict with lat, lng, formatted_address."""
    data = _api_get(GEOCODE_URL, {"address": address})
    if data.get("status") != "OK" or not data.get("results"):
        return {"error": f"Geocoding failed: {data.get('status', 'NO_RESULTS')}"}
    result = data["results"][0]
    loc = result["geometry"]["location"]
    components = {}
    for c in result.get("address_components", []):
        for t in c.get("types", []):
            components[t] = c.get("long_name", "")
    return {
        "formatted_address": result.get("formatted_address", ""),
        "latitude": loc["lat"],
        "longitude": loc["lng"],
        "place_id": result.get("place_id", ""),
        "city": components.get("locality", ""),
        "state": components.get("administrative_area_level_1", ""),
        "zip_code": components.get("postal_code", ""),
        "county": components.get("administrative_area_level_2", ""),
    }


async def geocode_address(address: str) -> dict:
    """Geocode an address — returns coordinates + normalized address.

    Called from execute_tool.
    """
    if not API_KEY:
        return {"error": "GOOGLE_MAPS_API_KEY not configured"}
    if not address or not address.strip():
        return {"error": "Address is required"}

    try:
        result = await asyncio.to_thread(_geocode, address.strip())
        return {"success": "error" not in result, **result}
    except Exception as e:
        logger.error(f"Geocode failed: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Directions & Distance
# ---------------------------------------------------------------------------

def _get_directions(origin: str, destination: str, mode: str) -> dict:
    """Get directions between two points."""
    data = _api_get(DIRECTIONS_URL, {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "units": "imperial",
        "departure_time": "now",
    })
    if data.get("status") != "OK" or not data.get("routes"):
        return {"error": f"Directions failed: {data.get('status', 'NO_ROUTES')}"}

    route = data["routes"][0]
    leg = route["legs"][0]

    # Build step-by-step directions
    steps = []
    for step in leg.get("steps", []):
        # Strip HTML tags from instructions
        instruction = step.get("html_instructions", "")
        import re
        instruction = re.sub(r"<[^>]+>", " ", instruction).strip()
        instruction = re.sub(r"\s+", " ", instruction)
        steps.append({
            "instruction": instruction,
            "distance": step.get("distance", {}).get("text", ""),
            "duration": step.get("duration", {}).get("text", ""),
        })

    # Build Google Maps link
    maps_url = (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={urllib.parse.quote(origin)}"
        f"&destination={urllib.parse.quote(destination)}"
        f"&travelmode={mode}"
    )

    return {
        "origin": leg.get("start_address", origin),
        "destination": leg.get("end_address", destination),
        "distance_text": leg.get("distance", {}).get("text", ""),
        "distance_miles": round(leg.get("distance", {}).get("value", 0) / 1609.34, 1),
        "duration_text": leg.get("duration", {}).get("text", ""),
        "duration_minutes": round(leg.get("duration", {}).get("value", 0) / 60, 1),
        "duration_in_traffic_text": leg.get("duration_in_traffic", {}).get("text", ""),
        "summary": route.get("summary", ""),
        "steps": steps[:15],  # Cap at 15 steps
        "maps_url": maps_url,
        "mode": mode,
    }


async def get_directions(
    origin: str,
    destination: str,
    mode: str = "driving",
) -> dict:
    """Get directions, distance, and travel time between two locations.

    Args:
        origin: Start address or place name.
        destination: End address or place name.
        mode: Travel mode — driving, transit, walking, bicycling.

    Called from execute_tool.
    """
    if not API_KEY:
        return {"error": "GOOGLE_MAPS_API_KEY not configured"}
    if not origin or not destination:
        return {"error": "Both origin and destination are required"}

    mode = (mode or "driving").strip().lower()
    if mode not in ("driving", "transit", "walking", "bicycling"):
        mode = "driving"

    try:
        result = await asyncio.to_thread(_get_directions, origin.strip(), destination.strip(), mode)
        return {"success": "error" not in result, **result}
    except Exception as e:
        logger.error(f"Directions failed: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Nearby Places
# ---------------------------------------------------------------------------

# Common place types for home care context
PLACE_TYPE_ALIASES = {
    "pharmacy": "pharmacy",
    "drug store": "pharmacy",
    "drugstore": "pharmacy",
    "hospital": "hospital",
    "doctor": "doctor",
    "clinic": "doctor",
    "urgent care": "doctor",
    "grocery": "supermarket",
    "supermarket": "supermarket",
    "grocery store": "supermarket",
    "restaurant": "restaurant",
    "gas station": "gas_station",
    "gas": "gas_station",
    "bank": "bank",
    "atm": "atm",
    "post office": "post_office",
    "library": "library",
    "park": "park",
    "gym": "gym",
    "dentist": "dentist",
    "veterinarian": "veterinary_care",
    "vet": "veterinary_care",
    "church": "church",
    "school": "school",
    "police": "police",
    "fire station": "fire_station",
}


def _search_places(location: str, place_type: str, radius_miles: int) -> dict:
    """Search for nearby places around a location."""
    # First geocode the location to get coordinates
    geo = _geocode(location)
    if "error" in geo:
        return geo

    lat, lng = geo["latitude"], geo["longitude"]
    radius_meters = int(radius_miles * 1609.34)

    # Resolve alias
    resolved_type = PLACE_TYPE_ALIASES.get(place_type.lower(), place_type.lower())

    data = _api_get(PLACES_URL, {
        "location": f"{lat},{lng}",
        "radius": str(min(radius_meters, 50000)),  # Max 50km
        "type": resolved_type,
    })

    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        return {"error": f"Places search failed: {data.get('status', 'UNKNOWN')}"}

    places = []
    for p in data.get("results", [])[:10]:
        place_loc = p.get("geometry", {}).get("location", {})
        places.append({
            "name": p.get("name", ""),
            "address": p.get("vicinity", ""),
            "rating": p.get("rating"),
            "total_ratings": p.get("user_ratings_total", 0),
            "open_now": p.get("opening_hours", {}).get("open_now"),
            "place_id": p.get("place_id", ""),
            "latitude": place_loc.get("lat"),
            "longitude": place_loc.get("lng"),
        })

    return {
        "search_location": geo["formatted_address"],
        "place_type": resolved_type,
        "radius_miles": radius_miles,
        "count": len(places),
        "places": places,
    }


async def search_nearby_places(
    location: str,
    place_type: str,
    radius_miles: int = 5,
) -> dict:
    """Find nearby places of a given type around a location.

    Args:
        location: Address or place name to search around.
        place_type: Type of place — pharmacy, hospital, grocery, restaurant, etc.
        radius_miles: Search radius in miles (default 5, max ~31).

    Called from execute_tool.
    """
    if not API_KEY:
        return {"error": "GOOGLE_MAPS_API_KEY not configured"}
    if not location or not place_type:
        return {"error": "Both location and place_type are required"}

    radius_miles = max(1, min(int(radius_miles or 5), 31))

    try:
        result = await asyncio.to_thread(
            _search_places, location.strip(), place_type.strip(), radius_miles
        )
        return {"success": "error" not in result, **result}
    except Exception as e:
        logger.error(f"Places search failed: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Distance Matrix (internal utility for shift filling)
# ---------------------------------------------------------------------------

def _distance_matrix(origins: list[str], destinations: list[str]) -> dict:
    """Get distance matrix between multiple origins and destinations.

    Returns dict mapping (origin_idx, dest_idx) to {distance_miles, duration_minutes}.
    Max 25 origins × 25 destinations per call.
    """
    data = _api_get(DISTANCE_MATRIX_URL, {
        "origins": "|".join(origins[:25]),
        "destinations": "|".join(destinations[:25]),
        "units": "imperial",
        "departure_time": "now",
    })

    if data.get("status") != "OK":
        return {"error": f"Distance matrix failed: {data.get('status', 'UNKNOWN')}"}

    results = {}
    for i, row in enumerate(data.get("rows", [])):
        for j, element in enumerate(row.get("elements", [])):
            if element.get("status") == "OK":
                results[f"{i},{j}"] = {
                    "distance_miles": round(element["distance"]["value"] / 1609.34, 1),
                    "duration_minutes": round(element["duration"]["value"] / 60, 1),
                    "distance_text": element["distance"]["text"],
                    "duration_text": element["duration"]["text"],
                }
            else:
                results[f"{i},{j}"] = {"error": element.get("status", "UNKNOWN")}

    return {
        "origins": data.get("origin_addresses", origins),
        "destinations": data.get("destination_addresses", destinations),
        "matrix": results,
    }


async def distance_matrix(origins: list[str], destinations: list[str]) -> dict:
    """Async wrapper for distance matrix. Internal utility."""
    if not API_KEY:
        return {"error": "GOOGLE_MAPS_API_KEY not configured"}
    return await asyncio.to_thread(_distance_matrix, origins, destinations)

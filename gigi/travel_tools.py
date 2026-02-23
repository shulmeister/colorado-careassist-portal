"""
Gigi Travel Tools — Flight, hotel, and car search.

Uses Amadeus Self-Service API for structured flight data.
Falls back to browse_with_claude for hotels, car rentals, or when API unavailable.

Env vars:
  AMADEUS_CLIENT_ID     — API key
  AMADEUS_CLIENT_SECRET — API secret
  AMADEUS_HOSTNAME      — "test" (default) or "production"
"""

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Amadeus SDK handles OAuth2 token refresh automatically
_amadeus_client = None


def _get_amadeus():
    """Lazy-init Amadeus client (SDK handles token caching + refresh)."""
    global _amadeus_client
    if _amadeus_client is not None:
        return _amadeus_client

    client_id = os.getenv("AMADEUS_CLIENT_ID", "")
    client_secret = os.getenv("AMADEUS_CLIENT_SECRET", "")
    hostname = os.getenv("AMADEUS_HOSTNAME", "test")

    if not client_id or not client_secret:
        logger.warning("Amadeus credentials not set — flight search will use browse fallback")
        return None

    try:
        from amadeus import Client
        _amadeus_client = Client(
            client_id=client_id,
            client_secret=client_secret,
            hostname=hostname,
        )
        logger.info(f"Amadeus client initialized (env: {hostname})")
        return _amadeus_client
    except Exception as e:
        logger.error(f"Failed to init Amadeus client: {e}")
        return None


def _parse_duration(iso_dur: str) -> str:
    """Convert ISO 8601 duration (PT12H30M) to readable string."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", iso_dur or "")
    if not match:
        return iso_dur or "unknown"
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    elif hours:
        return f"{hours}h"
    else:
        return f"{minutes}m"


async def _resolve_iata(query: str) -> Optional[str]:
    """Resolve a city/airport name to IATA code via Amadeus locations API."""
    # Already an IATA code
    if len(query) <= 3 and query.isalpha():
        return query.upper()

    amadeus = _get_amadeus()
    if not amadeus:
        return None

    try:
        import asyncio

        from amadeus import Location
        response = await asyncio.to_thread(
            amadeus.reference_data.locations.get,
            keyword=query,
            subType=Location.ANY,
        )
        if response.data:
            code = response.data[0].get("iataCode")
            logger.info(f"Resolved '{query}' → {code}")
            return code
    except Exception as e:
        logger.warning(f"IATA resolution failed for '{query}': {e}")
    return None


async def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    adults: int = 1,
    max_stops: int = None,
    sort: str = "price",
    limit: int = 5,
    currency: str = "USD",
) -> dict:
    """Search flights via Amadeus Flight Offers Search API.

    Args:
        origin: City name or IATA code (e.g., "Denver" or "DEN")
        destination: City name or IATA code (e.g., "Honolulu" or "HNL")
        departure_date: YYYY-MM-DD format
        return_date: Optional YYYY-MM-DD for round trip
        adults: Number of adult passengers
        max_stops: 0 = direct only, None = any
        sort: Sort by "price" or "duration"
        limit: Max results to return (max 250)
        currency: Currency code (default USD)

    Returns:
        Dict with flights list, each containing airline, price, duration, stops, times
    """
    amadeus = _get_amadeus()
    if not amadeus:
        return await _browse_flight_search(origin, destination, departure_date, return_date, adults)

    # Resolve city names to IATA codes
    origin_code = await _resolve_iata(origin) or origin.upper()
    dest_code = await _resolve_iata(destination) or destination.upper()

    params = {
        "originLocationCode": origin_code,
        "destinationLocationCode": dest_code,
        "departureDate": departure_date,
        "adults": adults,
        "currencyCode": currency,
        "max": min(limit, 250),
    }
    if return_date:
        params["returnDate"] = return_date
    if max_stops == 0:
        params["nonStop"] = "true"

    try:
        import asyncio
        response = await asyncio.to_thread(
            amadeus.shopping.flight_offers_search.get,
            **params,
        )

        # Extract carrier name lookup
        dictionaries = response.result.get("dictionaries", {})
        carriers = dictionaries.get("carriers", {})

        flights = []
        for offer in response.data[:limit]:
            itineraries = offer.get("itineraries", [])
            price_info = offer.get("price", {})

            # Build outbound info
            outbound = itineraries[0] if itineraries else {}
            out_segments = outbound.get("segments", [])

            if not out_segments:
                continue

            first_seg = out_segments[0]
            last_seg = out_segments[-1]
            stops = len(out_segments) - 1

            # Airline name from dictionary
            carrier_code = first_seg.get("carrierCode", "")
            airline_name = carriers.get(carrier_code, carrier_code)
            flight_num = f"{carrier_code}{first_seg.get('number', '')}"

            # Cabin class
            cabin = "ECONOMY"
            traveler_pricings = offer.get("travelerPricings", [])
            if traveler_pricings:
                fare_details = traveler_pricings[0].get("fareDetailsBySegment", [])
                if fare_details:
                    cabin = fare_details[0].get("cabin", "ECONOMY")

            flight = {
                "airline": airline_name,
                "flight_number": flight_num,
                "departure_airport": first_seg["departure"]["iataCode"],
                "departure_time": first_seg["departure"]["at"],
                "arrival_airport": last_seg["arrival"]["iataCode"],
                "arrival_time": last_seg["arrival"]["at"],
                "duration": _parse_duration(outbound.get("duration", "")),
                "stops": "Direct" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}",
                "price": f"${price_info.get('grandTotal', '?')} {currency}",
                "price_amount": float(price_info.get("grandTotal", 0)),
                "cabin": cabin,
                "seats_left": offer.get("numberOfBookableSeats"),
            }

            # Add return leg info if round trip
            if len(itineraries) > 1:
                ret = itineraries[1]
                ret_segs = ret.get("segments", [])
                if ret_segs:
                    flight["return_departure"] = ret_segs[0]["departure"]["at"]
                    flight["return_arrival"] = ret_segs[-1]["arrival"]["at"]
                    flight["return_duration"] = _parse_duration(ret.get("duration", ""))
                    flight["return_stops"] = len(ret_segs) - 1
                flight["type"] = "round-trip"

            flights.append(flight)

        return {
            "success": True,
            "source": "amadeus",
            "origin": origin_code,
            "destination": dest_code,
            "departure_date": departure_date,
            "return_date": return_date,
            "flights": flights,
            "total_results": len(flights),
            "currency": currency,
        }

    except Exception as e:
        logger.error(f"Amadeus flight search failed: {e}")
        return await _browse_flight_search(origin, destination, departure_date, return_date, adults)


async def _browse_flight_search(origin, destination, departure_date, return_date, adults) -> dict:
    """Fallback: use browse_with_claude to search Google Flights."""
    try:
        from gigi.claude_code_tools import browse_with_claude
        result = await browse_with_claude(
            f"Search for flights from {origin} to {destination} departing {departure_date}"
            + (f" returning {return_date}" if return_date else "")
            + f" for {adults} adult(s). "
            f"List the top 5 results with: airline, price, departure time, arrival time, duration, stops, and any booking link."
        )
        return {
            "success": True,
            "source": "google_flights_browse",
            "origin": origin,
            "destination": destination,
            "results": result,
        }
    except Exception as e:
        logger.error(f"Browse flight search fallback failed: {e}")
        return {"success": False, "error": f"Flight search unavailable. Error: {str(e)}"}


async def search_hotels(
    city: str,
    checkin: str,
    checkout: str,
    guests: int = 2,
    max_price: int = None,
    sort: str = "price",
    limit: int = 5,
    currency: str = "USD",
) -> dict:
    """Search hotels via browse_with_claude.

    Args:
        city: City name or IATA code
        checkin: Check-in date YYYY-MM-DD
        checkout: Check-out date YYYY-MM-DD
        guests: Number of guests
        max_price: Max price per night in cents (optional)
        sort: Sort by "price" or "rating"
        limit: Max results
        currency: Currency code
    """
    try:
        from gigi.claude_code_tools import browse_with_claude
        result = await browse_with_claude(
            f"Search for hotels in {city} checking in {checkin} and checking out {checkout} "
            f"for {guests} guests. "
            + (f"Max price ${max_price / 100} per night. " if max_price else "")
            + f"Sort by {sort}. List the top {limit} results with: hotel name, price per night, "
            f"star rating, location, and booking link. Use Google Hotels or Kayak."
        )
        return {
            "success": True,
            "source": "browse",
            "city": city,
            "checkin": checkin,
            "checkout": checkout,
            "results": result,
        }
    except Exception as e:
        logger.error(f"Hotel search failed: {e}")
        return {"success": False, "error": f"Hotel search unavailable. Error: {str(e)}"}


async def search_car_rentals(
    pickup_location: str,
    pickup_date: str,
    dropoff_date: str,
    dropoff_location: str = None,
    car_class: str = None,
) -> dict:
    """Search car rentals via browse_with_claude.

    Args:
        pickup_location: City or airport
        pickup_date: YYYY-MM-DD
        dropoff_date: YYYY-MM-DD
        dropoff_location: Optional different dropoff location
        car_class: Optional car class (economy, compact, midsize, full-size, SUV, luxury)
    """
    try:
        from gigi.claude_code_tools import browse_with_claude
        query = (
            f"Search for car rentals in {pickup_location} "
            f"picking up {pickup_date} and dropping off {dropoff_date}"
        )
        if dropoff_location:
            query += f" at {dropoff_location}"
        if car_class:
            query += f". Prefer {car_class} class."
        query += " List the top 5 results with: company, car type, price per day, total price, and booking link. Use Kayak or Google."

        result = await browse_with_claude(query)
        return {
            "success": True,
            "source": "browse",
            "pickup_location": pickup_location,
            "pickup_date": pickup_date,
            "dropoff_date": dropoff_date,
            "results": result,
        }
    except Exception as e:
        logger.error(f"Car rental search failed: {e}")
        return {"success": False, "error": f"Car rental search unavailable. Error: {str(e)}"}

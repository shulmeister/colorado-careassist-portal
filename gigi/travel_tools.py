"""
Gigi Travel Tools — Full Amadeus Self-Service API integration.

Uses Amadeus SDK v12.0.0 for flights, hotels, transfers, activities,
airport/airline info, travel insights, and booking management.
Falls back to browse_with_claude when API unavailable.

Env vars:
  AMADEUS_CLIENT_ID     — API key
  AMADEUS_CLIENT_SECRET — API secret
  AMADEUS_HOSTNAME      — "test" (default/sandbox) or "production"
"""

import asyncio
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

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
        logger.warning("Amadeus credentials not set — travel tools will use browse fallback")
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
    if len(query) <= 3 and query.isalpha():
        return query.upper()

    amadeus = _get_amadeus()
    if not amadeus:
        return None

    try:
        from amadeus import Location
        response = await asyncio.to_thread(
            amadeus.reference_data.locations.get,
            keyword=query,
            subType=Location.ANY,
        )
        if response.data:
            code = response.data[0].get("iataCode")
            logger.info(f"Resolved '{query}' -> {code}")
            return code
    except Exception as e:
        logger.warning(f"IATA resolution failed for '{query}': {e}")
    return None


async def _resolve_city_code(query: str) -> Optional[str]:
    """Resolve a city name to IATA city code for hotel searches."""
    if len(query) <= 3 and query.isalpha():
        return query.upper()

    amadeus = _get_amadeus()
    if not amadeus:
        return None

    try:
        response = await asyncio.to_thread(
            amadeus.reference_data.locations.cities.get,
            keyword=query,
        )
        if response.data:
            code = response.data[0].get("iataCode")
            logger.info(f"Resolved city '{query}' -> {code}")
            return code
    except Exception as e:
        logger.warning(f"City code resolution failed for '{query}': {e}")
    return None


# ============================================================
# FLIGHT SEARCH (upgraded — added travel_class param)
# ============================================================

async def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    adults: int = 1,
    max_stops: int = None,
    travel_class: str = None,
    sort: str = "price",
    limit: int = 5,
    currency: str = "USD",
) -> dict:
    """Search flights via Amadeus Flight Offers Search API."""
    amadeus = _get_amadeus()
    if not amadeus:
        return await _browse_flight_search(origin, destination, departure_date, return_date, adults)

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
    if travel_class:
        params["travelClass"] = travel_class.upper()

    try:
        response = await asyncio.to_thread(
            amadeus.shopping.flight_offers_search.get,
            **params,
        )

        dictionaries = response.result.get("dictionaries", {})
        carriers = dictionaries.get("carriers", {})

        flights = []
        for offer in response.data[:limit]:
            itineraries = offer.get("itineraries", [])
            price_info = offer.get("price", {})
            outbound = itineraries[0] if itineraries else {}
            out_segments = outbound.get("segments", [])
            if not out_segments:
                continue

            first_seg = out_segments[0]
            last_seg = out_segments[-1]
            stops = len(out_segments) - 1
            carrier_code = first_seg.get("carrierCode", "")
            airline_name = carriers.get(carrier_code, carrier_code)
            flight_num = f"{carrier_code}{first_seg.get('number', '')}"

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

        if not flights:
            # Sandbox returns empty data for real dates — fall back to browse
            logger.warning("Amadeus returned no flights (sandbox limitation?), falling back to browse")
            return await _browse_flight_search(origin, destination, departure_date, return_date, adults)

        return {"success": True, "source": "amadeus", "origin": origin_code, "destination": dest_code, "departure_date": departure_date, "return_date": return_date, "flights": flights, "total_results": len(flights), "currency": currency}

    except Exception as e:
        logger.error(f"Amadeus flight search failed: {e}")
        return await _browse_flight_search(origin, destination, departure_date, return_date, adults)


async def _browse_flight_search(origin, destination, departure_date, return_date, adults) -> dict:
    """Fallback flight search: Brave Search → Kayak direct URL browse."""
    # Step 1: Brave Search — fast, always available
    try:
        import httpx
        brave_api_key = os.getenv("BRAVE_API_KEY")
        if brave_api_key:
            trip_type = "round trip" if return_date else "one way"
            query = f"flights {origin} to {destination} {departure_date} {trip_type} cheapest price"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={"X-Subscription-Token": brave_api_key},
                    params={"q": query, "count": 5}
                )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for r in data.get("web", {}).get("results", [])[:5]:
                    results.append({
                        "title": r.get("title"),
                        "description": r.get("description"),
                        "url": r.get("url")
                    })
                if results:
                    return {
                        "success": True,
                        "source": "brave_search",
                        "origin": origin,
                        "destination": destination,
                        "departure_date": departure_date,
                        "results": results,
                        "note": "Web search results — click links for exact real-time pricing"
                    }
    except Exception as e:
        logger.warning(f"Brave flight search failed: {e}")

    # Step 2: Browse Kayak directly — real-time pricing via specific URL
    try:
        from gigi.claude_code_tools import browse_with_claude
        if return_date:
            kayak_url = f"https://www.kayak.com/flights/{origin}-{destination}/{departure_date}/{return_date}/{adults}adults"
        else:
            kayak_url = f"https://www.kayak.com/flights/{origin}-{destination}/{departure_date}/{adults}adults"
        result = await browse_with_claude(
            task="Extract the top 5 cheapest flight options shown on this page. For each flight include: airline, total price, departure time, arrival time, duration, and number of stops.",
            url=kayak_url
        )
        return {"success": True, "source": "kayak_browse", "origin": origin, "destination": destination, "results": result}
    except Exception as e:
        logger.error(f"Browse flight search fallback failed: {e}")
        return {"success": False, "error": f"Flight search unavailable: {str(e)}"}


# ============================================================
# HOTEL SEARCH (upgraded — Amadeus Hotel List + Offers)
# ============================================================

async def search_hotels(
    city: str, checkin: str, checkout: str, guests: int = 2,
    max_price: int = None, sort: str = "price", limit: int = 5, currency: str = "USD",
) -> dict:
    """Search hotels via Amadeus Hotel List + Hotel Offers Search APIs."""
    amadeus = _get_amadeus()
    if not amadeus:
        return await _browse_hotel_search(city, checkin, checkout, guests, max_price, sort, limit, currency)

    try:
        city_code = await _resolve_city_code(city) or city.upper()
        hotel_response = await asyncio.to_thread(amadeus.reference_data.locations.hotels.by_city.get, cityCode=city_code)
        if not hotel_response.data:
            return {"success": True, "source": "amadeus", "city": city_code, "hotels": [], "total_results": 0}

        hotel_ids = [h.get("hotelId") for h in hotel_response.data[:20] if h.get("hotelId")]
        if not hotel_ids:
            return {"success": True, "source": "amadeus", "city": city_code, "hotels": [], "total_results": 0}

        offers_response = await asyncio.to_thread(
            amadeus.shopping.hotel_offers_search.get,
            hotelIds=",".join(hotel_ids), adults=guests, checkInDate=checkin, checkOutDate=checkout, currency=currency,
        )

        hotels = []
        for hotel_data in offers_response.data[:limit]:
            hi = hotel_data.get("hotel", {})
            offers = hotel_data.get("offers", [])
            best = offers[0] if offers else {}
            pi = best.get("price", {})
            hotels.append({
                "name": hi.get("name", "Unknown"), "hotel_id": hi.get("hotelId", ""), "city": hi.get("cityCode", city_code),
                "latitude": hi.get("latitude"), "longitude": hi.get("longitude"),
                "price_per_night": f"${pi.get('total', '?')} {currency}" if pi else "N/A",
                "price_amount": float(pi.get("total", 0)) if pi.get("total") else None,
                "check_in": checkin, "check_out": checkout,
                "room_type": best.get("room", {}).get("description", {}).get("text", ""),
                "offer_id": best.get("id", ""),
                "cancellation": best.get("policies", {}).get("cancellation", {}).get("description", {}).get("text", ""),
            })
        if sort == "price":
            hotels.sort(key=lambda h: h.get("price_amount") or float("inf"))
        return {"success": True, "source": "amadeus", "city": city_code, "checkin": checkin, "checkout": checkout, "hotels": hotels[:limit], "total_results": len(hotels), "currency": currency}

    except Exception as e:
        logger.error(f"Amadeus hotel search failed: {e}")
        return await _browse_hotel_search(city, checkin, checkout, guests, max_price, sort, limit, currency)


async def _browse_hotel_search(city, checkin, checkout, guests, max_price, sort, limit, currency) -> dict:
    try:
        from gigi.claude_code_tools import browse_with_claude
        result = await browse_with_claude(
            f"Search for hotels in {city} checking in {checkin} and checking out {checkout} for {guests} guests. "
            + (f"Max price ${max_price / 100} per night. " if max_price else "")
            + f"Sort by {sort}. List the top {limit} results with: hotel name, price per night, star rating, location, and booking link."
        )
        return {"success": True, "source": "browse", "city": city, "checkin": checkin, "checkout": checkout, "results": result}
    except Exception as e:
        logger.error(f"Hotel search fallback failed: {e}")
        return {"success": False, "error": f"Hotel search unavailable. Error: {str(e)}"}


# ============================================================
# TRANSFER SEARCH (replaces search_car_rentals)
# ============================================================

async def search_transfers(
    start_location: str, end_location: str = None, start_date_time: str = "",
    passengers: int = 1, transfer_type: str = "PRIVATE",
    end_address: str = None, end_city: str = None, end_country: str = None,
) -> dict:
    """Search ground transfers via Amadeus Transfer Offers API."""
    amadeus = _get_amadeus()
    if not amadeus:
        return await _browse_transfer_search(start_location, end_location or end_address or end_city, start_date_time, passengers)

    try:
        body = {"startLocationCode": start_location.upper(), "transferType": transfer_type.upper(), "startDateTime": start_date_time, "passengers": passengers}
        if end_location and len(end_location) <= 4:
            body["endLocationCode"] = end_location.upper()
        else:
            if end_address:
                body["endAddressLine"] = end_address
            if end_city:
                body["endCityName"] = end_city
            if end_country:
                body["endCountryCode"] = end_country

        response = await asyncio.to_thread(amadeus.shopping.transfer_offers.post, body)
        transfers = []
        for offer in (response.data or [])[:10]:
            q = offer.get("quotation", {})
            transfers.append({
                "offer_id": offer.get("id", ""), "provider": offer.get("serviceProvider", {}).get("name", "Unknown"),
                "vehicle": offer.get("vehicle", {}).get("description", ""), "transfer_type": offer.get("transferType", ""),
                "price": f"${q.get('monetaryAmount', '?')} {q.get('currencyCode', 'USD')}", "price_amount": float(q.get("monetaryAmount", 0)),
                "currency": q.get("currencyCode", "USD"), "cancellation_type": offer.get("cancellationType", ""),
            })
        return {"success": True, "source": "amadeus", "start": start_location, "end": end_location or end_address or end_city, "transfers": transfers, "total_results": len(transfers)}

    except Exception as e:
        logger.error(f"Amadeus transfer search failed: {e}")
        return await _browse_transfer_search(start_location, end_location or end_address or end_city, start_date_time, passengers)


async def search_car_rentals(pickup_location: str, pickup_date: str, dropoff_date: str, dropoff_location: str = None, car_class: str = None) -> dict:
    """Legacy wrapper — redirects to search_transfers."""
    return await search_transfers(start_location=pickup_location, end_location=dropoff_location or pickup_location, start_date_time=f"{pickup_date}T10:00:00", passengers=2)


async def _browse_transfer_search(start, end, date_time, passengers) -> dict:
    try:
        from gigi.claude_code_tools import browse_with_claude
        result = await browse_with_claude(f"Search for ground transportation/transfers from {start} to {end} on {date_time} for {passengers} passenger(s). List the top 5 results with: provider, vehicle type, price, and booking link.")
        return {"success": True, "source": "browse", "results": result}
    except Exception as e:
        logger.error(f"Transfer search fallback failed: {e}")
        return {"success": False, "error": f"Transfer search unavailable. Error: {str(e)}"}


# ============================================================
# FLIGHT STATUS & DELAY PREDICTION
# ============================================================

async def get_flight_status(carrier_code: str, flight_number: str, departure_date: str, predict_delay: bool = True) -> dict:
    """Get real-time flight status and optional delay prediction."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    try:
        response = await asyncio.to_thread(amadeus.schedule.flights.get, carrierCode=carrier_code.upper(), flightNumber=str(flight_number), scheduledDepartureDate=departure_date)
        flights = []
        for flight in (response.data or []):
            points = flight.get("flightPoints", [])
            dep = points[0] if points else {}
            arr = points[-1] if len(points) > 1 else {}
            dep_timings = dep.get("departure", {}).get("timings", [])
            arr_timings = arr.get("arrival", {}).get("timings", [])
            flights.append({
                "carrier": flight.get("flightDesignator", {}).get("carrierCode", carrier_code),
                "flight_number": flight.get("flightDesignator", {}).get("number", flight_number),
                "departure_airport": dep.get("iataCode", ""), "departure_scheduled": dep_timings[0].get("value", "") if dep_timings else "",
                "arrival_airport": arr.get("iataCode", ""), "arrival_scheduled": arr_timings[0].get("value", "") if arr_timings else "",
                "aircraft": flight.get("legs", [{}])[0].get("aircraftEquipment", {}).get("aircraftType", "") if flight.get("legs") else "",
            })
        result = {"success": True, "source": "amadeus", "carrier": carrier_code.upper(), "flight_number": flight_number, "date": departure_date, "flights": flights}
        if predict_delay and flights:
            try:
                f = flights[0]
                dr = await asyncio.to_thread(amadeus.travel.predictions.flight_delay.get,
                    originLocationCode=f["departure_airport"], destinationLocationCode=f["arrival_airport"],
                    departureDate=departure_date, departureTime=(f.get("departure_scheduled", "") or "12:00:00")[:8],
                    arrivalDate=departure_date, arrivalTime=(f.get("arrival_scheduled", "") or "14:00:00")[:8],
                    aircraftCode=f.get("aircraft", "320") or "320", carrierCode=carrier_code.upper(),
                    flightNumber=str(flight_number), duration="PT2H")
                if dr.data:
                    result["delay_prediction"] = [{"result": p.get("result", ""), "probability": p.get("probability", "")} for p in dr.data]
            except Exception as e:
                logger.warning(f"Delay prediction failed: {e}")
                result["delay_prediction_error"] = str(e)
        return result
    except Exception as e:
        logger.error(f"Flight status lookup failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# EXPLORE FLIGHTS (inspiration + cheapest dates + price analysis)
# ============================================================

async def explore_flights(origin: str, destination: str = None, departure_date: str = None, currency: str = "USD") -> dict:
    """Explore flights: origin only=inspiration, +destination=cheapest dates, +date=price analysis."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    origin_code = await _resolve_iata(origin) or origin.upper()
    try:
        if not destination:
            response = await asyncio.to_thread(amadeus.shopping.flight_destinations.get, origin=origin_code)
            dests = [{"destination": d.get("destination", ""), "departure_date": d.get("departureDate", ""), "return_date": d.get("returnDate", ""),
                       "price": f"${d.get('price', {}).get('total', '?')} {currency}", "price_amount": float(d.get("price", {}).get("total", 0))} for d in (response.data or [])[:15]]
            return {"success": True, "source": "amadeus", "type": "inspiration", "origin": origin_code, "destinations": dests}

        dest_code = await _resolve_iata(destination) or destination.upper()
        if not departure_date:
            response = await asyncio.to_thread(amadeus.shopping.flight_dates.get, origin=origin_code, destination=dest_code)
            dates = [{"departure_date": d.get("departureDate", ""), "return_date": d.get("returnDate", ""),
                       "price": f"${d.get('price', {}).get('total', '?')} {currency}", "price_amount": float(d.get("price", {}).get("total", 0))} for d in (response.data or [])[:20]]
            return {"success": True, "source": "amadeus", "type": "cheapest_dates", "origin": origin_code, "destination": dest_code, "dates": dates}

        response = await asyncio.to_thread(amadeus.analytics.itinerary_price_metrics.get, originIataCode=origin_code, destinationIataCode=dest_code, departureDate=departure_date, currencyCode=currency)
        metrics = [{"quartile": pm.get("quartileRanking", ""), "amount": f"${pm.get('amount', '?')} {currency}"} for m in (response.data or []) for pm in m.get("priceMetrics", [])]
        return {"success": True, "source": "amadeus", "type": "price_analysis", "origin": origin_code, "destination": dest_code, "departure_date": departure_date, "price_metrics": metrics}
    except Exception as e:
        logger.error(f"Explore flights failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# CONFIRM FLIGHT PRICE & BRANDED FARES
# ============================================================

async def confirm_flight_price(flight_offer: dict, include_bags: bool = False, include_branded_fares: bool = False) -> dict:
    """Confirm pricing for a flight offer and optionally get branded fare upsells."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    try:
        kwargs = {}
        if include_bags:
            kwargs["include"] = "bags"
        response = await asyncio.to_thread(amadeus.shopping.flight_offers.pricing.post, flight_offer, **kwargs)
        pricing_data = response.data if response.data else {}
        fos = pricing_data.get("flightOffers", [])
        result = {"success": True, "source": "amadeus", "type": "price_confirmation", "confirmed_price": fos[0].get("price", {}) if fos else {}, "booking_requirements": pricing_data.get("bookingRequirements", {})}
        if include_branded_fares:
            try:
                ur = await asyncio.to_thread(amadeus.shopping.flight_offers.upselling.post, flight_offer)
                branded = []
                for offer in (ur.data or [])[:5]:
                    price = offer.get("price", {})
                    cabin, branded_name = "ECONOMY", ""
                    tp = offer.get("travelerPricings", [])
                    if tp:
                        fd = tp[0].get("fareDetailsBySegment", [])
                        if fd:
                            cabin = fd[0].get("cabin", "ECONOMY")
                            branded_name = fd[0].get("brandedFare", "")
                    branded.append({"cabin": cabin, "branded_fare": branded_name, "price": f"${price.get('grandTotal', '?')} {price.get('currency', 'USD')}", "price_amount": float(price.get("grandTotal", 0))})
                result["branded_fares"] = branded
            except Exception as e:
                logger.warning(f"Branded fares lookup failed: {e}")
                result["branded_fares_error"] = str(e)
        return result
    except Exception as e:
        logger.error(f"Flight price confirmation failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# SEATMAP
# ============================================================

async def get_seatmap(flight_offer: dict = None, flight_order_id: str = None) -> dict:
    """Get seatmap for a flight offer or booked order."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    try:
        if flight_order_id:
            response = await asyncio.to_thread(amadeus.shopping.seatmaps.get, flightOrderId=flight_order_id)
        elif flight_offer:
            response = await asyncio.to_thread(amadeus.shopping.seatmaps.post, flight_offer)
        else:
            return {"success": False, "error": "Provide flight_offer or flight_order_id"}
        seatmaps = []
        for sm in (response.data or []):
            seatmaps.append({"departure": sm.get("departure", {}).get("iataCode", ""), "arrival": sm.get("arrival", {}).get("iataCode", ""), "decks": len(sm.get("decks", []))})
        return {"success": True, "source": "amadeus", "seatmaps": seatmaps}
    except Exception as e:
        logger.error(f"Seatmap lookup failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# FLIGHT AVAILABILITY
# ============================================================

async def search_flight_availability(origin: str, destination: str, departure_date: str, adults: int = 1, travel_class: str = None) -> dict:
    """Search flight availability (seats per fare class)."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    origin_code = await _resolve_iata(origin) or origin.upper()
    dest_code = await _resolve_iata(destination) or destination.upper()
    try:
        body = {"originDestinations": [{"id": "1", "originLocationCode": origin_code, "destinationLocationCode": dest_code, "departureDateTime": {"date": departure_date}}],
                "travelers": [{"id": str(i + 1), "travelerType": "ADULT"} for i in range(adults)], "sources": ["GDS"]}
        if travel_class:
            body["searchCriteria"] = {"flightFilters": {"cabinRestrictions": [{"cabin": travel_class.upper(), "coverage": "MOST_SEGMENTS", "originDestinationIds": ["1"]}]}}
        response = await asyncio.to_thread(amadeus.shopping.availability.flight_availabilities.post, body)
        avails = []
        for avail in (response.data or [])[:10]:
            for seg in avail.get("segments", []):
                avails.append({"carrier": seg.get("carrierCode", ""), "flight_number": seg.get("number", ""),
                    "departure": seg.get("departure", {}).get("iataCode", ""), "arrival": seg.get("arrival", {}).get("iataCode", ""),
                    "departure_time": seg.get("departure", {}).get("at", ""),
                    "classes": [{"class": c.get("class", ""), "available_seats": c.get("numberOfBookableSeats", 0)} for c in seg.get("availabilityClasses", [])]})
        return {"success": True, "source": "amadeus", "origin": origin_code, "destination": dest_code, "date": departure_date, "availabilities": avails}
    except Exception as e:
        logger.error(f"Flight availability search failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# BOOK FLIGHT
# ============================================================

async def book_flight(flight_offer: dict, travelers: list) -> dict:
    """Create a flight order (booking). NOTE: Sandbox mode = test bookings only."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    hostname = os.getenv("AMADEUS_HOSTNAME", "test")
    if hostname == "test":
        logger.warning("book_flight called in SANDBOX mode")
    try:
        response = await asyncio.to_thread(amadeus.booking.flight_orders.post, flight_offer, travelers)
        order = response.data or {}
        return {"success": True, "source": "amadeus", "sandbox_mode": hostname == "test", "order_id": order.get("id", ""), "associated_records": order.get("associatedRecords", []), "price": order.get("flightOffers", [{}])[0].get("price", {})}
    except Exception as e:
        logger.error(f"Flight booking failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# MANAGE FLIGHT BOOKING
# ============================================================

async def manage_flight_booking(order_id: str, action: str = "get") -> dict:
    """Get or cancel a flight booking."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    try:
        if action == "cancel":
            await asyncio.to_thread(amadeus.booking.flight_order(order_id).delete)
            return {"success": True, "source": "amadeus", "action": "cancelled", "order_id": order_id}
        else:
            response = await asyncio.to_thread(amadeus.booking.flight_order(order_id).get)
            order = response.data or {}
            return {"success": True, "source": "amadeus", "action": "retrieved", "order_id": order.get("id", ""), "travelers": order.get("travelers", []),
                    "price": order.get("flightOffers", [{}])[0].get("price", {}), "itineraries": order.get("flightOffers", [{}])[0].get("itineraries", [])}
    except Exception as e:
        logger.error(f"Flight booking management failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# AIRPORT INFO
# ============================================================

async def get_airport_info(action: str, query: str = None, airport_code: str = None, latitude: float = None, longitude: float = None, date: str = None) -> dict:
    """Get airport/city info. Actions: search, nearest, routes, performance."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    try:
        if action == "search" and query:
            from amadeus import Location
            response = await asyncio.to_thread(amadeus.reference_data.locations.get, keyword=query, subType=Location.ANY)
            locs = [{"name": l.get("name", ""), "iata_code": l.get("iataCode", ""), "type": l.get("subType", ""), "city": l.get("address", {}).get("cityName", ""), "country": l.get("address", {}).get("countryCode", "")} for l in (response.data or [])[:10]]
            return {"success": True, "source": "amadeus", "action": "search", "locations": locs}
        elif action == "nearest" and latitude is not None and longitude is not None:
            response = await asyncio.to_thread(amadeus.reference_data.locations.airports.get, latitude=latitude, longitude=longitude)
            airports = [{"name": a.get("name", ""), "iata_code": a.get("iataCode", ""), "city": a.get("address", {}).get("cityName", ""), "distance": a.get("distance", {}).get("value", ""), "unit": a.get("distance", {}).get("unit", "")} for a in (response.data or [])[:5]]
            return {"success": True, "source": "amadeus", "action": "nearest", "airports": airports}
        elif action == "routes" and airport_code:
            response = await asyncio.to_thread(amadeus.airport.direct_destinations.get, departureAirportCode=airport_code.upper())
            dests = [{"destination": d.get("destination", ""), "name": d.get("name", "")} for d in (response.data or [])]
            return {"success": True, "source": "amadeus", "action": "routes", "airport": airport_code.upper(), "direct_destinations": dests, "total": len(dests)}
        elif action == "performance" and airport_code and date:
            response = await asyncio.to_thread(amadeus.airport.predictions.on_time.get, airportCode=airport_code.upper(), date=date)
            perf = response.data[0] if response.data else {}
            return {"success": True, "source": "amadeus", "action": "performance", "airport": airport_code.upper(), "date": date, "probability": perf.get("probability", ""), "result": perf.get("result", "")}
        else:
            return {"success": False, "error": f"Invalid action '{action}' or missing params"}
    except Exception as e:
        logger.error(f"Airport info lookup failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# AIRLINE INFO
# ============================================================

async def get_airline_info(action: str, airline_code: str, airport_code: str = None) -> dict:
    """Get airline info. Actions: lookup, routes, checkin."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    code = airline_code.upper()
    try:
        if action == "lookup":
            response = await asyncio.to_thread(amadeus.reference_data.airlines.get, airlineCodes=code)
            airlines = [{"iata_code": a.get("iataCode", ""), "icao_code": a.get("icaoCode", ""), "name": a.get("businessName", a.get("commonName", ""))} for a in (response.data or [])]
            return {"success": True, "source": "amadeus", "action": "lookup", "airlines": airlines}
        elif action == "routes":
            response = await asyncio.to_thread(amadeus.airline.destinations.get, airlineCode=code)
            dests = [{"destination": d.get("destination", ""), "name": d.get("name", "")} for d in (response.data or [])]
            return {"success": True, "source": "amadeus", "action": "routes", "airline": code, "destinations": dests, "total": len(dests)}
        elif action == "checkin":
            response = await asyncio.to_thread(amadeus.reference_data.urls.checkin_links.get, airlineCode=code)
            links = [{"channel": lnk.get("channel", ""), "url": lnk.get("href", "")} for lnk in (response.data or [])]
            return {"success": True, "source": "amadeus", "action": "checkin", "airline": code, "checkin_links": links}
        else:
            return {"success": False, "error": f"Invalid action '{action}'. Use: lookup, routes, checkin"}
    except Exception as e:
        logger.error(f"Airline info lookup failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# HOTEL RATINGS
# ============================================================

async def get_hotel_ratings(hotel_ids: str) -> dict:
    """Get hotel sentiment/rating analysis. hotel_ids: comma-separated (max 3)."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    try:
        response = await asyncio.to_thread(amadeus.e_reputation.hotel_sentiments.get, hotelIds=hotel_ids)
        ratings = [{"hotel_id": h.get("hotelId", ""), "overall_rating": h.get("overallRating", ""), "number_of_reviews": h.get("numberOfReviews", 0), "sentiments": h.get("sentiments", {})} for h in (response.data or [])]
        return {"success": True, "source": "amadeus", "ratings": ratings}
    except Exception as e:
        logger.error(f"Hotel ratings lookup failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# BOOK HOTEL
# ============================================================

async def book_hotel(offer_id: str, guests: list, payment: dict) -> dict:
    """Book a hotel room. NOTE: Sandbox mode = test bookings only."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    hostname = os.getenv("AMADEUS_HOSTNAME", "test")
    if hostname == "test":
        logger.warning("book_hotel called in SANDBOX mode")
    try:
        response = await asyncio.to_thread(amadeus.booking.hotel_orders.post, guests=guests,
            room_associations=[{"offerId": offer_id, "guestReferences": [{"guestReference": "1"}]}], payment=payment)
        order = response.data or {}
        return {"success": True, "source": "amadeus", "sandbox_mode": hostname == "test", "order_id": order.get("id", ""), "hotel": order.get("hotel", {})}
    except Exception as e:
        logger.error(f"Hotel booking failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# BOOK TRANSFER
# ============================================================

async def book_transfer(offer_id: str, passengers: list, payment: dict = None) -> dict:
    """Book a ground transfer. NOTE: Sandbox mode = test bookings only."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    hostname = os.getenv("AMADEUS_HOSTNAME", "test")
    if hostname == "test":
        logger.warning("book_transfer called in SANDBOX mode")
    try:
        body = {"passengers": passengers}
        if payment:
            body["payment"] = payment
        response = await asyncio.to_thread(amadeus.ordering.transfer_orders.post, body, offerId=offer_id)
        order = response.data or {}
        return {"success": True, "source": "amadeus", "sandbox_mode": hostname == "test", "order_id": order.get("id", ""), "status": order.get("status", "")}
    except Exception as e:
        logger.error(f"Transfer booking failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# MANAGE TRANSFER (cancellation)
# ============================================================

async def manage_transfer(order_id: str, confirm_number: str) -> dict:
    """Cancel a transfer booking."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    try:
        await asyncio.to_thread(amadeus.ordering.transfer_order(order_id).transfers.cancellation.post, {}, confirmNbr=confirm_number)
        return {"success": True, "source": "amadeus", "action": "cancelled", "order_id": order_id}
    except Exception as e:
        logger.error(f"Transfer cancellation failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# SEARCH ACTIVITIES (tours & activities)
# ============================================================

async def search_activities(city: str = None, latitude: float = None, longitude: float = None, radius: int = None) -> dict:
    """Search tours and activities at a destination."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    try:
        if city and latitude is None:
            from amadeus import Location
            loc_response = await asyncio.to_thread(amadeus.reference_data.locations.get, keyword=city, subType=Location.CITY)
            if loc_response.data:
                geo = loc_response.data[0].get("geoCode", {})
                latitude = geo.get("latitude")
                longitude = geo.get("longitude")
        if latitude is None or longitude is None:
            return {"success": False, "error": "Could not resolve location coordinates"}
        params = {"latitude": latitude, "longitude": longitude}
        if radius:
            params["radius"] = radius
        response = await asyncio.to_thread(amadeus.shopping.activities.get, **params)
        activities = []
        for a in (response.data or [])[:15]:
            activities.append({"id": a.get("id", ""), "name": a.get("name", ""), "description": (a.get("shortDescription") or a.get("description", ""))[:200],
                "rating": a.get("rating", ""), "price": f"${a.get('price', {}).get('amount', '?')} {a.get('price', {}).get('currencyCode', 'USD')}" if a.get("price") else "N/A",
                "booking_link": a.get("bookingLink", "")})
        return {"success": True, "source": "amadeus", "location": city or f"{latitude},{longitude}", "activities": activities, "total_results": len(activities)}
    except Exception as e:
        logger.error(f"Activities search failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# TRAVEL INSIGHTS
# ============================================================

async def get_travel_insights(action: str, origin: str = None, city: str = None, period: str = None,
    destination: str = None, departure_date: str = None, return_date: str = None, country_code: str = "US") -> dict:
    """Get travel insights. Actions: most_traveled, most_booked, busiest_period, recommendations, trip_purpose."""
    amadeus = _get_amadeus()
    if not amadeus:
        return {"success": False, "error": "Amadeus not configured"}
    try:
        if action == "most_traveled" and origin and period:
            response = await asyncio.to_thread(amadeus.travel.analytics.air_traffic.traveled.get, originCityCode=origin.upper(), period=period)
            dests = [{"destination": d.get("destination", ""), "score": d.get("analytics", {}).get("flights", {}).get("score", "")} for d in (response.data or [])[:15]]
            return {"success": True, "source": "amadeus", "action": action, "origin": origin.upper(), "period": period, "destinations": dests}
        elif action == "most_booked" and origin and period:
            response = await asyncio.to_thread(amadeus.travel.analytics.air_traffic.booked.get, originCityCode=origin.upper(), period=period)
            dests = [{"destination": d.get("destination", ""), "score": d.get("analytics", {}).get("travelers", {}).get("score", "")} for d in (response.data or [])[:15]]
            return {"success": True, "source": "amadeus", "action": action, "origin": origin.upper(), "period": period, "destinations": dests}
        elif action == "busiest_period" and city and period:
            from amadeus import Direction
            response = await asyncio.to_thread(amadeus.travel.analytics.air_traffic.busiest_period.get, cityCode=city.upper(), period=period, direction=Direction.ARRIVING)
            periods = [{"period": p.get("period", ""), "score": p.get("analytics", {}).get("travelers", {}).get("score", "")} for p in (response.data or [])]
            return {"success": True, "source": "amadeus", "action": action, "city": city.upper(), "year": period, "periods": periods}
        elif action == "recommendations" and origin:
            response = await asyncio.to_thread(amadeus.reference_data.recommended_locations.get, cityCodes=origin.upper(), travelerCountryCode=country_code)
            recs = [{"destination": r.get("iataCode", ""), "name": r.get("name", ""), "relevance": r.get("relevance", "")} for r in (response.data or [])[:10]]
            return {"success": True, "source": "amadeus", "action": action, "origin": origin.upper(), "recommendations": recs}
        elif action == "trip_purpose" and origin and destination and departure_date and return_date:
            oc = await _resolve_iata(origin) or origin.upper()
            dc = await _resolve_iata(destination) or destination.upper()
            response = await asyncio.to_thread(amadeus.travel.predictions.trip_purpose.get, originLocationCode=oc, destinationLocationCode=dc, departureDate=departure_date, returnDate=return_date)
            pred = response.data or {}
            return {"success": True, "source": "amadeus", "action": action, "purpose": pred.get("result", ""), "probability": pred.get("probability", "")}
        else:
            return {"success": False, "error": f"Invalid action '{action}' or missing params"}
    except Exception as e:
        logger.error(f"Travel insights failed: {e}")
        return {"success": False, "error": str(e)}

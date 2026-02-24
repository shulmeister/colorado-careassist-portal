import logging
import os
import uuid
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# In-memory session store for pending purchases
pending_sessions = {}

def send_2fa_text(message: str):
    """Send a confirmation text to Jason via RingCentral or Telegram"""
    # Using Telegram as the secondary 'secure' channel for 2FA
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8215335898")
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set - cannot send 2FA")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"🔐 GIGI 2FA REQUEST:\n\n{message}\n\nReply 'YES' to Gigi on the call to proceed."
    }
    try:
        requests.post(url, json=payload, timeout=5)
        logger.info(f"2FA text sent to Jason: {message[:50]}...")
    except Exception as e:
        logger.error(f"Failed to send 2FA text: {e}")

class ChiefOfStaffTools:
    def __init__(self):
        pass

    async def search_events(self, query: str = "", city: str = "Denver", state: str = "CO",
                           start_date: str = None, end_date: str = None, limit: int = 10):
        """Search events on Ticketmaster: concerts, sports, theater, comedy."""
        from datetime import timedelta

        import httpx

        api_key = os.environ.get("TICKETMASTER_API_KEY")
        if not api_key:
            logger.error("TICKETMASTER_API_KEY not configured")
            return {"success": False, "error": "Ticketmaster API not configured"}

        if not query:
            query = "all"

        # Default date range: today through next 30 days
        now = datetime.now()
        if not start_date:
            start_dt = now.strftime("%Y-%m-%dT00:00:00Z")
        else:
            start_dt = f"{start_date}T00:00:00Z"

        if not end_date:
            end_dt = (now + timedelta(days=30)).strftime("%Y-%m-%dT23:59:59Z")
        else:
            end_dt = f"{end_date}T23:59:59Z"

        params = {
            "apikey": api_key,
            "city": city,
            "stateCode": state,
            "startDateTime": start_dt,
            "endDateTime": end_dt,
            "size": min(limit, 20),
            "sort": "date,asc",
        }
        if query.lower() not in ("all", "events", "anything", ""):
            params["keyword"] = query

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("https://app.ticketmaster.com/discovery/v2/events.json", params=params)
                if resp.status_code != 200:
                    logger.error(f"Ticketmaster API error: {resp.status_code}")
                    return {"success": False, "error": f"Ticketmaster API returned {resp.status_code}"}

                data = resp.json()
                embedded = data.get("_embedded")
                if not embedded or "events" not in embedded:
                    return {"success": True, "events": [], "count": 0, "query": query, "city": city}

                events = []
                for ev in embedded["events"][:limit]:
                    name = ev.get("name", "Unknown Event")
                    event_date = ev.get("dates", {}).get("start", {}).get("localDate", "TBA")
                    event_time = ev.get("dates", {}).get("start", {}).get("localTime", "")
                    try:
                        dt = datetime.strptime(event_date, "%Y-%m-%d")
                        formatted_date = dt.strftime("%A, %B %d")
                    except Exception:
                        formatted_date = event_date

                    venues = ev.get("_embedded", {}).get("venues", [])
                    venue_name = venues[0].get("name", "Venue TBA") if venues else "Venue TBA"

                    price_range = ""
                    price_ranges = ev.get("priceRanges", [])
                    if price_ranges:
                        mn = price_ranges[0].get("min", 0)
                        mx = price_ranges[0].get("max", 0)
                        if mn and mx:
                            price_range = f"${mn:.0f}-${mx:.0f}"
                        elif mn:
                            price_range = f"from ${mn:.0f}"

                    status = ev.get("dates", {}).get("status", {}).get("code", "")
                    url = ev.get("url", "")

                    events.append({
                        "name": name,
                        "date": formatted_date,
                        "raw_date": event_date,
                        "time": event_time,
                        "venue": venue_name,
                        "price_range": price_range,
                        "url": url,
                        "status": status,
                    })

                return {"success": True, "events": events, "count": len(events), "query": query, "city": city}

        except Exception as e:
            logger.error(f"Ticketmaster search failed: {e}")
            return {"success": False, "error": str(e)}

    async def search_concerts(self, query: str = ""):
        """Search concerts — wrapper for search_events."""
        return await self.search_events(query=query if query else "concerts")

    async def buy_tickets_request(self, artist: str, venue: str, quantity: int = 2):
        """Search for real ticket availability, then send 2FA with actual options."""
        session_id = str(uuid.uuid4())[:8]

        # Use browse_with_claude to search Ticketmaster/AXS for real availability
        try:
            from gigi.claude_code_tools import browse_with_claude
            browse_result = await browse_with_claude(
                task=(
                    f"Search for {quantity} tickets to {artist} at {venue}. "
                    f"Go to ticketmaster.com and search for '{artist} {venue}'. "
                    f"Find available dates and ticket prices. "
                    f"List: date, section/seat options, and price per ticket. "
                    f"If no Ticketmaster results, try axs.com. "
                    f"Do NOT purchase anything — just gather availability info."
                )
            )
            availability_info = browse_result.get("result", "Could not find ticket information.")
        except Exception as e:
            logger.error(f"Ticket search browse failed: {e}")
            availability_info = f"Search failed: {str(e)}"

        # Save to pending sessions with REAL availability data
        pending_sessions[session_id] = {
            "type": "tickets",
            "artist": artist,
            "venue": venue,
            "quantity": quantity,
            "availability": availability_info,
            "timestamp": datetime.now().isoformat()
        }

        # Send 2FA with REAL availability info
        send_2fa_text(
            f"Ticket search results for {artist} at {venue} ({quantity} tickets):\n\n"
            f"{availability_info[:500]}\n\n"
            f"Reply YES to Gigi to proceed with purchase."
        )

        return {
            "success": True,
            "session_id": session_id,
            "availability": availability_info,
            "message": f"I found ticket options for {artist} at {venue}. I've sent the details to your phone — review and confirm if you'd like me to proceed.",
            "requires_2fa": True
        }

    async def book_table_request(self, restaurant: str, party_size: int, date: str, time: str):
        """Search OpenTable for real availability, then send 2FA with actual options."""
        session_id = str(uuid.uuid4())[:8]

        # Use browse_with_claude to search OpenTable for real availability
        try:
            from gigi.claude_code_tools import browse_with_claude
            browse_result = await browse_with_claude(
                task=(
                    f"Search for a restaurant reservation on OpenTable. "
                    f"Go to opentable.com and search for '{restaurant}' near Denver, CO. "
                    f"Look for availability on {date} at {time} for {party_size} people. "
                    f"List available time slots and any notes about the restaurant. "
                    f"If not on OpenTable, try resy.com or the restaurant's own website. "
                    f"Do NOT make a reservation — just check availability."
                )
            )
            availability_info = browse_result.get("result", "Could not find availability.")
        except Exception as e:
            logger.error(f"Restaurant search browse failed: {e}")
            availability_info = f"Search failed: {str(e)}"

        # Save to pending sessions with REAL availability data
        pending_sessions[session_id] = {
            "type": "restaurant",
            "restaurant": restaurant,
            "party_size": party_size,
            "date": date,
            "time": time,
            "availability": availability_info,
            "timestamp": datetime.now().isoformat()
        }

        # Send 2FA with REAL availability
        send_2fa_text(
            f"Restaurant search for {restaurant} ({party_size} people, {date} at {time}):\n\n"
            f"{availability_info[:500]}\n\n"
            f"Reply YES to Gigi to proceed with booking."
        )

        return {
            "success": True,
            "session_id": session_id,
            "availability": availability_info,
            "message": f"I checked {restaurant} for {date} at {time}. I've sent the availability details to your phone — confirm and I'll complete the reservation.",
            "requires_2fa": True
        }

    async def confirm_purchase(self, session_id: str):
        """Finalize the purchase/booking after user confirms."""
        session = pending_sessions.get(session_id)
        if not session:
            return {"success": False, "error": "Session not found or expired"}

        session_type = session.get("type", "unknown")
        logger.info(f"CONFIRMED: Executing {session_type} automation for {session_id}")

        try:
            from gigi.claude_code_tools import browse_with_claude

            if session_type == "restaurant":
                result = await browse_with_claude(
                    task=(
                        f"Complete a restaurant reservation on OpenTable (or resy.com if not on OpenTable). "
                        f"Restaurant: {session.get('restaurant')}. "
                        f"Date: {session.get('date')}, Time: {session.get('time')}, "
                        f"Party size: {session.get('party_size')}. "
                        f"Make the reservation. Use name: Jason Schulmeister, email: jason@coloradocareassist.com, phone: 603-997-1495. "
                        f"Take a screenshot of the confirmation. "
                        f"If it asks for a credit card, STOP and report back."
                    )
                )
                confirmation = result.get("result", "Reservation attempt completed.")

            elif session_type == "tickets":
                result = await browse_with_claude(
                    task=(
                        f"Purchase tickets on Ticketmaster or AXS. "
                        f"Artist: {session.get('artist')}, Venue: {session.get('venue')}, "
                        f"Quantity: {session.get('quantity')}. "
                        f"Navigate to the ticket page and add tickets to cart. "
                        f"Proceed to checkout. If it requires login, log in with jason@coloradocareassist.com. "
                        f"STOP at the payment page — take a screenshot showing the total and payment form. "
                        f"Do NOT enter payment info or complete the purchase."
                    )
                )
                confirmation = result.get("result", "Ticket checkout prepared.")

            else:
                confirmation = "Unknown session type."

            # Send confirmation to Telegram
            send_2fa_text(f"Booking/purchase update:\n\n{confirmation[:500]}")

            # Clean up
            del pending_sessions[session_id]

            return {
                "success": True,
                "message": confirmation,
            }

        except Exception as e:
            logger.error(f"Confirm purchase failed: {e}")
            return {
                "success": False,
                "error": f"Automation failed: {str(e)}. I'll need to do this manually."
            }

    async def watch_tickets(self, artist: str, venue: str = None, city: str = "Denver"):
        """Create a ticket watch — monitors Ticketmaster/AXS for on-sale dates."""
        import asyncio

        from gigi.ticket_monitor import create_watch
        return await asyncio.to_thread(create_watch, artist, venue, city)

    async def list_ticket_watches(self):
        """List all active ticket watches."""
        import asyncio

        from gigi.ticket_monitor import list_watches
        return await asyncio.to_thread(list_watches)

    async def remove_ticket_watch(self, watch_id: int):
        """Remove a ticket watch."""
        import asyncio

        from gigi.ticket_monitor import remove_watch
        return await asyncio.to_thread(remove_watch, int(watch_id))

    async def explore_national_parks(self, action: str = "parks", query: str = None,
                                     park_code: str = None, state: str = None, limit: int = 5):
        """Search the National Park Service API. Actions: parks, campgrounds, alerts,
        thingstodo, visitorcenters, events, tours, webcams, amenities, fees."""
        import httpx

        api_key = os.environ.get("NPS_API_KEY")
        if not api_key:
            return {"success": False, "error": "NPS_API_KEY not configured"}

        base = "https://developer.nps.gov/api/v1"
        params = {"api_key": api_key, "limit": min(limit, 20)}

        if park_code:
            params["parkCode"] = park_code
        if state:
            params["stateCode"] = state
        if query and action == "parks":
            params["q"] = query

        # Map action to endpoint
        endpoints = {
            "parks": "parks", "campgrounds": "campgrounds", "alerts": "alerts",
            "thingstodo": "thingstodo", "visitorcenters": "visitorcenters",
            "events": "events", "tours": "tours", "webcams": "webcams",
            "amenities": "amenities", "fees": "feespasses",
        }
        endpoint = endpoints.get(action)
        if not endpoint:
            return {"success": False, "error": f"Unknown action '{action}'. Use: {', '.join(endpoints.keys())}"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{base}/{endpoint}", params=params)
                if resp.status_code != 200:
                    return {"success": False, "error": f"NPS API returned {resp.status_code}"}

                data = resp.json()
                items = data.get("data", [])
                total = data.get("total", "0")

                if action == "parks":
                    results = [{"name": p.get("fullName", ""), "code": p.get("parkCode", ""),
                                "description": p.get("description", "")[:200], "state": p.get("states", ""),
                                "activities": [a["name"] for a in p.get("activities", [])[:8]],
                                "url": p.get("url", ""),
                                "directions": p.get("directionsInfo", "")[:150],
                                "fees": [{"title": f.get("title", ""), "cost": f.get("cost", "")} for f in p.get("entranceFees", [])[:3]],
                                } for p in items]
                elif action == "campgrounds":
                    results = [{"name": c.get("name", ""), "description": c.get("description", "")[:150],
                                "total_sites": c.get("campsites", {}).get("totalSites", ""),
                                "reservable": c.get("reservationInfo", "")[:100],
                                "fees": [f.get("cost", "") for f in c.get("fees", [])],
                                "amenities": {k: v for k, v in c.get("amenities", {}).items() if v and v not in ("0", "", "No")},
                                "url": c.get("reservationUrl") or c.get("url", ""),
                                } for c in items]
                elif action == "alerts":
                    results = [{"title": a.get("title", ""), "category": a.get("category", ""),
                                "description": a.get("description", "")[:200],
                                "url": a.get("url", "")} for a in items]
                elif action == "thingstodo":
                    results = [{"title": t.get("title", ""), "description": t.get("shortDescription", "")[:150],
                                "activities": [a["name"] for a in t.get("activities", [])[:5]],
                                "duration": t.get("duration", ""), "url": t.get("url", "")} for t in items]
                elif action == "visitorcenters":
                    results = [{"name": v.get("name", ""), "description": v.get("description", "")[:150],
                                "directions": v.get("directionsInfo", "")[:100],
                                "url": v.get("url", "")} for v in items]
                elif action == "events":
                    results = [{"title": e.get("title", ""), "date": e.get("dateStart", ""),
                                "time": e.get("times", [{}])[0].get("timeStart", "") if e.get("times") else "",
                                "description": e.get("description", "")[:150],
                                "location": e.get("location", ""), "fee": e.get("feeInfo", "")} for e in items]
                elif action == "tours":
                    results = [{"title": t.get("title", ""), "description": t.get("description", "")[:150],
                                "duration": t.get("duration", ""),
                                "activities": [a["name"] for a in t.get("activities", [])[:5]]} for t in items]
                elif action == "webcams":
                    results = [{"title": w.get("title", ""), "description": w.get("description", "")[:100],
                                "url": w.get("url", ""), "status": w.get("status", "")} for w in items]
                elif action == "amenities":
                    results = [{"name": a.get("name", ""), "parks": [p.get("parkCode", "") for p in a.get("parks", [])[:5]]} for a in items]
                elif action == "fees":
                    results = items[:limit]
                else:
                    results = items[:limit]

                return {"success": True, "action": action, "total": total, "count": len(results),
                        "park_code": park_code, "results": results}

        except Exception as e:
            logger.error(f"NPS API failed: {e}")
            return {"success": False, "error": str(e)}

# Singleton
cos_tools = ChiefOfStaffTools()

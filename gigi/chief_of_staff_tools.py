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

    async def search_concerts(self, query: str = ""):
        """Search upcoming concerts using real web search"""
        if not query:
            query = "upcoming concerts Denver Colorado"

        search_query = f"{query} concerts tickets 2026"

        # Try Brave Search first
        try:
            import httpx
            brave_api_key = os.environ.get("BRAVE_API_KEY")
            if brave_api_key:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        headers={"X-Subscription-Token": brave_api_key},
                        params={"q": search_query, "count": 5},
                    )
                    if resp.status_code == 200:
                        results = resp.json().get("web", {}).get("results", [])
                        if results:
                            matches = [{"title": r.get("title", ""), "snippet": r.get("description", ""), "url": r.get("url", "")} for r in results[:5]]
                            return {"success": True, "query": query, "matches": matches}
        except Exception as e:
            logger.warning(f"Brave concert search failed: {e}")

        # Fallback: DuckDuckGo
        try:
            from ddgs import DDGS
            results = DDGS().text(search_query, max_results=5)
            if results:
                matches = [{"title": r.get("title", ""), "snippet": r.get("body", ""), "url": r.get("href", "")} for r in results]
                return {"success": True, "query": query, "matches": matches}
        except Exception as e:
            logger.warning(f"DDG concert search failed: {e}")

        return {"success": False, "error": "Concert search temporarily unavailable"}

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

# Singleton
cos_tools = ChiefOfStaffTools()

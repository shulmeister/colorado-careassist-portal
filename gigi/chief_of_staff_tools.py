import logging
import os
import uuid
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# Paths to existing automation tools
BUYING_AUTO_PATH = "/Users/shulmeister/mac-mini-apps/clawd/tools/buying-automation"
CONCERT_ALERTS_PATH = "/Users/shulmeister/mac-mini-apps/clawd/tools/concert-alerts"

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
        """Initiate ticket purchase and send 2FA confirmation"""
        session_id = str(uuid.uuid4())[:8]

        details = f"Buy {quantity} tickets for {artist} at {venue}."

        # Save to pending sessions
        pending_sessions[session_id] = {
            "type": "tickets",
            "artist": artist,
            "venue": venue,
            "quantity": quantity,
            "timestamp": datetime.now().isoformat()
        }

        # Send 2FA text
        send_2fa_text(f"Gigi is about to buy {quantity} tickets for {artist} at {venue}. Is this okay?")

        return {
            "success": True,
            "session_id": session_id,
            "message": f"I've initiated the request for {artist} tickets and sent a confirmation text to your phone. Please confirm if I should proceed with the purchase.",
            "requires_2fa": True
        }

    async def book_table_request(self, restaurant: str, party_size: int, date: str, time: str):
        """Initiate restaurant reservation and send 2FA confirmation"""
        session_id = str(uuid.uuid4())[:8]

        # Save to pending sessions
        pending_sessions[session_id] = {
            "type": "restaurant",
            "restaurant": restaurant,
            "party_size": party_size,
            "date": date,
            "time": time,
            "timestamp": datetime.now().isoformat()
        }

        # Send 2FA text
        send_2fa_text(f"Gigi is booking a table for {party_size} at {restaurant} on {date} at {time}. OK?")

        return {
            "success": True,
            "session_id": session_id,
            "message": f"I'm working on that {restaurant} reservation for {party_size}. I've sent a quick confirmation text to your phone just to be sure.",
            "requires_2fa": True
        }

    async def confirm_purchase(self, session_id: str):
        """Finalize the purchase after user says 'Yes' on the call"""
        session = pending_sessions.get(session_id)
        if not session:
            return {"success": False, "error": "Session not found or expired"}

        # HERE IS WHERE WE WOULD TRIGGER THE PLAYWRIGHT/BROWSER AUTOMATION
        # For this phase, we'll simulate the successful automation trigger

        logger.info(f"CONFIRMED: Executing automation for {session_id}")

        # Clean up
        del pending_sessions[session_id]

        return {
            "success": True,
            "message": "Excellent. I'm processing that now and will send you the confirmation screenshot once it's done."
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

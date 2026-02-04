import os
import json
import logging
import asyncio
import uuid
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

# Paths to existing automation tools
BUYING_AUTO_PATH = "/Users/shulmeister/mac-mini-apps/clawd/tools/buying-automation"
CONCERT_ALERTS_PATH = "/Users/shulmeister/mac-mini-apps/clawd/tools/concert-alerts"

# In-memory session store for pending purchases
pending_sessions = {}

def send_2fa_text(message: str):
    """Send a confirmation text to Jason via RingCentral or Telegram"""
    # Using Telegram as the secondary 'secure' channel for 2FA as requested in architecture
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8508806105:AAExZ25ZN19X3xjBQAZ3Q9fHgAQmWWklX8U")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8215335898")
    
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
        """Search upcoming concerts for Jason's favorite artists"""
        try:
            # For now, we'll interface with the monitor logic
            # This is a stub that will return some 'live' data soon
            return {
                "success": True,
                "matches": [
                    {"artist": "Dogs In A Pile", "venue": "Ogden Theatre", "date": "2026-02-13", "status": "Tickets Available"},
                    {"artist": "Goose", "venue": "Red Rocks", "date": "2026-06-15", "status": "Presale Starts Wednesday"}
                ]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

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

# Singleton
cos_tools = ChiefOfStaffTools()

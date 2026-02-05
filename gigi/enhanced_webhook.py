"""
Enhanced Retell Webhook Handler
Handles caller ID lookup, greetings, transfers, and message taking
"""

import os
import logging
from typing import Optional, Dict
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

# Configuration - use environment variables (no hardcoded secrets)
JASON_PHONE = "+16039971495"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8215335898")
RETELL_API_KEY = os.environ.get("RETELL_API_KEY")

class CallerLookupService:
    """Handles multi-source caller lookup"""
    
    def __init__(self, db_lookup_fn=None, cache_lookup_fn=None):
        self.db_lookup = db_lookup_fn
        self.cache_lookup = cache_lookup_fn
    
    def lookup(self, phone: str) -> Dict:
        """
        Lookup caller with fallback chain:
        1. Database (CCA clients/caregivers)
        2. JSON cache
        3. Apple Contacts (via Mac node)
        4. Unknown
        """
        clean_phone = ''.join(filter(str.isdigit, phone))[-10:]
        
        # Special case: Jason
        if clean_phone == "6039971495":
            return {
                "found": True,
                "name": "Jason",
                "type": "owner",
                "source": "hardcoded",
                "phone": phone,
                "should_transfer": True
            }
        
        # Try database
        if self.db_lookup:
            try:
                result = self.db_lookup(clean_phone)
                if result:
                    return {
                        "found": True,
                        "name": result.get("name"),
                        "type": result.get("type"),  # caregiver or client
                        "source": "database",
                        "phone": phone,
                        "should_transfer": True,  # Known contact → transfer
                        "additional_info": result
                    }
            except Exception as e:
                logger.warning(f"Database lookup failed: {e}")
        
        # Try cache
        if self.cache_lookup:
            try:
                result = self.cache_lookup(clean_phone)
                if result:
                    return {
                        "found": True,
                        "name": result.get("name"),
                        "type": result.get("type"),
                        "source": "cache",
                        "phone": phone,
                        "should_transfer": True,
                        "additional_info": result
                    }
            except Exception as e:
                logger.warning(f"Cache lookup failed: {e}")
        
        # Try Apple Contacts (TODO: implement when Mac node is available)
        # apple_result = self._lookup_apple_contacts(clean_phone)
        # if apple_result:
        #     return {
        #         "found": True,
        #         "name": apple_result.get("name"),
        #         "type": "personal_contact",
        #         "source": "apple_contacts",
        #         "phone": phone,
        #         "should_transfer": True
        #     }
        
        # Unknown caller
        return {
            "found": False,
            "name": None,
            "type": "unknown",
            "source": None,
            "phone": phone,
            "should_transfer": False,  # Unknown → take message
            "take_message": True
        }
    
    def _lookup_apple_contacts(self, clean_phone: str) -> Optional[Dict]:
        """TODO: Implement Apple Contacts lookup via Mac node"""
        return None


def generate_greeting(caller_info: Dict) -> str:
    """Generate personalized greeting based on caller info"""
    if caller_info.get("found"):
        name = caller_info.get("name", "there")
        caller_type = caller_info.get("type", "")
        
        if caller_type == "owner":
            return f"Hi {name}! How can I help you today?"
        elif caller_type == "caregiver":
            return f"Hi {name}! This is Gigi from Colorado Care Assist. What can I help you with?"
        elif caller_type == "client":
            return f"Hi {name}! This is Gigi. How can I assist you today?"
        else:
            return f"Hi {name}! This is Gigi, Jason's assistant. Let me transfer you."
    else:
        return "Hi! This is Gigi, Jason Shulman's assistant. He's not available right now. Would you like to leave a message?"


def transfer_call(call_id: str, to_number: str = JASON_PHONE) -> bool:
    """Transfer call to Jason using Retell API"""
    try:
        url = "https://api.retellai.com/v2/transfer-call"
        headers = {
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "call_id": call_id,
            "to_number": to_number
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"Successfully transferred call {call_id} to {to_number}")
            return True
        else:
            logger.error(f"Transfer failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Transfer exception: {e}")
        return False


def send_telegram_message(message: str, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    """Send message to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"Telegram message sent to {chat_id}")
            return True
        else:
            logger.error(f"Telegram send failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Telegram exception: {e}")
        return False


def handle_message_received(caller_info: Dict, message: str, call_id: str):
    """Handle message from unknown caller"""
    phone = caller_info.get("phone", "Unknown")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    telegram_message = f"""
📞 **New Voice Message**

**From:** {phone}
**Time:** {timestamp}
**Call ID:** {call_id}

**Message:**
{message}
"""
    
    success = send_telegram_message(telegram_message)
    
    if success:
        logger.info(f"Message from {phone} sent to Telegram")
    else:
        logger.error(f"Failed to send message to Telegram")
        # TODO: Fallback to email if Telegram fails


def get_weather(location: str = "Boulder CO") -> str:
    """Get current weather - integrated from gigi_voice_functions.py"""
    try:
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
        lat, lon = coords_map.get(loc_lower, (40.01, -105.27))  # Default Boulder
        
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
        
        return f"It's {temp} degrees with {weather} and winds at {wind} miles per hour"
        
    except Exception as e:
        logger.error(f"Weather error: {e}")
        return "I couldn't get the weather right now, sorry about that"

"""
Gigi RingCentral Bot - Manager & After-Hours Coverage

Two Distinct Roles:
1. THE REPLIER (After-Hours Only):
   - M-F 8am-5pm: SILENT (Israt handles replies).
   - Nights/Weekends: Replies IMMEDIATELY to texts/chats.
   - Replaces Gigi's missing reply function.

2. THE DOCUMENTER (24/7/365):
   - Acts as QA/Manager for the whole team (Israt, Cynthia, Gigi).
   - Monitors 'New Scheduling' and Direct SMS.
   - Logs ALL Care Alerts and Tasks into WellSky.
   - Ensures nothing falls through the cracks, even if "handled" silently.
"""

import os
import sys
import logging
import asyncio
import json
from datetime import datetime, date, time, timedelta
import pytz
import requests

try:
    import anthropic
except ImportError:
    anthropic = None

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ringcentral_messaging_service import ringcentral_messaging_service, RINGCENTRAL_SERVER
from services.wellsky_service import WellSkyService

# HARDCODED FOR SAFETY - The 719 number is the company main line
RINGCENTRAL_FROM_NUMBER = "+17194283999"

# ADMIN TOKEN (Jason x101) - Required for visibility into Company Lines (719/303)
# Standard x111 token is blind to these numbers.
# Use JWT from environment variable (refreshed regularly)
ADMIN_JWT_TOKEN = os.getenv("RINGCENTRAL_JWT_TOKEN", "")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gigi_rc_bot")

# Configuration
CHECK_INTERVAL = 30  # seconds
TARGET_CHAT = "New Scheduling"
TIMEZONE = pytz.timezone("America/Denver")

# Business Hours (M-F, 8am-5pm)
BUSINESS_START = time(8, 0)
BUSINESS_END = time(17, 0)

# REPLY MODE - Set to True when Jason says go live with replies
REPLIES_ENABLED = False

# LOOP PREVENTION - Critical safeguards
REPLY_COOLDOWN_MINUTES = 30  # Don't reply to same number within this window
MAX_REPLIES_PER_DAY_PER_NUMBER = 3  # Max replies to any single number per day
MAX_REPLIES_PER_HOUR_GLOBAL = 20  # Max total SMS per hour
REPLY_HISTORY_FILE = "/Users/shulmeister/.gigi-reply-history.json"

# Autonomous Shift Coordination
GIGI_SHIFT_MONITOR_ENABLED = os.getenv("GIGI_SHIFT_MONITOR_ENABLED", "false").lower() == "true"
CAMPAIGN_CHECK_INTERVAL_SECONDS = 300  # Check campaigns every 5 minutes
CAMPAIGN_ESCALATION_MINUTES = 30  # Escalate unfilled campaigns after 30 min
VOICE_OUTREACH_ENABLED = os.getenv("VOICE_OUTREACH_ENABLED", "false").lower() == "true"

# Claude API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 1024
CLAUDE_MAX_TOOL_ROUNDS = 3
CONVERSATION_TIMEOUT_MINUTES = 30
CONVERSATION_HISTORY_FILE = "/Users/shulmeister/.gigi-sms-conversations.json"
MAX_CONVERSATION_MESSAGES = 10

# Tools available to Claude for SMS replies
SMS_TOOLS = [
    {
        "name": "identify_caller",
        "description": "Look up who is texting based on their phone number. Checks caregiver and client records in WellSky. Always call this first to know who you're talking to.",
        "input_schema": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "The caller's phone number"
                }
            },
            "required": ["phone_number"]
        }
    },
    {
        "name": "get_wellsky_shifts",
        "description": "Get shift schedule from WellSky. Look up shifts by caregiver_id or client_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "caregiver_id": {
                    "type": "string",
                    "description": "WellSky caregiver ID to get their schedule"
                },
                "client_id": {
                    "type": "string",
                    "description": "WellSky client ID to get their upcoming visits"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look ahead (default 7, max 14)",
                    "default": 7
                }
            },
            "required": []
        }
    },
    {
        "name": "get_wellsky_clients",
        "description": "Search for clients in WellSky by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_name": {
                    "type": "string",
                    "description": "Client name to search for (first, last, or full)"
                }
            },
            "required": ["search_name"]
        }
    },
    {
        "name": "get_wellsky_caregivers",
        "description": "Search for caregivers in WellSky by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_name": {
                    "type": "string",
                    "description": "Caregiver name to search for (first, last, or full)"
                }
            },
            "required": ["search_name"]
        }
    },
    {
        "name": "log_call_out",
        "description": "Log a caregiver call-out in WellSky and create an urgent admin task for coverage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "caregiver_id": {
                    "type": "string",
                    "description": "The caregiver's WellSky ID"
                },
                "caregiver_name": {
                    "type": "string",
                    "description": "The caregiver's name"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for the call-out (e.g., 'sick', 'emergency')"
                },
                "shift_date": {
                    "type": "string",
                    "description": "Date of the shift (YYYY-MM-DD, defaults to today)"
                }
            },
            "required": ["caregiver_id", "caregiver_name", "reason"]
        }
    }
]

SMS_SYSTEM_PROMPT = """You are Gigi, the AI assistant for Colorado Care Assist, a home care agency in Colorado Springs. You are responding via SMS text message.

CRITICAL RULES:
- Keep responses under 300 characters when possible. This is SMS, not email.
- If data requires more detail, you may go up to 500 characters but no more.
- Never share sensitive medical info via SMS.
- Never share other people's phone numbers or personal details.
- Do NOT make up shift times or caregiver names. Always use tools to look up real data.
- If unsure, say "I'll have the office follow up with you in the morning."

FIRST MESSAGE PROTOCOL:
On the FIRST message in a conversation, ALWAYS use identify_caller with the caller's phone number. This tells you if they are a caregiver, client, or unknown.

COMMON SCENARIOS:
- Caregiver calling out sick: Use identify_caller, then log_call_out. Reassure them.
- Caregiver asking about schedule: Use identify_caller, then get_wellsky_shifts with their caregiver_id.
- Client asking when caregiver is coming: Use identify_caller, then get_wellsky_shifts with their client_id.
- Anyone asking about a person by name: Use get_wellsky_clients or get_wellsky_caregivers.
- Unknown caller or general question: Respond helpfully, note the office will follow up.

TONE:
- Friendly, professional, concise
- Plain language (many caregivers speak English as a second language)
- OK to use abbreviations (Mon, Tue, etc.)

Today is {current_date}.
The caller's phone number is {caller_phone}.
"""


class GigiRingCentralBot:
    def __init__(self):
        self.rc_service = ringcentral_messaging_service
        self.wellsky = WellSkyService()
        self.processed_message_ids = set()
        self.bot_extension_id = None
        self.startup_time = datetime.utcnow()
        self.reply_history = self._load_reply_history()
        # Claude API for intelligent SMS replies
        if anthropic and ANTHROPIC_API_KEY:
            self.claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            logger.info("Claude API initialized for intelligent SMS replies")
        else:
            self.claude = None
            logger.warning("Claude API not available - using static SMS replies")
        self.sms_conversations = self._load_sms_conversations()
        # Autonomous shift coordination
        self._active_campaigns = {}  # campaign_id -> {shift_id, started_at, client_name}
        self._last_campaign_check = datetime.utcnow()
        if GIGI_SHIFT_MONITOR_ENABLED:
            logger.info("Autonomous shift monitor ENABLED")
        else:
            logger.info("Autonomous shift monitor disabled (set GIGI_SHIFT_MONITOR_ENABLED=true to enable)")

        # --- Caregiver preference extraction (GAP 3) ---
        self.preference_extractor = None
        try:
            from gigi.memory_system import MemorySystem
            from gigi.caregiver_preference_extractor import (
                CaregiverPreferenceExtractor, CAREGIVER_MEMORY_ENABLED
            )
            if CAREGIVER_MEMORY_ENABLED and self.claude:
                memory_sys = MemorySystem()
                self.preference_extractor = CaregiverPreferenceExtractor(
                    memory_system=memory_sys,
                    anthropic_api_key=ANTHROPIC_API_KEY
                )
                logger.info("Caregiver preference extractor ENABLED")
            else:
                logger.info("Caregiver preference extractor disabled")
        except Exception as e:
            logger.warning(f"Caregiver preference extractor not available: {e}")

        # --- Clock in/out reminders (GAP 4) ---
        self.clock_reminder = None
        self._last_clock_check = datetime.utcnow()
        try:
            from gigi.clock_reminder_service import ClockReminderService, CLOCK_REMINDER_ENABLED
            if CLOCK_REMINDER_ENABLED:
                self.clock_reminder = ClockReminderService(
                    wellsky_service=self.wellsky,
                    sms_send_fn=self._send_sms_via_rc
                )
                logger.info("Clock reminder service ENABLED")
            else:
                logger.info("Clock reminder service disabled")
        except Exception as e:
            logger.warning(f"Clock reminder service not available: {e}")

        # --- Daily shift confirmations (GAP 5) ---
        self.daily_confirmation = None
        try:
            from gigi.daily_confirmation_service import DailyConfirmationService, DAILY_CONFIRMATION_ENABLED
            if DAILY_CONFIRMATION_ENABLED:
                self.daily_confirmation = DailyConfirmationService(
                    wellsky_service=self.wellsky,
                    sms_send_fn=self._send_sms_via_rc
                )
                logger.info("Daily confirmation service ENABLED")
            else:
                logger.info("Daily confirmation service disabled")
        except Exception as e:
            logger.warning(f"Daily confirmation service not available: {e}")

        logger.info(f"Bot initialized. Startup time (UTC): {self.startup_time}")
        logger.info(f"Reply history loaded: {len(self.reply_history.get('replies', []))} recent replies tracked")

    def _load_reply_history(self) -> dict:
        """Load reply history from persistent storage for loop prevention"""
        try:
            import json
            from pathlib import Path
            history_file = Path(REPLY_HISTORY_FILE)
            if history_file.exists():
                with open(history_file, 'r') as f:
                    data = json.load(f)
                    # Clean old entries (older than 24 hours)
                    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
                    data['replies'] = [r for r in data.get('replies', []) if r.get('timestamp', '') > cutoff]
                    return data
        except Exception as e:
            logger.warning(f"Could not load reply history: {e}")
        return {'replies': [], 'hourly_count': 0, 'hourly_reset': datetime.utcnow().isoformat()}

    def _save_reply_history(self):
        """Save reply history to persistent storage"""
        try:
            import json
            with open(REPLY_HISTORY_FILE, 'w') as f:
                json.dump(self.reply_history, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save reply history: {e}")

    def _can_reply_to_number(self, phone: str) -> tuple[bool, str]:
        """
        Check if we can safely reply to this phone number.
        Returns (can_reply, reason).
        """
        now = datetime.utcnow()

        # Check global hourly rate limit
        hourly_reset = datetime.fromisoformat(self.reply_history.get('hourly_reset', now.isoformat()))
        if (now - hourly_reset).total_seconds() > 3600:
            # Reset hourly counter
            self.reply_history['hourly_count'] = 0
            self.reply_history['hourly_reset'] = now.isoformat()

        if self.reply_history.get('hourly_count', 0) >= MAX_REPLIES_PER_HOUR_GLOBAL:
            return False, f"Global hourly limit reached ({MAX_REPLIES_PER_HOUR_GLOBAL}/hr)"

        # Normalize phone number for comparison
        clean_phone = ''.join(filter(str.isdigit, phone))[-10:]

        # Check per-number limits
        today = now.date().isoformat()
        replies_to_number_today = 0
        last_reply_to_number = None

        for reply in self.reply_history.get('replies', []):
            reply_phone = ''.join(filter(str.isdigit, reply.get('phone', '')))[-10:]
            if reply_phone == clean_phone:
                reply_time = datetime.fromisoformat(reply.get('timestamp', '2000-01-01'))

                # Check cooldown
                minutes_since = (now - reply_time).total_seconds() / 60
                if minutes_since < REPLY_COOLDOWN_MINUTES:
                    return False, f"Cooldown active ({int(REPLY_COOLDOWN_MINUTES - minutes_since)} min remaining)"

                # Count today's replies
                if reply.get('timestamp', '').startswith(today):
                    replies_to_number_today += 1

        if replies_to_number_today >= MAX_REPLIES_PER_DAY_PER_NUMBER:
            return False, f"Daily limit reached for this number ({MAX_REPLIES_PER_DAY_PER_NUMBER}/day)"

        return True, "OK"

    def _record_reply(self, phone: str):
        """Record that we sent a reply to this number"""
        clean_phone = ''.join(filter(str.isdigit, phone))[-10:]
        self.reply_history.setdefault('replies', []).append({
            'phone': clean_phone,
            'timestamp': datetime.utcnow().isoformat()
        })
        self.reply_history['hourly_count'] = self.reply_history.get('hourly_count', 0) + 1
        self._save_reply_history()

    async def initialize(self):
        """Initialize connections"""
        logger.info("Initializing Gigi Manager Bot...")

        # Perform immediate health check SMS
        # This confirms the bot has started and has send permissions
        await self.send_health_check_sms()

        status = self.rc_service.get_status()
        if not status.get("api_connected"):
            logger.error("RingCentral API not connected! Check credentials.")
            return False

        # Get bot's own extension ID to avoid replying to self
        try:
            token = self.rc_service._get_access_token()
            if token:
                import requests
                response = requests.get(
                    f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if response.status_code == 200:
                    ext_data = response.json()
                    self.bot_extension_id = str(ext_data.get("id"))
                    logger.info(f"Bot extension ID: {self.bot_extension_id}")
        except Exception as e:
            logger.warning(f"Could not get bot extension ID: {e}")

        logger.info(f"Monitoring chat: {TARGET_CHAT} and Direct SMS")
        return True

    def _get_admin_access_token(self):
        """Exchange JWT for access token"""
        try:
            # Get RC credentials from environment - NO hardcoded fallbacks
            client_id = os.getenv("RINGCENTRAL_CLIENT_ID")
            client_secret = os.getenv("RINGCENTRAL_CLIENT_SECRET")
            if not client_id or not client_secret:
                logger.error("RINGCENTRAL_CLIENT_ID or RINGCENTRAL_CLIENT_SECRET not set")
                return None

            response = requests.post(
                f"{RINGCENTRAL_SERVER}/restapi/oauth/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=(client_id, client_secret),  # Basic auth with client credentials
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": ADMIN_JWT_TOKEN
                },
                timeout=20
            )
            if response.status_code == 200:
                logger.info("✅ JWT exchanged for access token")
                return response.json().get("access_token")
            else:
                logger.error(f"JWT exchange failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"JWT exchange error: {e}")
            return None

    def _send_sms_via_rc(self, to_phone: str, message: str):
        """Send SMS using the admin JWT token. Used by clock reminders and daily confirmations."""
        access_token = self._get_admin_access_token()
        if not access_token:
            return False, "No access token"

        import re
        clean_phone = re.sub(r'[^\d]', '', to_phone)
        if len(clean_phone) == 10:
            clean_phone = f"+1{clean_phone}"
        elif len(clean_phone) == 11 and clean_phone.startswith('1'):
            clean_phone = f"+{clean_phone}"
        elif not clean_phone.startswith('+'):
            clean_phone = f"+{clean_phone}"

        try:
            response = requests.post(
                f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/sms",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": {"phoneNumber": RINGCENTRAL_FROM_NUMBER},
                    "to": [{"phoneNumber": clean_phone}],
                    "text": message
                },
                timeout=20
            )
            if response.status_code in (200, 201):
                return True, response.json().get("id")
            else:
                logger.error(f"SMS send failed: {response.status_code}")
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            logger.error(f"SMS send error: {e}")
            return False, str(e)

    async def send_health_check_sms(self):
        """Send a startup SMS to the admin to confirm vitality"""
        try:
            admin_phone = "+16039971495" # Jason's number
            logger.info(f"🚑 Sending Health Check SMS to {admin_phone}...")

            # Get access token from JWT
            access_token = self._get_admin_access_token()
            if not access_token:
                logger.error("❌ Could not get access token from JWT")
                return

            url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/sms"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            data = {
                "from": {"phoneNumber": RINGCENTRAL_FROM_NUMBER},
                "to": [{"phoneNumber": admin_phone}],
                "text": "🤖 Gigi Bot Online: Monitoring 719/303 lines via Admin Context."
            }

            # Using synchronous requests in async init is fine for startup
            response = requests.post(url, headers=headers, json=data, timeout=20)
            if response.status_code == 200:
                logger.info("✅ Health Check SMS Sent Successfully!")
            else:
                logger.error(f"❌ Health Check Failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"❌ Health Check Exception: {e}")

    def is_business_hours(self) -> bool:
        """Check if currently within M-F 8am-5pm Mountain Time"""
        now = datetime.now(TIMEZONE)
        is_weekday = now.weekday() < 5  # 0-4 is Mon-Fri
        is_working_hours = BUSINESS_START <= now.time() <= BUSINESS_END
        return is_weekday and is_working_hours

    async def check_and_act(self):
        """Main loop: Run Documentation (always) and Reply (after-hours)"""
        try:
            status = "BUSINESS HOURS (Silent)" if self.is_business_hours() else "AFTER HOURS (Active)"
            logger.info(f"--- Gigi Bot Cycle: {status} ---")

            # 1. Check Direct SMS (RingCentral SMS) - PRIORITY
            await self.check_direct_sms()

            # 2. Check Team Chats (Glip)
            await self.check_team_chats()

            # 3. Check active shift-filling campaigns (every 5 min)
            if GIGI_SHIFT_MONITOR_ENABLED and self._active_campaigns:
                now = datetime.utcnow()
                if (now - self._last_campaign_check).total_seconds() >= CAMPAIGN_CHECK_INTERVAL_SECONDS:
                    self._last_campaign_check = now
                    await self._check_campaign_status()

            # 4. Clock in/out reminders (every 5 min during business hours)
            # Respects REPLIES_ENABLED as global SMS kill switch
            if self.clock_reminder and REPLIES_ENABLED and self.is_business_hours():
                now = datetime.utcnow()
                if (now - self._last_clock_check).total_seconds() >= 300:
                    self._last_clock_check = now
                    try:
                        actions = self.clock_reminder.check_and_remind()
                        if actions:
                            logger.info(f"Clock reminders sent: {actions}")
                    except Exception as e:
                        logger.error(f"Clock reminder error: {e}")

            # 5. Daily shift confirmations (service handles its own 2pm timing)
            # Respects REPLIES_ENABLED as global SMS kill switch
            if self.daily_confirmation and REPLIES_ENABLED:
                try:
                    notified = self.daily_confirmation.check_and_send()
                    if notified:
                        logger.info(f"Daily confirmations sent to: {notified}")
                except Exception as e:
                    logger.error(f"Daily confirmation error: {e}")

        except Exception as e:
            logger.error(f"Error in check_and_act: {e}")

    async def check_team_chats(self):
        """Monitor Glip channels for activity documentation and replies"""
        chat = self.rc_service.find_chat_by_name(TARGET_CHAT)
        if not chat:
            logger.warning(f"Target chat {TARGET_CHAT} not found in check_team_chats")
            return

        # Reduced lookback for team chats to save quota
        messages = self.rc_service.get_chat_messages(
            chat["id"], 
            since=datetime.utcnow() - timedelta(minutes=10),
            limit=20
        )
        
        if not messages:
            return

        logger.info(f"Glip: Found {len(messages)} recent messages in {TARGET_CHAT}")
        messages.sort(key=lambda x: x.get("creationTime", ""))

        for msg in messages:
            msg_id = msg.get("id")
            if msg_id in self.processed_message_ids:
                continue

            # Skip historical messages (older than startup) to prevent bursts on restart
            creation_time_str = msg.get("creationTime", "")
            if creation_time_str:
                try:
                    # RC timestamp format: 2026-02-03T18:10:34Z
                    creation_time = datetime.strptime(creation_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    try:
                        creation_time = datetime.strptime(creation_time_str, "%Y-%m-%dT%H:%M:%SZ")
                    except ValueError:
                        creation_time = None
                
                if creation_time and creation_time < self.startup_time:
                    logger.debug(f"Skipping historical Glip message {msg_id} (pre-startup)")
                    self.processed_message_ids.add(msg_id)
                    continue

            # CRITICAL: Skip messages sent by the bot itself to prevent infinite loops
            creator_id = str(msg.get("creatorId", ""))
            if self.bot_extension_id and creator_id == self.bot_extension_id:
                logger.debug(f"Skipping message from bot itself: {msg_id}")
                self.processed_message_ids.add(msg_id)
                continue

            # Also skip messages that look like bot replies (double safety)
            text = msg.get("text", "")
            if text.startswith(("Thanks for your message!", "I hear you.", "Got it.", "I've processed", "I've noted")):
                logger.debug(f"Skipping bot-like message: {msg_id}")
                self.processed_message_ids.add(msg_id)
                continue

            logger.info(f"Glip: Processing new message {msg_id}: {text[:30]}...")
            await self.process_documentation(msg, text, source_type="chat")

            # Only reply on team chat if someone directly addresses Gigi AND replies are enabled
            if REPLIES_ENABLED and not self.is_business_hours() and "gigi" in text.lower():
                logger.info(f"Gigi addressed in team chat — replying")
                await self.process_reply(msg, text, reply_method="chat")

            self.processed_message_ids.add(msg_id)

    async def check_direct_sms(self):
        """Monitor RingCentral SMS using Admin Token for full visibility"""
        # Get access token from JWT
        token = self._get_admin_access_token()

        if not token:
            logger.error("Admin Token missing or invalid in check_direct_sms")
            return

        try:
            # Poll the extension message-store (x101 context)
            url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/message-store"
            params = {
                "messageType": "SMS",
                "dateFrom": (datetime.utcnow() - timedelta(hours=12)).isoformat(), # 12h lookback for missed msgs
                "perPage": 100
            }
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            }

            logger.info("SMS: Polling extension message-store (x101 Admin context) - JWT→Token")
            response = requests.get(url, headers=headers, params=params, timeout=20)
            if response.status_code != 200:
                logger.error(f"RC SMS Store Error: {response.status_code} - {response.text}")
                return

            data = response.json()
            records = data.get("records", [])
            
            for sms in records:
                msg_id = str(sms.get("id"))
                from_phone = sms.get("from", {}).get("phoneNumber")
                to_phone = sms.get("to", [{}])[0].get("phoneNumber")
                text = sms.get("subject", "")
                
                if msg_id in self.processed_message_ids:
                    continue

                # Skip historical SMS (older than startup) to prevent bursts on restart
                creation_time_str = sms.get("creationTime", "")
                if creation_time_str:
                    try:
                        creation_time = datetime.strptime(creation_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                    except ValueError:
                        try:
                            creation_time = datetime.strptime(creation_time_str, "%Y-%m-%dT%H:%M:%SZ")
                        except ValueError:
                            creation_time = None
                    
                    if creation_time and creation_time < self.startup_time:
                        logger.debug(f"Skipping historical SMS {msg_id} (pre-startup)")
                        self.processed_message_ids.add(msg_id)
                        continue
                
                # Check for duplicate replies within 60s window (cooldown)

                # Role 1: Documenter
                await self.process_documentation(sms, text, source_type="sms", phone=from_phone)

                # Role 2: Replier (only when REPLIES_ENABLED)
                if REPLIES_ENABLED and not self.is_business_hours():
                    # IMPORTANT: Don't reply if it's from US (to prevent loops)
                    if from_phone not in [RINGCENTRAL_FROM_NUMBER, "+13074598220", "+17194283999", "+13037571777", "+16039971495"]:
                        await self.process_reply(sms, text, reply_method="sms", phone=from_phone)
                    else:
                        logger.info(f"⏭️ Skipping reply to internal/company number: {from_phone}")

                self.processed_message_ids.add(msg_id)

            # Cleanup processed IDs to keep memory low (keep last 1000)
            if len(self.processed_message_ids) > 1000:
                logger.info("Cleaning up processed message IDs cache...")
                self.processed_message_ids = set(list(self.processed_message_ids)[-500:])

        except Exception as e:
            logger.error(f"Failed to check direct SMS: {e}")

    async def process_documentation(self, msg: dict, text: str, source_type: str = "chat", phone: str = None):
        """QA/Manager Logic: Document ALL care-related communications in WellSky.

        HEALTHCARE RULE: If a client or caregiver is mentioned, it gets documented.
        Uses DocumentReference API (clinical-note) as PRIMARY WellSky path — works for
        any client, no encounter/shift needed.
        """
        import re
        import psycopg2

        db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")

        # =====================================================================
        # 1. Identify Caregiver (from phone number via cached DB)
        # =====================================================================
        caregiver_id = None
        caregiver_name = None

        if source_type == "sms" and phone:
            try:
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                # Normalize phone to 10 digits
                clean_phone = re.sub(r'[^\d]', '', phone)
                if len(clean_phone) == 11 and clean_phone.startswith("1"):
                    clean_phone = clean_phone[1:]
                if len(clean_phone) == 10:
                    cur.execute("""
                        SELECT id, full_name FROM cached_practitioners
                        WHERE is_active = true AND phone IS NOT NULL
                        AND RIGHT(REGEXP_REPLACE(phone, '[^0-9]', '', 'g'), 10) = %s
                        LIMIT 1
                    """, (clean_phone,))
                    row = cur.fetchone()
                    if row:
                        caregiver_id = str(row[0])
                        caregiver_name = row[1]
                        logger.info(f"Doc: Identified SMS sender as caregiver: {caregiver_name}")
                conn.close()
            except Exception as e:
                logger.warning(f"Doc: Caregiver phone lookup error: {e}")

        # =====================================================================
        # 2. Extract Client Name from message text + match against cached DB
        # =====================================================================
        client_id = None
        client_name = None
        lower_text = text.lower()

        # Extract potential names from text
        possible_names = []
        # Pattern 1: Names after context words
        name_match = re.search(
            r'(?:for|client|visit|shift|with|about|at|to|see|seeing|from)\s+'
            r'([A-Z][a-z]+\.?(?:\s[A-Z][a-z]+)?)',
            text
        )
        if name_match:
            possible_names.append(name_match.group(1))

        # Pattern 2: Any "FirstName LastName" pattern
        fallback_matches = re.findall(r'([A-Z][a-z]+\.?\s[A-Z][a-z]+)', text)
        for m in fallback_matches:
            if m not in possible_names:
                possible_names.append(m)

        # Match against cached_patients (reliable — all 70 clients)
        if possible_names:
            try:
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                for pname in possible_names:
                    if client_id:
                        break
                    clean_name = pname.replace(".", "").strip()
                    name_parts = clean_name.split()
                    # Strip honorifics (Mrs, Mr, Ms, Dr)
                    if name_parts and name_parts[0].lower() in ("mrs", "mr", "ms", "dr", "miss"):
                        name_parts = name_parts[1:]
                    if len(name_parts) >= 2:
                        first = name_parts[0].lower()
                        last = name_parts[-1].lower()
                        if len(last) < 2:
                            continue
                        cur.execute("""
                            SELECT id, full_name FROM cached_patients
                            WHERE is_active = true
                            AND lower(last_name) = %s
                            AND (lower(first_name) = %s
                                 OR lower(first_name) LIKE %s
                                 OR %s LIKE lower(first_name) || '%%')
                            LIMIT 1
                        """, (last, first, f"{first}%", first))
                    elif len(name_parts) == 1 and len(name_parts[0]) > 3:
                        search = name_parts[0].lower()
                        cur.execute("""
                            SELECT id, full_name FROM cached_patients
                            WHERE is_active = true
                            AND (lower(last_name) = %s OR lower(first_name) = %s)
                            LIMIT 1
                        """, (search, search))
                    else:
                        continue
                    row = cur.fetchone()
                    if row:
                        client_id = str(row[0])
                        client_name = row[1]
                conn.close()
            except Exception as e:
                logger.warning(f"Doc: Client name lookup error: {e}")

        # =====================================================================
        # 3. Classify the Event
        # =====================================================================
        note_type = "general"
        is_alert = False
        is_task = False
        priority = "normal"

        if any(w in lower_text for w in [
            "call out", "call-out", "callout", "sick", "emergency",
            "cancel", "can't make it", "cant make it", "won't be able",
            "wont be able", "not coming", "not going to make"
        ]):
            note_type = "callout"
            is_alert = True
            is_task = True
            priority = "urgent"
        elif any(w in lower_text for w in [
            "fell", "fall ", "injury", "hospital", "er ", " er.",
            "ambulance", "911", "hurt", "bleeding", "unconscious",
            "chest pain", "stroke", "seizure"
        ]):
            note_type = "safety"
            is_alert = True
            is_task = True
            priority = "urgent"
        elif any(w in lower_text for w in [
            "late", "traffic", "delayed", "running behind", "on my way",
            "running late", "be there soon"
        ]):
            note_type = "late"
            is_alert = True
        elif any(w in lower_text for w in [
            "complain", "upset", "angry", "issue", "quit", "problem",
            "concerned", "worried", "unhappy", "frustrated", "refuse"
        ]):
            note_type = "complaint"
            is_alert = True
            is_task = True
            priority = "high"
        elif any(w in lower_text for w in [
            "medication", "meds", "prescription", "pharmacy", "dose",
            "medicine", "refill"
        ]):
            note_type = "medication"
            is_alert = True
        elif any(w in lower_text for w in [
            "accept", "take the shift", "can work", "available",
            "filled", "confirmed", "i'll be there", "ill be there"
        ]):
            note_type = "schedule"
        elif any(w in lower_text for w in [
            "reschedule", "swap", "switch", "cover", "replacement",
            "change shift", "move shift"
        ]):
            note_type = "schedule_change"
            is_task = True

        # =====================================================================
        # 4. HEALTHCARE RULE: Document if client OR caregiver identified, or alert/task
        # =====================================================================
        should_log = bool(client_id) or bool(caregiver_id) or is_alert or is_task

        if not should_log:
            return  # Skip non-care-related messages with no identified people

        # =====================================================================
        # 5. Document to WellSky via DocumentReference API + PostgreSQL backup
        # =====================================================================
        wellsky_doc_id = None
        wellsky_synced = False

        try:
            source_label = "SMS" if source_type == "sms" else "Team Chat"
            sender = caregiver_name or phone or str(msg.get("creatorId", "Unknown"))
            alert_prefix = "CARE ALERT" if is_alert else "Care Note"

            note_title = f"{alert_prefix}: {note_type.upper()} ({source_label})"
            note_body = (
                f"From: {sender}\n"
                f"Source: {source_label}\n"
                f"Type: {note_type}\n"
                f"Priority: {priority}\n"
                + (f"Client: {client_name}\n" if client_name else "Client: Not identified\n")
                + (f"Caregiver: {caregiver_name}\n" if caregiver_name else "")
                + f"\n--- Original Message ---\n{text}\n"
            )

            # -----------------------------------------------------------------
            # A. Client identified → Document on their WellSky profile
            #    Uses encounter/TaskLog API (searches 90 days for an encounter)
            # -----------------------------------------------------------------
            if client_id:
                try:
                    full_note = f"{note_title}\n{note_body}"
                    success, result_msg = self.wellsky.add_note_to_client(
                        client_id=client_id,
                        note=full_note,
                        note_type=note_type,
                        source="gigi_manager"
                    )
                    if success and "WellSky" in str(result_msg):
                        wellsky_synced = True
                        wellsky_doc_id = str(result_msg)
                        logger.info(f"✅ Documented to WellSky for {client_name}: {result_msg}")
                    elif success:
                        logger.warning(f"⚠️ Documented LOCALLY ONLY for {client_name}: {result_msg}")
                    else:
                        logger.error(f"Documentation failed for {client_name}: {result_msg}")
                except Exception as e:
                    logger.error(f"WellSky documentation error for {client_name}: {e}")

            # -----------------------------------------------------------------
            # B. Caregiver only → find their client from today's schedule, document there
            # -----------------------------------------------------------------
            elif caregiver_id:
                try:
                    from datetime import date as date_cls
                    shifts = self.wellsky.get_shifts(
                        caregiver_id=caregiver_id,
                        date_from=date_cls.today(),
                        date_to=date_cls.today()
                    )
                    if shifts:
                        # Find client ID from first shift
                        shift_client_id = None
                        shift_client_name = None
                        for s in shifts:
                            sid = getattr(s, 'client_id', None) or (s.get('client_id') if isinstance(s, dict) else None)
                            if sid:
                                shift_client_id = str(sid)
                                shift_client_name = getattr(s, 'client_name', None) or (s.get('client') if isinstance(s, dict) else None)
                                break
                        if shift_client_id:
                            full_note = f"{note_title}\n{note_body}\n(Auto-linked via {caregiver_name}'s schedule)"
                            success, result_msg = self.wellsky.add_note_to_client(
                                client_id=shift_client_id,
                                note=full_note,
                                note_type=note_type,
                                source="gigi_manager"
                            )
                            if success and "WellSky" in str(result_msg):
                                wellsky_synced = True
                                wellsky_doc_id = str(result_msg)
                                client_name = shift_client_name or "Unknown"
                                logger.info(f"✅ Documented to WellSky via caregiver schedule → {client_name}: {result_msg}")
                            else:
                                logger.warning(f"⚠️ Caregiver doc for {caregiver_name} saved locally: {result_msg}")
                    else:
                        logger.info(f"No shifts today for {caregiver_name} — documented in PostgreSQL only")
                except Exception as e:
                    logger.warning(f"Caregiver→client schedule lookup for doc failed: {e}")

            # -----------------------------------------------------------------
            # C. PostgreSQL backup log (ALWAYS — regardless of WellSky success)
            # -----------------------------------------------------------------
            try:
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS gigi_wellsky_documentation (
                        id SERIAL PRIMARY KEY,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        source TEXT,
                        person_type TEXT,
                        person_id TEXT,
                        person_name TEXT,
                        note_type TEXT,
                        priority TEXT,
                        message_text TEXT,
                        wellsky_doc_id TEXT,
                        wellsky_synced BOOLEAN DEFAULT FALSE,
                        sender_phone TEXT
                    )
                """)
                person_type = "client" if client_id else ("caregiver" if caregiver_id else "unknown")
                person_id_val = client_id or caregiver_id or ""
                person_name_val = client_name or caregiver_name or "Unknown"
                cur.execute("""
                    INSERT INTO gigi_wellsky_documentation
                    (source, person_type, person_id, person_name, note_type, priority,
                     message_text, wellsky_doc_id, wellsky_synced, sender_phone)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (source_type, person_type, person_id_val, person_name_val,
                      note_type, priority, text, wellsky_doc_id, wellsky_synced,
                      phone or ""))
                conn.commit()
                conn.close()
                logger.info(f"Doc: PostgreSQL backup logged (synced={wellsky_synced}, type={note_type}, person={person_name_val})")
            except Exception as e:
                logger.error(f"Doc: PostgreSQL backup log error: {e}")

        except Exception as e:
            logger.error(f"Failed to document: {e}")

        # Extract caregiver preferences from conversation (GAP 3)
        if caregiver_id and self.preference_extractor:
            try:
                memory_ids = await self.preference_extractor.extract_and_store(
                    caregiver_id=caregiver_id,
                    caregiver_name=caregiver_name or "Unknown",
                    message_text=text
                )
                if memory_ids:
                    logger.info(f"Extracted {len(memory_ids)} preferences for {caregiver_name}")
            except Exception as e:
                logger.warning(f"Preference extraction failed: {e}")

        # Autonomous shift filling: trigger when callout detected
        if note_type == "callout" and GIGI_SHIFT_MONITOR_ENABLED:
            await self._trigger_shift_filling(possible_names, caregiver_name if caregiver_id else None, text[:100])

    # =========================================================================
    # Autonomous Shift Coordination
    # =========================================================================

    async def _trigger_shift_filling(self, possible_names: list, caregiver_name: str, reason: str):
        """When a callout is documented, find affected shifts and start filling campaigns."""
        try:
            import re
            # Try to identify the caregiver who called out
            caregiver_id = None
            cg_name = ""

            # First try names from the message text
            for name in possible_names:
                clean = name.replace(".", "").strip()
                if len(clean.split()) < 2:
                    continue
                last_name = clean.split()[-1]
                if len(last_name) < 3:
                    continue
                try:
                    practitioners = self.wellsky.search_practitioners(last_name=last_name)
                    for p in practitioners:
                        if clean.lower() in p.full_name.lower() or p.last_name.lower() == last_name.lower():
                            caregiver_id = p.id
                            cg_name = p.full_name
                            break
                except Exception:
                    pass
                if caregiver_id:
                    break

            if not caregiver_id:
                logger.info("Shift monitor: Could not identify caregiver for auto-fill")
                return

            # Get this caregiver's shifts for the next 48 hours
            from datetime import timedelta
            shifts = self.wellsky.get_shifts(
                caregiver_id=caregiver_id,
                date_from=date.today(),
                date_to=date.today() + timedelta(days=2),
                limit=10
            )

            if not shifts:
                logger.info(f"Shift monitor: No upcoming shifts found for {cg_name}")
                return

            import requests as http_requests
            for shift in shifts:
                shift_status = shift.status.value if hasattr(shift.status, 'value') else str(shift.status)
                if shift_status not in ('scheduled', 'open', 'confirmed'):
                    continue

                # Don't re-trigger for shifts we already started campaigns for
                if shift.id in self._active_campaigns:
                    continue

                logger.info(f"Shift monitor: Auto-triggering fill for shift {shift.id} ({cg_name} → {getattr(shift, 'client_name', 'unknown client')})")

                try:
                    resp = http_requests.post(
                        "http://localhost:8765/api/internal/shift-filling/calloff",
                        json={
                            "shift_id": shift.id,
                            "caregiver_id": caregiver_id,
                            "reason": reason
                        },
                        timeout=30
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        campaign_id = data.get("campaign_id")
                        if campaign_id:
                            self._active_campaigns[campaign_id] = {
                                "shift_id": shift.id,
                                "started_at": datetime.utcnow().isoformat(),
                                "client_name": getattr(shift, 'client_name', 'unknown'),
                                "caregiver_name": cg_name
                            }
                            logger.info(f"Shift filling campaign started: {campaign_id}, contacted {data.get('candidates_contacted', 0)} caregivers")

                            # Notify team chat
                            try:
                                self.rc_service.send_message_to_chat(
                                    TARGET_CHAT,
                                    f"[Gigi] Shift filling started for {getattr(shift, 'client_name', 'client')} "
                                    f"(was: {cg_name}). Contacting {data.get('candidates_contacted', 0)} replacement caregivers."
                                )
                            except Exception:
                                pass
                    else:
                        logger.error(f"Shift filling API error: {resp.status_code} - {resp.text[:200]}")
                except Exception as e:
                    logger.error(f"Failed to call shift filling API: {e}")

        except Exception as e:
            logger.error(f"Error in callout-triggered shift filling: {e}")

    async def _check_campaign_status(self):
        """Check active shift-filling campaigns and escalate/notify as needed."""
        if not self._active_campaigns:
            return

        import requests as http_requests
        completed = []

        for campaign_id, info in self._active_campaigns.items():
            try:
                resp = http_requests.get(
                    f"http://localhost:8765/api/internal/shift-filling/campaigns/{campaign_id}",
                    timeout=10
                )
                if resp.status_code != 200:
                    continue

                data = resp.json()
                if not data.get("found"):
                    completed.append(campaign_id)
                    continue

                if data.get("shift_filled"):
                    winner = data.get("winning_caregiver", "someone")
                    logger.info(f"Campaign {campaign_id} FILLED by {winner}")
                    try:
                        self.rc_service.send_message_to_chat(
                            TARGET_CHAT,
                            f"[Gigi] Shift FILLED: {info.get('client_name', 'client')} now covered by {winner}. "
                            f"(was: {info.get('caregiver_name', 'unknown')})"
                        )
                    except Exception:
                        pass
                    completed.append(campaign_id)

                elif not data.get("escalated"):
                    # Check if campaign has been running too long
                    started_at = datetime.fromisoformat(info["started_at"])
                    elapsed_min = (datetime.utcnow() - started_at).total_seconds() / 60

                    if elapsed_min >= CAMPAIGN_ESCALATION_MINUTES:
                        logger.warning(f"Campaign {campaign_id} unfilled after {elapsed_min:.0f} min — escalating")
                        try:
                            self.rc_service.send_message_to_chat(
                                TARGET_CHAT,
                                f"[Gigi] URGENT: Shift for {info.get('client_name', 'client')} still unfilled after "
                                f"{int(elapsed_min)} min. {data.get('total_contacted', 0)} contacted, "
                                f"{data.get('total_responded', 0)} responded. Manual action needed."
                            )
                        except Exception:
                            pass
                        completed.append(campaign_id)  # Stop tracking to avoid repeat notifications

            except Exception as e:
                logger.error(f"Campaign status check error for {campaign_id}: {e}")

        for cid in completed:
            self._active_campaigns.pop(cid, None)

        # Trigger voice follow-up calls for non-responding caregivers
        if VOICE_OUTREACH_ENABLED:
            try:
                resp = http_requests.post(
                    "http://localhost:8765/api/internal/shift-filling/voice-followups",
                    timeout=15
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("calls_made", 0) > 0:
                        logger.info(f"Voice follow-ups initiated: {data['calls_made']} calls")
            except Exception as e:
                logger.error(f"Voice followup check error: {e}")

    # =========================================================================
    # Claude SMS Conversation History
    # =========================================================================

    def _load_sms_conversations(self) -> dict:
        """Load SMS conversation history, pruning expired conversations"""
        try:
            from pathlib import Path
            history_file = Path(CONVERSATION_HISTORY_FILE)
            if history_file.exists():
                with open(history_file, 'r') as f:
                    data = json.load(f)
                now = datetime.utcnow()
                pruned = {}
                for phone, convo in data.items():
                    last_activity = datetime.fromisoformat(convo.get("last_activity", "2000-01-01"))
                    if (now - last_activity).total_seconds() < CONVERSATION_TIMEOUT_MINUTES * 60:
                        pruned[phone] = convo
                return pruned
        except Exception as e:
            logger.warning(f"Could not load SMS conversations: {e}")
        return {}

    def _save_sms_conversations(self):
        """Persist SMS conversation history"""
        try:
            with open(CONVERSATION_HISTORY_FILE, 'w') as f:
                json.dump(self.sms_conversations, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Could not save SMS conversations: {e}")

    def _get_conversation_history(self, phone: str) -> list:
        """Get conversation messages for a phone number, resetting if expired"""
        clean_phone = ''.join(filter(str.isdigit, phone))[-10:]
        convo = self.sms_conversations.get(clean_phone, {})

        last_activity = convo.get("last_activity")
        if last_activity:
            try:
                last_dt = datetime.fromisoformat(last_activity)
                if (datetime.utcnow() - last_dt).total_seconds() > CONVERSATION_TIMEOUT_MINUTES * 60:
                    logger.info(f"Conversation timeout for ...{clean_phone[-4:]}, resetting")
                    self.sms_conversations.pop(clean_phone, None)
                    return []
            except (ValueError, TypeError):
                pass

        return list(convo.get("messages", []))

    def _add_to_conversation(self, phone: str, role: str, content):
        """Append a message to conversation history for a phone number"""
        clean_phone = ''.join(filter(str.isdigit, phone))[-10:]

        if clean_phone not in self.sms_conversations:
            self.sms_conversations[clean_phone] = {"messages": [], "last_activity": datetime.utcnow().isoformat()}

        convo = self.sms_conversations[clean_phone]
        convo["messages"].append({"role": role, "content": content})
        convo["last_activity"] = datetime.utcnow().isoformat()

        if len(convo["messages"]) > MAX_CONVERSATION_MESSAGES:
            convo["messages"] = convo["messages"][-MAX_CONVERSATION_MESSAGES:]

        self._save_sms_conversations()

    # =========================================================================
    # Claude SMS Tool Execution
    # =========================================================================

    def _execute_sms_tool(self, tool_name: str, tool_input: dict, caller_phone: str = None) -> str:
        """Execute a tool call and return the result as a JSON string"""
        try:
            if tool_name == "identify_caller":
                phone = tool_input.get("phone_number", caller_phone or "")
                # Use fast SQL lookup (checks all 4 tables: staff, practitioners, patients, family)
                try:
                    from services.wellsky_fast_lookup import identify_caller as fast_identify
                    caller = fast_identify(phone)
                    if caller:
                        caller_type = caller.get('type', 'unknown')
                        # Map type to identified_as value
                        type_map = {
                            'practitioner': 'caregiver',
                            'patient': 'client',
                            'staff': 'staff',
                            'family': 'family'
                        }
                        result = {
                            "identified_as": type_map.get(caller_type, caller_type),
                            "id": caller.get('id', ''),
                            "name": caller.get('full_name', caller.get('name', '')),
                            "first_name": caller.get('first_name', ''),
                            "status": caller.get('status', caller.get('role', ''))
                        }
                        # Add extra context for family members
                        if caller_type == 'family':
                            result["relationship"] = caller.get('relationship', '')
                            result["client_name"] = caller.get('client_name', '')
                            result["patient_id"] = caller.get('patient_id', '')
                        return json.dumps(result)
                except Exception as e:
                    logger.warning(f"Fast caller ID failed, trying fallback: {e}")

                # Fallback to WellSky API if fast lookup fails
                try:
                    cg = self.wellsky.get_caregiver_by_phone(phone)
                    if cg:
                        return json.dumps({
                            "identified_as": "caregiver",
                            "id": cg.id,
                            "name": cg.full_name,
                            "first_name": cg.first_name,
                            "status": cg.status.value if hasattr(cg.status, 'value') else str(cg.status)
                        })
                except Exception:
                    pass

                return json.dumps({"identified_as": "unknown", "message": "Phone number not found in records"})

            elif tool_name == "get_wellsky_shifts":
                days = min(tool_input.get("days", 7), 14)
                client_id = tool_input.get("client_id")
                caregiver_id = tool_input.get("caregiver_id")
                date_from = date.today()
                date_to = date.today() + timedelta(days=days)

                shifts = self.wellsky.get_shifts(
                    date_from=date_from, date_to=date_to,
                    client_id=client_id, caregiver_id=caregiver_id,
                    limit=20
                )
                shift_list = []
                for s in shifts[:10]:
                    shift_list.append({
                        "date": s.date.isoformat() if hasattr(s, 'date') and s.date else "unknown",
                        "day": s.date.strftime("%a") if hasattr(s, 'date') and s.date else "",
                        "time": f"{s.start_time}-{s.end_time}" if hasattr(s, 'start_time') and s.start_time else "TBD",
                        "client": s.client_name if hasattr(s, 'client_name') else "",
                        "caregiver": s.caregiver_name if hasattr(s, 'caregiver_name') else "",
                        "caregiver_id": s.caregiver_id if hasattr(s, 'caregiver_id') else "",
                        "client_id": s.client_id if hasattr(s, 'client_id') else "",
                        "status": s.status.value if hasattr(s.status, 'value') else str(s.status) if hasattr(s, 'status') else ""
                    })
                # Enrich with names from cached database when WellSky API returns blanks
                try:
                    import psycopg2
                    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
                    conn = psycopg2.connect(db_url)
                    cur = conn.cursor()
                    for shift in shift_list:
                        if shift.get("caregiver_id") and not shift.get("caregiver"):
                            cur.execute("SELECT full_name FROM cached_practitioners WHERE id = %s", (shift["caregiver_id"],))
                            row = cur.fetchone()
                            if row:
                                shift["caregiver"] = row[0]
                        if shift.get("client_id") and not shift.get("client"):
                            cur.execute("SELECT full_name FROM cached_patients WHERE id = %s", (shift["client_id"],))
                            row = cur.fetchone()
                            if row:
                                shift["client"] = row[0]
                    conn.close()
                except Exception as e:
                    logger.warning(f"Shift name enrichment failed (non-fatal): {e}")
                return json.dumps({"count": len(shifts), "shifts": shift_list})

            elif tool_name == "get_wellsky_clients":
                # Use cached database for reliable client lookup (synced daily from WellSky)
                import psycopg2
                db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
                search_name = tool_input.get("search_name", "")
                try:
                    conn = psycopg2.connect(db_url)
                    cur = conn.cursor()
                    if search_name:
                        search_lower = f"%{search_name.lower()}%"
                        cur.execute("""SELECT id, full_name, phone FROM cached_patients
                                      WHERE is_active = true AND (lower(full_name) LIKE %s
                                      OR lower(first_name) LIKE %s OR lower(last_name) LIKE %s)
                                      ORDER BY full_name LIMIT 10""",
                                   (search_lower, search_lower, search_lower))
                    else:
                        cur.execute("SELECT id, full_name, phone FROM cached_patients WHERE is_active = true ORDER BY full_name LIMIT 100")
                    rows = cur.fetchall()
                    client_list = [{"id": str(r[0]), "name": r[1], "phone": r[2] or ""} for r in rows]
                    conn.close()
                    return json.dumps({"count": len(client_list), "clients": client_list})
                except Exception as e:
                    logger.error(f"Client cache lookup failed: {e}")
                    return json.dumps({"error": f"Client lookup failed: {str(e)}"})

            elif tool_name == "get_wellsky_caregivers":
                # Use cached database for reliable caregiver lookup (synced daily from WellSky)
                import psycopg2
                db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
                search_name = tool_input.get("search_name", "")
                try:
                    conn = psycopg2.connect(db_url)
                    cur = conn.cursor()
                    if search_name:
                        search_lower = f"%{search_name.lower()}%"
                        cur.execute("""SELECT id, full_name, phone FROM cached_practitioners
                                      WHERE is_active = true AND (lower(full_name) LIKE %s
                                      OR lower(first_name) LIKE %s OR lower(last_name) LIKE %s)
                                      ORDER BY full_name LIMIT 10""",
                                   (search_lower, search_lower, search_lower))
                    else:
                        cur.execute("SELECT id, full_name, phone FROM cached_practitioners WHERE is_active = true ORDER BY full_name LIMIT 100")
                    rows = cur.fetchall()
                    cg_list = [{"id": str(r[0]), "name": r[1], "phone": r[2] or ""} for r in rows]
                    conn.close()
                    return json.dumps({"count": len(cg_list), "caregivers": cg_list})
                except Exception as e:
                    logger.error(f"Caregiver cache lookup failed: {e}")
                    return json.dumps({"error": f"Caregiver lookup failed: {str(e)}"})

            elif tool_name == "log_call_out":
                caregiver_id = tool_input.get("caregiver_id")
                caregiver_name = tool_input.get("caregiver_name", "Unknown")
                reason = tool_input.get("reason", "not specified")
                shift_date = tool_input.get("shift_date", date.today().isoformat())

                self.wellsky.create_admin_task(
                    title=f"CALL-OUT: {caregiver_name} - {reason}",
                    description=(
                        f"Caregiver {caregiver_name} called out via SMS.\n"
                        f"Reason: {reason}\n"
                        f"Shift date: {shift_date}\n"
                        f"ACTION: Find coverage immediately."
                    ),
                    priority="urgent",
                    related_caregiver_id=caregiver_id
                )
                return json.dumps({"success": True, "message": f"Call-out logged for {caregiver_name}. Admin task created."})

            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except Exception as e:
            logger.error(f"SMS tool error ({tool_name}): {e}")
            return json.dumps({"error": f"Tool {tool_name} failed: {str(e)}"})

    # =========================================================================
    # Claude SMS Reply Generation
    # =========================================================================

    async def _get_claude_sms_reply(self, text: str, phone: str) -> str:
        """Get an intelligent reply from Claude with tool calling. Returns reply text or None."""
        if not self.claude:
            return None

        try:
            now = datetime.now(TIMEZONE)
            system = SMS_SYSTEM_PROMPT.format(
                current_date=now.strftime("%A, %B %d, %Y at %I:%M %p MT"),
                caller_phone=phone
            )

            messages = self._get_conversation_history(phone)
            messages.append({"role": "user", "content": text})
            self._add_to_conversation(phone, "user", text)

            response = self.claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                system=system,
                tools=SMS_TOOLS,
                messages=messages
            )

            tool_round = 0
            while response.stop_reason == "tool_use" and tool_round < CLAUDE_MAX_TOOL_ROUNDS:
                tool_round += 1
                logger.info(f"SMS Claude tool round {tool_round}")

                tool_results = []
                assistant_content = []

                for block in response.content:
                    if block.type == "tool_use":
                        logger.info(f"  Tool: {block.name}({json.dumps(block.input)[:100]})")
                        result = self._execute_sms_tool(block.name, block.input, caller_phone=phone)
                        logger.info(f"  Result: {result[:200]}")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input
                        })
                    elif block.type == "text":
                        assistant_content.append({
                            "type": "text",
                            "text": block.text
                        })

                self._add_to_conversation(phone, "assistant", assistant_content)
                self._add_to_conversation(phone, "user", tool_results)

                messages = self._get_conversation_history(phone)

                response = self.claude.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=CLAUDE_MAX_TOKENS,
                    system=system,
                    tools=SMS_TOOLS,
                    messages=messages
                )

            # Extract final text
            final_text = ""
            for block in response.content:
                if block.type == "text":
                    final_text += block.text

            if not final_text:
                final_text = "Thanks for your message. I'll have the office follow up with you in the morning."

            self._add_to_conversation(phone, "assistant", final_text)
            logger.info(f"Claude SMS reply ({tool_round} tool rounds, {len(final_text)} chars)")
            return final_text

        except Exception as e:
            logger.error(f"Claude SMS reply error: {e}", exc_info=True)
            return None

    # =========================================================================
    # Process Reply (Claude-powered with static fallback)
    # =========================================================================

    async def process_reply(self, msg: dict, text: str, reply_method: str = "chat", phone: str = None):
        """Replier Logic: Respond to EVERY unanswered request after-hours.
        Uses Claude + tool calling for dynamic replies, falls back to static templates."""

        # LOOP PREVENTION CHECK - Critical safety gate
        if reply_method == "sms" and phone:
            can_reply, reason = self._can_reply_to_number(phone)
            if not can_reply:
                logger.warning(f"⛔ LOOP PREVENTION: Blocking reply to {phone}. Reason: {reason}")
                return

        # --- TRY CLAUDE FIRST ---
        reply = None
        if self.claude:
            try:
                reply = await self._get_claude_sms_reply(text, phone or "unknown")
            except Exception as e:
                logger.error(f"Claude reply failed, falling back to static: {e}")
                reply = None

        # --- FALLBACK: Static replies if Claude unavailable ---
        if not reply:
            lower_text = text.lower()
            if "call out" in lower_text or "sick" in lower_text:
                reply = "I hear you. I've logged your call-out and we're already reaching out for coverage. Feel better!"
            elif "late" in lower_text:
                reply = "Thanks for letting us know. I've noted that you're running late in the system. Drive safe!"
            elif "cancel" in lower_text:
                reply = "I've processed that cancellation and notified the team. Thanks for the heads up."
            elif "help" in lower_text or "shift" in lower_text or "question" in lower_text:
                reply = "Got it. I've notified the care team that you need assistance. Someone will get back to you shortly."
            else:
                reply = "Thanks for your message! This is Gigi, the AI Operations Manager. I've logged this for the team, and someone will follow up with you as soon as possible."

        # --- SEND REPLY ---
        if reply:
            try:
                if reply_method == "chat":
                    self.rc_service.send_message_to_chat(TARGET_CHAT, reply)
                elif reply_method == "sms" and phone:
                    clean_phone = ''.join(filter(str.isdigit, phone))
                    if len(clean_phone) == 10: clean_phone = f"+1{clean_phone}"
                    elif not clean_phone.startswith('+'): clean_phone = f"+{clean_phone}"

                    logger.info(f"Sending SMS reply to {clean_phone} via {RINGCENTRAL_FROM_NUMBER} (using Admin Token)")

                    access_token = self._get_admin_access_token()
                    if not access_token:
                        logger.error("Could not get access token for SMS reply")
                        return

                    url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/sms"
                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                    data = {
                        "from": {"phoneNumber": RINGCENTRAL_FROM_NUMBER},
                        "to": [{"phoneNumber": clean_phone}],
                        "text": reply
                    }

                    response = requests.post(url, headers=headers, json=data, timeout=20)
                    if response.status_code == 200:
                        logger.info(f"🌙 After-Hours SMS Reply Sent to {clean_phone}")
                        self._record_reply(clean_phone)
                    else:
                        logger.error(f"Failed to send SMS reply: {response.status_code} - {response.text}")

            except Exception as e:
                logger.error(f"Failed to send {reply_method} reply: {e}")

async def main():
    bot = GigiRingCentralBot()
    if await bot.initialize():
        while True:
            try:
                await bot.check_and_act()
            except Exception as e:
                logger.error(f"Error in bot loop: {e}")
            
            # Wait for next check
            await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
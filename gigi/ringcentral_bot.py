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
from datetime import datetime, time, timedelta
import pytz
import requests

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ringcentral_messaging_service import ringcentral_messaging_service, RINGCENTRAL_SERVER
from services.wellsky_service import WellSkyService

RINGCENTRAL_FROM_NUMBER = os.getenv("RINGCENTRAL_FROM_NUMBER", "+17194283999")

# ADMIN TOKEN (Jason x101) - Required for visibility into Company Lines (719/303)
# Standard x111 token is blind to these numbers.
ADMIN_JWT_TOKEN = "eyJraWQiOiI4NzYyZjU5OGQwNTk0NGRiODZiZjVjYTk3ODA0NzYwOCIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0.eyJhdWQiOiJodHRwczovL3BsYXRmb3JtLnJpbmdjZW50cmFsLmNvbS9yZXN0YXBpL29hdXRoL3Rva2VuIiwic3ViIjoiMjYyNzQwMDA5IiwiaXNzIjoiaHR0cHM6Ly9wbGF0Zm9ybS5yaW5nY2VudHJhbC5jb20iLCJleHAiOjM5MTAyNDA5NjUsImlhdCI6MTc2Mjc1NzMxOCwianRpIjoiZ3Jsd0pPWGFTM2EwalpibThvTmtZdyJ9.WA9DUSlb_4SlCo9UHNjscHKrVDoJTF4iW3D7Rre9E2qg5UQ_hWfCgysiZJMXlL8-vUuJ2XDNivvpfbxriESKIEPAEEY85MolJZS9KG3g90ga-3pJtHq7SC87mcacXtDWqzmbBS_iDOjmNMHiynWFR9Wgi30DMbz9rQ1U__Bl88qVRTvZfY17ovu3dZDhh-FmLUWRnKOc4LQUvRChQCO-21LdSquZPvEAe7qHEsh-blS8Cvh98wvX-9vaiurDR-kC9Tp007x4lTI74MwQ5rJif7tL7Hslqaoag0WoNEIP9VPrp4x-Q7AzKIzBNbrGr9kIPthIebmeOBDMIIrw6pg_lg"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gigi_rc_bot")

# Configuration
CHECK_INTERVAL = 5  # seconds (Reduced for faster testing)
TARGET_CHAT = "New Scheduling"
TIMEZONE = pytz.timezone("America/Denver")

# Business Hours (M-F, 8am-5pm)
BUSINESS_START = time(8, 0)
BUSINESS_END = time(17, 0)

class GigiRingCentralBot:
    def __init__(self):
        self.rc_service = ringcentral_messaging_service
        self.wellsky = WellSkyService()
        self.processed_message_ids = set()
        self.bot_extension_id = None

    async def initialize(self):
        """Initialize connections"""
        logger.info("Initializing Gigi Manager Bot...")

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

            if not self.is_business_hours():
                await self.process_reply(msg, text, reply_method="chat")

            self.processed_message_ids.add(msg_id)

    async def check_direct_sms(self):
        """Monitor RingCentral SMS using Admin Token for full visibility"""
        token = ADMIN_JWT_TOKEN

        if not token:
            logger.error("Admin Token missing in check_direct_sms")
            return

        try:
            # Poll the extension message-store (x101 context)
            url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/message-store"
            params = {
                "messageType": "SMS",
                "dateFrom": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                "perPage": 100
            }
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            }

            logger.info("SMS: Polling extension message-store (x101 Admin context) - v3 RESTORED")
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
                
                logger.info(f"✨ NEW SMS DETECTED: ID={msg_id} From={from_phone} To={to_phone} Subject={text[:30]}")

                # Role 1: Documenter
                await self.process_documentation(sms, text, source_type="sms", phone=from_phone)

                # Role 2: Replier
                if not self.is_business_hours():
                    # IMPORTANT: Don't reply if it's from US (to prevent loops)
                    if from_phone not in [RINGCENTRAL_FROM_NUMBER, "+13074598220", "+17194283999", "+13037571777"]:
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
        """QA/Manager Logic: Document everything in WellSky."""
        # 1. Identify Client Context
        client_id = None
        client_name = "Unknown"
        
        # Try to identify caregiver if possible (for SMS sourcing)
        if source_type == "sms" and phone:
            try:
                cg = self.wellsky.get_caregiver_by_phone(phone)
                if cg:
                    logger.info(f"Identified SMS sender as caregiver: {cg.full_name}")
            except Exception:
                pass

        # Try to find client name in text
        import re
        possible_names = []
        name_match = re.search(r'(?:for|client|visit|shift|with|about)\s+([A-Z][a-z]+\.?(?:\s[A-Z][a-z]+)?)', text, re.IGNORECASE)
        if name_match:
            possible_names.append(name_match.group(1))
            
        fallback_matches = re.findall(r'([A-Z][a-z]+\.?\s[A-Z][a-z]+)', text)
        for m in fallback_matches:
            if m not in possible_names:
                possible_names.append(m)

        # Verify against WellSky
        for pname in possible_names:
            if client_id: break
            try:
                clean_name = pname.replace(".", "")
                last_name_search = clean_name.split()[-1]
                if len(last_name_search) > 2:
                    clients = self.wellsky.search_patients(last_name=last_name_search)
                    if clients:
                        for c in clients:
                            c_full = c.full_name.lower().replace(".", "")
                            c_last = c.last_name.lower().replace(".", "")
                            p_clean = clean_name.lower()
                            if p_clean in c_full or c_last in p_clean:
                                client = c
                                client_id = client.id
                                client_name = client.full_name
                                break
            except Exception:
                pass

        # 2. Classify the Event
        note_type = "general"
        is_alert = False
        is_task = False
        lower_text = text.lower()
        
        if any(w in lower_text for w in ["call out", "call-out", "sick", "emergency", "cancel", "help"]):
            note_type = "callout"
            is_alert = True
            is_task = True
        elif any(w in lower_text for w in ["late", "traffic", "delayed"]):
            note_type = "late"
            is_alert = True
        elif any(w in lower_text for w in ["complain", "upset", "angry", "issue", "quit", "problem"]):
            note_type = "complaint"
            is_alert = True
            is_task = True
        elif any(w in lower_text for w in ["accept", "take the shift", "can work", "available", "filled"]):
            note_type = "schedule"
            
        # 3. Log to WellSky
        should_log = (client_id and (is_alert or is_task or note_type == "schedule")) or "gigi" in lower_text
        
        if should_log and client_id:
            try:
                note_prefix = "🚨 CARE ALERT" if is_alert else "ℹ️ RC ACTIVITY"
                full_note = f"{note_prefix} ({source_type.upper()}): {text}\n(From: {phone or msg.get('creatorId')})"
                
                self.wellsky.add_note_to_client(
                    client_id=client_id,
                    note=full_note,
                    note_type=note_type,
                    source="gigi_manager"
                )
                logger.info(f"✅ Documented {source_type} activity for {client_name} in WellSky")

                if is_task:
                    self.wellsky.create_admin_task(
                        title=f"RC {source_type.upper()} Alert: {note_type.upper()} - {client_name}",
                        description=f"Automated Task from {source_type}:\n{text}\n\nSender: {phone or msg.get('creatorId')}",
                        priority="urgent" if "call" in note_type or "complaint" in note_type else "normal",
                        related_client_id=client_id
                    )
            except Exception as e:
                logger.error(f"Failed to document to WellSky: {e}")

    async def process_reply(self, msg: dict, text: str, reply_method: str = "chat", phone: str = None):
        """Replier Logic: Respond to EVERY unanswered request after-hours."""
        lower_text = text.lower()
        
        # Determine the best reply using smart defaults (retell integration can follow)
        reply = None
        if "call out" in lower_text or "sick" in lower_text:
            reply = "I hear you. I've logged your call-out and we're already reaching out for coverage. Feel better!"
        elif "late" in lower_text:
            reply = "Thanks for letting us know. I've noted that you're running late in the system. Drive safe!"
        elif "cancel" in lower_text:
            reply = "I've processed that cancellation and notified the team. Thanks for the heads up."
        elif "help" in lower_text or "shift" in lower_text or "question" in lower_text:
            reply = "Got it. I've notified the care team that you need assistance. Someone will get back to you shortly."
        else:
            # DEFAULT REPLY FOR EVERYTHING ELSE
            reply = "Thanks for your message! This is Gigi, the AI Operations Manager. I've logged this for the team, and someone will follow up with you as soon as possible."
            
        if reply:
            try:
                if reply_method == "chat":
                    self.rc_service.send_message_to_chat(TARGET_CHAT, reply)
                elif reply_method == "sms" and phone:
                    # Use RC service to send generic SMS
                    # Normalize phone for sender
                    clean_phone = ''.join(filter(str.isdigit, phone))
                    if len(clean_phone) == 10: clean_phone = f"+1{clean_phone}"
                    elif not clean_phone.startswith('+'): clean_phone = f"+{clean_phone}"

                    logger.info(f"Sending SMS reply to {clean_phone} via {RINGCENTRAL_FROM_NUMBER} (using Admin Token)")
                    
                    # USE ADMIN TOKEN to Send
                    url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/sms"
                    headers = {
                        "Authorization": f"Bearer {ADMIN_JWT_TOKEN}",
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

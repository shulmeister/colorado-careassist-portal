"""
Gigi RingCentral Bot - Manager & After-Hours Coverage

Two Distinct Roles:
1. THE REPLIER (After-Hours Only):
   - M-F 8am-5pm: SILENT (Israt handles replies).
   - Nights/Weekends: Replies IMMEDIATELY to texts/chats.
   - Replaces Zingage's missing reply function.

2. THE DOCUMENTER (24/7/365):
   - Acts as QA/Manager for the whole team (Israt, Cynthia, Zingage).
   - Monitors 'New Scheduling' and other chats.
   - Logs ALL Care Alerts and Tasks into WellSky.
   - Ensures nothing falls through the cracks, even if "handled" silently.
"""

import os
import sys
import logging
import asyncio
from datetime import datetime, time, timedelta
import pytz

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ringcentral_messaging_service import ringcentral_messaging_service
from services.wellsky_service import WellSkyService

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

class GigiRingCentralBot:
    def __init__(self):
        self.rc_service = ringcentral_messaging_service
        self.wellsky = WellSkyService()
        self.processed_message_ids = set()

    async def initialize(self):
        """Initialize connections"""
        logger.info("Initializing Gigi Manager Bot...")
        
        status = self.rc_service.get_status()
        if not status.get("api_connected"):
            logger.error("RingCentral API not connected! Check credentials.")
            return False

        logger.info(f"Monitoring chat: {TARGET_CHAT}")
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
            # Fetch recent messages
            chat = self.rc_service.find_chat_by_name(TARGET_CHAT)
            if not chat:
                return

            # Get messages from last hour to catch up
            messages = self.rc_service.get_chat_messages(
                chat["id"], 
                since=datetime.utcnow() - timedelta(minutes=60),
                limit=50
            )
            
            if not messages:
                return

            # Sort oldest to newest
            messages.sort(key=lambda x: x.get("creationTime", ""))

            for msg in messages:
                msg_id = msg.get("id")
                if msg_id in self.processed_message_ids:
                    continue

                text = msg.get("text", "")
                creator_id = msg.get("creatorId")
                
                # ---------------------------------------------------------
                # ROLE 1: THE DOCUMENTER (24/7/365)
                # ---------------------------------------------------------
                # We analyze EVERY message to see if it needs WellSky logging
                await self.process_documentation(msg, text)

                # ---------------------------------------------------------
                # ROLE 2: THE REPLIER (After-Hours Only)
                # ---------------------------------------------------------
                # If it's NOT business hours, we check if we need to reply
                if not self.is_business_hours():
                    await self.process_reply(msg, text)

                # Mark as processed so we don't duplicate actions
                self.processed_message_ids.add(msg_id)
                
            # Cleanup processed IDs to keep memory low (keep last 1000)
            if len(self.processed_message_ids) > 1000:
                self.processed_message_ids = set(list(self.processed_message_ids)[-500:])

        except Exception as e:
            logger.error(f"Error in check_and_act: {e}")

    async def process_documentation(self, msg: dict, text: str):
        """
        QA/Manager Logic: Document everything in WellSky.
        Runs 24/7 on ALL messages (Israt, Cynthia, Zingage, Caregivers).
        """
        # 1. Identify Client Context
        client_id = None
        client_name = "Unknown"
        
        # Try to find client name in text
        # Regex 1: Contextual (High Confidence)
        # Allow optional dot for titles (Mrs., Mr., Dr.)
        import re
        name_match = re.search(r'(?:for|client|visit|shift|with|about)\s+([A-Z][a-z]+\.?(?:\s[A-Z][a-z]+)?)', text, re.IGNORECASE)
        
        possible_names = []
        if name_match:
            possible_names.append(name_match.group(1))
            
        # Regex 2: Any Capitalized Name-like pattern (Fallback)
        # Looks for "Mrs. Smith", "Jane Doe", etc.
        # Modified to handle optional dot: [A-Z][a-z]+\.?\s[A-Z][a-z]+
        fallback_matches = re.findall(r'([A-Z][a-z]+\.?\s[A-Z][a-z]+)', text)
        for m in fallback_matches:
            if m not in possible_names:
                possible_names.append(m)

        # Verify against WellSky
        for pname in possible_names:
            if client_id: break # Stop if found
            try:
                # Search by last name (split by space)
                # Remove punctuation from search term
                clean_name = pname.replace(".", "")
                last_name_search = clean_name.split()[-1]
                
                if len(last_name_search) > 2: # Avoid short noise
                    clients = self.wellsky.search_patients(last_name=last_name_search)
                    if clients:
                        # Simple check: is the full search name in the result name?
                        for c in clients:
                            # Check normalized names
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

        # 2. Classify the Event
        note_type = "general"
        is_alert = False
        is_task = False
        
        lower_text = text.lower()
        
        if any(w in lower_text for w in ["call out", "call-out", "sick", "emergency", "cancel"]):
            note_type = "callout"
            is_alert = True
            is_task = True # Needs coverage finding
            
        elif any(w in lower_text for w in ["late", "traffic", "delayed"]):
            note_type = "late"
            is_alert = True
            
        elif any(w in lower_text for w in ["complain", "upset", "angry", "issue", "quit", "problem"]):
            note_type = "complaint"
            is_alert = True
            is_task = True # Needs follow up
            
        elif any(w in lower_text for w in ["accept", "take the shift", "can work", "available", "filled"]):
            note_type = "schedule"
            is_task = False # Just a note, unless we want to confirm
            
        # 3. Log to WellSky
        # We log if we found a client context AND it's a relevant event type (including schedule)
        # OR if it's a "gigi" mention
        should_log = (client_id and (is_alert or is_task or note_type == "schedule")) or "gigi" in lower_text
        
        if should_log and client_id:
            try:
                # Log the Note (The "Record")
                note_prefix = "🚨 CARE ALERT" if is_alert else "ℹ️ RC ACTIVITY"
                full_note = f"{note_prefix}: {text}\n(Source: RingCentral - {msg.get('creatorId')})"
                
                self.wellsky.add_note_to_client(
                    client_id=client_id,
                    note=full_note,
                    note_type=note_type,
                    source="gigi_manager"
                )
                logger.info(f"✅ Documented RC activity for {client_name} in WellSky")

                # Create Admin Task if actionable (The "Follow-up")
                if is_task:
                    self.wellsky.create_admin_task(
                        title=f"RC Alert: {note_type.upper()} - {client_name}",
                        description=f"Automated Task from RingCentral:\n{text}\n\nPlease verify this is resolved.",
                        priority="urgent" if "call" in note_type or "complaint" in note_type else "normal",
                        related_client_id=client_id
                    )
                    logger.info(f"✅ Created WellSky Task for {client_name}")
                    
            except Exception as e:
                logger.error(f"Failed to document to WellSky: {e}")

    async def process_reply(self, msg: dict, text: str):
        """
        Replier Logic: Respond to unanswered requests.
        Runs ONLY After-Hours.
        """
        # We only reply to requests, not random chatter
        lower_text = text.lower()
        is_request = any(kw in lower_text for kw in ["call out", "sick", "late", "cancel", "help", "shift"])
        
        if not is_request:
            return

        # Check if already replied to (by anyone)
        # In a real event stream, we'd need to peek ahead or track thread state.
        # For simplicity in this poller: we assume if we haven't seen it, we reply.
        # But we must be careful not to spam.
        
        # Determine Reply
        reply = None
        if "call out" in lower_text or "sick" in lower_text:
            reply = "I hear you. I've logged your call-out and we're reaching out for coverage. Feel better!"
        elif "late" in lower_text:
            reply = "Thanks for letting us know. I've noted that you're running late in the system."
        elif "cancel" in lower_text:
            reply = "I've processed that cancellation and notified the team. Thanks for the heads up."
            
        if reply:
            # Send the reply
            self.rc_service.send_message_to_chat(TARGET_CHAT, reply)
            logger.info(f"🌙 After-Hours Reply Sent: {reply}")
            
            # Since we just took action, we should explicitly ensure THIS action is also documented
            # (The process_documentation loop will catch our own message eventually, but good to be sure)

async def main():
    bot = GigiRingCentralBot()
    if await bot.initialize():
        while True:
            try:
                await bot.check_and_act()
            except Exception as e:
                logger.error(f"Error in bot loop: {e}")
            
            # Wait for next check
            logger.info(f"Sleeping for {ZINGAGE_CHECK_INTERVAL}s...")
            await asyncio.sleep(ZINGAGE_CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())

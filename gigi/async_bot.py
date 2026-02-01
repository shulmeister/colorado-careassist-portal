"""
Async Minimal Bot - Designed to run INSIDE FastAPI
Now with WellSky Logging!
"""
import os
import sys
import asyncio
import logging
import requests
import re
from datetime import datetime, timedelta

# Add project root to path for services import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import WellSky Service
try:
    from services.wellsky_service import WellSkyService
    wellsky_service = WellSkyService()
    WELLSKY_AVAILABLE = True
except Exception as e:
    wellsky_service = None
    WELLSKY_AVAILABLE = False
    print(f"WellSky Import Failed: {e}")

# Configure logging
logger = logging.getLogger("gigi_bot")

# ADMIN TOKEN (Jason x101)
ADMIN_JWT_TOKEN = "eyJraWQiOiI4NzYyZjU5OGQwNTk0NGRiODZiZjVjYTk3ODA0NzYwOCIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0.eyJhdWQiOiJodHRwczovL3BsYXRmb3JtLnJpbmdjZW50cmFsLmNvbS9yZXN0YXBpL29hdXRoL3Rva2VuIiwic3ViIjoiMjYyNzQwMDA5IiwiaXNzIjoiaHR0cHM6Ly9wbGF0Zm9ybS5yaW5nY2VudHJhbC5jb20iLCJleHAiOjM5MTAyNDA5NjUsImlhdCI6MTc2Mjc1NzMxOCwianRpIjoiZ3Jsd0pPWGFTM2EwalpibThvTmtZdyJ9.WA9DUSlb_4SlCo9UHNjscHKrVDoJTF4iW3D7Rre9E2qg5UQ_hWfCgysiZJMXlL8-vUuJ2XDNivvpfbxriESKIEPAEEY85MolJZS9KG3g90ga-3pJtHq7SC87mcacXtDWqzmbBS_iDOjmNMHiynWFR9Wgi30DMbz9rQ1U__Bl88qVRTvZfY17ovu3dZDhh-FmLUWRnKOc4LQUvRChQCO-21LdSquZPvEAe7qHEsh-blS8Cvh98wvX-9vaiurDR-kC9Tp007x4lTI74MwQ5rJif7tL7Hslqaoag0WoNEIP9VPrp4x-Q7AzKIzBNbrGr9kIPthIebmeOBDMIIrw6pg_lg"

RINGCENTRAL_SERVER = "https://platform.ringcentral.com"
RINGCENTRAL_FROM_NUMBER = "+17194283999"
ADMIN_PHONE = "+16039971495"

class AsyncGigiBot:
    def __init__(self):
        self.processed_ids = set()
        self.token = None

    def get_token(self):
        # Synchronous token fetch
        url = f"{RINGCENTRAL_SERVER}/restapi/oauth/token"
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": ADMIN_JWT_TOKEN
        }
        CLIENT_ID = "8HQNG4wPwl3cejTAdz1ZBX"
        CLIENT_SECRET = "5xwSbWIOKZvc0ADlafSZdWZ0SpwfRSgZ1cVA5AmUr5mW"
        
        try:
            response = requests.post(url, auth=(CLIENT_ID, CLIENT_SECRET), data=data, timeout=30)
            if response.status_code == 200:
                return response.json()["access_token"]
            logger.error(f"Token Fetch Failed: {response.text}")
            return None
        except Exception as e:
            logger.error(f"Token Exception: {e}")
            return None

    async def send_sms(self, to_phone, text):
        if not self.token: return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_sms_sync, to_phone, text)

    def _send_sms_sync(self, to_phone, text):
        url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/sms"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        data = {
            "from": {"phoneNumber": RINGCENTRAL_FROM_NUMBER},
            "to": [{"phoneNumber": to_phone}],
            "text": text
        }
        try:
            resp = requests.post(url, headers=headers, json=data)
            if resp.status_code == 200:
                logger.info(f"✅ SMS Sent to {to_phone}")
            else:
                logger.error(f"❌ Send Failed: {resp.text}")
        except Exception as e:
            logger.error(f"Send Exception: {e}")

    # --- DOCUMENTATION LOGIC ---
    def _document_sync(self, text, phone, source="sms"):
        """Synchronous documentation logic run in thread pool"""
        if not WELLSKY_AVAILABLE or not wellsky_service:
            return

        try:
            # 1. Identify Client Context
            client_id = None
            client_name = "Unknown"
            
            # Identify sender as caregiver if possible
            try:
                cg = wellsky_service.get_caregiver_by_phone(phone)
                if cg:
                    logger.info(f"Identified SMS sender as caregiver: {cg.full_name}")
            except Exception:
                pass

            # Find client name in text
            possible_names = []
            name_match = re.search(r'(?:for|client|visit|shift|with|about)\s+([A-Z][a-z]+\.?(?:\s[A-Z][a-z]+)?)', text, re.IGNORECASE)
            if name_match:
                possible_names.append(name_match.group(1))
            
            # 2. Classify Event
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

            # 3. Log to WellSky (Simple: Log to sender's profile if CG, or try to find Client)
            # For now, we'll try to find a client match to be smart
            for pname in possible_names:
                if client_id: break
                try:
                    search_term = pname.split()[-1]
                    clients = wellsky_service.search_patients(last_name=search_term)
                    if clients:
                        client = clients[0] # Take first match for speed
                        client_id = client.id
                        client_name = client.full_name
                except Exception:
                    pass
            
            if client_id:
                note_prefix = "🚨 CARE ALERT" if is_alert else "ℹ️ RC SMS"
                full_note = f"{note_prefix}: {text}\n(From: {phone})"
                
                wellsky_service.add_note_to_client(
                    client_id=client_id,
                    note=full_note,
                    note_type=note_type,
                    source="gigi_manager"
                )
                logger.info(f"✅ Documented to WellSky Client: {client_name}")
                
                if is_task:
                    wellsky_service.create_admin_task(
                        title=f"SMS Alert: {note_type.upper()} - {client_name}",
                        description=f"Message: {text}\nFrom: {phone}",
                        priority="urgent",
                        related_client_id=client_id
                    )
            
        except Exception as e:
            logger.error(f"Documentation Error: {e}")

    async def document_message(self, text, phone):
        """Run documentation in thread pool"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._document_sync, text, phone)

    async def check_messages(self):
        if not self.token: return

        # 12 hour lookback
        date_from = (datetime.utcnow() - timedelta(hours=12)).isoformat()
        
        # Fetch both Inbound and Outbound to see full context
        url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/message-store"
        params = {"messageType": "SMS", "dateFrom": date_from, "perPage": 100}
        headers = {"Authorization": f"Bearer {self.token}"}

        loop = asyncio.get_event_loop()
        try:
            resp = await loop.run_in_executor(None, lambda: requests.get(url, headers=headers, params=params))
            
            if resp.status_code != 200:
                logger.error(f"Poll Failed: {resp.status_code}")
                return

            records = resp.json().get("records", [])
            
            # Group by remote phone number to handle conversations
            conversations = {}
            for msg in records:
                direction = msg.get("direction")
                # Identify the "other" party
                if direction == "Inbound":
                    remote_phone = msg.get("from", {}).get("phoneNumber")
                else:
                    remote_list = msg.get("to", [])
                    remote_phone = remote_list[0].get("phoneNumber") if remote_list else None
                
                if not remote_phone: continue
                
                if remote_phone not in conversations:
                    conversations[remote_phone] = []
                conversations[remote_phone].append(msg)

            # Process each conversation
            for phone, msgs in conversations.items():
                # Sort by creation time (oldest first)
                msgs.sort(key=lambda x: x.get("creationTime", ""))
                
                # Get the very last message in the thread
                last_msg = msgs[-1]
                last_direction = last_msg.get("direction")
                msg_id = str(last_msg.get("id"))
                
                # Logic: Only reply if the LAST action was them talking to us (Inbound)
                # And we haven't processed this specific message ID in this session yet
                if last_direction == "Inbound":
                    if msg_id in self.processed_ids:
                        continue
                        
                    text = last_msg.get("subject", "")
                    logger.info(f"📩 Unanswered Message from {phone}: {text[:30]}...")
                    
                    # 1. Document (Async) - Always document new inbound, even if we crash later
                    await self.document_message(text, phone)
                    
                    # 2. Reply
                    reply_text = "Thanks for your message! This is Gigi, the AI Operations Manager. I've logged this for the team, and someone will follow up with you as soon as possible."
                    lower_text = text.lower()
                    if "call out" in lower_text or "sick" in lower_text:
                        reply_text = "I hear you. I've logged your call-out and we're already reaching out for coverage. Feel better!"
                    
                    await self.send_sms(phone, reply_text)
                    
                    # Mark processed
                    self.processed_ids.add(msg_id)
                else:
                    # The last message was Outbound (from us), so we are caught up.
                    # Add the last inbound ID to processed so we don't trip up
                    for m in msgs:
                        self.processed_ids.add(str(m.get("id")))

        except Exception as e:
            logger.error(f"Poll Exception: {e}")

    async def run_loop(self):
        logger.info("🚀 Starting Async Bot Loop (With WellSky Logging)...")
        self.token = self.get_token()
        
        while True:
            try:
                if not self.token:
                    self.token = self.get_token()
                await self.check_messages()
            except Exception as e:
                logger.error(f"Bot Loop Error: {e}")
            await asyncio.sleep(5)

bot = AsyncGigiBot()
import os
import sys
import asyncio
import logging
import requests
import re
import json
from datetime import datetime, timedelta
import google.generativeai as genai

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

# CREDENTIALS (HARDCODED FOR RELIABILITY)
ADMIN_JWT_TOKEN = "eyJraWQiOiI4NzYyZjU5OGQwNTk0NGRiODZiZjVjYTk3ODA0NzYwOCIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0.eyJhdWQiOiJodHRwczovL3BsYXRmb3JtLnJpbmdjZW50cmFsLmNvbS9yZXN0YXBpL29hdXRoL3Rva2VuIiwic3ViIjoiMjYyNzQwMDA5IiwiaXNzIjoiaHR0cHM6Ly9wbGF0Zm9ybS5yaW5nY2VudHJhbC5jb20iLCJleHAiOjM5MTAyNDA5NjUsImlhdCI6MTc2Mjc1NzMxOCwianRpIjoiZ3Jsd0pPWGFTM2EwalpibThvTmtZdyJ9.WA9DUSlb_4SlCo9UHNjscHKrVDoJTF4iW3D7Rre9E2qg5UQ_hWfCgysiZJMXlL8-vUuJ2XDNivvpfbxriESKIEPAEEY85MolJZS9KG3g90ga-3pJtHq7SC87mcacXtDWqzmbBS_iDOjmNMHiynWFR9Wgi30DMbz9rQ1U__Bl88qVRTvZfY17ovu3dZDhh-FmLUWRnKOc4LQUvRChQCO-21LdSquZPvEAe7qHEsh-blS8Cvh98wvX-9vaiurDR-kC9Tp007x4lTI74MwQ5rJif7tL7Hslqaoag0WoNEIP9VPrp4x-Q7AzKIzBNbrGr9kIPthIebmeOBDMIIrw6pg_lg"
GEMINI_API_KEY = "AIzaSyB-67dmnNUmfJfvbEznwqLYcnMZBMPam8o"

# Constants
RINGCENTRAL_SERVER = "https://platform.ringcentral.com"
RINGCENTRAL_FROM_NUMBER = "+17194283999"
ADMIN_PHONE = "+16039971495"

# Initialize Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
    GEMINI_OK = True
    GEMINI_ERROR = None
except Exception as e:
    GEMINI_OK = False
    GEMINI_ERROR = str(e)

SYSTEM_PROMPT = """
You are Gigi, a real team member at Colorado Care Assist.
Your role: Respond to text messages from Caregivers.

Tone: Professional, calm, empathetic, and concise. You are NOT a robot.
Action: You have ALREADY logged their request to the WellSky system.

SCENARIOS:
1. Sick/Call-out: "I hear you. I've logged your call-out and we're reaching out for coverage. Feel better."
2. Late: "Thanks for letting us know. Drive safe."
3. General: "Got it. I've logged this for the team."

INSTRUCTIONS:
- Keep it under 160 characters if possible.
- Use the person's First Name if provided.
- Do NOT offer to do things you can't do.
- Do NOT say "as an AI".
"""

class AsyncGigiBot:
    def __init__(self):
        # We'll use a local session-based set for deduplication
        # But our main defense is checking if WE were the last sender in RC history
        self.processed_ids = set()
        self.token = None

    def get_token(self):
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
            return None
        except Exception as e:
            logger.error(f"Token Error: {e}")
            return None

    async def generate_smart_reply(self, incoming_text, name, sender_type):
        """Use Gemini to generate a context-aware reply"""
        if not GEMINI_OK:
            return f"Hi {name or ''}! I've logged your message for the team. (Diag: AI Offline - {GEMINI_ERROR})"
            
        try:
            prompt = f"""
            {SYSTEM_PROMPT}
            
            Incoming Text: "{incoming_text}"
            Sender Name: {name or 'Unknown'}
            Sender Type: {sender_type}
            
            Draft a reply:
            """
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
            return response.text.strip().replace('"', '')
        except Exception as e:
            logger.error(f"Gemini Error: {e}")
            return f"Hi {name or ''}! I've logged your message. Someone will follow up shortly."

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
        identified_name = None
        sender_type = "Unknown"
        
        # 0. Owner Check
        clean_phone = ''.join(filter(str.isdigit, phone))
        if clean_phone.endswith("6039971495"):
            return "Jason", "Owner"

        if not WELLSKY_AVAILABLE or not wellsky_service:
            return None, "Unknown"

        try:
            # 1. Identify Caregiver
            try:
                cg = wellsky_service.get_caregiver_by_phone(phone)
                if cg:
                    identified_name = cg.first_name
                    sender_type = "Caregiver"
                    logger.info(f"Identified CG: {cg.full_name}")
            except Exception:
                pass

            # 2. Log to WellSky
            client_id = None
            possible_names = re.findall(r'([A-Z][a-z]+)', text)
            for pname in possible_names:
                if client_id: break
                try:
                    search_term = pname.split()[-1]
                    clients = wellsky_service.search_patients(last_name=search_term)
                    if clients: client_id = clients[0].id
                except: pass
            
            if client_id:
                wellsky_service.add_note_to_client(client_id=client_id, note=f"Gigi SMS from {phone}: {text}", note_type="general", source="gigi_ai")
            else:
                # Always create at least an Admin Task
                wellsky_service.create_admin_task(
                    title=f"SMS from {identified_name or phone}", 
                    description=f"Message: {text}\nSender: {phone}", 
                    priority="normal"
                )

            return identified_name, sender_type
            
        except Exception as e:
            logger.error(f"Doc Error: {e}")
            return None, "Unknown"

    async def document_message(self, text, phone):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._document_sync, text, phone)

    async def check_messages(self):
        if not self.token: return
        date_from = (datetime.utcnow() - timedelta(hours=12)).isoformat()
        url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/message-store"
        params = {"messageType": "SMS", "dateFrom": date_from, "perPage": 100}
        headers = {"Authorization": f"Bearer {self.token}"}

        loop = asyncio.get_event_loop()
        try:
            resp = await loop.run_in_executor(None, lambda: requests.get(url, headers=headers, params=params))
            if resp.status_code != 200: return

            records = resp.json().get("records", [])
            conversations = {}
            for msg in records:
                direction = msg.get("direction")
                remote_phone = msg.get("from", {}).get("phoneNumber") if direction == "Inbound" else msg.get("to", [{}])[0].get("phoneNumber")
                if not remote_phone: continue
                if remote_phone not in conversations: conversations[remote_phone] = []
                conversations[remote_phone].append(msg)

            for phone, msgs in conversations.items():
                msgs.sort(key=lambda x: x.get("creationTime", ""))
                last_msg = msgs[-1]
                
                # CRITICAL DEFENSE: Only reply if the LAST message was from THEM
                if last_msg.get("direction") == "Inbound":
                    msg_id = str(last_msg.get("id"))
                    
                    # Deduplicate in current session
                    if msg_id in self.processed_ids:
                        continue
                    self.processed_ids.add(msg_id)
                        
                    text = last_msg.get("subject", "")
                    logger.info(f"📩 New Message from {phone}: {text[:30]}...")
                    
                    # 1. Document & Identify
                    first_name, sender_type = await self.document_message(text, phone)
                    
                    # 2. GENERATE SMART REPLY
                    reply_text = await self.generate_smart_reply(text, first_name, sender_type)
                    
                    # 3. Send SMS
                    await self.send_sms(phone, reply_text)
                else:
                    # Mark all messages in this thread as handled
                    for m in msgs:
                        self.processed_ids.add(str(m.get("id")))

        except Exception as e:
            logger.error(f"Poll Error: {e}")

    async def run_loop(self):
        logger.info("🚀 Starting Smart Gigi Bot...")
        self.token = self.get_token()
        while True:
            try:
                if not self.token: self.token = self.get_token()
                await self.check_messages()
            except Exception as e:
                logger.error(f"Loop Error: {e}")
            await asyncio.sleep(5)

bot = AsyncGigiBot()
"""
Async Minimal Bot - Designed to run INSIDE FastAPI
"""
import os
import sys
import asyncio
import logging
import requests
from datetime import datetime, timedelta

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
        # Synchronous token fetch (ok to block briefly on startup/refresh)
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
        
        # Run synchronous request in thread pool to avoid blocking FastAPI
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

    async def check_messages(self):
        if not self.token: return

        # 12 hour lookback
        date_from = (datetime.utcnow() - timedelta(hours=12)).isoformat()
        
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
            for msg in records:
                msg_id = str(msg.get("id"))
                if msg_id in self.processed_ids:
                    continue
                
                direction = msg.get("direction")
                from_ph = msg.get("from", {}).get("phoneNumber")
                text = msg.get("subject", "")
                
                # Only reply to Inbound messages
                if direction == "Inbound":
                    logger.info(f"📩 New Message from {from_ph}: {text[:30]}...")
                    
                    # Send Reply
                    reply_text = "Thanks for your message! This is Gigi, the AI Operations Manager. I've logged this for the team, and someone will follow up with you as soon as possible."
                    
                    # Custom replies
                    lower_text = text.lower()
                    if "call out" in lower_text or "sick" in lower_text:
                        reply_text = "I hear you. I've logged your call-out and we're already reaching out for coverage. Feel better!"
                    
                    await self.send_sms(from_ph, reply_text)
                    self.processed_ids.add(msg_id)
                else:
                    # Mark outbound as processed so we don't re-read them
                    self.processed_ids.add(msg_id)

        except Exception as e:
            logger.error(f"Poll Exception: {e}")

    async def run_loop(self):
        logger.info("🚀 Starting Async Bot Loop...")
        self.token = self.get_token()
        
        if self.token:
            await self.send_sms(ADMIN_PHONE, "🚑 Embedded Bot Online (running inside Web Process)")
        
        while True:
            try:
                if not self.token:
                    self.token = self.get_token()
                
                await self.check_messages()
            except Exception as e:
                logger.error(f"Bot Loop Error: {e}")
            
            await asyncio.sleep(5) # Poll every 5 seconds

# Singleton for import
bot = AsyncGigiBot()

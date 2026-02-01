"""
Minimal RingCentral Bot - Debug Mode
"""
import os
import sys
import time
import requests
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("minimal_bot")

# ADMIN TOKEN (Jason x101)
ADMIN_JWT_TOKEN = "eyJraWQiOiI4NzYyZjU5OGQwNTk0NGRiODZiZjVjYTk3ODA0NzYwOCIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0.eyJhdWQiOiJodHRwczovL3BsYXRmb3JtLnJpbmdjZW50cmFsLmNvbS9yZXN0YXBpL29hdXRoL3Rva2VuIiwic3ViIjoiMjYyNzQwMDA5IiwiaXNzIjoiaHR0cHM6Ly9wbGF0Zm9ybS5yaW5nY2VudHJhbC5jb20iLCJleHAiOjM5MTAyNDA5NjUsImlhdCI6MTc2Mjc1NzMxOCwianRpIjoiZ3Jsd0pPWGFTM2EwalpibThvTmtZdyJ9.WA9DUSlb_4SlCo9UHNjscHKrVDoJTF4iW3D7Rre9E2qg5UQ_hWfCgysiZJMXlL8-vUuJ2XDNivvpfbxriESKIEPAEEY85MolJZS9KG3g90ga-3pJtHq7SC87mcacXtDWqzmbBS_iDOjmNMHiynWFR9Wgi30DMbz9rQ1U__Bl88qVRTvZfY17ovu3dZDhh-FmLUWRnKOc4LQUvRChQCO-21LdSquZPvEAe7qHEsh-blS8Cvh98wvX-9vaiurDR-kC9Tp007x4lTI74MwQ5rJif7tL7Hslqaoag0WoNEIP9VPrp4x-Q7AzKIzBNbrGr9kIPthIebmeOBDMIIrw6pg_lg"

RINGCENTRAL_SERVER = "https://platform.ringcentral.com"
# Hardcoded FROM number (Company Line)
RINGCENTRAL_FROM_NUMBER = "+17194283999"
# Hardcoded ADMIN phone for health check
ADMIN_PHONE = "+16039971495"

def get_access_token():
    url = f"{RINGCENTRAL_SERVER}/restapi/oauth/token"
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": ADMIN_JWT_TOKEN
    }
    # We need client ID/Secret for OAuth even with JWT
    # Using the ones from your file
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

def send_sms(token, to_phone, text):
    url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/sms"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "from": {"phoneNumber": RINGCENTRAL_FROM_NUMBER},
        "to": [{"phoneNumber": to_phone}],
        "text": text
    }
    try:
        resp = requests.post(url, headers=headers, json=data)
        if resp.status_code == 200:
            logger.info(f"✅ Sent SMS to {to_phone}")
            return True
        else:
            logger.error(f"❌ Failed to send SMS: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Send Exception: {e}")
        return False

def main():
    logger.info("Starting Minimal Bot...")
    
    # 1. Get Token
    token = get_access_token()
    if not token:
        logger.error("Could not get token. Exiting.")
        sys.exit(1)
        
    # 2. Send Health Check
    send_sms(token, ADMIN_PHONE, "🚑 Minimal Bot Online. If you see this, the worker is running.")
    
    # 3. Simple Loop (just keep process alive for now)
    while True:
        logger.info("Minimal Bot Heartbeat...")
        time.sleep(60)

if __name__ == "__main__":
    main()

import requests
import json
import os

# Point to LOCAL server
BASE_URL = "http://localhost:8765"

def test_voice_tools():
    print("📞 TESTING VOICE TOOLS (WEBHOOK)...")
    
    # 1. Health Check
    res = requests.get(f"{BASE_URL}/gigi/health")
    print(f"   Health Check: {res.status_code}")

    # 2. Verify Caller (Caregiver Simulation)
    payload = {
        "call_id": "test_voice_123",
        "arguments": {"phone_number": "+17205551234"}
    }
    # Note the /gigi prefix from unified_app mounting
    res = requests.post(f"{BASE_URL}/gigi/webhook/retell/function/verify_caller", json=payload)
    print(f"   Verify Caller: {res.status_code}")
    if res.status_code == 200:
        print(f"   Result: {res.json().get('caller_type', 'unknown')}")
    else:
        print(f"   Error: {res.text[:100]}")

def test_text_replies():
    print("\n💬 TESTING TEXT REPLIES (SMS WEBHOOK)...")
    
    # Simulate an inbound "I am sick" text
    payload = {
        "event": "/restapi/v1.0/account/~/extension/~/message-store/instant?type=SMS",
        "body": {
            "direction": "Inbound",
            "from": {"phoneNumber": "+16039971495"}, # Jason's phone
            "to": [{"phoneNumber": "+17194283999"}],
            "subject": "I am sick and cannot make my shift"
        }
    }
    
    # Note the /gigi prefix
    res = requests.post(f"{BASE_URL}/gigi/webhook/ringcentral-sms", json=payload)
    print(f"   SMS Webhook: {res.status_code}")
    if res.status_code == 200:
        print(f"   Response: {res.json()}")
    else:
        print(f"   Error: {res.text[:100]}")

if __name__ == "__main__":
    test_voice_tools()
    test_text_replies()
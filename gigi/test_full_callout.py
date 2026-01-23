#!/usr/bin/env python3
"""
Test the full call-out flow:
1. Caregiver calls out
2. Post to New Scheduling chat
3. Start SMS campaign to find coverage
"""

import os
import json
import requests

print("=" * 60)
print("FULL CALL-OUT TEST")
print("=" * 60)

# Test data - simulating a caregiver calling out
test_callout = {
    "caregiver_name": "Maria Test",
    "reason": "sick - flu symptoms",
    "shift_date": "tomorrow",
    "client_name": "Charles"
}

WEBHOOK_BASE = "https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/webhook/retell/function"

# Step 1: Test report_call_out function
print("\n1. TESTING report_call_out")
print("-" * 40)

response = requests.post(
    f"{WEBHOOK_BASE}/report_call_out",
    json={
        "args": test_callout
    },
    headers={"Content-Type": "application/json"},
    timeout=30
)

print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500]}")

# Step 2: Test start_shift_filling_campaign
print("\n2. TESTING start_shift_filling_campaign")
print("-" * 40)

response2 = requests.post(
    f"{WEBHOOK_BASE}/start_shift_filling_campaign",
    json={
        "args": {
            "client_name": "Charles",
            "shift_date": "tomorrow Fri 1/24",
            "shift_time": "11 AM - 1 PM",
            "urgency": "urgent"
        }
    },
    headers={"Content-Type": "application/json"},
    timeout=30
)

print(f"Status: {response2.status_code}")
print(f"Response: {response2.text[:500]}")

# Step 3: Check RingCentral - who is the authenticated user?
print("\n3. CHECKING RINGCENTRAL AUTH IDENTITY")
print("-" * 40)

try:
    from services.ringcentral_messaging_service import ringcentral_messaging_service

    # Get the current user info
    token = ringcentral_messaging_service._get_access_token()
    if token:
        import requests as req
        user_response = req.get(
            "https://platform.ringcentral.com/restapi/v1.0/account/~/extension/~",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        if user_response.status_code == 200:
            user_data = user_response.json()
            print(f"Authenticated as: {user_data.get('name')}")
            print(f"Extension: {user_data.get('extensionNumber')}")
            print(f"Email: {user_data.get('contact', {}).get('email')}")
        else:
            print(f"Could not get user info: {user_response.status_code}")
    else:
        print("No token available")

    # Step 4: Send test message to New Scheduling
    print("\n4. SENDING TEST TO NEW SCHEDULING CHAT")
    print("-" * 40)

    result = ringcentral_messaging_service.send_message_to_chat(
        "New Scheduling",
        "🤖 GIGI TEST: Maria Test called out sick for tomorrow's 11 AM - 1 PM shift with Charles. Looking for coverage now."
    )
    print(f"Result: {json.dumps(result, indent=2)}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

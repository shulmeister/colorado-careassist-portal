#!/usr/bin/env python3
"""Debug: Check which extension can see SMS for 719-428-3999 and 303-757-1777"""

import os
import sys
import requests
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ringcentral_messaging_service import ringcentral_messaging_service, RINGCENTRAL_SERVER

token = ringcentral_messaging_service._get_access_token()
if not token:
    print("❌ Failed to get access token")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json"
}

print("="*60)
print("CHECKING SMS VISIBILITY FOR EXTENSION 111")
print("="*60)

# Check current extension info
print("\n1. Current Extension Info:")
response = requests.get(
    f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~",
    headers=headers
)
if response.status_code == 200:
    ext_data = response.json()
    print(f"   Extension ID: {ext_data.get('id')}")
    print(f"   Extension Number: {ext_data.get('extensionNumber')}")
    print(f"   Name: {ext_data.get('name')}")
    print(f"   Status: {ext_data.get('status')}")
else:
    print(f"   ❌ Failed: {response.status_code}")

# Check phone numbers assigned to this extension
print("\n2. Phone Numbers Assigned to This Extension:")
response = requests.get(
    f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/phone-number",
    headers=headers
)
if response.status_code == 200:
    numbers = response.json().get('records', [])
    for num in numbers:
        print(f"   - {num.get('phoneNumber')} ({num.get('usageType')})")
else:
    print(f"   ❌ Failed: {response.status_code}")

# Try to get ALL account phone numbers (requires admin)
print("\n3. All Account Phone Numbers (if accessible):")
response = requests.get(
    f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/phone-number",
    headers=headers
)
if response.status_code == 200:
    numbers = response.json().get('records', [])
    target_numbers = ["+17194283999", "+13037571777"]
    print(f"   Total numbers in account: {len(numbers)}")
    for num in numbers:
        phone = num.get('phoneNumber')
        if phone in target_numbers:
            print(f"   ⭐ FOUND: {phone}")
            print(f"      Extension: {num.get('extension', {}).get('extensionNumber')}")
            print(f"      Extension ID: {num.get('extension', {}).get('id')}")
            print(f"      Usage: {num.get('usageType')}")
else:
    print(f"   ❌ Failed: {response.status_code} - {response.text[:200]}")

# Check message-store directly
print("\n4. Recent SMS Messages (last 24 hours):")
date_from = (datetime.utcnow() - timedelta(hours=24)).isoformat()
response = requests.get(
    f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/message-store",
    headers=headers,
    params={
        "messageType": "SMS",
        "dateFrom": date_from,
        "perPage": 10
    }
)
if response.status_code == 200:
    messages = response.json().get('records', [])
    print(f"   Found {len(messages)} SMS messages")
    for msg in messages[:5]:
        print(f"   - ID: {msg.get('id')}")
        print(f"     From: {msg.get('from', {}).get('phoneNumber')}")
        print(f"     To: {msg.get('to', [{}])[0].get('phoneNumber')}")
        print(f"     Direction: {msg.get('direction')}")
        print(f"     Subject: {msg.get('subject', '')[:50]}")
        print()
else:
    print(f"   ❌ Failed: {response.status_code} - {response.text[:200]}")

print("\n" + "="*60)
print("DIAGNOSIS COMPLETE")
print("="*60)

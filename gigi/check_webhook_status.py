#!/usr/bin/env python3
"""Check RingCentral webhook subscription status"""

import os
import sys
import requests
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ringcentral_messaging_service import ringcentral_messaging_service, RINGCENTRAL_SERVER

token = ringcentral_messaging_service._get_access_token()
if not token:
    print("❌ Failed to get access token")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

print("="*80)
print("WEBHOOK SUBSCRIPTION STATUS")
print("="*80)

# Get all subscriptions
response = requests.get(
    f"{RINGCENTRAL_SERVER}/restapi/v1.0/subscription",
    headers=headers
)

if response.status_code == 200:
    subs = response.json().get("records", [])
    print(f"\n📋 Found {len(subs)} active subscriptions:\n")

    for sub in subs:
        print(f"ID: {sub.get('id')}")
        print(f"Status: {sub.get('status')}")
        print(f"Created: {sub.get('creationTime')}")
        print(f"Expires: {sub.get('expirationTime')}")
        print(f"Events: {sub.get('eventFilters')}")
        print(f"Webhook URL: {sub.get('deliveryMode', {}).get('address')}")
        print(f"Transport: {sub.get('deliveryMode', {}).get('transportType')}")
        print("-" * 80)
else:
    print(f"❌ Failed: {response.status_code} - {response.text}")

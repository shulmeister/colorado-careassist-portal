#!/usr/bin/env python3
"""
Register RingCentral webhook subscription for SMS events.
This will make ALL inbound SMS (including group/auto-receptionist numbers)
trigger webhooks to Gigi.
"""

import os
import sys
import requests
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ringcentral_messaging_service import ringcentral_messaging_service, RINGCENTRAL_SERVER

# Webhook endpoint URL
WEBHOOK_URL = "https://portal.coloradocareassist.com/gigi/webhook/ringcentral-sms"

print("="*80)
print("SETTING UP RINGCENTRAL SMS WEBHOOK SUBSCRIPTION")
print("="*80)

# Get access token
token = ringcentral_messaging_service._get_access_token()
if not token:
    print("❌ Failed to get access token")
    sys.exit(1)

print(f"✅ Got access token")

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Check existing subscriptions first
print("\n📋 Checking existing subscriptions...")
response = requests.get(
    f"{RINGCENTRAL_SERVER}/restapi/v1.0/subscription",
    headers=headers
)

if response.status_code == 200:
    existing = response.json().get("records", [])
    print(f"Found {len(existing)} existing subscriptions")

    # Check if webhook already exists
    for sub in existing:
        if WEBHOOK_URL in sub.get("deliveryMode", {}).get("address", ""):
            print(f"\n⚠️  Webhook already exists!")
            print(f"   Subscription ID: {sub.get('id')}")
            print(f"   Status: {sub.get('status')}")
            print(f"   Events: {sub.get('eventFilters')}")

            # Delete old subscription to recreate
            print(f"\n🔄 Deleting old subscription to recreate...")
            delete_response = requests.delete(
                f"{RINGCENTRAL_SERVER}/restapi/v1.0/subscription/{sub.get('id')}",
                headers=headers
            )
            if delete_response.status_code == 204:
                print(f"✅ Deleted old subscription")
            else:
                print(f"⚠️  Failed to delete: {delete_response.status_code}")

# Create new webhook subscription
print(f"\n📝 Creating new SMS webhook subscription...")

subscription_data = {
    "eventFilters": [
        "/restapi/v1.0/account/~/extension/~/message-store/instant?type=SMS"
    ],
    "deliveryMode": {
        "transportType": "WebHook",
        "address": WEBHOOK_URL
    },
    "expiresIn": 630720000  # 20 years in seconds (max allowed)
}

print(f"\nSubscription config:")
print(f"  Event: SMS message-store instant notifications")
print(f"  Webhook URL: {WEBHOOK_URL}")
print(f"  Expires: ~20 years")

response = requests.post(
    f"{RINGCENTRAL_SERVER}/restapi/v1.0/subscription",
    headers=headers,
    json=subscription_data
)

if response.status_code == 200:
    result = response.json()
    print(f"\n✅ SUCCESS! Webhook subscription created")
    print(f"\n📋 Subscription Details:")
    print(f"   ID: {result.get('id')}")
    print(f"   Status: {result.get('status')}")
    print(f"   Created: {result.get('creationTime')}")
    print(f"   Expires: {result.get('expirationTime')}")
    print(f"\n🎉 All inbound SMS (including 719 & 303) will now trigger webhooks!")
else:
    print(f"\n❌ Failed to create subscription: {response.status_code}")
    print(f"Response: {response.text}")
    sys.exit(1)

print("\n" + "="*80)
print("SETUP COMPLETE")
print("="*80)

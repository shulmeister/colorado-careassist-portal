#!/usr/bin/env python3
"""Setup RingCentral SMS webhook to forward to Gigi."""

import os
import requests
import json

# RingCentral credentials from Mac Mini (Local)
JWT_TOKEN = os.getenv("RINGCENTRAL_JWT_TOKEN", "[REDACTED_JWT]")
WEBHOOK_URL = "https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/gigi/webhook/ringcentral-sms"

def get_access_token():
    """Get RingCentral access token using JWT."""
    CLIENT_ID = os.getenv("RINGCENTRAL_CLIENT_ID", "VbxfL4RkN8ncFItIqSP5k7")
    CLIENT_SECRET = os.getenv("RINGCENTRAL_CLIENT_SECRET", "W3NjGB4CFnJdhGrYsQsovD3dlIzliPo3Oejdw2pB0puW")

    response = requests.post(
        "https://platform.ringcentral.com/restapi/oauth/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        auth=(CLIENT_ID, CLIENT_SECRET),
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": JWT_TOKEN
        },
        timeout=30
    )

    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"❌ Failed to get access token: {response.status_code}")
        print(response.text)
        return None

def list_existing_webhooks(access_token):
    """List existing webhook subscriptions."""
    response = requests.get(
        "https://platform.ringcentral.com/restapi/v1.0/subscription",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30
    )

    if response.status_code == 200:
        return response.json().get("records", [])
    else:
        print(f"❌ Failed to list webhooks: {response.status_code}")
        return []

def create_sms_webhook(access_token):
    """Create webhook subscription for SMS events."""
    webhook_config = {
        "eventFilters": [
            "/restapi/v1.0/account/~/extension/~/message-store/instant?type=SMS"
        ],
        "deliveryMode": {
            "transportType": "WebHook",
            "address": WEBHOOK_URL
        },
        "expiresIn": 630720000  # 20 years
    }

    response = requests.post(
        "https://platform.ringcentral.com/restapi/v1.0/subscription",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        json=webhook_config,
        timeout=30
    )

    if response.status_code in (200, 201):
        return response.json()
    else:
        print(f"❌ Failed to create webhook: {response.status_code}")
        print(response.text)
        return None

def main():
    print("=" * 80)
    print("RINGCENTRAL SMS WEBHOOK SETUP")
    print("=" * 80)
    print(f"Target URL: {WEBHOOK_URL}")
    print()

    # Step 1: Get access token
    print("1. Getting RingCentral access token...")
    access_token = get_access_token()
    if not access_token:
        return
    print("   ✅ Got access token")
    print()

    # Step 2: Check existing webhooks
    print("2. Checking existing webhooks...")
    existing = list_existing_webhooks(access_token)
    print(f"   Found {len(existing)} existing webhook(s)")

    # Check if Gigi webhook already exists
    gigi_webhook = None
    for webhook in existing:
        if webhook.get("deliveryMode", {}).get("address") == WEBHOOK_URL:
            gigi_webhook = webhook
            print(f"   ⚠️  Gigi webhook already exists: {webhook['id']}")
            print(f"       Status: {webhook.get('status')}")
            break
    print()

    # Step 3: Create webhook if it doesn't exist
    if not gigi_webhook:
        print("3. Creating SMS webhook subscription...")
        result = create_sms_webhook(access_token)
        if result:
            print("   ✅ Webhook created successfully!")
            print(f"   Subscription ID: {result['id']}")
            print(f"   Status: {result.get('status')}")
            print(f"   Event filters: {result.get('eventFilters')}")
        else:
            print("   ❌ Failed to create webhook")
    else:
        print("3. Webhook already configured - skipping creation")

    print()
    print("=" * 80)
    print("SETUP COMPLETE")
    print("=" * 80)
    print("RingCentral will now forward SMS messages to Gigi.")
    print(f"Webhook URL: {WEBHOOK_URL}")
    print()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Set up RingCentral webhook subscription for Gigi direct messages.

This subscribes to team messaging events so Gigi receives notifications
when someone sends her a direct message (like "gigi stop" or "gigi go").
"""

import os
import json
import requests

# Configuration
CLIENT_ID = os.getenv("RINGCENTRAL_CLIENT_ID")
CLIENT_SECRET = os.getenv("RINGCENTRAL_CLIENT_SECRET")
JWT_TOKEN = os.getenv("RINGCENTRAL_JWT_TOKEN")
SERVER_URL = "https://platform.ringcentral.com"

# Webhook endpoint for Gigi commands
WEBHOOK_URL = "https://careassist-unified-0a11ddb45ac0.herokuapp.com/api/gigi/ringcentral/command"

if not all([CLIENT_ID, CLIENT_SECRET, JWT_TOKEN]):
    print("ERROR: Missing RingCentral credentials")
    print(f"  CLIENT_ID: {'SET' if CLIENT_ID else 'NOT SET'}")
    print(f"  CLIENT_SECRET: {'SET' if CLIENT_SECRET else 'NOT SET'}")
    print(f"  JWT_TOKEN: {'SET' if JWT_TOKEN else 'NOT SET'}")
    exit(1)

print("=" * 60)
print("SETTING UP RINGCENTRAL WEBHOOK FOR GIGI")
print("=" * 60)

# Get access token via JWT
print("\nAuthenticating...")
auth_response = requests.post(
    f"{SERVER_URL}/restapi/oauth/token",
    data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": JWT_TOKEN,
    },
    auth=(CLIENT_ID, CLIENT_SECRET),
    timeout=30
)

if auth_response.status_code != 200:
    print(f"ERROR: Failed to authenticate: {auth_response.text}")
    exit(1)

token_data = auth_response.json()
access_token = token_data.get("access_token")
print("Authenticated successfully")

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

# Get current user info
user_response = requests.get(
    f"{SERVER_URL}/restapi/v1.0/account/~/extension/~",
    headers=headers,
    timeout=30
)
if user_response.status_code == 200:
    user_info = user_response.json()
    print(f"Logged in as: {user_info.get('name')} (ext {user_info.get('extensionNumber')})")

# List existing subscriptions
print("\nExisting subscriptions:")
subs_response = requests.get(
    f"{SERVER_URL}/restapi/v1.0/subscription",
    headers=headers,
    timeout=30
)

if subs_response.status_code == 200:
    subs = subs_response.json()
    existing_subs = subs.get("records", [])
    for sub in existing_subs:
        print(f"  - {sub.get('id')}: {sub.get('status')} - {sub.get('deliveryMode', {}).get('address', 'N/A')}")

    # Delete old webhooks to this URL if they exist
    for sub in existing_subs:
        if sub.get("deliveryMode", {}).get("address") == WEBHOOK_URL:
            print(f"  Deleting old subscription {sub.get('id')}...")
            requests.delete(
                f"{SERVER_URL}/restapi/v1.0/subscription/{sub.get('id')}",
                headers=headers,
                timeout=30
            )
else:
    print(f"  Could not list subscriptions: {subs_response.status_code}")

# Create new webhook subscription for team messaging
print("\nCreating new webhook subscription...")

# Subscribe to team messaging events
event_filters = [
    "/restapi/v1.0/glip/posts",  # Team messaging posts
]

sub_response = requests.post(
    f"{SERVER_URL}/restapi/v1.0/subscription",
    headers=headers,
    json={
        "eventFilters": event_filters,
        "deliveryMode": {
            "transportType": "WebHook",
            "address": WEBHOOK_URL,
        },
        "expiresIn": 604800,  # 7 days (max)
    },
    timeout=30
)

if sub_response.status_code in (200, 201):
    result = sub_response.json()
    print(f"\nSubscription created!")
    print(f"  ID: {result.get('id')}")
    print(f"  Status: {result.get('status')}")
    print(f"  Expires: {result.get('expirationTime')}")
    print(f"  Delivery: {result.get('deliveryMode', {}).get('address')}")
    print(f"\nEvent filters:")
    for ef in result.get("eventFilters", []):
        print(f"    - {ef}")
else:
    print(f"ERROR: Failed to create subscription: {sub_response.status_code}")
    print(sub_response.text[:500])

print("\n" + "=" * 60)
print("WEBHOOK SETUP COMPLETE")
print("=" * 60)
print(f"\nWebhook URL: {WEBHOOK_URL}")
print("\nCommands Gigi will respond to:")
print("  - 'gigi stop' - Disables all Gigi features")
print("  - 'gigi go' - Enables all Gigi features")
print("  - 'gigi status' - Reports current status")

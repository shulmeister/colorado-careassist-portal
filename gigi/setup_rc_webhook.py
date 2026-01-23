#!/usr/bin/env python3
"""
Set up RingCentral webhook subscription for Gigi direct messages.

This subscribes to team messaging events so Gigi receives notifications
when someone sends her a direct message (like "gigi stop" or "gigi go").
"""

import os
import json
from ringcentral import SDK

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

# Initialize SDK
sdk = SDK(CLIENT_ID, CLIENT_SECRET, SERVER_URL)
platform = sdk.platform()

try:
    platform.login(jwt=JWT_TOKEN)
    print("Authenticated successfully")
except Exception as e:
    print(f"ERROR: Failed to authenticate: {e}")
    exit(1)

# Get current user info
try:
    user_info = platform.get("/restapi/v1.0/account/~/extension/~").json()
    print(f"Logged in as: {user_info.get('name')} (ext {user_info.get('extensionNumber')})")
except Exception as e:
    print(f"WARNING: Could not get user info: {e}")

# List existing subscriptions
print("\nExisting subscriptions:")
try:
    subs = platform.get("/restapi/v1.0/subscription").json()
    existing_subs = subs.get("records", [])
    for sub in existing_subs:
        print(f"  - {sub.get('id')}: {sub.get('status')} - {sub.get('deliveryMode', {}).get('address', 'N/A')}")

    # Delete old webhooks to this URL if they exist
    for sub in existing_subs:
        if sub.get("deliveryMode", {}).get("address") == WEBHOOK_URL:
            print(f"  Deleting old subscription {sub.get('id')}...")
            platform.delete(f"/restapi/v1.0/subscription/{sub.get('id')}")
except Exception as e:
    print(f"  Could not list subscriptions: {e}")

# Create new webhook subscription for team messaging
print("\nCreating new webhook subscription...")

# Subscribe to team messaging events
# /restapi/v1.0/glip/posts - all posts in chats user is member of
# /restapi/v1.0/account/~/extension/~/message-store/instant - instant messages

event_filters = [
    "/restapi/v1.0/glip/posts",  # Team messaging posts
    "/restapi/v1.0/account/~/extension/~/message-store/instant",  # Direct messages
]

try:
    response = platform.post("/restapi/v1.0/subscription", {
        "eventFilters": event_filters,
        "deliveryMode": {
            "transportType": "WebHook",
            "address": WEBHOOK_URL,
        },
        "expiresIn": 604800,  # 7 days (max)
    })

    result = response.json()
    print(f"\nSubscription created!")
    print(f"  ID: {result.get('id')}")
    print(f"  Status: {result.get('status')}")
    print(f"  Expires: {result.get('expirationTime')}")
    print(f"  Delivery: {result.get('deliveryMode', {}).get('address')}")
    print(f"\nEvent filters:")
    for ef in result.get("eventFilters", []):
        print(f"    - {ef}")

except Exception as e:
    print(f"ERROR: Failed to create subscription: {e}")

    # Try with just one event filter
    print("\nTrying with simpler event filter...")
    try:
        response = platform.post("/restapi/v1.0/subscription", {
            "eventFilters": ["/restapi/v1.0/glip/posts"],
            "deliveryMode": {
                "transportType": "WebHook",
                "address": WEBHOOK_URL,
            },
            "expiresIn": 604800,
        })
        result = response.json()
        print(f"Subscription created with ID: {result.get('id')}")
    except Exception as e2:
        print(f"ERROR: Still failed: {e2}")

print("\n" + "=" * 60)
print("WEBHOOK SETUP COMPLETE")
print("=" * 60)
print(f"\nWebhook URL: {WEBHOOK_URL}")
print("\nCommands Gigi will respond to:")
print("  - 'gigi stop' - Disables all Gigi features")
print("  - 'gigi go' - Enables all Gigi features")
print("  - 'gigi status' - Reports current status")

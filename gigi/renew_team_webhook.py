#!/usr/bin/env python3
"""
Auto-renew RingCentral Team Messaging webhook.

RingCentral limits Team Messaging webhooks to 7 days max.
Run this script every 6 days via Mac Mini (Local) Scheduler to prevent expiration.

Schedule: Daily at 3am (checks if renewal needed)
"""
import os
import requests
from datetime import datetime, timedelta

CLIENT_ID = os.getenv("RINGCENTRAL_CLIENT_ID")
CLIENT_SECRET = os.getenv("RINGCENTRAL_CLIENT_SECRET")
JWT_TOKEN = os.getenv("RINGCENTRAL_JWT_TOKEN")
WEBHOOK_URL = "https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/api/gigi/ringcentral/command"

def get_token():
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
    return response.json()["access_token"]

def renew_webhook():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Get existing subscriptions
    response = requests.get(
        "https://platform.ringcentral.com/restapi/v1.0/subscription",
        headers=headers,
        timeout=30
    )

    subs = response.json().get("records", [])
    team_webhook = None

    for sub in subs:
        if sub.get("deliveryMode", {}).get("address") == WEBHOOK_URL:
            team_webhook = sub
            break

    if not team_webhook:
        print("⚠️  No Team Messaging webhook found - creating new one")
        create_new = True
    else:
        # Check if expires within 2 days
        expires = datetime.fromisoformat(team_webhook["expirationTime"].replace("Z", "+00:00"))
        days_left = (expires - datetime.now(expires.tzinfo)).days

        if days_left <= 2:
            print(f"⚠️  Webhook expires in {days_left} days - renewing")
            # Delete old
            requests.delete(
                f"https://platform.ringcentral.com/restapi/v1.0/subscription/{team_webhook['id']}",
                headers=headers,
                timeout=30
            )
            create_new = True
        else:
            print(f"✅ Webhook healthy - {days_left} days until expiration")
            create_new = False

    if create_new:
        # Create new webhook
        response = requests.post(
            "https://platform.ringcentral.com/restapi/v1.0/subscription",
            headers=headers,
            json={
                "eventFilters": ["/restapi/v1.0/glip/posts"],
                "deliveryMode": {
                    "transportType": "WebHook",
                    "address": WEBHOOK_URL,
                },
                "expiresIn": 604800,  # 7 days (max for Team Messaging)
            },
            timeout=30
        )

        if response.status_code in (200, 201):
            result = response.json()
            print(f"✅ Webhook renewed!")
            print(f"   ID: {result['id']}")
            print(f"   Expires: {result['expirationTime']}")
        else:
            print(f"❌ Failed to renew: {response.status_code}")
            print(response.text[:500])
            raise Exception("Webhook renewal failed")

if __name__ == "__main__":
    print("=" * 60)
    print("RINGCENTRAL TEAM MESSAGING WEBHOOK RENEWAL")
    print("=" * 60)
    renew_webhook()
    print("=" * 60)

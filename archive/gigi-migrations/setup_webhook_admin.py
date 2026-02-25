#!/usr/bin/env python3
"""Setup account-wide webhook using admin JWT token from env vars"""

import os
import requests
import json

CLIENT_ID = os.getenv("RINGCENTRAL_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("RINGCENTRAL_CLIENT_SECRET", "")
JWT_TOKEN = os.getenv("RINGCENTRAL_JWT_TOKEN", "")
SERVER = "https://platform.ringcentral.com"
WEBHOOK_URL = "https://portal.coloradocareassist.com/gigi/webhook/ringcentral-sms"

print("="*80)
print("SETTING UP ADMIN-LEVEL WEBHOOK FOR ALL SMS")
print("="*80)

# Get access token using JWT
print("\n1. Getting access token...")
auth_response = requests.post(
    f"{SERVER}/restapi/oauth/token",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": JWT_TOKEN
    },
    auth=(CLIENT_ID, CLIENT_SECRET)
)

if auth_response.status_code != 200:
    print(f"❌ Auth failed: {auth_response.status_code}")
    print(auth_response.text)
    exit(1)

token = auth_response.json().get("access_token")
print("✅ Got access token")

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Check current extension
print("\n2. Checking extension info...")
ext_response = requests.get(f"{SERVER}/restapi/v1.0/account/~/extension/~", headers=headers)
if ext_response.status_code == 200:
    ext = ext_response.json()
    print(f"   Extension: {ext.get('extensionNumber')} ({ext.get('name')})")
    print(f"   ID: {ext.get('id')}")
    print(f"   Type: {ext.get('type')}")

# Delete existing webhooks for this URL
print("\n3. Checking existing webhooks...")
subs_response = requests.get(f"{SERVER}/restapi/v1.0/subscription", headers=headers)
if subs_response.status_code == 200:
    subs = subs_response.json().get("records", [])
    for sub in subs:
        if WEBHOOK_URL in sub.get("deliveryMode", {}).get("address", ""):
            print(f"   Deleting old webhook: {sub.get('id')}")
            requests.delete(f"{SERVER}/restapi/v1.0/subscription/{sub.get('id')}", headers=headers)

# Find all phone numbers and their extensions
print("\n4. Finding all phone numbers and extensions...")
phone_response = requests.get(f"{SERVER}/restapi/v1.0/account/~/phone-number", headers=headers, params={"perPage": 1000})
TARGET_NUMBERS = ["+17194283999", "+13037571777", "+13074598220"]
extension_ids = set()

if phone_response.status_code == 200:
    phone_numbers = phone_response.json().get('records', [])
    for phone in phone_numbers:
        if phone.get('phoneNumber') in TARGET_NUMBERS:
            ext_id = phone.get('extension', {}).get('id')
            if ext_id:
                extension_ids.add(ext_id)
                print(f"   {phone.get('phoneNumber')} → Extension {ext_id}")

if not extension_ids:
    print("   ⚠️  No extension IDs found for target numbers. Using current extension.")
    extension_ids.add('262740009')  # Jason's extension as fallback

# Create webhooks for each extension
print(f"\n5. Creating SMS webhooks for {len(extension_ids)} extensions...")
subscription_data = {
    "eventFilters": [
        f"/restapi/v1.0/account/~/extension/{ext_id}/message-store/instant?type=SMS"
        for ext_id in extension_ids
    ],
    "deliveryMode": {
        "transportType": "WebHook",
        "address": WEBHOOK_URL
    },
    "expiresIn": 630720000  # 20 years
}

print(f"   Event filters: {len(subscription_data['eventFilters'])} extensions")

create_response = requests.post(
    f"{SERVER}/restapi/v1.0/subscription",
    headers=headers,
    json=subscription_data
)

if create_response.status_code == 200:
    result = create_response.json()
    print("\n✅ SUCCESS! Account-wide webhook created")
    print(f"\n   Subscription ID: {result.get('id')}")
    print(f"   Status: {result.get('status')}")
    print(f"   Events: {result.get('eventFilters')}")
    print(f"   URL: {result.get('deliveryMode', {}).get('address')}")
    print(f"\n🎉 ALL SMS (including 719 & 303) will now trigger Gigi!")
else:
    print(f"\n❌ Failed: {create_response.status_code}")
    print(create_response.text)

print("\n" + "="*80)

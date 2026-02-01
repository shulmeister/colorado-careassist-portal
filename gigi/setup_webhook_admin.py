#!/usr/bin/env python3
"""Setup account-wide webhook using admin JWT token from desktop credentials"""

import requests
import json

# Admin credentials from desktop file
CLIENT_ID = "8HQNG4wPwl3cejTAdz1ZBX"
CLIENT_SECRET = "5xwSbWIOKZvc0ADlafSZdWZ0SpwfRSgZ1cVA5AmUr5mW"
JWT_TOKEN = "eyJraWQiOiI4NzYyZjU5OGQwNTk0NGRiODZiZjVjYTk3ODA0NzYwOCIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0.eyJhdWQiOiJodHRwczovL3BsYXRmb3JtLnJpbmdjZW50cmFsLmNvbS9yZXN0YXBpL29hdXRoL3Rva2VuIiwic3ViIjoiMjYyNzQwMDA5IiwiaXNzIjoiaHR0cHM6Ly9wbGF0Zm9ybS5yaW5nY2VudHJhbC5jb20iLCJleHAiOjM5MTAyNDA5NjUsImlhdCI6MTc2Mjc1NzMxOCwianRpIjoiZ3Jsd0pPWGFTM2EwalpibThvTmtZdyJ9.WA9DUSlb_4SlCo9UHNjscHKrVDoJTF4iW3D7Rre9E2qg5UQ_hWfCgysiZJMXlL8-vUuJ2XDNivvpfbxriESKIEPAEEY85MolJZS9KG3g90ga-3pJtHq7SC87mcacXtDWqzmbBS_iDOjmNMHiynWFR9Wgi30DMbz9rQ1U__Bl88qVRTvZfY17ovu3dZDhh-FmLUWRnKOc4LQUvRChQCO-21LdSquZPvEAe7qHEsh-blS8Cvh98wvX-9vaiurDR-kC9Tp007x4lTI74MwQ5rJif7tL7Hslqaoag0WoNEIP9VPrp4x-Q7AzKIzBNbrGr9kIPthIebmeOBDMIIrw6pg_lg"
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

# Create account-wide webhook with wildcard
print("\n4. Creating account-wide SMS webhook...")
subscription_data = {
    "eventFilters": [
        # Wildcard for ALL extensions including group numbers
        "/restapi/v1.0/account/~/extension/+/message-store/instant?type=SMS"
    ],
    "deliveryMode": {
        "transportType": "WebHook",
        "address": WEBHOOK_URL
    },
    "expiresIn": 630720000  # 20 years
}

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

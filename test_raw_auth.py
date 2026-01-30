#!/usr/bin/env python3
"""Test raw OAuth and API calls"""

import requests
import json

CLIENT_ID = "bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS"
CLIENT_SECRET = "Do06wgoZuV7ni4zO"
AGENCY_ID = "4505"

print("=" * 80)
print("RAW WELLSKY API TEST")
print("=" * 80)

# Step 1: Get OAuth token
print("\n1. Getting OAuth token...")
oauth_url = "https://connect.clearcareonline.com/oauth/accesstoken"
oauth_data = {
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET
}

print(f"POST {oauth_url}")
print(f"Body: {json.dumps(oauth_data, indent=2)}")

resp = requests.post(oauth_url, json=oauth_data, timeout=30)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:200]}")

if resp.status_code != 200:
    print("❌ OAuth failed!")
    exit(1)

token_data = resp.json()
access_token = token_data["access_token"]
print(f"✅ Got token: {access_token[:20]}...")

# Step 2: Call Practitioner API
print("\n2. Calling Practitioner API...")
api_url = "https://connect.clearcareonline.com/v1/Practitioner"
headers = {
    "Authorization": f"BearerToken {access_token}",
    "Content-Type": "application/json"
}
params = {
    "agencyId": AGENCY_ID,
    "_count": 5
}

print(f"GET {api_url}")
print(f"Headers: Authorization: BearerToken {access_token[:20]}...")
print(f"Params: {params}")

resp = requests.get(api_url, headers=headers, params=params, timeout=30)
print(f"Status: {resp.status_code}")

if resp.status_code == 200:
    data = resp.json()
    total = data.get("total", 0)
    entries = data.get("entry", [])
    print(f"✅ SUCCESS! Found {total} practitioners")
    for entry in entries[:3]:
        resource = entry.get("resource", {})
        name = resource.get("name", [{}])[0]
        print(f"  - {name.get('given', [''])[0]} {name.get('family', '')}")
else:
    print(f"❌ API call failed!")
    print(f"Response: {resp.text}")

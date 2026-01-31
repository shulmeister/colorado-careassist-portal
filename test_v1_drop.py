import os
import requests
import json

client_id = "[REDACTED_CLIENT_ID]"
client_secret = "[REDACTED_CLIENT_SECRET]"
agency_id = "4505"

def get_token():
    url = "https://connect.clearcareonline.com/oauth/accesstoken"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    response = requests.post(url, json=payload)
    return response.json().get("access_token")

token = get_token()
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Test with and without v1
endpoints = [
    f"https://connect.clearcareonline.com/v1/practitioners/?agencyId={agency_id}&_count=1",
    f"https://connect.clearcareonline.com/practitioners/?agencyId={agency_id}&_count=1",
]

for url in endpoints:
    print(f"\nTesting: {url}")
    try:
        response = requests.get(url, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text[:200]}...")
    except Exception as e:
        print(f"Error: {e}")

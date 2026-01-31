import os
import requests
import json
from datetime import datetime, timedelta

client_id = os.environ.get("WELLSKY_CLIENT_ID")
client_secret = os.environ.get("WELLSKY_CLIENT_SECRET")
agency_id = os.environ.get("WELLSKY_AGENCY_ID", "4505")

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

# The endpoint MUST be singular 'appointment' for shifts
url = f"https://connect.clearcareonline.com/v1/appointment/_search/?agencyId={agency_id}"

# Use a recent date range
start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
payload = {
    "caregiverId": "1939895",  # Bonnie Hart
    "startDate": start_date,
    "additionalDays": "6"
}

print(f"Testing Shift Search: {url}")
print(f"Payload: {payload}")
response = requests.post(url, headers=headers, json=payload)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    count = len(data.get("entry", []))
    print(f"SUCCESS! Found {count} shifts for Bonnie Hart in the last week.")
else:
    print(f"FAILED: {response.text}")

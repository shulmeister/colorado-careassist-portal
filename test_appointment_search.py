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

url = "https://connect.clearcareonline.com/v1/appointment/_search/?agencyId=4505"
payload = {
    "caregiverId": "1939895",  # Bonnie Hart from previous test
    "startDate": "20260101",
    "additionalDays": "6"
}

print(f"Testing: {url}")
response = requests.post(url, headers=headers, json=payload)
print(f"Status: {response.status_code}")
print(f"Body: {response.text}")

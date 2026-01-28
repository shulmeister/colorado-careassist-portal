import os
import requests
import json

RETELL_API_KEY = os.getenv("RETELL_API_KEY")

if not RETELL_API_KEY:
    print("Error: RETELL_API_KEY not found.")
    exit(1)

# Guessing the endpoint
url = "https://api.retellai.com/list-test-cases"
headers = {
    "Authorization": f"Bearer {RETELL_API_KEY}",
    "Content-Type": "application/json"
}

try:
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        print("Test Cases:")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error fetching test cases: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Exception: {e}")

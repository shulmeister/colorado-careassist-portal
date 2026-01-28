import os
import requests
import json

RETELL_API_KEY = os.getenv("RETELL_API_KEY")

if not RETELL_API_KEY:
    print("Error: RETELL_API_KEY not found.")
    exit(1)

CONVERSATION_FLOW_ID = "conversation_flow_7226ef696925"
url = f"https://api.retellai.com/list-batch-tests?type=conversation-flow&conversation_flow_id={CONVERSATION_FLOW_ID}"
headers = {
    "Authorization": f"Bearer {RETELL_API_KEY}",
    "Content-Type": "application/json"
}

try:
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        print("Batch Call Tests:")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error fetching batch tests: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Exception: {e}")

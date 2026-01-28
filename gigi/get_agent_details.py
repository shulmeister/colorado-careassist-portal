import os
import requests
import json

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
AGENT_ID = "agent_d5c3f32bdf48fa4f7f24af7d36" # From conversation_flow.py

if not RETELL_API_KEY:
    print("Error: RETELL_API_KEY not found.")
    exit(1)

url = f"https://api.retellai.com/get-agent/{AGENT_ID}"
headers = {
    "Authorization": f"Bearer {RETELL_API_KEY}",
    "Content-Type": "application/json"
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    data = response.json()
    print("Agent Details:")
    print(json.dumps(data, indent=2))
    
    if 'response_engine' in data and 'conversation_flow_id' in data['response_engine']:
        print(f"\nActive Conversation Flow ID: {data['response_engine']['conversation_flow_id']}")
else:
    print(f"Error fetching agent: {response.status_code}")
    print(response.text)

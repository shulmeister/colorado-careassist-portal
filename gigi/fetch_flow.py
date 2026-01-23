#!/usr/bin/env python3
"""Fetch and display the current conversation flow structure."""

import os
import json
import requests

RETELL_API_KEY = os.getenv('RETELL_API_KEY')
CONVERSATION_FLOW_ID = 'conversation_flow_7226ef696925'

response = requests.get(
    f'https://api.retellai.com/get-conversation-flow/{CONVERSATION_FLOW_ID}',
    headers={'Authorization': f'Bearer {RETELL_API_KEY}'},
    timeout=30
)

if response.status_code == 200:
    data = response.json()
    print(json.dumps(data, indent=2))
else:
    print(f'Error: {response.status_code}')
    print(response.text)

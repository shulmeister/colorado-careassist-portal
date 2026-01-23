#!/usr/bin/env python3
"""Check if tools are saved in the Retell conversation flow."""

import os
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
    nodes = data.get('nodes', [])
    print('=' * 60)
    print('CHECKING TOOLS IN CONVERSATION FLOW')
    print('=' * 60)
    for node in nodes:
        node_id = node.get('id')
        tools = node.get('tools', [])
        if tools:
            print(f'\n{node_id}: {len(tools)} tool(s)')
            for t in tools:
                func = t.get('function', {})
                print(f'  - {func.get("name")}')
                print(f'    URL: {func.get("url", "NO URL")}')
        else:
            print(f'\n{node_id}: NO TOOLS')
else:
    print(f'Error: {response.status_code}')
    print(response.text[:500])

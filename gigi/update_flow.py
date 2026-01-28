#!/usr/bin/env python3
"""Update the existing Gigi conversation flow in Retell AI."""

import os
import requests
from conversation_flow import get_conversation_flow_config

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
CONVERSATION_FLOW_ID = "conversation_flow_7226ef696925"

if not RETELL_API_KEY:
    print("ERROR: RETELL_API_KEY not set")
    exit(1)

config = get_conversation_flow_config()

print("=" * 60)
print("UPDATING GIGI CONVERSATION FLOW")
print("=" * 60)
print(f"Flow ID: {CONVERSATION_FLOW_ID}")
print(f"Nodes: {len(config['nodes'])}")

for node in config['nodes']:
    tools = node.get('tools', [])
    print(f"  - {node['id']}: {len(tools)} tool(s)")

response = requests.patch(
    f"https://api.retellai.com/update-conversation-flow/{CONVERSATION_FLOW_ID}",
    headers={
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "name": config["name"],
        "global_prompt": config["general_prompt"],  # API uses global_prompt
        "tools": config.get("tools", []),
        "nodes": config["nodes"],
        "start_node_id": config["start_node_id"],
        "start_speaker": config["start_speaker"]
    },
    timeout=30
)

print(f"\nResponse status: {response.status_code}")
if response.status_code == 200:
    print("SUCCESS - Flow updated!")
    print("\nRemember to click 'Publish' in Retell dashboard.")
else:
    print(f"ERROR: {response.text[:500]}")

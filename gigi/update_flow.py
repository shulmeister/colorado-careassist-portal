#!/usr/bin/env python3
"""Update the existing conversation flow in Retell."""

import os
import sys
import json
import requests

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
if not RETELL_API_KEY:
    print("ERROR: RETELL_API_KEY environment variable is required")
    sys.exit(1)
RETELL_API_BASE = "https://api.retellai.com"
CONVERSATION_FLOW_ID = "conversation_flow_7226ef696925"  # Active flow used by agent

sys.path.insert(0, os.path.dirname(__file__))
from conversation_flow import get_conversation_flow_config


def main():
    print("=" * 60)
    print("UPDATING GIGI CONVERSATION FLOW")
    print("=" * 60)

    config = get_conversation_flow_config()

    print(f"\nNodes defined: {len(config['nodes'])}")
    for node in config['nodes']:
        tools = node.get('tools', [])
        edges = node.get('edges', [])
        print(f"  - {node['id']}: {len(tools)} tools, {len(edges)} edges")

    print("\n" + "-" * 60)
    print(f"Updating conversation flow {CONVERSATION_FLOW_ID}...")

    response = requests.patch(
        f"{RETELL_API_BASE}/update-conversation-flow/{CONVERSATION_FLOW_ID}",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "name": config["name"],
            "model_choice": config["model_choice"],
            "general_prompt": config["general_prompt"],
            "nodes": config["nodes"],
            "start_node_id": config["start_node_id"],
            "start_speaker": config["start_speaker"]
        },
        timeout=60
    )

    print(f"Response status: {response.status_code}")

    if response.status_code == 200:
        print("SUCCESS! Conversation flow updated.")
        print("\nChanges made:")
        print("  - unknown_handler: Removed tools (no more looping)")
        print("  - family_handler: New node for family members")
        print("  - Clearer routing from start_greeting")
        print("\nRe-run your simulation tests in the Retell dashboard.")
    else:
        print(f"ERROR: {response.text[:1000]}")
        return False

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
Deploy Gigi Conversation Flow to Retell AI.
Non-interactive version for automated deployment.
"""

import os
import sys
import json
import requests

# Set API key (required - no hardcoded fallback for security)
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
if not RETELL_API_KEY:
    print("ERROR: RETELL_API_KEY environment variable is required")
    sys.exit(1)
RETELL_API_BASE = "https://api.retellai.com"
WEBHOOK_BASE = "https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/gigi/webhook/retell/function"
CURRENT_AGENT_ID = "agent_d5c3f32bdf48fa4f7f24af7d36"  # Gigi v2 - Conversation Flow

# Import the config
sys.path.insert(0, os.path.dirname(__file__))
from conversation_flow import get_conversation_flow_config


def main():
    print("=" * 60)
    print("DEPLOYING GIGI CONVERSATION FLOW")
    print("=" * 60)

    config = get_conversation_flow_config()

    print(f"\nNodes defined: {len(config['nodes'])}")
    for node in config['nodes']:
        tools = node.get('tools', [])
        edges = node.get('edges', [])
        print(f"  - {node['id']}: {node.get('name', '')} ({len(tools)} tools, {len(edges)} edges)")

    # Create the conversation flow
    print("\n" + "-" * 60)
    print("Creating conversation flow...")

    flow_payload = {
        "name": config["name"],
        "model_choice": config["model_choice"],
        "general_prompt": config["general_prompt"],
        "nodes": config["nodes"],
        "start_node_id": config["start_node_id"],
        "start_speaker": config["start_speaker"]
    }

    print(f"Payload size: {len(json.dumps(flow_payload))} bytes")

    flow_response = requests.post(
        f"{RETELL_API_BASE}/create-conversation-flow",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        },
        json=flow_payload,
        timeout=60
    )

    print(f"Response status: {flow_response.status_code}")

    if flow_response.status_code not in (200, 201):
        print(f"ERROR creating conversation flow:")
        print(flow_response.text[:2000])
        return False

    flow_data = flow_response.json()
    conversation_flow_id = flow_data.get("conversation_flow_id")
    print(f"SUCCESS! Created conversation flow: {conversation_flow_id}")

    # Update the agent
    print("\n" + "-" * 60)
    print(f"Updating agent {CURRENT_AGENT_ID}...")

    agent_response = requests.patch(
        f"{RETELL_API_BASE}/update-agent/{CURRENT_AGENT_ID}",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "response_engine": {
                "type": "conversation-flow",
                "conversation_flow_id": conversation_flow_id
            },
            "webhook_url": "https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/gigi/webhook/retell",
            "begin_message": "Hi, this is Gigi with Colorado Care Assist. How can I help you tonight?"
        },
        timeout=30
    )

    print(f"Response status: {agent_response.status_code}")

    if agent_response.status_code != 200:
        print(f"ERROR updating agent:")
        print(agent_response.text[:2000])
        return False

    print("SUCCESS! Agent updated.")

    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print(f"Conversation Flow ID: {conversation_flow_id}")
    print(f"Agent ID: {CURRENT_AGENT_ID}")
    print("\nTest Gigi in the Retell dashboard using the simulation feature.")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

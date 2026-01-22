#!/usr/bin/env python3
"""
Sync Gigi's configuration to Retell AI

This script pushes the local system_prompt.txt and retell_tools_schema.json
to the Retell AI agent configuration via their API.

Usage:
    python gigi/sync_retell.py

Requires:
    RETELL_API_KEY environment variable
"""

import os
import json
import requests
import sys

# Retell API configuration
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = "agent_363f3725498b851037ea84bda5"
RETELL_LLM_ID = "llm_0c8e72ac4ef9447b4ed514a720c1"
RETELL_API_BASE = "https://api.retellai.com"

# File paths (relative to script location)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SYSTEM_PROMPT_FILE = os.path.join(SCRIPT_DIR, "system_prompt.txt")
TOOLS_SCHEMA_FILE = os.path.join(SCRIPT_DIR, "retell_tools_schema.json")


def load_system_prompt():
    """Load system prompt from file."""
    with open(SYSTEM_PROMPT_FILE, "r") as f:
        return f.read().strip()


def load_tools_schema():
    """Load tools schema from JSON file and convert to Retell format."""
    with open(TOOLS_SCHEMA_FILE, "r") as f:
        data = json.load(f)
        openai_tools = data.get("tools", [])

    # Convert from OpenAI format to Retell format
    WEBHOOK_BASE = "https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/webhook/retell/function"
    retell_tools = []

    for tool in openai_tools:
        func = tool.get("function", {})
        retell_tool = {
            "name": func.get("name"),
            "description": func.get("description"),
            "type": "custom",
            "parameters": func.get("parameters", {}),
            "url": f"{WEBHOOK_BASE}/{func.get('name')}",
            "speak_during_execution": True,
            "speak_after_execution": True,
            "execution_message_description": "One moment while I look that up.",
        }
        retell_tools.append(retell_tool)

    return retell_tools


def get_current_agent():
    """Get current agent configuration from Retell."""
    response = requests.get(
        f"{RETELL_API_BASE}/get-agent/{RETELL_AGENT_ID}",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        }
    )
    response.raise_for_status()
    return response.json()


def get_current_llm():
    """Get current LLM configuration from Retell."""
    response = requests.get(
        f"{RETELL_API_BASE}/get-retell-llm/{RETELL_LLM_ID}",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        }
    )
    response.raise_for_status()
    return response.json()


def get_time_of_day_greeting():
    """Get the appropriate time-of-day greeting."""
    from datetime import datetime
    import pytz

    mountain = pytz.timezone('America/Denver')
    now = datetime.now(mountain)
    hour = now.hour

    if 3 <= hour < 12:
        return "this morning"
    elif 12 <= hour < 17:
        return "this afternoon"
    else:
        return "tonight"


def update_llm(system_prompt: str, tools: list):
    """Update the LLM configuration with prompt and tools."""
    time_greeting = get_time_of_day_greeting()
    payload = {
        "general_prompt": system_prompt,
        "general_tools": tools,
        "begin_message": f"Hello, this is Gigi with Colorado Care Assist. How can I help you {time_greeting}?",
    }

    response = requests.patch(
        f"{RETELL_API_BASE}/update-retell-llm/{RETELL_LLM_ID}",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload
    )
    response.raise_for_status()
    return response.json()


def update_agent_webhook():
    """Update the agent's webhook URL."""
    payload = {
        "webhook_url": "https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/webhook/retell",
    }

    response = requests.patch(
        f"{RETELL_API_BASE}/update-agent/{RETELL_AGENT_ID}",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload
    )
    response.raise_for_status()
    return response.json()


def main():
    if not RETELL_API_KEY:
        print("ERROR: RETELL_API_KEY environment variable not set")
        print("Set it with: export RETELL_API_KEY=your_key_here")
        sys.exit(1)

    print("=" * 60)
    print("GIGI RETELL SYNC")
    print("=" * 60)

    # Load local configuration
    print("\n[1/5] Loading local configuration...")
    system_prompt = load_system_prompt()
    tools = load_tools_schema()
    print(f"  - System prompt: {len(system_prompt)} chars")
    print(f"  - Tools: {len(tools)} functions")
    for tool in tools:
        print(f"    • {tool['name']}")

    # Get current agent
    print("\n[2/5] Fetching current Retell agent...")
    try:
        agent = get_current_agent()
        print(f"  - Agent: {agent.get('agent_name', 'Unknown')}")
        print(f"  - Agent ID: {RETELL_AGENT_ID}")
        print(f"  - LLM ID: {RETELL_LLM_ID}")
    except requests.exceptions.HTTPError as e:
        print(f"  ERROR: {e}")
        print(f"  Response: {e.response.text if e.response else 'No response'}")
        sys.exit(1)

    # Get current LLM to show what we're updating
    print("\n[3/5] Fetching current LLM configuration...")
    try:
        llm = get_current_llm()
        current_tools = llm.get("general_tools", [])
        print(f"  - Current tools: {len(current_tools)}")
        for tool in current_tools:
            print(f"    • {tool.get('name', 'unknown')}")
    except requests.exceptions.HTTPError as e:
        print(f"  WARNING: Could not fetch LLM: {e}")

    # Update LLM with new prompt and tools
    print("\n[4/5] Updating LLM configuration...")
    try:
        result = update_llm(system_prompt, tools)
        print(f"  - LLM updated successfully!")
        print(f"  - New prompt length: {len(system_prompt)} chars")
        print(f"  - New tools count: {len(tools)}")
    except requests.exceptions.HTTPError as e:
        print(f"  ERROR: {e}")
        print(f"  Response: {e.response.text if e.response else 'No response'}")
        sys.exit(1)

    # Update webhook URL
    print("\n[5/5] Updating agent webhook...")
    try:
        result = update_agent_webhook()
        print(f"  - Webhook updated")
    except requests.exceptions.HTTPError as e:
        print(f"  WARNING: Could not update webhook: {e}")

    print("\n" + "=" * 60)
    print("SUCCESS! Gigi's Retell agent has been updated.")
    print("=" * 60)
    print("\nNew capabilities synced:")
    print("  ✓ Active shift filling (finds replacement caregivers)")
    print("  ✓ Automated SMS outreach to available caregivers")
    print("  ✓ Updated system prompt (CAN change schedules now!)")
    print("  ✓ New tools: find_replacement_caregivers, start_shift_filling_campaign, etc.")
    print("\nTest by calling the Gigi line and saying you need to call out sick.")


if __name__ == "__main__":
    main()

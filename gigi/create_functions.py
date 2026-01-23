#!/usr/bin/env python3
"""Create custom functions in Retell AI that can be used in conversation flows."""

import os
import requests

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
WEBHOOK_BASE = "https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/webhook/retell/function"

headers = {
    "Authorization": f"Bearer {RETELL_API_KEY}",
    "Content-Type": "application/json"
}

functions = [
    {
        "name": "log_call_out",
        "description": "Log a caregiver call-out and notify the care team",
        "url": f"{WEBHOOK_BASE}/log_call_out",
        "speak_during_execution": "Let me log that for you.",
        "parameters": {
            "type": "object",
            "properties": {
                "caregiver_name": {"type": "string", "description": "Name of the caregiver"},
                "reason": {"type": "string", "description": "Reason for calling out"},
                "client_name": {"type": "string", "description": "Client they were scheduled with"}
            },
            "required": ["caregiver_name", "reason"]
        }
    },
    {
        "name": "start_shift_filling",
        "description": "Text available caregivers to find coverage for an open shift",
        "url": f"{WEBHOOK_BASE}/start_shift_filling",
        "speak_during_execution": "I'm texting available caregivers now to find coverage.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_name": {"type": "string", "description": "Client who needs coverage"},
                "shift_date": {"type": "string", "description": "Date of the shift"},
                "urgency": {"type": "string", "description": "urgent or normal"}
            },
            "required": ["client_name"]
        }
    },
    {
        "name": "send_team_message",
        "description": "Send a message to the care team on RingCentral",
        "url": f"{WEBHOOK_BASE}/send_team_message",
        "speak_during_execution": "I'm sending that message to the team now.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The message to send"},
                "caller_name": {"type": "string", "description": "Name of the caller"},
                "callback_number": {"type": "string", "description": "Callback phone number"},
                "recipient": {"type": "string", "description": "scheduler, cynthia, jason, or all"}
            },
            "required": ["message", "caller_name"]
        }
    },
    {
        "name": "log_issue",
        "description": "Log a client complaint and escalate to Cynthia",
        "url": f"{WEBHOOK_BASE}/log_issue",
        "speak_during_execution": "I'm logging this and notifying our Care Manager Cynthia.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_name": {"type": "string", "description": "Name of the client"},
                "issue": {"type": "string", "description": "Description of the issue"},
                "severity": {"type": "string", "description": "low, medium, high, urgent"}
            },
            "required": ["client_name", "issue"]
        }
    },
    {
        "name": "get_schedule",
        "description": "Look up a client's schedule from WellSky",
        "url": f"{WEBHOOK_BASE}/get_schedule",
        "speak_during_execution": "Let me look that up for you.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_name": {"type": "string", "description": "Name of the client"}
            },
            "required": ["client_name"]
        }
    },
    {
        "name": "cancel_visit",
        "description": "Cancel a client visit and notify the caregiver",
        "url": f"{WEBHOOK_BASE}/cancel_visit",
        "speak_during_execution": "Let me cancel that visit and notify your caregiver.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_name": {"type": "string", "description": "Name of the client"},
                "visit_date": {"type": "string", "description": "Date of the visit to cancel"}
            },
            "required": ["client_name"]
        }
    }
]

print("=" * 60)
print("CREATING CUSTOM FUNCTIONS IN RETELL")
print("=" * 60)

# Try to list existing tools first
list_response = requests.get(
    "https://api.retellai.com/list-tools",
    headers=headers,
    timeout=30
)

existing_tools = {}
if list_response.status_code == 200:
    for tool in list_response.json():
        existing_tools[tool.get("name")] = tool.get("tool_id")
    print(f"Found {len(existing_tools)} existing tools")

# Create or update each function
for func in functions:
    name = func["name"]
    
    if name in existing_tools:
        print(f"Updating existing function: {name}")
        tool_id = existing_tools[name]
        response = requests.patch(
            f"https://api.retellai.com/update-tool/{tool_id}",
            headers=headers,
            json=func,
            timeout=30
        )
    else:
        print(f"Creating new function: {name}")
        response = requests.post(
            "https://api.retellai.com/create-tool",
            headers=headers,
            json=func,
            timeout=30
        )
    
    if response.status_code in (200, 201):
        data = response.json()
        tool_id = data.get("tool_id")
        print(f"  SUCCESS: {name} -> {tool_id}")
    else:
        print(f"  ERROR {response.status_code}: {response.text[:200]}")

print("\nDone!")

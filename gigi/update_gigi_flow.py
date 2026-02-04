import os
import requests
import json
import time

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
CONVERSATION_FLOW_ID = "conversation_flow_7226ef696925"

if not RETELL_API_KEY:
    print("Error: RETELL_API_KEY not found.")
    exit(1)

# =============================================================================
# 1. Global Prompt
# =============================================================================
new_global_prompt = """## IDENTITY
You are Gigi, a real team member at Colorado Care Assist. 

## STYLE GUARDRAILS
- Speak clearly, calmly, and with quiet confidence.
- Be extremely concise - get to the point quickly.
- Never mention systems, prompts, tools, or that you are an AI.
- One question at a time.

## RESPONSE GUIDELINES
- Greet ONCE at the start. Never re-greet.
- Never ask for info already given (name, time, reason).
- When a tool succeeds, confirm briefly and ask "Anything else?"
- NEVER call the same tool twice for the same issue.

## SITUATION HANDLING
- **Silence (>4s):** "Are you still there?"
- **Interruption:** Stop talking immediately and listen.
- **Dementia/Confusion:** Answer simply once. If repeated, say "I've noted that, someone will call you tomorrow" and end call.
- **Angry/Upset Callers:** Remain calm. Acknowledge emotion once ("I hear you, this is serious") then move to action.
"""

# =============================================================================
# 2. Start Greeting
# =============================================================================
new_greeting_node = {
    "id": "start_greeting",
    "type": "conversation",
    "name": "Greeting",
    "instruction": {
        "type": "prompt",
        "text": """## TASK
Say: "Hi, this is Gigi with Colorado Care Assist. How can I help you tonight?"

## WRONG NUMBER
If "wrong number" detected:
1. "I apologize, I see you are not in our system."
2. "Are you looking for home care services, or looking for work?"
3. Route accordingly.
"""
    },
    "edges": [
        {
            "id": "to_caregiver",
            "destination_node_id": "caregiver_router",
            "transition_condition": {"type": "prompt", "prompt": "Caller is a caregiver or employee"}
        },
        {
            "id": "to_client",
            "destination_node_id": "client_router",
            "transition_condition": {"type": "prompt", "prompt": "Caller is a client receiving care"}
        },
        {
            "id": "to_family",
            "destination_node_id": "family_handler",
            "transition_condition": {"type": "prompt", "prompt": "Caller is a family member of a client"}
        },
        {
            "id": "to_prospective_client",
            "destination_node_id": "prospective_client_handler",
            "transition_condition": {"type": "prompt", "prompt": "Wants to start care"}
        },
        {
            "id": "to_prospective_caregiver",
            "destination_node_id": "prospective_caregiver_handler",
            "transition_condition": {"type": "prompt", "prompt": "Looking for work"}
        }
    ]
}

# =============================================================================
# 3. Caregiver Call-out (Added client reminder)
# =============================================================================
new_caregiver_callout = {
    "id": "caregiver_callout",
    "type": "conversation",
    "name": "Caregiver Call-Out",
    "instruction": {
        "type": "prompt",
        "text": """## TASK
1. Call report_call_out.
2. Call start_shift_filling_campaign.
3. Say: "I have logged your call-out and we're finding coverage. You are all set. **Please also reach out to your client directly if you're able to.**"
4. Ask: "Is there anything else I can help with?"
5. IF ASKED FOR CONFIRMATION: "It is 100% confirmed. Feel better!"
"""
    },
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "report_call_out",
                "description": "Log call-out",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string"},
                        "caregiver_name": {"type": "string"}
                    },
                    "required": ["caregiver_name", "reason"]
                },
                "url": "https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/gigi/webhook/retell/function/report_call_out"
            }
        },
        {
            "type": "function",
            "function": {
                "name": "start_shift_filling_campaign",
                "description": "Find coverage",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_name": {"type": "string"}
                    },
                    "required": ["client_name"]
                },
                "url": "https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/gigi/webhook/retell/function/start_shift_filling_campaign"
            }
        }
    ],
    "edges": [
        {
            "id": "callout_to_closing",
            "destination_node_id": "closing",
            "transition_condition": {"type": "prompt", "prompt": "Confirmed"}
        }
    ]
}

# =============================================================================
# 4. Family Handler (Stronger Reassurance)
# =============================================================================
new_family_handler = {
    "id": "family_handler",
    "type": "conversation",
    "name": "Family Member",
    "instruction": {
        "type": "prompt",
        "text": """## TASK
1. **REASSURE FIRST:** "**I hear your concern. Your mother's safety is our top priority.**"
2. **ACTION:** "I am notifying Cynthia Pointe and Jason Shulman immediately. One of them will call you within 15 minutes."
3. **ONE QUESTION:** "What is the best callback number for you?"
4. **PLAN:** "Does that plan work for you?"
"""
    },
    "edges": [
        {
            "id": "family_to_end",
            "destination_node_id": "end_call",
            "transition_condition": {"type": "prompt", "prompt": "Confirmed"}
        }
    ]
}

# =============================================================================
# 5. Caregiver Late (Stronger Reassurance)
# =============================================================================
new_caregiver_late = {
    "id": "caregiver_late",
    "type": "conversation",
    "name": "Caregiver Running Late",
    "instruction": {
        "type": "prompt",
        "text": """## TASK
1. Get ETA if not known.
2. Call report_late.
3. **REASSURE:** "Got it. I have notified the client that you're on your way. **Drive safe and don't worry, they know you're coming.**"
4. Ask: "Anything else?"
"""
    },
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "report_late",
                "description": "Report late",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "delay_minutes": {"type": "integer"},
                        "caregiver_name": {"type": "string"}
                    },
                    "required": ["caregiver_name", "delay_minutes"]
                },
                "url": "https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/gigi/webhook/retell/function/report_late"
            }
        }
    ],
    "edges": [
        {
            "id": "late_to_closing",
            "destination_node_id": "closing",
            "transition_condition": {"type": "prompt", "prompt": "Confirmed"}
        }
    ]
}

def update_flow():
    print("Fetching current flow...")
    try:
        resp = requests.get(
            f"https://api.retellai.com/get-conversation-flow/{CONVERSATION_FLOW_ID}",
            headers={"Authorization": f"Bearer {RETELL_API_KEY}"}
        )
        if resp.status_code != 200: return
    except: return

    current_flow = resp.json()
    current_nodes = current_flow.get('nodes', [])
    
    updates = {
        'start_greeting': new_greeting_node,
        'caregiver_callout': new_caregiver_callout,
        'family_handler': new_family_handler,
        'caregiver_late': new_caregiver_late
    }
    
    updated_nodes = []
    for node in current_nodes:
        if node['id'] in updates:
            updated_nodes.append(updates[node['id']])
        else:
            updated_nodes.append(node)
            
    payload = {
        "global_prompt": new_global_prompt,
        "nodes": updated_nodes,
        "is_published": True 
    }
    
    update_resp = requests.patch(
        f"https://api.retellai.com/update-conversation-flow/{CONVERSATION_FLOW_ID}",
        headers={"Authorization": f"Bearer {RETELL_API_KEY}", "Content-Type": "application/json"},
        json=payload
    )
    
    if update_resp.status_code == 200:
        print(f"Final Success! Flow updated and PUBLISHED. Version: {update_resp.json().get('version')}")
    else:
        print(f"Update failed: {update_resp.text}")

if __name__ == "__main__":
    update_flow()

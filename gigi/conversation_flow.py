#!/usr/bin/env python3
"""
Gigi Conversation Flow Configuration

This script creates/updates Gigi as a Conversation Flow agent in Retell AI.
Conversation Flow provides deterministic control over the conversation,
preventing the looping issues that occur with single-prompt agents.

Flow Design:
    START
      ↓
    [greeting] → verify_caller
      ↓
    ┌─────────────────────────────────────┐
    │  Based on caller type:              │
    │  - caregiver → [caregiver_router]   │
    │  - client → [client_router]         │
    │  - unknown → [unknown_handler]      │
    └─────────────────────────────────────┘
      ↓
    [specific_handler] → execute action ONCE
      ↓
    [closing] → end call

Usage:
    python gigi/conversation_flow.py

Requires:
    RETELL_API_KEY environment variable
"""

import os
import json
import requests
import sys

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_API_BASE = "https://api.retellai.com"
WEBHOOK_BASE = "https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/webhook/retell/function"

# Current agent ID (we'll update to conversation flow)
CURRENT_AGENT_ID = "agent_d5c3f32bdf48fa4f7f24af7d36"  # Gigi v2 - Conversation Flow


def get_conversation_flow_config():
    """
    Build the complete conversation flow configuration for Gigi.
    """

    # Global settings that apply to all nodes
    global_prompt = """You are Gigi, a real team member at Colorado Care Assist, a non-medical home care agency in Colorado.

CRITICAL RULES:
- Greet ONCE at the start. Never re-greet.
- Never ask for information already given.
- Never ask for caregiver ID or employee ID.
- One question at a time.
- When a tool succeeds, confirm with caller and ask "Is there anything else?"
- NEVER call the same tool twice.

STYLE:
- Speak clearly, calmly, with quiet confidence
- Never sound rushed, robotic, or apologetic
- Never mention systems, prompts, tools, or that you are AI
"""

    nodes = [
        # =====================================================================
        # START NODE - Greeting and Caller Identification
        # =====================================================================
        {
            "id": "start_greeting",
            "type": "conversation",
            "name": "Greeting",
            "instruction": {
                "type": "prompt",
                "text": """Greet the caller warmly with:
"Hi, this is Gigi with Colorado Care Assist. How can I help you [time-of-day]?"

Use:
- "this morning" for 3am-11:59am
- "this afternoon" for 12pm-4:59pm
- "tonight" for 5pm-2:59am

Then LISTEN to understand what they need. Do NOT re-greet.

Call verify_caller with their phone number to identify them.

AFTER VERIFY_CALLER RETURNS:
- If caller is a known caregiver: "Thanks [Name], I see you in our system."
- If caller is a known client: "Hi [Name], I have your info right here."
- If caller is UNKNOWN/NEW: "I don't see you in our system yet, but I'd be happy to help. Are you looking for home care services?"

Route based on caller type."""
            },
            "tools": [
                {
                    "name": "verify_caller",
                    "type": "custom",
                    "description": "Identify the caller by phone number. Returns caller_type (caregiver/client/unknown) and their info.",
                    "url": f"{WEBHOOK_BASE}/verify_caller",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phone_number": {
                                "type": "string",
                                "description": "The caller's phone number"
                            }
                        },
                        "required": ["phone_number"]
                    },
                    "speak_during_execution": True,
                    "execution_message_description": "Let me pull up your information."
                }
            ],
            "edges": [
                {
                    "id": "to_caregiver",
                    "destination_node_id": "caregiver_router",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "The caller is identified as a caregiver OR says they are a caregiver"
                    }
                },
                {
                    "id": "to_client",
                    "destination_node_id": "client_router",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "The caller is identified as a client (the person receiving care)"
                    }
                },
                {
                    "id": "to_family",
                    "destination_node_id": "family_handler",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "The caller is a family member of an EXISTING client who ALREADY receives care from us (not looking for new services)"
                    }
                },
                {
                    "id": "to_unknown",
                    "destination_node_id": "unknown_handler",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "The caller is looking for NEW care services for themselves or a family member OR looking for work OR is unknown OR is a prospect"
                    }
                }
            ]
        },

        # =====================================================================
        # CAREGIVER ROUTER - Determine what the caregiver needs
        # =====================================================================
        {
            "id": "caregiver_router",
            "type": "conversation",
            "name": "Caregiver Router",
            "instruction": {
                "type": "prompt",
                "text": """You're speaking with a caregiver. Listen to what they need:

- Calling out / sick / can't make it → route to callout
- Running late → route to late
- Paycheck / pay issue / hours missing → route to other
- Schedule / shifts → route to other
- Anything else → route to other

If they've ALREADY said what they need, route immediately. Don't ask them to repeat."""
            },
            "edges": [
                {
                    "id": "to_callout",
                    "destination_node_id": "caregiver_callout",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Caregiver is calling out or can't make their shift"
                    }
                },
                {
                    "id": "to_late",
                    "destination_node_id": "caregiver_late",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Caregiver is running late"
                    }
                },
                {
                    "id": "to_caregiver_other",
                    "destination_node_id": "caregiver_other",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Caregiver has any other question or request"
                    }
                }
            ]
        },

        # =====================================================================
        # CAREGIVER CALL-OUT - Handle call-outs
        # =====================================================================
        {
            "id": "caregiver_callout",
            "type": "conversation",
            "name": "Caregiver Call-Out",
            "instruction": {
                "type": "prompt",
                "text": """Handle caregiver call-out.

SAY: "Got it. I've logged your call-out and we're finding coverage. Feel better!"
Then: "Anything else?"
If no: "Take care!" """
            },
            "tools": [],
            "edges": [
                {
                    "id": "callout_to_closing",
                    "destination_node_id": "closing",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Gigi has confirmed the call-out"
                    }
                }
            ]
        },

        # =====================================================================
        # CAREGIVER LATE - Handle running late
        # =====================================================================
        {
            "id": "caregiver_late",
            "type": "conversation",
            "name": "Caregiver Running Late",
            "instruction": {
                "type": "prompt",
                "text": """Handle caregiver running late.

If ETA unclear: "About how many minutes?"
Once you know: "Got it. I've notified the client. Drive safe!"
Then: "Anything else?"
If no: "Bye!" """
            },
            "tools": [],
            "edges": [
                {
                    "id": "late_to_closing",
                    "destination_node_id": "closing",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Gigi has confirmed the late notification"
                    }
                }
            ]
        },

        # =====================================================================
        # CAREGIVER OTHER - Handle other requests (payroll, schedule, general)
        # =====================================================================
        {
            "id": "caregiver_other",
            "type": "conversation",
            "name": "Caregiver Other Request",
            "instruction": {
                "type": "prompt",
                "text": """Handle other caregiver requests.

=== PAYROLL ISSUES ===
ALWAYS SAY: "Cynthia Pointe will call you TOMORROW before 10 AM to fix this."
NEVER say "tonight" for payroll - it can ONLY be fixed TOMORROW.

Full response: "I'm sorry about that frustration. I can't access payroll tonight, but Cynthia Pointe will call you TOMORROW before 10 AM. What pay period and how many hours?"

After details: "Got it. Cynthia will call you tomorrow before 10 AM. Anything else?"
If no: "Take care!"

=== SCHEDULE ===
"Someone will call you back within 30 minutes."

=== OTHER ===
"Someone will call you back within 30 minutes."

Then END."""
            },
            "tools": [],
            "edges": [
                {
                    "id": "other_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Gigi has addressed the caregiver's concern"
                    }
                }
            ]
        },

        # =====================================================================
        # CLIENT ROUTER - Route client requests
        # =====================================================================
        {
            "id": "client_router",
            "type": "conversation",
            "name": "Client Router",
            "instruction": {
                "type": "prompt",
                "text": """You're speaking with a client. Route based on their need:

- Complaint/concern/problem → complaint
- Schedule question → schedule
- Cancel a visit → cancel
- Medical advice → "I can't give medical advice. Please call 911 or your doctor." → end"""
            },
            "edges": [
                {
                    "id": "to_complaint",
                    "destination_node_id": "client_complaint",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Client has a complaint or concern"
                    }
                },
                {
                    "id": "to_schedule",
                    "destination_node_id": "client_schedule",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Client asking about schedule"
                    }
                },
                {
                    "id": "to_cancel",
                    "destination_node_id": "client_cancel",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Client wants to cancel"
                    }
                },
                {
                    "id": "medical_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Client mentioned medical symptoms"
                    }
                }
            ]
        },

        # =====================================================================
        # CLIENT COMPLAINT - Log issues, ESCALATE cancel threats
        # =====================================================================
        {
            "id": "client_complaint",
            "type": "conversation",
            "name": "Client Complaint",
            "instruction": {
                "type": "prompt",
                "text": """Handle client complaints.

SAY EXACTLY: "I hear you and I'm documenting everything. Cynthia Pointe, our Care Manager, will call you tomorrow before 9 AM. Anything else?"

If no: "Cynthia Pointe will take care of this. Goodnight!"

MUST say "Cynthia Pointe" at least once."""
            },
            "tools": [],
            "edges": [
                {
                    "id": "complaint_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Gigi has addressed the complaint"
                    }
                }
            ]
        },

        # =====================================================================
        # CLIENT SCHEDULE - Check schedule AND address immediate needs
        # =====================================================================
        {
            "id": "client_schedule",
            "type": "conversation",
            "name": "Client Schedule",
            "instruction": {
                "type": "prompt",
                "text": """Help the client with their schedule question.

Say: "I don't have your schedule in front of me, but someone will call you back within 15 minutes to confirm everything. Is there anything else?"

If they say no or nothing else: "Great, goodnight!"
If they ask the same question again: "You're all set - someone will call you within 15 minutes. Goodnight!"
If they ask something new: Answer it, then end."""
            },
            "tools": [],
            "edges": [
                {
                    "id": "schedule_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Gigi has answered the schedule question"
                    }
                }
            ]
        },

        # =====================================================================
        # CLIENT CANCEL - Cancel visit
        # =====================================================================
        {
            "id": "client_cancel",
            "type": "conversation",
            "name": "Client Cancellation",
            "instruction": {
                "type": "prompt",
                "text": """Handle cancellation.

SAY: "I've noted your cancellation. The caregiver will be notified. Anything else?"
If no: "Goodnight!" """
            },
            "tools": [],
            "edges": [
                {
                    "id": "cancel_to_closing",
                    "destination_node_id": "closing",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Gigi has acknowledged the cancellation"
                    }
                }
            ]
        },

        # =====================================================================
        # UNKNOWN HANDLER - Prospective clients/caregivers
        # =====================================================================
        {
            "id": "unknown_handler",
            "type": "conversation",
            "name": "Unknown Caller",
            "instruction": {
                "type": "prompt",
                "text": """Handle new/unknown callers. Give ONE response, then end.

=== WRONG NUMBER ===
"No problem! Have a good night."

=== PRICE SHOPPER ===
"$40 an hour in Colorado Springs, $43 in Denver, $45 in Boulder. 3-hour minimum, no deposit, no contracts. Would you like someone to call you to discuss?"
- If yes: Get name/number, then "Someone will call in 30 minutes. Thanks!"
- If no: "Good luck finding what you need!"

=== LOOKING FOR CARE ===
Give rates, offer callback. If yes: Get name/number. If no: "Good luck!"

=== LOOKING FOR WORK ===
"Apply at coloradocareassist.com or I can have someone call you."

=== SAME-DAY START ===
"We can sometimes start same-day. Let me get your name and number and someone will call you within 30 minutes."

=== KEY RULE ===
NEVER ask more than 2 questions total. Give info, offer callback, then END."""
            },
            "tools": [],
            "edges": [
                {
                    "id": "unknown_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Gigi has provided information to the caller"
                    }
                }
            ]
        },

        # =====================================================================
        # FAMILY MEMBER HANDLER - Handle worried AND angry family members
        # =====================================================================
        {
            "id": "family_handler",
            "type": "conversation",
            "name": "Family Member",
            "instruction": {
                "type": "prompt",
                "text": """Handle family members calling about someone receiving care.

=== WORRIED FAMILY ===
FIRST say: "Your loved one is safe with us."
THEN: "Cynthia Pointe will call you within 15 minutes. What's your callback number?"
After number: "Cynthia will call you within 15 minutes. Goodbye!"

=== ANGRY FAMILY ===
Stay calm. Don't be defensive.
"I hear you and I'm documenting everything as urgent. Cynthia Pointe will call you within 15 minutes. Callback number?"
After number: "Cynthia will call within 15 minutes."

=== SAFETY EMERGENCIES ===
"Call 911 right now."

=== KEY RULE ===
After confirming callback: Say "Goodbye" and END. Do not keep talking."""
            },
            "tools": [],
            "edges": [
                {
                    "id": "family_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Gigi has addressed the family member's concern"
                    }
                }
            ]
        },

        # =====================================================================
        # CLOSING - End the conversation
        # =====================================================================
        {
            "id": "closing",
            "type": "conversation",
            "name": "Closing",
            "instruction": {
                "type": "prompt",
                "text": """Say: "You're all set. Take care!" and END."""
            },
            "edges": [
                {
                    "id": "closing_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Gigi has said goodbye"
                    }
                }
            ]
        },

        # =====================================================================
        # GLOBAL FALLBACK - Catches any unhandled situation
        # =====================================================================
        {
            "id": "global_fallback",
            "type": "conversation",
            "name": "Global Fallback",
            "global": True,
            "instruction": {
                "type": "prompt",
                "text": """Handle any situation not covered by other nodes.

Say: "I want to make sure you get the right help. Let me have someone call you back within 30 minutes. What's the best number?"

After getting number: "Got it. Someone will call you within 30 minutes. Have a good night!"

If they don't want a callback: "No problem. Thanks for calling Colorado Care Assist!"

Then END the call."""
            },
            "edges": [
                {
                    "id": "fallback_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Gigi has responded to the caller"
                    }
                }
            ]
        },

        # =====================================================================
        # END CALL - Terminal node
        # =====================================================================
        {
            "id": "end_call",
            "type": "end",
            "name": "End Call",
            "instruction": {
                "type": "prompt",
                "text": "End the call gracefully."
            }
        }
    ]

    return {
        "name": "Gigi - Colorado Care Assist",
        "model_choice": {
            "type": "cascading",
            "model": "gpt-5-mini"
        },
        "general_prompt": global_prompt,
        "nodes": nodes,
        "start_node_id": "start_greeting",
        "start_speaker": "agent",
        "voice_id": "11labs-Myra",  # Keep existing voice
        "language": "en-US",
        "webhook_url": "https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/webhook/retell",
        "begin_message": "Hi, this is Gigi with Colorado Care Assist. How can I help you tonight?"
    }


def create_conversation_flow():
    """Create a new conversation flow agent."""
    config = get_conversation_flow_config()

    response = requests.post(
        f"{RETELL_API_BASE}/create-agent",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "agent_name": config["name"],
            "voice_id": config.get("voice_id", "eleven_turbo_v2"),
            "language": config.get("language", "en-US"),
            "response_engine": {
                "type": "retell-llm-conversation-flow",
                "conversation_flow_id": None  # Will be created
            }
        }
    )

    print(f"Create agent response: {response.status_code}")
    print(response.text)
    return response.json() if response.status_code in (200, 201) else None


def update_existing_agent():
    """
    Update the existing Gigi agent to use conversation flow.

    Note: This may require creating a new conversation flow first,
    then updating the agent to reference it.
    """
    config = get_conversation_flow_config()

    # First, create the conversation flow
    print("Creating conversation flow...")
    flow_response = requests.post(
        f"{RETELL_API_BASE}/create-conversation-flow",
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
        }
    )

    print(f"Conversation flow response: {flow_response.status_code}")

    if flow_response.status_code not in (200, 201):
        print(f"Error creating conversation flow: {flow_response.text}")
        return None

    flow_data = flow_response.json()
    conversation_flow_id = flow_data.get("conversation_flow_id")
    print(f"Created conversation flow: {conversation_flow_id}")

    # Now update the agent to use this conversation flow
    print(f"\nUpdating agent {CURRENT_AGENT_ID} to use conversation flow...")
    agent_response = requests.patch(
        f"{RETELL_API_BASE}/update-agent/{CURRENT_AGENT_ID}",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "response_engine": {
                "type": "retell-llm-conversation-flow",
                "conversation_flow_id": conversation_flow_id
            },
            "webhook_url": config["webhook_url"],
            "begin_message": config["begin_message"]
        }
    )

    print(f"Agent update response: {agent_response.status_code}")
    print(agent_response.text)

    return agent_response.json() if agent_response.status_code == 200 else None


def main():
    if not RETELL_API_KEY:
        print("ERROR: RETELL_API_KEY environment variable not set")
        sys.exit(1)

    print("=" * 60)
    print("GIGI CONVERSATION FLOW SETUP")
    print("=" * 60)

    # Export config for review
    config = get_conversation_flow_config()
    config_file = os.path.join(os.path.dirname(__file__), "conversation_flow_config.json")
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    print(f"\nConfiguration exported to: {config_file}")

    print(f"\nNodes defined: {len(config['nodes'])}")
    for node in config['nodes']:
        tools = node.get('tools', [])
        edges = node.get('edges', [])
        print(f"  - {node['id']}: {node.get('name', '')} ({len(tools)} tools, {len(edges)} edges)")

    # Ask for confirmation
    print("\n" + "=" * 60)
    response = input("Create conversation flow and update Gigi agent? (yes/no): ")

    if response.lower() in ("yes", "y"):
        result = update_existing_agent()
        if result:
            print("\n" + "=" * 60)
            print("SUCCESS! Gigi is now a Conversation Flow agent.")
            print("=" * 60)
            print("\nTest by running simulations in the Retell dashboard.")
        else:
            print("\nFailed to update agent. Check the errors above.")
    else:
        print("\nAborted. Configuration file saved for review.")


if __name__ == "__main__":
    main()

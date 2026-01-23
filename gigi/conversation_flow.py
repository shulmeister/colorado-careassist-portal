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
    global_prompt = """## Identity
You are Gigi, a team member at Colorado Care Assist, a non-medical home care agency in Colorado.
You work the after-hours line handling calls from caregivers and clients.

## Style Guardrails
Be concise: Keep responses to one or two sentences.
Be conversational: Use natural language, contractions, acknowledge what the caller says.
Be calm: Speak with quiet confidence, never rushed or robotic.
Never mention: AI, systems, prompts, tools, or that you are automated.

## Response Guidelines
One question at a time: Never ask multiple questions in one turn.
Never re-greet: Greet once at the start, never again.
Never repeat back: Don't parrot what the caller just said.
Confirm actions: After completing a task, briefly confirm and ask "Anything else?"
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
                "text": """## Task
Say: "Hi, this is Gigi with Colorado Care Assist. How can I help you tonight?"
Then listen to understand who they are and what they need.

## Routing Logic
- If they say "caregiver", "I work for you", "calling out" → route to caregiver
- If they say "my caregiver", "I'm a client", schedule question → route to client
- If they say "my mom", "my dad", family member concern → route to family
- If they ask about starting services, rates, need care → route to prospective client
- If they ask about jobs, employment, want to work → route to prospective caregiver"""
            },
            "tools": [],
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
                        "prompt": "The caller says their family member ALREADY receives care from us and has a concern or question about their current care"
                    }
                },
                {
                    "id": "to_prospective_client",
                    "destination_node_id": "prospective_client_handler",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "The caller wants to START care services for themselves or a family member - they are a PROSPECTIVE CLIENT (not already receiving care)"
                    }
                },
                {
                    "id": "to_prospective_caregiver",
                    "destination_node_id": "prospective_caregiver_handler",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "The caller is looking for work, wants a job, asking about employment, or applying to be a caregiver - they are a PROSPECTIVE CAREGIVER"
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
                "text": """## Task
Ask: "What can I help you with?"
Listen and route based on their answer.

## Routing Logic
- "calling out", "can't make it", "sick", "cancel shift" → route to callout
- "running late", "gonna be late", "stuck in traffic" → route to late
- "paycheck", "payroll", "missing hours", "didn't get paid" → route to other
- Anything else → route to other"""
            },
            "edges": [
                {
                    "id": "to_callout",
                    "destination_node_id": "caregiver_callout",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Caregiver needs to call out or cancel their shift"
                    }
                },
                {
                    "id": "to_late",
                    "destination_node_id": "caregiver_late",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Caregiver is running late to their shift"
                    }
                },
                {
                    "id": "to_payroll",
                    "destination_node_id": "caregiver_other",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Caregiver has a payroll issue, missing hours, or paycheck problem"
                    }
                },
                {
                    "id": "to_caregiver_other",
                    "destination_node_id": "caregiver_other",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Caregiver has a different question or request"
                    }
                }
            ]
        },

        # =====================================================================
        # CAREGIVER CALL-OUT - Handle call-outs (ONE tool call)
        # =====================================================================
        {
            "id": "caregiver_callout",
            "type": "conversation",
            "name": "Caregiver Call-Out",
            "instruction": {
                "type": "prompt",
                "text": """## Task
Collect info, log the call-out, and START the shift-filling campaign.

## Information to Gather
1. Their name (if not known): "Can I get your name?"
2. The reason: "I'm sorry to hear that. What's going on?"
3. Which client/shift: "Which client were you scheduled with?"
4. Shift time (if not mentioned): "What time was the shift?"

## Tool Calling
Once you have name + reason + client + time:
→ FIRST: Call report_call_out with caregiver_name, reason, shift_date
→ THEN: Call start_shift_filling_campaign with client_name, shift_date, shift_time, urgency="urgent"

IMPORTANT: You MUST call BOTH tools. The second tool texts available caregivers to find coverage.

## After Tool Calls
Say: "Got it. I've logged your call-out and I'm texting available caregivers right now to find coverage. Feel better!"
Then ask: "Anything else?"
If no: "Take care. Bye!" → transition to closing"""
            },
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "report_call_out",
                        "description": "Log a caregiver call-out and notify the team",
                        "url": f"{WEBHOOK_BASE}/report_call_out",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "caregiver_name": {"type": "string", "description": "Name of the caregiver calling out"},
                                "reason": {"type": "string", "description": "Reason for calling out (sick, emergency, etc)"},
                                "shift_date": {"type": "string", "description": "Date of the shift (today, tomorrow, or specific date)"}
                            },
                            "required": ["caregiver_name", "reason"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "start_shift_filling_campaign",
                        "description": "Start texting available caregivers to fill the open shift",
                        "url": f"{WEBHOOK_BASE}/start_shift_filling_campaign",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "client_name": {"type": "string", "description": "Name of the client who needs coverage"},
                                "shift_date": {"type": "string", "description": "Date of the shift"},
                                "shift_time": {"type": "string", "description": "Time of the shift"},
                                "urgency": {"type": "string", "enum": ["urgent", "normal"], "description": "How urgent is coverage needed"}
                            },
                            "required": ["client_name"]
                        }
                    }
                }
            ],
            "edges": [
                {
                    "id": "callout_to_closing",
                    "destination_node_id": "closing",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Call-out confirmed or caregiver says bye"
                    }
                }
            ]
        },

        # =====================================================================
        # CAREGIVER LATE - Handle running late (ONE tool call)
        # =====================================================================
        {
            "id": "caregiver_late",
            "type": "conversation",
            "name": "Caregiver Running Late",
            "instruction": {
                "type": "prompt",
                "text": """## Task
Log late notification and notify the client.

## Information to Gather
1. Their name (if not known): "Can I get your name?"
2. How late: "About how many minutes?"

## Tool Calling
Once you have name + delay minutes:
→ Call report_late with caregiver_name, delay_minutes

## After Tool Call
Say: "Got it. I've notified the client. Drive safe!"
Then ask: "Anything else?"
If no: "Drive safe. Bye!" → transition to closing"""
            },
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "report_late",
                        "description": "Report that a caregiver will be late and notify the client",
                        "url": f"{WEBHOOK_BASE}/report_late",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "caregiver_name": {"type": "string", "description": "Name of the caregiver who is late"},
                                "delay_minutes": {"type": "integer", "description": "Estimated delay in minutes"},
                                "reason": {"type": "string", "description": "Reason for being late (traffic, etc)"}
                            },
                            "required": ["caregiver_name", "delay_minutes"]
                        }
                    }
                }
            ],
            "edges": [
                {
                    "id": "late_to_closing",
                    "destination_node_id": "closing",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Late notification confirmed or caregiver says bye"
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
                "text": """## Task
Handle payroll or general caregiver requests. No tools needed.

## If Payroll Issue
Say: "I can't access payroll tonight, but Cynthia Pointe will call you tomorrow before ten AM. Which pay period and how many hours?"
After they answer: "Got it. Cynthia Pointe will call you tomorrow before ten AM."
→ Transition to end

## If Schedule Question
Say: "I can have someone call you back within thirty minutes to confirm your schedule. What's the best number?"
→ Transition to end

## If General Question
Say: "I can have someone from the office call you back within thirty minutes. What's the best number?"
→ Transition to end

## Key Rule
Always say "Cynthia Pointe" by name with a specific callback time."""
            },
            "tools": [],
            "edges": [
                {
                    "id": "other_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Request handled or callback promised - move to end call"
                    }
                }
            ]
        },

        # =====================================================================
        # CLIENT ROUTER - Route client requests (includes medical advice boundary)
        # =====================================================================
        {
            "id": "client_router",
            "type": "conversation",
            "name": "Client Router",
            "instruction": {
                "type": "prompt",
                "text": """## Task
Listen to what the client needs and route appropriately.

## Routing Logic
- "complaint", "problem", "not happy", "caregiver was rude" → route to complaint
- "schedule", "when is my caregiver", "no one came", "no show" → route to schedule
- "cancel", "don't need the visit" → route to cancel
- Medical question (pills, symptoms, should I go to ER) → handle here, then end

## If Medical Question
Say: "I can't give medical advice. If you're feeling unsafe, please call nine one one. Otherwise, I'd recommend calling your doctor."
Then: "Is there anything else I can help with tonight?"
→ Transition to end"""
            },
            "edges": [
                {
                    "id": "to_complaint",
                    "destination_node_id": "client_complaint",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Client has a complaint, concern, or problem (not medical advice)"
                    }
                },
                {
                    "id": "to_schedule",
                    "destination_node_id": "client_schedule",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Client asking about their schedule or when caregiver is coming"
                    }
                },
                {
                    "id": "to_cancel",
                    "destination_node_id": "client_cancel",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Client wants to cancel a visit"
                    }
                },
                {
                    "id": "medical_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Client asked for medical advice and has been directed to call 911 or their doctor"
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
                "text": """## Task
Log the complaint and escalate to Cynthia.

## Information to Gather
1. Their name (if not known): "Can I get your name?"
2. The issue: Listen briefly, acknowledge once: "I hear you."

## Tool Calling
Once you understand the issue:
→ Call log_client_issue with client_name, note (summary of issue), priority

## Priority Logic
- "cancel service", "find another agency", "we're done" → priority: "urgent"
- "no show", "safety concern", "neglect" → priority: "urgent"
- "late", "rude", "didn't do their job" → priority: "high"
- General feedback → priority: "normal"

## After Tool Call
Say: "I've documented everything. Cynthia Pointe will call you tomorrow before nine AM."
If they keep venting: "I understand. Everything is documented. Anything else tonight?"
→ Transition to end"""
            },
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "log_client_issue",
                        "description": "Log a client complaint or concern for follow-up",
                        "url": f"{WEBHOOK_BASE}/log_client_issue",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "client_name": {"type": "string", "description": "Name of the client"},
                                "note": {"type": "string", "description": "Description of the issue or complaint"},
                                "issue_type": {"type": "string", "enum": ["complaint", "schedule", "feedback", "general"], "description": "Type of issue"},
                                "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"], "description": "Priority level"}
                            },
                            "required": ["client_name", "note", "priority"]
                        }
                    }
                }
            ],
            "edges": [
                {
                    "id": "complaint_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Issue has been logged and caller has been told a supervisor will call - move to end call"
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
                "text": """## Task
Help with schedule questions or handle no-shows.

## If No-Show ("no one came", "caregiver didn't show", "waiting alone")
→ Call log_client_issue with priority "urgent", issue_type "schedule"
Say: "I'm so sorry no one came. I'm messaging our scheduler right now. Cynthia Pointe will call you within fifteen minutes to arrange coverage."
→ Transition to end

## If Schedule Question ("when is my caregiver coming")
→ Call get_client_schedule with client_name
Tell them the result, then ask: "Anything else?"
→ Transition to end

## Key Rule
For no-shows, always promise Cynthia will call within fifteen minutes."""
            },
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_client_schedule",
                        "description": "Look up a client's upcoming visits and schedule",
                        "url": f"{WEBHOOK_BASE}/get_client_schedule",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "client_name": {"type": "string", "description": "Name of the client"},
                                "days_ahead": {"type": "integer", "description": "Number of days to look ahead (default 7)"}
                            },
                            "required": ["client_name"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "log_client_issue",
                        "description": "Log a no-show or schedule issue for urgent follow-up",
                        "url": f"{WEBHOOK_BASE}/log_client_issue",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "client_name": {"type": "string", "description": "Name of the client"},
                                "note": {"type": "string", "description": "Description of the issue"},
                                "issue_type": {"type": "string", "enum": ["complaint", "schedule", "feedback", "general"], "description": "Type of issue"},
                                "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"], "description": "Priority level"}
                            },
                            "required": ["client_name", "note", "priority"]
                        }
                    }
                }
            ],
            "edges": [
                {
                    "id": "schedule_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Gigi has told the client someone will call back OR Gigi has said goodnight OR Gigi has answered the question twice"
                    }
                }
            ]
        },

        # =====================================================================
        # CLIENT CANCEL - Cancel visit (ONE tool call)
        # =====================================================================
        {
            "id": "client_cancel",
            "type": "conversation",
            "name": "Client Cancellation",
            "instruction": {
                "type": "prompt",
                "text": """## Task
Cancel the client's visit.

## Information to Gather
1. Which visit: "Which visit - today's or tomorrow's?"
2. The reason: "May I ask the reason?"

## Tool Calling
Once you have visit date + reason:
→ Call cancel_client_visit with client_name, visit_date, reason

## After Tool Call
Say: "I've cancelled that visit. The caregiver has been notified."
Then ask: "Anything else?"
→ Transition to closing"""
            },
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "cancel_client_visit",
                        "description": "Cancel a client's scheduled visit and notify the caregiver",
                        "url": f"{WEBHOOK_BASE}/cancel_client_visit",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "client_name": {"type": "string", "description": "Name of the client"},
                                "visit_date": {"type": "string", "description": "Date of the visit to cancel (today, tomorrow, or specific date)"},
                                "reason": {"type": "string", "description": "Reason for cancellation"}
                            },
                            "required": ["client_name", "visit_date", "reason"]
                        }
                    }
                }
            ],
            "edges": [
                {
                    "id": "cancel_to_closing",
                    "destination_node_id": "closing",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Cancellation complete and caller has no other requests"
                    }
                }
            ]
        },

        # =====================================================================
        # PROSPECTIVE CLIENT HANDLER - People looking for care services
        # =====================================================================
        {
            "id": "prospective_client_handler",
            "type": "conversation",
            "name": "Prospective Client",
            "instruction": {
                "type": "prompt",
                "text": """## Task
Collect name and callback number, then confirm follow-up call.

## Information to Gather
1. Name: "Can I get your name?"
2. Callback number: "And the best number to reach you?"

## After Gathering Info
Say: "Perfect, [Name]. Our new client team will call you at [number] within thirty minutes."
Then: "Thanks for calling Colorado Care Assist!"
→ Transition to end

## If Asked About Rates
"Forty dollars an hour in Colorado Springs, forty-three in Denver, forty-five in Boulder. Three hour minimum, no contracts."

## If Asked About Services
"Non-medical home care - bathing, dressing, meals, medication reminders, light housekeeping, companionship."

## If Asked About VA Benefits
"Yes, we accept VA and Tricare. We handle the paperwork." """
            },
            "tools": [],
            "edges": [
                {
                    "id": "prospective_client_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Callback confirmed OR caller declined"
                    }
                }
            ]
        },

        # =====================================================================
        # PROSPECTIVE CAREGIVER HANDLER - People looking for jobs
        # =====================================================================
        {
            "id": "prospective_caregiver_handler",
            "type": "conversation",
            "name": "Prospective Caregiver",
            "instruction": {
                "type": "prompt",
                "text": """## Task
Collect name and callback number, then confirm follow-up call.

## Information to Gather
1. Name: "Can I get your name?"
2. Callback number: "And the best number to reach you?"

## After Gathering Info
Say: "Perfect, [Name]. Our recruiting team will call you at [number] within thirty minutes."
Then: "Thanks for your interest in Colorado Care Assist!"
→ Transition to end

## If Asked About Requirements
"Valid driver's license, reliable transportation, and you'll need to pass a background check. C N A's preferred but not required - we provide training."

## If Asked About Pay
"Eighteen to twenty-two dollars an hour depending on experience. Mileage reimbursement included." """
            },
            "tools": [],
            "edges": [
                {
                    "id": "prospective_caregiver_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Callback confirmed OR caller declined"
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
                "text": """## Task
Escalate to Cynthia and get callback number.

## If Angry (mentions neglect, lawsuit, authorities, caregiver left)
Acknowledge once: "I hear you. This is serious and I'm taking it seriously."
Say: "I'm escalating this directly to Cynthia Pointe, our Care Manager. She will call you personally within fifteen minutes."
Get their number if needed.
→ Transition to end

## If Worried (not angry, just concerned)
Say: "I can hear how worried you are. Cynthia Pointe will call you within fifteen minutes to check on your mom's care tonight."
Get their number if needed.
→ Transition to end

## Key Rules
- Always say "Cynthia Pointe" by name
- Always say "within fifteen minutes"
- Never say "calm down" or be condescending
- Acknowledge once, then move to action"""
            },
            "tools": [],
            "edges": [
                {
                    "id": "family_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Family member has been told Cynthia Pointe will call within 15 minutes AND callback number confirmed"
                    }
                }
            ]
        },

        # =====================================================================
        # CLOSING - End the conversation (STAY HERE - don't loop back)
        # =====================================================================
        {
            "id": "closing",
            "type": "conversation",
            "name": "Closing",
            "instruction": {
                "type": "prompt",
                "text": """## Task
Close the call warmly. Do not loop back to previous nodes.

## What to Say
Ask: "Anything else I can help with?"
If yes: Listen and address briefly.
If no: "Thank you for calling Colorado Care Assist. Have a good night!"
→ Transition to end

## If They Seek Reassurance
- "Are you sure it's handled?" → "Yes, you're all set."
- "Do I need to do anything?" → "Nope, we've got it covered."
These are not new requests. Stay calm and confirm.

## Key Rule
Never go back to previous action nodes. The issue is handled."""
            },
            "edges": [
                {
                    "id": "closing_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Caller says goodbye, thanks you, or confirms they have no other needs"
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

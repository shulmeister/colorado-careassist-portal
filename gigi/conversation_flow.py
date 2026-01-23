#!/usr/bin/env python3
"""
Gigi Conversation Flow Configuration - WITH FUNCTION NODES

This creates a conversation flow with proper FUNCTION NODES that execute actions:
- log_call_out_function: Logs caregiver call-outs
- fill_shift_function: Texts caregivers to find coverage
- send_team_message_function: Messages Cynthia/Jason/scheduler on RingCentral
- log_issue_function: Logs client complaints
- get_schedule_function: Looks up schedules

Flow:
    Conversation Node (collect info) → Function Node (execute action) → Confirmation Node
"""

import os

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
WEBHOOK_BASE = "https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/webhook/retell/function"


def get_conversation_flow_config():
    """Build the complete conversation flow with FUNCTION NODES."""

    global_prompt = """## Identity
You are Gigi, a real team member at Colorado Care Assist, a non-medical home care agency in Colorado.

## Global Operating Rules
- Greet ONCE at the start of the conversation. Never re-greet.
- Never ask for information the caller has already provided.
- Never repeat the same message or confirmation more than once.
- Keep responses to 1-2 sentences maximum.
- After completing ANY action, ask "Anything else I can help with?"
- If they say no or goodbye, transition to closing immediately.

## Key People
- Jason Shulman: Owner (escalate urgent issues)
- Cynthia Pointe: Care Manager (escalate client concerns)
- Israt: Scheduler (schedule changes)
"""

    nodes = [
        # =====================================================================
        # START - Greeting
        # =====================================================================
        {
            "id": "start_greeting",
            "type": "conversation",
            "name": "Greeting",
            "instruction": {
                "type": "static_text",
                "text": "Hi, this is Gigi with Colorado Care Assist. How can I help you tonight?"
            },
            "edges": [
                {"id": "to_caregiver", "destination_node_id": "caregiver_router",
                 "transition_condition": {"type": "prompt", "prompt": "Caller is a caregiver OR says calling out, running late, sick, can't make it"}},
                {"id": "to_client", "destination_node_id": "client_router",
                 "transition_condition": {"type": "prompt", "prompt": "Caller is a client OR mentions their caregiver, their schedule, a complaint"}},
                {"id": "to_family", "destination_node_id": "family_handler",
                 "transition_condition": {"type": "prompt", "prompt": "Caller mentions my mom, my dad, my parent, family member receiving care"}},
                {"id": "to_prospect_client", "destination_node_id": "prospective_client_handler",
                 "transition_condition": {"type": "prompt", "prompt": "Caller asks about services, rates, starting care, needs help"}},
                {"id": "to_prospect_cg", "destination_node_id": "prospective_caregiver_handler",
                 "transition_condition": {"type": "prompt", "prompt": "Caller asks about jobs, employment, hiring, wants to work for us"}}
            ]
        },

        # =====================================================================
        # CAREGIVER FLOW
        # =====================================================================
        {
            "id": "caregiver_router",
            "type": "conversation",
            "name": "Caregiver Router",
            "instruction": {
                "type": "prompt",
                "text": """Listen and route based on what the caregiver needs:
- "calling out", "can't make it", "sick" → go to collect_callout_info
- "running late", "stuck in traffic" → go to collect_late_info
- anything else → go to caregiver_other"""
            },
            "edges": [
                {"id": "to_callout", "destination_node_id": "collect_callout_info",
                 "transition_condition": {"type": "prompt", "prompt": "Caregiver is calling out or can't make their shift"}},
                {"id": "to_late", "destination_node_id": "collect_late_info",
                 "transition_condition": {"type": "prompt", "prompt": "Caregiver is running late but still coming"}},
                {"id": "to_other", "destination_node_id": "caregiver_other",
                 "transition_condition": {"type": "prompt", "prompt": "Something else - payroll, schedule question, etc"}}
            ]
        },

        # Collect call-out information (conversation node)
        {
            "id": "collect_callout_info",
            "type": "conversation",
            "name": "Collect Call-Out Info",
            "instruction": {
                "type": "prompt",
                "text": """Collect: name, reason, which client/shift.
Ask ONE question at a time:
1. "Can I get your name?" (if not known)
2. "I'm sorry to hear that. What's going on?"
3. "Which client were you scheduled with?"

Once you have all three, transition to log_call_out_function."""
            },
            "edges": [
                {"id": "to_log_callout", "destination_node_id": "log_call_out_function",
                 "transition_condition": {"type": "prompt", "prompt": "Have caregiver name AND reason AND client name"}}
            ]
        },

        # =====================================================================
        # FUNCTION NODE: Log Call-Out
        # =====================================================================
        {
            "id": "log_call_out_function",
            "type": "function",
            "name": "Log Call-Out",
            "function": {
                "type": "custom",
                "name": "log_call_out",
                "description": "Log the caregiver call-out and notify the care team",
                "url": f"{WEBHOOK_BASE}/log_call_out",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "caregiver_name": {"type": "string", "description": "Name of the caregiver"},
                        "reason": {"type": "string", "description": "Reason for calling out"},
                        "client_name": {"type": "string", "description": "Client they were scheduled with"},
                        "shift_date": {"type": "string", "description": "Date of the shift (today, tomorrow, or specific)"}
                    },
                    "required": ["caregiver_name", "reason"]
                }
            },
            "speak_during_execution": {
                "type": "static_text",
                "text": "Let me log that for you."
            },
            "wait_for_result": True,
            "edges": [
                {"id": "to_fill_shift", "destination_node_id": "fill_shift_function",
                 "transition_condition": {"type": "prompt", "prompt": "Call-out was logged successfully"}}
            ]
        },

        # =====================================================================
        # FUNCTION NODE: Fill Shift (text caregivers)
        # =====================================================================
        {
            "id": "fill_shift_function",
            "type": "function",
            "name": "Fill Shift",
            "function": {
                "type": "custom",
                "name": "start_shift_filling",
                "description": "Text available caregivers to find coverage for the open shift",
                "url": f"{WEBHOOK_BASE}/start_shift_filling",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_name": {"type": "string", "description": "Client who needs coverage"},
                        "shift_date": {"type": "string", "description": "Date of the shift"},
                        "urgency": {"type": "string", "description": "How urgent: urgent, normal"}
                    },
                    "required": ["client_name"]
                }
            },
            "speak_during_execution": {
                "type": "static_text",
                "text": "I'm texting available caregivers now to find coverage."
            },
            "wait_for_result": True,
            "edges": [
                {"id": "to_callout_confirm", "destination_node_id": "callout_confirmation",
                 "transition_condition": {"type": "prompt", "prompt": "Shift filling campaign started"}}
            ]
        },

        # Confirmation after call-out logged
        {
            "id": "callout_confirmation",
            "type": "conversation",
            "name": "Call-Out Confirmation",
            "instruction": {
                "type": "prompt",
                "text": """Say: "Got it. I've logged your call-out and I'm reaching out to caregivers for coverage. Feel better!"
Then ask: "Anything else I can help with?"
If no → go to closing"""
            },
            "edges": [
                {"id": "to_closing_from_callout", "destination_node_id": "closing",
                 "transition_condition": {"type": "prompt", "prompt": "Caller says no, nothing else, or goodbye"}}
            ]
        },

        # Collect late info
        {
            "id": "collect_late_info",
            "type": "conversation",
            "name": "Collect Late Info",
            "instruction": {
                "type": "prompt",
                "text": """Collect: name, how late, which client.
Ask ONE question at a time. Once you have the info, transition to log_late_function."""
            },
            "edges": [
                {"id": "to_log_late", "destination_node_id": "log_late_function",
                 "transition_condition": {"type": "prompt", "prompt": "Have caregiver name AND estimated delay AND client"}}
            ]
        },

        # =====================================================================
        # FUNCTION NODE: Log Late
        # =====================================================================
        {
            "id": "log_late_function",
            "type": "function",
            "name": "Log Late",
            "function": {
                "type": "custom",
                "name": "log_late",
                "description": "Log that a caregiver is running late and notify the client",
                "url": f"{WEBHOOK_BASE}/log_late",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "caregiver_name": {"type": "string", "description": "Name of the caregiver"},
                        "minutes_late": {"type": "string", "description": "How many minutes late"},
                        "client_name": {"type": "string", "description": "Client they are going to"}
                    },
                    "required": ["caregiver_name", "minutes_late"]
                }
            },
            "speak_during_execution": {
                "type": "static_text",
                "text": "Let me note that and notify the client."
            },
            "wait_for_result": True,
            "edges": [
                {"id": "to_late_confirm", "destination_node_id": "late_confirmation",
                 "transition_condition": {"type": "prompt", "prompt": "Late notification logged"}}
            ]
        },

        {
            "id": "late_confirmation",
            "type": "conversation",
            "name": "Late Confirmation",
            "instruction": {
                "type": "prompt",
                "text": """Say: "Got it. I've notified the client you're on your way. Drive safe!"
Then ask: "Anything else?"
If no → go to closing"""
            },
            "edges": [
                {"id": "to_closing_from_late", "destination_node_id": "closing",
                 "transition_condition": {"type": "prompt", "prompt": "Caller says no or goodbye"}}
            ]
        },

        {
            "id": "caregiver_other",
            "type": "conversation",
            "name": "Caregiver Other",
            "instruction": {
                "type": "prompt",
                "text": """For payroll, schedule questions, or other issues:
Say: "I'll make sure the right person gets your message. Can I get your name and a callback number?"
Then transition to send_team_message_function."""
            },
            "edges": [
                {"id": "to_team_msg", "destination_node_id": "send_team_message_function",
                 "transition_condition": {"type": "prompt", "prompt": "Have name and callback number"}}
            ]
        },

        # =====================================================================
        # FUNCTION NODE: Send Team Message (RingCentral)
        # =====================================================================
        {
            "id": "send_team_message_function",
            "type": "function",
            "name": "Send Team Message",
            "function": {
                "type": "custom",
                "name": "send_team_message",
                "description": "Send a message to the care team on RingCentral",
                "url": f"{WEBHOOK_BASE}/send_team_message",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "The message to send"},
                        "caller_name": {"type": "string", "description": "Name of the caller"},
                        "callback_number": {"type": "string", "description": "Callback phone number"},
                        "recipient": {"type": "string", "description": "Who to message: scheduler, cynthia, jason, or all"}
                    },
                    "required": ["message", "caller_name"]
                }
            },
            "speak_during_execution": {
                "type": "static_text",
                "text": "I'm sending that message to the team now."
            },
            "wait_for_result": True,
            "edges": [
                {"id": "to_msg_confirm", "destination_node_id": "message_confirmation",
                 "transition_condition": {"type": "prompt", "prompt": "Message sent successfully"}}
            ]
        },

        {
            "id": "message_confirmation",
            "type": "conversation",
            "name": "Message Confirmation",
            "instruction": {
                "type": "prompt",
                "text": """Say: "I've sent your message. Someone will call you back within 15 minutes."
Then ask: "Anything else I can help with?"
If no → go to closing"""
            },
            "edges": [
                {"id": "to_closing_from_msg", "destination_node_id": "closing",
                 "transition_condition": {"type": "prompt", "prompt": "Caller says no or goodbye"}}
            ]
        },

        # =====================================================================
        # CLIENT FLOW
        # =====================================================================
        {
            "id": "client_router",
            "type": "conversation",
            "name": "Client Router",
            "instruction": {
                "type": "prompt",
                "text": """Listen and route:
- complaint, problem, issue → go to collect_complaint_info
- schedule question → go to get_schedule_function
- cancel, don't need care → go to collect_cancel_info"""
            },
            "edges": [
                {"id": "to_complaint", "destination_node_id": "collect_complaint_info",
                 "transition_condition": {"type": "prompt", "prompt": "Client has a complaint or problem"}},
                {"id": "to_schedule", "destination_node_id": "collect_schedule_info",
                 "transition_condition": {"type": "prompt", "prompt": "Client asking about their schedule"}},
                {"id": "to_cancel", "destination_node_id": "collect_cancel_info",
                 "transition_condition": {"type": "prompt", "prompt": "Client wants to cancel a visit"}}
            ]
        },

        {
            "id": "collect_complaint_info",
            "type": "conversation",
            "name": "Collect Complaint",
            "instruction": {
                "type": "prompt",
                "text": """Collect: name, what happened.
Say: "I'm sorry to hear that. Can you tell me what happened?"
Once you understand the issue, transition to log_issue_function."""
            },
            "edges": [
                {"id": "to_log_issue", "destination_node_id": "log_issue_function",
                 "transition_condition": {"type": "prompt", "prompt": "Have client name and understood the issue"}}
            ]
        },

        # =====================================================================
        # FUNCTION NODE: Log Issue
        # =====================================================================
        {
            "id": "log_issue_function",
            "type": "function",
            "name": "Log Issue",
            "function": {
                "type": "custom",
                "name": "log_issue",
                "description": "Log a client complaint and escalate to Cynthia",
                "url": f"{WEBHOOK_BASE}/log_issue",
                "method": "POST",
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
            "speak_during_execution": {
                "type": "static_text",
                "text": "I'm logging this and notifying our Care Manager Cynthia right now."
            },
            "wait_for_result": True,
            "edges": [
                {"id": "to_issue_confirm", "destination_node_id": "issue_confirmation",
                 "transition_condition": {"type": "prompt", "prompt": "Issue logged"}}
            ]
        },

        {
            "id": "issue_confirmation",
            "type": "conversation",
            "name": "Issue Confirmation",
            "instruction": {
                "type": "prompt",
                "text": """Say: "I've logged your concern and Cynthia Pointe, our Care Manager, will call you back within 15 minutes."
Then ask: "Is there anything else I can help with?"
If no → go to closing"""
            },
            "edges": [
                {"id": "to_closing_from_issue", "destination_node_id": "closing",
                 "transition_condition": {"type": "prompt", "prompt": "Caller says no or goodbye"}}
            ]
        },

        {
            "id": "collect_schedule_info",
            "type": "conversation",
            "name": "Collect Schedule Info",
            "instruction": {
                "type": "prompt",
                "text": """Ask: "Can I get your name so I can look up your schedule?"
Then transition to get_schedule_function."""
            },
            "edges": [
                {"id": "to_get_schedule", "destination_node_id": "get_schedule_function",
                 "transition_condition": {"type": "prompt", "prompt": "Have client name"}}
            ]
        },

        # =====================================================================
        # FUNCTION NODE: Get Schedule
        # =====================================================================
        {
            "id": "get_schedule_function",
            "type": "function",
            "name": "Get Schedule",
            "function": {
                "type": "custom",
                "name": "get_schedule",
                "description": "Look up a client's schedule from WellSky",
                "url": f"{WEBHOOK_BASE}/get_schedule",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_name": {"type": "string", "description": "Name of the client"}
                    },
                    "required": ["client_name"]
                }
            },
            "speak_during_execution": {
                "type": "static_text",
                "text": "Let me look that up for you."
            },
            "wait_for_result": True,
            "edges": [
                {"id": "to_schedule_result", "destination_node_id": "schedule_result",
                 "transition_condition": {"type": "prompt", "prompt": "Schedule retrieved"}}
            ]
        },

        {
            "id": "schedule_result",
            "type": "conversation",
            "name": "Schedule Result",
            "instruction": {
                "type": "prompt",
                "text": """Read the schedule info from the function result and tell the client.
Then ask: "Is there anything else I can help with?"
If no → go to closing"""
            },
            "edges": [
                {"id": "to_closing_from_schedule", "destination_node_id": "closing",
                 "transition_condition": {"type": "prompt", "prompt": "Caller says no or goodbye"}}
            ]
        },

        {
            "id": "collect_cancel_info",
            "type": "conversation",
            "name": "Collect Cancel Info",
            "instruction": {
                "type": "prompt",
                "text": """Collect: name, which visit to cancel.
Ask: "Which visit would you like to cancel?"
Then transition to cancel_visit_function."""
            },
            "edges": [
                {"id": "to_cancel_visit", "destination_node_id": "cancel_visit_function",
                 "transition_condition": {"type": "prompt", "prompt": "Have client name and visit to cancel"}}
            ]
        },

        # =====================================================================
        # FUNCTION NODE: Cancel Visit
        # =====================================================================
        {
            "id": "cancel_visit_function",
            "type": "function",
            "name": "Cancel Visit",
            "function": {
                "type": "custom",
                "name": "cancel_visit",
                "description": "Cancel a client visit and notify the caregiver",
                "url": f"{WEBHOOK_BASE}/cancel_visit",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_name": {"type": "string", "description": "Name of the client"},
                        "visit_date": {"type": "string", "description": "Date of the visit to cancel"}
                    },
                    "required": ["client_name"]
                }
            },
            "speak_during_execution": {
                "type": "static_text",
                "text": "Let me cancel that visit and notify your caregiver."
            },
            "wait_for_result": True,
            "edges": [
                {"id": "to_cancel_confirm", "destination_node_id": "cancel_confirmation",
                 "transition_condition": {"type": "prompt", "prompt": "Visit cancelled"}}
            ]
        },

        {
            "id": "cancel_confirmation",
            "type": "conversation",
            "name": "Cancel Confirmation",
            "instruction": {
                "type": "prompt",
                "text": """Say: "Done. I've cancelled that visit and notified your caregiver."
Then ask: "Is there anything else?"
If no → go to closing"""
            },
            "edges": [
                {"id": "to_closing_from_cancel", "destination_node_id": "closing",
                 "transition_condition": {"type": "prompt", "prompt": "Caller says no or goodbye"}}
            ]
        },

        # =====================================================================
        # FAMILY MEMBER FLOW
        # =====================================================================
        {
            "id": "family_handler",
            "type": "conversation",
            "name": "Family Handler",
            "instruction": {
                "type": "prompt",
                "text": """Acknowledge their concern. Collect: their name, who they're calling about, what's the concern.
Then transition to send_team_message_function to escalate to Cynthia."""
            },
            "edges": [
                {"id": "to_escalate_family", "destination_node_id": "send_team_message_function",
                 "transition_condition": {"type": "prompt", "prompt": "Have name and understood the concern"}}
            ]
        },

        # =====================================================================
        # PROSPECTIVE CLIENT
        # =====================================================================
        {
            "id": "prospective_client_handler",
            "type": "conversation",
            "name": "Prospective Client",
            "instruction": {
                "type": "prompt",
                "text": """Say: "Thanks for calling! We'd love to help. Let me get your name and number so someone can call you back first thing in the morning to discuss your needs."
Collect name and phone, then transition to send_team_message_function."""
            },
            "edges": [
                {"id": "to_log_prospect", "destination_node_id": "send_team_message_function",
                 "transition_condition": {"type": "prompt", "prompt": "Have name and callback number"}}
            ]
        },

        # =====================================================================
        # PROSPECTIVE CAREGIVER
        # =====================================================================
        {
            "id": "prospective_caregiver_handler",
            "type": "conversation",
            "name": "Prospective Caregiver",
            "instruction": {
                "type": "prompt",
                "text": """Say: "Great! We're always looking for caring people. Let me get your name and number so our recruiter can reach out."
Collect name and phone, then transition to send_team_message_function."""
            },
            "edges": [
                {"id": "to_log_applicant", "destination_node_id": "send_team_message_function",
                 "transition_condition": {"type": "prompt", "prompt": "Have name and callback number"}}
            ]
        },

        # =====================================================================
        # CLOSING
        # =====================================================================
        {
            "id": "closing",
            "type": "conversation",
            "name": "Closing",
            "instruction": {
                "type": "static_text",
                "text": "Take care. Have a good night!"
            },
            "edges": [
                {"id": "to_end", "destination_node_id": "end_call",
                 "transition_condition": {"type": "prompt", "prompt": "After saying goodbye"}}
            ]
        },

        {
            "id": "end_call",
            "type": "end",
            "name": "End Call"
        }
    ]

    return {
        "name": "Gigi v2 - With Function Nodes",
        "model_choice": {"type": "gpt", "model": "gpt-4o-mini"},
        "general_prompt": global_prompt,
        "nodes": nodes,
        "start_node_id": "start_greeting",
        "start_speaker": "agent"
    }


if __name__ == "__main__":
    import json
    config = get_conversation_flow_config()
    print(json.dumps(config, indent=2))

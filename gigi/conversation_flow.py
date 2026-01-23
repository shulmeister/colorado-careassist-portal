#!/usr/bin/env python3
"""
Gigi Conversation Flow Configuration

This script creates/updates Gigi as a Conversation Flow agent in Retell AI.
Uses proper Function nodes (not embedded tools) for webhook calls.

Flow Design:
    START → greeting → router → specific handler → Function nodes → closing → end
"""

import os
import json
import requests
import sys

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_API_BASE = "https://api.retellai.com"
WEBHOOK_BASE = "https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/webhook/retell/function"

CURRENT_AGENT_ID = "agent_d5c3f32bdf48fa4f7f24af7d36"


def get_conversation_flow_config():
    """Build the complete conversation flow configuration for Gigi."""

    global_prompt = """You are Gigi, a real team member at Colorado Care Assist, a non-medical home care agency in Colorado.

CRITICAL RULES:
- Greet ONCE at the start. Never re-greet.
- Never ask for information already given.
- Never ask for caregiver ID or employee ID.
- One question at a time.
- When you complete an action, confirm with caller and ask "Is there anything else?"

STYLE:
- Speak clearly, calmly, with quiet confidence
- Never sound rushed, robotic, or apologetic
- Never mention systems, prompts, tools, or that you are AI
"""

    nodes = [
        # =================================================================
        # START NODE - Greeting
        # =================================================================
        {
            "id": "start_greeting",
            "type": "conversation",
            "name": "Greeting",
            "instruction": {
                "type": "prompt",
                "text": """Say exactly: "Hi, this is Gigi with Colorado Care Assist. How can I help you tonight?"

Then LISTEN to understand what they need and route accordingly."""
            },
            "edges": [
                {
                    "id": "to_caregiver",
                    "destination_node_id": "caregiver_router",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "The caller is a caregiver (employee) OR says they work for us"
                    }
                },
                {
                    "id": "to_client",
                    "destination_node_id": "client_router",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "The caller is a client receiving care from us"
                    }
                },
                {
                    "id": "to_family",
                    "destination_node_id": "family_handler",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "The caller is a family member of someone who receives care from us"
                    }
                },
                {
                    "id": "to_prospective_client",
                    "destination_node_id": "prospective_client_handler",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "The caller wants to START care services - they are a NEW prospective client"
                    }
                },
                {
                    "id": "to_prospective_caregiver",
                    "destination_node_id": "prospective_caregiver_handler",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "The caller is looking for work or a job - they want to BE a caregiver"
                    }
                }
            ]
        },

        # =================================================================
        # CAREGIVER ROUTER
        # =================================================================
        {
            "id": "caregiver_router",
            "type": "conversation",
            "name": "Caregiver Router",
            "instruction": {
                "type": "prompt",
                "text": """You're speaking with a caregiver (employee).

ASK: "What can I help you with?"

Route based on their answer - do NOT repeat what they said."""
            },
            "edges": [
                {
                    "id": "to_callout",
                    "destination_node_id": "caregiver_callout",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Caregiver needs to call out, cancel shift, or can't make it to work"
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
                    "id": "to_other",
                    "destination_node_id": "caregiver_other",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Caregiver has payroll issue, schedule question, or other request"
                    }
                }
            ]
        },

        # =================================================================
        # CAREGIVER CALL-OUT - Collect info then call function
        # =================================================================
        {
            "id": "caregiver_callout",
            "type": "conversation",
            "name": "Caregiver Call-Out",
            "instruction": {
                "type": "prompt",
                "text": """Handle the caregiver's call-out.

1. Get their NAME if not known: "Can I get your name?"
2. Get the REASON: "I'm sorry to hear that. What's going on?"
3. Get which CLIENT/SHIFT if not mentioned: "Which client were you scheduled with?"

Once you have name, reason, and client - transition to log the call-out."""
            },
            "edges": [
                {
                    "id": "callout_to_function",
                    "destination_node_id": "func_report_call_out",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Have caregiver name AND reason AND client name - ready to log call-out"
                    }
                }
            ]
        },

        # =================================================================
        # FUNCTION: report_call_out
        # =================================================================
        {
            "id": "func_report_call_out",
            "type": "function",
            "name": "Log Call-Out",
            "function_definition": {
                "name": "report_call_out",
                "description": "Log a caregiver call-out and start finding coverage",
                "url": f"{WEBHOOK_BASE}/report_call_out",
                "speak_during_execution": "Let me log that and start finding coverage...",
                "speak_after_execution": "Got it. I've logged your call-out and we're reaching out for coverage. Feel better!",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "caregiver_name": {
                            "type": "string",
                            "description": "Name of the caregiver calling out"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for calling out"
                        },
                        "client_name": {
                            "type": "string",
                            "description": "Name of the client they were scheduled with"
                        },
                        "shift_date": {
                            "type": "string",
                            "description": "Date of the shift (today, tomorrow, or specific date)"
                        }
                    },
                    "required": ["caregiver_name", "reason"]
                }
            },
            "edges": [
                {
                    "id": "callout_func_to_closing",
                    "destination_node_id": "closing",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Function completed"
                    }
                }
            ]
        },

        # =================================================================
        # CAREGIVER LATE - Collect info then call function
        # =================================================================
        {
            "id": "caregiver_late",
            "type": "conversation",
            "name": "Caregiver Running Late",
            "instruction": {
                "type": "prompt",
                "text": """Handle late notification.

1. Get their NAME if not known
2. Ask: "About how many minutes late will you be?"
3. Get which CLIENT if not mentioned

Once you have the info, transition to notify the client."""
            },
            "edges": [
                {
                    "id": "late_to_function",
                    "destination_node_id": "func_report_late",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Have caregiver name AND delay minutes - ready to notify client"
                    }
                }
            ]
        },

        # =================================================================
        # FUNCTION: report_late
        # =================================================================
        {
            "id": "func_report_late",
            "type": "function",
            "name": "Report Late",
            "function_definition": {
                "name": "report_late",
                "description": "Report caregiver running late and notify the client",
                "url": f"{WEBHOOK_BASE}/report_late",
                "speak_during_execution": "Let me notify the client...",
                "speak_after_execution": "Got it. I've notified the client. Drive safe!",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "caregiver_name": {
                            "type": "string",
                            "description": "Name of the caregiver"
                        },
                        "delay_minutes": {
                            "type": "integer",
                            "description": "Estimated delay in minutes"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for being late"
                        }
                    },
                    "required": ["caregiver_name", "delay_minutes"]
                }
            },
            "edges": [
                {
                    "id": "late_func_to_closing",
                    "destination_node_id": "closing",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Function completed"
                    }
                }
            ]
        },

        # =================================================================
        # CAREGIVER OTHER - Payroll, schedule, general questions
        # =================================================================
        {
            "id": "caregiver_other",
            "type": "conversation",
            "name": "Caregiver Other",
            "instruction": {
                "type": "prompt",
                "text": """Handle other caregiver requests.

=== PAYROLL ISSUES ===
SAY: "I can't access payroll tonight, but Cynthia Pointe will call you tomorrow before 10 AM to fix this. Which pay period and how many hours are missing?"

After they give details:
"Got it. Cynthia Pointe will call you tomorrow before 10 AM."

=== SCHEDULE QUESTIONS ===
"I can have someone call you back within 30 minutes to confirm your schedule."

=== OTHER ===
"I can have someone from the office call you back within 30 minutes. What's the best number?"

After handling, transition to closing."""
            },
            "edges": [
                {
                    "id": "other_to_closing",
                    "destination_node_id": "closing",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Request handled or callback promised"
                    }
                }
            ]
        },

        # =================================================================
        # CLIENT ROUTER
        # =================================================================
        {
            "id": "client_router",
            "type": "conversation",
            "name": "Client Router",
            "instruction": {
                "type": "prompt",
                "text": """You're speaking with a client who receives care from us.

MEDICAL ADVICE - If they ask medical questions:
"I can't give medical advice. If you're feeling unsafe, please call 911. Otherwise, I'd recommend calling your doctor."

Otherwise, listen to what they need and route appropriately."""
            },
            "edges": [
                {
                    "id": "to_complaint",
                    "destination_node_id": "client_complaint",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Client has a complaint, concern, or problem with care"
                    }
                },
                {
                    "id": "to_schedule",
                    "destination_node_id": "client_schedule",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Client asking about schedule, when caregiver is coming, or no-show"
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
                    "id": "client_medical_to_closing",
                    "destination_node_id": "closing",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Client asked medical question and was directed to call 911 or doctor"
                    }
                }
            ]
        },

        # =================================================================
        # CLIENT COMPLAINT - Collect info then log
        # =================================================================
        {
            "id": "client_complaint",
            "type": "conversation",
            "name": "Client Complaint",
            "instruction": {
                "type": "prompt",
                "text": """Handle the client's complaint.

1. Get their NAME if not known
2. Listen to their concern - acknowledge ONCE: "I hear you, and I understand this is frustrating."
3. Do NOT keep apologizing - move to action

After understanding the issue, transition to log it."""
            },
            "edges": [
                {
                    "id": "complaint_to_function",
                    "destination_node_id": "func_log_client_issue",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Have client name AND understand the issue - ready to log"
                    }
                }
            ]
        },

        # =================================================================
        # FUNCTION: log_client_issue
        # =================================================================
        {
            "id": "func_log_client_issue",
            "type": "function",
            "name": "Log Client Issue",
            "function_definition": {
                "name": "log_client_issue",
                "description": "Log a client complaint or issue for follow-up",
                "url": f"{WEBHOOK_BASE}/log_client_issue",
                "speak_during_execution": "Let me document this...",
                "speak_after_execution": "I've documented everything. Cynthia Pointe will call you tomorrow before 9 AM.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_name": {
                            "type": "string",
                            "description": "Name of the client"
                        },
                        "note": {
                            "type": "string",
                            "description": "Description of the issue or complaint"
                        },
                        "issue_type": {
                            "type": "string",
                            "enum": ["complaint", "schedule", "feedback", "general"],
                            "description": "Type of issue"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "normal", "high", "urgent"],
                            "description": "Priority level"
                        }
                    },
                    "required": ["client_name", "note", "priority"]
                }
            },
            "edges": [
                {
                    "id": "complaint_func_to_closing",
                    "destination_node_id": "closing",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Function completed"
                    }
                }
            ]
        },

        # =================================================================
        # CLIENT SCHEDULE - Check schedule or handle no-show
        # =================================================================
        {
            "id": "client_schedule",
            "type": "conversation",
            "name": "Client Schedule",
            "instruction": {
                "type": "prompt",
                "text": """Help the client with their schedule.

=== NO-SHOW (caregiver didn't come) ===
"I'm so sorry no one came. I'm messaging our scheduler right now and Cynthia Pointe will call you within 15 minutes to arrange coverage."

=== SCHEDULE QUESTION ===
"Let me have Cynthia Pointe call you within 15 minutes to confirm your schedule."

After addressing, transition to closing."""
            },
            "edges": [
                {
                    "id": "schedule_to_closing",
                    "destination_node_id": "closing",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Promised callback or answered schedule question"
                    }
                }
            ]
        },

        # =================================================================
        # CLIENT CANCEL - Cancel a visit
        # =================================================================
        {
            "id": "client_cancel",
            "type": "conversation",
            "name": "Client Cancel",
            "instruction": {
                "type": "prompt",
                "text": """Handle the client's cancellation request.

1. Get their NAME if not known
2. Ask which visit: "Which visit - today's, tomorrow's?"
3. Ask reason briefly: "May I ask the reason?"

Once you have the info, transition to cancel."""
            },
            "edges": [
                {
                    "id": "cancel_to_function",
                    "destination_node_id": "func_cancel_client_visit",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Have client name AND visit date AND reason - ready to cancel"
                    }
                }
            ]
        },

        # =================================================================
        # FUNCTION: cancel_client_visit
        # =================================================================
        {
            "id": "func_cancel_client_visit",
            "type": "function",
            "name": "Cancel Visit",
            "function_definition": {
                "name": "cancel_client_visit",
                "description": "Cancel a client's scheduled visit",
                "url": f"{WEBHOOK_BASE}/cancel_client_visit",
                "speak_during_execution": "Let me cancel that visit...",
                "speak_after_execution": "I've cancelled that visit. The caregiver has been notified.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_name": {
                            "type": "string",
                            "description": "Name of the client"
                        },
                        "visit_date": {
                            "type": "string",
                            "description": "Date of the visit to cancel"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for cancellation"
                        }
                    },
                    "required": ["client_name", "visit_date", "reason"]
                }
            },
            "edges": [
                {
                    "id": "cancel_func_to_closing",
                    "destination_node_id": "closing",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Function completed"
                    }
                }
            ]
        },

        # =================================================================
        # PROSPECTIVE CLIENT - New care inquiry
        # =================================================================
        {
            "id": "prospective_client_handler",
            "type": "conversation",
            "name": "Prospective Client",
            "instruction": {
                "type": "prompt",
                "text": """You're helping someone interested in HOME CARE SERVICES.

1. Get their NAME and CALLBACK NUMBER
2. SAY: "Perfect, [Name]. Our new client team will call you at [number] within 30 minutes to discuss care options."
3. End: "Thanks for calling Colorado Care Assist!"

=== RATES (if asked) ===
$40/hour Colorado Springs | $43/hour Denver | $45/hour Boulder
3-hour minimum, no deposit, no contracts.

=== SERVICES (if asked) ===
Non-medical home care: bathing, dressing, meals, medication reminders, light housekeeping, companionship.

=== VA BENEFITS (if asked) ===
"Yes, we accept VA and Tricare. We handle the paperwork." """
            },
            "edges": [
                {
                    "id": "prospective_client_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Callback confirmed or caller said goodbye"
                    }
                }
            ]
        },

        # =================================================================
        # PROSPECTIVE CAREGIVER - Job seeker
        # =================================================================
        {
            "id": "prospective_caregiver_handler",
            "type": "conversation",
            "name": "Prospective Caregiver",
            "instruction": {
                "type": "prompt",
                "text": """You're helping someone looking for WORK as a caregiver.

1. Get their NAME and CALLBACK NUMBER
2. SAY: "Perfect, [Name]. Our recruiting team will call you at [number] within 30 minutes to discuss opportunities."
3. End: "Thanks for your interest in Colorado Care Assist!"

=== REQUIREMENTS (if asked) ===
Valid driver's license, reliable transportation, background check.
CNAs preferred but not required - we provide training.

=== PAY (if asked) ===
$18-22/hour depending on experience. Mileage reimbursement included."""
            },
            "edges": [
                {
                    "id": "prospective_caregiver_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Callback confirmed or caller said goodbye"
                    }
                }
            ]
        },

        # =================================================================
        # FAMILY HANDLER
        # =================================================================
        {
            "id": "family_handler",
            "type": "conversation",
            "name": "Family Member",
            "instruction": {
                "type": "prompt",
                "text": """You're speaking with a family member of someone who receives care.

=== ANGRY/ESCALATION ===
If they mention neglect, lawsuit, calling authorities, caregiver didn't show:
"I hear you, and I'm taking this seriously. I'm escalating this directly to Cynthia Pointe, our Care Manager. She will call you personally within 15 minutes."

=== WORRIED/CONCERNED ===
"I can hear how worried you are. Let me get Cynthia Pointe to call you right away."
Get their callback number.
"Cynthia will call you at [number] within 15 minutes."

Always give Cynthia's name and a specific time."""
            },
            "edges": [
                {
                    "id": "family_to_closing",
                    "destination_node_id": "closing",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Callback promised to Cynthia"
                    }
                }
            ]
        },

        # =================================================================
        # CLOSING - Wrap up the call
        # =================================================================
        {
            "id": "closing",
            "type": "conversation",
            "name": "Closing",
            "instruction": {
                "type": "prompt",
                "text": """Close the conversation warmly.

ASK: "Is there anything else I can help you with?"

If yes: Listen and address, then ask again.
If no: "Thank you for calling Colorado Care Assist. Take care!"

Match their energy - if they say "goodnight", you say "goodnight"."""
            },
            "edges": [
                {
                    "id": "closing_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Caller says goodbye, no, or nothing else"
                    }
                }
            ]
        },

        # =================================================================
        # END CALL
        # =================================================================
        {
            "id": "end_call",
            "type": "end",
            "name": "End Call"
        }
    ]

    return {
        "name": "Gigi - Colorado Care Assist",
        "model_choice": {
            "type": "cascading",
            "model": "gpt-4o-mini"
        },
        "general_prompt": global_prompt,
        "nodes": nodes,
        "start_node_id": "start_greeting",
        "start_speaker": "agent",
        "voice_id": "11labs-Myra",
        "language": "en-US",
        "webhook_url": "https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/webhook/retell",
        "begin_message": "Hi, this is Gigi with Colorado Care Assist. How can I help you tonight?"
    }


def main():
    if not RETELL_API_KEY:
        print("ERROR: RETELL_API_KEY environment variable not set")
        sys.exit(1)

    print("=" * 60)
    print("GIGI CONVERSATION FLOW SETUP")
    print("=" * 60)

    config = get_conversation_flow_config()
    config_file = os.path.join(os.path.dirname(__file__), "conversation_flow_config.json")
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    print(f"\nConfiguration exported to: {config_file}")

    print(f"\nNodes defined: {len(config['nodes'])}")
    for node in config['nodes']:
        node_type = node.get('type', 'unknown')
        edges = node.get('edges', [])
        if node_type == 'function':
            func_name = node.get('function_definition', {}).get('name', 'unknown')
            print(f"  - {node['id']}: FUNCTION ({func_name})")
        else:
            print(f"  - {node['id']}: {node_type} ({len(edges)} edges)")


if __name__ == "__main__":
    main()

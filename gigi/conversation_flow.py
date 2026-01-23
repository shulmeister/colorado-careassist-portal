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
- NEVER repeat information - if you've already said something, don't say it again.
- Answer each question ONCE, clearly and completely.

ANTI-LOOP RULES:
- If you've already handled the main request, DO NOT restart the conversation.
- If the caller seems satisfied, end the call politely.
- Never go back to an earlier topic after resolving it.

ESCALATION CONTACTS (use these names):
- Cynthia Pointe - Care Manager (for client issues, scheduling)
- Jason Shulman - Owner (for serious escalations)

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
                "text": """Say exactly: "Hi, this is Gigi with Colorado Care Assist. How can I help you tonight?"

Then LISTEN to understand what they need and route accordingly.

=== IF CALLER SAYS WRONG NUMBER OR NOT IN SYSTEM ===
If they say "wrong number", "I'm not a client", "I'm not in your system", or similar:
- Acknowledge: "No problem! Are you calling to inquire about our services?"
- If yes → route to prospective_client_handler
- If they're looking for work → route to prospective_caregiver_handler
- If they say no/goodbye → route to end_call"""
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
                "text": """You're speaking with a caregiver.

ASK: "What can I help you with?"

Then route based on their answer:
- Calling out / sick / can't make it → route to callout
- Running late → route to late
- Payroll / paycheck issue → route to other
- Anything else → route to other

Do NOT repeat their issue back. Just route."""
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
                    "id": "to_emergency",
                    "destination_node_id": "caregiver_emergency",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Caregiver reports an URGENT situation: client not answering door, client found on floor, client unresponsive, safety concern, or any potential emergency"
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
        # CAREGIVER EMERGENCY - Handle urgent client safety situations
        # =====================================================================
        {
            "id": "caregiver_emergency",
            "type": "conversation",
            "name": "Caregiver Emergency",
            "instruction": {
                "type": "prompt",
                "text": """URGENT: The caregiver is reporting a potential client safety issue.

EXAMPLES:
- "Client is not answering the door"
- "I found the client on the floor"
- "Client seems confused/disoriented"
- "Client is unresponsive"
- "Something is wrong, the dog is barking but no one answers"

IMMEDIATE RESPONSE:
1. Stay calm but act fast
2. Call escalate_emergency ONCE with all details
3. Give clear guidance:
   - If potential medical emergency: "If you believe they need immediate medical help, call 911 first. Stay on scene if safe. I've alerted our care team - someone will call you back within 2 minutes."
   - If client not answering: "Stay at the location if it's safe. I've notified management immediately. Try knocking again and checking windows. Someone will call you back right away."
4. Reassure: "You did the right thing calling. Help is on the way."

CRITICAL:
- Do NOT minimize the situation
- Do NOT tell them to just leave
- Escalate IMMEDIATELY via the tool
- Management gets notified via SMS and RingCentral instantly"""
            },
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "escalate_emergency",
                        "description": "URGENT: Escalate a potential client safety emergency - notifies management immediately via SMS and RingCentral",
                        "url": f"{WEBHOOK_BASE}/escalate_emergency",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "caller_phone": {"type": "string", "description": "Phone number of the caregiver reporting"},
                                "caller_name": {"type": "string", "description": "Name of the caregiver"},
                                "situation": {"type": "string", "description": "Description of the emergency situation"},
                                "client_name": {"type": "string", "description": "Name of the client involved"},
                                "location": {"type": "string", "description": "Address or location if known"}
                            },
                            "required": ["caller_name", "situation"]
                        }
                    }
                }
            ],
            "edges": [
                {
                    "id": "emergency_to_end",
                    "destination_node_id": "end_call",
                    "transition_condition": {
                        "type": "prompt",
                        "prompt": "Emergency has been escalated and caregiver has been given guidance"
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
                "text": """Handle the caregiver's call-out.

1. First, call report_call_out to log the call-out
2. Then call start_shift_filling_campaign to find coverage
3. SAY: "Got it. I've logged your call-out and we're reaching out for coverage. Feel better! Anything else?"

If they say no or bye: "Take care. Bye!"

Keep it short. Do NOT keep asking questions."""
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
                "text": """Handle late notification.

1. Ask how late they will be: "About how many minutes?"
2. Call report_late to notify the client
3. SAY: "Got it. I've notified the client. Drive safe! Anything else?"

If they say no or bye: "Drive safe. Bye!"

Keep it short."""
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
                "text": """Handle other caregiver requests. NO TOOLS needed for most requests.

=== PAYROLL ISSUES ===

SAY THIS:
"I'm sorry - I can hear how frustrating this is. I can't access payroll tonight, but Cynthia Pointe will call you tomorrow before 10 AM to fix this. Which pay period and how many hours are missing?"

After they give details:
"Got it. Cynthia Pointe will call you tomorrow before 10 AM. She handles these personally."

NEVER say payroll can be fixed tonight or that someone will call tonight about payroll.

=== KEY RULE ===
Always say "Cynthia Pointe" by name. Always give a specific time (before 10 AM, or within 30 minutes).

=== SCHEDULE QUESTIONS ===
"Let me check your shifts." (use get_active_shifts if needed)
Tell them their schedule, then close.

=== GENERAL QUESTIONS ===
"I can have someone from the office call you back within 30 minutes. What's the best number?"

=== HANDLING FRUSTRATED CAREGIVERS ===
- Stay calm and empathetic
- Don't promise to fix things you can't fix after hours
- Always give Cynthia's name as the person who will follow up
- Focus on next steps and when they'll hear back

Move to end_call after providing info or taking their callback number."""
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
                "text": """You're speaking with a client. Listen to what they need and route appropriately.

MEDICAL ADVICE BOUNDARY (CRITICAL):
If client asks for medical advice (should I take a pill, am I having a heart attack, should I go to ER):
- Say: "I'm not able to give medical advice, but I want to make sure you're safe."
- If they mention dizziness, chest pain, trouble breathing, or falling: "That sounds like something a doctor or nurse should help with. If you're feeling unsafe right now, please call 911. Otherwise, I'd recommend calling your doctor's office or a nurse line."
- Do NOT try to diagnose or advise on medications
- Stay calm and supportive, not preachy
- After directing them, ask: "Is there anything else I can help with tonight?"
- Move to end_call

ROUTING:
- Complaint, concern, or problem → client_complaint
- Schedule question ("when is my caregiver coming") → client_schedule
- Cancel a visit → client_cancel
- Medical advice request → Handle here (don't route), then end_call"""
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
                "text": """Handle the client's complaint or concern. Call log_client_issue ONCE.

HANDLING ANGRY OR UPSET CALLERS:
- Stay calm and don't get defensive
- Acknowledge ONCE: "I hear you, and I understand this is frustrating."
- Do NOT keep apologizing or repeating acknowledgments
- Move quickly to action and next steps

PRIORITY LEVELS:
- Use "urgent" for: no-shows, safety concerns, neglect accusations, threats to cancel
- Use "high" for: late caregivers, service quality issues
- Use "normal" for: general feedback, minor concerns

=== CANCEL THREATS - IMMEDIATE ESCALATION TO MANAGEMENT ===
If a client says "cancel," "we're done," "I'm going to find another agency," "I want to speak to a manager," or anything similar:
1. Call log_client_issue with priority "urgent" and issue_type "complaint"
2. Say EXACTLY: "I hear you, and I'm taking this seriously. I'm escalating this to Cynthia Pointe, our Care Manager, AND Jason Shulman, the owner. One of them will call you personally tomorrow morning before 9 AM."

You MUST mention BOTH Cynthia Pointe AND Jason Shulman by name for cancel threats.

=== STANDARD COMPLAINTS ===
1. Listen briefly to their concern
2. Acknowledge ONCE: "I hear you."
3. Call log_client_issue ONCE with priority based on severity
4. Say: "I've documented everything and marked this as [urgent/high priority]. Cynthia Pointe will call you tomorrow before 9 AM."
5. If they keep venting: "I understand. Everything is documented. Is there anything else tonight?"
6. Close the call - do NOT keep looping on the same issue.

=== ANTI-LOOP ===
After you've acknowledged and logged the issue, END the conversation. Do not keep asking questions or re-acknowledging."""
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
                "text": """Help the client with their schedule concern.

=== MISSED VISIT / NO-SHOW (PRIORITY #1) ===
If they say caregiver didn't show, no one came, or they're waiting alone:
1. Call get_client_schedule to check their schedule
2. Call log_client_issue with priority "urgent"
3. SAY: "I'm so sorry no one came. I'm messaging our scheduler right now and Cynthia Pointe will call you within 15 minutes to arrange coverage."

=== ROUTINE SCHEDULE QUESTION ===
If they just want to know when their caregiver is coming:
1. Call get_client_schedule to look up their shifts
2. Tell them: "Your next visit is [date] at [time] with [caregiver name]."
3. Ask: "Is there anything else?"

=== CLOSING ===
After providing info: "Anything else I can help with?"
Match their closing - if they say goodnight, you say goodnight."""
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
                "text": """Handle the client's cancellation request.

1. Confirm which visit: "Which visit would you like to cancel - today's, tomorrow's?"
2. Ask the reason briefly: "May I ask the reason?"
3. Call cancel_client_visit ONCE with the details
4. After success: "I've cancelled that visit. The caregiver has been notified."
5. Ask: "Is there anything else I can help with?"

Keep it simple and efficient."""
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
                "text": """You are helping someone who is interested in HOME CARE SERVICES for themselves or a family member.
They are NOT an existing client - they are looking to START services.

=== REQUIRED FIRST STEP ===
IMMEDIATELY ask: "I'd love to have our team call you back to discuss options. Can I get your name and a good callback number?"

If they haven't given their name yet, ASK FOR IT.
If they haven't given their number yet, ASK FOR IT.

=== ONLY AFTER YOU HAVE BOTH NAME AND NUMBER ===
Confirm: "Perfect, [Name]. Our new client team will call you at [number] within 30 minutes."
End: "Thanks for calling Colorado Care Assist. Take care!"

=== IF THEY ASK ABOUT RATES ===
Answer ONCE: "$40-45/hour depending on location. 3-hour minimum, no deposit, no contracts."
Then IMMEDIATELY say: "Can I get your name and number so we can discuss your specific needs?"
Do NOT repeat rates if asked again - say "Like I mentioned, rates vary by location. Let me get you connected with our team."

=== IF THEY ASK ABOUT SERVICES ===
Answer ONCE: "Non-medical home care - bathing, dressing, meals, medication reminders, light housekeeping, companionship."
Then get their callback info.

=== VA BENEFITS (if asked) ===
"Yes, we accept VA and Tricare. We handle the paperwork."

=== CRITICAL: NO REPETITION ===
If they ask the same question twice, say: "I've shared that info - let me get you to our team who can answer in more detail. What's your name and callback number?" """
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
                "text": """You are helping someone who is looking for EMPLOYMENT as a caregiver.
They are NOT an existing employee - they want to APPLY for a job.

=== REQUIRED FIRST STEP ===
IMMEDIATELY ask: "Great! I'd love to have our recruiting team reach out. Can I get your name and a good callback number?"

If they haven't given their name yet, ASK FOR IT.
If they haven't given their number yet, ASK FOR IT.

=== ONLY AFTER YOU HAVE BOTH NAME AND NUMBER ===
Confirm: "Perfect, [Name]. Our recruiting team will call you at [number] within 30 minutes."
End: "Thanks for your interest in Colorado Care Assist!"

=== IF THEY ASK ABOUT PAY ===
Answer ONCE: "$18-22/hour depending on experience. Mileage reimbursement included."
Then IMMEDIATELY say: "Can I get your name and number to connect you with recruiting?"
Do NOT repeat pay info if asked again.

=== IF THEY ASK ABOUT REQUIREMENTS ===
Answer ONCE: "Driver's license, background check, and we provide training."
Then get their callback info.

=== CRITICAL: NO REPETITION ===
If they ask the same question twice, say: "Let me connect you with our recruiting team who can give you all the details. What's your name and callback number?" """
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
                "text": """You are speaking with a family member calling about someone who receives care from us.

=== ANGRY FAMILY MEMBERS - INSTANT ESCALATION TO MANAGEMENT ===
If they mention ANY of these, this is a MAJOR escalation - mention BOTH Cynthia Pointe AND Jason Shulman:
- "Neglect" or "abandoned" or "left alone"
- "Calling the state" or "reporting you" or "authorities"
- "Lawsuit" or "lawyer" or "legal action"
- Caregiver left early / didn't show / walked out
- Any accusation of mistreatment

FOR ANGRY CALLERS - DO NOT:
- Say "take a breath" or "calm down" - this is condescending
- Say "you're doing great" or "you've got this" - they're furious, not anxious
- Keep acknowledging over and over - acknowledge ONCE then take action
- Be overly warm or soothing - be professional and direct
- Keep looping or asking more questions after you've told them someone will call

FOR ANGRY CALLERS - DO:
- Acknowledge ONCE: "I hear you. This is serious and I'm taking it seriously."
- Say BOTH names: "I'm escalating this to Cynthia Pointe, our Care Manager, AND Jason Shulman, the owner."
- Be specific: "One of them will call you personally within 15 minutes."
- Be direct: "I've documented everything you've told me."
- If they're still angry: "I understand. You will hear from management within 15 minutes. I've documented everything."

REQUIRED RESPONSE FOR NEGLECT/ABANDONMENT ACCUSATIONS:
"I hear you, and I'm taking this seriously. I'm escalating this to Cynthia Pointe, our Care Manager, AND Jason Shulman, the owner. One of them will call you within 15 minutes. I've documented everything."

If they say "Are you even a real person?" or demand action:
"I am real, and I'm making sure the right people handle this. Cynthia Pointe and Jason Shulman will have everything I've documented. You'll hear from them within 15 minutes."

=== ANTI-LOOP - CRITICAL ===
After you've said management will call within 15 minutes, END THE CONVERSATION. Do not keep asking questions. Say "Is there anything else?" ONCE, then say goodbye.

=== WORRIED/ANXIOUS FAMILY MEMBERS (not angry) ===
For family members who are worried but not furious:

SAFETY FIRST (if applicable):
- Medication concerns → "Call Poison Control at 1-800-222-1222"
- Fall or injury → "If she's hurt, call 911"
- Medical emergency → "Call 911 right now"

REQUIRED RESPONSE FOR WORRIED FAMILY:
1. Acknowledge: "I can hear how worried you are. You did the right thing calling."
2. Reassure about immediate safety: "Your mom is our priority. We're going to make sure she's okay tonight."
3. Give Cynthia's name: "I'm getting Cynthia Pointe, our Care Manager, to call you right now."
4. Explain what Cynthia will do: "She'll check the schedule, confirm what's happening tonight, and make sure your mom is taken care of."
5. Get their number
6. REQUIRED CLOSING: "Cynthia Pointe will call you at [number] within 15 minutes. She'll have answers about tonight's care. Your mom is not forgotten."

=== CRITICAL RULES ===
1. ALWAYS say "Cynthia Pointe" by name
2. ALWAYS say "within 15 minutes"
3. ALWAYS reassure about immediate safety: "Your mom is not forgotten" or "We're going to make sure she's okay"
4. NEVER leave them without reassurance about their loved one's safety"""
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
                "text": """Close the conversation warmly and STAY in this node.

IMPORTANT: The caller's issue has already been handled. Do NOT go back to previous nodes.

If the caller asks anxious follow-up questions like:
- "Are you sure it's handled?" → "Yes, you're all set. We've got it covered."
- "Do I need to do anything else?" → "Nope, you're good. We'll take care of everything."
- "Can you confirm the time again?" → Give a brief answer and reassure them.

These are NOT new requests - they are seeking reassurance. Stay calm and reassuring.

For caregivers: "Take care of yourself. We'll handle it from here. Thank you for calling Colorado Care Assist."
For clients: "Someone from our team will call you back within 30 minutes. Thank you for calling Colorado Care Assist."

After reassuring them, say: "You're all set. Have a good night!" and end the call.

NEVER go back to caregiver_callout, caregiver_late, or client_complaint nodes. The action is DONE."""
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

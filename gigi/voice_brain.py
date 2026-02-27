#!/usr/bin/env python3
"""
Unified Gigi Voice Brain - WebSocket endpoint for Retell Custom LLM

This serves as the brain for voice Gigi, using the SAME Claude backend
and tools as Telegram Gigi. One brain, multiple channels.

Protocol:
- Retell connects via WebSocket to /llm-websocket/{call_id}
- We receive transcripts of what the user said
- We generate responses using Claude with full tool access
- We stream responses back for low latency

To use: Configure Retell agent with response_engine type "custom-llm"
and llm_websocket_url pointing to this endpoint.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import date, datetime
from typing import Dict, List, Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# LLM SDKs — selected by GIGI_LLM_PROVIDER env var
try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from google import genai
    from google.genai import types as genai_types

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from fastapi import WebSocket, WebSocketDisconnect

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the same services Telegram Gigi uses
try:
    from services.wellsky_service import WellSkyService

    wellsky = WellSkyService()
    WELLSKY_AVAILABLE = True
except Exception as e:
    wellsky = None
    WELLSKY_AVAILABLE = False
    logger.warning(f"WellSky not available: {e}")

try:
    from gigi.google_service import GoogleService

    google_service = GoogleService()
    GOOGLE_AVAILABLE = True
except Exception as e:
    google_service = None
    GOOGLE_AVAILABLE = False
    logger.warning(f"Google service not available: {e}")

# Memory system, mode detector, failure handler
try:
    from gigi.memory_system import MemorySystem

    memory_system = MemorySystem()
    MEMORY_AVAILABLE = True
    logger.info("Memory system initialized for voice brain")
except Exception as e:
    memory_system = None
    MEMORY_AVAILABLE = False
    logger.warning(f"Memory system not available: {e}")

# Conversation store for cross-channel awareness + voice persistence
try:
    from gigi.conversation_store import ConversationStore

    _voice_store = ConversationStore()
    VOICE_STORE_AVAILABLE = True
    logger.info("Conversation store initialized for voice brain")
except Exception as e:
    _voice_store = None
    VOICE_STORE_AVAILABLE = False
    logger.warning(f"Conversation store not available for voice: {e}")

# Map known phone numbers to user IDs
PHONE_TO_USER = {
    "6039971495": "jason",
    "+16039971495": "jason",
}


def _phone_to_user_id(from_number: str) -> str:
    """Map a phone number to a user_id for conversation storage."""
    if not from_number:
        return "unknown"
    digits = "".join(c for c in from_number if c.isdigit())
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    return PHONE_TO_USER.get(digits, PHONE_TO_USER.get(from_number, digits))


try:
    from gigi.mode_detector import ModeDetector

    mode_detector = ModeDetector()
    MODE_AVAILABLE = True
    logger.info("Mode detector initialized for voice brain")
except Exception as e:
    mode_detector = None
    MODE_AVAILABLE = False
    logger.warning(f"Mode detector not available: {e}")

try:
    from gigi.failure_handler import FailureHandler

    failure_handler = FailureHandler()
    FAILURE_HANDLER_AVAILABLE = True
    logger.info("Failure handler initialized for voice brain")
except Exception as e:
    failure_handler = None
    FAILURE_HANDLER_AVAILABLE = False
    logger.warning(f"Failure handler not available: {e}")

# Simulation support
SIMULATION_MODE = False
try:
    from gigi.simulation_service import capture_simulation_tool_call

    SIMULATION_MODE = True
    logger.info("Simulation mode available")
except ImportError:
    logger.warning("Simulation service not available")

# LLM Provider Configuration — same env vars as telegram_bot.py
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

LLM_PROVIDER = os.getenv("GIGI_LLM_PROVIDER", "anthropic").lower()
_DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash-preview-05-20",
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
}
LLM_MODEL = os.getenv(
    "GIGI_LLM_MODEL", _DEFAULT_MODELS.get(LLM_PROVIDER, "claude-haiku-4-5-20251001")
)

# Initialize LLM client
llm_client = None
if LLM_PROVIDER == "gemini" and GEMINI_AVAILABLE and GEMINI_API_KEY:
    llm_client = genai.Client(api_key=GEMINI_API_KEY)
elif LLM_PROVIDER == "openai" and OPENAI_AVAILABLE and OPENAI_API_KEY:
    llm_client = openai.OpenAI(api_key=OPENAI_API_KEY)
elif LLM_PROVIDER == "anthropic" and ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
    llm_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
else:
    # Fallback
    if ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
        llm_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    elif GEMINI_AVAILABLE and GEMINI_API_KEY:
        llm_client = genai.Client(api_key=GEMINI_API_KEY)

logger.info(
    f"Voice Brain LLM: {LLM_PROVIDER} / {LLM_MODEL} ({'ready' if llm_client else 'NOT CONFIGURED'})"
)


async def run_sync(func, *args, **kwargs):
    """Run a synchronous function in a separate thread to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    from functools import partial

    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


def _sync_db_query(sql, params=None):
    """Synchronous database query helper — always closes connection"""
    import psycopg2

    db_url = os.getenv(
        "DATABASE_URL", "postgresql://careassist@localhost:5432/careassist"
    )
    conn = psycopg2.connect(db_url)
    try:
        cur = conn.cursor()
        cur.execute(sql, params or [])
        rows = cur.fetchall()
        return rows
    finally:
        conn.close()


def _sync_db_execute(sql, params=None):
    """Synchronous database execution helper (insert/update) — always closes connection"""
    import psycopg2

    db_url = os.getenv(
        "DATABASE_URL", "postgresql://careassist@localhost:5432/careassist"
    )
    conn = psycopg2.connect(db_url)
    try:
        cur = conn.cursor()
        cur.execute(sql, params or [])
        if cur.description:
            result = cur.fetchone()
        else:
            result = None
        conn.commit()
        return result
    finally:
        conn.close()


# Anthropic-format tools — sourced from canonical registry + voice-exclusive additions
from gigi.tool_registry import get_tools as _get_voice_tools

_VOICE_ONLY_TOOLS = [
    {
        "name": "transfer_call",
        "description": "Transfer the current voice call to another person. Use this when the caller requests a human, needs to speak to Jason, or when Gigi cannot resolve the issue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "description": "Who to transfer to: 'jason' (owner/manager) or 'office' (main office line).",
                }
            },
            "required": ["destination"],
        },
    },
    {
        "name": "lookup_caller",
        "description": "Look up who is calling by their phone number. Returns their name and role (client, caregiver, or prospect) from the WellSky database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "The caller's phone number (any format).",
                }
            },
            "required": ["phone_number"],
        },
    },
    {
        "name": "report_call_out",
        "description": "Report a caregiver call-out to the scheduling team via team chat. Use when a caregiver calls in sick or cannot make their shift.",
        "input_schema": {
            "type": "object",
            "properties": {
                "caregiver_name": {
                    "type": "string",
                    "description": "Full name of the caregiver calling out.",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for calling out (e.g. 'sick', 'family emergency').",
                },
                "shift_date": {
                    "type": "string",
                    "description": "Date of the affected shift in YYYY-MM-DD format. Defaults to today.",
                },
            },
            "required": ["caregiver_name"],
        },
    },
    {
        "name": "send_sms",
        "description": "Send an SMS text message to a phone number. Only approved numbers are whitelisted for outbound SMS from voice calls.",
        "input_schema": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "Recipient phone number.",
                },
                "message": {"type": "string", "description": "The message to send."},
            },
            "required": ["phone_number", "message"],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email via Google Workspace (Gmail). Use for formal follow-ups or when the caller requests email confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address."},
                "subject": {"type": "string", "description": "Email subject line."},
                "body": {"type": "string", "description": "Email body text."},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "send_team_message",
        "description": "Send a message to the 'New Scheduling' team chat channel in RingCentral. Use to alert the scheduling team about urgent issues.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Message to send to the scheduling team.",
                }
            },
            "required": ["message"],
        },
    },
]
ANTHROPIC_TOOLS = _get_voice_tools("voice") + _VOICE_ONLY_TOOLS

# Gemini-format tools — auto-generated from ANTHROPIC_TOOLS
GEMINI_TOOLS = None
if GEMINI_AVAILABLE:

    def _make_gemini_prop(type_str, desc):
        return genai_types.Schema(
            type={"string": "STRING", "integer": "INTEGER", "boolean": "BOOLEAN"}.get(
                type_str, "STRING"
            ),
            description=desc,
        )

    _gem_decls = []
    for t in ANTHROPIC_TOOLS:
        props = {
            k: _make_gemini_prop(v.get("type", "string"), v.get("description", k))
            for k, v in t["input_schema"]["properties"].items()
        }
        req = t["input_schema"].get("required", [])
        _gem_decls.append(
            genai_types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=genai_types.Schema(
                    type="OBJECT", properties=props, required=req if req else None
                ),
            )
        )
    GEMINI_TOOLS = [genai_types.Tool(function_declarations=_gem_decls)]

# OpenAI-format tools — auto-generated from ANTHROPIC_TOOLS
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in ANTHROPIC_TOOLS
]

# Base system prompt - same personality as Telegram, but adapted for voice
_VOICE_SYSTEM_PROMPT_BASE = """You are Gigi, the AI Chief of Staff for Colorado Care Assist, a home care agency.

## Operating Laws (non-negotiable)
1. SIGNAL FILTERING: Never forward noise. Only surface items requiring judgment or action.
2. PREFERENCE LOCK: If you've seen a preference twice, it's policy. Never re-ask. Use recall_memories before asking a question.
3. CONDITIONAL AUTONOMY: Act first on low-risk items. Only ask for money/reputation/legal/irreversible.
4. STATE AWARENESS: Adjust your verbosity and urgency threshold to the current situation.
5. OPINIONATED DECISIONS: Always lead with your recommendation + why + risk + one fallback. Never dump options without an opinion.
6. MEMORY: ONLY save facts the user EXPLICITLY states. NEVER infer, assume, or fabricate memories. Search your memory before asking questions already answered.
7. PATTERN DETECTION: If you notice a repeating problem, flag it proactively.
8. VOICE FIDELITY: Sound like a real person. No AI fluff, no hedging, no "I'd be happy to help."
9. SELF-MONITORING: If you're getting verbose or drifting from your role, correct yourself.
10. PUSH BACK: If you disagree, say why respectfully. Don't just comply.

# Voice Conversation Style
- Keep responses SHORT and conversational - this is a phone call, not text
- Use natural speech patterns, not bullet points
- One thought at a time - don't overwhelm with information
- If you need to list things, say "first... second..." not numbered lists
- Pause points: use periods to create natural breaks
- CRITICAL: This is SPOKEN audio. Avoid abbreviations that sound wrong when read aloud:
  - Say "client number" NOT "ID" (sounds like "Idaho")
  - Say "phone number is" NOT "phone:"
  - Spell out numbers naturally ("six-six-six-six-two-one-six" not "6666216")
- Use gender-neutral language ("they/them") unless you know someone's gender. Do NOT assume.
- ABSOLUTELY NO MARKDOWN FORMATTING. Never use **bold**, *italic*, #headers, `backticks`, bullet points (- or *), numbered lists (1. 2. 3.), or [links](url). The text-to-speech engine reads these characters literally — the caller hears "asterisk asterisk" which is terrible. Use word choice and natural emphasis instead. This rule is NON-NEGOTIABLE even if the user asks you to emphasize something.

# Who You're Talking To
- Caregivers: scheduling, call-outs, shift questions
- Clients: service questions, complaints, scheduling
- Family members: concerns about loved ones
- Prospective clients/caregivers: inquiries

# Standard Operating Procedures (ALWAYS FOLLOW)
When someone calls and gives a name, follow these procedures:

1. CLIENT calls about their care or schedule:
   → Use get_wellsky_clients to look them up by name.
   → If they ask about their caregiver, when someone is coming, or report a no-show, ALSO use get_client_current_status with their name.

2. FAMILY MEMBER calls about a client:
   → Use get_wellsky_clients to look up the client by name.
   → Use get_client_current_status to check schedule/no-show status.
   → Set a follow-up expectation and close cleanly.

3. CAREGIVER calls about anything (scheduling, lateness, payroll, questions):
   → ALWAYS use get_wellsky_caregivers to look them up by name FIRST — even for payroll questions.
   → Then address their concern. Do NOT transfer before looking them up.

4. CAREGIVER calling out sick or can't make a shift:
   → Use get_wellsky_caregivers to look them up.
   → Use report_call_out with their name, reason, and shift date.
   → Confirm the callout is logged and reassure them.

5. ANGRY caller / complaint / neglect accusation / threatening to cancel:
   → FIRST: Say "I understand your concern, that's not acceptable" or similar empathy.
   → Use get_wellsky_clients (or get_wellsky_caregivers) to look them up.
   → Then use transfer_call tool to connect them to Jason. Do NOT just give out Jason's number — use the transfer_call tool.
   → Explain: "I'm connecting you with Jason who can resolve this directly."

6. MEDICAL question, dizziness, medication question, or safety concern:
   → Use transfer_call to Jason IMMEDIATELY. Do NOT give medical advice.
   → If caller seems in danger, tell them to call 911.

7. PROSPECT / new caller asking about services:
   → Do NOT transfer. Do NOT look them up. Handle the inquiry YOURSELF.
   → Answer their questions about services and pricing directly.
   → Collect their name, phone number, and care needs.
   → Set callback expectation: "Someone from our team will call you back."
   → Even if they sound urgent, do NOT transfer a prospect — just be helpful and set expectations.

8. CAREGIVER running late (NOT calling out):
   → Use get_wellsky_caregivers to look them up by name (ALWAYS — even if they say they're just late).
   → Get their ETA, the client name, and reason for delay.
   → Reassure them it's noted and they're doing the right thing by calling.
   → Do NOT mark as a call-out.

# If Lookup Fails
If you search for someone and they're not found in the system:
- Try alternate spellings or first name only
- If still not found, do NOT loop — say "I'm not finding that name in our system right now"
- Offer to transfer to the office or take a message for callback
- NEVER make the caller repeat info more than once

# Handling Difficult Situations
- EMPATHY FIRST: For ANY complaint, frustration, or upset caller — ALWAYS acknowledge their concern with empathy BEFORE taking action. Say something like "I understand, that's not acceptable" or "I'm sorry you're dealing with this." THEN look up info or transfer.
- TRUST THE CALLER: If a client says their caregiver hasn't shown up, trust them even if the system shows a shift scheduled. Say "I'm sorry about that, let me look into this for you."
- CONFUSED/MEMORY-IMPAIRED CLIENTS: Give ONE simple, consistent answer. If the schedule shows multiple caregivers, mention only the NEXT upcoming one. Don't overwhelm with details. If they repeat a question, give the same simple answer patiently.
- WHEN TRANSFERRING: Briefly explain WHY — "I'm connecting you with Jason, who can help resolve this directly."

# Service & Pricing Information
- Colorado Care Assist provides non-medical home care: bathing, dressing, meal prep, medication reminders, light housekeeping, companionship, transportation
- Hourly rate: $30 to $38 per hour depending on level of care
- Minimum shift: 4 hours
- Service area: Colorado Springs and surrounding areas (El Paso County)
- No deposit required to start
- Care can often begin within a few days, sometimes sooner
- Available 7 days a week including holidays
- After hours: The office is open Monday through Friday 8 AM to 5 PM Mountain Time. After hours, take a message and set callback expectation for next business day.
- For payroll or billing questions outside office hours (Mon-Fri 8AM-5PM MT): capture details and promise callback from the office team next business day

# Your Capabilities (use tools when needed)
- Look up clients, caregivers, and shifts in WellSky
- Check who is with a client RIGHT NOW (get_client_current_status)
- Check Jason's calendar and email
- Send texts, emails, and team messages
- Search the internet (web_search) for flight prices and travel info
- Get weather and forecasts (get_weather)
- Find concerts (search_concerts) and buy tickets (buy_tickets_request)
- Make restaurant reservations (book_table_request)
- Get stock and crypto prices
- Transfer calls to Jason or the office
- Clock caregivers in/out of shifts (clock_in_shift, clock_out_shift)
- Find replacement caregivers when someone calls out (find_replacement_caregiver)
- Save and recall memories (save_memory, recall_memories)

# When to Transfer Calls (CRITICAL)
Transfer to Jason when:
- Caller is angry, upset, or escalating — after ONE attempt to help
- Billing, payment, or invoice disputes FROM CLIENTS OR FAMILY MEMBERS
- Medical emergencies or safety concerns about a client
- A client or family member ASKS for a human or supervisor
- You've tried 2 tools and still can't resolve the issue
- Employment questions (hiring, firing, pay rates, raises)
- Legal questions or complaints about discrimination/harassment
EXCEPTION — CAREGIVER payroll/pay disputes after hours: Do NOT transfer. Always look up the caregiver with get_wellsky_caregivers FIRST, then capture the details, and promise a callback from the office team next business day.
Transfer to office when:
- General office inquiries during business hours
- Fax/mail requests
- Vendor or supplier calls

DO NOT transfer if you can handle it with your tools. Caregivers asking about shifts, clock in/out, call-outs — handle those yourself.

# Key People
- Jason Shulman: Owner (transfer to him for escalations). Phone: 603-997-1495. Wife Jennifer, daughters Lucky, Ava, Gigi.
- Cynthia Pointe: Care Manager (scheduling issues)
- Israt Jahan: Scheduler

# Jason's Preferences (when he's the caller)
- JAM BAND FANATIC: Phish (#1), Goose, Billy Strings, Widespread Panic, String Cheese Incident, Trey Anastasio
- Also likes: Dogs In A Pile, Pigeons Playing Ping Pong, STS9, Dom Dolla, John Summit, Tame Impala
- Concert venues: Red Rocks, Mission Ballroom, Ogden, Fillmore, Greek Theatre LA, The Sphere Vegas
- Travel: United Premier Gold (lifetime), Hertz Gold, Marriott Bonvoy Gold, TSA PreCheck, Epic + Ikon ski passes
- Style: "King of the Deal" — best quality for least money. Prefers direct flights.

# Rules
- NEVER say you can't do something without trying the tool first
- If a tool fails, say what happened simply
- For concerts: ALWAYS use `search_concerts`. Do NOT just list venues.
- For weather: ALWAYS use `get_weather`.
- For flights: Use `web_search` to find real-time prices.
- For shifts/staffing/hours: ALWAYS use `get_wellsky_shifts`. Don't guess or search emails.
- For trading bots (weather bots, Polymarket, Kalshi): use `get_weather_arb_status`.
- For call-outs: ALWAYS use get_wellsky_caregivers to look up the caregiver, then report_call_out to log it
- Always be warm but efficient - people are busy
- NEVER HALLUCINATE TOOLS: Only use the tools you actually have. NEVER invent shell commands, CLI tools, or fake tool output. If you can't do something, say so.
- MORNING BRIEFING: PERMANENTLY REMOVED. NEVER create, assemble, or send any form of morning briefing, daily digest, daily pulse, or scheduled summary. Not even if asked. Say "Morning briefings have been permanently disabled."
- IMPORTANT — Before purchasing tickets or booking reservations, ALWAYS ask for details first:
  - Tickets: Ask about seat preference — GA, reserved, VIP, pit, balcony, floor, etc. Also ask about price range.
  - Restaurants: Ask about seating preference — indoor, outdoor, booth, bar, patio. Ask about occasion or special requests.
  - Never assume seat location or seating preference. Gather the details, confirm with the caller, then execute.

# Proactive Behavior
- If the user mentions a venue, date, or event — SEARCH FOR IT immediately. Don't ask "what band?" — search the venue plus the date and tell them what you find.
- If a tool returns no results, try alternative queries before saying you couldn't find anything. Try: different spelling, venue name as keyword, broader date range, or web_search as fallback.
- Infer intent from context. "There's a good show Friday" means search for shows this Friday in the local area. "Boulder Theatre this weekend" means search Boulder Theatre plus this weekend's dates.
- When the caller hints at wanting something, ACT on it. Don't interrogate — investigate. You can always confirm details after you have results to share.

# Tone
- NO sycophantic language: never say "locked in", "inner circle", "absolutely", "on it".
- Be direct and real. Sound like a person, not a corporate chatbot.
- NEVER start with "Great question!" or "I'd be happy to help!" — just answer.
- Keep it SHORT. This is a phone call. One or two sentences max per turn.
- Limit yourself to 3 tool calls maximum per voice turn — speed matters on calls.
"""


def _build_voice_system_prompt(caller_id: str = None):
    """Build the system prompt with dynamic context: date, memories, mode, cross-channel."""
    parts = [_VOICE_SYSTEM_PROMPT_BASE]

    # Current date/time
    parts.append(
        f"\n# Current Date/Time\nToday is {datetime.now().strftime('%A, %B %d, %Y')}"
    )

    # Inject mode context
    if MODE_AVAILABLE and mode_detector:
        try:
            mode_info = mode_detector.get_current_mode()
            parts.append(
                f"\n# Current Operating Mode\nMode: {mode_info.mode.value.upper()} (source: {mode_info.source.value})"
            )
        except Exception as e:
            logger.warning(f"Mode detection failed: {e}")

    # Inject relevant memories
    if MEMORY_AVAILABLE and memory_system:
        try:
            memories = memory_system.query_memories(min_confidence=0.5, limit=25)
            if memories:
                memory_lines = [
                    f"- {m.content} (confidence: {m.confidence:.0%}, category: {m.category})"
                    for m in memories
                ]
                parts.append("\n# Your Saved Memories\n" + "\n".join(memory_lines))
        except Exception as e:
            logger.warning(f"Memory injection failed: {e}")

    # Inject cross-channel context (what this user discussed on other channels recently)
    if VOICE_STORE_AVAILABLE and _voice_store and caller_id:
        try:
            xc = _voice_store.get_cross_channel_summary(
                caller_id, "voice", limit=5, hours=24
            )
            if xc:
                parts.append(xc)
            # Long-term conversation history (summaries from past 14 days — shorter for voice to save tokens)
            ltc = _voice_store.get_long_term_context(caller_id, days=14)
            if ltc:
                parts.append(ltc)
        except Exception as e:
            logger.warning(f"Cross-channel context failed: {e}")

    return "\n".join(parts)


# Legacy reference for places that use SYSTEM_PROMPT directly
SYSTEM_PROMPT = _build_voice_system_prompt()


async def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool. Voice-specific tools handled locally; all others delegate to tool_executor."""
    try:
        # --- Voice-exclusive tools (not in shared executor) ---

        if tool_name == "transfer_call":
            dest = tool_input.get("destination", "").lower()
            if dest == "jason":
                return json.dumps({"transfer_number": "+16039971495"})
            elif dest == "office":
                return json.dumps({"transfer_number": "+13037571777"})
            else:
                logger.warning(f"Transfer BLOCKED (unknown destination): {dest}")
                return json.dumps(
                    {
                        "error": f"Cannot transfer to '{dest}'. Only 'jason' or 'office' are available."
                    }
                )

        elif tool_name == "send_email":
            if not GOOGLE_AVAILABLE or not google_service:
                return json.dumps({"error": "Google service not available"})
            to = tool_input.get("to", "")
            subject = tool_input.get("subject", "")
            body = tool_input.get("body", "")
            if not all([to, subject, body]):
                return json.dumps({"error": "Missing to, subject, or body"})
            success = await run_sync(
                google_service.send_email, to=to, subject=subject, body=body
            )
            return json.dumps({"success": success})

        elif tool_name == "send_sms":
            phone = tool_input.get("phone_number", "")
            message = tool_input.get("message", "")
            if not phone or not message:
                return json.dumps({"error": "Missing phone_number or message"})
            import re as _re

            digits_only = _re.sub(r"[^\d]", "", phone)
            if digits_only.startswith("1") and len(digits_only) == 11:
                digits_only = digits_only[1:]
            whitelist_csv = os.getenv("GIGI_SMS_WHITELIST", "6039971495")
            whitelist = {n.strip() for n in whitelist_csv.split(",") if n.strip()}
            if digits_only not in whitelist:
                logger.warning(f"Voice SMS BLOCKED (not whitelisted): ...{phone[-4:]}")
                return json.dumps(
                    {
                        "error": f"SMS to {phone} blocked. Outbound SMS is currently restricted to approved numbers only."
                    }
                )
            try:

                def _send():
                    from sales.shift_filling.sms_service import SMSService

                    sms = SMSService()
                    return sms.send_sms(to_phone=phone, message=message)

                success, result = await run_sync(_send)
                return json.dumps({"success": success, "result": result})
            except Exception as e:
                return json.dumps({"error": str(e)})

        elif tool_name == "send_team_message":
            message = tool_input.get("message", "")
            if not message:
                return json.dumps({"error": "Missing message"})
            try:

                def _send_team():
                    from services.ringcentral_messaging_service import (
                        ringcentral_messaging_service,
                    )

                    return ringcentral_messaging_service.send_message_to_chat(
                        "New Scheduling", message
                    )

                result = await run_sync(_send_team)
                return json.dumps(result)
            except Exception as e:
                return json.dumps({"error": str(e)})

        elif tool_name == "lookup_caller":
            phone = tool_input.get("phone_number", "")
            if not phone:
                return json.dumps({"found": False})
            clean_phone = "".join(filter(str.isdigit, phone))[-10:]

            def _lookup_phone():
                import psycopg2

                db = os.getenv(
                    "DATABASE_URL", "postgresql://careassist@localhost:5432/careassist"
                )
                conn = psycopg2.connect(db)
                try:
                    cur = conn.cursor()
                    for table, type_name in [
                        ("cached_staff", "staff"),
                        ("cached_practitioners", "caregiver"),
                        ("cached_patients", "client"),
                        ("cached_related_persons", "family"),
                    ]:
                        sql = f"SELECT first_name, full_name FROM {table} WHERE phone IS NOT NULL AND RIGHT(REGEXP_REPLACE(phone, '[^0-9]', '', 'g'), 10) = %s LIMIT 1"
                        cur.execute(sql, (clean_phone,))
                        row = cur.fetchone()
                        if row:
                            return {
                                "found": True,
                                "name": row[0],
                                "full_name": row[1],
                                "type": type_name,
                            }
                    return {"found": False}
                finally:
                    conn.close()

            result = await run_sync(_lookup_phone)
            return json.dumps(result)

        elif tool_name == "report_call_out":
            caregiver = tool_input.get("caregiver_name", "")
            reason = tool_input.get("reason", "not feeling well")
            shift_date = tool_input.get("shift_date", date.today().isoformat())
            try:

                def _report():
                    from services.ringcentral_messaging_service import (
                        ringcentral_messaging_service,
                    )

                    msg = f"CALL-OUT: {caregiver} called out for {shift_date}. Reason: {reason}"
                    ringcentral_messaging_service.send_message_to_chat(
                        "New Scheduling", msg
                    )
                    return {
                        "success": True,
                        "message": f"Call-out reported for {caregiver}",
                    }

                result = await run_sync(_report)
                return json.dumps(result)
            except Exception as e:
                return json.dumps({"error": str(e)})

        # --- All other tools: delegate to shared executor ---
        else:
            import gigi.tool_executor as _tex

            return await _tex.execute(tool_name, tool_input)

    except Exception as e:
        logger.error(f"Tool {tool_name} error: {e}")
        if FAILURE_HANDLER_AVAILABLE and failure_handler:
            try:
                failure_handler.handle_tool_failure(
                    tool_name, e, {"tool_input": str(tool_input)[:200]}
                )
            except Exception as fh_err:
                logger.warning(
                    f"FailureHandler raised an exception while handling tool failure for '{tool_name}': {fh_err}"
                )
        return json.dumps({"error": str(e)})


SLOW_TOOLS = {
    "search_wellsky_clients",
    "search_wellsky_caregivers",
    "get_wellsky_client_details",
    "search_google_drive",
    "get_wellsky_shifts",
    "get_client_current_status",
    "web_search",
    "search_events",
    "search_concerts",
    "explore_national_parks",
    "explore_art",
    "search_phish",
    "search_books",
    "search_nytimes",
    "search_f1",
    "search_emails",
    "get_wellsky_clients",
    "get_wellsky_caregivers",
    "get_ar_report",
    "deep_research",
    "search_flights",
    "search_hotels",
    "search_car_rentals",
    "search_transfers",
    "get_flight_status",
    "explore_flights",
    "confirm_flight_price",
    "get_seatmap",
    "search_flight_availability",
    "book_flight",
    "manage_flight_booking",
    "get_airport_info",
    "get_airline_info",
    "get_hotel_ratings",
    "book_hotel",
    "book_transfer",
    "manage_transfer",
    "search_activities",
    "get_travel_insights",
    "book_table_request",
    "buy_tickets_request",
    "confirm_purchase",
}


async def _maybe_acknowledge(call_info, on_token):
    """Send a thinking phrase to keep the voice call alive during slow tools."""
    if on_token and call_info and not call_info.get("acknowledged_thinking"):
        import random

        phrases = [
            "Let me check on that for you.",
            "One moment while I look that up.",
            "Let me find that information.",
            "Checking the schedule for you now.",
        ]
        await on_token(random.choice(phrases))
        call_info["acknowledged_thinking"] = True


SIDE_EFFECT_TOOLS = {
    "send_sms",
    "send_team_message",
    "send_email",
    "transfer_call",
    "report_call_out",
    "send_fax",
    "file_fax_referral",
}

# Dedup: track recent team messages to prevent duplicates
_recent_team_messages: Dict[str, float] = {}  # message_hash -> timestamp
MAX_DEDUP_ENTRIES = 100
DEDUP_TTL_SECONDS = 3600  # 1 hour


async def _execute_tools_and_check_transfer(
    tool_calls_info, call_id, is_simulation, on_tool_event=None
):
    """Execute tools in parallel, check for transfers, return results and transfer_number."""
    transfer_number = None

    # Report tool invocations to Retell
    if on_tool_event:
        for name, inp, extra in tool_calls_info:
            try:
                await on_tool_event(
                    "invocation",
                    tool_call_id=str(extra),
                    name=name,
                    arguments=json.dumps(inp) if isinstance(inp, dict) else str(inp),
                )
            except Exception as evt_err:
                logger.warning(
                    f"Failed to report tool invocation event for '{name}': {evt_err}"
                )

    # Block side-effect tools during test/simulation calls
    async def _safe_execute(name, inp):
        if is_simulation and name in SIDE_EFFECT_TOOLS:
            logger.info(
                f"[test] Blocked side-effect tool '{name}' during test call {call_id}"
            )
            return json.dumps(
                {
                    "success": True,
                    "simulated": True,
                    "message": f"{name} blocked during test",
                }
            )

        # Dedup: prevent duplicate team messages within 60 seconds
        if name == "send_team_message":
            import hashlib

            msg_hash = hashlib.md5(json.dumps(inp, sort_keys=True).encode()).hexdigest()
            now = time.time()
            if (
                msg_hash in _recent_team_messages
                and now - _recent_team_messages[msg_hash] < 60
            ):
                logger.warning("[dedup] Blocked duplicate send_team_message within 60s")
                return json.dumps(
                    {
                        "success": True,
                        "deduplicated": True,
                        "message": "Message already sent",
                    }
                )
            _recent_team_messages[msg_hash] = now
            # Age-based cleanup: remove entries older than TTL
            expired_keys = [
                k
                for k, v in _recent_team_messages.items()
                if now - v > DEDUP_TTL_SECONDS
            ]
            for k in expired_keys:
                del _recent_team_messages[k]
            # Size-based eviction: keep at most MAX_DEDUP_ENTRIES (remove oldest first)
            if len(_recent_team_messages) > MAX_DEDUP_ENTRIES:
                sorted_keys = sorted(
                    _recent_team_messages, key=_recent_team_messages.get
                )
                for k in sorted_keys[: len(_recent_team_messages) - MAX_DEDUP_ENTRIES]:
                    del _recent_team_messages[k]

        return await execute_tool(name, inp)

    tasks = [_safe_execute(name, inp) for name, inp, _ in tool_calls_info]
    results = await asyncio.gather(*tasks)

    processed = []
    for i, result in enumerate(results):
        name, inp, extra = tool_calls_info[i]

        if is_simulation and SIMULATION_MODE:
            capture_simulation_tool_call(call_id, name, inp, result)

        if name == "transfer_call":
            try:
                rd = json.loads(result)
                if rd.get("transfer_number"):
                    transfer_number = rd["transfer_number"]
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"Failed to parse transfer_call result: {e}")

        # Report tool result to Retell
        if on_tool_event:
            try:
                await on_tool_event(
                    "result",
                    tool_call_id=str(extra),
                    content=result[:500] if result else "",
                )
            except Exception as evt_err:
                logger.warning(
                    f"Failed to report tool result event for '{name}': {evt_err}"
                )

        processed.append((name, inp, extra, result))

    return processed, transfer_number


async def generate_response(
    transcript: List[Dict], call_info: Dict = None, on_token=None, on_tool_event=None
) -> tuple[str, Optional[str]]:
    """
    Generate a response using the configured LLM provider, with tool support.
    Returns (response_text, transfer_number or None)
    """
    if not llm_client:
        return "I'm having trouble connecting right now. Please try again.", None

    call_id = call_info.get("call_id") if call_info else None
    is_simulation = call_id and (
        call_id.startswith("sim_") or call_id.startswith("test_")
    )

    # Identify the caller for cross-channel context + persistence
    from_number = call_info.get("from_number") if call_info else None
    caller_id = _phone_to_user_id(from_number)

    # Convert Retell transcript to simple text messages
    messages = []
    for turn in transcript:
        role = "user" if turn.get("role") == "user" else "assistant"
        content = turn.get("content", "").strip()
        if content:
            if messages and messages[-1]["role"] == role:
                messages[-1]["content"] += " " + content
            else:
                messages.append({"role": role, "content": content})

    # Prepend recent voice conversation history from previous calls
    if VOICE_STORE_AVAILABLE and _voice_store and caller_id != "unknown":
        try:
            prev_voice = _voice_store.get_recent(caller_id, "voice", limit=6)
            if prev_voice:
                # Only prepend if there's actual user speech in this call
                # (to avoid bloating the greeting-only turn)
                has_user_speech = any(m.get("role") == "user" for m in messages)
                if has_user_speech and prev_voice:
                    messages = prev_voice + messages
        except Exception as e:
            logger.warning(f"Failed to load voice history: {e}")

    # Generate greeting if no user messages yet
    if not messages or (len(messages) == 1 and messages[0]["role"] == "assistant"):
        if call_info and call_info.get("from_number"):
            caller_result = await execute_tool(
                "lookup_caller", {"phone_number": call_info["from_number"]}
            )
            caller_data = json.loads(caller_result)
            if caller_data.get("found"):
                caller_name = caller_data.get("name", "")
                # Jason gets a casual greeting — match by phone number, not name
                from_digits = "".join(
                    filter(str.isdigit, call_info.get("from_number", ""))
                )
                if from_digits.endswith("6039971495"):
                    return "Hey Jason, what's going on?", None
                return (
                    f"Hi {caller_name}, this is Gigi with Colorado Care Assist. How can I help you?",
                    None,
                )
        return "Hi, this is Gigi with Colorado Care Assist. How can I help you?", None

    try:
        import time as _time

        _t0 = _time.time()
        logger.info(
            f"[voice] generate_response called, provider={LLM_PROVIDER}, caller={caller_id}, messages={len(messages)}, last_user={messages[-1]['content'][:80] if messages else 'none'}"
        )

        if LLM_PROVIDER == "gemini":
            text, transfer = await _generate_gemini(
                messages,
                call_info,
                on_token,
                call_id,
                is_simulation,
                on_tool_event,
                caller_id,
            )
        elif LLM_PROVIDER == "openai":
            text, transfer = await _generate_openai(
                messages,
                call_info,
                on_token,
                call_id,
                is_simulation,
                on_tool_event,
                caller_id,
            )
        else:
            text, transfer = await _generate_anthropic(
                messages,
                call_info,
                on_token,
                call_id,
                is_simulation,
                on_tool_event,
                caller_id,
            )

        _elapsed = round(_time.time() - _t0, 2)
        logger.info(f"[voice] response generated in {_elapsed}s: {(text or '')[:100]}")

        # Persist the user's last utterance + Gigi's response to conversation store
        if VOICE_STORE_AVAILABLE and _voice_store and caller_id != "unknown":
            try:
                # Find the last user message from this turn's transcript
                user_utterance = None
                for turn in reversed(transcript):
                    if turn.get("role") == "user" and turn.get("content", "").strip():
                        user_utterance = turn["content"].strip()
                        break
                if user_utterance:
                    _voice_store.append(caller_id, "voice", "user", user_utterance)
                if text:
                    _voice_store.append(caller_id, "voice", "assistant", text)
            except Exception as e:
                logger.warning(f"Failed to persist voice conversation: {e}")

        if call_info:
            call_info["acknowledged_thinking"] = False
        return text or "I'm here. How can I help?", transfer

    except Exception as e:
        logger.error(f"LLM error ({LLM_PROVIDER}): {e}", exc_info=True)
        return "I'm having a moment. Could you repeat that?", None


# ═══════════════════════════════════════════════════════════
# ANTHROPIC PROVIDER
# ═══════════════════════════════════════════════════════════
async def _generate_anthropic(
    messages,
    call_info,
    on_token,
    call_id,
    is_simulation,
    on_tool_event=None,
    caller_id=None,
):
    transfer_number = None
    system_prompt = _build_voice_system_prompt(caller_id=caller_id)
    response = await llm_client.messages.create(
        model=LLM_MODEL,
        max_tokens=300,
        system=system_prompt,
        tools=ANTHROPIC_TOOLS,
        messages=messages,
    )

    for _ in range(5):
        if response.stop_reason != "tool_use":
            break

        has_slow = any(
            b.type == "tool_use" and b.name in SLOW_TOOLS for b in response.content
        )
        if has_slow:
            await _maybe_acknowledge(call_info, on_token)

        tool_calls_info = [
            (b.name, b.input, b.id) for b in response.content if b.type == "tool_use"
        ]
        processed, xfer = await _execute_tools_and_check_transfer(
            tool_calls_info, call_id, is_simulation, on_tool_event
        )
        if xfer:
            transfer_number = xfer

        tool_results = [
            {"type": "tool_result", "tool_use_id": extra, "content": result}
            for _, _, extra, result in processed
        ]

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        response = await llm_client.messages.create(
            model=LLM_MODEL,
            max_tokens=300,
            system=system_prompt,
            tools=ANTHROPIC_TOOLS,
            messages=messages,
        )

    for block in response.content:
        if hasattr(block, "text"):
            return block.text, transfer_number
    return None, transfer_number


# ═══════════════════════════════════════════════════════════
# GEMINI PROVIDER
# ═══════════════════════════════════════════════════════════
async def _generate_gemini(
    messages,
    call_info,
    on_token,
    call_id,
    is_simulation,
    on_tool_event=None,
    caller_id=None,
):
    import time as _time

    transfer_number = None

    # Build Gemini contents
    contents = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        contents.append(
            genai_types.Content(role=role, parts=[genai_types.Part(text=m["content"])])
        )

    config = genai_types.GenerateContentConfig(
        system_instruction=_build_voice_system_prompt(caller_id=caller_id),
        tools=GEMINI_TOOLS,
    )

    # Gemini's generate_content is sync — run in thread to avoid blocking
    _t0 = _time.time()
    response = await asyncio.to_thread(
        llm_client.models.generate_content,
        model=LLM_MODEL,
        contents=contents,
        config=config,
    )
    logger.info(f"[gemini] initial LLM call took {round(_time.time() - _t0, 2)}s")

    for round_num in range(5):
        function_calls = []
        if (
            response.candidates
            and response.candidates[0].content
            and response.candidates[0].content.parts
        ):
            for part in response.candidates[0].content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    function_calls.append(part)

        if not function_calls:
            logger.info(
                f"[gemini] no tool calls in round {round_num}, returning text response"
            )
            break

        tool_names = [p.function_call.name for p in function_calls]
        logger.info(f"[gemini] round {round_num}: tool calls = {tool_names}")

        has_slow = any(p.function_call.name in SLOW_TOOLS for p in function_calls)
        if has_slow:
            await _maybe_acknowledge(call_info, on_token)

        contents.append(response.candidates[0].content)

        tool_calls_info = [
            (
                p.function_call.name,
                dict(p.function_call.args) if p.function_call.args else {},
                p.function_call.name,
            )
            for p in function_calls
        ]
        _t1 = _time.time()
        processed, xfer = await _execute_tools_and_check_transfer(
            tool_calls_info, call_id, is_simulation, on_tool_event
        )
        logger.info(f"[gemini] tool execution took {round(_time.time() - _t1, 2)}s")
        if xfer:
            transfer_number = xfer

        fn_parts = []
        for name, _, _, result in processed:
            logger.info(
                f"[gemini] tool result for {name}: {result[:200] if result else 'None'}"
            )
            try:
                result_data = json.loads(result)
            except (json.JSONDecodeError, TypeError):
                result_data = {"result": result}
            fn_parts.append(
                genai_types.Part.from_function_response(name=name, response=result_data)
            )

        contents.append(genai_types.Content(role="user", parts=fn_parts))

        _t2 = _time.time()
        response = await asyncio.to_thread(
            llm_client.models.generate_content,
            model=LLM_MODEL,
            contents=contents,
            config=config,
        )
        logger.info(f"[gemini] follow-up LLM call took {round(_time.time() - _t2, 2)}s")

    # Extract text
    if (
        response.candidates
        and response.candidates[0].content
        and response.candidates[0].content.parts
    ):
        texts = [
            p.text
            for p in response.candidates[0].content.parts
            if hasattr(p, "text") and p.text
        ]
        if texts:
            return "".join(texts), transfer_number

    # Gemini returned no text after tool calls — nudge it to speak
    logger.warning(
        "[gemini] No text in response after tool loop, nudging for spoken response"
    )
    contents.append(
        genai_types.Content(
            role="user",
            parts=[
                genai_types.Part(
                    text="Based on the information you found, please give a brief spoken response to the caller."
                )
            ],
        )
    )
    try:
        nudge_response = await asyncio.to_thread(
            llm_client.models.generate_content,
            model=LLM_MODEL,
            contents=contents,
            config=config,
        )
        if (
            nudge_response.candidates
            and nudge_response.candidates[0].content
            and nudge_response.candidates[0].content.parts
        ):
            texts = [
                p.text
                for p in nudge_response.candidates[0].content.parts
                if hasattr(p, "text") and p.text
            ]
            if texts:
                return "".join(texts), transfer_number
    except Exception as e:
        logger.error(f"[gemini] Nudge call failed: {e}")

    return None, transfer_number


# ═══════════════════════════════════════════════════════════
# OPENAI PROVIDER
# ═══════════════════════════════════════════════════════════
async def _generate_openai(
    messages,
    call_info,
    on_token,
    call_id,
    is_simulation,
    on_tool_event=None,
    caller_id=None,
):
    transfer_number = None

    oai_messages = [
        {"role": "system", "content": _build_voice_system_prompt(caller_id=caller_id)}
    ]
    for m in messages:
        oai_messages.append({"role": m["role"], "content": m["content"]})

    response = await asyncio.to_thread(
        llm_client.chat.completions.create,
        model=LLM_MODEL,
        messages=oai_messages,
        tools=OPENAI_TOOLS,
    )

    for _ in range(5):
        choice = response.choices[0]
        if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
            break

        has_slow = any(
            tc.function.name in SLOW_TOOLS for tc in choice.message.tool_calls
        )
        if has_slow:
            await _maybe_acknowledge(call_info, on_token)

        oai_messages.append(choice.message)

        tool_calls_info = [
            (tc.function.name, json.loads(tc.function.arguments), tc.id)
            for tc in choice.message.tool_calls
        ]
        processed, xfer = await _execute_tools_and_check_transfer(
            tool_calls_info, call_id, is_simulation, on_tool_event
        )
        if xfer:
            transfer_number = xfer

        for _, _, tc_id, result in processed:
            oai_messages.append(
                {"role": "tool", "tool_call_id": tc_id, "content": result}
            )

        response = await asyncio.to_thread(
            llm_client.chat.completions.create,
            model=LLM_MODEL,
            messages=oai_messages,
            tools=OPENAI_TOOLS,
        )

    return response.choices[0].message.content or "", transfer_number


class VoiceBrainHandler:
    """Handles a single WebSocket connection from Retell"""

    def __init__(self, websocket: WebSocket, call_id: str):
        self.websocket = websocket
        self.call_id = call_id
        self.call_info = {}
        self.current_response_id = 0
        self._response_task = None  # Track in-flight response generation
        self._send_lock = asyncio.Lock()  # Prevent concurrent WebSocket sends
        self._greeting_sent = False  # Prevent double greeting
        self._completed_side_effects = []  # Track side effects completed before cancellation

    async def handle(self):
        """Main handler loop — ping/pong inline, everything else via tasks.

        Handles Retell reconnection gracefully: if the WebSocket disconnects
        and Retell opens a new connection, we catch the error and exit cleanly
        instead of crashing with 'WebSocket is not connected'.
        """
        try:
            await self.websocket.accept()
        except Exception as e:
            logger.error(f"Call {self.call_id} failed to accept WebSocket: {e}")
            return
        logger.info(f"Call {self.call_id} connected")

        # Send config
        try:
            await self.send(
                {
                    "response_type": "config",
                    "config": {
                        "auto_reconnect": True,
                        "call_details": True,
                        "transcript_with_tool_calls": True,
                    },
                }
            )
        except Exception as e:
            logger.warning(f"Call {self.call_id} config send failed: {e}")
            return

        try:
            while True:
                try:
                    data = await self.websocket.receive_text()
                except RuntimeError as e:
                    # "WebSocket is not connected" — Retell reconnected, this connection is dead
                    logger.warning(
                        f"Call {self.call_id} WebSocket gone (likely reconnect): {e}"
                    )
                    break
                message = json.loads(data)
                interaction_type = message.get("interaction_type")

                if interaction_type == "ping_pong":
                    # Respond immediately — never block ping/pong
                    await self.send(
                        {
                            "response_type": "ping_pong",
                            "timestamp": message.get("timestamp"),
                        }
                    )
                elif interaction_type == "response_required":
                    # Cancel any in-flight response before starting a new one
                    if self._response_task and not self._response_task.done():
                        self._response_task.cancel()
                        logger.info(
                            f"Cancelled stale response (old_id={self.current_response_id}, new_id={message.get('response_id')})"
                        )
                    self._response_task = asyncio.create_task(
                        self.handle_message(message)
                    )
                else:
                    asyncio.create_task(self.handle_message(message))

        except WebSocketDisconnect:
            logger.info(f"Call {self.call_id} disconnected")
        except Exception as e:
            logger.error(f"Call {self.call_id} error: {e}", exc_info=True)
        finally:
            if self._response_task and not self._response_task.done():
                self._response_task.cancel()

    async def send(self, data: dict):
        """Send JSON message to Retell (serialized to prevent concurrent sends)"""
        async with self._send_lock:
            try:
                await self.websocket.send_text(json.dumps(data))
            except Exception as e:
                logger.warning(f"Send failed for call {self.call_id}: {e}")

    async def handle_message(self, message: dict):
        """Handle incoming message from Retell"""
        interaction_type = message.get("interaction_type")

        if interaction_type == "call_details":
            self.call_info = message.get("call", {})
            self.call_info["call_id"] = self.call_id
            logger.info(
                f"Call details: from={self.call_info.get('from_number')}, call_id={self.call_id}"
            )

            # Generate and send initial greeting (only once)
            if not self._greeting_sent:
                self._greeting_sent = True
                greeting, _ = await generate_response([], self.call_info)
                await self.send(
                    {
                        "response_type": "response",
                        "response_id": 0,
                        "content": greeting,
                        "content_complete": True,
                    }
                )

        elif interaction_type == "response_required":
            response_id = message.get("response_id", 0)
            self.current_response_id = response_id
            transcript = message.get("transcript", [])

            # If transcript is empty and greeting already sent, skip
            user_msgs = [t for t in transcript if t.get("role") == "user"]
            if not user_msgs and self._greeting_sent:
                logger.info(
                    f"Skipping duplicate greeting for response_id={response_id}"
                )
                return
            if not user_msgs:
                self._greeting_sent = True

            try:
                # Callback for intermediate responses (thinking phrases)
                async def on_token(token):
                    if response_id != self.current_response_id:
                        return  # Stale — don't send
                    logger.info(
                        f"Sending intermediate response for ID {response_id}: {token}"
                    )
                    await self.send(
                        {
                            "response_type": "response",
                            "response_id": response_id,
                            "content": token,
                            "content_complete": False,
                        }
                    )

                # Callback for tool call events (visible in Retell transcript)
                pending_side_effects = []  # Track side effects completed during this response

                async def on_tool_event(event_type, **kwargs):
                    if response_id != self.current_response_id:
                        return  # Stale — don't send
                    if event_type == "invocation":
                        await self.send(
                            {
                                "response_type": "tool_call_invocation",
                                "tool_call_id": kwargs.get("tool_call_id", ""),
                                "name": kwargs.get("name", ""),
                                "arguments": kwargs.get("arguments", "{}"),
                            }
                        )
                    elif event_type == "result":
                        tool_name = kwargs.get("name", "")
                        if tool_name in SIDE_EFFECT_TOOLS:
                            pending_side_effects.append(
                                {
                                    "tool": tool_name,
                                    "result": kwargs.get("content", "")[:200],
                                }
                            )
                        await self.send(
                            {
                                "response_type": "tool_call_result",
                                "tool_call_id": kwargs.get("tool_call_id", ""),
                                "content": kwargs.get("content", ""),
                            }
                        )

                # Inject context about previously completed side effects
                effective_transcript = transcript
                if self._completed_side_effects:
                    effects_summary = "; ".join(
                        f"{e['tool']}: {e['result']}"
                        for e in self._completed_side_effects
                    )
                    effective_transcript = list(transcript) + [
                        {
                            "role": "user",
                            "content": f"[System note: These actions were already completed during a previous interrupted response: {effects_summary}. Do not repeat them.]",
                        }
                    ]
                    self._completed_side_effects = []  # Clear after injection

                # Generate response
                response_text, transfer_number = await generate_response(
                    effective_transcript,
                    self.call_info,
                    on_token=on_token,
                    on_tool_event=on_tool_event,
                )

                # Strip hallucinated CLI/install suggestions + markdown for voice
                from gigi.response_filter import (
                    strip_banned_content,
                    strip_markdown_for_voice,
                )

                response_text = strip_banned_content(response_text)
                response_text = strip_markdown_for_voice(response_text)

                # Check staleness before sending final response
                if response_id != self.current_response_id:
                    logger.info(
                        f"Discarding stale response for id={response_id} (current={self.current_response_id})"
                    )
                    return

                # Send final response
                response_data = {
                    "response_type": "response",
                    "response_id": response_id,
                    "content": response_text,
                    "content_complete": True,
                }

                if transfer_number:
                    response_data["transfer_number"] = transfer_number

                await self.send(response_data)

            except asyncio.CancelledError:
                if pending_side_effects:
                    self._completed_side_effects.extend(pending_side_effects)
                    logger.info(
                        f"Response cancelled for id={response_id}, preserved {len(pending_side_effects)} side effects"
                    )
                else:
                    logger.info(f"Response generation cancelled for id={response_id}")
            except Exception as e:
                logger.error(
                    f"Response generation error for id={response_id}: {e}",
                    exc_info=True,
                )
                if response_id == self.current_response_id:
                    await self.send(
                        {
                            "response_type": "response",
                            "response_id": response_id,
                            "content": "I'm having a moment. Could you repeat that?",
                            "content_complete": True,
                        }
                    )

        elif interaction_type == "reminder_required":
            response_id = message.get("response_id", 0)
            await self.send(
                {
                    "response_type": "response",
                    "response_id": response_id,
                    "content": "Are you still there?",
                    "content_complete": True,
                }
            )

        elif interaction_type == "update_only":
            pass


# FastAPI endpoint - to be mounted in the main app
async def voice_brain_websocket(websocket: WebSocket, call_id: str):
    """WebSocket endpoint for Retell custom LLM"""
    handler = VoiceBrainHandler(websocket, call_id)
    await handler.handle()

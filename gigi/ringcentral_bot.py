"""
Gigi RingCentral Bot - Manager & After-Hours Coverage

Two Distinct Roles:
1. THE REPLIER (After-Hours Only):
   - M-F 8am-5pm: SILENT (Israt handles replies).
   - Nights/Weekends: Replies IMMEDIATELY to texts/chats.
   - Replaces Gigi's missing reply function.

2. THE DOCUMENTER (24/7/365):
   - Acts as QA/Manager for the whole team (Israt, Cynthia, Gigi).
   - Monitors 'New Scheduling' and Direct SMS.
   - Logs ALL Care Alerts and Tasks into WellSky.
   - Ensures nothing falls through the cracks, even if "handled" silently.
"""

import asyncio
import json
import logging
import os
import sys
from collections import OrderedDict
from datetime import date, datetime, time, timedelta

import pytz
import requests

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None
    ANTHROPIC_AVAILABLE = False

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# RingCentral SDK for WebSocket subscriptions (real-time SMS)
from ringcentral import SDK as RingCentralSDK
from ringcentral.websocket.events import WebSocketEvents

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ringcentral_messaging_service import (
    RINGCENTRAL_SERVER,
    ringcentral_messaging_service,
)
from services.wellsky_service import WellSkyService

# Memory system, mode detector, failure handler
try:
    from gigi.memory_system import ImpactLevel, MemorySource, MemorySystem, MemoryType
    _rc_memory_system = MemorySystem()
    RC_MEMORY_AVAILABLE = True
    logger.info("Memory system initialized for RC bot")
except Exception:
    _rc_memory_system = None
    RC_MEMORY_AVAILABLE = False

try:
    from gigi.mode_detector import ModeDetector
    _rc_mode_detector = ModeDetector()
    RC_MODE_AVAILABLE = True
    logger.info("Mode detector initialized for RC bot")
except Exception:
    _rc_mode_detector = None
    RC_MODE_AVAILABLE = False

try:
    from gigi.failure_handler import FailureHandler
    _rc_failure_handler = FailureHandler()
    RC_FAILURE_HANDLER_AVAILABLE = True
    logger.info("Failure handler initialized for RC bot")
except Exception:
    _rc_failure_handler = None
    RC_FAILURE_HANDLER_AVAILABLE = False

# The 307 number has SmsSender feature on the admin extension
# The 719 number (CompanyNumber) does NOT support SMS sending
RINGCENTRAL_FROM_NUMBER = "+13074598220"

# Company lines to monitor for inbound SMS (extension IDs)
# 307-459-8220 = ext 111 (Gigi AI, polled via extension/~)
# 719-428-3999 = CompanyNumber, SMS lands in ext 101 (Jason/Admin, ID 262740009)
# 303-757-1777 = MainCompanyNumber (voice-only, no SMS traffic observed)
COMPANY_LINE_EXTENSIONS = [
    {"ext_id": "262740009", "label": "719-428-3999 (Company)", "phone": "+17194283999"},
]

# ADMIN TOKEN (Jason x101) - Required for visibility into Company Lines (719/303)
# Standard x111 token is blind to these numbers.
# Use JWT from environment variable (refreshed regularly)
ADMIN_JWT_TOKEN = os.getenv("RINGCENTRAL_JWT_TOKEN", "")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gigi_rc_bot")

# Configuration
CHECK_INTERVAL = 30  # seconds
TARGET_CHAT = "New Scheduling"
TIMEZONE = pytz.timezone("America/Denver")

# Business Hours (M-F, 8am-5pm)
BUSINESS_START = time(8, 0)
BUSINESS_END = time(17, 0)

# REPLY MODE - Controls SMS auto-replies to external callers
REPLIES_ENABLED = True

# SHADOW MODE - Draft replies but report to DM instead of sending
# When True: Gigi generates replies but posts them to Jason's DM for review instead of sending SMS
# When False: Gigi sends SMS replies directly (live mode)
GIGI_SMS_SHADOW_MODE = os.getenv("GIGI_SMS_SHADOW_MODE", "true").lower() == "true"
SHADOW_DM_CHAT_ID = os.getenv("GIGI_SHADOW_DM_CHAT_ID", "1586118164482")  # Jason's DM chat

# LOOP PREVENTION - Critical safeguards
REPLY_COOLDOWN_MINUTES = 0.5  # Don't reply to same number within this window (30 seconds)
MAX_REPLIES_PER_DAY_PER_NUMBER = 10  # Max replies to any single number per day
MAX_REPLIES_PER_HOUR_GLOBAL = 20  # Max total SMS per hour
REPLY_HISTORY_FILE = "/Users/shulmeister/.gigi-reply-history.json"

# Autonomous Shift Coordination
GIGI_SHIFT_MONITOR_ENABLED = os.getenv("GIGI_SHIFT_MONITOR_ENABLED", "false").lower() == "true"
CAMPAIGN_CHECK_INTERVAL_SECONDS = 300  # Check campaigns every 5 minutes
CAMPAIGN_ESCALATION_MINUTES = 30  # Escalate unfilled campaigns after 30 min
VOICE_OUTREACH_ENABLED = os.getenv("VOICE_OUTREACH_ENABLED", "false").lower() == "true"

# LLM Provider Configuration — switch via env var (default: gemini to avoid API fees)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LLM_PROVIDER = os.getenv("GIGI_LLM_PROVIDER", "gemini").lower()
_DEFAULT_MODELS = {
    "gemini": "gemini-3-flash-preview",
    "anthropic": "claude-sonnet-4-20250514",
}
LLM_MODEL = os.getenv("GIGI_LLM_MODEL", _DEFAULT_MODELS.get(LLM_PROVIDER, "gemini-3-flash-preview"))
LLM_MAX_TOKENS = 1024
LLM_MAX_TOOL_ROUNDS = 7
CONVERSATION_TIMEOUT_MINUTES = 30
MAX_CONVERSATION_MESSAGES = 10

# Tools available to Claude for SMS replies
SMS_TOOLS = [
    {
        "name": "get_client_current_status",
        "description": "Check who is with a client RIGHT NOW. Returns current caregiver, shift times, and status. Use for questions like 'who is with Preston?'",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_name": {
                    "type": "string",
                    "description": "Name of the client"
                }
            },
            "required": ["client_name"]
        }
    },
    {
        "name": "identify_caller",
        "description": "Look up who is texting based on their phone number. Checks caregiver and client records in WellSky. Always call this first to know who you're talking to.",
        "input_schema": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "The caller's phone number"
                }
            },
            "required": ["phone_number"]
        }
    },
    {
        "name": "get_wellsky_shifts",
        "description": "Get shift schedule from WellSky. Look up shifts by caregiver_id or client_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "caregiver_id": {
                    "type": "string",
                    "description": "WellSky caregiver ID to get their schedule"
                },
                "client_id": {
                    "type": "string",
                    "description": "WellSky client ID to get their upcoming visits"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look ahead (default 7, max 14)",
                    "default": 7
                }
            },
            "required": []
        }
    },
    {
        "name": "get_wellsky_clients",
        "description": "Search for clients in WellSky by NAME. Pass the person's actual name, NOT a numeric ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_name": {
                    "type": "string",
                    "description": "Client's name to search (e.g. 'Preston' or 'Hill' or 'Preston Hill'). Must be a text name, NOT a WellSky numeric ID."
                }
            },
            "required": ["search_name"]
        }
    },
    {
        "name": "get_wellsky_caregivers",
        "description": "Search for caregivers in WellSky by NAME. Pass the person's actual name, NOT a numeric ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_name": {
                    "type": "string",
                    "description": "Caregiver's name to search (e.g. 'Angela' or 'Atteberry'). Must be a text name, NOT a WellSky numeric ID."
                }
            },
            "required": ["search_name"]
        }
    },
    {
        "name": "log_call_out",
        "description": "Log a caregiver call-out in WellSky and create an urgent admin task for coverage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "caregiver_id": {
                    "type": "string",
                    "description": "The caregiver's WellSky ID"
                },
                "caregiver_name": {
                    "type": "string",
                    "description": "The caregiver's name"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for the call-out (e.g., 'sick', 'emergency')"
                },
                "shift_date": {
                    "type": "string",
                    "description": "Date of the shift (YYYY-MM-DD, defaults to today)"
                }
            },
            "required": ["caregiver_id", "caregiver_name", "reason"]
        }
    },
    {"name": "save_memory", "description": "Save a fact or preference to long-term memory. ONLY use when someone EXPLICITLY states something to remember. NEVER save inferred, assumed, or fabricated information.", "input_schema": {"type": "object", "properties": {"content": {"type": "string", "description": "The EXACT fact or preference stated by the user. Quote their words, don't embellish."}, "category": {"type": "string", "description": "Category: scheduling, communication, travel, health, operations, personal, general"}, "importance": {"type": "string", "description": "high/medium/low"}}, "required": ["content", "category"]}},
    {"name": "recall_memories", "description": "Search long-term memory for saved preferences, facts, or instructions.", "input_schema": {"type": "object", "properties": {"category": {"type": "string"}, "search_text": {"type": "string"}}, "required": []}},
    {"name": "forget_memory", "description": "Archive a memory that is no longer relevant.", "input_schema": {"type": "object", "properties": {"memory_id": {"type": "string"}}, "required": ["memory_id"]}},
    {"name": "search_memory_logs", "description": "Search Gigi's daily operation logs for past activity.", "input_schema": {"type": "object", "properties": {"query": {"type": "string", "description": "Keywords to search"}, "days_back": {"type": "integer", "description": "Days back (default 30)"}}, "required": ["query"]}},
    {"name": "get_morning_briefing", "description": "Generate the full morning briefing with weather, calendar, shifts, emails, ski conditions, alerts. ALWAYS use this when asked for a briefing, daily digest, or daily summary.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_ar_report", "description": "Get the QuickBooks accounts receivable aging report showing outstanding invoices and overdue amounts.", "input_schema": {"type": "object", "properties": {"detail_level": {"type": "string", "description": "Level of detail: 'summary' or 'detailed'"}}, "required": []}},
    {"name": "clock_in_shift", "description": "Clock a caregiver into their shift in WellSky. Use when a caregiver texts that they forgot to clock in. Look up their shift first with get_wellsky_shifts.", "input_schema": {"type": "object", "properties": {"appointment_id": {"type": "string", "description": "Shift/appointment ID from WellSky"}, "caregiver_name": {"type": "string", "description": "Caregiver name"}, "notes": {"type": "string", "description": "Optional notes"}}, "required": ["appointment_id"]}},
    {"name": "clock_out_shift", "description": "Clock a caregiver out of their shift in WellSky. Use when a caregiver texts that they forgot to clock out. Look up their shift first with get_wellsky_shifts.", "input_schema": {"type": "object", "properties": {"appointment_id": {"type": "string", "description": "Shift/appointment ID from WellSky"}, "caregiver_name": {"type": "string", "description": "Caregiver name"}, "notes": {"type": "string", "description": "Optional notes"}}, "required": ["appointment_id"]}},
    {"name": "find_replacement_caregiver", "description": "Find a replacement caregiver when someone calls out sick. Scores by fit, initiates SMS outreach.", "input_schema": {"type": "object", "properties": {"shift_id": {"type": "string", "description": "Shift/appointment ID needing coverage"}, "original_caregiver_id": {"type": "string", "description": "WellSky ID of caregiver who called out"}, "reason": {"type": "string", "description": "Reason for calloff"}}, "required": ["shift_id", "original_caregiver_id"]}},
    {"name": "get_task_board", "description": "Read Jason's task board. Shows tasks by section: Today, Soon, Later, Waiting, Agenda, Inbox, Done.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "add_task", "description": "Add a task to Jason's task board. Use when Jason texts 'I have a task', 'add to my list', 'remind me to'.", "input_schema": {"type": "object", "properties": {"task": {"type": "string", "description": "The task description"}, "section": {"type": "string", "description": "Board section: Today, Soon, Later, Waiting, Agenda, Inbox (default: Today)"}}, "required": ["task"]}},
    {"name": "complete_task", "description": "Mark a task done on Jason's task board.", "input_schema": {"type": "object", "properties": {"task_text": {"type": "string", "description": "Text of the task to complete (partial match OK)"}}, "required": ["task_text"]}},
    {"name": "capture_note", "description": "Capture a quick note or idea to Jason's scratchpad. Use when Jason texts 'I have an idea', 'note this', 'jot this down'.", "input_schema": {"type": "object", "properties": {"note": {"type": "string", "description": "The note or idea to capture"}}, "required": ["note"]}},
    {"name": "get_daily_notes", "description": "Read today's daily notes for context.", "input_schema": {"type": "object", "properties": {"date": {"type": "string", "description": "Date YYYY-MM-DD (default: today)"}}, "required": []}},
]

# Exclude marketing/finance tools from SMS (caregivers don't need these)
_SMS_EXCLUDE = {
    "get_marketing_dashboard", "get_google_ads_report", "get_website_analytics",
    "get_social_media_report", "get_gbp_report", "get_email_campaign_report",
    "generate_social_content", "get_pnl_report", "get_balance_sheet",
    "get_invoice_list", "get_cash_position", "get_financial_dashboard",
    "get_subscription_audit",
    "run_claude_code", "browse_with_claude",
}

# Auto-extend SMS tools from Telegram canonical set (ensures tool parity across channels)
try:
    from gigi.telegram_bot import ANTHROPIC_TOOLS as _TELE_TOOLS
    _sms_names = {t["name"] for t in SMS_TOOLS}
    for _t in _TELE_TOOLS:
        if _t["name"] not in _sms_names and _t["name"] not in _SMS_EXCLUDE:
            SMS_TOOLS.append(_t)
except ImportError:
    pass

# Full tool set for Glip DM replies — matches Telegram capabilities
DM_TOOLS = [
    {"name": "get_client_current_status", "description": "Check who is with a client RIGHT NOW. Returns current caregiver, shift times, and status.", "input_schema": {"type": "object", "properties": {"client_name": {"type": "string", "description": "Name of the client"}}, "required": ["client_name"]}},
    {"name": "get_wellsky_clients", "description": "Search for clients in WellSky by name, or get all active clients.", "input_schema": {"type": "object", "properties": {"search_name": {"type": "string", "description": "Client name to search (leave empty for all)"}, "active_only": {"type": "boolean", "description": "Only active clients (default true)"}}, "required": []}},
    {"name": "get_wellsky_caregivers", "description": "Search for caregivers in WellSky by name, or get all active caregivers.", "input_schema": {"type": "object", "properties": {"search_name": {"type": "string", "description": "Caregiver name to search (leave empty for all)"}, "active_only": {"type": "boolean", "description": "Only active caregivers (default true)"}}, "required": []}},
    {"name": "get_wellsky_shifts", "description": "Get shifts from WellSky. Use get_wellsky_clients/caregivers first to find IDs.", "input_schema": {"type": "object", "properties": {"client_id": {"type": "string"}, "caregiver_id": {"type": "string"}, "days": {"type": "integer", "description": "Days ahead (default 7)"}, "past_days": {"type": "integer", "description": "Days back for history/hours (default 0)"}, "open_only": {"type": "boolean", "description": "Only open/unfilled shifts"}}, "required": []}},
    {"name": "get_weather", "description": "Get current weather and forecast for a location.", "input_schema": {"type": "object", "properties": {"location": {"type": "string", "description": "City and State (e.g. Denver, CO)"}}, "required": ["location"]}},
    {"name": "web_search", "description": "Search the internet for current information — news, sports, prices, general knowledge.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "get_stock_price", "description": "Get current stock price for a ticker symbol (AAPL, TSLA, etc.)", "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}},
    {"name": "get_crypto_price", "description": "Get current cryptocurrency price (BTC, ETH, DOGE, SOL, etc.)", "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}},
    {"name": "search_concerts", "description": "Find upcoming concerts and live music events.", "input_schema": {"type": "object", "properties": {"query": {"type": "string", "description": "Artist, venue, or city to search"}}, "required": ["query"]}},
    {"name": "get_calendar_events", "description": "Get upcoming events from Jason's Google Calendar.", "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "description": "Days to look ahead (1-7)"}}, "required": []}},
    {"name": "search_emails", "description": "Search Jason's Gmail.", "input_schema": {"type": "object", "properties": {"query": {"type": "string", "description": "Gmail search query"}, "max_results": {"type": "integer"}}, "required": []}},
    {"name": "check_recent_sms", "description": "Check recent inbound SMS text messages across ALL company lines (307-459-8220, 719-428-3999). Shows texts from caregivers, clients, and anyone else who texted in.", "input_schema": {"type": "object", "properties": {"hours": {"type": "integer", "description": "How many hours back to look (default 12, max 48)"}, "from_phone": {"type": "string", "description": "Filter by sender phone number (optional)"}}, "required": []}},
    {"name": "send_sms", "description": "Send an SMS text message from the company number (307-459-8220) to any phone number.", "input_schema": {"type": "object", "properties": {"to_phone": {"type": "string", "description": "Phone number to text (e.g., +13035551234)"}, "message": {"type": "string", "description": "The SMS message to send (keep under 300 chars)"}}, "required": ["to_phone", "message"]}},
    {"name": "log_call_out", "description": "Log a caregiver call-out in WellSky and create an urgent admin task for coverage. Use when a caregiver reports they can't make their shift.", "input_schema": {"type": "object", "properties": {"caregiver_id": {"type": "string", "description": "The caregiver's WellSky ID"}, "caregiver_name": {"type": "string", "description": "The caregiver's name"}, "reason": {"type": "string", "description": "Reason for the call-out (e.g., 'sick', 'emergency', 'car trouble')"}, "shift_date": {"type": "string", "description": "Date of the shift (YYYY-MM-DD, defaults to today)"}}, "required": ["caregiver_id", "caregiver_name", "reason"]}},
    {"name": "identify_caller", "description": "Look up who a phone number belongs to. Checks caregiver, client, staff, and family records in WellSky.", "input_schema": {"type": "object", "properties": {"phone_number": {"type": "string", "description": "Phone number to look up"}}, "required": ["phone_number"]}},
    {"name": "save_memory", "description": "Save a fact or preference to long-term memory. ONLY use when someone EXPLICITLY states something to remember. NEVER save inferred, assumed, or fabricated information.", "input_schema": {"type": "object", "properties": {"content": {"type": "string", "description": "The EXACT fact or preference stated by the user. Quote their words, don't embellish."}, "category": {"type": "string", "description": "Category: scheduling, communication, travel, health, operations, personal, general"}, "importance": {"type": "string", "description": "high/medium/low"}}, "required": ["content", "category"]}},
    {"name": "recall_memories", "description": "Search long-term memory for saved preferences, facts, or instructions.", "input_schema": {"type": "object", "properties": {"category": {"type": "string"}, "search_text": {"type": "string"}}, "required": []}},
    {"name": "forget_memory", "description": "Archive a memory that is no longer relevant.", "input_schema": {"type": "object", "properties": {"memory_id": {"type": "string"}}, "required": ["memory_id"]}},
    {"name": "search_memory_logs", "description": "Search Gigi's daily operation logs for past activity.", "input_schema": {"type": "object", "properties": {"query": {"type": "string", "description": "Keywords to search"}, "days_back": {"type": "integer", "description": "Days back (default 30)"}}, "required": ["query"]}},
    {"name": "browse_webpage", "description": "Browse a webpage and extract its text content. Use for research, reading articles, checking websites.", "input_schema": {"type": "object", "properties": {"url": {"type": "string", "description": "URL to browse"}, "extract_links": {"type": "boolean", "description": "Also extract links (default false)"}}, "required": ["url"]}},
    {"name": "take_screenshot", "description": "Take a screenshot of a webpage. Returns the file path of the saved image.", "input_schema": {"type": "object", "properties": {"url": {"type": "string", "description": "URL to screenshot"}, "full_page": {"type": "boolean", "description": "Capture full scrollable page (default false)"}}, "required": ["url"]}},
    {"name": "get_morning_briefing", "description": "Generate the full morning briefing with weather, calendar, shifts, emails, ski conditions, alerts. ALWAYS use this when asked for a briefing, daily digest, or daily summary.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_ar_report", "description": "Get the QuickBooks accounts receivable aging report showing outstanding invoices and overdue amounts.", "input_schema": {"type": "object", "properties": {"detail_level": {"type": "string", "description": "Level of detail: 'summary' or 'detailed'"}}, "required": []}},
    {"name": "deep_research", "description": "Run deep autonomous financial research using the Elite Trading platform's 40+ data tools and 9 AI agents. Use for ANY investment question: stock analysis, crypto, macro outlook, etc. Takes 30-120 seconds.", "input_schema": {"type": "object", "properties": {"question": {"type": "string", "description": "The financial research question to analyze"}}, "required": ["question"]}},
    {"name": "get_weather_arb_status", "description": "Get weather trading bots: Weather Sniper Bot (Polymarket, LIVE, auto-snipes US temp markets at daily open) and Kalshi bot. Shows sniper status, forecasts, orders, P&L, positions.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "watch_tickets", "description": "Set up a ticket watch for an artist/event. Monitors Ticketmaster and AXS, sends Telegram alerts when tickets go on presale or general sale.", "input_schema": {"type": "object", "properties": {"artist": {"type": "string", "description": "Artist or event name"}, "venue": {"type": "string", "description": "Venue filter (optional)"}, "city": {"type": "string", "description": "City (default Denver)"}}, "required": ["artist"]}},
    {"name": "list_ticket_watches", "description": "List all active ticket watches.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "remove_ticket_watch", "description": "Stop watching for tickets.", "input_schema": {"type": "object", "properties": {"watch_id": {"type": "integer", "description": "Watch ID to remove"}}, "required": ["watch_id"]}},
    {"name": "clock_in_shift", "description": "Clock a caregiver into their shift in WellSky. Use when a caregiver needs help clocking in.", "input_schema": {"type": "object", "properties": {"appointment_id": {"type": "string", "description": "Shift/appointment ID from WellSky"}, "caregiver_name": {"type": "string", "description": "Caregiver name"}, "notes": {"type": "string", "description": "Optional notes"}}, "required": ["appointment_id"]}},
    {"name": "clock_out_shift", "description": "Clock a caregiver out of their shift in WellSky. Use when a caregiver needs help clocking out.", "input_schema": {"type": "object", "properties": {"appointment_id": {"type": "string", "description": "Shift/appointment ID from WellSky"}, "caregiver_name": {"type": "string", "description": "Caregiver name"}, "notes": {"type": "string", "description": "Optional notes"}}, "required": ["appointment_id"]}},
    {"name": "find_replacement_caregiver", "description": "Find a replacement caregiver when someone calls out sick. Scores by fit, initiates SMS outreach.", "input_schema": {"type": "object", "properties": {"shift_id": {"type": "string", "description": "Shift/appointment ID needing coverage"}, "original_caregiver_id": {"type": "string", "description": "WellSky ID of caregiver who called out"}, "reason": {"type": "string", "description": "Reason for calloff"}}, "required": ["shift_id", "original_caregiver_id"]}},
    {"name": "get_task_board", "description": "Read Jason's task board. Shows tasks by section: Today, Soon, Later, Waiting, Agenda, Inbox, Done.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "add_task", "description": "Add a task to Jason's task board. Use when Jason says 'I have a task', 'add to my list', 'remind me to'.", "input_schema": {"type": "object", "properties": {"task": {"type": "string", "description": "The task description"}, "section": {"type": "string", "description": "Board section: Today, Soon, Later, Waiting, Agenda, Inbox (default: Today)"}}, "required": ["task"]}},
    {"name": "complete_task", "description": "Mark a task done on Jason's task board.", "input_schema": {"type": "object", "properties": {"task_text": {"type": "string", "description": "Text of the task to complete (partial match OK)"}}, "required": ["task_text"]}},
    {"name": "capture_note", "description": "Capture a quick note or idea to Jason's scratchpad.", "input_schema": {"type": "object", "properties": {"note": {"type": "string", "description": "The note or idea to capture"}}, "required": ["note"]}},
    {"name": "get_daily_notes", "description": "Read today's daily notes for context.", "input_schema": {"type": "object", "properties": {"date": {"type": "string", "description": "Date YYYY-MM-DD (default: today)"}}, "required": []}},
]

# Auto-extend DM tools from Telegram canonical set (ensures tool parity across channels)
try:
    from gigi.telegram_bot import ANTHROPIC_TOOLS as _TELE_TOOLS
    _dm_names = {t["name"] for t in DM_TOOLS}
    for _t in _TELE_TOOLS:
        if _t["name"] not in _dm_names:
            DM_TOOLS.append(_t)
except ImportError:
    pass

# =========================================================================
# Gemini-format tool definitions — auto-generated from Anthropic-format lists
# =========================================================================
GEMINI_SMS_TOOLS = None
GEMINI_DM_TOOLS = None

if GEMINI_AVAILABLE:
    def _gs(type_str, desc, **kwargs):
        type_map = {"string": "STRING", "integer": "INTEGER", "boolean": "BOOLEAN"}
        return genai_types.Schema(type=type_map.get(type_str, type_str.upper()), description=desc, **kwargs)

    def _auto_gemini_tools(tools_list):
        """Auto-generate Gemini tool declarations from Anthropic-format tools."""
        decls = []
        for t in tools_list:
            props = {k: _gs(v.get("type", "string"), v.get("description", k))
                     for k, v in t["input_schema"]["properties"].items()}
            req = t["input_schema"].get("required", [])
            decls.append(genai_types.FunctionDeclaration(
                name=t["name"], description=t["description"],
                parameters=genai_types.Schema(type="OBJECT", properties=props, required=req if req else None)))
        return [genai_types.Tool(function_declarations=decls)]

    GEMINI_SMS_TOOLS = _auto_gemini_tools(SMS_TOOLS)
    GEMINI_DM_TOOLS = _auto_gemini_tools(DM_TOOLS)

    logger.info(f"Gemini tools auto-generated: SMS={len(SMS_TOOLS)}, DM={len(DM_TOOLS)}")

GLIP_DM_SYSTEM_PROMPT = """You are Gigi, the AI Chief of Staff for Colorado Care Assist, a home care agency in Colorado. You are responding via RingCentral internal messaging (Glip DM or Team Chat).

## Operating Laws (non-negotiable)
1. SIGNAL FILTERING: Never forward noise. Only surface items requiring judgment or action.
2. PREFERENCE LOCK: If you've seen a preference twice, it's policy. Never re-ask. Use recall_memories first.
3. CONDITIONAL AUTONOMY: Act first on low-risk items. Only ask for money/reputation/legal/irreversible.
4. STATE AWARENESS: Adjust your verbosity and urgency threshold to the current situation.
5. OPINIONATED DECISIONS: Lead with your recommendation + why + risk + one fallback.
6. MEMORY: ONLY save facts the user EXPLICITLY states. NEVER infer, assume, or fabricate memories. Search memory before asking questions already answered.
7. PATTERN DETECTION: If you notice a repeating problem, flag it proactively.
8. SELF-MONITORING: If you're getting verbose or drifting, correct yourself.
9. PUSH BACK: If you disagree, say why respectfully.

You are messaging with {sender_name}, a team member. This is an INTERNAL company conversation.

ABOUT JASON (the CEO/owner):
- Family: Wife Jennifer, daughters Lucky, Ava, and Gigi (you're named after his youngest)
- JAM BAND FANATIC: Phish (#1), Goose, Billy Strings, Widespread Panic, String Cheese, Trey Anastasio
- Also: Dogs In A Pile, Pigeons Playing Ping Pong, STS9, Dom Dolla, John Summit, Tame Impala, Khruangbin
- Venues: Red Rocks, Mission Ballroom, Ogden, Fillmore, Greek Theatre LA, The Sphere Vegas
- Travel: United Premier Gold (lifetime), Hertz Gold, Marriott Bonvoy Gold, TSA Pre, Epic + Ikon ski
- Style: "King of the Deal" — best quality for least money. Sharp, efficient, no fluff.

CRITICAL RULES:
- You are the Chief of Staff. Be direct, knowledgeable, and helpful.
- Use tools to look up real data — never make up shift times or caregiver names.
- If the sender is Jason (the CEO/owner), you can share any company data freely.
- For other team members, share data relevant to their role.
- Keep responses concise but not SMS-short — this is internal messaging, not SMS.
- No need to identify the caller — you already know who they are from the Glip conversation.
- ALWAYS use "they/them" pronouns for clients and caregivers unless you are certain of their gender. Preston Hill is female (she/her).
- Trust tool results. If get_client_current_status says someone IS with a client, report that directly. Do NOT then call a different tool and contradict yourself.
- If the schedule shows a gap for a 24-hour client, just report the facts (last caregiver, next caregiver, scheduled times). Do NOT say "COVERAGE GAP" or "needs immediate attention" — the schedule data may simply be incomplete. Our 24-hour clients always have coverage.

COMMON SCENARIOS:
- "Who is with [client]?" or "What caregiver is with [client]?": Use get_client_current_status. This is the DEFINITIVE tool for this question — it checks BOTH the cached database AND the live WellSky API, including 24-hour shifts. Trust its answer and do NOT call additional shift tools to second-guess it.
- "When is [name]'s next shift?" — The name could be a CLIENT or a CAREGIVER. Try get_client_current_status first (it shows next_shift). If not found as a client, try get_wellsky_shifts with the name as caregiver.
- Questions about schedules or shifts: Use get_wellsky_shifts.
- Questions about clients: Use get_wellsky_clients.
- Questions about caregivers: Use get_wellsky_caregivers. If a name isn't found, the person might be a CLIENT, not a caregiver — try get_wellsky_clients instead.
- "Any texts from caregivers?": Use check_recent_sms to see recent inbound SMS messages.
- "Text Angela and tell her...": Use send_sms with their phone number and your message.
- Caregiver calling out or cancelling: Use log_call_out after confirming the details. Then use find_replacement_caregiver to start finding a replacement.
- "I forgot to clock in" or "Can you clock me in?": Use identify_caller to find them, then get_wellsky_shifts to find their shift, then clock_in_shift with the appointment ID.
- "I forgot to clock out" or "Can you clock me out?": Same flow — identify, find shift, then clock_out_shift.
- "Who is this number?": Use identify_caller to look up a phone number.
- Operational questions: Answer from your knowledge or use tools.

KEY CAPABILITIES:
- You CAN see incoming text messages via check_recent_sms — you monitor ALL company lines: 307-459-8220, 719-428-3999, and 303-757-1777.
- You CAN send text messages via send_sms — you can text caregivers, clients, or anyone.
- You CAN log call-outs and create urgent admin tasks in WellSky.
- You CAN clock caregivers in and out of shifts via clock_in_shift and clock_out_shift.
- You CAN find replacement caregivers when someone calls out via find_replacement_caregiver.
- You CAN look up any phone number to identify who it belongs to.
- You CAN check calendars, emails, weather, stocks, crypto, and search the web.
- You have the FULL Gigi tool set: concerts, ticket watches, task board, notes, trading bots, AR reports, deep research, browser automation, and more.

ACKNOWLEDGMENTS:
- If someone replies with just "Sure", "Ok", "Thanks", "Got it", "Cool", "Perfect", "Sounds good", or similar — that's a conversation closer. Just say something brief like "Let me know if you need anything!" Do NOT call tools or start investigating something new.

TONE:
- Professional but warm — this is a colleague, not an external caller.
- Proactive — offer additional useful info when relevant, but NOT after acknowledgment messages.
- Never say "check with the office" — YOU are the office. Look it up.
- Never say "I don't have access to" something — check your tools first. You have 15+ tools.
- NEVER send unsolicited messages. NEVER proactively generate or send a morning briefing, daily digest, or any scheduled message unless explicitly asked by Jason in the current conversation. Jason does NOT want automated briefings.
- NEVER suggest installing software or mention CLI tools. There is NO "gog CLI", "gcloud CLI", "curl", "wttr.in", or any CLI. All services are built into your tools. If a tool fails, say "that's temporarily unavailable" — do NOT suggest installing anything.
- NEVER HALLUCINATE TOOLS or troubleshooting: Only use tools you actually have. NEVER invent commands, suggest configuration steps, or fabricate explanations for failures.
- NEVER REFORMAT TOOL OUTPUT: When get_morning_briefing returns a briefing, relay it as-is. Do NOT add "SETUP ISSUES" sections, troubleshooting, or TODO lists.
- OUTBOUND MESSAGES: NEVER send SMS/texts to external contacts without explicit confirmation from Jason. Show the draft first, wait for approval.
- NO sycophantic language: never say "locked in", "inner circle", "absolutely", "on it boss". Be direct and real.
- NEVER start with "Great question!" or "I'd be happy to help!" — just answer.

Today is {current_date}.
"""

SMS_SYSTEM_PROMPT = """You are Gigi, the AI assistant for Colorado Care Assist, a home care agency in Colorado Springs. You are responding via SMS text message.

## Operating Laws (non-negotiable)
1. PREFERENCE LOCK: If you've seen a preference twice, it's policy. Never re-ask. Use recall_memories first.
2. CONDITIONAL AUTONOMY: Act first on low-risk items. Only ask for escalation on money/reputation/legal.
3. MEMORY: Save important info using save_memory. Search memory before asking questions already answered.
4. PATTERN DETECTION: If you notice a repeating problem, flag it proactively.

CRITICAL RULES:
- Keep responses under 300 characters when possible. This is SMS, not email.
- If data requires more detail, you may go up to 500 characters but no more.
- Never share sensitive medical info via SMS.
- Never share other people's phone numbers or personal details.
- Do NOT make up shift times or caregiver names. Always use tools to look up real data.
- ALWAYS use "they/them" pronouns for clients and caregivers unless you know their gender. Preston Hill is female (she/her).
- Trust tool results. Report what the tools return — do not editorialize, add urgency, or say "URGENT" unless the human asks you to escalate.
- If the schedule shows a gap for a 24-hour client, just report the facts (last caregiver, next caregiver). Do NOT say "COVERAGE GAP" or "needs immediate attention" — the schedule data may simply be incomplete.

FIRST MESSAGE PROTOCOL:
On the FIRST message in a conversation, ALWAYS use identify_caller with the caller's phone number. This tells you if they are a caregiver, client, or unknown.

COMMON SCENARIOS:
- "Who is with [client]?" or "What caregiver is with [client]?": Use get_client_current_status. This checks BOTH the cached database AND the live WellSky API, including 24-hour shifts. Trust its answer and report it directly.
- "When is [name]'s next shift?" — Could be a CLIENT or a CAREGIVER. Try get_client_current_status first (shows next_shift). If not found as a client, try get_wellsky_shifts with the name.
- Caregiver calling out sick: Use identify_caller, then log_call_out. Then use find_replacement_caregiver to start finding a replacement. Reassure them.
- Caregiver forgot to clock in/out: Use identify_caller, then get_wellsky_shifts to find their shift, then clock_in_shift or clock_out_shift.
- Caregiver asking about schedule: Use identify_caller, then get_wellsky_shifts with their caregiver_id.
- Client asking when caregiver is coming: Use identify_caller, then get_wellsky_shifts with their client_id.
- Anyone asking about a person by name: Try get_wellsky_clients first, then get_wellsky_caregivers if not found. A name could be either.
- IMPORTANT: get_wellsky_clients and get_wellsky_caregivers search by NAME (e.g. "Angela"), NOT by WellSky ID numbers. If you have a caregiver_id or client_id from identify_caller, pass it directly to get_wellsky_shifts — do NOT pass it to get_wellsky_clients/caregivers.
- Unknown caller or general question: Respond helpfully, note the office will follow up.
- Simple acknowledgments ("Ok", "Thanks", "Got it", "Sure"): Just respond briefly. Do NOT call tools.

KEY CAPABILITIES:
- You monitor ALL company lines: 307-459-8220 (your direct line), 719-428-3999 (company line), and 303-757-1777 (main company number).
- You CAN look up clients and caregivers by NAME using get_wellsky_clients and get_wellsky_caregivers.
- You CAN check shift schedules using get_wellsky_shifts (requires a caregiver_id or client_id from the lookup tools).
- You CAN identify who is texting using identify_caller with their phone number.
- You have the FULL Gigi tool set: weather, web search, concerts, stocks, crypto, calendar, email, task board, notes, memory, research, trading bots, ticket watches, AR reports, browsing, and more.

TONE:
- Friendly, professional, concise
- Plain language (many caregivers speak English as a second language)
- OK to use abbreviations (Mon, Tue, etc.)
- NEVER suggest installing software or mention CLI tools. There is NO "gog CLI" or any CLI. If a tool fails, say "temporarily unavailable."
- NEVER HALLUCINATE TOOLS or troubleshooting: Only use tools you have. NEVER invent commands or suggest configuration steps.
- OUTBOUND SMS: NEVER send texts to contacts without explicit confirmation from the requester. Show the draft first.
- NO sycophantic language. Be direct and real.

Today is {current_date}.
The caller's phone number is {caller_phone}.
"""


class GigiRingCentralBot:
    def __init__(self):
        self.rc_service = ringcentral_messaging_service
        self.wellsky = WellSkyService()
        self.processed_message_ids = OrderedDict()  # preserves insertion order for FIFO eviction
        self.bot_extension_id = None
        self.startup_time = datetime.utcnow()
        self.reply_history = self._load_reply_history()
        # LLM for intelligent SMS/DM replies
        self.llm = None
        self.llm_provider = LLM_PROVIDER
        if LLM_PROVIDER == "gemini" and GEMINI_AVAILABLE and GEMINI_API_KEY:
            self.llm = genai.Client(api_key=GEMINI_API_KEY)
            logger.info(f"Gemini LLM initialized ({LLM_MODEL}) for SMS/DM replies")
        elif LLM_PROVIDER == "anthropic" and ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
            self.llm = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            logger.info(f"Anthropic LLM initialized ({LLM_MODEL}) for SMS/DM replies")
        else:
            # Fallback: try Gemini first (free), then Anthropic
            if GEMINI_AVAILABLE and GEMINI_API_KEY:
                self.llm = genai.Client(api_key=GEMINI_API_KEY)
                self.llm_provider = "gemini"
                logger.warning(f"Provider '{LLM_PROVIDER}' not available, falling back to gemini")
            elif ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
                self.llm = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                self.llm_provider = "anthropic"
                logger.warning(f"Provider '{LLM_PROVIDER}' not available, falling back to anthropic")
            else:
                logger.warning("No LLM provider available - using static replies")
        from gigi.conversation_store import ConversationStore
        self.conversation_store = ConversationStore()
        logger.info("Conversation store initialized (PostgreSQL)")
        self._reply_lock = asyncio.Lock()  # Prevent concurrent cooldown check + reply races
        # Track active team chat conversations (creator_id -> last_interaction_time)
        self._team_chat_active_conversations = {}
        # Autonomous shift coordination
        self._active_campaigns = {}  # campaign_id -> {shift_id, started_at, client_name}
        self._last_campaign_check = datetime.utcnow()
        if GIGI_SHIFT_MONITOR_ENABLED:
            logger.info("Autonomous shift monitor ENABLED")
        else:
            logger.info("Autonomous shift monitor disabled (set GIGI_SHIFT_MONITOR_ENABLED=true to enable)")

        # --- Caregiver preference extraction (GAP 3) ---
        self.preference_extractor = None
        try:
            from gigi.caregiver_preference_extractor import (
                CAREGIVER_MEMORY_ENABLED,
                CaregiverPreferenceExtractor,
            )
            from gigi.memory_system import MemorySystem
            if CAREGIVER_MEMORY_ENABLED and self.llm:
                memory_sys = MemorySystem()
                self.preference_extractor = CaregiverPreferenceExtractor(
                    memory_system=memory_sys,
                    llm_provider=self.llm_provider,
                )
                logger.info("Caregiver preference extractor ENABLED")
            else:
                logger.info("Caregiver preference extractor disabled")
        except Exception as e:
            logger.warning(f"Caregiver preference extractor not available: {e}")

        # --- Clock in/out reminders (GAP 4) ---
        self.clock_reminder = None
        self._last_clock_check = datetime.utcnow()
        try:
            from gigi.clock_reminder_service import (
                CLOCK_REMINDER_ENABLED,
                ClockReminderService,
            )
            if CLOCK_REMINDER_ENABLED:
                self.clock_reminder = ClockReminderService(
                    wellsky_service=self.wellsky,
                    sms_send_fn=self._send_sms_via_rc
                )
                logger.info("Clock reminder service ENABLED")
            else:
                logger.info("Clock reminder service disabled")
        except Exception as e:
            logger.warning(f"Clock reminder service not available: {e}")

        # --- Daily shift confirmations (GAP 5) ---
        self.daily_confirmation = None
        try:
            from gigi.daily_confirmation_service import (
                DAILY_CONFIRMATION_ENABLED,
                DailyConfirmationService,
            )
            if DAILY_CONFIRMATION_ENABLED:
                self.daily_confirmation = DailyConfirmationService(
                    wellsky_service=self.wellsky,
                    sms_send_fn=self._send_sms_via_rc
                )
                logger.info("Daily confirmation service ENABLED")
            else:
                logger.info("Daily confirmation service disabled")
        except Exception as e:
            logger.warning(f"Daily confirmation service not available: {e}")

        # --- Morning briefing via Telegram (7 AM MT) ---
        self.morning_briefing = None
        try:
            from gigi.morning_briefing_service import (
                MORNING_BRIEFING_ENABLED,
                MorningBriefingService,
            )
            if MORNING_BRIEFING_ENABLED:
                self.morning_briefing = MorningBriefingService()
                logger.info("Morning briefing service ENABLED")
            else:
                logger.info("Morning briefing service disabled")
        except Exception as e:
            logger.warning(f"Morning briefing service not available: {e}")

        # Task completion tracking (last notified task ID)
        self._last_notified_task_id = self._load_last_notified_task_id()

        # RingCentral SDK for WebSocket subscriptions
        self.rc_sdk = None
        self.rc_platform = None
        self.ws_client = None

        logger.info(f"Bot initialized. Startup time (UTC): {self.startup_time}")
        if GIGI_SMS_SHADOW_MODE:
            logger.info("📋 SMS SHADOW MODE: Draft replies will be reported to DM for review (not sent)")
        else:
            logger.info("🟢 SMS LIVE MODE: Replies will be sent directly to callers")
        logger.info(f"Reply history loaded: {len(self.reply_history.get('replies', []))} recent replies tracked")

    def _get_client_current_status(self, client_name: str) -> str:
        """Comprehensive client status check — cached DB + WellSky live API fallback.
        Returns JSON string with client status, current caregiver, and 24-hour context."""
        import psycopg2
        db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")

        if not client_name:
            return json.dumps({"error": "No client name provided"})

        conn = None
        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            search_lower = f"%{client_name.lower()}%"
            cur.execute("""
                SELECT id, full_name, address, city FROM cached_patients
                WHERE is_active = true
                AND (lower(full_name) LIKE %s OR lower(first_name) LIKE %s OR lower(last_name) LIKE %s)
                LIMIT 1
            """, (search_lower, search_lower, search_lower))
            client_row = cur.fetchone()
            if not client_row:
                return json.dumps({"status": "not_found", "message": f"No active client matching '{client_name}'"})

            client_id, client_full_name, addr, city = client_row
            now = datetime.now(TIMEZONE).replace(tzinfo=None)

            # Step 1: Check cached DB for active/upcoming shifts (look back 2 days for 24hr shifts)
            cur.execute("""
                SELECT a.scheduled_start, a.scheduled_end, p.full_name as caregiver_name, a.status
                FROM cached_appointments a
                LEFT JOIN cached_practitioners p ON a.practitioner_id = p.id
                WHERE a.patient_id = %s
                AND a.scheduled_start >= CURRENT_DATE - INTERVAL '2 days'
                AND a.scheduled_start < CURRENT_DATE + INTERVAL '2 days'
                ORDER BY a.scheduled_start ASC
            """, (client_id,))
            all_shifts = cur.fetchall()

            # Detect if this is a 24-hour client (has 24hr shifts in recent history)
            is_24hr_client = False
            for s in all_shifts:
                if s[0] and s[1]:
                    hours = (s[1] - s[0]).total_seconds() / 3600
                    if hours >= 20:  # 20+ hours = effectively 24-hour shift
                        is_24hr_client = True
                        break

            # Check for currently active shift
            for s in all_shifts:
                start, end, cg_name, status = s
                if start and end and start <= now <= end:
                    result = {
                        "client": client_full_name, "status": "active",
                        "caregiver": cg_name or "Unassigned",
                        "shift_start": start.strftime('%a %I:%M %p'),
                        "shift_end": end.strftime('%a %I:%M %p'),
                        "location": f"{addr}, {city}" if addr else "",
                        "is_24hr_client": is_24hr_client,
                        "message": f"{cg_name or 'Unassigned'} is with {client_full_name} right now. Shift: {start.strftime('%a %I:%M %p')} - {end.strftime('%a %I:%M %p')}."
                    }
                    return json.dumps(result)

            # Step 2: No active shift in cached DB — check WellSky live API
            try:
                live_shifts = self.wellsky.get_shifts(
                    date_from=date.today() - timedelta(days=1),
                    date_to=date.today() + timedelta(days=1),
                    client_id=client_id,
                    limit=10
                )
                for s in live_shifts:
                    s_start = getattr(s, 'start_datetime', None) or getattr(s, 'scheduled_start', None)
                    s_end = getattr(s, 'end_datetime', None) or getattr(s, 'scheduled_end', None)
                    cg_name = getattr(s, 'caregiver_name', None) or ''
                    cg_id = getattr(s, 'caregiver_id', None) or getattr(s, 'practitioner_id', None)

                    # Resolve "Unassigned" names from cached_practitioners
                    if (not cg_name or cg_name == 'Unassigned') and cg_id:
                        try:
                            cur.execute("SELECT full_name FROM cached_practitioners WHERE id = %s", (str(cg_id),))
                            prow = cur.fetchone()
                            if prow and prow[0]:
                                cg_name = prow[0]
                        except Exception:
                            pass

                    # Try to build datetime from date + time strings
                    if not s_start and hasattr(s, 'date') and hasattr(s, 'start_time') and s.date and s.start_time:
                        try:
                            s_start = datetime.combine(s.date, datetime.strptime(s.start_time, "%H:%M").time())
                        except (ValueError, TypeError):
                            pass
                    if not s_end and hasattr(s, 'date') and hasattr(s, 'end_time') and s.date and s.end_time:
                        try:
                            s_end = datetime.combine(s.date, datetime.strptime(s.end_time, "%H:%M").time())
                            if s_start and s_end <= s_start:
                                s_end += timedelta(days=1)
                        except (ValueError, TypeError):
                            pass

                    if s_start and s_end and s_start <= now <= s_end and cg_name and cg_name != 'Unassigned':
                        result = {
                            "client": client_full_name, "status": "active",
                            "caregiver": cg_name,
                            "source": "live_wellsky",
                            "shift_start": s_start.strftime('%a %I:%M %p'),
                            "shift_end": s_end.strftime('%a %I:%M %p'),
                            "is_24hr_client": is_24hr_client,
                            "message": f"{cg_name} is with {client_full_name} right now. Shift: {s_start.strftime('%a %I:%M %p')} - {s_end.strftime('%a %I:%M %p')}."
                        }
                        return json.dumps(result)
            except Exception as e:
                logger.warning(f"WellSky live API fallback failed (non-fatal): {e}")

            # Step 3: No active shift found anywhere — find next upcoming + recent history
            recent_shifts = []
            for s in all_shifts:
                start, end, cg_name, status = s
                if start and end and end < now and cg_name:
                    recent_shifts.append({"caregiver": cg_name, "start": start.strftime('%a %I:%M %p'), "end": end.strftime('%a %I:%M %p')})

            next_shifts = [s for s in all_shifts if s[0] and s[0] > now]
            next_info = None
            if next_shifts:
                ns = next_shifts[0]
                next_info = {"caregiver": ns[2] or "Unassigned", "start": ns[0].strftime('%a %I:%M %p')}

            # Build response — report facts, don't alarm
            if is_24hr_client:
                msg = f"{client_full_name} is a 24-hour care client."
                if recent_shifts:
                    last = recent_shifts[-1]
                    msg += f" The last scheduled caregiver was {last['caregiver']} ({last['start']} - {last['end']})."
                if next_info:
                    msg += f" The next scheduled caregiver is {next_info['caregiver']} starting {next_info['start']}."
                msg += " The schedule does not show a caregiver assigned right now — this may be a gap in the scheduling system rather than actual missing coverage."
            elif next_info:
                msg = f"The schedule does not show an active shift for {client_full_name} right now."
                if recent_shifts:
                    last = recent_shifts[-1]
                    msg += f" Last caregiver was {last['caregiver']} ({last['start']} - {last['end']})."
                msg += f" Next scheduled: {next_info['caregiver']} at {next_info['start']}."
            else:
                msg = f"No shifts found in the schedule for {client_full_name} today or tomorrow."
                if recent_shifts:
                    last = recent_shifts[-1]
                    msg += f" Last caregiver was {last['caregiver']} ({last['start']} - {last['end']})."

            result = {
                "client": client_full_name,
                "status": "schedule_gap" if is_24hr_client else "no_active_shift",
                "is_24hr_client": is_24hr_client,
                "message": msg
            }
            if recent_shifts:
                result["recent_shifts"] = recent_shifts[-3:]
            if next_info:
                result["next_shift"] = next_info
            return json.dumps(result)

        except Exception as e:
            logger.error(f"get_client_current_status error: {e}", exc_info=True)
            return json.dumps({"error": f"Failed to check status: {str(e)}"})
        finally:
            if conn:
                conn.close()

    def _load_reply_history(self) -> dict:
        """Load reply history from persistent storage for loop prevention"""
        try:
            import json
            from pathlib import Path
            history_file = Path(REPLY_HISTORY_FILE)
            if history_file.exists():
                with open(history_file, 'r') as f:
                    data = json.load(f)
                    # Clean old entries (older than 24 hours)
                    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
                    data['replies'] = [r for r in data.get('replies', []) if r.get('timestamp', '') > cutoff]
                    return data
        except Exception as e:
            logger.warning(f"Could not load reply history: {e}")
        return {'replies': [], 'hourly_count': 0, 'hourly_reset': datetime.utcnow().isoformat()}

    def _save_reply_history(self):
        """Save reply history to persistent storage"""
        try:
            import json
            with open(REPLY_HISTORY_FILE, 'w') as f:
                json.dump(self.reply_history, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save reply history: {e}")

    def _can_reply_to_number(self, phone: str) -> tuple[bool, str]:
        """
        Check if we can safely reply to this phone number.
        Returns (can_reply, reason).
        """
        now = datetime.utcnow()

        # Check global hourly rate limit
        hourly_reset = datetime.fromisoformat(self.reply_history.get('hourly_reset', now.isoformat()))
        if (now - hourly_reset).total_seconds() > 3600:
            # Reset hourly counter
            self.reply_history['hourly_count'] = 0
            self.reply_history['hourly_reset'] = now.isoformat()

        if self.reply_history.get('hourly_count', 0) >= MAX_REPLIES_PER_HOUR_GLOBAL:
            return False, f"Global hourly limit reached ({MAX_REPLIES_PER_HOUR_GLOBAL}/hr)"

        # Normalize phone number for comparison
        clean_phone = ''.join(filter(str.isdigit, phone))[-10:]

        # Check per-number limits
        today = now.date().isoformat()
        replies_to_number_today = 0
        last_reply_to_number = None

        for reply in self.reply_history.get('replies', []):
            reply_phone = ''.join(filter(str.isdigit, reply.get('phone', '')))[-10:]
            if reply_phone == clean_phone:
                reply_time = datetime.fromisoformat(reply.get('timestamp', '2000-01-01'))

                # Check cooldown
                minutes_since = (now - reply_time).total_seconds() / 60
                if minutes_since < REPLY_COOLDOWN_MINUTES:
                    return False, f"Cooldown active ({int(REPLY_COOLDOWN_MINUTES - minutes_since)} min remaining)"

                # Count today's replies
                if reply.get('timestamp', '').startswith(today):
                    replies_to_number_today += 1

        if replies_to_number_today >= MAX_REPLIES_PER_DAY_PER_NUMBER:
            return False, f"Daily limit reached for this number ({MAX_REPLIES_PER_DAY_PER_NUMBER}/day)"

        return True, "OK"

    def _record_reply(self, phone: str, reply_text: str = ""):
        """Record that we sent a reply to this number"""
        clean_phone = ''.join(filter(str.isdigit, phone))[-10:]
        self.reply_history.setdefault('replies', []).append({
            'phone': clean_phone,
            'timestamp': datetime.utcnow().isoformat(),
            'text': reply_text[:200] if reply_text else ""
        })
        self.reply_history['hourly_count'] = self.reply_history.get('hourly_count', 0) + 1
        self._save_reply_history()

    def _detect_semantic_loop(self, phone: str, new_reply: str) -> bool:
        """
        Detect if Gigi is repeating herself to this phone number.
        Compares key phrases in the new reply against recent replies.
        Returns True if a semantic loop is detected.
        """
        import re
        clean_phone = ''.join(filter(str.isdigit, phone))[-10:]

        # Gather recent reply texts to this number (last 3)
        recent_texts = []
        for reply in reversed(self.reply_history.get('replies', [])):
            reply_phone = ''.join(filter(str.isdigit, reply.get('phone', '')))[-10:]
            if reply_phone == clean_phone and reply.get('text'):
                recent_texts.append(reply['text'])
                if len(recent_texts) >= 3:
                    break

        if len(recent_texts) < 2:
            return False

        def _extract_key_phrases(text: str) -> set:
            """Extract meaningful words (4+ chars, lowercase, no stopwords)."""
            stopwords = {'this', 'that', 'with', 'from', 'have', 'been', 'will', 'your',
                         'more', 'about', 'would', 'could', 'should', 'their', 'there',
                         'here', 'they', 'them', 'than', 'then', 'also', 'just', 'like',
                         'when', 'what', 'which', 'were', 'some', 'these', 'those',
                         'into', 'other', 'know', 'need', 'help', 'back', 'sure',
                         'please', 'thanks', 'thank', 'very', 'really', 'going'}
            words = set(re.findall(r'[a-z]{4,}', text.lower()))
            return words - stopwords

        new_phrases = _extract_key_phrases(new_reply)
        if not new_phrases:
            return False

        # Check overlap with each recent reply
        loop_count = 0
        for prev_text in recent_texts:
            prev_phrases = _extract_key_phrases(prev_text)
            if not prev_phrases:
                continue
            overlap = len(new_phrases & prev_phrases) / max(len(new_phrases), 1)
            if overlap >= 0.5:  # 50%+ overlap = semantically similar
                loop_count += 1

        # If 2+ recent replies are similar to the new one, it's a loop
        return loop_count >= 2

    async def initialize(self):
        """Initialize connections and RingCentral SDK"""
        logger.info("Initializing Gigi Manager Bot...")

        # Perform immediate health check SMS
        # DISABLED: Repetitive spam (Feb 10, 2026) - Emergency fix
        # await self.send_health_check_sms()

        status = self.rc_service.get_status()
        if not status.get("api_connected"):
            logger.error("RingCentral API not connected! Check credentials.")
            return False

        # Get bot's own extension ID to avoid replying to self
        try:
            token = self.rc_service._get_access_token()
            if token:
                import requests
                response = requests.get(
                    f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if response.status_code == 200:
                    ext_data = response.json()
                    self.bot_extension_id = str(ext_data.get("id"))
                    logger.info(f"Bot extension ID: {self.bot_extension_id}")
        except Exception as e:
            logger.warning(f"Could not get bot extension ID: {e}")

        # Initialize RingCentral SDK for WebSocket subscriptions
        try:
            client_id = os.getenv("RINGCENTRAL_CLIENT_ID")
            client_secret = os.getenv("RINGCENTRAL_CLIENT_SECRET")
            self.rc_sdk = RingCentralSDK(client_id, client_secret, RINGCENTRAL_SERVER)
            self.rc_platform = self.rc_sdk.platform()
            self.rc_platform.login(jwt=ADMIN_JWT_TOKEN)
            logger.info("✅ RingCentral SDK logged in via JWT")
        except Exception as e:
            logger.error(f"RingCentral SDK login failed: {e}")
            return False

        logger.info(f"Monitoring chat: {TARGET_CHAT} and Direct SMS (WebSocket)")
        return True

    async def run_sms_websocket(self):
        """Run WebSocket subscription for real-time SMS on all company lines."""
        # Subscribe to instant SMS events on:
        # - Gigi's extension (~/extension/~ = ext 111, phone 307-459-8220)
        # - Admin extension (ext 101, ID 262740009, receives 719-428-3999 SMS)
        event_filters = [
            "/restapi/v1.0/account/~/extension/~/message-store/instant?type=SMS",
        ]
        for ext in COMPANY_LINE_EXTENSIONS:
            event_filters.append(
                f"/restapi/v1.0/account/~/extension/{ext['ext_id']}/message-store/instant?type=SMS"
            )
        logger.info(f"📡 WebSocket subscribing to SMS events: {event_filters}")
        ws_backoff = 30  # Start with 30s, increase on repeated failures

        while True:
            try:
                self.ws_client = self.rc_sdk.create_web_socket_client()

                def on_notification(message):
                    """Handle real-time SMS notification from RingCentral."""
                    asyncio.ensure_future(self._handle_sms_notification(message))

                def on_ws_created(ws):
                    nonlocal ws_backoff
                    ws_backoff = 30  # Reset backoff on successful connection
                    logger.info("📡 WebSocket connection established")

                def on_sub_created(sub):
                    info = sub.get_subscription_info()
                    logger.info(f"📡 WebSocket subscription created: {info.get('id', 'unknown')}")

                def on_error(error):
                    logger.error(f"📡 WebSocket error: {error}")

                def on_raw_message(message):
                    """Log raw WebSocket messages and route ServerNotifications.

                    The SDK's receiveSubscriptionNotification fires for ServerNotification
                    messages (via WebSocketSubscription.on_message), so we only need this
                    as a fallback for cases where the SDK callback doesn't fire.
                    We use a flag to avoid double-processing.
                    """
                    try:
                        import json as _json
                        parsed = _json.loads(message) if isinstance(message, str) else message
                        if isinstance(parsed, list) and len(parsed) > 0:
                            msg_type = parsed[0].get("type", "unknown")
                            logger.info(f"📡 WS raw msg: type={msg_type}")
                            if msg_type == "ServerNotification":
                                # Route to notification handler — SDK's on_notification
                                # may also fire, but processed_message_ids prevents double-processing
                                asyncio.ensure_future(self._handle_sms_notification(parsed))
                    except Exception as e:
                        logger.warning(f"📡 WS raw msg parse error: {e}")

                self.ws_client.on(WebSocketEvents.receiveMessage, on_raw_message)
                # NOTE: NOT registering receiveSubscriptionNotification separately —
                # on_raw_message already routes ServerNotification messages to avoid double-processing
                self.ws_client.on(WebSocketEvents.connectionCreated, on_ws_created)
                self.ws_client.on(WebSocketEvents.subscriptionCreated, on_sub_created)
                self.ws_client.on(WebSocketEvents.createConnectionError, on_error)

                await asyncio.gather(
                    self.ws_client.create_new_connection(),
                    self.ws_client.create_subscription(event_filters),
                )
            except Exception:
                logger.error(f"📡 WebSocket failed — reconnecting in {ws_backoff}s")
                await asyncio.sleep(ws_backoff)
                ws_backoff = min(ws_backoff * 2, 300)  # Exponential backoff, max 5 min
                # Re-login SDK before retry — token may have expired (401 TokenInvalid)
                try:
                    self.rc_platform.login(jwt=ADMIN_JWT_TOKEN)
                    logger.info("📡 SDK re-login successful before WebSocket reconnect")
                except Exception as login_err:
                    logger.error(f"📡 SDK re-login failed: {login_err}")

    async def _handle_sms_notification(self, message):
        """Process a real-time SMS notification from WebSocket subscription.

        Notification format from SDK is a list: [meta, payload]
        - meta: {"type": "ServerNotification", ...}
        - payload: {"event": "...", "body": {"changes": [{"type": "SMS", "newMessageIds": [...]}]}}
        """
        try:
            # Parse the notification — SDK passes it as a list [meta, payload]
            if isinstance(message, list) and len(message) >= 2:
                payload = message[1]
            elif isinstance(message, dict):
                payload = message
            else:
                logger.warning(f"📨 Unexpected notification format: {type(message)}")
                return

            body = payload.get("body", {})
            event_filter = payload.get("event", "")
            logger.info(f"📨 WebSocket SMS notification: event={event_filter}")

            # Changes-style notification (newMessageIds to fetch)
            changes = body.get("changes", [])
            if changes:
                for change in changes:
                    change_type = change.get("type", "")
                    new_ids = change.get("newMessageIds", [])
                    if change_type == "SMS" and new_ids:
                        logger.info(f"📨 New SMS message IDs: {new_ids}")
                        for new_msg_id in new_ids:
                            await self._fetch_and_process_sms(str(new_msg_id), event_filter)
                return

            # Direct message body (some instant filters may provide full message)
            msg_id = str(body.get("id", ""))
            if msg_id and msg_id not in self.processed_message_ids:
                direction = body.get("direction", "")
                msg_type = body.get("type", "")
                if direction == "Inbound" and msg_type == "SMS":
                    await self._process_sms_record(body, msg_id)

        except Exception as e:
            logger.error(f"Error handling SMS notification: {e}", exc_info=True)

    async def _fetch_and_process_sms(self, msg_id: str, event_filter: str):
        """Fetch a specific SMS message by ID and process it."""
        if msg_id in self.processed_message_ids:
            return
        # Mark IMMEDIATELY to prevent WebSocket+polling race
        self.processed_message_ids[msg_id] = True
        try:
            token = self._get_admin_access_token()
            if not token:
                logger.error("No token to fetch SMS message")
                return

            # Determine extension ID from event filter
            ext_id = "~"
            if "/extension/" in event_filter:
                parts = event_filter.split("/extension/")[1].split("/")
                if parts[0] and parts[0] != "~":
                    ext_id = parts[0]

            url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/{ext_id}/message-store/{msg_id}"
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                sms_data = response.json()
                if sms_data.get("direction") == "Inbound" and sms_data.get("type") == "SMS":
                    await self._process_sms_record(sms_data, msg_id)
                else:
                    self.processed_message_ids[msg_id] = True
            else:
                logger.error(f"Failed to fetch SMS {msg_id}: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching SMS {msg_id}: {e}")

    async def _process_sms_record(self, body: dict, msg_id: str):
        """Process a single inbound SMS record."""
        from_phone = body.get("from", {}).get("phoneNumber", "")
        to_phone = (body.get("to", [{}])[0].get("phoneNumber", "") if body.get("to") else "")
        text = body.get("subject", "")

        logger.info(f"📨 Real-time SMS from {from_phone} → {to_phone}: {text[:60]}")

        # Mark as processed IMMEDIATELY to prevent duplicate responses from fallback poll
        self.processed_message_ids[msg_id] = True

        sms_record = {
            "id": body.get("id"),
            "from": body.get("from", {}),
            "to": body.get("to", []),
            "subject": text,
            "direction": body.get("direction", ""),
            "creationTime": body.get("creationTime", body.get("lastModifiedTime", "")),
        }

        # Role 1: Documenter (always)
        await self.process_documentation(sms_record, text, source_type="sms", phone=from_phone)

        # Role 2: Replier
        if REPLIES_ENABLED:
            own_numbers = [RINGCENTRAL_FROM_NUMBER, "+13074598220", "+17194283999", "+13037571777"]
            if from_phone not in own_numbers:
                await self.process_reply(sms_record, text, reply_method="sms", phone=from_phone)
            else:
                logger.info(f"⏭️ Skipping reply to company number: {from_phone}")

        if len(self.processed_message_ids) > 1000:
            # Evict oldest entries (OrderedDict preserves insertion order)
            while len(self.processed_message_ids) > 500:
                self.processed_message_ids.popitem(last=False)

    def _get_admin_access_token(self):
        """Exchange JWT for access token"""
        try:
            # Get RC credentials from environment - NO hardcoded fallbacks
            client_id = os.getenv("RINGCENTRAL_CLIENT_ID")
            client_secret = os.getenv("RINGCENTRAL_CLIENT_SECRET")
            if not client_id or not client_secret:
                logger.error("RINGCENTRAL_CLIENT_ID or RINGCENTRAL_CLIENT_SECRET not set")
                return None

            response = requests.post(
                f"{RINGCENTRAL_SERVER}/restapi/oauth/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=(client_id, client_secret),  # Basic auth with client credentials
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": ADMIN_JWT_TOKEN
                },
                timeout=20
            )
            if response.status_code == 200:
                logger.info("✅ JWT exchanged for access token")
                return response.json().get("access_token")
            else:
                logger.error(f"JWT exchange failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"JWT exchange error: {e}")
            return None

    def _send_sms_via_rc(self, to_phone: str, message: str):
        """Send SMS using the admin JWT token. Used by clock reminders and daily confirmations."""
        # --- Outbound SMS whitelist (only whitelisted numbers until Gigi goes live) ---
        import re
        digits_only = re.sub(r'[^\d]', '', to_phone)
        if digits_only.startswith('1') and len(digits_only) == 11:
            digits_only = digits_only[1:]  # strip country code for comparison
        whitelist_csv = os.getenv("GIGI_SMS_WHITELIST", "6039971495")
        whitelist = {n.strip() for n in whitelist_csv.split(",") if n.strip()}
        if digits_only not in whitelist:
            logger.warning(f"SMS BLOCKED (not whitelisted): {to_phone} — message: {message[:80]}...")
            return False, f"Number {to_phone} not in SMS whitelist. Gigi outbound SMS is restricted."

        access_token = self._get_admin_access_token()
        if not access_token:
            return False, "No access token"

        clean_phone = re.sub(r'[^\d]', '', to_phone)
        if len(clean_phone) == 10:
            clean_phone = f"+1{clean_phone}"
        elif len(clean_phone) == 11 and clean_phone.startswith('1'):
            clean_phone = f"+{clean_phone}"
        elif not clean_phone.startswith('+'):
            clean_phone = f"+{clean_phone}"

        try:
            response = requests.post(
                f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/sms",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": {"phoneNumber": RINGCENTRAL_FROM_NUMBER},
                    "to": [{"phoneNumber": clean_phone}],
                    "text": message
                },
                timeout=20
            )
            if response.status_code in (200, 201):
                return True, response.json().get("id")
            else:
                logger.error(f"SMS send failed: {response.status_code}")
                return False, f"HTTP {response.status_code}"
        except Exception as e:
            logger.error(f"SMS send error: {e}")
            return False, str(e)

    async def send_health_check_sms(self):
        """Send a startup SMS to the admin to confirm vitality"""
        try:
            admin_phone = "+16039971495" # Jason's number
            logger.info(f"🚑 Sending Health Check SMS to {admin_phone}...")

            # Get access token from JWT
            access_token = self._get_admin_access_token()
            if not access_token:
                logger.error("❌ Could not get access token from JWT")
                return

            url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/sms"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            data = {
                "from": {"phoneNumber": RINGCENTRAL_FROM_NUMBER},
                "to": [{"phoneNumber": admin_phone}],
                "text": "🤖 Gigi Bot Online: Monitoring 719/303 lines via Admin Context."
            }

            # Using synchronous requests in async init is fine for startup
            response = requests.post(url, headers=headers, json=data, timeout=20)
            if response.status_code == 200:
                logger.info("✅ Health Check SMS Sent Successfully!")
            else:
                logger.error(f"❌ Health Check Failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"❌ Health Check Exception: {e}")

    def is_business_hours(self) -> bool:
        """Check if currently within M-F 8am-5pm Mountain Time"""
        now = datetime.now(TIMEZONE)
        is_weekday = now.weekday() < 5  # 0-4 is Mon-Fri
        is_working_hours = BUSINESS_START <= now.time() <= BUSINESS_END
        return is_weekday and is_working_hours

    async def check_and_act(self):
        """Main loop: Team chat, DMs, SMS fallback polling, scheduled services."""
        try:
            status = "BUSINESS HOURS (Silent)" if self.is_business_hours() else "AFTER HOURS (Active)"
            logger.info(f"--- Gigi Bot Cycle: {status} ---")

            # 1. SMS fallback poll (catches anything WebSocket missed, every 4th cycle = ~2 min)
            if not hasattr(self, '_sms_poll_counter'):
                self._sms_poll_counter = 0
            self._sms_poll_counter += 1
            if self._sms_poll_counter >= 4:
                self._sms_poll_counter = 0
                await self.check_direct_sms()

            # 2. Check Team Chats (Glip)
            await self.check_team_chats()

            # 3. Check Direct Glip Messages (1:1 DMs)
            await self.check_direct_glip_messages()

            # 4. Check active shift-filling campaigns (every 5 min)
            if GIGI_SHIFT_MONITOR_ENABLED and self._active_campaigns:
                now = datetime.utcnow()
                if (now - self._last_campaign_check).total_seconds() >= CAMPAIGN_CHECK_INTERVAL_SECONDS:
                    self._last_campaign_check = now
                    await self._check_campaign_status()

            # 4. Clock in/out reminders (every 5 min during business hours)
            # Respects REPLIES_ENABLED as global SMS kill switch
            if self.clock_reminder and REPLIES_ENABLED and self.is_business_hours():
                now = datetime.utcnow()
                if (now - self._last_clock_check).total_seconds() >= 300:
                    self._last_clock_check = now
                    try:
                        actions = self.clock_reminder.check_and_remind()
                        if actions:
                            logger.info(f"Clock reminders sent: {actions}")
                    except Exception as e:
                        logger.error(f"Clock reminder error: {e}")

            # 5. Daily shift confirmations (service handles its own 2pm timing)
            # Respects REPLIES_ENABLED as global SMS kill switch
            if self.daily_confirmation and REPLIES_ENABLED:
                try:
                    notified = self.daily_confirmation.check_and_send()
                    if notified:
                        logger.info(f"Daily confirmations sent to: {notified}")
                except Exception as e:
                    logger.error(f"Daily confirmation error: {e}")

            # 6. Morning briefing — DISABLED (user request: no unsolicited messages)
            # if self.morning_briefing:
            #     try:
            #         sent = self.morning_briefing.check_and_send()
            #         if sent:
            #             logger.info("Morning briefing sent to Jason via Telegram")
            #     except Exception as e:
            #         logger.error(f"Morning briefing error: {e}")

            # 7. Claude Code task completion notifications — DISABLED (user request: no unsolicited messages)
            # try:
            #     await self._check_task_completions()
            # except Exception as e:
            #     logger.error(f"Task completion check error: {e}")

            # 8. Ticket watch monitor — DISABLED (user request: no unsolicited messages)
            # if not hasattr(self, '_ticket_check_counter'):
            #     self._ticket_check_counter = 0
            #     self._ticket_monitor = None
            # self._ticket_check_counter += 1
            # if self._ticket_check_counter >= 30:
            #     self._ticket_check_counter = 0
            #     try:
            #         if self._ticket_monitor is None:
            #             from gigi.ticket_monitor import TicketMonitorService
            #             self._ticket_monitor = TicketMonitorService()
            #         await asyncio.to_thread(self._ticket_monitor.check_watches)
            #         logger.debug("Ticket watch check completed")
            #     except Exception as e:
            #         logger.error(f"Ticket monitor error: {e}")

        except Exception as e:
            logger.error(f"Error in check_and_act: {e}")

    def _load_last_notified_task_id(self) -> int:
        """Load last notified task ID from DB."""
        try:
            import psycopg2
            db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            cur.execute("SELECT value FROM gigi_dedup_state WHERE key = 'last_notified_task_id'")
            row = cur.fetchone()
            cur.close()
            conn.close()
            return int(row[0]) if row else 0
        except Exception:
            return 0

    def _save_last_notified_task_id(self, task_id: int):
        """Persist last notified task ID."""
        try:
            import psycopg2
            db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO gigi_dedup_state (key, value, created_at)
                VALUES ('last_notified_task_id', %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, created_at = NOW()
            """, (str(task_id),))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.warning(f"Could not save last notified task ID: {e}")

    async def _check_task_completions(self):
        """Check for newly completed/failed Claude Code tasks and notify via Telegram."""
        try:
            import psycopg2
            db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            cur.execute("""
                SELECT id, title, status, LEFT(result, 200) as result_preview, error
                FROM claude_code_tasks
                WHERE status IN ('completed', 'failed')
                  AND id > %s
                ORDER BY id ASC
                LIMIT 5
            """, (self._last_notified_task_id,))
            rows = cur.fetchall()
            cur.close()
            conn.close()

            if not rows:
                return

            for task_id, title, status, result_preview, error in rows:
                if status == "completed":
                    msg = f"Task #{task_id} completed: {title}"
                    if result_preview:
                        msg += f"\n\nResult: {result_preview}"
                else:
                    msg = f"Task #{task_id} FAILED: {title}"
                    if error:
                        msg += f"\n\nError: {error[:200]}"

                # Send via Telegram
                try:
                    import httpx
                    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
                    tg_chat = os.getenv("TELEGRAM_CHAT_ID", "8215335898")
                    if tg_token:
                        async with httpx.AsyncClient(timeout=10) as client:
                            await client.post(
                                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                                json={"chat_id": tg_chat, "text": msg},
                            )
                        logger.info(f"Task completion notification sent for #{task_id}")
                except Exception as e:
                    logger.warning(f"Task notification send failed: {e}")

                self._last_notified_task_id = task_id

            self._save_last_notified_task_id(self._last_notified_task_id)

        except Exception as e:
            logger.warning(f"Task completion check failed: {e}")

    async def check_team_chats(self):
        """Monitor Glip channels for activity documentation and replies"""
        chat = self.rc_service.find_chat_by_name(TARGET_CHAT)
        if not chat:
            logger.warning(f"Target chat {TARGET_CHAT} not found in check_team_chats")
            return

        # Reduced lookback for team chats to save quota
        messages = self.rc_service.get_chat_messages(
            chat["id"],
            since=datetime.utcnow() - timedelta(minutes=10),
            limit=20
        )

        if not messages:
            return

        logger.info(f"Glip: Found {len(messages)} recent messages in {TARGET_CHAT}")
        messages.sort(key=lambda x: x.get("creationTime", ""))

        new_msg_count = 0
        for msg in messages:
            msg_id = msg.get("id")
            if msg_id in self.processed_message_ids:
                continue

            # Skip historical messages (older than startup) to prevent bursts on restart
            creation_time_str = msg.get("creationTime", "")
            if creation_time_str:
                try:
                    creation_time = datetime.strptime(creation_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    try:
                        creation_time = datetime.strptime(creation_time_str, "%Y-%m-%dT%H:%M:%SZ")
                    except ValueError:
                        creation_time = None

                if creation_time and creation_time < self.startup_time:
                    self.processed_message_ids[msg_id] = True
                    continue

            # CRITICAL: Skip messages sent by the bot itself to prevent infinite loops
            creator_id = str(msg.get("creatorId", ""))
            if self.bot_extension_id and creator_id == self.bot_extension_id:
                self.processed_message_ids[msg_id] = True
                continue

            # Mark as processed IMMEDIATELY to prevent duplicate responses
            self.processed_message_ids[msg_id] = True

            text = msg.get("text", "")
            # RC @mentions may include ![:Person](id) format — extract clean text
            # Also check mentions array for Gigi's name
            mentions = msg.get("mentions", [])
            mentioned_names = [m.get("name", "").lower() for m in mentions] if mentions else []

            new_msg_count += 1
            logger.info(f"Glip: Processing new message {msg_id}: {text[:60]}...")
            await self.process_documentation(msg, text, source_type="chat")

            # Reply when someone mentions Gigi OR is in an active conversation with her
            gigi_mentioned = "gigi" in text.lower() or any("gigi" in n for n in mentioned_names)

            # Check if this person has an active conversation with Gigi (within 5 min)
            in_active_convo = False
            if creator_id in self._team_chat_active_conversations:
                last_time = self._team_chat_active_conversations[creator_id]
                if (datetime.utcnow() - last_time).total_seconds() < 300:
                    in_active_convo = True

            if gigi_mentioned or in_active_convo:
                sender_name = self._resolve_sender_name(creator_id) if creator_id else "Team member"
                reason = "mentioned" if gigi_mentioned else "active conversation"
                logger.info(f"Gigi replying in team chat ({reason}) to {sender_name}")
                chat = self.rc_service.find_chat_by_name(TARGET_CHAT)
                chat_id = chat.get("id") if chat else "team"
                reply = await self._get_llm_dm_reply(text, sender_name, f"team_{chat_id}")
                if reply:
                    try:
                        self.rc_service.send_message_to_chat(TARGET_CHAT, reply)
                        logger.info(f"Team chat reply sent: {reply[:50]}...")
                        # Track this as an active conversation
                        self._team_chat_active_conversations[creator_id] = datetime.utcnow()
                    except Exception as e:
                        logger.error(f"Failed to send team chat reply: {e}")
                # Update conversation tracking even on initial mention
                if gigi_mentioned:
                    self._team_chat_active_conversations[creator_id] = datetime.utcnow()

        if new_msg_count == 0:
            logger.debug(f"Glip: All {len(messages)} messages in {TARGET_CHAT} were pre-startup or already processed")

    async def check_direct_glip_messages(self):
        """Monitor Glip 1:1 direct message conversations and reply via Claude."""
        try:
            direct_chats = self.rc_service.list_direct_chats()
            if not direct_chats:
                return

            for chat in direct_chats:
                chat_id = chat.get("id")
                if not chat_id:
                    continue

                # Get recent messages from this DM
                messages = self.rc_service.get_chat_messages(
                    chat_id,
                    since=datetime.utcnow() - timedelta(minutes=10),
                    limit=10
                )
                if not messages:
                    continue

                messages.sort(key=lambda x: x.get("creationTime", ""))

                for msg in messages:
                    msg_id = msg.get("id")
                    if msg_id in self.processed_message_ids:
                        continue

                    # Skip historical messages (older than startup)
                    creation_time_str = msg.get("creationTime", "")
                    if creation_time_str:
                        try:
                            creation_time = datetime.strptime(creation_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                        except ValueError:
                            try:
                                creation_time = datetime.strptime(creation_time_str, "%Y-%m-%dT%H:%M:%SZ")
                            except ValueError:
                                creation_time = None

                        if creation_time and creation_time < self.startup_time:
                            self.processed_message_ids[msg_id] = True
                            continue

                    # Skip messages from bot itself
                    creator_id = str(msg.get("creatorId", ""))
                    if self.bot_extension_id and creator_id == self.bot_extension_id:
                        self.processed_message_ids[msg_id] = True
                        continue

                    text = msg.get("text", "").strip()
                    if not text:
                        self.processed_message_ids[msg_id] = True
                        continue

                    # Mark as processed IMMEDIATELY to prevent duplicate responses
                    # (LLM call + reply send can take 1-3s, during which next poll cycle could pick up same message)
                    self.processed_message_ids[msg_id] = True

                    sender_name = self._resolve_sender_name(creator_id)
                    logger.info(f"Glip DM: New message from {sender_name} ({creator_id}) in chat {chat_id}: {text[:50]}...")

                    # Get LLM reply using Chief of Staff prompt
                    reply = None
                    if self.llm:
                        try:
                            reply = await self._get_llm_dm_reply(text, sender_name, chat_id)
                        except Exception as e:
                            logger.error(f"LLM DM reply failed ({self.llm_provider}): {e}")

                    if not reply:
                        reply = f"Hi {sender_name.split()[0]}! Let me look into that and get back to you."

                    # Reply in the same DM chat
                    try:
                        result = self.rc_service.post_to_chat(chat_id, reply)
                        if result:
                            logger.info(f"Glip DM reply sent to chat {chat_id}: {reply[:50]}...")
                        else:
                            logger.error(f"Failed to send Glip DM reply to chat {chat_id}")
                    except Exception as e:
                        logger.error(f"Error sending Glip DM reply: {e}")

        except Exception as e:
            logger.error(f"Failed to check direct Glip messages: {e}")

    async def check_direct_sms(self):
        """Monitor RingCentral SMS across Gigi's extension AND company lines."""
        # Get access token from JWT
        token = self._get_admin_access_token()

        if not token:
            logger.error("Admin Token missing or invalid in check_direct_sms")
            return

        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            }
            params = {
                "messageType": "SMS",
                "dateFrom": (datetime.utcnow() - timedelta(hours=12)).isoformat(),
                "perPage": 100
            }

            # Poll Gigi's own extension (307 number) + company line extensions (719, etc.)
            extensions_to_poll = [
                {"ext_id": "~", "label": "307-459-8220 (Gigi)"},
            ] + COMPANY_LINE_EXTENSIONS

            all_records = []
            for ext_info in extensions_to_poll:
                ext_id = ext_info["ext_id"]
                label = ext_info["label"]
                url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/{ext_id}/message-store"
                logger.info(f"SMS: Polling {label} message-store")
                try:
                    response = requests.get(url, headers=headers, params=params, timeout=20)
                    if response.status_code == 200:
                        records = response.json().get("records", [])
                        # Tag each record with the line it came from
                        for r in records:
                            r["_company_line"] = label
                        all_records.extend(records)
                    else:
                        logger.error(f"RC SMS Store Error ({label}): {response.status_code}")
                except Exception as e:
                    logger.error(f"Failed to poll {label}: {e}")

            for sms in all_records:
                msg_id = str(sms.get("id"))
                from_phone = sms.get("from", {}).get("phoneNumber")
                to_phone = sms.get("to", [{}])[0].get("phoneNumber")
                text = sms.get("subject", "")
                line_label = sms.get("_company_line", "")

                if msg_id in self.processed_message_ids:
                    continue

                # Only process inbound messages from company lines (skip outbound)
                direction = sms.get("direction", "")
                if line_label != "307-459-8220 (Gigi)" and direction == "Outbound":
                    self.processed_message_ids[msg_id] = True
                    continue

                # Skip historical SMS (older than startup) to prevent bursts on restart
                creation_time_str = sms.get("creationTime", "")
                if creation_time_str:
                    try:
                        creation_time = datetime.strptime(creation_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                    except ValueError:
                        try:
                            creation_time = datetime.strptime(creation_time_str, "%Y-%m-%dT%H:%M:%SZ")
                        except ValueError:
                            creation_time = None

                    if creation_time and creation_time < self.startup_time:
                        self.processed_message_ids[msg_id] = True
                        continue

                # Mark as processed IMMEDIATELY to prevent duplicate responses
                self.processed_message_ids[msg_id] = True

                # Role 1: Documenter
                await self.process_documentation(sms, text, source_type="sms", phone=from_phone)

                # Role 2: Replier
                if REPLIES_ENABLED:
                    # Don't reply to our own numbers (prevent loops), but DO reply to real people
                    own_numbers = [RINGCENTRAL_FROM_NUMBER, "+13074598220", "+17194283999", "+13037571777"]
                    if from_phone not in own_numbers:
                        await self.process_reply(sms, text, reply_method="sms", phone=from_phone)
                    else:
                        logger.info(f"⏭️ Skipping reply to company number: {from_phone}")

            # Cleanup processed IDs to keep memory low (evict oldest, keep 500)
            if len(self.processed_message_ids) > 1000:
                logger.info("Cleaning up processed message IDs cache...")
                while len(self.processed_message_ids) > 500:
                    self.processed_message_ids.popitem(last=False)

        except Exception as e:
            logger.error(f"Failed to check direct SMS: {e}")

    async def process_documentation(self, msg: dict, text: str, source_type: str = "chat", phone: str = None):
        """QA/Manager Logic: Document ALL care-related communications in WellSky.

        HEALTHCARE RULE: If a client or caregiver is mentioned, it gets documented.
        Uses DocumentReference API (clinical-note) as PRIMARY WellSky path — works for
        any client, no encounter/shift needed.
        """
        import re

        import psycopg2

        db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")

        # =====================================================================
        # 1. Identify Caregiver (from phone number via cached DB)
        # =====================================================================
        caregiver_id = None
        caregiver_name = None

        if source_type == "sms" and phone:
            try:
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                # Normalize phone to 10 digits
                clean_phone = re.sub(r'[^\d]', '', phone)
                if len(clean_phone) == 11 and clean_phone.startswith("1"):
                    clean_phone = clean_phone[1:]
                if len(clean_phone) == 10:
                    cur.execute("""
                        SELECT id, full_name FROM cached_practitioners
                        WHERE is_active = true AND phone IS NOT NULL
                        AND RIGHT(REGEXP_REPLACE(phone, '[^0-9]', '', 'g'), 10) = %s
                        LIMIT 1
                    """, (clean_phone,))
                    row = cur.fetchone()
                    if row:
                        caregiver_id = str(row[0])
                        caregiver_name = row[1]
                        logger.info(f"Doc: Identified SMS sender as caregiver: {caregiver_name}")
                conn.close()
            except Exception as e:
                logger.warning(f"Doc: Caregiver phone lookup error: {e}")

        # =====================================================================
        # 2. Extract Client Name from message text + match against cached DB
        # =====================================================================
        client_id = None
        client_name = None
        lower_text = text.lower()

        # Extract potential names from text
        possible_names = []
        # Pattern 1: Names after context words
        name_match = re.search(
            r'(?:for|client|visit|shift|with|about|at|to|see|seeing|from)\s+'
            r'([A-Z][a-z]+\.?(?:\s[A-Z][a-z]+)?)',
            text
        )
        if name_match:
            possible_names.append(name_match.group(1))

        # Pattern 2: Any "FirstName LastName" pattern
        fallback_matches = re.findall(r'([A-Z][a-z]+\.?\s[A-Z][a-z]+)', text)
        for m in fallback_matches:
            if m not in possible_names:
                possible_names.append(m)

        # Match against cached_patients (reliable — all 70 clients)
        if possible_names:
            try:
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                for pname in possible_names:
                    if client_id:
                        break
                    clean_name = pname.replace(".", "").strip()
                    name_parts = clean_name.split()
                    # Strip honorifics (Mrs, Mr, Ms, Dr)
                    if name_parts and name_parts[0].lower() in ("mrs", "mr", "ms", "dr", "miss"):
                        name_parts = name_parts[1:]
                    if len(name_parts) >= 2:
                        first = name_parts[0].lower()
                        last = name_parts[-1].lower()
                        if len(last) < 2:
                            continue
                        cur.execute("""
                            SELECT id, full_name FROM cached_patients
                            WHERE is_active = true
                            AND lower(last_name) = %s
                            AND (lower(first_name) = %s
                                 OR lower(first_name) LIKE %s
                                 OR %s LIKE lower(first_name) || '%%')
                            LIMIT 1
                        """, (last, first, f"{first}%", first))
                    elif len(name_parts) == 1 and len(name_parts[0]) > 3:
                        search = name_parts[0].lower()
                        cur.execute("""
                            SELECT id, full_name FROM cached_patients
                            WHERE is_active = true
                            AND (lower(last_name) = %s OR lower(first_name) = %s)
                            LIMIT 1
                        """, (search, search))
                    else:
                        continue
                    row = cur.fetchone()
                    if row:
                        client_id = str(row[0])
                        client_name = row[1]
                conn.close()
            except Exception as e:
                logger.warning(f"Doc: Client name lookup error: {e}")

        # =====================================================================
        # 3. Classify the Event
        # =====================================================================
        note_type = "general"
        is_alert = False
        is_task = False
        priority = "normal"

        if any(w in lower_text for w in [
            "call out", "call-out", "callout", "sick", "emergency",
            "cancel", "can't make it", "cant make it", "won't be able",
            "wont be able", "not coming", "not going to make"
        ]):
            note_type = "callout"
            is_alert = True
            is_task = True
            priority = "urgent"
        elif any(w in lower_text for w in [
            "fell", "fall ", "injury", "hospital", "er ", " er.",
            "ambulance", "911", "hurt", "bleeding", "unconscious",
            "chest pain", "stroke", "seizure"
        ]):
            note_type = "safety"
            is_alert = True
            is_task = True
            priority = "urgent"
        elif any(w in lower_text for w in [
            "late", "traffic", "delayed", "running behind", "on my way",
            "running late", "be there soon"
        ]):
            note_type = "late"
            is_alert = True
        elif any(w in lower_text for w in [
            "complain", "upset", "angry", "issue", "quit", "problem",
            "concerned", "worried", "unhappy", "frustrated", "refuse"
        ]):
            note_type = "complaint"
            is_alert = True
            is_task = True
            priority = "high"
        elif any(w in lower_text for w in [
            "medication", "meds", "prescription", "pharmacy", "dose",
            "medicine", "refill"
        ]):
            note_type = "medication"
            is_alert = True
        elif any(w in lower_text for w in [
            "accept", "take the shift", "can work", "available",
            "filled", "confirmed", "i'll be there", "ill be there"
        ]):
            note_type = "schedule"
        elif any(w in lower_text for w in [
            "reschedule", "swap", "switch", "cover", "replacement",
            "change shift", "move shift"
        ]):
            note_type = "schedule_change"
            is_task = True

        # =====================================================================
        # 4. HEALTHCARE RULE: Document if client OR caregiver identified, or alert/task
        # =====================================================================
        should_log = bool(client_id) or bool(caregiver_id) or is_alert or is_task

        if not should_log:
            return  # Skip non-care-related messages with no identified people

        # =====================================================================
        # 5. Document to WellSky via DocumentReference API + PostgreSQL backup
        # =====================================================================
        wellsky_doc_id = None
        wellsky_synced = False

        try:
            source_label = "SMS" if source_type == "sms" else "Team Chat"
            sender = caregiver_name or phone or str(msg.get("creatorId", "Unknown"))

            # Build a natural, human-readable title for the WellSky dashboard
            # Should read like Israt or Cynthia wrote it: "Angela Atteberry call-out — Grant Allred shift"
            if note_type == "callout":
                note_title = f"{sender} call-out" + (f" — {client_name} shift" if client_name else "")
            elif note_type == "late":
                note_title = f"{sender} running late" + (f" — {client_name}" if client_name else "")
            elif note_type == "safety":
                snippet = text[:60].rsplit(" ", 1)[0] if len(text) > 60 else text
                note_title = f"Safety Alert: {client_name or sender} — {snippet}"
            elif note_type == "complaint":
                snippet = text[:50].rsplit(" ", 1)[0] if len(text) > 50 else text
                note_title = f"Complaint: {client_name or sender} — {snippet}"
            elif note_type == "medication":
                note_title = f"Medication: {client_name or sender}"
            elif note_type == "schedule":
                note_title = f"{sender} shift confirmed" + (f" — {client_name}" if client_name else "")
            elif note_type == "schedule_change":
                note_title = f"{sender} schedule change" + (f" — {client_name}" if client_name else "")
            else:
                # general/care_plan — use sender + brief snippet of message
                snippet = text[:60].rsplit(" ", 1)[0] if len(text) > 60 else text
                note_title = f"{sender}: {snippet}"

            note_body = (
                f"Via {source_label}\n"
                + (f"Client: {client_name}\n" if client_name else "")
                + (f"Caregiver: {caregiver_name}\n" if caregiver_name and caregiver_name != sender else "")
                + f"\n{text}\n"
            )

            # -----------------------------------------------------------------
            # A. Client identified → Document on their WellSky profile
            #    Uses encounter/TaskLog API (searches 90 days for an encounter)
            # -----------------------------------------------------------------
            if client_id:
                try:
                    success, result_msg = self.wellsky.add_note_to_client(
                        client_id=client_id,
                        note=note_body,
                        note_type=note_type,
                        source="gigi_manager",
                        title=note_title
                    )
                    if success and "WellSky" in str(result_msg):
                        wellsky_synced = True
                        wellsky_doc_id = str(result_msg)
                        logger.info(f"✅ Documented to WellSky for {client_name}: {result_msg}")
                    elif success:
                        logger.warning(f"⚠️ Documented LOCALLY ONLY for {client_name}: {result_msg}")
                    else:
                        logger.error(f"Documentation failed for {client_name}: {result_msg}")
                except Exception as e:
                    logger.error(f"WellSky documentation error for {client_name}: {e}")

            # -----------------------------------------------------------------
            # B. Caregiver only → find their client from today's schedule, document there
            # -----------------------------------------------------------------
            elif caregiver_id:
                try:
                    from datetime import date as date_cls
                    shifts = self.wellsky.get_shifts(
                        caregiver_id=caregiver_id,
                        date_from=date_cls.today(),
                        date_to=date_cls.today()
                    )
                    if shifts:
                        # Find client ID from first shift
                        shift_client_id = None
                        shift_client_name = None
                        for s in shifts:
                            sid = getattr(s, 'client_id', None) or (s.get('client_id') if isinstance(s, dict) else None)
                            if sid:
                                shift_client_id = str(sid)
                                shift_client_name = getattr(s, 'client_name', None) or (s.get('client') if isinstance(s, dict) else None)
                                break
                        if shift_client_id:
                            linked_note = f"{note_body}(Auto-linked via {caregiver_name}'s schedule)\n"
                            success, result_msg = self.wellsky.add_note_to_client(
                                client_id=shift_client_id,
                                note=linked_note,
                                note_type=note_type,
                                source="gigi_manager",
                                title=note_title
                            )
                            if success and "WellSky" in str(result_msg):
                                wellsky_synced = True
                                wellsky_doc_id = str(result_msg)
                                client_name = shift_client_name or "Unknown"
                                logger.info(f"✅ Documented to WellSky via caregiver schedule → {client_name}: {result_msg}")
                            else:
                                logger.warning(f"⚠️ Caregiver doc for {caregiver_name} saved locally: {result_msg}")
                    else:
                        logger.info(f"No shifts today for {caregiver_name} — documented in PostgreSQL only")
                except Exception as e:
                    logger.warning(f"Caregiver→client schedule lookup for doc failed: {e}")

            # -----------------------------------------------------------------
            # C. PostgreSQL backup log (ALWAYS — regardless of WellSky success)
            # -----------------------------------------------------------------
            try:
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS gigi_wellsky_documentation (
                        id SERIAL PRIMARY KEY,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        source TEXT,
                        person_type TEXT,
                        person_id TEXT,
                        person_name TEXT,
                        note_type TEXT,
                        priority TEXT,
                        message_text TEXT,
                        wellsky_doc_id TEXT,
                        wellsky_synced BOOLEAN DEFAULT FALSE,
                        sender_phone TEXT
                    )
                """)
                person_type = "client" if client_id else ("caregiver" if caregiver_id else "unknown")
                person_id_val = client_id or caregiver_id or ""
                person_name_val = client_name or caregiver_name or "Unknown"
                cur.execute("""
                    INSERT INTO gigi_wellsky_documentation
                    (source, person_type, person_id, person_name, note_type, priority,
                     message_text, wellsky_doc_id, wellsky_synced, sender_phone)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (source_type, person_type, person_id_val, person_name_val,
                      note_type, priority, text, wellsky_doc_id, wellsky_synced,
                      phone or ""))
                conn.commit()
                conn.close()
                logger.info(f"Doc: PostgreSQL backup logged (synced={wellsky_synced}, type={note_type}, person={person_name_val})")
            except Exception as e:
                logger.error(f"Doc: PostgreSQL backup log error: {e}")

        except Exception as e:
            logger.error(f"Failed to document: {e}")

        # Extract caregiver preferences from conversation (GAP 3)
        if caregiver_id and self.preference_extractor:
            try:
                memory_ids = await self.preference_extractor.extract_and_store(
                    caregiver_id=caregiver_id,
                    caregiver_name=caregiver_name or "Unknown",
                    message_text=text
                )
                if memory_ids:
                    logger.info(f"Extracted {len(memory_ids)} preferences for {caregiver_name}")
            except Exception as e:
                logger.warning(f"Preference extraction failed: {e}")

        # Autonomous shift filling: trigger when callout detected
        if note_type == "callout" and GIGI_SHIFT_MONITOR_ENABLED:
            await self._trigger_shift_filling(possible_names, caregiver_name if caregiver_id else None, text[:100])

    # =========================================================================
    # Autonomous Shift Coordination
    # =========================================================================

    async def _trigger_shift_filling(self, possible_names: list, caregiver_name: str, reason: str):
        """When a callout is documented, find affected shifts and start filling campaigns."""
        try:
            # Try to identify the caregiver who called out
            caregiver_id = None
            cg_name = ""

            # First try names from the message text
            for name in possible_names:
                clean = name.replace(".", "").strip()
                if len(clean.split()) < 2:
                    continue
                last_name = clean.split()[-1]
                if len(last_name) < 3:
                    continue
                try:
                    practitioners = self.wellsky.search_practitioners(last_name=last_name)
                    for p in practitioners:
                        if clean.lower() in p.full_name.lower() or p.last_name.lower() == last_name.lower():
                            caregiver_id = p.id
                            cg_name = p.full_name
                            break
                except Exception:
                    pass
                if caregiver_id:
                    break

            if not caregiver_id:
                logger.info("Shift monitor: Could not identify caregiver for auto-fill")
                return

            # Get this caregiver's shifts for the next 48 hours
            from datetime import timedelta
            shifts = self.wellsky.get_shifts(
                caregiver_id=caregiver_id,
                date_from=date.today(),
                date_to=date.today() + timedelta(days=2),
                limit=10
            )

            if not shifts:
                logger.info(f"Shift monitor: No upcoming shifts found for {cg_name}")
                return

            import requests as http_requests
            for shift in shifts:
                shift_status = shift.status.value if hasattr(shift.status, 'value') else str(shift.status)
                if shift_status not in ('scheduled', 'open', 'confirmed'):
                    continue

                # Don't re-trigger for shifts we already started campaigns for
                if shift.id in self._active_campaigns:
                    continue

                logger.info(f"Shift monitor: Auto-triggering fill for shift {shift.id} ({cg_name} → {getattr(shift, 'client_name', 'unknown client')})")

                try:
                    resp = http_requests.post(
                        "http://localhost:8765/api/internal/shift-filling/calloff",
                        json={
                            "shift_id": shift.id,
                            "caregiver_id": caregiver_id,
                            "reason": reason
                        },
                        timeout=30
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        campaign_id = data.get("campaign_id")
                        if campaign_id:
                            self._active_campaigns[campaign_id] = {
                                "shift_id": shift.id,
                                "started_at": datetime.utcnow().isoformat(),
                                "client_name": getattr(shift, 'client_name', 'unknown'),
                                "caregiver_name": cg_name
                            }
                            logger.info(f"Shift filling campaign started: {campaign_id}, contacted {data.get('candidates_contacted', 0)} caregivers")

                            # Notify team chat
                            try:
                                self.rc_service.send_message_to_chat(
                                    TARGET_CHAT,
                                    f"[Gigi] Shift filling started for {getattr(shift, 'client_name', 'client')} "
                                    f"(was: {cg_name}). Contacting {data.get('candidates_contacted', 0)} replacement caregivers."
                                )
                            except Exception:
                                pass
                    else:
                        logger.error(f"Shift filling API error: {resp.status_code} - {resp.text[:200]}")
                except Exception as e:
                    logger.error(f"Failed to call shift filling API: {e}")

        except Exception as e:
            logger.error(f"Error in callout-triggered shift filling: {e}")

    async def _check_campaign_status(self):
        """Check active shift-filling campaigns and escalate/notify as needed."""
        if not self._active_campaigns:
            return

        import requests as http_requests
        completed = []

        for campaign_id, info in self._active_campaigns.items():
            try:
                resp = http_requests.get(
                    f"http://localhost:8765/api/internal/shift-filling/campaigns/{campaign_id}",
                    timeout=10
                )
                if resp.status_code != 200:
                    continue

                data = resp.json()
                if not data.get("found"):
                    completed.append(campaign_id)
                    continue

                if data.get("shift_filled"):
                    winner = data.get("winning_caregiver", "someone")
                    logger.info(f"Campaign {campaign_id} FILLED by {winner}")
                    try:
                        self.rc_service.send_message_to_chat(
                            TARGET_CHAT,
                            f"[Gigi] Shift FILLED: {info.get('client_name', 'client')} now covered by {winner}. "
                            f"(was: {info.get('caregiver_name', 'unknown')})"
                        )
                    except Exception:
                        pass
                    completed.append(campaign_id)

                elif not data.get("escalated"):
                    # Check if campaign has been running too long
                    started_at = datetime.fromisoformat(info["started_at"])
                    elapsed_min = (datetime.utcnow() - started_at).total_seconds() / 60

                    if elapsed_min >= CAMPAIGN_ESCALATION_MINUTES:
                        logger.warning(f"Campaign {campaign_id} unfilled after {elapsed_min:.0f} min — escalating")
                        try:
                            self.rc_service.send_message_to_chat(
                                TARGET_CHAT,
                                f"[Gigi] URGENT: Shift for {info.get('client_name', 'client')} still unfilled after "
                                f"{int(elapsed_min)} min. {data.get('total_contacted', 0)} contacted, "
                                f"{data.get('total_responded', 0)} responded. Manual action needed."
                            )
                        except Exception:
                            pass
                        completed.append(campaign_id)  # Stop tracking to avoid repeat notifications

            except Exception as e:
                logger.error(f"Campaign status check error for {campaign_id}: {e}")

        for cid in completed:
            self._active_campaigns.pop(cid, None)

        # Trigger voice follow-up calls for non-responding caregivers
        if VOICE_OUTREACH_ENABLED:
            try:
                resp = http_requests.post(
                    "http://localhost:8765/api/internal/shift-filling/voice-followups",
                    timeout=15
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("calls_made", 0) > 0:
                        logger.info(f"Voice follow-ups initiated: {data['calls_made']} calls")
            except Exception as e:
                logger.error(f"Voice followup check error: {e}")

    # =========================================================================
    # Claude SMS Conversation History
    # =========================================================================

    def _clean_phone(self, phone: str) -> str:
        """Normalize phone to last 10 digits."""
        return ''.join(filter(str.isdigit, phone))[-10:]

    # =========================================================================
    # SMS Tool Execution
    # =========================================================================

    def _execute_sms_tool(self, tool_name: str, tool_input: dict, caller_phone: str = None) -> str:
        """Execute a tool call and return the result as a JSON string"""
        try:
            if tool_name == "get_client_current_status":
                return self._get_client_current_status(tool_input.get("client_name", ""))

            elif tool_name == "identify_caller":
                phone = tool_input.get("phone_number", caller_phone or "")
                # Use fast SQL lookup (checks all 4 tables: staff, practitioners, patients, family)
                try:
                    from services.wellsky_fast_lookup import (
                        identify_caller as fast_identify,
                    )
                    caller = fast_identify(phone)
                    if caller:
                        caller_type = caller.get('type', 'unknown')
                        # Map type to identified_as value
                        type_map = {
                            'practitioner': 'caregiver',
                            'patient': 'client',
                            'staff': 'staff',
                            'family': 'family'
                        }
                        result = {
                            "identified_as": type_map.get(caller_type, caller_type),
                            "id": caller.get('id', ''),
                            "name": caller.get('full_name', caller.get('name', '')),
                            "first_name": caller.get('first_name', ''),
                            "status": caller.get('status', caller.get('role', ''))
                        }
                        # Add extra context for family members
                        if caller_type == 'family':
                            result["relationship"] = caller.get('relationship', '')
                            result["client_name"] = caller.get('client_name', '')
                            result["patient_id"] = caller.get('patient_id', '')
                        return json.dumps(result)
                except Exception as e:
                    logger.warning(f"Fast caller ID failed, trying fallback: {e}")

                # Fallback to WellSky API if fast lookup fails
                try:
                    cg = self.wellsky.get_caregiver_by_phone(phone)
                    if cg:
                        return json.dumps({
                            "identified_as": "caregiver",
                            "id": cg.id,
                            "name": cg.full_name,
                            "first_name": cg.first_name,
                            "status": cg.status.value if hasattr(cg.status, 'value') else str(cg.status)
                        })
                except Exception:
                    pass

                return json.dumps({"identified_as": "unknown", "message": "Phone number not found in records"})

            elif tool_name == "get_wellsky_shifts":
                days = min(tool_input.get("days", 7), 14)
                client_id = tool_input.get("client_id")
                caregiver_id = tool_input.get("caregiver_id")
                date_from = date.today()
                date_to = date.today() + timedelta(days=days)

                shifts = self.wellsky.get_shifts(
                    date_from=date_from, date_to=date_to,
                    client_id=client_id, caregiver_id=caregiver_id,
                    limit=20
                )
                shift_list = []
                for s in shifts[:10]:
                    shift_list.append({
                        "date": s.date.isoformat() if hasattr(s, 'date') and s.date else "unknown",
                        "day": s.date.strftime("%a") if hasattr(s, 'date') and s.date else "",
                        "time": f"{s.start_time}-{s.end_time}" if hasattr(s, 'start_time') and s.start_time else "TBD",
                        "client": s.client_name if hasattr(s, 'client_name') else "",
                        "caregiver": s.caregiver_name if hasattr(s, 'caregiver_name') else "",
                        "caregiver_id": s.caregiver_id if hasattr(s, 'caregiver_id') else "",
                        "client_id": s.client_id if hasattr(s, 'client_id') else "",
                        "status": s.status.value if hasattr(s.status, 'value') else str(s.status) if hasattr(s, 'status') else ""
                    })
                # Enrich with names from cached database when WellSky API returns blanks
                conn = None
                try:
                    import psycopg2
                    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
                    conn = psycopg2.connect(db_url)
                    cur = conn.cursor()
                    for shift in shift_list:
                        if shift.get("caregiver_id") and not shift.get("caregiver"):
                            cur.execute("SELECT full_name FROM cached_practitioners WHERE id = %s", (shift["caregiver_id"],))
                            row = cur.fetchone()
                            if row:
                                shift["caregiver"] = row[0]
                        if shift.get("client_id") and not shift.get("client"):
                            cur.execute("SELECT full_name FROM cached_patients WHERE id = %s", (shift["client_id"],))
                            row = cur.fetchone()
                            if row:
                                shift["client"] = row[0]
                except Exception as e:
                    logger.warning(f"Shift name enrichment failed (non-fatal): {e}")
                finally:
                    if conn:
                        conn.close()
                return json.dumps({"count": len(shifts), "shifts": shift_list})

            elif tool_name == "get_wellsky_clients":
                # Use cached database for reliable client lookup (synced daily from WellSky)
                import psycopg2
                db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
                search_name = tool_input.get("search_name", "")
                conn = None
                try:
                    conn = psycopg2.connect(db_url)
                    cur = conn.cursor()
                    if search_name:
                        search_lower = f"%{search_name.lower()}%"
                        cur.execute("""SELECT id, full_name, phone FROM cached_patients
                                      WHERE is_active = true AND (lower(full_name) LIKE %s
                                      OR lower(first_name) LIKE %s OR lower(last_name) LIKE %s)
                                      ORDER BY full_name LIMIT 10""",
                                   (search_lower, search_lower, search_lower))
                    else:
                        cur.execute("SELECT id, full_name, phone FROM cached_patients WHERE is_active = true ORDER BY full_name LIMIT 100")
                    rows = cur.fetchall()
                    client_list = [{"id": str(r[0]), "name": r[1], "phone": r[2] or ""} for r in rows]
                    return json.dumps({"count": len(client_list), "clients": client_list})
                except Exception as e:
                    logger.error(f"Client cache lookup failed: {e}")
                    return json.dumps({"error": f"Client lookup failed: {str(e)}"})
                finally:
                    if conn:
                        conn.close()

            elif tool_name == "get_wellsky_caregivers":
                # Use cached database for reliable caregiver lookup (synced daily from WellSky)
                import psycopg2
                db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
                search_name = tool_input.get("search_name", "")
                conn = None
                try:
                    conn = psycopg2.connect(db_url)
                    cur = conn.cursor()
                    if search_name:
                        search_lower = f"%{search_name.lower()}%"
                        cur.execute("""SELECT id, full_name, phone FROM cached_practitioners
                                      WHERE is_active = true AND (lower(full_name) LIKE %s
                                      OR lower(first_name) LIKE %s OR lower(last_name) LIKE %s)
                                      ORDER BY full_name LIMIT 10""",
                                   (search_lower, search_lower, search_lower))
                    else:
                        cur.execute("SELECT id, full_name, phone FROM cached_practitioners WHERE is_active = true ORDER BY full_name LIMIT 100")
                    rows = cur.fetchall()
                    cg_list = [{"id": str(r[0]), "name": r[1], "phone": r[2] or ""} for r in rows]
                    return json.dumps({"count": len(cg_list), "caregivers": cg_list})
                except Exception as e:
                    logger.error(f"Caregiver cache lookup failed: {e}")
                    return json.dumps({"error": f"Caregiver lookup failed: {str(e)}"})
                finally:
                    if conn:
                        conn.close()

            elif tool_name == "log_call_out":
                caregiver_id = tool_input.get("caregiver_id")
                caregiver_name = tool_input.get("caregiver_name", "Unknown")
                reason = tool_input.get("reason", "not specified")
                shift_date = tool_input.get("shift_date", date.today().isoformat())

                self.wellsky.create_admin_task(
                    title=f"CALL-OUT: {caregiver_name} - {reason}",
                    description=(
                        f"Caregiver {caregiver_name} called out via SMS.\n"
                        f"Reason: {reason}\n"
                        f"Shift date: {shift_date}\n"
                        f"ACTION: Find coverage immediately."
                    ),
                    priority="urgent",
                    related_caregiver_id=caregiver_id
                )
                return json.dumps({"success": True, "message": f"Call-out logged for {caregiver_name}. Admin task created."})

            elif tool_name == "save_memory":
                if not RC_MEMORY_AVAILABLE or not _rc_memory_system:
                    return json.dumps({"error": "Memory system not available"})
                content = tool_input.get("content", "")
                category = tool_input.get("category", "general")
                importance = tool_input.get("importance", "medium")
                impact_map = {"high": ImpactLevel.HIGH, "medium": ImpactLevel.MEDIUM, "low": ImpactLevel.LOW}
                memory_id = _rc_memory_system.create_memory(
                    content=content, memory_type=MemoryType.EXPLICIT_INSTRUCTION,
                    source=MemorySource.EXPLICIT, confidence=1.0,
                    category=category, impact_level=impact_map.get(importance, ImpactLevel.MEDIUM)
                )
                return json.dumps({"saved": True, "memory_id": memory_id, "content": content})

            elif tool_name == "recall_memories":
                if not RC_MEMORY_AVAILABLE or not _rc_memory_system:
                    return json.dumps({"memories": [], "message": "Memory system not available"})
                category = tool_input.get("category")
                search_text = tool_input.get("search_text")
                memories = _rc_memory_system.query_memories(category=category, min_confidence=0.3, limit=10)
                if search_text:
                    search_lower = search_text.lower()
                    memories = [m for m in memories if search_lower in m.content.lower()]
                results = [{"id": m.id, "content": m.content, "category": m.category,
                           "confidence": float(m.confidence), "type": m.type.value} for m in memories]
                return json.dumps({"memories": results, "count": len(results)})

            elif tool_name == "forget_memory":
                if not RC_MEMORY_AVAILABLE or not _rc_memory_system:
                    return json.dumps({"error": "Memory system not available"})
                memory_id = tool_input.get("memory_id", "")
                memory = _rc_memory_system.get_memory(memory_id)
                if not memory:
                    return json.dumps({"error": f"Memory {memory_id} not found"})
                with _rc_memory_system._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE gigi_memories SET status = 'archived' WHERE id = %s", (memory_id,))
                        _rc_memory_system._log_event(cur, memory_id, "archived", memory.confidence, memory.confidence, "User requested forget")
                    conn.commit()
                return json.dumps({"archived": True, "memory_id": memory_id, "content": memory.content})

            elif tool_name == "search_memory_logs":
                from gigi.memory_logger import MemoryLogger
                ml = MemoryLogger()
                query = tool_input.get("query", "")
                days_back = tool_input.get("days_back", 30)
                results = ml.search_logs(query, days_back=days_back)
                return json.dumps({"query": query, "results": results[:10], "total": len(results)})

            elif tool_name == "get_morning_briefing":
                from gigi.morning_briefing_service import MorningBriefingService
                svc = MorningBriefingService()
                return svc.generate_briefing()

            elif tool_name == "get_ar_report":
                from sales.quickbooks_service import QuickBooksService
                qb = QuickBooksService()
                if not qb.load_tokens_from_db():
                    return json.dumps({"error": "QuickBooks not connected. Visit https://portal.coloradocareassist.com/auth/quickbooks to authorize."})
                detail_level = tool_input.get("detail_level", "summary")
                result = qb.generate_ar_report(detail_level)
                if result.get("success"):
                    return result["report"]
                return json.dumps(result)

            elif tool_name == "deep_research":
                question = tool_input.get("question", "")
                try:
                    import httpx
                    with httpx.Client(timeout=150.0) as client:
                        resp = client.post(
                            "http://localhost:3002/api/research/deep",
                            json={"question": question}
                        )
                        data = resp.json()
                        answer = data.get("answer", "Research unavailable.")
                        confidence = data.get("confidence", 0)
                        tools_used = data.get("metadata", {}).get("tools_used", [])
                        duration = data.get("metadata", {}).get("total_duration_seconds", 0)
                        return f"{answer}\n\n---\nConfidence: {confidence:.0%} | Data sources: {len(tools_used)} | Research time: {duration:.0f}s"
                except Exception as e:
                    logger.error(f"Deep research failed: {e}")
                    return json.dumps({"error": f"Elite Trading research unavailable: {e}"})

            elif tool_name == "get_weather_arb_status":
                try:
                    import httpx
                    result = {"polymarket": {"status": "offline"}, "kalshi": {"status": "offline"}}
                    with httpx.Client(timeout=15.0) as client:
                        try:
                            status_resp = client.get("http://127.0.0.1:3010/status")
                            pnl_resp = client.get("http://127.0.0.1:3010/pnl")
                            poly = {"status": "online"}
                            if status_resp.status_code == 200:
                                st = status_resp.json()
                                sniper = st.get("sniper", {})
                                poly["running"] = bool(st.get("running"))
                                poly["scans"] = sniper.get("scan_count", 0)
                            if pnl_resp.status_code == 200:
                                data = pnl_resp.json()
                                poly["portfolio_value"] = data.get("portfolio_value", 0)
                                poly["cash"] = data.get("cash", 0)
                                poly["unrealized_pnl"] = data.get("unrealized_pnl", 0)
                                poly["num_positions"] = len(data.get("positions", []))
                                poly["positions"] = [
                                    {"title": p.get("title", "?")[:60], "pnl": round(p.get("pnl", 0), 2), "pnl_pct": round(p.get("pnl_pct", 0), 1)}
                                    for p in data.get("positions", [])[:10]
                                ]
                            result["polymarket"] = poly
                        except Exception:
                            pass
                        try:
                            kalshi_resp = client.get("http://127.0.0.1:3011/pnl")
                            if kalshi_resp.status_code == 200:
                                data = kalshi_resp.json()
                                result["kalshi"] = {
                                    "status": "online",
                                    "portfolio_value": data.get("portfolio_value", 0),
                                    "cash": data.get("cash", 0),
                                    "unrealized_pnl": data.get("unrealized_pnl", 0),
                                    "num_positions": len(data.get("positions", [])),
                                    "positions": [
                                        {"ticker": p.get("ticker", "?"), "count": p.get("count", 0), "pnl": round(p.get("pnl", 0), 2)}
                                        for p in data.get("positions", [])[:10]
                                    ]
                                }
                        except Exception:
                            pass
                    return json.dumps(result)
                except Exception as e:
                    logger.error(f"Weather arb status failed: {e}")
                    return json.dumps({"error": f"Weather bots unavailable: {str(e)}"})

            elif tool_name == "watch_tickets":
                from gigi.ticket_monitor import create_watch
                result = create_watch(tool_input.get("artist", ""), tool_input.get("venue"), tool_input.get("city", "Denver"))
                return json.dumps(result)

            elif tool_name == "list_ticket_watches":
                from gigi.ticket_monitor import list_watches
                return json.dumps(list_watches())

            elif tool_name == "remove_ticket_watch":
                from gigi.ticket_monitor import remove_watch
                return json.dumps(remove_watch(int(tool_input.get("watch_id", 0))))

            elif tool_name == "clock_in_shift":
                appointment_id = tool_input.get("appointment_id", "")
                caregiver_name = tool_input.get("caregiver_name", "")
                notes = tool_input.get("notes", "Clocked in via Gigi SMS")
                if not appointment_id:
                    return json.dumps({"error": "Missing appointment_id. Use get_wellsky_shifts first."})
                try:
                    from services.wellsky_service import WellSkyService
                    ws = WellSkyService()
                    success, message = ws.clock_in_shift(appointment_id, notes=notes)
                    return json.dumps({"success": success, "message": message, "appointment_id": appointment_id, "caregiver_name": caregiver_name})
                except Exception as e:
                    return json.dumps({"error": f"Clock-in failed: {str(e)}"})

            elif tool_name == "clock_out_shift":
                appointment_id = tool_input.get("appointment_id", "")
                caregiver_name = tool_input.get("caregiver_name", "")
                notes = tool_input.get("notes", "Clocked out via Gigi SMS")
                if not appointment_id:
                    return json.dumps({"error": "Missing appointment_id. Use get_wellsky_shifts first."})
                try:
                    from services.wellsky_service import WellSkyService
                    ws = WellSkyService()
                    success, message = ws.clock_out_shift(appointment_id, notes=notes)
                    return json.dumps({"success": success, "message": message, "appointment_id": appointment_id, "caregiver_name": caregiver_name})
                except Exception as e:
                    return json.dumps({"error": f"Clock-out failed: {str(e)}"})

            elif tool_name == "find_replacement_caregiver":
                shift_id = tool_input.get("shift_id", "")
                original_caregiver_id = tool_input.get("original_caregiver_id", "")
                reason = tool_input.get("reason", "called out")
                if not shift_id or not original_caregiver_id:
                    return json.dumps({"error": "Missing shift_id or original_caregiver_id"})
                try:
                    from sales.shift_filling.engine import shift_filling_engine
                    campaign = shift_filling_engine.process_calloff(
                        shift_id=shift_id, caregiver_id=original_caregiver_id,
                        reason=reason, reported_by="gigi_sms"
                    )
                    if not campaign:
                        return json.dumps({"success": False, "error": "Could not create replacement campaign"})
                    return json.dumps({
                        "success": True, "campaign_id": campaign.id,
                        "status": campaign.status.value if hasattr(campaign.status, 'value') else str(campaign.status),
                        "caregivers_contacted": campaign.total_contacted,
                        "message": f"Replacement search started. Contacting {campaign.total_contacted} caregivers via SMS."
                    })
                except ImportError:
                    return json.dumps({"error": "Shift filling engine not available"})
                except Exception as e:
                    return json.dumps({"error": f"Shift filling failed: {str(e)}"})

            elif tool_name == "get_task_board":
                try:
                    with open(os.path.expanduser("~/Task Board.md"), "r") as f:
                        return json.dumps({"task_board": f.read()})
                except FileNotFoundError:
                    return json.dumps({"task_board": "(empty)"})

            elif tool_name == "add_task":
                task_text = tool_input.get("task", "").strip()
                section = tool_input.get("section", "Today").strip()
                if not task_text:
                    return json.dumps({"error": "No task text provided"})
                valid_sections = ["Today", "Soon", "Later", "Waiting", "Agenda", "Inbox", "Reference"]
                section_match = next((s for s in valid_sections if s.lower() == section.lower()), "Today")
                path = os.path.expanduser("~/Task Board.md")
                try:
                    with open(path, "r") as f:
                        content = f.read()
                    marker = f"## {section_match}\n"
                    if marker in content:
                        idx = content.index(marker) + len(marker)
                        rest = content[idx:]
                        if rest.startswith("-\n") or rest.startswith("- \n"):
                            content = content[:idx] + f"- [ ] {task_text}\n" + rest[rest.index("\n") + 1:]
                        else:
                            content = content[:idx] + f"- [ ] {task_text}\n" + rest
                    else:
                        content += f"\n## {section_match}\n- [ ] {task_text}\n"
                    with open(path, "w") as f:
                        f.write(content)
                    return json.dumps({"success": True, "task": task_text, "section": section_match})
                except Exception as e:
                    return json.dumps({"error": f"Failed: {str(e)}"})

            elif tool_name == "complete_task":
                task_text = tool_input.get("task_text", "").strip().lower()
                if not task_text:
                    return json.dumps({"error": "No task text provided"})
                try:
                    path = os.path.expanduser("~/Task Board.md")
                    with open(path, "r") as f:
                        lines = f.readlines()
                    completed = False
                    completed_task = ""
                    new_lines = []
                    for line in lines:
                        if not completed and "- [ ]" in line and task_text in line.lower():
                            completed_task = line.replace("- [ ]", "- [x]").strip()
                            completed = True
                        else:
                            new_lines.append(line)
                    if not completed:
                        return json.dumps({"error": f"No uncompleted task matching '{task_text}'"})
                    content = "".join(new_lines)
                    done_marker = "## Done\n"
                    if done_marker in content:
                        idx = content.index(done_marker) + len(done_marker)
                        rest = content[idx:]
                        if rest.startswith("-\n") or rest.startswith("- \n"):
                            content = content[:idx] + completed_task + "\n" + rest[rest.index("\n") + 1:]
                        else:
                            content = content[:idx] + completed_task + "\n" + rest
                    else:
                        content += f"\n## Done\n{completed_task}\n"
                    with open(path, "w") as f:
                        f.write(content)
                    return json.dumps({"success": True, "completed": completed_task})
                except Exception as e:
                    return json.dumps({"error": f"Failed: {str(e)}"})

            elif tool_name == "capture_note":
                note = tool_input.get("note", "").strip()
                if not note:
                    return json.dumps({"error": "No note provided"})
                path = os.path.expanduser("~/Scratchpad.md")
                try:
                    try:
                        with open(path, "r") as f:
                            content = f.read()
                    except FileNotFoundError:
                        content = "# Scratchpad\n\n---\n"
                    from datetime import datetime as dt
                    timestamp = dt.now().strftime("%I:%M %p")
                    content = content.rstrip() + f"\n- {note} ({timestamp})\n"
                    with open(path, "w") as f:
                        f.write(content)
                    return json.dumps({"success": True, "note": note})
                except Exception as e:
                    return json.dumps({"error": f"Failed: {str(e)}"})

            elif tool_name == "get_daily_notes":
                target_date = tool_input.get("date", "")
                try:
                    import glob as g
                    import re as _re
                    from datetime import datetime as dt
                    d = target_date if _re.match(r"^\d{4}-\d{2}-\d{2}$", target_date) else dt.now().strftime("%Y-%m-%d")
                    matches = g.glob(os.path.join(os.path.expanduser("~/Daily Notes"), f"{d}*"))
                    if matches:
                        with open(matches[0], "r") as f:
                            return json.dumps({"date": d, "notes": f.read()})
                    return json.dumps({"date": d, "notes": "(no daily notes for this date)"})
                except Exception as e:
                    return json.dumps({"error": f"Failed: {str(e)}"})

            else:
                # Delegate to Telegram bot for shared tools not natively handled
                try:
                    if not hasattr(self, '_shared_tele_bot'):
                        from gigi.telegram_bot import GigiTelegramBot
                        self._shared_tele_bot = GigiTelegramBot()
                    loop = asyncio.new_event_loop()
                    try:
                        result = loop.run_until_complete(
                            self._shared_tele_bot.execute_tool(tool_name, tool_input))
                    finally:
                        loop.close()
                    return result
                except Exception as e:
                    logger.error(f"Delegated SMS tool {tool_name} failed: {e}")
                    return json.dumps({"error": f"Tool '{tool_name}' is not available right now."})

        except Exception as e:
            logger.error(f"SMS tool error ({tool_name}): {e}")
            if RC_FAILURE_HANDLER_AVAILABLE and _rc_failure_handler:
                try:
                    _rc_failure_handler.handle_tool_failure(tool_name, e, {"tool_input": str(tool_input)[:200]})
                except Exception:
                    pass
            return json.dumps({"error": f"Tool {tool_name} failed: {str(e)}"})

    # =========================================================================
    # LLM SMS Reply Generation (Gemini or Anthropic)
    # =========================================================================

    async def _get_llm_sms_reply(self, text: str, phone: str) -> str:
        """Get an intelligent reply with tool calling. Returns reply text or None."""
        if not self.llm:
            return None

        now = datetime.now(TIMEZONE)
        system = SMS_SYSTEM_PROMPT.format(
            current_date=now.strftime("%A, %B %d, %Y at %I:%M %p MT"),
            caller_phone=phone
        )

        # Inject mode context and memories
        if RC_MODE_AVAILABLE and _rc_mode_detector:
            try:
                mode_info = _rc_mode_detector.get_current_mode()
                system += f"\n\nCurrent Operating Mode: {mode_info.mode.value.upper()} (source: {mode_info.source.value})"
            except Exception:
                pass

        if RC_MEMORY_AVAILABLE and _rc_memory_system:
            try:
                memories = _rc_memory_system.query_memories(min_confidence=0.5, limit=15)
                if memories:
                    memory_lines = [f"- {m.content} ({m.category})" for m in memories]
                    system += "\n\nYour Saved Memories:\n" + "\n".join(memory_lines)
            except Exception:
                pass

        # Retrieve conversation history from PostgreSQL (user message stored after LLM success)
        clean_phone = self._clean_phone(phone)
        conv_history = self.conversation_store.get_recent(
            clean_phone, "sms", limit=MAX_CONVERSATION_MESSAGES,
            timeout_minutes=CONVERSATION_TIMEOUT_MINUTES
        )
        # Append user message to history for LLM context (not yet persisted)
        conv_history.append({"role": "user", "content": text})

        # Inject cross-channel context if this is Jason
        if clean_phone in ("3074598220",):
            xc = self.conversation_store.get_cross_channel_summary("jason", "sms", limit=5, hours=24)
            if xc:
                system += xc

        try:
            if self.llm_provider == "gemini":
                final_text = await self._call_gemini(system, conv_history, GEMINI_SMS_TOOLS,
                                                     lambda name, inp: self._execute_sms_tool(name, inp, caller_phone=phone),
                                                     "SMS")
            else:
                final_text = await self._call_anthropic(system, conv_history, SMS_TOOLS,
                                                        lambda name, inp: self._execute_sms_tool(name, inp, caller_phone=phone),
                                                        "SMS")

            if not final_text:
                final_text = "Thanks for your message. I'll have the office follow up with you shortly."

            # Strip hallucinated CLI/install suggestions (Gemini keeps adding these)
            from gigi.response_filter import strip_banned_content
            final_text = strip_banned_content(final_text)

            # Persist both user message and assistant reply only after LLM success
            self.conversation_store.append(clean_phone, "sms", "user", text)
            self.conversation_store.append(clean_phone, "sms", "assistant", final_text)
            return final_text

        except Exception as e:
            logger.error(f"LLM SMS reply error ({self.llm_provider}): {e}", exc_info=True)
            return None

    # =========================================================================
    # LLM Glip DM Reply Generation (Gemini or Anthropic)
    # =========================================================================

    async def _get_llm_dm_reply(self, text: str, sender_name: str, chat_id: str) -> str:
        """Get an intelligent reply for Glip DMs. Uses Chief of Staff prompt."""
        if not self.llm:
            return None

        now = datetime.now(TIMEZONE)
        system = GLIP_DM_SYSTEM_PROMPT.format(
            sender_name=sender_name,
            current_date=now.strftime("%A, %B %d, %Y at %I:%M %p MT"),
        )

        # Inject mode context and memories
        if RC_MODE_AVAILABLE and _rc_mode_detector:
            try:
                mode_info = _rc_mode_detector.get_current_mode()
                system += f"\n\nCurrent Operating Mode: {mode_info.mode.value.upper()} (source: {mode_info.source.value})"
            except Exception:
                pass

        if RC_MEMORY_AVAILABLE and _rc_memory_system:
            try:
                memories = _rc_memory_system.query_memories(min_confidence=0.5, limit=25)
                if memories:
                    memory_lines = [f"- {m.content} (confidence: {m.confidence:.0%}, category: {m.category})" for m in memories]
                    system += "\n\nYour Saved Memories:\n" + "\n".join(memory_lines)
            except Exception:
                pass

        # Inject cross-channel context (what Jason discussed on other channels recently)
        try:
            xc = self.conversation_store.get_cross_channel_summary("jason", "dm", limit=5, hours=24)
            if xc:
                system += xc
            # Long-term conversation history (summaries from past 30 days)
            ltc = self.conversation_store.get_long_term_context("jason", days=30)
            if ltc:
                system += ltc
        except Exception:
            pass

        # Inject elite team context if triggered
        try:
            from gigi.elite_teams import detect_team, get_team_context
            team_key = detect_team(text)
            if team_key:
                system += get_team_context(team_key)
                logger.info(f"Elite team activated in DM: {team_key}")
        except Exception:
            pass

        # Retrieve DM conversation history from PostgreSQL (user message stored after LLM success)
        dm_user_id = f"dm_{chat_id}"
        conv_history = self.conversation_store.get_recent(
            dm_user_id, "dm", limit=MAX_CONVERSATION_MESSAGES,
            timeout_minutes=CONVERSATION_TIMEOUT_MINUTES
        )
        # Append user message to history for LLM context (not yet persisted)
        conv_history.append({"role": "user", "content": text})

        try:
            if self.llm_provider == "gemini":
                final_text = await self._call_gemini(system, conv_history, GEMINI_DM_TOOLS,
                                                     lambda name, inp: self._execute_dm_tool(name, inp),
                                                     "DM")
            else:
                final_text = await self._call_anthropic(system, conv_history, DM_TOOLS,
                                                        lambda name, inp: self._execute_dm_tool(name, inp),
                                                        "DM")

            if not final_text:
                final_text = "I checked our records but couldn't find the specific information. Please text or call the office for assistance."

            # Strip hallucinated CLI/install suggestions (Gemini keeps adding these)
            from gigi.response_filter import strip_banned_content
            final_text = strip_banned_content(final_text)

            # Persist both user message and assistant reply only after LLM success
            self.conversation_store.append(dm_user_id, "dm", "user", text)
            self.conversation_store.append(dm_user_id, "dm", "assistant", final_text)
            logger.info(f"LLM DM reply to {sender_name} ({self.llm_provider}, {len(final_text)} chars)")
            return final_text

        except Exception as e:
            logger.error(f"LLM DM reply error ({self.llm_provider}): {e}", exc_info=True)
            # Only clear conversation on history-corruption errors (e.g., Anthropic 400),
            # NOT on transient errors (timeouts, rate limits, network issues)
            err_str = str(e).lower()
            if "400" in err_str or "invalid" in err_str or "malformed" in err_str:
                logger.warning(f"Clearing corrupted DM history for {dm_user_id}")
                self.conversation_store.clear_channel(dm_user_id, "dm")
            return None

    # =========================================================================
    # Gemini Provider — tool calling loop
    # =========================================================================

    async def _call_gemini(self, system_prompt: str, conv_history: list, tools, tool_executor, channel: str) -> str:
        """Call Gemini with tool support. conv_history is text-only [{role, content}]."""
        # Build Gemini-format contents from text-only history (skip non-text entries from old format)
        contents = []
        for m in conv_history:
            content_val = m.get("content", "")
            if not isinstance(content_val, str):
                continue  # Skip old tool_use/tool_result list entries
            role = "user" if m["role"] == "user" else "model"
            contents.append(genai_types.Content(
                role=role,
                parts=[genai_types.Part(text=content_val)]
            ))

        config = genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=tools,
        )

        response = await asyncio.to_thread(
            self.llm.models.generate_content,
            model=LLM_MODEL, contents=contents, config=config
        )

        tool_round = 0
        for _ in range(LLM_MAX_TOOL_ROUNDS):
            # Check if response has function calls
            function_calls = []
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        function_calls.append(part)

            if not function_calls:
                break

            tool_round += 1
            logger.info(f"{channel} Gemini tool round {tool_round}")

            # Add model's response to contents
            contents.append(response.candidates[0].content)

            # Execute each tool and build function response parts
            fn_response_parts = []
            for part in function_calls:
                fc = part.function_call
                tool_input = dict(fc.args) if fc.args else {}
                logger.info(f"  Tool: {fc.name}({json.dumps(tool_input)[:100]})")

                # tool_executor may be sync or async (lambda wrapping async)
                result_str = tool_executor(fc.name, tool_input)
                if asyncio.iscoroutine(result_str):
                    result_str = await result_str
                logger.info(f"  Result: {result_str[:200]}")

                try:
                    result_data = json.loads(result_str)
                except (json.JSONDecodeError, TypeError):
                    result_data = {"result": result_str}

                fn_response_parts.append(
                    genai_types.Part.from_function_response(
                        name=fc.name, response=result_data
                    )
                )

            contents.append(genai_types.Content(role="user", parts=fn_response_parts))

            response = await asyncio.to_thread(
                self.llm.models.generate_content,
                model=LLM_MODEL, contents=contents, config=config
            )

        # Extract final text
        text_parts = []
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    text_parts.append(part.text)

        final_text = "".join(text_parts)

        # If exhausted tool rounds without generating text, force a summary call WITHOUT tools
        if not final_text and tool_round >= LLM_MAX_TOOL_ROUNDS:
            logger.info(f"{channel} Gemini exhausted {tool_round} tool rounds with no text — forcing summary")
            # Ask Gemini to summarize what it found, with NO tools to prevent more function calls
            contents.append(genai_types.Content(
                role="user",
                parts=[genai_types.Part(text="Based on all the tool results above, please give a direct, complete answer to the original question. Be concise.")]
            ))
            summary_config = genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                # No tools — force text-only response
            )
            try:
                summary_response = await asyncio.to_thread(
                    self.llm.models.generate_content,
                    model=LLM_MODEL, contents=contents, config=summary_config
                )
                if summary_response.candidates and summary_response.candidates[0].content and summary_response.candidates[0].content.parts:
                    for part in summary_response.candidates[0].content.parts:
                        if hasattr(part, 'text') and part.text:
                            text_parts.append(part.text)
                    final_text = "".join(text_parts)
                    logger.info(f"{channel} Gemini forced summary: {len(final_text)} chars")
            except Exception as e:
                logger.error(f"{channel} Gemini forced summary failed: {e}")

        logger.info(f"{channel} Gemini reply ({tool_round} tool rounds, {len(final_text)} chars)")
        return final_text

    # =========================================================================
    # Anthropic Provider — tool calling loop (fallback)
    # =========================================================================

    async def _call_anthropic(self, system_prompt: str, conv_history: list, tools, tool_executor, channel: str) -> str:
        """Call Anthropic Claude with tool support. conv_history is text-only [{role, content}]."""
        # Build Anthropic-format messages from text-only history (skip non-text entries from old format)
        messages = [{"role": m["role"], "content": m["content"]}
                    for m in conv_history if isinstance(m.get("content"), str)]

        response = await asyncio.to_thread(
            self.llm.messages.create,
            model=LLM_MODEL, max_tokens=LLM_MAX_TOKENS,
            system=system_prompt, tools=tools,
            messages=messages
        )

        tool_round = 0
        while response.stop_reason == "tool_use" and tool_round < LLM_MAX_TOOL_ROUNDS:
            tool_round += 1
            logger.info(f"{channel} Anthropic tool round {tool_round}")

            tool_results = []
            assistant_content = []

            for block in response.content:
                if block.type == "tool_use":
                    logger.info(f"  Tool: {block.name}({json.dumps(block.input)[:100]})")

                    result = tool_executor(block.name, block.input)
                    if asyncio.iscoroutine(result):
                        result = await result
                    logger.info(f"  Result: {result[:200]}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
                    assistant_content.append({
                        "type": "tool_use", "id": block.id,
                        "name": block.name, "input": block.input
                    })
                elif block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

            response = await asyncio.to_thread(
                self.llm.messages.create,
                model=LLM_MODEL, max_tokens=LLM_MAX_TOKENS,
                system=system_prompt, tools=tools,
                messages=messages
            )

        final_text = "".join(b.text for b in response.content if b.type == "text")

        # If exhausted tool rounds without generating text, force a summary
        if not final_text and tool_round >= LLM_MAX_TOOL_ROUNDS:
            logger.info(f"{channel} Anthropic exhausted {tool_round} tool rounds — forcing text summary")
            messages.append({"role": "assistant", "content": [{"type": "text", "text": "Based on the information I've gathered, let me summarize:"}]})
            messages.append({"role": "user", "content": "Please summarize what you found from the tools you just called. Give a direct, complete answer."})
            summary_response = await asyncio.to_thread(
                self.llm.messages.create,
                model=LLM_MODEL, max_tokens=LLM_MAX_TOKENS,
                system=system_prompt, messages=messages
            )
            final_text = "".join(b.text for b in summary_response.content if b.type == "text")

        logger.info(f"{channel} Anthropic reply ({tool_round} tool rounds, {len(final_text)} chars)")
        return final_text

    # =========================================================================
    # DM Tool Execution (full tool set matching Telegram capabilities)
    # =========================================================================

    async def _execute_dm_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a DM tool — full feature parity with Telegram bot."""
        import psycopg2
        db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")

        try:
            if tool_name == "get_client_current_status":
                return self._get_client_current_status(tool_input.get("client_name", ""))

            elif tool_name == "get_wellsky_clients":
                search_name = tool_input.get("search_name", "")
                active_only = tool_input.get("active_only", True)
                conn = None
                try:
                    conn = psycopg2.connect(db_url)
                    cur = conn.cursor()
                    if search_name:
                        search_lower = f"%{search_name.lower()}%"
                        sql = """SELECT id, first_name, last_name, full_name, phone, home_phone, email
                                 FROM cached_patients WHERE (lower(full_name) LIKE %s
                                 OR lower(first_name) LIKE %s OR lower(last_name) LIKE %s)"""
                        params = [search_lower, search_lower, search_lower]
                        if active_only:
                            sql += " AND is_active = true"
                        sql += " ORDER BY full_name LIMIT 20"
                        cur.execute(sql, params)
                    else:
                        sql = "SELECT id, first_name, last_name, full_name, phone, home_phone, email FROM cached_patients"
                        if active_only:
                            sql += " WHERE is_active = true"
                        sql += " ORDER BY full_name LIMIT 100"
                        cur.execute(sql)
                    rows = cur.fetchall()
                    clients = [{"id": str(r[0]), "name": r[3], "phone": r[4] or r[5] or ""} for r in rows]
                    return json.dumps({"count": len(clients), "clients": clients})
                finally:
                    if conn:
                        conn.close()

            elif tool_name == "get_wellsky_caregivers":
                search_name = tool_input.get("search_name", "")
                active_only = tool_input.get("active_only", True)
                conn = None
                try:
                    conn = psycopg2.connect(db_url)
                    cur = conn.cursor()
                    if search_name:
                        search_lower = f"%{search_name.lower()}%"
                        sql = """SELECT id, first_name, last_name, full_name, phone, home_phone, email
                                 FROM cached_practitioners WHERE (lower(full_name) LIKE %s
                                 OR lower(first_name) LIKE %s OR lower(last_name) LIKE %s)"""
                        params = [search_lower, search_lower, search_lower]
                        if active_only:
                            sql += " AND is_active = true"
                        sql += " ORDER BY full_name LIMIT 20"
                        cur.execute(sql, params)
                    else:
                        sql = "SELECT id, first_name, last_name, full_name, phone, home_phone, email FROM cached_practitioners"
                        if active_only:
                            sql += " WHERE is_active = true"
                        sql += " ORDER BY full_name LIMIT 100"
                        cur.execute(sql)
                    rows = cur.fetchall()
                    caregivers = [{"id": str(r[0]), "name": r[3], "phone": r[4] or r[5] or ""} for r in rows]
                    return json.dumps({"count": len(caregivers), "caregivers": caregivers})
                finally:
                    if conn:
                        conn.close()

            elif tool_name == "get_wellsky_shifts":
                days = min(tool_input.get("days", 7), 30)
                past_days = min(tool_input.get("past_days", 0), 90)
                open_only = tool_input.get("open_only", False)
                client_id = tool_input.get("client_id")
                caregiver_id = tool_input.get("caregiver_id")
                if past_days > 0:
                    date_from = date.today() - timedelta(days=past_days)
                    date_to = date.today()
                else:
                    date_from = date.today()
                    date_to = date.today() + timedelta(days=days)
                conn = None
                try:
                    conn = psycopg2.connect(db_url)
                    cur = conn.cursor()
                    conditions = ["a.scheduled_start >= %s", "a.scheduled_start < %s"]
                    params = [date_from, date_to]
                    if client_id:
                        conditions.append("a.patient_id = %s")
                        params.append(client_id)
                    if caregiver_id:
                        conditions.append("a.practitioner_id = %s")
                        params.append(caregiver_id)
                    if open_only:
                        conditions.append("(a.practitioner_id IS NULL OR a.status IN ('open', 'pending', 'proposed'))")
                    where = " AND ".join(conditions)
                    cur.execute(f"""
                        SELECT a.id, a.scheduled_start, a.scheduled_end, a.status,
                               p.full_name as client_name, pr.full_name as caregiver_name
                        FROM cached_appointments a
                        LEFT JOIN cached_patients p ON a.patient_id = p.id
                        LEFT JOIN cached_practitioners pr ON a.practitioner_id = pr.id
                        WHERE {where} ORDER BY a.scheduled_start LIMIT 50
                    """, params)
                    shift_list = []
                    total_hours = 0
                    for row in cur.fetchall():
                        hours = round((row[2] - row[1]).total_seconds() / 3600, 1) if row[1] and row[2] else None
                        if hours:
                            total_hours += hours
                        shift_list.append({
                            "date": row[1].strftime("%a %m/%d") if row[1] else None,
                            "start": row[1].strftime("%I:%M %p") if row[1] else None,
                            "end": row[2].strftime("%I:%M %p") if row[2] else None,
                            "status": row[3], "client": row[4] or "Unknown",
                            "caregiver": row[5] or "Unassigned", "hours": hours
                        })
                    return json.dumps({"count": len(shift_list), "total_hours": round(total_hours, 1),
                                       "date_range": f"{date_from} to {date_to}", "shifts": shift_list})
                finally:
                    if conn:
                        conn.close()

            elif tool_name == "get_weather":
                location = tool_input.get("location", "")
                if not location:
                    return json.dumps({"error": "No location provided"})
                import httpx
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(f"https://wttr.in/{location}?format=j1")
                        if resp.status_code == 200:
                            w = resp.json()
                            current = w.get("current_condition", [{}])[0]
                            forecast = w.get("weather", [{}])[0]
                            area = w.get("nearest_area", [{}])[0].get("areaName", [{}])[0].get("value", location)
                            return json.dumps({"location": area, "temp_f": current.get("temp_F"),
                                "feels_like_f": current.get("FeelsLikeF"),
                                "description": current.get("weatherDesc", [{}])[0].get("value"),
                                "humidity": current.get("humidity"), "wind_mph": current.get("windspeedMiles"),
                                "high_f": forecast.get("maxtempF"), "low_f": forecast.get("mintempF")})
                except Exception as e:
                    logger.warning(f"Weather API failed: {e}")
                try:
                    from ddgs import DDGS
                    results = DDGS().text(f"current weather {location}", max_results=1)
                    if results:
                        return json.dumps({"location": location, "weather": results[0].get("body")})
                except Exception:
                    pass
                return json.dumps({"error": "Weather service temporarily unavailable"})

            elif tool_name == "web_search":
                query = tool_input.get("query", "")
                if not query:
                    return json.dumps({"error": "No search query provided"})
                try:
                    from ddgs import DDGS
                    results = DDGS().text(query, max_results=5)
                    if results:
                        formatted = [{"title": r.get("title", ""), "description": r.get("body", ""), "url": r.get("href", "")} for r in results]
                        return json.dumps({"query": query, "results": formatted})
                except Exception as e:
                    logger.warning(f"Web search failed: {e}")
                return json.dumps({"query": query, "message": "No results found."})

            elif tool_name == "get_stock_price":
                symbol = tool_input.get("symbol", "").upper()
                if not symbol:
                    return json.dumps({"error": "No stock symbol provided"})
                import httpx
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d",
                            headers={"User-Agent": "Mozilla/5.0 (CareAssist/1.0)"})
                        if resp.status_code == 200:
                            meta = resp.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                            price = meta.get("regularMarketPrice")
                            if price:
                                prev = meta.get("chartPreviousClose") or meta.get("previousClose", 0)
                                change = price - prev if prev else 0
                                pct = (change / prev * 100) if prev else 0
                                return json.dumps({"symbol": symbol, "price": f"${price:.2f}",
                                    "change": f"${change:+.2f}", "change_percent": f"{pct:+.2f}%"})
                except Exception as e:
                    logger.warning(f"Stock price error: {e}")
                return json.dumps({"error": f"Could not find stock price for {symbol}"})

            elif tool_name == "get_crypto_price":
                symbol = tool_input.get("symbol", "").upper()
                if not symbol:
                    return json.dumps({"error": "No crypto symbol provided"})
                crypto_map = {"BTC": "bitcoin", "BITCOIN": "bitcoin", "ETH": "ethereum",
                    "DOGE": "dogecoin", "SOL": "solana", "XRP": "ripple", "ADA": "cardano",
                    "AVAX": "avalanche-2", "LINK": "chainlink", "DOT": "polkadot"}
                coin_id = crypto_map.get(symbol, symbol.lower())
                import httpx
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true")
                        if resp.status_code == 200:
                            data = resp.json()
                            if coin_id in data:
                                info = data[coin_id]
                                return json.dumps({"symbol": symbol, "price": f"${info['usd']:,.2f}",
                                    "24h_change": f"{info.get('usd_24h_change', 0):+.2f}%"})
                except Exception as e:
                    logger.warning(f"Crypto price error: {e}")
                return json.dumps({"error": f"Could not find crypto price for {symbol}"})

            elif tool_name == "search_concerts":
                query = tool_input.get("query", "concerts in Denver")
                try:
                    from ddgs import DDGS
                    results = DDGS().text(f"{query} concerts tickets 2026", max_results=5)
                    if results:
                        formatted = [{"title": r.get("title", ""), "description": r.get("body", ""), "url": r.get("href", "")} for r in results]
                        return json.dumps({"query": query, "results": formatted})
                except Exception as e:
                    logger.warning(f"Concert search failed: {e}")
                return json.dumps({"query": query, "message": "No concert results found."})

            elif tool_name == "get_calendar_events":
                try:
                    from gigi.google_service import GoogleService
                    google = GoogleService()
                    if google.is_configured:
                        days = tool_input.get("days", 1)
                        events = google.get_calendar_events(days=min(days, 7))
                        return json.dumps({"events": events or [], "count": len(events or [])})
                except Exception as e:
                    logger.warning(f"Calendar error: {e}")
                return json.dumps({"error": "Google Calendar not available"})

            elif tool_name == "search_emails":
                try:
                    from gigi.google_service import GoogleService
                    google = GoogleService()
                    if google.is_configured:
                        query = tool_input.get("query", "is:unread")
                        max_results = tool_input.get("max_results", 5)
                        emails = google.search_emails(query=query, max_results=max_results)
                        return json.dumps({"emails": emails or [], "count": len(emails or [])})
                except Exception as e:
                    logger.warning(f"Email search error: {e}")
                return json.dumps({"error": "Gmail not available"})

            elif tool_name == "check_recent_sms":
                hours = min(tool_input.get("hours", 12), 48)
                filter_phone = tool_input.get("from_phone")
                token = self._get_admin_access_token()
                if not token:
                    return json.dumps({"error": "Could not get RingCentral access token"})
                try:
                    params = {
                        "messageType": "SMS",
                        "dateFrom": (datetime.utcnow() - timedelta(hours=hours)).isoformat(),
                        "perPage": 50,
                        "direction": "Inbound"
                    }
                    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
                    # Poll Gigi's extension + all company line extensions
                    all_records = []
                    for ext_info in [{"ext_id": "~", "label": "307"}] + COMPANY_LINE_EXTENSIONS:
                        try:
                            url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/{ext_info['ext_id']}/message-store"
                            resp = requests.get(url, headers=headers, params=params, timeout=15)
                            if resp.status_code == 200:
                                for r in resp.json().get("records", []):
                                    r["_line"] = ext_info["label"]
                                    all_records.append(r)
                        except Exception:
                            pass
                    sms_list = []
                    seen_ids = set()
                    for sms in all_records:
                        sms_id = str(sms.get("id", ""))
                        if sms_id in seen_ids:
                            continue
                        seen_ids.add(sms_id)
                        from_phone = sms.get("from", {}).get("phoneNumber", "")
                        if filter_phone and filter_phone not in from_phone:
                            continue
                        # Skip messages from our own numbers
                        own_numbers = [RINGCENTRAL_FROM_NUMBER, "+13074598220", "+17194283999", "+13037571777"]
                        if from_phone in own_numbers:
                            continue
                        to_phone = sms.get("to", [{}])[0].get("phoneNumber", "")
                        sms_list.append({
                            "from": from_phone,
                            "to": to_phone,
                            "line": sms.get("_line", ""),
                            "text": sms.get("subject", ""),
                            "time": sms.get("creationTime", ""),
                            "read_status": sms.get("readStatus", ""),
                        })
                    # Try to identify senders
                    for sms_item in sms_list:
                        try:
                            from services.wellsky_fast_lookup import (
                                identify_caller as fast_identify,
                            )
                            caller = fast_identify(sms_item["from"])
                            if caller:
                                sms_item["sender_name"] = caller.get("full_name", caller.get("name", ""))
                                sms_item["sender_type"] = caller.get("type", "unknown")
                        except Exception:
                            pass
                    # Sort by time descending
                    sms_list.sort(key=lambda x: x.get("time", ""), reverse=True)
                    return json.dumps({"count": len(sms_list), "hours_back": hours, "lines_monitored": ["307-459-8220", "719-428-3999"], "messages": sms_list})
                except Exception as e:
                    logger.error(f"check_recent_sms failed: {e}")
                    return json.dumps({"error": f"Failed to check SMS: {str(e)}"})

            elif tool_name == "send_sms":
                to_phone = tool_input.get("to_phone", "")
                message = tool_input.get("message", "")
                if not to_phone or not message:
                    return json.dumps({"error": "Both to_phone and message are required"})
                success, result = self._send_sms_via_rc(to_phone, message)
                if success:
                    logger.info(f"SMS sent from DM tool to {to_phone}: {message[:50]}...")
                    return json.dumps({"success": True, "message": f"SMS sent to {to_phone}"})
                else:
                    return json.dumps({"error": f"Failed to send SMS: {result}"})

            elif tool_name == "log_call_out":
                caregiver_id = tool_input.get("caregiver_id")
                caregiver_name = tool_input.get("caregiver_name", "Unknown")
                reason = tool_input.get("reason", "not specified")
                shift_date = tool_input.get("shift_date", date.today().isoformat())
                self.wellsky.create_admin_task(
                    title=f"CALL-OUT: {caregiver_name} - {reason}",
                    description=(
                        f"Caregiver {caregiver_name} called out.\n"
                        f"Reason: {reason}\n"
                        f"Shift date: {shift_date}\n"
                        f"ACTION: Find coverage immediately."
                    ),
                    priority="urgent",
                    related_caregiver_id=caregiver_id
                )
                return json.dumps({"success": True, "message": f"Call-out logged for {caregiver_name}. Admin task created."})

            elif tool_name == "identify_caller":
                phone = tool_input.get("phone_number", "")
                if not phone:
                    return json.dumps({"error": "No phone number provided"})
                try:
                    from services.wellsky_fast_lookup import (
                        identify_caller as fast_identify,
                    )
                    caller = fast_identify(phone)
                    if caller:
                        type_map = {"practitioner": "caregiver", "patient": "client", "staff": "staff", "family": "family"}
                        result = {
                            "identified_as": type_map.get(caller.get("type", ""), caller.get("type", "")),
                            "id": caller.get("id", ""),
                            "name": caller.get("full_name", caller.get("name", "")),
                            "phone": phone
                        }
                        if caller.get("type") == "family":
                            result["relationship"] = caller.get("relationship", "")
                            result["client_name"] = caller.get("client_name", "")
                        return json.dumps(result)
                except Exception as e:
                    logger.warning(f"Fast caller ID failed: {e}")
                return json.dumps({"identified_as": "unknown", "message": f"Phone number {phone} not found in records"})

            elif tool_name == "save_memory":
                if not RC_MEMORY_AVAILABLE or not _rc_memory_system:
                    return json.dumps({"error": "Memory system not available"})
                content = tool_input.get("content", "")
                category = tool_input.get("category", "general")
                importance = tool_input.get("importance", "medium")
                impact_map = {"high": ImpactLevel.HIGH, "medium": ImpactLevel.MEDIUM, "low": ImpactLevel.LOW}
                memory_id = _rc_memory_system.create_memory(
                    content=content, memory_type=MemoryType.EXPLICIT_INSTRUCTION,
                    source=MemorySource.EXPLICIT, confidence=1.0,
                    category=category, impact_level=impact_map.get(importance, ImpactLevel.MEDIUM)
                )
                return json.dumps({"saved": True, "memory_id": memory_id, "content": content})

            elif tool_name == "recall_memories":
                if not RC_MEMORY_AVAILABLE or not _rc_memory_system:
                    return json.dumps({"memories": [], "message": "Memory system not available"})
                category = tool_input.get("category")
                search_text = tool_input.get("search_text")
                memories = _rc_memory_system.query_memories(category=category, min_confidence=0.3, limit=10)
                if search_text:
                    search_lower = search_text.lower()
                    memories = [m for m in memories if search_lower in m.content.lower()]
                results = [{"id": m.id, "content": m.content, "category": m.category,
                           "confidence": float(m.confidence), "type": m.type.value} for m in memories]
                return json.dumps({"memories": results, "count": len(results)})

            elif tool_name == "forget_memory":
                if not RC_MEMORY_AVAILABLE or not _rc_memory_system:
                    return json.dumps({"error": "Memory system not available"})
                memory_id = tool_input.get("memory_id", "")
                memory = _rc_memory_system.get_memory(memory_id)
                if not memory:
                    return json.dumps({"error": f"Memory {memory_id} not found"})
                with _rc_memory_system._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE gigi_memories SET status = 'archived' WHERE id = %s", (memory_id,))
                        _rc_memory_system._log_event(cur, memory_id, "archived", memory.confidence, memory.confidence, "User requested forget")
                    conn.commit()
                return json.dumps({"archived": True, "memory_id": memory_id, "content": memory.content})

            elif tool_name == "search_memory_logs":
                from gigi.memory_logger import MemoryLogger
                ml = MemoryLogger()
                query = tool_input.get("query", "")
                days_back = tool_input.get("days_back", 30)
                results = ml.search_logs(query, days_back=days_back)
                return json.dumps({"query": query, "results": results[:10], "total": len(results)})

            elif tool_name == "browse_webpage":
                # Redirect to browse_with_claude (replaces old Playwright path)
                from gigi.claude_code_tools import browse_with_claude
                url = tool_input.get("url", "")
                result = await browse_with_claude(task=f"Navigate to {url} and extract the main text content of the page.", url=url)
                return json.dumps(result)

            elif tool_name == "take_screenshot":
                # Redirect to browse_with_claude (replaces old Playwright path)
                from gigi.claude_code_tools import browse_with_claude
                url = tool_input.get("url", "")
                result = await browse_with_claude(task=f"Navigate to {url} and take a screenshot. Describe what the page looks like.", url=url)
                return json.dumps(result)

            elif tool_name == "get_morning_briefing":
                from gigi.morning_briefing_service import MorningBriefingService
                svc = MorningBriefingService()
                return svc.generate_briefing()

            elif tool_name == "get_ar_report":
                from sales.quickbooks_service import QuickBooksService
                qb = QuickBooksService()
                loaded = await asyncio.to_thread(qb.load_tokens_from_db)
                if not loaded:
                    return json.dumps({"error": "QuickBooks not connected. Visit https://portal.coloradocareassist.com/auth/quickbooks to authorize."})
                detail_level = tool_input.get("detail_level", "summary")
                result = await asyncio.to_thread(qb.generate_ar_report, detail_level)
                if result.get("success"):
                    return result["report"]
                return json.dumps(result)

            elif tool_name == "deep_research":
                question = tool_input.get("question", "")
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=150.0) as client:
                        resp = await client.post(
                            "http://localhost:3002/api/research/deep",
                            json={"question": question}
                        )
                        data = resp.json()
                        answer = data.get("answer", "Research unavailable.")
                        confidence = data.get("confidence", 0)
                        tools_used = data.get("metadata", {}).get("tools_used", [])
                        duration = data.get("metadata", {}).get("total_duration_seconds", 0)
                        return f"{answer}\n\n---\nConfidence: {confidence:.0%} | Data sources: {len(tools_used)} | Research time: {duration:.0f}s"
                except Exception as e:
                    logger.error(f"Deep research failed: {e}")
                    return json.dumps({"error": f"Elite Trading research unavailable: {e}"})

            elif tool_name == "get_weather_arb_status":
                try:
                    import httpx
                    result = {"polymarket": {"status": "offline"}, "kalshi": {"status": "offline"}}
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        try:
                            status_resp, pnl_resp = await asyncio.gather(
                                client.get("http://127.0.0.1:3010/status"),
                                client.get("http://127.0.0.1:3010/pnl"),
                                return_exceptions=True,
                            )
                            poly = {"status": "online"}
                            if not isinstance(status_resp, Exception) and status_resp.status_code == 200:
                                st = status_resp.json()
                                sniper = st.get("sniper", {})
                                poly["running"] = bool(st.get("running"))
                                poly["scans"] = sniper.get("scan_count", 0)
                            if not isinstance(pnl_resp, Exception) and pnl_resp.status_code == 200:
                                data = pnl_resp.json()
                                poly["portfolio_value"] = data.get("portfolio_value", 0)
                                poly["cash"] = data.get("cash", 0)
                                poly["unrealized_pnl"] = data.get("unrealized_pnl", 0)
                                poly["num_positions"] = len(data.get("positions", []))
                                poly["positions"] = [
                                    {"title": p.get("title", "?")[:60], "pnl": round(p.get("pnl", 0), 2), "pnl_pct": round(p.get("pnl_pct", 0), 1)}
                                    for p in data.get("positions", [])[:10]
                                ]
                            result["polymarket"] = poly
                        except Exception:
                            pass
                        try:
                            kalshi_resp = await client.get("http://127.0.0.1:3011/pnl")
                            if kalshi_resp.status_code == 200:
                                data = kalshi_resp.json()
                                result["kalshi"] = {
                                    "status": "online",
                                    "portfolio_value": data.get("portfolio_value", 0),
                                    "cash": data.get("cash", 0),
                                    "unrealized_pnl": data.get("unrealized_pnl", 0),
                                    "num_positions": len(data.get("positions", [])),
                                    "positions": [
                                        {"ticker": p.get("ticker", "?"), "count": p.get("count", 0), "pnl": round(p.get("pnl", 0), 2)}
                                        for p in data.get("positions", [])[:10]
                                    ]
                                }
                        except Exception:
                            pass
                    return json.dumps(result)
                except Exception as e:
                    logger.error(f"Weather arb status failed: {e}")
                    return json.dumps({"error": f"Weather bots unavailable: {str(e)}"})

            elif tool_name == "watch_tickets":
                from gigi.ticket_monitor import create_watch
                result = await asyncio.to_thread(create_watch, tool_input.get("artist", ""), tool_input.get("venue"), tool_input.get("city", "Denver"))
                return json.dumps(result)

            elif tool_name == "list_ticket_watches":
                from gigi.ticket_monitor import list_watches
                return json.dumps(await asyncio.to_thread(list_watches))

            elif tool_name == "remove_ticket_watch":
                from gigi.ticket_monitor import remove_watch
                return json.dumps(await asyncio.to_thread(remove_watch, int(tool_input.get("watch_id", 0))))

            elif tool_name == "clock_in_shift":
                appointment_id = tool_input.get("appointment_id", "")
                caregiver_name = tool_input.get("caregiver_name", "")
                notes = tool_input.get("notes", "Clocked in via Gigi DM")
                if not appointment_id:
                    return json.dumps({"error": "Missing appointment_id. Use get_wellsky_shifts first."})
                def _dm_clock_in():
                    from services.wellsky_service import WellSkyService
                    ws = WellSkyService()
                    success, message = ws.clock_in_shift(appointment_id, notes=notes)
                    return {"success": success, "message": message, "appointment_id": appointment_id, "caregiver_name": caregiver_name}
                return json.dumps(await asyncio.to_thread(_dm_clock_in))

            elif tool_name == "clock_out_shift":
                appointment_id = tool_input.get("appointment_id", "")
                caregiver_name = tool_input.get("caregiver_name", "")
                notes = tool_input.get("notes", "Clocked out via Gigi DM")
                if not appointment_id:
                    return json.dumps({"error": "Missing appointment_id. Use get_wellsky_shifts first."})
                def _dm_clock_out():
                    from services.wellsky_service import WellSkyService
                    ws = WellSkyService()
                    success, message = ws.clock_out_shift(appointment_id, notes=notes)
                    return {"success": success, "message": message, "appointment_id": appointment_id, "caregiver_name": caregiver_name}
                return json.dumps(await asyncio.to_thread(_dm_clock_out))

            elif tool_name == "find_replacement_caregiver":
                shift_id = tool_input.get("shift_id", "")
                original_caregiver_id = tool_input.get("original_caregiver_id", "")
                reason = tool_input.get("reason", "called out")
                if not shift_id or not original_caregiver_id:
                    return json.dumps({"error": "Missing shift_id or original_caregiver_id"})
                def _dm_find_replacement():
                    try:
                        from sales.shift_filling.engine import shift_filling_engine
                        campaign = shift_filling_engine.process_calloff(
                            shift_id=shift_id, caregiver_id=original_caregiver_id,
                            reason=reason, reported_by="gigi_dm"
                        )
                        if not campaign:
                            return {"success": False, "error": "Could not create replacement campaign"}
                        return {
                            "success": True, "campaign_id": campaign.id,
                            "status": campaign.status.value if hasattr(campaign.status, 'value') else str(campaign.status),
                            "caregivers_contacted": campaign.total_contacted,
                            "message": f"Replacement search started. Contacting {campaign.total_contacted} caregivers via SMS."
                        }
                    except ImportError:
                        return {"error": "Shift filling engine not available"}
                    except Exception as e:
                        return {"error": f"Shift filling failed: {str(e)}"}
                return json.dumps(await asyncio.to_thread(_dm_find_replacement))

            elif tool_name == "get_task_board":
                def _dm_read_board():
                    try:
                        with open(os.path.expanduser("~/Task Board.md"), "r") as f:
                            return {"task_board": f.read()}
                    except FileNotFoundError:
                        return {"task_board": "(empty)"}
                return json.dumps(await asyncio.to_thread(_dm_read_board))

            elif tool_name == "add_task":
                task_text = tool_input.get("task", "").strip()
                section = tool_input.get("section", "Today").strip()
                if not task_text:
                    return json.dumps({"error": "No task text provided"})
                valid_sections = ["Today", "Soon", "Later", "Waiting", "Agenda", "Inbox", "Reference"]
                section_match = next((s for s in valid_sections if s.lower() == section.lower()), "Today")
                def _dm_add_task():
                    try:
                        path = os.path.expanduser("~/Task Board.md")
                        with open(path, "r") as f:
                            content = f.read()
                        marker = f"## {section_match}\n"
                        if marker in content:
                            idx = content.index(marker) + len(marker)
                            rest = content[idx:]
                            if rest.startswith("-\n") or rest.startswith("- \n"):
                                content = content[:idx] + f"- [ ] {task_text}\n" + rest[rest.index("\n") + 1:]
                            else:
                                content = content[:idx] + f"- [ ] {task_text}\n" + rest
                        else:
                            content += f"\n## {section_match}\n- [ ] {task_text}\n"
                        with open(path, "w") as f:
                            f.write(content)
                        return {"success": True, "task": task_text, "section": section_match}
                    except Exception as e:
                        return {"error": f"Failed: {str(e)}"}
                return json.dumps(await asyncio.to_thread(_dm_add_task))

            elif tool_name == "complete_task":
                task_text = tool_input.get("task_text", "").strip().lower()
                if not task_text:
                    return json.dumps({"error": "No task text provided"})
                def _dm_complete_task():
                    try:
                        path = os.path.expanduser("~/Task Board.md")
                        with open(path, "r") as f:
                            lines = f.readlines()
                        completed = False
                        completed_task = ""
                        new_lines = []
                        for line in lines:
                            if not completed and "- [ ]" in line and task_text in line.lower():
                                completed_task = line.replace("- [ ]", "- [x]").strip()
                                completed = True
                            else:
                                new_lines.append(line)
                        if not completed:
                            return {"error": f"No uncompleted task matching '{task_text}'"}
                        content = "".join(new_lines)
                        done_marker = "## Done\n"
                        if done_marker in content:
                            idx = content.index(done_marker) + len(done_marker)
                            rest = content[idx:]
                            if rest.startswith("-\n") or rest.startswith("- \n"):
                                content = content[:idx] + completed_task + "\n" + rest[rest.index("\n") + 1:]
                            else:
                                content = content[:idx] + completed_task + "\n" + rest
                        else:
                            content += f"\n## Done\n{completed_task}\n"
                        with open(path, "w") as f:
                            f.write(content)
                        return {"success": True, "completed": completed_task}
                    except Exception as e:
                        return {"error": f"Failed: {str(e)}"}
                return json.dumps(await asyncio.to_thread(_dm_complete_task))

            elif tool_name == "capture_note":
                note = tool_input.get("note", "").strip()
                if not note:
                    return json.dumps({"error": "No note provided"})
                def _dm_capture_note():
                    try:
                        path = os.path.expanduser("~/Scratchpad.md")
                        try:
                            with open(path, "r") as f:
                                content = f.read()
                        except FileNotFoundError:
                            content = "# Scratchpad\n\n---\n"
                        from datetime import datetime as dt
                        timestamp = dt.now().strftime("%I:%M %p")
                        content = content.rstrip() + f"\n- {note} ({timestamp})\n"
                        with open(path, "w") as f:
                            f.write(content)
                        return {"success": True, "note": note}
                    except Exception as e:
                        return {"error": f"Failed: {str(e)}"}
                return json.dumps(await asyncio.to_thread(_dm_capture_note))

            elif tool_name == "get_daily_notes":
                target_date = tool_input.get("date", "")
                def _dm_read_notes():
                    try:
                        import glob as g
                        import re as _re
                        from datetime import datetime as dt
                        d = target_date if _re.match(r"^\d{4}-\d{2}-\d{2}$", target_date) else dt.now().strftime("%Y-%m-%d")
                        matches = g.glob(os.path.join(os.path.expanduser("~/Daily Notes"), f"{d}*"))
                        if matches:
                            with open(matches[0], "r") as f:
                                return {"date": d, "notes": f.read()}
                        return {"date": d, "notes": "(no daily notes for this date)"}
                    except Exception as e:
                        return {"error": f"Failed: {str(e)}"}
                return json.dumps(await asyncio.to_thread(_dm_read_notes))

            else:
                # Delegate to Telegram bot for shared tools not natively handled
                try:
                    if not hasattr(self, '_shared_tele_bot'):
                        from gigi.telegram_bot import GigiTelegramBot
                        self._shared_tele_bot = GigiTelegramBot()
                    return await self._shared_tele_bot.execute_tool(tool_name, tool_input)
                except Exception as e:
                    logger.error(f"Delegated DM tool {tool_name} failed: {e}")
                    return json.dumps({"error": f"Tool '{tool_name}' is not available right now."})

        except Exception as e:
            logger.error(f"DM tool execution error ({tool_name}): {e}")
            if RC_FAILURE_HANDLER_AVAILABLE and _rc_failure_handler:
                try:
                    _rc_failure_handler.handle_tool_failure(tool_name, e, {"tool_input": str(tool_input)[:200]})
                except Exception:
                    pass
            return json.dumps({"error": f"Tool {tool_name} failed: {str(e)}"})

    def _resolve_sender_name(self, creator_id: str) -> str:
        """Resolve a RingCentral extension ID to a person name."""
        try:
            ext_info = self.rc_service._api_request(f"/account/~/extension/{creator_id}")
            if ext_info:
                return ext_info.get("name", f"Extension {creator_id}")
        except Exception as e:
            logger.warning(f"Could not resolve sender name for {creator_id}: {e}")
        return f"Extension {creator_id}"

    # =========================================================================
    # Process Reply (Claude-powered with static fallback)
    # =========================================================================

    async def process_reply(self, msg: dict, text: str, reply_method: str = "chat", phone: str = None):
        """Replier Logic: Respond to EVERY unanswered request after-hours.
        Uses Claude + tool calling for dynamic replies, falls back to static templates."""

        async with self._reply_lock:
            await self._process_reply_inner(msg, text, reply_method, phone)

    async def _process_reply_inner(self, msg: dict, text: str, reply_method: str = "chat", phone: str = None):
        """Inner implementation of process_reply, called under _reply_lock."""

        # LOOP PREVENTION CHECK - Critical safety gate
        if reply_method == "sms" and phone:
            can_reply, reason = self._can_reply_to_number(phone)
            if not can_reply:
                logger.warning(f"⛔ LOOP PREVENTION: Blocking reply to {phone}. Reason: {reason}")
                return

        # --- TRY LLM FIRST ---
        reply = None
        if self.llm:
            try:
                reply = await self._get_llm_sms_reply(text, phone or "unknown")
            except Exception as e:
                logger.error(f"LLM reply failed ({self.llm_provider}), falling back to static: {e}")
                reply = None

        # --- FALLBACK: Static replies if LLM unavailable ---
        if not reply:
            lower_text = text.lower()
            if "call out" in lower_text or "sick" in lower_text:
                reply = "I hear you. I've logged your call-out and we're already reaching out for coverage. Feel better!"
            elif "late" in lower_text:
                reply = "Thanks for letting us know. I've noted that you're running late in the system. Drive safe!"
            elif "cancel" in lower_text:
                reply = "I've processed that cancellation and notified the team. Thanks for the heads up."
            elif "help" in lower_text or "shift" in lower_text or "question" in lower_text:
                reply = "Got it. I've notified the care team that you need assistance. Someone will get back to you shortly."
            else:
                reply = "Thanks for your message! This is Gigi, the AI Operations Manager. I've logged this for the team, and someone will follow up with you as soon as possible."

        # --- SEMANTIC LOOP DETECTION ---
        if reply and reply_method == "sms" and phone:
            if self._detect_semantic_loop(phone, reply):
                logger.warning(f"🔁 SEMANTIC LOOP detected for {phone} — forcing escalation reply")
                reply = "I want to make sure you get the help you need. Let me have someone from the team call you back shortly."

        # --- SEND REPLY ---
        if reply:
            try:
                if reply_method == "chat":
                    self.rc_service.send_message_to_chat(TARGET_CHAT, reply)
                elif reply_method == "sms" and phone:
                    clean_phone = ''.join(filter(str.isdigit, phone))
                    if len(clean_phone) == 10: clean_phone = f"+1{clean_phone}"
                    elif not clean_phone.startswith('+'): clean_phone = f"+{clean_phone}"

                    # --- SHADOW MODE: Report to DM instead of sending ---
                    if GIGI_SMS_SHADOW_MODE:
                        # Look up sender name
                        sender_name = clean_phone
                        try:
                            conn = psycopg2.connect(db_url)
                            cur = conn.cursor()
                            phone_digits = ''.join(filter(str.isdigit, clean_phone))[-10:]
                            cur.execute("""
                                SELECT full_name, 'caregiver' as type FROM cached_practitioners
                                WHERE phone LIKE %s OR home_phone LIKE %s
                                UNION ALL
                                SELECT full_name, 'client' as type FROM cached_patients
                                WHERE phone LIKE %s OR home_phone LIKE %s
                                LIMIT 1
                            """, (f"%{phone_digits}", f"%{phone_digits}", f"%{phone_digits}", f"%{phone_digits}"))
                            row = cur.fetchone()
                            if row:
                                sender_name = f"{row[0]} ({row[1]})"
                            conn.close()
                        except Exception:
                            pass

                        shadow_msg = (
                            f"**SMS Shadow Mode**\n"
                            f"**From:** {sender_name} ({clean_phone})\n"
                            f"**Message:** {text}\n\n"
                            f"**My draft reply:**\n{reply}"
                        )
                        try:
                            self.rc_service.post_to_chat(SHADOW_DM_CHAT_ID, shadow_msg)
                            logger.info(f"👻 Shadow Mode: Draft SMS to {clean_phone} reported to DM (not sent)")
                        except Exception as e:
                            logger.error(f"Shadow mode DM failed: {e}")
                        # NOTE: Do NOT record cooldown for shadow mode — no SMS was actually sent,
                        # so there's no loop risk. Recording cooldown here blocks real inbound SMS.
                        return

                    # --- LIVE MODE: Actually send the SMS ---
                    logger.info(f"Sending SMS reply to {clean_phone} via {RINGCENTRAL_FROM_NUMBER} (using Admin Token)")

                    access_token = self._get_admin_access_token()
                    if not access_token:
                        logger.error("Could not get access token for SMS reply")
                        return

                    url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/sms"
                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                    data = {
                        "from": {"phoneNumber": RINGCENTRAL_FROM_NUMBER},
                        "to": [{"phoneNumber": clean_phone}],
                        "text": reply
                    }

                    response = requests.post(url, headers=headers, json=data, timeout=20)
                    if response.status_code == 200:
                        logger.info(f"🌙 After-Hours SMS Reply Sent to {clean_phone}")
                        self._record_reply(clean_phone, reply)
                    else:
                        logger.error(f"Failed to send SMS reply: {response.status_code} - {response.text}")

            except Exception as e:
                logger.error(f"Failed to send {reply_method} reply: {e}")

async def polling_loop(bot):
    """Run the periodic polling loop for team chat, DMs, and scheduled services."""
    while True:
        try:
            await bot.check_and_act()
        except Exception as e:
            logger.error(f"Error in polling loop: {e}")
        await asyncio.sleep(CHECK_INTERVAL)


async def main():
    bot = GigiRingCentralBot()
    if await bot.initialize():
        logger.info("🚀 Starting Gigi: WebSocket (SMS) + Polling (Chat/DM/Services)")
        await asyncio.gather(
            bot.run_sms_websocket(),   # Real-time SMS via RingCentral WebSocket
            polling_loop(bot),          # Team chat, DMs, scheduled services
        )

if __name__ == "__main__":
    asyncio.run(main())

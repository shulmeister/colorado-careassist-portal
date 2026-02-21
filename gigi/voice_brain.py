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
    from gigi.memory_system import ImpactLevel, MemorySource, MemorySystem, MemoryType
    memory_system = MemorySystem()
    MEMORY_AVAILABLE = True
    logger.info("Memory system initialized for voice brain")
except Exception as e:
    memory_system = None
    MEMORY_AVAILABLE = False
    logger.warning(f"Memory system not available: {e}")

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

LLM_PROVIDER = os.getenv("GIGI_LLM_PROVIDER", "gemini").lower()
_DEFAULT_MODELS = {
    "gemini": "gemini-3-flash-preview",  # override with GIGI_LLM_MODEL env var
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-5.1",
}
LLM_MODEL = os.getenv("GIGI_LLM_MODEL", _DEFAULT_MODELS.get(LLM_PROVIDER, "gemini-3-flash-preview"))

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

logger.info(f"Voice Brain LLM: {LLM_PROVIDER} / {LLM_MODEL} ({'ready' if llm_client else 'NOT CONFIGURED'})")

async def run_sync(func, *args, **kwargs):
    """Run a synchronous function in a separate thread to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    from functools import partial
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))

def _sync_db_query(sql, params=None):
    """Synchronous database query helper — always closes connection"""
    import psycopg2
    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
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
    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
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

# Anthropic-format tools
ANTHROPIC_TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather and forecast for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City and State (e.g. Denver, CO)"}
            },
            "required": ["location"]
        }
    },
    {
        "name": "search_concerts",
        "description": "Find upcoming concerts in Denver or other cities for specific artists or venues.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (artist, venue, or city)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "buy_tickets_request",
        "description": "Initiate a ticket purchase request for a concert or event. Requires 2FA confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "artist": {"type": "string", "description": "Artist/Band name"},
                "venue": {"type": "string", "description": "Venue name"},
                "quantity": {"type": "integer", "description": "Number of tickets", "default": 2}
            },
            "required": ["artist", "venue"]
        }
    },
    {
        "name": "book_table_request",
        "description": "Request a restaurant reservation. Requires 2FA confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "restaurant": {"type": "string", "description": "Restaurant name"},
                "party_size": {"type": "integer", "description": "Number of people"},
                "date": {"type": "string", "description": "Date (YYYY-MM-DD)"},
                "time": {"type": "string", "description": "Time (e.g. 7:00 PM)"}
            },
            "required": ["restaurant", "party_size", "date", "time"]
        }
    },
    {
        "name": "get_client_current_status",
        "description": "Check who is with a client right now. Returns current caregiver, shift times, and status.",
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
        "name": "get_calendar_events",
        "description": "Get upcoming calendar events from Jason's Google Calendar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days to look ahead (default 1)", "default": 1}
            },
            "required": []
        }
    },
    {
        "name": "search_emails",
        "description": "Search Jason's Gmail for emails.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search query", "default": "is:unread"},
                "max_results": {"type": "integer", "description": "Max emails to return", "default": 5}
            },
            "required": []
        }
    },
    {
        "name": "send_email",
        "description": "Send an email via Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email"},
                "subject": {"type": "string", "description": "Subject line"},
                "body": {"type": "string", "description": "Email body"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "get_wellsky_clients",
        "description": "Search for clients in WellSky by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_name": {"type": "string", "description": "Client name to search"},
                "active_only": {"type": "boolean", "description": "Only active clients", "default": True}
            },
            "required": []
        }
    },
    {
        "name": "get_wellsky_caregivers",
        "description": "Search for caregivers in WellSky by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_name": {"type": "string", "description": "Caregiver name to search"},
                "active_only": {"type": "boolean", "description": "Only active caregivers", "default": True}
            },
            "required": []
        }
    },
    {
        "name": "get_wellsky_shifts",
        "description": "Get shifts from WellSky cached data. Can look forward (upcoming) or backward (past/completed). Use get_wellsky_clients or get_wellsky_caregivers first to find an ID if filtering by person.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string", "description": "Filter by client ID"},
                "caregiver_id": {"type": "string", "description": "Filter by caregiver ID"},
                "days": {"type": "integer", "description": "Days to look ahead for upcoming shifts", "default": 7},
                "past_days": {"type": "integer", "description": "Days to look BACK for past/completed shifts. Use when asked about shift history, hours worked, etc.", "default": 0},
                "open_only": {"type": "boolean", "description": "If true, only return open or unfilled shifts (no assigned caregiver)", "default": False}
            },
            "required": []
        }
    },
    {
        "name": "send_sms",
        "description": "Send a text message (SMS) to a phone number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "Recipient phone number"},
                "message": {"type": "string", "description": "Message content"}
            },
            "required": ["phone_number", "message"]
        }
    },
    {
        "name": "send_team_message",
        "description": "Send a message to the RingCentral team chat (New Scheduling).",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message content"}
            },
            "required": ["message"]
        }
    },
    {
        "name": "web_search",
        "description": "Search the internet for information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_stock_price",
        "description": "Get current stock price for a ticker symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker (e.g., AAPL, TSLA)"}
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_crypto_price",
        "description": "Get current cryptocurrency price.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Crypto symbol (BTC, ETH, etc.)"}
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "lookup_caller",
        "description": "Look up caller information by phone number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "Phone number to look up"}
            },
            "required": ["phone_number"]
        }
    },
    {
        "name": "report_call_out",
        "description": "Report a caregiver calling out sick.",
        "input_schema": {
            "type": "object",
            "properties": {
                "caregiver_name": {"type": "string", "description": "Caregiver's name"},
                "reason": {"type": "string", "description": "Reason for call-out"},
                "shift_date": {"type": "string", "description": "Date of shift (YYYY-MM-DD)"}
            },
            "required": ["caregiver_name"]
        }
    },
    {
        "name": "clock_in_shift",
        "description": "Clock a caregiver into their shift. Use when a caregiver says they forgot to clock in or needs help clocking in. Look up their shift first with get_wellsky_shifts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string", "description": "The shift/appointment ID from WellSky (get this from get_wellsky_shifts)"},
                "caregiver_name": {"type": "string", "description": "Caregiver's name (for logging)"},
                "notes": {"type": "string", "description": "Optional notes (e.g. 'clocked in via phone call')"}
            },
            "required": ["appointment_id"]
        }
    },
    {
        "name": "clock_out_shift",
        "description": "Clock a caregiver out of their shift. Use when a caregiver says they forgot to clock out or needs help clocking out. Look up their shift first with get_wellsky_shifts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string", "description": "The shift/appointment ID from WellSky (get this from get_wellsky_shifts)"},
                "caregiver_name": {"type": "string", "description": "Caregiver's name (for logging)"},
                "notes": {"type": "string", "description": "Optional notes (e.g. 'clocked out via phone call')"}
            },
            "required": ["appointment_id"]
        }
    },
    {
        "name": "find_replacement_caregiver",
        "description": "Find a replacement caregiver when someone calls out sick. Searches available caregivers, scores them by fit, and initiates SMS outreach. Use after report_call_out when a shift needs coverage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "shift_id": {"type": "string", "description": "The shift/appointment ID that needs coverage"},
                "original_caregiver_id": {"type": "string", "description": "WellSky ID of the caregiver who called out"},
                "reason": {"type": "string", "description": "Reason for the calloff"}
            },
            "required": ["shift_id", "original_caregiver_id"]
        }
    },
    {
        "name": "transfer_call",
        "description": "Transfer the call to another number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Who to transfer to: 'jason', 'office', or a phone number"}
            },
            "required": ["destination"]
        }
    },
    {
        "name": "create_claude_task",
        "description": "Create a task for Claude Code to work on. Use this when Jason asks you to tell Claude Code to do something technical — fix a bug, check a service, update code, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title for the task (e.g., 'Fix elite trading build error')"},
                "description": {"type": "string", "description": "Detailed description of what Claude Code should do"},
                "priority": {"type": "string", "description": "Priority level", "enum": ["low", "normal", "high", "urgent"]},
                "working_directory": {"type": "string", "description": "Directory to work in (optional, defaults to careassist-unified)"}
            },
            "required": ["title", "description"]
        }
    },
    {
        "name": "check_claude_task",
        "description": "Check the status of a Claude Code task. Can check the latest task or a specific task by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "Specific task ID to check (optional, defaults to most recent)"}
            },
            "required": []
        }
    },
    {
        "name": "save_memory",
        "description": "Save a fact or preference to long-term memory. ONLY use when someone EXPLICITLY states something to remember. NEVER save inferred, assumed, or fabricated information. If unsure, ask before saving.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The EXACT fact or preference stated by the user. Quote their words, don't paraphrase or embellish."},
                "category": {"type": "string", "description": "Category: scheduling, communication, travel, health, operations, personal, general"},
                "importance": {"type": "string", "description": "How important: high (money/legal/reputation), medium (scheduling/communication), low (preferences)", "enum": ["high", "medium", "low"]}
            },
            "required": ["content", "category"]
        }
    },
    {
        "name": "recall_memories",
        "description": "Search your long-term memory for saved preferences, facts, or instructions. Use before asking a question that may have already been answered.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filter by category (optional)"},
                "search_text": {"type": "string", "description": "Keywords to search for (optional)"}
            },
            "required": []
        }
    },
    {
        "name": "forget_memory",
        "description": "Archive a memory that is no longer relevant. Use when told to forget something or when a preference has changed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string", "description": "ID of the memory to archive"}
            },
            "required": ["memory_id"]
        }
    },
    {
        "name": "search_memory_logs",
        "description": "Search Gigi's daily operation logs for past conversations, tool usage, failures, and patterns. Use when asked about past activity or 'what happened on...'",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords to search for in past logs"},
                "days_back": {"type": "integer", "description": "How many days back to search (default 30)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_ar_report",
        "description": "Get the QuickBooks accounts receivable aging report showing outstanding invoices and overdue amounts. Use when asked about AR, accounts receivable, or who owes money.",
        "input_schema": {
            "type": "object",
            "properties": {
                "detail_level": {"type": "string", "description": "Level of detail: 'summary' (default) or 'detailed' (full invoice list)"}
            },
            "required": []
        }
    },
    {
        "name": "deep_research",
        "description": "Run deep autonomous financial research using 40+ data tools and 9 AI agents. Takes 30-120 seconds. Tell the caller you'll look into it and they can ask about something else while you wait.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The financial research question to analyze"}
            },
            "required": ["question"]
        }
    },
    {
        "name": "browse_webpage",
        "description": "Browse a webpage and extract its text content. Use for research, reading articles, checking websites. Takes 10-30 seconds. Tell the caller you'll check it and they can ask about something else while you wait.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to browse"},
                "extract_links": {"type": "boolean", "description": "Also extract links (default false)"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "watch_tickets",
        "description": "Set up a ticket watch for an artist or event. Gigi will monitor Ticketmaster and AXS and send Telegram alerts when tickets go on presale or general sale.",
        "input_schema": {
            "type": "object",
            "properties": {
                "artist": {"type": "string", "description": "Artist or event name to watch"},
                "venue": {"type": "string", "description": "Venue to filter (optional)"},
                "city": {"type": "string", "description": "City to search (default Denver)"}
            },
            "required": ["artist"]
        }
    },
    {
        "name": "list_ticket_watches",
        "description": "List all active ticket watches Gigi is monitoring.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "remove_ticket_watch",
        "description": "Stop watching for tickets. Use list_ticket_watches first to get the watch ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "watch_id": {"type": "integer", "description": "Watch ID to remove"}
            },
            "required": ["watch_id"]
        }
    },
    {
        "name": "get_morning_briefing",
        "description": "Generate the full morning briefing with weather, calendar, shifts, emails, ski conditions, alerts. Use when asked for a briefing or daily summary.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_polybot_status",
        "description": "Get Elite Trading paper-mode Polybot status.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_weather_arb_status",
        "description": "Get weather trading bots status: Weather Sniper Bot (Polymarket, LIVE) and Kalshi bot. Shows sniper status, forecasts, orders, P&L, positions.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_task_board",
        "description": "Read Jason's task board. Shows tasks by section: Today, Soon, Later, Waiting, Agenda, Inbox, Done. Use when asked about priorities or to-dos.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "add_task",
        "description": "Add a task to Jason's task board. Use when Jason says 'I have a task', 'add to my list', 'remind me to', 'I need to'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "The task description"},
                "section": {"type": "string", "description": "Board section: Today, Soon, Later, Inbox (default: Today)"}
            },
            "required": ["task"]
        }
    },
    {
        "name": "complete_task",
        "description": "Mark a task done on Jason's task board. Use when Jason says 'done with X', 'finished X', 'check off X'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_text": {"type": "string", "description": "Text of the task to complete (partial match OK)"}
            },
            "required": ["task_text"]
        }
    },
    {
        "name": "capture_note",
        "description": "Capture a quick note or idea to Jason's scratchpad. Use when Jason says 'I have an idea', 'note this', 'jot this down'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "note": {"type": "string", "description": "The note or idea to capture"}
            },
            "required": ["note"]
        }
    },
    {
        "name": "get_daily_notes",
        "description": "Read today's daily notes for context on what Jason has been working on.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date YYYY-MM-DD (default: today)"}
            },
            "required": []
        }
    },
    # === MARKETING TOOLS ===
    {"name": "get_marketing_dashboard", "description": "Get an aggregated marketing snapshot: social media, ads, email metrics.", "input_schema": {"type": "object", "properties": {"date_range": {"type": "string", "description": "Period: today/7d/30d/mtd/ytd (default 7d)"}}, "required": []}},
    {"name": "get_google_ads_report", "description": "Google Ads performance: spend, clicks, impressions, ROAS.", "input_schema": {"type": "object", "properties": {"date_range": {"type": "string", "description": "Period (default 30d)"}}, "required": []}},
    {"name": "get_website_analytics", "description": "GA4 website analytics: traffic, sessions, conversions.", "input_schema": {"type": "object", "properties": {"date_range": {"type": "string", "description": "Period (default 7d)"}}, "required": []}},
    {"name": "get_social_media_report", "description": "Social media metrics from Facebook, Instagram, LinkedIn, Pinterest.", "input_schema": {"type": "object", "properties": {"date_range": {"type": "string", "description": "Period (default 7d)"}, "platform": {"type": "string", "description": "Filter: facebook/instagram/linkedin/pinterest (default all)"}}, "required": []}},
    {"name": "get_gbp_report", "description": "Google Business Profile: reviews, calls, direction requests.", "input_schema": {"type": "object", "properties": {"date_range": {"type": "string", "description": "Period (default 30d)"}}, "required": []}},
    {"name": "get_email_campaign_report", "description": "Brevo email marketing: campaigns, open rate, click rate.", "input_schema": {"type": "object", "properties": {"date_range": {"type": "string", "description": "Period (default 30d)"}}, "required": []}},
    {"name": "generate_social_content", "description": "Generate social media content using Predis AI.", "input_schema": {"type": "object", "properties": {"prompt": {"type": "string", "description": "What the post should be about"}, "media_type": {"type": "string", "description": "Content type: single_image/carousel/video/quote"}}, "required": ["prompt"]}},
    # === FINANCE TOOLS ===
    {"name": "get_pnl_report", "description": "Profit & Loss from QuickBooks: revenue, expenses, net income.", "input_schema": {"type": "object", "properties": {"period": {"type": "string", "description": "ThisMonth/LastMonth/ThisQuarter/ThisYear/LastYear"}}, "required": []}},
    {"name": "get_balance_sheet", "description": "Balance Sheet from QuickBooks: assets, liabilities, equity.", "input_schema": {"type": "object", "properties": {"as_of_date": {"type": "string", "description": "Date YYYY-MM-DD (default today)"}}, "required": []}},
    {"name": "get_invoice_list", "description": "Open/overdue invoices from QuickBooks.", "input_schema": {"type": "object", "properties": {"status": {"type": "string", "description": "Open/Overdue/All (default Open)"}}, "required": []}},
    {"name": "get_cash_position", "description": "Cash on hand and runway estimate.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_financial_dashboard", "description": "Complete financial snapshot: AR, cash, P&L, invoices.", "input_schema": {"type": "object", "properties": {}, "required": []}},
]

# Gemini-format tools — auto-generated from ANTHROPIC_TOOLS
GEMINI_TOOLS = None
if GEMINI_AVAILABLE:
    def _gs(type_str, desc):
        return genai_types.Schema(type={"string":"STRING","integer":"INTEGER","boolean":"BOOLEAN"}.get(type_str, "STRING"), description=desc)

    _gem_decls = []
    for t in ANTHROPIC_TOOLS:
        props = {k: _gs(v.get("type", "string"), v.get("description", k))
                 for k, v in t["input_schema"]["properties"].items()}
        req = t["input_schema"].get("required", [])
        _gem_decls.append(genai_types.FunctionDeclaration(
            name=t["name"], description=t["description"],
            parameters=genai_types.Schema(type="OBJECT", properties=props, required=req if req else None)))
    GEMINI_TOOLS = [genai_types.Tool(function_declarations=_gem_decls)]

# OpenAI-format tools — auto-generated from ANTHROPIC_TOOLS
OPENAI_TOOLS = [
    {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
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

# Who You're Talking To
- Caregivers: scheduling, call-outs, shift questions
- Clients: service questions, complaints, scheduling
- Family members: concerns about loved ones
- Prospective clients/caregivers: inquiries

# Handling Prospects & New Callers (DO NOT TRANSFER — Handle Yourself)
When someone calls asking about services, pricing, or getting started:
1. Answer their questions directly — you are fully equipped to handle prospect inquiries
2. Services we offer: Non-medical home care — companionship, personal care (bathing, dressing, grooming), meal prep, light housekeeping, medication reminders, transportation, respite care for family caregivers
3. Service area: Denver metro and surrounding communities in Colorado
4. Pricing: Our rates typically range from $32 to $42 per hour depending on the level of care. 4-hour minimum per visit. No deposits and no long-term contracts required.
5. Timeline: We can often start within 24-48 hours after a free in-home assessment
6. If they want to get started, collect: name, phone number, brief description of care needs, and how soon they need help
7. End with: "Someone from our team will call you back [today/tomorrow] to schedule a free assessment."
8. For callers not in our system: Look them up with get_wellsky_clients to confirm they're new, then handle as a prospect

# Your Capabilities (use tools PROACTIVELY)
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

# CRITICAL: Proactive Lookup Rule
When a caller gives their name, IMMEDIATELY look them up:
- For clients/family: use get_wellsky_clients with their name
- For caregivers: use get_wellsky_caregivers with their name
- For schedule questions: use get_client_current_status or get_wellsky_shifts
Do NOT ask 3 rounds of clarifying questions before using a tool. Act first, ask later.

# When to Transfer Calls (CRITICAL)
Transfer to Jason when:
- Medical emergencies or safety concerns about a client
- A client or family member explicitly ASKS for a human or supervisor
- You've tried 3+ tools and still can't resolve the issue
- Legal questions or complaints about discrimination/harassment
- After attempting to help an angry/escalating caller and they still demand escalation
Transfer to office when:
- Fax/mail requests
- Vendor or supplier calls

NEVER transfer for (handle these yourself):
- Pricing questions — you know our rates ($32-42/hr)
- Service inquiries — you know what we offer
- Prospects wanting to get started — collect their info, promise callback
- Unknown/wrong-number callers with simple questions — help them, collect info
- Caregiver scheduling, call-outs, shift questions, clock in/out
- Client complaints — acknowledge, log with send_team_message, set follow-up expectation
- Payroll/pay disputes — empathize, capture details, promise business-hours follow-up
- Billing questions — capture details, promise callback from billing team
- Employment questions — capture details, promise HR callback

When someone is angry or upset: Acknowledge their concern, use your tools to log the issue and look up context, and set a clear follow-up expectation. Only transfer if they explicitly demand a human AFTER you've tried to help.

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
- For call-outs: get the caregiver's name and which shift, then report it
- ALWAYS log issues with send_team_message when: complaints, neglect accusations, missed/late visits, caregiver disputes, service concerns, client threats to cancel. Don't wait to be asked — log it proactively so the team sees it.
- Always be warm but efficient - people are busy
- NEVER HALLUCINATE TOOLS: Only use the tools you actually have. NEVER invent shell commands, CLI tools, or fake tool output. If you can't do something, say so.
- IMPORTANT — Before purchasing tickets or booking reservations, ALWAYS ask for details first:
  - Tickets: Ask about seat preference — GA, reserved, VIP, pit, balcony, floor, etc. Also ask about price range.
  - Restaurants: Ask about seating preference — indoor, outdoor, booth, bar, patio. Ask about occasion or special requests.
  - Never assume seat location or seating preference. Gather the details, confirm with the caller, then execute.

# Tone
- NO sycophantic language: never say "locked in", "inner circle", "absolutely", "on it".
- Be direct and real. Sound like a person, not a corporate chatbot.
- NEVER start with "Great question!" or "I'd be happy to help!" — just answer.
- Keep it SHORT. This is a phone call. One or two sentences max per turn.
- Limit yourself to 2 tool calls maximum per voice turn — speed matters on calls.
"""


def _build_voice_system_prompt():
    """Build the system prompt with dynamic context: date, memories, mode."""
    parts = [_VOICE_SYSTEM_PROMPT_BASE]

    # Current date/time
    parts.append(f"\n# Current Date/Time\nToday is {datetime.now().strftime('%A, %B %d, %Y')}")

    # Inject mode context
    if MODE_AVAILABLE and mode_detector:
        try:
            mode_info = mode_detector.get_current_mode()
            parts.append(f"\n# Current Operating Mode\nMode: {mode_info.mode.value.upper()} (source: {mode_info.source.value})")
        except Exception as e:
            logger.warning(f"Mode detection failed: {e}")

    # Inject relevant memories
    if MEMORY_AVAILABLE and memory_system:
        try:
            memories = memory_system.query_memories(min_confidence=0.5, limit=10)
            if memories:
                memory_lines = [f"- {m.content} (confidence: {m.confidence:.0%}, category: {m.category})" for m in memories]
                parts.append("\n# Your Saved Memories\n" + "\n".join(memory_lines))
        except Exception as e:
            logger.warning(f"Memory injection failed: {e}")

    return "\n".join(parts)


# Legacy reference for places that use SYSTEM_PROMPT directly
SYSTEM_PROMPT = _build_voice_system_prompt()


async def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool and return the result - same logic as Telegram bot"""
    import httpx

    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")

    try:
        if tool_name == "get_weather":
            location = tool_input.get("location", "")
            if not location:
                return json.dumps({"error": "No location provided"})

            # Primary: wttr.in — free, no API key, returns structured JSON
            try:
                from urllib.parse import quote
                encoded_loc = quote(location.replace(",", " ").strip())
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(f"https://wttr.in/{encoded_loc}?format=j1")
                    if resp.status_code == 200:
                        w = resp.json()
                        current = w.get("current_condition", [{}])[0]
                        area = w.get("nearest_area", [{}])[0]
                        area_name = area.get("areaName", [{}])[0].get("value", location)
                        forecast_today = w.get("weather", [{}])[0]
                        return json.dumps({
                            "location": area_name,
                            "temp_f": current.get("temp_F"),
                            "feels_like_f": current.get("FeelsLikeF"),
                            "description": current.get("weatherDesc", [{}])[0].get("value"),
                            "humidity": current.get("humidity"),
                            "wind_mph": current.get("windspeedMiles"),
                            "high_f": forecast_today.get("maxtempF"),
                            "low_f": forecast_today.get("mintempF"),
                        })
            except Exception as e:
                logger.warning(f"wttr.in failed: {e}")

            # Fallback: Brave Search
            try:
                brave_api_key = os.getenv("BRAVE_API_KEY")
                if brave_api_key:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(
                            "https://api.search.brave.com/res/v1/web/search",
                            headers={"X-Subscription-Token": brave_api_key},
                            params={"q": f"current weather {location}", "count": 1},
                        )
                        if resp.status_code == 200:
                            results = resp.json().get("web", {}).get("results", [])
                            if results:
                                return json.dumps({"location": location, "weather": results[0].get("description")})
            except Exception as e:
                logger.warning(f"Brave weather failed: {e}")

            # Fallback: DDG
            try:
                def _ddg_weather():
                    from ddgs import DDGS
                    return list(DDGS().text(f"current weather {location}", max_results=1))
                results = await run_sync(_ddg_weather)
                if results:
                    return json.dumps({"location": location, "weather": results[0].get("body", "")})
            except Exception as e:
                logger.warning(f"DDG weather failed: {e}")

            return json.dumps({"error": "Weather service temporarily unavailable"})

        elif tool_name == "search_concerts":
            from gigi.chief_of_staff_tools import cos_tools
            query = tool_input.get("query", "")
            result = await cos_tools.search_concerts(query=query)
            return json.dumps(result)

        elif tool_name == "buy_tickets_request":
            from gigi.chief_of_staff_tools import cos_tools
            artist = tool_input.get("artist")
            venue = tool_input.get("venue")
            quantity = tool_input.get("quantity", 2)
            result = await cos_tools.buy_tickets_request(artist=artist, venue=venue, quantity=quantity)
            return json.dumps(result)

        elif tool_name == "book_table_request":
            from gigi.chief_of_staff_tools import cos_tools
            restaurant = tool_input.get("restaurant")
            party_size = tool_input.get("party_size")
            date_val = tool_input.get("date")
            time_val = tool_input.get("time")
            result = await cos_tools.book_table_request(restaurant=restaurant, party_size=party_size, date=date_val, time=time_val)
            return json.dumps(result)

        elif tool_name == "get_client_current_status":
            # Uses cached_appointments (instant SQL) — same as Telegram bot
            client_name = tool_input.get("client_name", "")
            if not client_name:
                return json.dumps({"error": "No client name provided"})

            def _cached_status_check(name_val):
                from datetime import datetime

                import psycopg2
                db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
                conn = None
                try:
                    conn = psycopg2.connect(db_url)
                    cur = conn.cursor()

                    # 1. Find Client
                    search_lower = f"%{name_val.lower()}%"
                    cur.execute("""
                        SELECT id, full_name, address, city
                        FROM cached_patients
                        WHERE is_active = true
                        AND (lower(full_name) LIKE %s OR lower(first_name) LIKE %s OR lower(last_name) LIKE %s)
                        LIMIT 1
                    """, (search_lower, search_lower, search_lower))
                    client_row = cur.fetchone()
                    if not client_row:
                        return {"status": "not_found", "message": f"Could not find active client matching '{name_val}'"}

                    client_id, client_full_name, addr, city = client_row

                    # 2. Get Today's Shifts from cached_appointments (instant)
                    cur.execute("""
                        SELECT
                            a.scheduled_start,
                            a.scheduled_end,
                            p.full_name as caregiver_name,
                            p.phone as caregiver_phone,
                            a.status
                        FROM cached_appointments a
                        LEFT JOIN cached_practitioners p ON a.practitioner_id = p.id
                        WHERE a.patient_id = %s
                        AND a.scheduled_start >= CURRENT_DATE - INTERVAL '1 day'
                        AND a.scheduled_start < CURRENT_DATE + INTERVAL '2 days'
                        ORDER BY a.scheduled_start ASC
                    """, (client_id,))

                    shifts = cur.fetchall()

                    if not shifts:
                        return {"client": client_full_name, "status": "no_shifts",
                                "message": f"No shifts scheduled for {client_full_name} today."}

                    # 3. Analyze Status
                    now = datetime.now()
                    current_shift = None
                    next_shift = None
                    last_shift = None

                    for s in shifts:
                        start, end, cg_name, cg_phone, status = s
                        if start <= now <= end:
                            current_shift = s
                            break
                        elif start > now:
                            if not next_shift:
                                next_shift = s
                        elif end < now:
                            last_shift = s

                    if current_shift:
                        start, end, cg_name, _, _ = current_shift
                        return {"client": client_full_name, "status": "active",
                                "message": f"{cg_name} is with {client_full_name} right now. Shift: {start.strftime('%I:%M %p')} to {end.strftime('%I:%M %p')}."}
                    elif next_shift:
                        start, end, cg_name, _, _ = next_shift
                        return {"client": client_full_name, "status": "upcoming",
                                "message": f"No one is there right now. Next shift is {cg_name} at {start.strftime('%I:%M %p')}."}
                    else:
                        start, end, cg_name, _, _ = last_shift if last_shift else (None, None, "None", None, None)
                        msg = f"{cg_name} finished at {end.strftime('%I:%M %p')}." if last_shift else f"No active shifts right now for {client_full_name}."
                        return {"client": client_full_name, "status": "completed", "message": msg}

                except Exception as e:
                    logger.error(f"Status check failed: {e}")
                    return {"error": str(e)}
                finally:
                    if conn:
                        conn.close()

            result = await run_sync(_cached_status_check, client_name)
            return json.dumps(result)

        elif tool_name == "get_calendar_events":
            if not GOOGLE_AVAILABLE or not google_service:
                return json.dumps({"error": "Google service not available"})
            days = tool_input.get("days", 1)
            events = await run_sync(google_service.get_calendar_events, days=min(days, 7))
            return json.dumps({"events": events or []})

        elif tool_name == "search_emails":
            if not GOOGLE_AVAILABLE or not google_service:
                return json.dumps({"error": "Google service not available"})
            query = tool_input.get("query", "is:unread")
            max_results = tool_input.get("max_results", 5)
            emails = await run_sync(google_service.search_emails, query=query, max_results=max_results)
            return json.dumps({"emails": emails or []})

        elif tool_name == "send_email":
            if not GOOGLE_AVAILABLE or not google_service:
                return json.dumps({"error": "Google service not available"})
            to = tool_input.get("to", "")
            subject = tool_input.get("subject", "")
            body = tool_input.get("body", "")
            if not all([to, subject, body]):
                return json.dumps({"error": "Missing to, subject, or body"})
            success = await run_sync(google_service.send_email, to=to, subject=subject, body=body)
            return json.dumps({"success": success})

        elif tool_name == "get_wellsky_clients":
            search_name = tool_input.get("search_name", "")
            active_only = tool_input.get("active_only", True)

            def _query_clients():
                if search_name:
                    search = f"%{search_name.lower()}%"
                    sql = "SELECT id, first_name, last_name, full_name, phone FROM cached_patients WHERE lower(full_name) LIKE %s"
                    params = [search]
                else:
                    sql = "SELECT id, first_name, last_name, full_name, phone FROM cached_patients WHERE 1=1"
                    params = []
                if active_only:
                    sql += " AND is_active = true"
                sql += " ORDER BY full_name LIMIT 20"
                return _sync_db_query(sql, params)

            rows = await run_sync(_query_clients)
            clients = [{"id": str(r[0]), "first_name": r[1], "last_name": r[2], "name": r[3], "phone": r[4] or ""} for r in rows]
            return json.dumps({"clients": clients, "count": len(clients)})

        elif tool_name == "get_wellsky_caregivers":
            search_name = tool_input.get("search_name", "")
            active_only = tool_input.get("active_only", True)

            def _query_caregivers():
                if search_name:
                    search = f"%{search_name.lower()}%"
                    sql = "SELECT id, first_name, last_name, full_name, phone FROM cached_practitioners WHERE lower(full_name) LIKE %s"
                    params = [search]
                else:
                    sql = "SELECT id, first_name, last_name, full_name, phone FROM cached_practitioners WHERE 1=1"
                    params = []
                if active_only:
                    sql += " AND is_active = true"
                sql += " ORDER BY full_name LIMIT 20"
                return _sync_db_query(sql, params)

            rows = await run_sync(_query_caregivers)
            caregivers = [{"id": str(r[0]), "first_name": r[1], "last_name": r[2], "name": r[3], "phone": r[4] or ""} for r in rows]
            return json.dumps({"caregivers": caregivers, "count": len(caregivers)})

        elif tool_name == "get_wellsky_shifts":
            # Uses cached_appointments (instant SQL) — no live API calls during voice
            days = min(tool_input.get("days", 7), 30)
            past_days = min(tool_input.get("past_days", 0), 90)
            open_only = tool_input.get("open_only", False)
            client_id = tool_input.get("client_id")
            caregiver_id = tool_input.get("caregiver_id")

            def _get_cached_shifts():
                import psycopg2
                db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
                conn = psycopg2.connect(db_url)
                try:
                    cur = conn.cursor()

                    if past_days > 0:
                        date_condition = "a.scheduled_start >= CURRENT_DATE - make_interval(days => %s) AND a.scheduled_start < CURRENT_DATE"
                        params = [past_days]
                    else:
                        date_condition = "a.scheduled_start >= CURRENT_DATE AND a.scheduled_start < CURRENT_DATE + make_interval(days => %s)"
                        params = [days]

                    sql = f"""
                        SELECT a.id, a.patient_id, pat.full_name as client_name,
                               a.practitioner_id, p.full_name as caregiver_name,
                               a.scheduled_start, a.scheduled_end, a.status
                        FROM cached_appointments a
                        LEFT JOIN cached_practitioners p ON a.practitioner_id = p.id
                        LEFT JOIN cached_patients pat ON a.patient_id = pat.id
                        WHERE {date_condition}
                    """

                    if client_id:
                        sql += " AND a.patient_id = %s"
                        params.append(str(client_id))
                    if caregiver_id:
                        sql += " AND a.practitioner_id = %s"
                        params.append(str(caregiver_id))
                    if open_only:
                        sql += " AND (a.practitioner_id IS NULL OR a.status IN ('open', 'pending', 'proposed'))"

                    sql += " ORDER BY a.scheduled_start ASC LIMIT 50"
                    cur.execute(sql, params)
                    rows = cur.fetchall()

                    shift_list = []
                    total_hours = 0
                    for r in rows:
                        hours = None
                        if r[5] and r[6]:
                            hours = round((r[6] - r[5]).total_seconds() / 3600, 1)
                            total_hours += hours
                        shift_list.append({
                            "id": str(r[0]),
                            "client_id": str(r[1]),
                            "client_name": r[2] or "",
                            "caregiver_id": str(r[3]) if r[3] else "",
                            "caregiver_name": r[4] or "Unassigned",
                            "start": r[5].strftime('%Y-%m-%d %I:%M %p') if r[5] else "",
                            "end": r[6].strftime('%I:%M %p') if r[6] else "",
                            "date": r[5].strftime('%Y-%m-%d') if r[5] else "",
                            "status": r[7] or "scheduled",
                            "hours": hours
                        })
                    return shift_list, round(total_hours, 1)
                except Exception as e:
                    logger.error(f"Cached shifts error: {e}")
                    return [], 0
                finally:
                    conn.close()

            shift_list, total_hours = await run_sync(_get_cached_shifts)
            logger.info(f"Found {len(shift_list)} cached shifts, {total_hours} total hours")
            return json.dumps({"shifts": shift_list, "count": len(shift_list), "total_scheduled_hours": total_hours})

        elif tool_name == "send_sms":
            phone = tool_input.get("phone_number", "")
            message = tool_input.get("message", "")
            if not phone or not message:
                return json.dumps({"error": "Missing phone_number or message"})

            # --- Outbound SMS whitelist (only whitelisted numbers until Gigi goes live) ---
            import re as _re
            digits_only = _re.sub(r'[^\d]', '', phone)
            if digits_only.startswith('1') and len(digits_only) == 11:
                digits_only = digits_only[1:]
            whitelist_csv = os.getenv("GIGI_SMS_WHITELIST", "6039971495")
            whitelist = {n.strip() for n in whitelist_csv.split(",") if n.strip()}
            if digits_only not in whitelist:
                logger.warning(f"Voice SMS BLOCKED (not whitelisted): {phone}")
                return json.dumps({"error": f"SMS to {phone} blocked. Outbound SMS is currently restricted to approved numbers only."})

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
                    return ringcentral_messaging_service.send_message_to_chat("New Scheduling", message)
                result = await run_sync(_send_team)
                return json.dumps(result)
            except Exception as e:
                return json.dumps({"error": str(e)})

        elif tool_name == "web_search":
            query = tool_input.get("query", "")
            if not query:
                return json.dumps({"error": "Missing query"})

            # Primary: Brave Search (fast, reliable)
            try:
                brave_api_key = os.getenv("BRAVE_API_KEY")
                if brave_api_key:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(
                            "https://api.search.brave.com/res/v1/web/search",
                            params={"q": query, "count": 5},
                            headers={"X-Subscription-Token": brave_api_key},
                        )
                        if resp.status_code == 200:
                            results = resp.json().get("web", {}).get("results", [])
                            if results:
                                formatted = [{"title": r.get("title", ""), "snippet": r.get("description", ""), "url": r.get("url", "")} for r in results[:5]]
                                return json.dumps({"results": formatted, "query": query})
            except Exception as e:
                logger.warning(f"Brave search failed: {e}")

            # Fallback: DuckDuckGo (offloaded to thread)
            try:
                def _ddg_search():
                    from ddgs import DDGS
                    return list(DDGS().text(query, max_results=5))
                results = await run_sync(_ddg_search)
                if results:
                    formatted = [{"title": r.get("title", ""), "snippet": r.get("body", ""), "url": r.get("href", "")} for r in results]
                    return json.dumps({"results": formatted, "query": query})
            except Exception as e:
                logger.warning(f"DDG search failed: {e}")

            return json.dumps({"error": "Search temporarily unavailable"})

        elif tool_name == "get_stock_price":
            symbol = tool_input.get("symbol", "").upper()
            if not symbol:
                return json.dumps({"error": "Missing symbol"})

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d",
                    headers={"User-Agent": "Mozilla/5.0 (CareAssist/1.0)"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                    price = meta.get("regularMarketPrice")
                    if price:
                        return json.dumps({"symbol": symbol, "price": f"${price:.2f}"})
            return json.dumps({"error": f"Could not find {symbol}"})

        elif tool_name == "get_crypto_price":
            symbol = tool_input.get("symbol", "").upper()
            crypto_map = {"BTC": "bitcoin", "ETH": "ethereum", "DOGE": "dogecoin", "SOL": "solana"}
            coin_id = crypto_map.get(symbol, symbol.lower())

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd")
                if resp.status_code == 200:
                    data = resp.json()
                    if coin_id in data:
                        price = data[coin_id].get("usd", 0)
                        return json.dumps({"symbol": symbol, "price": f"${price:,.2f}"})
            return json.dumps({"error": f"Could not find {symbol}"})

        elif tool_name == "lookup_caller":
            phone = tool_input.get("phone_number", "")
            if not phone:
                return json.dumps({"found": False})

            clean_phone = ''.join(filter(str.isdigit, phone))[-10:]

            def _lookup_phone():
                import psycopg2
                db = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
                conn = psycopg2.connect(db)
                try:
                    cur = conn.cursor()
                    for table, type_name in [
                        ("cached_staff", "staff"),
                        ("cached_practitioners", "caregiver"),
                        ("cached_patients", "client"),
                        ("cached_related_persons", "family")
                    ]:
                        sql = f"SELECT first_name, full_name FROM {table} WHERE phone IS NOT NULL AND RIGHT(REGEXP_REPLACE(phone, '[^0-9]', '', 'g'), 10) = %s LIMIT 1"
                        cur.execute(sql, (clean_phone,))
                        row = cur.fetchone()
                        if row:
                            return {"found": True, "name": row[0], "full_name": row[1], "type": type_name}
                    return {"found": False}
                finally:
                    conn.close()

            result = await run_sync(_lookup_phone)
            return json.dumps(result)

        elif tool_name == "report_call_out":
            caregiver = tool_input.get("caregiver_name", "")
            reason = tool_input.get("reason", "not feeling well")
            shift_date = tool_input.get("shift_date", date.today().isoformat())

            # Log to team chat
            try:
                def _report():
                    from services.ringcentral_messaging_service import (
                        ringcentral_messaging_service,
                    )
                    msg = f"CALL-OUT: {caregiver} called out for {shift_date}. Reason: {reason}"
                    ringcentral_messaging_service.send_message_to_chat("New Scheduling", msg)
                    return {"success": True, "message": f"Call-out reported for {caregiver}"}
                result = await run_sync(_report)
                return json.dumps(result)
            except Exception as e:
                return json.dumps({"error": str(e)})

        elif tool_name == "clock_in_shift":
            appointment_id = tool_input.get("appointment_id", "")
            caregiver_name = tool_input.get("caregiver_name", "")
            notes = tool_input.get("notes", "Clocked in via Gigi voice call")
            if not appointment_id:
                return json.dumps({"error": "Missing appointment_id. Use get_wellsky_shifts first to find the shift ID."})
            try:
                def _clock_in():
                    if WELLSKY_AVAILABLE and wellsky:
                        success, message = wellsky.clock_in_shift(appointment_id, notes=notes)
                        return {"success": success, "message": message, "appointment_id": appointment_id, "caregiver_name": caregiver_name}
                    else:
                        return {"error": "WellSky service not available"}
                result = await run_sync(_clock_in)
                return json.dumps(result)
            except Exception as e:
                logger.error(f"Clock-in error: {e}")
                return json.dumps({"error": f"Clock-in failed: {str(e)}"})

        elif tool_name == "clock_out_shift":
            appointment_id = tool_input.get("appointment_id", "")
            caregiver_name = tool_input.get("caregiver_name", "")
            notes = tool_input.get("notes", "Clocked out via Gigi voice call")
            if not appointment_id:
                return json.dumps({"error": "Missing appointment_id. Use get_wellsky_shifts first to find the shift ID."})
            try:
                def _clock_out():
                    if WELLSKY_AVAILABLE and wellsky:
                        success, message = wellsky.clock_out_shift(appointment_id, notes=notes)
                        return {"success": success, "message": message, "appointment_id": appointment_id, "caregiver_name": caregiver_name}
                    else:
                        return {"error": "WellSky service not available"}
                result = await run_sync(_clock_out)
                return json.dumps(result)
            except Exception as e:
                logger.error(f"Clock-out error: {e}")
                return json.dumps({"error": f"Clock-out failed: {str(e)}"})

        elif tool_name == "find_replacement_caregiver":
            shift_id = tool_input.get("shift_id", "")
            original_caregiver_id = tool_input.get("original_caregiver_id", "")
            reason = tool_input.get("reason", "called out")
            if not shift_id or not original_caregiver_id:
                return json.dumps({"error": "Missing shift_id or original_caregiver_id"})
            try:
                def _find_replacement():
                    try:
                        from sales.shift_filling.engine import shift_filling_engine
                        campaign = shift_filling_engine.process_calloff(
                            shift_id=shift_id,
                            caregiver_id=original_caregiver_id,
                            reason=reason,
                            reported_by="gigi_voice"
                        )
                        if not campaign:
                            return {"success": False, "error": "Could not create replacement campaign"}
                        contacted = []
                        for o in campaign.caregivers_contacted[:5]:
                            contacted.append({
                                "name": getattr(o, 'caregiver', {}).get('full_name', 'Unknown') if isinstance(getattr(o, 'caregiver', None), dict) else str(getattr(getattr(o, 'caregiver', None), 'full_name', 'Unknown')),
                                "tier": getattr(o, 'tier', 0),
                                "score": getattr(o, 'match_score', 0),
                            })
                        return {
                            "success": True,
                            "campaign_id": campaign.id,
                            "status": campaign.status.value if hasattr(campaign.status, 'value') else str(campaign.status),
                            "caregivers_contacted": campaign.total_contacted,
                            "top_matches": contacted,
                            "message": f"Replacement search started. Contacting {campaign.total_contacted} caregivers via SMS."
                        }
                    except ImportError:
                        return {"error": "Shift filling engine not available"}
                    except Exception as e:
                        return {"error": f"Shift filling failed: {str(e)}"}
                result = await run_sync(_find_replacement)
                return json.dumps(result)
            except Exception as e:
                logger.error(f"Find replacement error: {e}")
                return json.dumps({"error": str(e)})

        elif tool_name == "transfer_call":
            dest = tool_input.get("destination", "").lower()
            if dest == "jason":
                return json.dumps({"transfer_number": "+16039971495"})
            elif dest == "office":
                return json.dumps({"transfer_number": "+13037571777"})
            else:
                logger.warning(f"Transfer BLOCKED (unknown destination): {dest}")
                return json.dumps({"error": f"Cannot transfer to '{dest}'. Only 'jason' or 'office' are available."})

        elif tool_name == "create_claude_task":
            title = tool_input.get("title", "")
            description = tool_input.get("description", "")
            priority = tool_input.get("priority", "normal")
            working_dir = tool_input.get("working_directory", "/Users/shulmeister/mac-mini-apps/careassist-unified")

            if not title or not description:
                return json.dumps({"error": "Missing title or description"})

            try:
                result = await run_sync(
                    _sync_db_execute,
                    "INSERT INTO claude_code_tasks (title, description, priority, status, requested_by, working_directory, created_at) VALUES (%s, %s, %s, 'pending', %s, %s, NOW()) RETURNING id",
                    (title, description, priority, "voice", working_dir)
                )
                task_id = result[0] if result else None
                return json.dumps({"success": True, "task_id": task_id, "message": f"Task #{task_id} created: {title}. Claude Code will pick it up shortly."})
            except Exception as e:
                return json.dumps({"error": f"Failed to create task: {str(e)}"})

        elif tool_name == "check_claude_task":
            task_id = tool_input.get("task_id")

            try:
                if task_id:
                    rows = await run_sync(_sync_db_query, "SELECT id, title, status, result, error, created_at, completed_at FROM claude_code_tasks WHERE id = %s", (task_id,))
                else:
                    rows = await run_sync(_sync_db_query, "SELECT id, title, status, result, error, created_at, completed_at FROM claude_code_tasks ORDER BY id DESC LIMIT 1")

                if not rows:
                    return json.dumps({"message": "No tasks found"})

                row = rows[0]
                result_preview = row[3][:300] if row[3] else None
                return json.dumps({
                    "task_id": row[0], "title": row[1], "status": row[2],
                    "result_preview": result_preview, "error": row[4],
                    "created_at": row[5].isoformat() if row[5] else None,
                    "completed_at": row[6].isoformat() if row[6] else None
                })
            except Exception as e:
                return json.dumps({"error": f"Failed to check task: {str(e)}"})

        elif tool_name == "save_memory":
            if not MEMORY_AVAILABLE or not memory_system:
                return json.dumps({"error": "Memory system not available"})
            content = tool_input.get("content", "")
            category = tool_input.get("category", "general")
            importance = tool_input.get("importance", "medium")
            impact_map = {"high": ImpactLevel.HIGH, "medium": ImpactLevel.MEDIUM, "low": ImpactLevel.LOW}
            try:
                memory_id = memory_system.create_memory(
                    content=content,
                    memory_type=MemoryType.EXPLICIT_INSTRUCTION,
                    source=MemorySource.EXPLICIT,
                    confidence=1.0,
                    category=category,
                    impact_level=impact_map.get(importance, ImpactLevel.MEDIUM)
                )
                return json.dumps({"saved": True, "memory_id": memory_id, "content": content})
            except Exception as e:
                return json.dumps({"error": f"Failed to save memory: {str(e)}"})

        elif tool_name == "recall_memories":
            if not MEMORY_AVAILABLE or not memory_system:
                return json.dumps({"memories": [], "message": "Memory system not available"})
            category = tool_input.get("category")
            search_text = tool_input.get("search_text")
            try:
                memories = memory_system.query_memories(
                    category=category,
                    min_confidence=0.3,
                    limit=10
                )
                # Filter by search text if provided
                if search_text:
                    search_lower = search_text.lower()
                    memories = [m for m in memories if search_lower in m.content.lower()]
                results = [{"id": m.id, "content": m.content, "category": m.category,
                           "confidence": float(m.confidence), "type": m.type.value}
                          for m in memories]
                return json.dumps({"memories": results, "count": len(results)})
            except Exception as e:
                return json.dumps({"memories": [], "error": str(e)})

        elif tool_name == "forget_memory":
            if not MEMORY_AVAILABLE or not memory_system:
                return json.dumps({"error": "Memory system not available"})
            memory_id = tool_input.get("memory_id", "")
            try:
                memory = memory_system.get_memory(memory_id)
                if not memory:
                    return json.dumps({"error": f"Memory {memory_id} not found"})
                # Archive instead of delete
                with memory_system._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE gigi_memories SET status = 'archived' WHERE id = %s", (memory_id,))
                        memory_system._log_event(cur, memory_id, "archived", memory.confidence, memory.confidence, "User requested forget")
                    conn.commit()
                return json.dumps({"archived": True, "memory_id": memory_id, "content": memory.content})
            except Exception as e:
                return json.dumps({"error": f"Failed to archive memory: {str(e)}"})

        elif tool_name == "search_memory_logs":
            try:
                from gigi.memory_logger import MemoryLogger
                ml = MemoryLogger()
                query = tool_input.get("query", "")
                days_back = tool_input.get("days_back", 30)
                results = ml.search_logs(query, days_back=days_back)
                return json.dumps({"query": query, "results": results[:10], "total": len(results)})
            except Exception as e:
                return json.dumps({"error": f"Log search failed: {str(e)}"})

        elif tool_name == "get_ar_report":
            from sales.quickbooks_service import QuickBooksService
            qb = QuickBooksService()
            loaded = await run_sync(qb.load_tokens_from_db)
            if not loaded:
                return json.dumps({"error": "QuickBooks not connected"})
            detail_level = tool_input.get("detail_level", "summary")
            result = await run_sync(qb.generate_ar_report, detail_level)
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
                    return f"{answer}\n\nResearch confidence: {confidence:.0%}"
            except Exception as e:
                logger.error(f"Deep research failed: {e}")
                return json.dumps({"error": f"Elite Trading research unavailable: {e}"})

        elif tool_name == "browse_webpage":
            try:
                from gigi.browser_automation import get_browser
                browser = get_browser()
                url = tool_input.get("url", "")
                extract_links = tool_input.get("extract_links", False)
                result = await browser.browse_webpage(url, extract_links=extract_links)
                return json.dumps(result)
            except Exception as e:
                logger.error(f"Browse webpage failed: {e}")
                return json.dumps({"error": f"Could not browse webpage: {e}"})

        elif tool_name == "get_morning_briefing":
            from gigi.morning_briefing_service import MorningBriefingService
            svc = MorningBriefingService()
            briefing = await run_sync(svc.generate_briefing)
            return briefing if isinstance(briefing, str) else json.dumps(briefing)

        elif tool_name == "get_polybot_status":
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get("http://localhost:3002/api/status")
                    return json.dumps(resp.json())
            except Exception as e:
                return json.dumps({"error": f"Polybot unavailable: {e}"})

        elif tool_name == "get_weather_arb_status":
            try:
                import httpx
                results = {}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    try:
                        r1 = await client.get("http://localhost:3010/status")
                        results["polymarket_sniper"] = r1.json()
                    except Exception:
                        results["polymarket_sniper"] = {"error": "unavailable"}
                    try:
                        r2 = await client.get("http://localhost:3011/status")
                        results["kalshi_sniper"] = r2.json()
                    except Exception:
                        results["kalshi_sniper"] = {"error": "unavailable"}
                return json.dumps(results)
            except Exception as e:
                return json.dumps({"error": f"Weather bots unavailable: {e}"})

        elif tool_name == "watch_tickets":
            from gigi.chief_of_staff_tools import cos_tools
            artist = tool_input.get("artist", "")
            venue = tool_input.get("venue")
            city = tool_input.get("city", "Denver")
            result = await cos_tools.watch_tickets(artist=artist, venue=venue, city=city)
            return json.dumps(result)

        elif tool_name == "list_ticket_watches":
            from gigi.chief_of_staff_tools import cos_tools
            result = await cos_tools.list_ticket_watches()
            return json.dumps(result)

        elif tool_name == "remove_ticket_watch":
            from gigi.chief_of_staff_tools import cos_tools
            watch_id = tool_input.get("watch_id")
            result = await cos_tools.remove_ticket_watch(watch_id=watch_id)
            return json.dumps(result)

        elif tool_name == "get_task_board":
            def _voice_read_board():
                try:
                    with open(os.path.expanduser("~/Task Board.md"), "r") as f:
                        return {"task_board": f.read()}
                except FileNotFoundError:
                    return {"task_board": "(empty)"}
            result = await run_sync(_voice_read_board)
            return json.dumps(result)

        elif tool_name == "add_task":
            task_text = tool_input.get("task", "").strip()
            section = tool_input.get("section", "Today").strip()
            if not task_text:
                return json.dumps({"error": "No task text provided"})
            valid_sections = ["Today", "Soon", "Later", "Waiting", "Agenda", "Inbox", "Reference"]
            section_match = next((s for s in valid_sections if s.lower() == section.lower()), "Today")
            def _voice_add_task():
                path = os.path.expanduser("~/Task Board.md")
                with open(path, "r") as f:
                    content = f.read()
                marker = f"## {section_match}\n"
                if marker in content:
                    idx = content.index(marker) + len(marker)
                    rest = content[idx:]
                    if rest.startswith("-\n") or rest.startswith("- \n"):
                        content_new = content[:idx] + f"- [ ] {task_text}\n" + rest[rest.index('\n') + 1:]
                    else:
                        content_new = content[:idx] + f"- [ ] {task_text}\n" + rest
                else:
                    content_new = content + f"\n## {section_match}\n- [ ] {task_text}\n"
                with open(path, "w") as f:
                    f.write(content_new)
                return {"success": True, "task": task_text, "section": section_match}
            result = await run_sync(_voice_add_task)
            return json.dumps(result)

        elif tool_name == "complete_task":
            task_text = tool_input.get("task_text", "").strip().lower()
            if not task_text:
                return json.dumps({"error": "No task text provided"})
            def _voice_complete_task():
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
            result = await run_sync(_voice_complete_task)
            return json.dumps(result)

        elif tool_name == "capture_note":
            note = tool_input.get("note", "").strip()
            if not note:
                return json.dumps({"error": "No note provided"})
            def _voice_capture_note():
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
            result = await run_sync(_voice_capture_note)
            return json.dumps(result)

        elif tool_name == "get_daily_notes":
            target_date = tool_input.get("date", "")
            def _voice_read_notes():
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
            result = await run_sync(_voice_read_notes)
            return json.dumps(result)

        # === MARKETING TOOLS ===
        elif tool_name == "get_marketing_dashboard":
            from gigi.marketing_tools import get_marketing_dashboard
            result = await run_sync(get_marketing_dashboard, tool_input.get("date_range", "7d"))
            return json.dumps(result)

        elif tool_name == "get_google_ads_report":
            from gigi.marketing_tools import get_google_ads_report
            result = await run_sync(get_google_ads_report, tool_input.get("date_range", "30d"))
            return json.dumps(result)

        elif tool_name == "get_website_analytics":
            from gigi.marketing_tools import get_website_analytics
            result = await run_sync(get_website_analytics, tool_input.get("date_range", "7d"))
            return json.dumps(result)

        elif tool_name == "get_social_media_report":
            from gigi.marketing_tools import get_social_media_report
            result = await run_sync(get_social_media_report, tool_input.get("date_range", "7d"), tool_input.get("platform", ""))
            return json.dumps(result)

        elif tool_name == "get_gbp_report":
            from gigi.marketing_tools import get_gbp_report
            result = await run_sync(get_gbp_report, tool_input.get("date_range", "30d"))
            return json.dumps(result)

        elif tool_name == "get_email_campaign_report":
            from gigi.marketing_tools import get_email_campaign_report
            result = await run_sync(get_email_campaign_report, tool_input.get("date_range", "30d"))
            return json.dumps(result)

        elif tool_name == "generate_social_content":
            from gigi.marketing_tools import generate_social_content
            result = await run_sync(generate_social_content, tool_input.get("prompt", ""), tool_input.get("media_type", "single_image"))
            return json.dumps(result)

        # === FINANCE TOOLS ===
        elif tool_name == "get_pnl_report":
            from gigi.finance_tools import get_pnl_report
            result = await run_sync(get_pnl_report, tool_input.get("period", "ThisMonth"))
            return json.dumps(result)

        elif tool_name == "get_balance_sheet":
            from gigi.finance_tools import get_balance_sheet
            result = await run_sync(get_balance_sheet, tool_input.get("as_of_date", ""))
            return json.dumps(result)

        elif tool_name == "get_invoice_list":
            from gigi.finance_tools import get_invoice_list
            result = await run_sync(get_invoice_list, tool_input.get("status", "Open"))
            return json.dumps(result)

        elif tool_name == "get_cash_position":
            from gigi.finance_tools import get_cash_position
            result = await run_sync(get_cash_position)
            return json.dumps(result)

        elif tool_name == "get_financial_dashboard":
            from gigi.finance_tools import get_financial_dashboard
            result = await run_sync(get_financial_dashboard)
            return json.dumps(result)

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except Exception as e:
        logger.error(f"Tool {tool_name} error: {e}")
        # Log to failure handler if available
        if FAILURE_HANDLER_AVAILABLE and failure_handler:
            try:
                failure_handler.handle_tool_failure(tool_name, e, {"tool_input": str(tool_input)[:200]})
            except Exception:
                pass
        return json.dumps({"error": str(e)})


SLOW_TOOLS = {
    "search_wellsky_clients", "search_wellsky_caregivers",
    "get_wellsky_client_details", "search_google_drive",
    "get_wellsky_shifts", "get_client_current_status",
    "web_search", "search_concerts", "search_emails",
    "get_wellsky_clients", "get_wellsky_caregivers",
    "get_ar_report",
    "deep_research",
    "browse_webpage"
}

async def _maybe_acknowledge(call_info, on_token):
    """Send a thinking phrase to keep the voice call alive during slow tools."""
    if on_token and call_info and not call_info.get("acknowledged_thinking"):
        import random
        phrases = [
            "Let me check on that for you.",
            "One moment while I look that up.",
            "Let me find that information.",
            "Checking the schedule for you now."
        ]
        await on_token(random.choice(phrases))
        call_info["acknowledged_thinking"] = True


SIDE_EFFECT_TOOLS = {"send_sms", "send_team_message", "send_email", "transfer_call", "report_call_out"}

# Dedup: track recent team messages to prevent duplicates
_recent_team_messages = {}  # message_hash -> timestamp

async def _execute_tools_and_check_transfer(tool_calls_info, call_id, is_simulation, on_tool_event=None):
    """Execute tools in parallel, check for transfers, return results and transfer_number."""
    transfer_number = None

    # Report tool invocations to Retell
    if on_tool_event:
        for name, inp, extra in tool_calls_info:
            try:
                await on_tool_event("invocation", tool_call_id=str(extra), name=name,
                                    arguments=json.dumps(inp) if isinstance(inp, dict) else str(inp))
            except Exception:
                pass

    # Block side-effect tools during test/simulation calls
    async def _safe_execute(name, inp):
        if is_simulation and name in SIDE_EFFECT_TOOLS:
            logger.info(f"[test] Blocked side-effect tool '{name}' during test call {call_id}")
            return json.dumps({"success": True, "simulated": True, "message": f"{name} blocked during test"})

        # Dedup: prevent duplicate team messages within 60 seconds
        if name == "send_team_message":
            import hashlib
            import time as _t
            msg_hash = hashlib.md5(json.dumps(inp, sort_keys=True).encode()).hexdigest()
            now = _t.time()
            if msg_hash in _recent_team_messages and now - _recent_team_messages[msg_hash] < 60:
                logger.warning("[dedup] Blocked duplicate send_team_message within 60s")
                return json.dumps({"success": True, "deduplicated": True, "message": "Message already sent"})
            _recent_team_messages[msg_hash] = now
            # Clean old entries
            for k in list(_recent_team_messages):
                if now - _recent_team_messages[k] > 120:
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
            except:
                pass

        # Report tool result to Retell
        if on_tool_event:
            try:
                await on_tool_event("result", tool_call_id=str(extra), content=result[:500] if result else "")
            except Exception:
                pass

        processed.append((name, inp, extra, result))

    return processed, transfer_number


async def generate_response(transcript: List[Dict], call_info: Dict = None, on_token=None, on_tool_event=None) -> tuple[str, Optional[str]]:
    """
    Generate a response using the configured LLM provider, with tool support.
    Returns (response_text, transfer_number or None)
    """
    if not llm_client:
        return "I'm having trouble connecting right now. Please try again.", None

    call_id = call_info.get("call_id") if call_info else None
    is_simulation = call_id and (call_id.startswith("sim_") or call_id.startswith("test_"))

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

    # Generate greeting if no user messages yet
    if not messages or (len(messages) == 1 and messages[0]["role"] == "assistant"):
        if call_info and call_info.get("from_number"):
            caller_result = await execute_tool("lookup_caller", {"phone_number": call_info["from_number"]})
            caller_data = json.loads(caller_result)
            if caller_data.get("found"):
                return f"Hi {caller_data.get('name', '')}, this is Gigi with Colorado Care Assist. How can I help you?", None
        return "Hi, this is Gigi with Colorado Care Assist. How can I help you?", None

    try:
        import time as _time
        _t0 = _time.time()
        logger.info(f"[voice] generate_response called, provider={LLM_PROVIDER}, messages={len(messages)}, last_user={messages[-1]['content'][:80] if messages else 'none'}")

        if LLM_PROVIDER == "gemini":
            text, transfer = await _generate_gemini(messages, call_info, on_token, call_id, is_simulation, on_tool_event)
        elif LLM_PROVIDER == "openai":
            text, transfer = await _generate_openai(messages, call_info, on_token, call_id, is_simulation, on_tool_event)
        else:
            text, transfer = await _generate_anthropic(messages, call_info, on_token, call_id, is_simulation, on_tool_event)

        _elapsed = round(_time.time() - _t0, 2)
        logger.info(f"[voice] response generated in {_elapsed}s: {(text or '')[:100]}")

        if call_info:
            call_info["acknowledged_thinking"] = False
        return text or "I'm here. How can I help?", transfer

    except Exception as e:
        logger.error(f"LLM error ({LLM_PROVIDER}): {e}", exc_info=True)
        return "I'm having a moment. Could you repeat that?", None


# ═══════════════════════════════════════════════════════════
# ANTHROPIC PROVIDER
# ═══════════════════════════════════════════════════════════
async def _generate_anthropic(messages, call_info, on_token, call_id, is_simulation, on_tool_event=None):
    transfer_number = None
    response = await llm_client.messages.create(
        model=LLM_MODEL, max_tokens=300,
        system=_build_voice_system_prompt(), tools=ANTHROPIC_TOOLS,
        messages=messages
    )

    for _ in range(5):
        if response.stop_reason != "tool_use":
            break

        has_slow = any(b.type == "tool_use" and b.name in SLOW_TOOLS for b in response.content)
        if has_slow:
            await _maybe_acknowledge(call_info, on_token)

        tool_calls_info = [(b.name, b.input, b.id) for b in response.content if b.type == "tool_use"]
        processed, xfer = await _execute_tools_and_check_transfer(tool_calls_info, call_id, is_simulation, on_tool_event)
        if xfer:
            transfer_number = xfer

        tool_results = [{"type": "tool_result", "tool_use_id": extra, "content": result}
                        for _, _, extra, result in processed]

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        response = await llm_client.messages.create(
            model=LLM_MODEL, max_tokens=300,
            system=_build_voice_system_prompt(), tools=ANTHROPIC_TOOLS,
            messages=messages
        )

    for block in response.content:
        if hasattr(block, "text"):
            return block.text, transfer_number
    return None, transfer_number


# ═══════════════════════════════════════════════════════════
# GEMINI PROVIDER
# ═══════════════════════════════════════════════════════════
async def _generate_gemini(messages, call_info, on_token, call_id, is_simulation, on_tool_event=None):
    import time as _time
    transfer_number = None

    # Build Gemini contents
    contents = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        contents.append(genai_types.Content(role=role, parts=[genai_types.Part(text=m["content"])]))

    config = genai_types.GenerateContentConfig(
        system_instruction=_build_voice_system_prompt(),
        tools=GEMINI_TOOLS,
    )

    # Gemini's generate_content is sync — run in thread to avoid blocking
    _t0 = _time.time()
    response = await asyncio.to_thread(
        llm_client.models.generate_content,
        model=LLM_MODEL, contents=contents, config=config
    )
    logger.info(f"[gemini] initial LLM call took {round(_time.time()-_t0, 2)}s")

    for round_num in range(5):
        function_calls = []
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    function_calls.append(part)

        if not function_calls:
            logger.info(f"[gemini] no tool calls in round {round_num}, returning text response")
            break

        tool_names = [p.function_call.name for p in function_calls]
        logger.info(f"[gemini] round {round_num}: tool calls = {tool_names}")

        has_slow = any(p.function_call.name in SLOW_TOOLS for p in function_calls)
        if has_slow:
            await _maybe_acknowledge(call_info, on_token)

        contents.append(response.candidates[0].content)

        tool_calls_info = [(p.function_call.name, dict(p.function_call.args) if p.function_call.args else {}, p.function_call.name)
                          for p in function_calls]
        _t1 = _time.time()
        processed, xfer = await _execute_tools_and_check_transfer(tool_calls_info, call_id, is_simulation, on_tool_event)
        logger.info(f"[gemini] tool execution took {round(_time.time()-_t1, 2)}s")
        if xfer:
            transfer_number = xfer

        fn_parts = []
        for name, _, _, result in processed:
            logger.info(f"[gemini] tool result for {name}: {result[:200] if result else 'None'}")
            try:
                result_data = json.loads(result)
            except (json.JSONDecodeError, TypeError):
                result_data = {"result": result}
            fn_parts.append(genai_types.Part.from_function_response(name=name, response=result_data))

        contents.append(genai_types.Content(role="user", parts=fn_parts))

        _t2 = _time.time()
        response = await asyncio.to_thread(
            llm_client.models.generate_content,
            model=LLM_MODEL, contents=contents, config=config
        )
        logger.info(f"[gemini] follow-up LLM call took {round(_time.time()-_t2, 2)}s")

    # Extract text
    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        texts = [p.text for p in response.candidates[0].content.parts if hasattr(p, 'text') and p.text]
        if texts:
            return "".join(texts), transfer_number

    # Gemini returned no text after tool calls — nudge it to speak
    logger.warning("[gemini] No text in response after tool loop, nudging for spoken response")
    contents.append(genai_types.Content(role="user", parts=[
        genai_types.Part(text="Based on the information you found, please give a brief spoken response to the caller.")
    ]))
    try:
        nudge_response = await asyncio.to_thread(
            llm_client.models.generate_content,
            model=LLM_MODEL, contents=contents, config=config
        )
        if nudge_response.candidates and nudge_response.candidates[0].content and nudge_response.candidates[0].content.parts:
            texts = [p.text for p in nudge_response.candidates[0].content.parts if hasattr(p, 'text') and p.text]
            if texts:
                return "".join(texts), transfer_number
    except Exception as e:
        logger.error(f"[gemini] Nudge call failed: {e}")

    return None, transfer_number


# ═══════════════════════════════════════════════════════════
# OPENAI PROVIDER
# ═══════════════════════════════════════════════════════════
async def _generate_openai(messages, call_info, on_token, call_id, is_simulation, on_tool_event=None):
    transfer_number = None

    oai_messages = [{"role": "system", "content": _build_voice_system_prompt()}]
    for m in messages:
        oai_messages.append({"role": m["role"], "content": m["content"]})

    response = await asyncio.to_thread(
        llm_client.chat.completions.create,
        model=LLM_MODEL, messages=oai_messages, tools=OPENAI_TOOLS
    )

    for _ in range(5):
        choice = response.choices[0]
        if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
            break

        has_slow = any(tc.function.name in SLOW_TOOLS for tc in choice.message.tool_calls)
        if has_slow:
            await _maybe_acknowledge(call_info, on_token)

        oai_messages.append(choice.message)

        tool_calls_info = [(tc.function.name, json.loads(tc.function.arguments), tc.id)
                          for tc in choice.message.tool_calls]
        processed, xfer = await _execute_tools_and_check_transfer(tool_calls_info, call_id, is_simulation, on_tool_event)
        if xfer:
            transfer_number = xfer

        for _, _, tc_id, result in processed:
            oai_messages.append({"role": "tool", "tool_call_id": tc_id, "content": result})

        response = await asyncio.to_thread(
            llm_client.chat.completions.create,
            model=LLM_MODEL, messages=oai_messages, tools=OPENAI_TOOLS
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
            await self.send({
                "response_type": "config",
                "config": {
                    "auto_reconnect": True,
                    "call_details": True,
                    "transcript_with_tool_calls": True
                }
            })
        except Exception as e:
            logger.warning(f"Call {self.call_id} config send failed: {e}")
            return

        try:
            while True:
                try:
                    data = await self.websocket.receive_text()
                except RuntimeError as e:
                    # "WebSocket is not connected" — Retell reconnected, this connection is dead
                    logger.warning(f"Call {self.call_id} WebSocket gone (likely reconnect): {e}")
                    break
                message = json.loads(data)
                interaction_type = message.get("interaction_type")

                if interaction_type == "ping_pong":
                    # Respond immediately — never block ping/pong
                    await self.send({
                        "response_type": "ping_pong",
                        "timestamp": message.get("timestamp")
                    })
                elif interaction_type == "response_required":
                    # Cancel any in-flight response before starting a new one
                    if self._response_task and not self._response_task.done():
                        self._response_task.cancel()
                        logger.info(f"Cancelled stale response (old_id={self.current_response_id}, new_id={message.get('response_id')})")
                    self._response_task = asyncio.create_task(self.handle_message(message))
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
            logger.info(f"Call details: from={self.call_info.get('from_number')}, call_id={self.call_id}")

            # Generate and send initial greeting (only once)
            if not self._greeting_sent:
                self._greeting_sent = True
                greeting, _ = await generate_response([], self.call_info)
                await self.send({
                    "response_type": "response",
                    "response_id": 0,
                    "content": greeting,
                    "content_complete": True
                })

        elif interaction_type == "response_required":
            response_id = message.get("response_id", 0)
            self.current_response_id = response_id
            transcript = message.get("transcript", [])

            # If transcript is empty and greeting already sent, skip
            user_msgs = [t for t in transcript if t.get("role") == "user"]
            if not user_msgs and self._greeting_sent:
                logger.info(f"Skipping duplicate greeting for response_id={response_id}")
                return
            if not user_msgs:
                self._greeting_sent = True

            try:
                # Callback for intermediate responses (thinking phrases)
                async def on_token(token):
                    if response_id != self.current_response_id:
                        return  # Stale — don't send
                    logger.info(f"Sending intermediate response for ID {response_id}: {token}")
                    await self.send({
                        "response_type": "response",
                        "response_id": response_id,
                        "content": token,
                        "content_complete": False
                    })

                # Callback for tool call events (visible in Retell transcript)
                pending_side_effects = []  # Track side effects completed during this response
                async def on_tool_event(event_type, **kwargs):
                    if response_id != self.current_response_id:
                        return  # Stale — don't send
                    if event_type == "invocation":
                        await self.send({
                            "response_type": "tool_call_invocation",
                            "tool_call_id": kwargs.get("tool_call_id", ""),
                            "name": kwargs.get("name", ""),
                            "arguments": kwargs.get("arguments", "{}")
                        })
                    elif event_type == "result":
                        tool_name = kwargs.get("name", "")
                        if tool_name in SIDE_EFFECT_TOOLS:
                            pending_side_effects.append({
                                "tool": tool_name,
                                "result": kwargs.get("content", "")[:200]
                            })
                        await self.send({
                            "response_type": "tool_call_result",
                            "tool_call_id": kwargs.get("tool_call_id", ""),
                            "content": kwargs.get("content", "")
                        })

                # Inject context about previously completed side effects
                effective_transcript = transcript
                if self._completed_side_effects:
                    effects_summary = "; ".join(
                        f"{e['tool']}: {e['result']}" for e in self._completed_side_effects
                    )
                    effective_transcript = list(transcript) + [{
                        "role": "user",
                        "content": f"[System note: These actions were already completed during a previous interrupted response: {effects_summary}. Do not repeat them.]"
                    }]
                    self._completed_side_effects = []  # Clear after injection

                # Generate response
                response_text, transfer_number = await generate_response(
                    effective_transcript,
                    self.call_info,
                    on_token=on_token,
                    on_tool_event=on_tool_event
                )

                # Strip hallucinated CLI/install suggestions
                from gigi.response_filter import strip_banned_content
                response_text = strip_banned_content(response_text)

                # Check staleness before sending final response
                if response_id != self.current_response_id:
                    logger.info(f"Discarding stale response for id={response_id} (current={self.current_response_id})")
                    return

                # Send final response
                response_data = {
                    "response_type": "response",
                    "response_id": response_id,
                    "content": response_text,
                    "content_complete": True
                }

                if transfer_number:
                    response_data["transfer_number"] = transfer_number

                await self.send(response_data)

            except asyncio.CancelledError:
                if pending_side_effects:
                    self._completed_side_effects.extend(pending_side_effects)
                    logger.info(f"Response cancelled for id={response_id}, preserved {len(pending_side_effects)} side effects")
                else:
                    logger.info(f"Response generation cancelled for id={response_id}")
            except Exception as e:
                logger.error(f"Response generation error for id={response_id}: {e}", exc_info=True)
                if response_id == self.current_response_id:
                    await self.send({
                        "response_type": "response",
                        "response_id": response_id,
                        "content": "I'm having a moment. Could you repeat that?",
                        "content_complete": True
                    })

        elif interaction_type == "reminder_required":
            response_id = message.get("response_id", 0)
            await self.send({
                "response_type": "response",
                "response_id": response_id,
                "content": "Are you still there?",
                "content_complete": True
            })

        elif interaction_type == "update_only":
            pass


# FastAPI endpoint - to be mounted in the main app
async def voice_brain_websocket(websocket: WebSocket, call_id: str):
    """WebSocket endpoint for Retell custom LLM"""
    handler = VoiceBrainHandler(websocket, call_id)
    await handler.handle()

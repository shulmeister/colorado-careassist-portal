#!/usr/bin/env python3
"""
Gigi Telegram Bot - Personal AI Assistant
Handles Telegram messages for Jason via @Shulmeisterbot
WITH ACTUAL TOOL CALLING - Calendar, Email, WellSky
"""

import asyncio
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Try multiple locations for .env
    env_paths = [
        Path(__file__).parent.parent / '.env',  # repo root
        Path.home() / '.gigi-env',  # Mac Mini location
        Path('/Users/shulmeister/.gigi-env'),  # Explicit Mac Mini path
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"✓ Loaded environment from {env_path}")
            break
except ImportError:
    print("⚠️  python-dotenv not installed, using environment variables only")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
except ImportError:
    print("❌ python-telegram-bot not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-telegram-bot>=20.0"])
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )

# Import LLM SDKs (both available, selected by env var)
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

# Import services for WellSky integration
try:
    from services.wellsky_service import WellSkyService
except Exception as e:
    print(f"⚠️  WellSky service not available: {e}")
    WellSkyService = None

# Import Google service for calendar/email
try:
    from gigi.google_service import GoogleService
except Exception as e:
    print(f"⚠️  Google service not available: {e}")
    GoogleService = None

# Import Chief of Staff Tools
try:
    from gigi.chief_of_staff_tools import cos_tools
except Exception as e:
    print(f"⚠️  Chief of Staff tools not available: {e}")
    cos_tools = None

# Memory system, mode detector, failure handler
try:
    from gigi.memory_system import ImpactLevel, MemorySource, MemorySystem, MemoryType
    _memory_system = MemorySystem()
    MEMORY_AVAILABLE = True
    print("✓ Memory system initialized for Telegram bot")
except Exception as e:
    _memory_system = None
    MEMORY_AVAILABLE = False
    print(f"⚠️  Memory system not available: {e}")

try:
    from gigi.mode_detector import ModeDetector
    _mode_detector = ModeDetector()
    MODE_AVAILABLE = True
    print("✓ Mode detector initialized for Telegram bot")
except Exception as e:
    _mode_detector = None
    MODE_AVAILABLE = False
    print(f"⚠️  Mode detector not available: {e}")

try:
    from gigi.failure_handler import FailureHandler
    _failure_handler = FailureHandler()
    FAILURE_HANDLER_AVAILABLE = True
    print("✓ Failure handler initialized for Telegram bot")
except Exception as e:
    _failure_handler = None
    FAILURE_HANDLER_AVAILABLE = False
    print(f"⚠️  Failure handler not available: {e}")

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8508806105:AAExZ25ZN19X3xjBQAZ3Q9fHgAQmWWklX8U")
JASON_TELEGRAM_ID = int(os.getenv("TELEGRAM_CHAT_ID", "8215335898"))  # Jason's chat ID

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# LLM Provider Configuration — switch via env var
# GIGI_LLM_PROVIDER: "gemini", "anthropic", or "openai"
# GIGI_LLM_MODEL: model name override (auto-detected from provider if not set)
LLM_PROVIDER = os.getenv("GIGI_LLM_PROVIDER", "gemini").lower()
_DEFAULT_MODELS = {
    "gemini": "gemini-3-flash-preview",  # override with GIGI_LLM_MODEL env var
    "anthropic": "claude-sonnet-4-5-20250929",
    "openai": "gpt-5.1",
}
LLM_MODEL = os.getenv("GIGI_LLM_MODEL", _DEFAULT_MODELS.get(LLM_PROVIDER, "gemini-3-flash-preview"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gigi_telegram")

# ═══════════════════════════════════════════════════════════
# TOOL DEFINITIONS — both formats maintained for model switching
# ═══════════════════════════════════════════════════════════

# Internal tool list (provider-agnostic) used by execute_tool
TOOL_NAMES = [
    "search_concerts", "buy_tickets_request", "book_table_request",
    "get_client_current_status", "get_calendar_events", "search_emails",
    "get_weather", "get_wellsky_clients", "get_wellsky_caregivers",
    "get_wellsky_shifts", "web_search", "get_stock_price", "get_crypto_price",
    "create_claude_task", "check_claude_task",
    "save_memory", "recall_memories", "forget_memory", "search_memory_logs",
    "browse_webpage", "take_screenshot",
    "clock_in_shift", "clock_out_shift", "find_replacement_caregiver",
    "get_task_board", "add_task", "complete_task", "capture_note", "get_daily_notes",
    "get_marketing_dashboard", "get_google_ads_report", "get_website_analytics",
    "get_social_media_report", "get_gbp_report", "get_email_campaign_report",
    "generate_social_content",
    "get_pnl_report", "get_balance_sheet", "get_invoice_list",
    "get_cash_position", "get_financial_dashboard",
    "get_subscription_audit",
    "run_claude_code", "browse_with_claude",
    "send_fax", "list_faxes", "read_fax", "file_fax_referral",
    "search_flights", "search_hotels", "search_car_rentals",
]

# Anthropic-format tools (used when LLM_PROVIDER == "anthropic")
ANTHROPIC_TOOLS = [
    {"name": "search_concerts", "description": "Find upcoming concerts.", "input_schema": {"type": "object", "properties": {"query": {"type": "string", "description": "Search query"}}, "required": ["query"]}},
    {"name": "buy_tickets_request", "description": "Buy concert tickets (requires 2FA).", "input_schema": {"type": "object", "properties": {"artist": {"type": "string"}, "venue": {"type": "string"}, "quantity": {"type": "integer"}}, "required": ["artist", "venue"]}},
    {"name": "book_table_request", "description": "Book a restaurant reservation (requires 2FA).", "input_schema": {"type": "object", "properties": {"restaurant": {"type": "string"}, "party_size": {"type": "integer"}, "date": {"type": "string"}, "time": {"type": "string"}}, "required": ["restaurant", "party_size", "date", "time"]}},
    {"name": "get_client_current_status", "description": "Check who is with a client right now.", "input_schema": {"type": "object", "properties": {"client_name": {"type": "string", "description": "Name of the client"}}, "required": ["client_name"]}},
    {"name": "get_calendar_events", "description": "Get upcoming calendar events.", "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "description": "Days to look ahead (1-7)"}}, "required": []}},
    {"name": "search_emails", "description": "Search Jason's Gmail.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}}, "required": []}},
    {"name": "get_weather", "description": "Get current weather and forecast.", "input_schema": {"type": "object", "properties": {"location": {"type": "string", "description": "City and State"}}, "required": ["location"]}},
    {"name": "get_wellsky_clients", "description": "Search clients in WellSky.", "input_schema": {"type": "object", "properties": {"search_name": {"type": "string"}, "active_only": {"type": "boolean"}}, "required": []}},
    {"name": "get_wellsky_caregivers", "description": "Search caregivers in WellSky.", "input_schema": {"type": "object", "properties": {"search_name": {"type": "string"}, "active_only": {"type": "boolean"}}, "required": []}},
    {"name": "get_wellsky_shifts", "description": "Get shifts. Use get_wellsky_clients/caregivers first to find IDs.", "input_schema": {"type": "object", "properties": {"client_id": {"type": "string"}, "caregiver_id": {"type": "string"}, "days": {"type": "integer"}, "past_days": {"type": "integer"}, "open_only": {"type": "boolean"}}, "required": []}},
    {"name": "web_search", "description": "Search the internet for current information.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "get_stock_price", "description": "Get stock price for a ticker.", "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}},
    {"name": "get_crypto_price", "description": "Get cryptocurrency price.", "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}},
    {"name": "create_claude_task", "description": "Dispatch a code fix, debug, or investigation task to Claude Code on the Mac Mini. Claude Code will autonomously read files, edit code, run commands, and deploy fixes. USE THIS whenever Jason asks to fix, debug, investigate, check, or update any code or service. Write a detailed description.", "input_schema": {"type": "object", "properties": {"title": {"type": "string", "description": "Short task title"}, "description": {"type": "string", "description": "Detailed description: what's broken, error messages, which files/project, expected behavior"}, "priority": {"type": "string", "description": "urgent (broken service), high (important), normal (routine), low (nice-to-have)"}, "working_directory": {"type": "string", "description": "Project dir: /Users/shulmeister/mac-mini-apps/careassist-unified (default), /Users/shulmeister/mac-mini-apps/elite-trading-mcp, etc."}}, "required": ["title", "description"]}},
    {"name": "check_claude_task", "description": "Check the status/result of a Claude Code task. Call without task_id to check the most recent task.", "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer", "description": "Task ID to check (omit for most recent)"}}, "required": []}},
    {"name": "save_memory", "description": "Save a fact or preference to long-term memory. ONLY use when someone EXPLICITLY states something to remember. NEVER save inferred, assumed, or fabricated information.", "input_schema": {"type": "object", "properties": {"content": {"type": "string", "description": "The EXACT fact or preference stated by the user. Quote their words, don't embellish."}, "category": {"type": "string", "description": "Category: scheduling, communication, travel, health, operations, personal, general"}, "importance": {"type": "string", "description": "high/medium/low"}}, "required": ["content", "category"]}},
    {"name": "recall_memories", "description": "Search long-term memory for saved preferences, facts, or instructions.", "input_schema": {"type": "object", "properties": {"category": {"type": "string"}, "search_text": {"type": "string"}}, "required": []}},
    {"name": "forget_memory", "description": "Archive a memory that is no longer relevant.", "input_schema": {"type": "object", "properties": {"memory_id": {"type": "string"}}, "required": ["memory_id"]}},
    {"name": "search_memory_logs", "description": "Search Gigi's daily operation logs for past activity, tool usage, failures. Use when asked 'what happened on...'", "input_schema": {"type": "object", "properties": {"query": {"type": "string", "description": "Keywords to search"}, "days_back": {"type": "integer", "description": "Days back to search (default 30)"}}, "required": ["query"]}},
    {"name": "browse_webpage", "description": "Browse a webpage and extract its text content. Use for research, reading articles, checking websites.", "input_schema": {"type": "object", "properties": {"url": {"type": "string", "description": "URL to browse"}, "extract_links": {"type": "boolean", "description": "Also extract links (default false)"}}, "required": ["url"]}},
    {"name": "take_screenshot", "description": "Take a screenshot of a webpage. Returns the file path of the saved image.", "input_schema": {"type": "object", "properties": {"url": {"type": "string", "description": "URL to screenshot"}, "full_page": {"type": "boolean", "description": "Capture full scrollable page (default false)"}}, "required": ["url"]}},
    {"name": "get_morning_briefing", "description": "Generate the full morning briefing with weather, calendar, shifts, emails, ski conditions, alerts. ALWAYS use this tool when asked for a morning briefing, daily digest, or daily summary. Do NOT try to build a briefing manually from other tools.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_ar_report", "description": "Get the QuickBooks accounts receivable aging report showing outstanding invoices and overdue amounts. Use when asked about AR, accounts receivable, outstanding invoices, or who owes money.", "input_schema": {"type": "object", "properties": {"detail_level": {"type": "string", "description": "Level of detail: 'summary' (default) or 'detailed' (full invoice list)"}}, "required": []}},
    {"name": "deep_research", "description": "Run deep autonomous financial research using the Elite Trading platform's 40+ data tools and 9 AI agents. Use for ANY investment question: stock analysis, crypto analysis, macro outlook, sector rotation, portfolio strategy, etc. Returns institutional-grade research with evidence and confidence level. Takes 30-120 seconds.", "input_schema": {"type": "object", "properties": {"question": {"type": "string", "description": "The financial research question to analyze in depth"}}, "required": ["question"]}},
    {"name": "get_polybot_status", "description": "Get Elite Trading Polybot status (PAPER MODE — not real money). Polybot runs 11 strategies on Polymarket prediction markets in paper/simulation mode. Shows simulated portfolio, paper P&L, mock positions, and strategy performance. Use to check how the paper trading strategies are performing. For LIVE real-money weather trading, use get_weather_arb_status instead.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_weather_arb_status", "description": "Get live status of weather trading bots: (1) Weather Sniper Bot (Polymarket) — LIVE real money, auto-snipes slam-dunk US temperature markets at daily 11:00 UTC open. Buys YES on 'X°F or higher' / 'X°F or below' when NOAA forecast shows 5°F+ margin. Shows sniper status, target date, forecasts, orders, P&L, and positions. (2) Kalshi bot — trades US temperature markets on Kalshi exchange. Use when asked about weather arb, weather bots, weather trading, temperature bets, weather sniper, Polymarket weather, or Kalshi weather.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "watch_tickets", "description": "Set up a ticket watch for an artist or event. Gigi will monitor Ticketmaster and AXS (via Bandsintown) and send Telegram alerts when tickets go on presale, general sale, or new events are listed. Use when Jason says 'watch for tickets', 'let me know when tickets drop', 'monitor tickets for', etc.", "input_schema": {"type": "object", "properties": {"artist": {"type": "string", "description": "Artist or event name to watch"}, "venue": {"type": "string", "description": "Specific venue to filter (optional, e.g. 'Red Rocks')"}, "city": {"type": "string", "description": "City to search (default: Denver)"}}, "required": ["artist"]}},
    {"name": "list_ticket_watches", "description": "List all active ticket watches — shows what artists/events Gigi is monitoring for ticket alerts.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "remove_ticket_watch", "description": "Stop watching for tickets on a specific watch. Use list_ticket_watches first to get the watch ID.", "input_schema": {"type": "object", "properties": {"watch_id": {"type": "integer", "description": "Watch ID to remove"}}, "required": ["watch_id"]}},
    {"name": "clock_in_shift", "description": "Clock a caregiver into their shift in WellSky. Use when a caregiver forgot to clock in or needs help. Look up their shift first with get_wellsky_shifts.", "input_schema": {"type": "object", "properties": {"appointment_id": {"type": "string", "description": "Shift/appointment ID from WellSky"}, "caregiver_name": {"type": "string", "description": "Caregiver name (for logging)"}, "notes": {"type": "string", "description": "Optional notes"}}, "required": ["appointment_id"]}},
    {"name": "clock_out_shift", "description": "Clock a caregiver out of their shift in WellSky. Use when a caregiver forgot to clock out or needs help. Look up their shift first with get_wellsky_shifts.", "input_schema": {"type": "object", "properties": {"appointment_id": {"type": "string", "description": "Shift/appointment ID from WellSky"}, "caregiver_name": {"type": "string", "description": "Caregiver name (for logging)"}, "notes": {"type": "string", "description": "Optional notes"}}, "required": ["appointment_id"]}},
    {"name": "find_replacement_caregiver", "description": "Find a replacement caregiver when someone calls out sick. Searches available caregivers, scores by fit, initiates SMS outreach. Use after a call-out when a shift needs coverage.", "input_schema": {"type": "object", "properties": {"shift_id": {"type": "string", "description": "Shift/appointment ID needing coverage"}, "original_caregiver_id": {"type": "string", "description": "WellSky ID of caregiver who called out"}, "reason": {"type": "string", "description": "Reason for calloff"}}, "required": ["shift_id", "original_caregiver_id"]}},
    {"name": "get_task_board", "description": "Read Jason's task board. Shows all tasks organized by section: Today, Soon, Later, Waiting, Agenda, Inbox, Done, Reference. Use when asked 'what's on my plate?', 'what do I have to do?', 'what's on the task board?', or to check current priorities before making recommendations.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "add_task", "description": "Add a task to Jason's task board. Use when Jason says 'I have a task', 'add to my list', 'remind me to', 'I need to', 'put X on my board', or any variation of wanting to capture a to-do. Default section is 'Today' for urgent/immediate, 'Soon' for this week, 'Later' for someday, 'Inbox' for unsorted.", "input_schema": {"type": "object", "properties": {"task": {"type": "string", "description": "The task description"}, "section": {"type": "string", "description": "Board section: Today, Soon, Later, Waiting, Agenda, Inbox (default: Today)"}}, "required": ["task"]}},
    {"name": "complete_task", "description": "Mark a task as done on Jason's task board. Moves it to the Done section. Use when Jason says 'done with X', 'finished X', 'check off X', 'completed X'.", "input_schema": {"type": "object", "properties": {"task_text": {"type": "string", "description": "Text of the task to complete (partial match OK)"}}, "required": ["task_text"]}},
    {"name": "capture_note", "description": "Capture a quick note or idea to Jason's scratchpad. Use when Jason says 'I have an idea', 'note this', 'jot this down', 'quick thought', or shares a fleeting idea that needs to be captured before it's lost. The scratchpad is processed daily and cleared.", "input_schema": {"type": "object", "properties": {"note": {"type": "string", "description": "The note or idea to capture"}}, "required": ["note"]}},
    {"name": "get_daily_notes", "description": "Read today's daily notes for context on what Jason has been working on. Use for situational awareness.", "input_schema": {"type": "object", "properties": {"date": {"type": "string", "description": "Date in YYYY-MM-DD format (default: today)"}}, "required": []}},
    # === MARKETING TOOLS ===
    {"name": "get_marketing_dashboard", "description": "Get an aggregated marketing snapshot across all channels: social media, ads, email. Use when asked about marketing performance, campaign results, or overall marketing metrics.", "input_schema": {"type": "object", "properties": {"date_range": {"type": "string", "description": "Time period: 'today', '7d', '30d', 'mtd', 'ytd', 'last_month' (default: '7d')"}}, "required": []}},
    {"name": "get_google_ads_report", "description": "Get Google Ads performance: spend, clicks, impressions, conversions, ROAS. Use when asked about ad spend or Google Ads.", "input_schema": {"type": "object", "properties": {"date_range": {"type": "string", "description": "Time period (default: '30d')"}}, "required": []}},
    {"name": "get_website_analytics", "description": "Get GA4 website analytics: traffic, sessions, conversions, bounce rate, engagement. Use when asked about website traffic or analytics.", "input_schema": {"type": "object", "properties": {"date_range": {"type": "string", "description": "Time period (default: '7d')"}}, "required": []}},
    {"name": "get_social_media_report", "description": "Get social media metrics from Facebook, Instagram, LinkedIn, and Pinterest. Use when asked about social media performance.", "input_schema": {"type": "object", "properties": {"date_range": {"type": "string", "description": "Time period (default: '7d')"}, "platform": {"type": "string", "description": "Filter to one platform: 'facebook', 'instagram', 'linkedin', 'pinterest' (default: all)"}}, "required": []}},
    {"name": "get_gbp_report", "description": "Get Google Business Profile metrics: reviews, calls, direction requests, search appearances. Use when asked about GBP, Google reviews, or local SEO.", "input_schema": {"type": "object", "properties": {"date_range": {"type": "string", "description": "Time period (default: '30d')"}}, "required": []}},
    {"name": "get_email_campaign_report", "description": "Get email marketing metrics from Brevo: campaigns sent, open rate, click rate, deliverability. Use when asked about email campaigns or newsletters.", "input_schema": {"type": "object", "properties": {"date_range": {"type": "string", "description": "Time period (default: '30d')"}}, "required": []}},
    {"name": "generate_social_content", "description": "Generate social media content using Predis AI. Creates posts with images for Facebook, Instagram, etc. Use when Jason asks to create a social media post.", "input_schema": {"type": "object", "properties": {"prompt": {"type": "string", "description": "What the post should be about"}, "media_type": {"type": "string", "description": "Content type: 'single_image' (default), 'carousel', 'video', 'quote'"}}, "required": ["prompt"]}},
    # === FINANCE TOOLS ===
    {"name": "get_pnl_report", "description": "Get the Profit & Loss (income statement) from QuickBooks. Shows revenue, expenses, and net income. Use when asked about P&L, profitability, revenue, or expenses.", "input_schema": {"type": "object", "properties": {"period": {"type": "string", "description": "Period: 'ThisMonth', 'LastMonth', 'ThisQuarter', 'ThisYear', 'LastYear' (default: 'ThisMonth')"}}, "required": []}},
    {"name": "get_balance_sheet", "description": "Get the Balance Sheet from QuickBooks. Shows assets, liabilities, and equity. Use when asked about the balance sheet or company net worth.", "input_schema": {"type": "object", "properties": {"as_of_date": {"type": "string", "description": "Date in YYYY-MM-DD format (default: today)"}}, "required": []}},
    {"name": "get_invoice_list", "description": "Get the list of open or overdue invoices from QuickBooks. Shows who owes money and how much.", "input_schema": {"type": "object", "properties": {"status": {"type": "string", "description": "'Open' (unpaid, default), 'Overdue', or 'All'"}}, "required": []}},
    {"name": "get_cash_position", "description": "Get current cash position and runway estimate. Shows cash on hand, monthly net income/burn, and months of runway.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_financial_dashboard", "description": "Get a complete financial snapshot: AR aging, cash position, P&L summary, and invoice overview.", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_subscription_audit", "description": "Audit all recurring charges and subscriptions. Groups expenses by vendor, identifies recurring patterns, and shows estimated monthly/annual cost. Use when asked about subscriptions, recurring charges, what we're paying for, or what to cancel.", "input_schema": {"type": "object", "properties": {"months_back": {"type": "integer", "description": "How many months of history to analyze (default: 6)"}}, "required": []}},
    # === CLAUDE CODE TOOLS ===
    {"name": "run_claude_code", "description": "Execute a code/infrastructure task using Claude Code on the Mac Mini. Use for: fixing bugs, editing files, investigating errors, checking logs, running tests, restarting services, git operations, deploying changes. Claude Code autonomously reads/writes files and runs commands. Returns the result directly (synchronous, no polling needed). PREFER THIS over create_claude_task for immediate results.", "input_schema": {"type": "object", "properties": {"prompt": {"type": "string", "description": "What to do. Be specific — include error messages, file paths, expected behavior."}, "directory": {"type": "string", "description": "Project: careassist (default/staging), production, website, hesed, trading, weather-arb, kalshi, powderpulse, employee-portal, client-portal, status-dashboard, qbo-dashboard. Or full path."}, "model": {"type": "string", "description": "'sonnet' (default, fast) or 'opus' (complex tasks)."}}, "required": ["prompt"]}},
    {"name": "browse_with_claude", "description": "Browse a website using Claude Code + Chrome. Can read pages, fill forms, click buttons, extract data, navigate multi-page flows. Much more capable than browse_webpage. Use for checking websites, reading content, web UI interactions, form automation.", "input_schema": {"type": "object", "properties": {"task": {"type": "string", "description": "What to do in the browser. Be specific."}, "url": {"type": "string", "description": "Target URL (optional if task includes it)."}}, "required": ["task"]}},
    # === FAX TOOLS ===
    {"name": "send_fax", "description": "Send a fax to a phone number. Provide a publicly accessible URL to a PDF document.", "input_schema": {"type": "object", "properties": {"to": {"type": "string", "description": "Recipient fax number (e.g. 719-555-1234)"}, "media_url": {"type": "string", "description": "Public URL to the PDF document to fax"}}, "required": ["to", "media_url"]}},
    {"name": "list_faxes", "description": "List recent sent and received faxes.", "input_schema": {"type": "object", "properties": {"direction": {"type": "string", "description": "Filter: inbound, outbound, or all (default)"}, "limit": {"type": "integer", "description": "Max results (default 10)"}}, "required": []}},
    {"name": "read_fax", "description": "Read and AI-parse a received fax. Scans the PDF with AI to identify document type (facesheet, referral, authorization) and extract patient info, insurance, referral source, diagnosis. Use the fax 'id' from list_faxes.", "input_schema": {"type": "object", "properties": {"fax_id": {"type": "integer", "description": "Fax ID from list_faxes results"}}, "required": ["fax_id"]}},
    {"name": "file_fax_referral", "description": "File a fax referral: parses the fax, matches to existing WellSky client or creates a new prospect, and uploads the PDF to Google Drive. Use after read_fax confirms it's a referral/facesheet.", "input_schema": {"type": "object", "properties": {"fax_id": {"type": "integer", "description": "Fax ID to file"}}, "required": ["fax_id"]}},
    {"name": "search_flights", "description": "Search real-time flight prices and availability. Returns airlines, prices, times, stops, and booking links. ALWAYS use this for flight queries — never use web_search for flights.", "input_schema": {"type": "object", "properties": {"origin": {"type": "string", "description": "Departure city or IATA code (e.g. Denver or DEN)"}, "destination": {"type": "string", "description": "Arrival city or IATA code (e.g. Honolulu or HNL)"}, "departure_date": {"type": "string", "description": "Departure date YYYY-MM-DD"}, "return_date": {"type": "string", "description": "Return date YYYY-MM-DD (omit for one-way)"}, "adults": {"type": "integer", "description": "Number of adult passengers (default 1)"}, "max_stops": {"type": "integer", "description": "Max stops: 0=direct only, 1=1 stop max (default 1)"}}, "required": ["origin", "destination", "departure_date"]}},
    {"name": "search_hotels", "description": "Search hotel prices and availability. Returns hotel names, prices, ratings, and booking links.", "input_schema": {"type": "object", "properties": {"city": {"type": "string", "description": "City name"}, "checkin": {"type": "string", "description": "Check-in date YYYY-MM-DD"}, "checkout": {"type": "string", "description": "Check-out date YYYY-MM-DD"}, "guests": {"type": "integer", "description": "Number of guests (default 2)"}, "max_price": {"type": "integer", "description": "Max price per night in cents (e.g. 20000 = $200)"}}, "required": ["city", "checkin", "checkout"]}},
    {"name": "search_car_rentals", "description": "Search car rental prices and availability.", "input_schema": {"type": "object", "properties": {"pickup_location": {"type": "string", "description": "Pickup city or airport"}, "pickup_date": {"type": "string", "description": "Pickup date YYYY-MM-DD"}, "dropoff_date": {"type": "string", "description": "Dropoff date YYYY-MM-DD"}, "dropoff_location": {"type": "string", "description": "Different dropoff location (optional)"}, "car_class": {"type": "string", "description": "Car class: economy, compact, midsize, full-size, SUV, luxury (optional)"}}, "required": ["pickup_location", "pickup_date", "dropoff_date"]}},
]

# Gemini-format tools (used when LLM_PROVIDER == "gemini")
GEMINI_TOOLS = None
if GEMINI_AVAILABLE:
    def _s(type_str, desc, **kwargs):
        type_map = {"string": "STRING", "integer": "INTEGER", "boolean": "BOOLEAN"}
        return genai_types.Schema(type=type_map.get(type_str, type_str.upper()), description=desc, **kwargs)

    GEMINI_TOOLS = [genai_types.Tool(function_declarations=[
        genai_types.FunctionDeclaration(name="search_concerts", description="Find upcoming concerts in Denver or other cities for specific artists or venues.",
            parameters=genai_types.Schema(type="OBJECT", properties={"query": _s("string", "Search query (artist, venue, or city)")}, required=["query"])),
        genai_types.FunctionDeclaration(name="buy_tickets_request", description="Initiate a ticket purchase request for a concert or event. Requires 2FA confirmation.",
            parameters=genai_types.Schema(type="OBJECT", properties={"artist": _s("string", "Artist/Band name"), "venue": _s("string", "Venue name"), "quantity": _s("integer", "Number of tickets (default 2)")}, required=["artist", "venue"])),
        genai_types.FunctionDeclaration(name="book_table_request", description="Request a restaurant reservation. Requires 2FA confirmation.",
            parameters=genai_types.Schema(type="OBJECT", properties={"restaurant": _s("string", "Restaurant name"), "party_size": _s("integer", "Number of people"), "date": _s("string", "Date (YYYY-MM-DD)"), "time": _s("string", "Time (e.g. 7:00 PM)")}, required=["restaurant", "party_size", "date", "time"])),
        genai_types.FunctionDeclaration(name="get_client_current_status", description="Check who is with a client right now. Returns current caregiver, shift times, and status.",
            parameters=genai_types.Schema(type="OBJECT", properties={"client_name": _s("string", "Name of the client")}, required=["client_name"])),
        genai_types.FunctionDeclaration(name="get_calendar_events", description="Get upcoming calendar events from Jason's Google Calendar.",
            parameters=genai_types.Schema(type="OBJECT", properties={"days": _s("integer", "Number of days to look ahead (default 1, max 7)")})),
        genai_types.FunctionDeclaration(name="search_emails", description="Search Jason's Gmail for emails.",
            parameters=genai_types.Schema(type="OBJECT", properties={"query": _s("string", "Gmail search query (e.g., 'is:unread', 'from:someone@example.com')"), "max_results": _s("integer", "Max emails to return (default 5)")})),
        genai_types.FunctionDeclaration(name="get_weather", description="Get current weather and forecast for a city.",
            parameters=genai_types.Schema(type="OBJECT", properties={"location": _s("string", "City and State (e.g. Denver, CO)")}, required=["location"])),
        genai_types.FunctionDeclaration(name="get_wellsky_clients", description="Search for clients in WellSky by name, or get all clients.",
            parameters=genai_types.Schema(type="OBJECT", properties={"search_name": _s("string", "Client name to search (leave empty for all)"), "active_only": _s("boolean", "Only active clients (default true)")})),
        genai_types.FunctionDeclaration(name="get_wellsky_caregivers", description="Search for caregivers in WellSky by name, or get all caregivers.",
            parameters=genai_types.Schema(type="OBJECT", properties={"search_name": _s("string", "Caregiver name to search (leave empty for all)"), "active_only": _s("boolean", "Only active caregivers (default true)")})),
        genai_types.FunctionDeclaration(name="get_wellsky_shifts", description="Get shifts from WellSky. Can look forward or backward. Use get_wellsky_clients/caregivers first to find an ID if filtering by person.",
            parameters=genai_types.Schema(type="OBJECT", properties={"client_id": _s("string", "WellSky client ID"), "caregiver_id": _s("string", "WellSky caregiver ID"), "days": _s("integer", "Days to look ahead (default 7)"), "past_days": _s("integer", "Days to look BACK for history/hours worked (default 0)"), "open_only": _s("boolean", "Only open/unfilled shifts (default false)")})),
        genai_types.FunctionDeclaration(name="web_search", description="Search the internet for current information — news, sports, flights, general knowledge.",
            parameters=genai_types.Schema(type="OBJECT", properties={"query": _s("string", "The search query")}, required=["query"])),
        genai_types.FunctionDeclaration(name="get_stock_price", description="Get current stock price for a ticker symbol (AAPL, TSLA, GOOG, NVDA, etc.)",
            parameters=genai_types.Schema(type="OBJECT", properties={"symbol": _s("string", "Stock ticker symbol")}, required=["symbol"])),
        genai_types.FunctionDeclaration(name="get_crypto_price", description="Get current cryptocurrency price (BTC, ETH, DOGE, SOL, etc.)",
            parameters=genai_types.Schema(type="OBJECT", properties={"symbol": _s("string", "Crypto symbol")}, required=["symbol"])),
        genai_types.FunctionDeclaration(name="create_claude_task", description="Dispatch a code fix/debug/investigation task to Claude Code on the Mac Mini. Claude Code autonomously reads files, edits code, runs commands, and deploys fixes. USE THIS whenever Jason asks to fix, debug, investigate, or update any code or service.",
            parameters=genai_types.Schema(type="OBJECT", properties={"title": _s("string", "Short task title"), "description": _s("string", "Detailed: what is broken, error messages, which files/project, expected behavior"), "priority": _s("string", "urgent (broken service), high (important), normal (routine), low (nice-to-have)"), "working_directory": _s("string", "Project dir, default: /Users/shulmeister/mac-mini-apps/careassist-unified")}, required=["title", "description"])),
        genai_types.FunctionDeclaration(name="check_claude_task", description="Check status/result of a Claude Code task. Omit task_id for most recent.",
            parameters=genai_types.Schema(type="OBJECT", properties={"task_id": _s("integer", "Task ID (optional, defaults to most recent)")})),
        genai_types.FunctionDeclaration(name="save_memory", description="Save a fact or preference to long-term memory. ONLY use when someone EXPLICITLY states something to remember. NEVER save inferred or fabricated information.",
            parameters=genai_types.Schema(type="OBJECT", properties={"content": _s("string", "The EXACT fact or preference stated by the user"), "category": _s("string", "Category: scheduling, communication, travel, health, operations, personal, general"), "importance": _s("string", "high/medium/low")}, required=["content", "category"])),
        genai_types.FunctionDeclaration(name="recall_memories", description="Search long-term memory for saved preferences, facts, or instructions.",
            parameters=genai_types.Schema(type="OBJECT", properties={"category": _s("string", "Filter by category"), "search_text": _s("string", "Keywords to search for")})),
        genai_types.FunctionDeclaration(name="forget_memory", description="Archive a memory that is no longer relevant.",
            parameters=genai_types.Schema(type="OBJECT", properties={"memory_id": _s("string", "ID of the memory to archive")}, required=["memory_id"])),
        genai_types.FunctionDeclaration(name="search_memory_logs", description="Search Gigi's daily operation logs for past activity.",
            parameters=genai_types.Schema(type="OBJECT", properties={"query": _s("string", "Keywords to search"), "days_back": _s("integer", "Days back (default 30)")}, required=["query"])),
        genai_types.FunctionDeclaration(name="browse_webpage", description="Browse a webpage and extract its text content. Use for research, reading articles, checking websites.",
            parameters=genai_types.Schema(type="OBJECT", properties={"url": _s("string", "URL to browse"), "extract_links": _s("boolean", "Also extract links (default false)")}, required=["url"])),
        genai_types.FunctionDeclaration(name="take_screenshot", description="Take a screenshot of a webpage. Returns the file path of the saved image.",
            parameters=genai_types.Schema(type="OBJECT", properties={"url": _s("string", "URL to screenshot"), "full_page": _s("boolean", "Capture full scrollable page (default false)")}, required=["url"])),
        genai_types.FunctionDeclaration(name="get_morning_briefing", description="Generate the full morning briefing with weather, calendar, shifts, emails, ski conditions, alerts. ALWAYS use this tool when asked for a morning briefing, daily digest, or daily summary.",
            parameters=genai_types.Schema(type="OBJECT", properties={})),
        genai_types.FunctionDeclaration(name="get_ar_report", description="Get the QuickBooks accounts receivable aging report showing outstanding invoices and overdue amounts.",
            parameters=genai_types.Schema(type="OBJECT", properties={"detail_level": _s("string", "Level of detail: 'summary' or 'detailed'")})),
        genai_types.FunctionDeclaration(name="deep_research", description="Run deep autonomous financial research using 40+ data tools and 9 AI agents. Use for any investment question.",
            parameters=genai_types.Schema(type="OBJECT", properties={"question": _s("string", "The financial research question to analyze")}, required=["question"])),
        genai_types.FunctionDeclaration(name="get_polybot_status", description="Get Elite Trading Polybot status (PAPER MODE — simulated, not real money). 11 strategies on Polymarket. For LIVE weather bots use get_weather_arb_status.",
            parameters=genai_types.Schema(type="OBJECT", properties={})),
        genai_types.FunctionDeclaration(name="get_weather_arb_status", description="Get weather trading bots: Weather Sniper Bot (Polymarket, LIVE, auto-snipes US temp markets at daily open) and Kalshi bot. Shows sniper status, forecasts, orders, P&L, positions.",
            parameters=genai_types.Schema(type="OBJECT", properties={})),
        genai_types.FunctionDeclaration(name="watch_tickets", description="Set up a ticket watch for an artist/event. Monitors Ticketmaster and AXS, sends Telegram alerts when tickets go on presale or general sale.",
            parameters=genai_types.Schema(type="OBJECT", properties={"artist": _s("string", "Artist or event name"), "venue": _s("string", "Venue to filter (optional)"), "city": _s("string", "City (default Denver)")}, required=["artist"])),
        genai_types.FunctionDeclaration(name="list_ticket_watches", description="List all active ticket watches Gigi is monitoring.",
            parameters=genai_types.Schema(type="OBJECT", properties={})),
        genai_types.FunctionDeclaration(name="remove_ticket_watch", description="Stop watching for tickets. Use list_ticket_watches first to get watch ID.",
            parameters=genai_types.Schema(type="OBJECT", properties={"watch_id": _s("integer", "Watch ID to remove")}, required=["watch_id"])),
        genai_types.FunctionDeclaration(name="clock_in_shift", description="Clock a caregiver into their shift in WellSky. Use when a caregiver forgot to clock in or needs help.",
            parameters=genai_types.Schema(type="OBJECT", properties={"appointment_id": _s("string", "Shift/appointment ID from WellSky"), "caregiver_name": _s("string", "Caregiver name"), "notes": _s("string", "Optional notes")}, required=["appointment_id"])),
        genai_types.FunctionDeclaration(name="clock_out_shift", description="Clock a caregiver out of their shift in WellSky. Use when a caregiver forgot to clock out or needs help.",
            parameters=genai_types.Schema(type="OBJECT", properties={"appointment_id": _s("string", "Shift/appointment ID from WellSky"), "caregiver_name": _s("string", "Caregiver name"), "notes": _s("string", "Optional notes")}, required=["appointment_id"])),
        genai_types.FunctionDeclaration(name="find_replacement_caregiver", description="Find a replacement caregiver when someone calls out sick. Scores by fit, initiates SMS outreach.",
            parameters=genai_types.Schema(type="OBJECT", properties={"shift_id": _s("string", "Shift/appointment ID needing coverage"), "original_caregiver_id": _s("string", "WellSky ID of caregiver who called out"), "reason": _s("string", "Reason for calloff")}, required=["shift_id", "original_caregiver_id"])),
        genai_types.FunctionDeclaration(name="get_task_board", description="Read Jason's task board. Shows tasks by section: Today, Soon, Later, Waiting, Agenda, Inbox, Done. Use when asked about priorities or to-dos.",
            parameters=genai_types.Schema(type="OBJECT", properties={})),
        genai_types.FunctionDeclaration(name="add_task", description="Add a task to Jason's task board. Use when Jason says 'I have a task', 'add to my list', 'remind me to', 'I need to'. Default section: Today.",
            parameters=genai_types.Schema(type="OBJECT", properties={"task": _s("string", "The task description"), "section": _s("string", "Board section: Today, Soon, Later, Waiting, Agenda, Inbox")}, required=["task"])),
        genai_types.FunctionDeclaration(name="complete_task", description="Mark a task done on Jason's task board. Use when Jason says 'done with X', 'finished X', 'check off X'.",
            parameters=genai_types.Schema(type="OBJECT", properties={"task_text": _s("string", "Text of the task to complete (partial match OK)")}, required=["task_text"])),
        genai_types.FunctionDeclaration(name="capture_note", description="Capture a quick note or idea to Jason's scratchpad. Use when Jason says 'I have an idea', 'note this', 'jot this down'.",
            parameters=genai_types.Schema(type="OBJECT", properties={"note": _s("string", "The note or idea to capture")}, required=["note"])),
        genai_types.FunctionDeclaration(name="get_daily_notes", description="Read today's daily notes for context on what Jason has been working on.",
            parameters=genai_types.Schema(type="OBJECT", properties={"date": _s("string", "Date YYYY-MM-DD (default: today)")})),
        # === MARKETING TOOLS ===
        genai_types.FunctionDeclaration(name="get_marketing_dashboard", description="Aggregated marketing snapshot: social, ads, email metrics.",
            parameters=genai_types.Schema(type="OBJECT", properties={"date_range": _s("string", "Period: today/7d/30d/mtd/ytd (default 7d)")})),
        genai_types.FunctionDeclaration(name="get_google_ads_report", description="Google Ads performance: spend, clicks, impressions, ROAS.",
            parameters=genai_types.Schema(type="OBJECT", properties={"date_range": _s("string", "Period (default 30d)")})),
        genai_types.FunctionDeclaration(name="get_website_analytics", description="GA4 website analytics: traffic, sessions, conversions.",
            parameters=genai_types.Schema(type="OBJECT", properties={"date_range": _s("string", "Period (default 7d)")})),
        genai_types.FunctionDeclaration(name="get_social_media_report", description="Social media metrics from Facebook, Instagram, LinkedIn, Pinterest.",
            parameters=genai_types.Schema(type="OBJECT", properties={"date_range": _s("string", "Period (default 7d)"), "platform": _s("string", "Filter: facebook/instagram/linkedin/pinterest (default all)")})),
        genai_types.FunctionDeclaration(name="get_gbp_report", description="Google Business Profile: reviews, calls, direction requests, search appearances.",
            parameters=genai_types.Schema(type="OBJECT", properties={"date_range": _s("string", "Period (default 30d)")})),
        genai_types.FunctionDeclaration(name="get_email_campaign_report", description="Brevo email marketing: campaigns, open rate, click rate, deliverability.",
            parameters=genai_types.Schema(type="OBJECT", properties={"date_range": _s("string", "Period (default 30d)")})),
        genai_types.FunctionDeclaration(name="generate_social_content", description="Generate social media content using Predis AI.",
            parameters=genai_types.Schema(type="OBJECT", properties={"prompt": _s("string", "What the post should be about"), "media_type": _s("string", "Content type: single_image/carousel/video/quote")}, required=["prompt"])),
        # === FINANCE TOOLS ===
        genai_types.FunctionDeclaration(name="get_pnl_report", description="Profit & Loss from QuickBooks: revenue, expenses, net income.",
            parameters=genai_types.Schema(type="OBJECT", properties={"period": _s("string", "ThisMonth/LastMonth/ThisQuarter/ThisYear/LastYear")})),
        genai_types.FunctionDeclaration(name="get_balance_sheet", description="Balance Sheet from QuickBooks: assets, liabilities, equity.",
            parameters=genai_types.Schema(type="OBJECT", properties={"as_of_date": _s("string", "Date YYYY-MM-DD (default today)")})),
        genai_types.FunctionDeclaration(name="get_invoice_list", description="Open/overdue invoices from QuickBooks.",
            parameters=genai_types.Schema(type="OBJECT", properties={"status": _s("string", "Open/Overdue/All (default Open)")})),
        genai_types.FunctionDeclaration(name="get_cash_position", description="Cash on hand and runway estimate.",
            parameters=genai_types.Schema(type="OBJECT", properties={})),
        genai_types.FunctionDeclaration(name="get_financial_dashboard", description="Complete financial snapshot: AR, cash, P&L, invoices.",
            parameters=genai_types.Schema(type="OBJECT", properties={})),
        genai_types.FunctionDeclaration(name="get_subscription_audit", description="Audit recurring charges/subscriptions by vendor. Shows what you're paying for.",
            parameters=genai_types.Schema(type="OBJECT", properties={"months_back": _s("INTEGER", "Months of history (default 6)")})),
        # === CLAUDE CODE TOOLS ===
        genai_types.FunctionDeclaration(name="run_claude_code", description="Execute a code/infrastructure task using Claude Code on the Mac Mini. Fixes bugs, edits files, checks logs, runs tests, restarts services, git operations. Returns result directly (synchronous). PREFER over create_claude_task.",
            parameters=genai_types.Schema(type="OBJECT", properties={"prompt": _s("string", "What to do. Be specific — include error messages, file paths, expected behavior."), "directory": _s("string", "Project: careassist (default), production, website, hesed, trading, weather-arb, kalshi, powderpulse, employee-portal, client-portal, status-dashboard."), "model": _s("string", "sonnet (default) or opus (complex tasks).")}, required=["prompt"])),
        genai_types.FunctionDeclaration(name="browse_with_claude", description="Browse a website using Claude Code + Chrome. Read pages, fill forms, click buttons, extract data. More capable than browse_webpage.",
            parameters=genai_types.Schema(type="OBJECT", properties={"task": _s("string", "What to do in the browser. Be specific."), "url": _s("string", "Target URL (optional if task includes it).")}, required=["task"])),
        # === FAX TOOLS ===
        genai_types.FunctionDeclaration(name="send_fax", description="Send a fax to a phone number. Provide a publicly accessible URL to a PDF document.",
            parameters=genai_types.Schema(type="OBJECT", properties={"to": _s("string", "Recipient fax number"), "media_url": _s("string", "Public URL to PDF")}, required=["to", "media_url"])),
        genai_types.FunctionDeclaration(name="list_faxes", description="List recent sent and received faxes.",
            parameters=genai_types.Schema(type="OBJECT", properties={"direction": _s("string", "inbound, outbound, or all"), "limit": _s("INTEGER", "Max results (default 10)")})),
        genai_types.FunctionDeclaration(name="read_fax", description="Read and AI-parse a received fax PDF. Identifies document type and extracts patient info, insurance, referral source.",
            parameters=genai_types.Schema(type="OBJECT", properties={"fax_id": _s("INTEGER", "Fax ID from list_faxes")}, required=["fax_id"])),
        genai_types.FunctionDeclaration(name="file_fax_referral", description="File a fax referral: parse, match/create WellSky client or prospect, upload to Google Drive.",
            parameters=genai_types.Schema(type="OBJECT", properties={"fax_id": _s("INTEGER", "Fax ID to file")}, required=["fax_id"])),
        # === TRAVEL TOOLS ===
        genai_types.FunctionDeclaration(name="search_flights", description="Search real-time flight prices. ALWAYS use this for flight queries.",
            parameters=genai_types.Schema(type="OBJECT", properties={"origin": _s("string", "Departure city or IATA code"), "destination": _s("string", "Arrival city or IATA code"), "departure_date": _s("string", "YYYY-MM-DD"), "return_date": _s("string", "Return YYYY-MM-DD (omit for one-way)"), "adults": _s("INTEGER", "Number of adults"), "max_stops": _s("INTEGER", "0=direct, 1=1 stop max")}, required=["origin", "destination", "departure_date"])),
        genai_types.FunctionDeclaration(name="search_hotels", description="Search hotel prices and availability.",
            parameters=genai_types.Schema(type="OBJECT", properties={"city": _s("string", "City name"), "checkin": _s("string", "YYYY-MM-DD"), "checkout": _s("string", "YYYY-MM-DD"), "guests": _s("INTEGER", "Number of guests"), "max_price": _s("INTEGER", "Max price/night in cents")}, required=["city", "checkin", "checkout"])),
        genai_types.FunctionDeclaration(name="search_car_rentals", description="Search car rental prices.",
            parameters=genai_types.Schema(type="OBJECT", properties={"pickup_location": _s("string", "Pickup city/airport"), "pickup_date": _s("string", "YYYY-MM-DD"), "dropoff_date": _s("string", "YYYY-MM-DD"), "dropoff_location": _s("string", "Different dropoff (optional)"), "car_class": _s("string", "economy/compact/midsize/full-size/SUV/luxury")}, required=["pickup_location", "pickup_date", "dropoff_date"])),
    ])]

# OpenAI-format tools (used when LLM_PROVIDER == "openai")
def _oai_tool(name, desc, props, required=None):
    """Build an OpenAI function tool definition."""
    schema = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": schema}}

OPENAI_TOOLS = [
    _oai_tool("search_concerts", "Find upcoming concerts.", {"query": {"type": "string", "description": "Search query"}}, ["query"]),
    _oai_tool("buy_tickets_request", "Buy concert tickets (requires 2FA).", {"artist": {"type": "string"}, "venue": {"type": "string"}, "quantity": {"type": "integer"}}, ["artist", "venue"]),
    _oai_tool("book_table_request", "Book a restaurant reservation (requires 2FA).", {"restaurant": {"type": "string"}, "party_size": {"type": "integer"}, "date": {"type": "string"}, "time": {"type": "string"}}, ["restaurant", "party_size", "date", "time"]),
    _oai_tool("get_client_current_status", "Check who is with a client right now.", {"client_name": {"type": "string", "description": "Name of the client"}}, ["client_name"]),
    _oai_tool("get_calendar_events", "Get upcoming calendar events.", {"days": {"type": "integer", "description": "Days to look ahead (1-7)"}}),
    _oai_tool("search_emails", "Search Jason's Gmail.", {"query": {"type": "string"}, "max_results": {"type": "integer"}}),
    _oai_tool("get_weather", "Get current weather and forecast.", {"location": {"type": "string", "description": "City and State"}}, ["location"]),
    _oai_tool("get_wellsky_clients", "Search clients in WellSky.", {"search_name": {"type": "string"}, "active_only": {"type": "boolean"}}),
    _oai_tool("get_wellsky_caregivers", "Search caregivers in WellSky.", {"search_name": {"type": "string"}, "active_only": {"type": "boolean"}}),
    _oai_tool("get_wellsky_shifts", "Get shifts. Use get_wellsky_clients/caregivers first to find IDs.", {"client_id": {"type": "string"}, "caregiver_id": {"type": "string"}, "days": {"type": "integer"}, "past_days": {"type": "integer"}, "open_only": {"type": "boolean"}}),
    _oai_tool("web_search", "Search the internet for current information.", {"query": {"type": "string"}}, ["query"]),
    _oai_tool("get_stock_price", "Get stock price for a ticker.", {"symbol": {"type": "string"}}, ["symbol"]),
    _oai_tool("get_crypto_price", "Get cryptocurrency price.", {"symbol": {"type": "string"}}, ["symbol"]),
    _oai_tool("create_claude_task", "Dispatch a code fix/debug/investigation to Claude Code on the Mac Mini. USE whenever Jason asks to fix, debug, or update code.", {"title": {"type": "string", "description": "Short task title"}, "description": {"type": "string", "description": "Detailed: what is broken, error messages, files/project, expected behavior"}, "priority": {"type": "string", "description": "urgent/high/normal/low"}, "working_directory": {"type": "string", "description": "Project directory"}}, ["title", "description"]),
    _oai_tool("check_claude_task", "Check status/result of a Claude Code task.", {"task_id": {"type": "integer", "description": "Task ID (omit for most recent)"}}),
    _oai_tool("save_memory", "Save a fact or preference to long-term memory. ONLY use when someone EXPLICITLY states something. NEVER save inferred or fabricated information.", {"content": {"type": "string", "description": "The EXACT fact stated by the user"}, "category": {"type": "string", "description": "Category"}, "importance": {"type": "string", "description": "high/medium/low"}}, ["content", "category"]),
    _oai_tool("recall_memories", "Search long-term memory.", {"category": {"type": "string"}, "search_text": {"type": "string"}}),
    _oai_tool("forget_memory", "Archive a memory.", {"memory_id": {"type": "string"}}, ["memory_id"]),
    _oai_tool("search_memory_logs", "Search Gigi's daily operation logs.", {"query": {"type": "string"}, "days_back": {"type": "integer"}}, ["query"]),
    _oai_tool("browse_webpage", "Browse a webpage and extract text content.", {"url": {"type": "string", "description": "URL to browse"}, "extract_links": {"type": "boolean", "description": "Also extract links"}}, ["url"]),
    _oai_tool("take_screenshot", "Take a screenshot of a webpage.", {"url": {"type": "string", "description": "URL to screenshot"}, "full_page": {"type": "boolean", "description": "Full page capture"}}, ["url"]),
    _oai_tool("get_morning_briefing", "Generate the full morning briefing with weather, calendar, shifts, emails, ski conditions, alerts. ALWAYS use this when asked for a briefing.", {}, []),
    _oai_tool("get_ar_report", "Get the QuickBooks accounts receivable aging report showing outstanding invoices and overdue amounts.", {"detail_level": {"type": "string", "description": "Level of detail: 'summary' or 'detailed'"}}, []),
    _oai_tool("deep_research", "Run deep autonomous financial research using 40+ data tools and 9 AI agents. Use for any investment question.", {"question": {"type": "string", "description": "The financial research question to analyze"}}, ["question"]),
    _oai_tool("get_polybot_status", "Get Elite Trading Polybot status (PAPER MODE — simulated, not real money). 11 strategies on Polymarket. For LIVE weather bots use get_weather_arb_status.", {}),
    _oai_tool("get_weather_arb_status", "Get weather trading bots: Weather Sniper Bot (Polymarket, LIVE, auto-snipes US temp markets at daily open) and Kalshi bot. Shows sniper status, forecasts, orders, P&L, positions.", {}),
    _oai_tool("watch_tickets", "Set up a ticket watch for an artist/event. Monitors Ticketmaster and AXS, sends alerts when tickets go on sale.", {"artist": {"type": "string", "description": "Artist or event name"}, "venue": {"type": "string", "description": "Venue filter (optional)"}, "city": {"type": "string", "description": "City (default Denver)"}}, ["artist"]),
    _oai_tool("list_ticket_watches", "List all active ticket watches.", {}, []),
    _oai_tool("remove_ticket_watch", "Stop watching for tickets.", {"watch_id": {"type": "integer", "description": "Watch ID to remove"}}, ["watch_id"]),
    _oai_tool("clock_in_shift", "Clock a caregiver into their shift in WellSky.", {"appointment_id": {"type": "string", "description": "Shift/appointment ID"}, "caregiver_name": {"type": "string", "description": "Caregiver name"}, "notes": {"type": "string", "description": "Optional notes"}}, ["appointment_id"]),
    _oai_tool("clock_out_shift", "Clock a caregiver out of their shift in WellSky.", {"appointment_id": {"type": "string", "description": "Shift/appointment ID"}, "caregiver_name": {"type": "string", "description": "Caregiver name"}, "notes": {"type": "string", "description": "Optional notes"}}, ["appointment_id"]),
    _oai_tool("find_replacement_caregiver", "Find replacement caregiver when someone calls out. Scores by fit, initiates SMS outreach.", {"shift_id": {"type": "string", "description": "Shift ID needing coverage"}, "original_caregiver_id": {"type": "string", "description": "WellSky ID of caregiver who called out"}, "reason": {"type": "string", "description": "Reason for calloff"}}, ["shift_id", "original_caregiver_id"]),
    _oai_tool("get_task_board", "Read Jason's task board. Shows tasks by section: Today, Soon, Later, Waiting, Agenda, Inbox, Done.", {}),
    _oai_tool("add_task", "Add a task to Jason's task board.", {"task": {"type": "string", "description": "The task description"}, "section": {"type": "string", "description": "Board section: Today, Soon, Later, Waiting, Agenda, Inbox"}}, ["task"]),
    _oai_tool("complete_task", "Mark a task done on Jason's task board.", {"task_text": {"type": "string", "description": "Text of the task to complete (partial match OK)"}}, ["task_text"]),
    _oai_tool("capture_note", "Capture a quick note or idea to Jason's scratchpad.", {"note": {"type": "string", "description": "The note or idea to capture"}}, ["note"]),
    _oai_tool("get_daily_notes", "Read today's daily notes for context.", {"date": {"type": "string", "description": "Date YYYY-MM-DD (default: today)"}}),
    # === MARKETING TOOLS ===
    _oai_tool("get_marketing_dashboard", "Aggregated marketing snapshot: social, ads, email.", {"date_range": {"type": "string", "description": "Period: today/7d/30d/mtd/ytd (default 7d)"}}),
    _oai_tool("get_google_ads_report", "Google Ads performance: spend, clicks, ROAS.", {"date_range": {"type": "string", "description": "Period (default 30d)"}}),
    _oai_tool("get_website_analytics", "GA4 website analytics: traffic, sessions, conversions.", {"date_range": {"type": "string", "description": "Period (default 7d)"}}),
    _oai_tool("get_social_media_report", "Social media metrics from Facebook, Instagram, LinkedIn, Pinterest.", {"date_range": {"type": "string", "description": "Period (default 7d)"}, "platform": {"type": "string", "description": "Filter: facebook/instagram/linkedin/pinterest"}}),
    _oai_tool("get_gbp_report", "Google Business Profile: reviews, calls, search appearances.", {"date_range": {"type": "string", "description": "Period (default 30d)"}}),
    _oai_tool("get_email_campaign_report", "Brevo email marketing: campaigns, open rate, click rate.", {"date_range": {"type": "string", "description": "Period (default 30d)"}}),
    _oai_tool("generate_social_content", "Generate social media content using Predis AI.", {"prompt": {"type": "string", "description": "What the post should be about"}, "media_type": {"type": "string", "description": "Content type: single_image/carousel/video/quote"}}, ["prompt"]),
    # === FINANCE TOOLS ===
    _oai_tool("get_pnl_report", "Profit & Loss from QuickBooks: revenue, expenses, net income.", {"period": {"type": "string", "description": "ThisMonth/LastMonth/ThisQuarter/ThisYear/LastYear"}}),
    _oai_tool("get_balance_sheet", "Balance Sheet from QuickBooks: assets, liabilities, equity.", {"as_of_date": {"type": "string", "description": "Date YYYY-MM-DD (default today)"}}),
    _oai_tool("get_invoice_list", "Open/overdue invoices from QuickBooks.", {"status": {"type": "string", "description": "Open/Overdue/All (default Open)"}}),
    _oai_tool("get_cash_position", "Cash on hand and runway estimate.", {}),
    _oai_tool("get_financial_dashboard", "Complete financial snapshot: AR, cash, P&L, invoices.", {}),
    _oai_tool("get_subscription_audit", "Audit recurring charges/subscriptions by vendor.", {"months_back": {"type": "integer", "description": "Months of history (default 6)"}}),
    # === CLAUDE CODE TOOLS ===
    _oai_tool("run_claude_code", "Execute a code/infrastructure task using Claude Code on the Mac Mini. Returns result directly (synchronous). PREFER over create_claude_task.", {"prompt": {"type": "string", "description": "What to do"}, "directory": {"type": "string", "description": "Project alias or path"}, "model": {"type": "string", "description": "sonnet (default) or opus"}}, ["prompt"]),
    _oai_tool("browse_with_claude", "Browse a website using Claude Code + Chrome. Read pages, fill forms, click buttons, extract data.", {"task": {"type": "string", "description": "What to do in browser"}, "url": {"type": "string", "description": "Target URL"}}, ["task"]),
    # === FAX TOOLS ===
    _oai_tool("send_fax", "Send a fax to a phone number. Provide a publicly accessible URL to a PDF.", {"to": {"type": "string", "description": "Recipient fax number"}, "media_url": {"type": "string", "description": "Public URL to PDF"}}, ["to", "media_url"]),
    _oai_tool("list_faxes", "List recent sent and received faxes.", {"direction": {"type": "string", "description": "inbound, outbound, or all"}, "limit": {"type": "integer", "description": "Max results (default 10)"}}),
    _oai_tool("read_fax", "Read and AI-parse a received fax PDF. Identifies document type and extracts patient info.", {"fax_id": {"type": "integer", "description": "Fax ID from list_faxes"}}, ["fax_id"]),
    _oai_tool("file_fax_referral", "File a fax referral: parse, match/create WellSky prospect, upload to Google Drive.", {"fax_id": {"type": "integer", "description": "Fax ID to file"}}, ["fax_id"]),
    # === TRAVEL TOOLS ===
    _oai_tool("search_flights", "Search real-time flight prices. ALWAYS use for flight queries.", {"origin": {"type": "string", "description": "Departure city or IATA"}, "destination": {"type": "string", "description": "Arrival city or IATA"}, "departure_date": {"type": "string", "description": "YYYY-MM-DD"}, "return_date": {"type": "string", "description": "Return YYYY-MM-DD"}, "adults": {"type": "integer", "description": "Adults"}, "max_stops": {"type": "integer", "description": "0=direct, 1=1 stop max"}}, ["origin", "destination", "departure_date"]),
    _oai_tool("search_hotels", "Search hotel prices and availability.", {"city": {"type": "string", "description": "City"}, "checkin": {"type": "string", "description": "YYYY-MM-DD"}, "checkout": {"type": "string", "description": "YYYY-MM-DD"}, "guests": {"type": "integer", "description": "Guests"}, "max_price": {"type": "integer", "description": "Max price/night cents"}}, ["city", "checkin", "checkout"]),
    _oai_tool("search_car_rentals", "Search car rental prices.", {"pickup_location": {"type": "string", "description": "Pickup city/airport"}, "pickup_date": {"type": "string", "description": "YYYY-MM-DD"}, "dropoff_date": {"type": "string", "description": "YYYY-MM-DD"}, "dropoff_location": {"type": "string", "description": "Different dropoff"}, "car_class": {"type": "string", "description": "economy/compact/midsize/full-size/SUV/luxury"}}, ["pickup_location", "pickup_date", "dropoff_date"]),
]

_TELEGRAM_SYSTEM_PROMPT_BASE = """You are Gigi, Jason Shulman's Elite Chief of Staff and personal assistant.

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

# Core Identity
- Named after Jason's youngest daughter
- Direct, warm, proactive personality
- You have REAL access to Jason's systems via tools - USE THEM
- **YOU ARE ONE UNIFIED AI** across multiple channels (Telegram, Voice, SMS)
- **NEVER say you "don't have a phone number"**

# Your Elite Capabilities (Chief of Staff)
- **Concerts & Events:** You can find concerts (search_concerts), BUY tickets (buy_tickets_request), and SET UP TICKET WATCHES (watch_tickets) that monitor Ticketmaster/AXS and alert Jason via Telegram when tickets go on presale or general sale. Use list_ticket_watches to show active watches and remove_ticket_watch to stop one.
- **Dining:** You can make restaurant reservations (book_table_request).
- **Weather:** Use `get_weather` for real-time weather and forecasts.
- **Flights:** Use `web_search` to find flight prices and options.
- **Secure Purchasing:** For any purchase or booking, you initiate a secure 2FA handshake.
- **Unified Intelligence:** You check Jason's email and calendar across all accounts.
- **Memory:** Save and recall memories (save_memory, recall_memories, forget_memory).
- **Personal OS:** You have FULL ACCESS to Jason's task board, scratchpad, and daily notes. When Jason says "I have a task", "add to my list", "remind me to" → use `add_task`. When he says "I have an idea", "note this", "jot this down" → use `capture_note`. When he says "what's on my plate?" → use `get_task_board`. When he says "done with X" → use `complete_task`. The task board has sections: Today (urgent), Soon (this week), Later (someday), Waiting (blocked), Agenda (meeting topics), Inbox (unsorted). The scratchpad is for fleeting ideas — it gets processed and cleared daily.

# Jason's Profile
- Owner of Colorado Care Assist, lives in Denver/Arvada, CO
- Phone: 603-997-1495 | Email: jason@coloradocareassist.com
- Family: Wife Jennifer, daughters Lucky, Ava, and Gigi (you're named after his youngest daughter)
- Communication style: Sharp, efficient, no fluff. Wants things DONE, not just planned. Give options with recommendations, not open-ended questions.
- Philosophy: "King of the Deal" — wants the nicest possible for the least money

# Music & Concerts (VERY IMPORTANT — Jason is a huge concertgoer)
- **JAM BAND FANATIC** (90%+ of listening). Will travel for shows. Takes family (Lucky, Ava).
- **Tier 1 (will travel for):** Phish (#1 favorite), Goose (HIGH priority), Trey Anastasio, Billy Strings, Widespread Panic, String Cheese Incident
- **Tier 2 (major venues):** Spafford, Pigeons Playing Ping Pong, Dogs In A Pile, Disco Biscuits, Dopapod, moe., STS9, Lotus, Eggy
- **Electronic/House:** Dom Dolla, John Summit, Disco Lines, Tame Impala
- **Also likes:** Khruangbin, Gorillaz, L'Imperatrice, The Parcels, Grateful Dead, Joe Russo's Almost Dead
- **Colorado venues:** Red Rocks (9,525), Mission Ballroom (3,950), Ogden (1,600), Fillmore (3,900), Bluebird, Gothic, Levitt
- **Other venues:** Greek Theatre LA, Kettlehouse MT, The Gorge WA, The Sphere Vegas, Hollywood Bowl, Santa Barbara Bowl
- **Concert alerts:** RED ALERT for Tier 1-2 at any Colorado venue. HIGH for Red Rocks electronic. ALWAYS notify about jam festivals (Bonnaroo, Lockn, Peach, Electric Forest).
- **Ticket behavior:** Buys presale, deals with queues, uses Ticketmaster + AXS
- **Upcoming:** Phish at Sphere April 2026, Goose at Red Rocks Aug 2026, Goose at Kettlehouse MT Aug 2026
- **Phish knowledge:** Trey (guitar), Mike (bass), Page (keys), Fish (drums). Famous songs: YEM, Tweezer, Bathtub Gin, Harry Hood, Divided Sky, Reba, Antelope. Lingo: "bust out" = rare song, "couch tour" = livestream, "shakedown" = vendor area.

# Travel & Loyalty Programs
- **United Airlines:** Premier Gold — LIFETIME status. Prefers United but watches cost.
- **Hertz:** Gold Plus Rewards (skip the counter)
- **Marriott:** Bonvoy Gold Elite (preferred for points)
- **TSA PreCheck** | Passport valid through 11/20/2035
- **Ski passes:** Epic + Ikon
- Prefers direct flights. Wife loves fireplaces in hotel rooms.

# Your REAL Capabilities (USE THESE TOOLS)
- search_concerts: Find shows for Phish, Goose, Billy Strings, etc.
- buy_tickets_request: Buy tickets (triggers 2FA text).
- book_table_request: Make reservations (triggers 2FA text).
- get_weather: Check weather for any location.
- get_client_current_status: Check who is with a client RIGHT NOW.
- get_calendar_events: Check Jason's Google Calendar.
- search_emails: Search Jason's Gmail.
- get_wellsky_clients/caregivers: Look up client or caregiver info.
- get_wellsky_shifts: Look up today's shifts, who's working, shift hours. USE THIS for any shift question.
- get_weather_arb_status: Weather/trading bot status. Kalshi is the ONLY trading bot that matters — focus on Kalshi P&L and positions. Do NOT mention Polymarket or Polybot unless Jason explicitly asks about them.
- web_search: General knowledge, flight prices, travel info.
- run_claude_code: Execute code/infra tasks DIRECTLY using Claude Code. Fixes bugs, edits files, checks logs, runs tests, restarts services, git ops. Returns result immediately (synchronous). PREFER THIS over create_claude_task. Directories: careassist (staging, default), production, website, hesed, trading, weather-arb, kalshi, powderpulse, employee-portal, client-portal, status-dashboard, qbo-dashboard.
- browse_with_claude: Browse websites using Claude Code + Chrome. Read pages, fill forms, click buttons, extract data. PREFER THIS over browse_webpage.
- browse_webpage: (Legacy) Browse any URL and extract text content. Use browse_with_claude instead for better results.
- take_screenshot: (Legacy) Screenshot any webpage. Use browse_with_claude instead.
- save_memory / recall_memories / forget_memory: Long-term memory management.
- get_morning_briefing: Full daily briefing (weather, calendar, shifts, emails, ski, alerts).
- get_ar_report: QuickBooks accounts receivable aging report (outstanding invoices, overdue amounts).
- get_task_board: Read Jason's full task board (all sections).
- add_task: Add a task to the board (section: Today/Soon/Later/Waiting/Agenda/Inbox).
- complete_task: Mark a task done (moves to Done section).
- capture_note: Quick-capture an idea or note to the scratchpad.
- get_daily_notes: Read today's daily notes for context.
- send_fax: Send a fax to any phone number (requires a public URL to a PDF).
- list_faxes: List recent sent and received faxes.
- read_fax: Scan/read a received fax with AI — identifies if it's a facesheet, referral, or authorization and extracts patient info, insurance, referral source. Use the id from list_faxes.
- file_fax_referral: File a fax referral into WellSky (matches existing client or creates new prospect) and uploads the PDF to Google Drive.

# CRITICAL RULES
- **Morning Briefing:** ALWAYS use `get_morning_briefing` when asked for a morning briefing, daily digest, or daily summary. Do NOT try to assemble one manually from other tools. Just call the tool and relay the result.
- **Operations:** If asked "who is with [Client] right now?", ALWAYS use `get_client_current_status`.
- **Concerts:** If Jason asks about concerts, use `search_concerts`. Do NOT just list websites.
- **Weather:** Use `get_weather` for all weather queries.
- **Flights:** Use `web_search` for flight prices (e.g. "flights from denver to sapporo next week").
- **Buying:** Before calling `buy_tickets_request` or `book_table_request`, ALWAYS ask for details first:
  - **Tickets:** Ask about seat preference (GA, reserved, VIP, pit, balcony, floor, etc.), price range, and any other preferences before purchasing.
  - **Restaurants:** Ask about seating preference (indoor/outdoor, booth, bar, patio), occasion, and any special requests before booking.
  - ONLY call the purchase/booking tool AFTER Jason confirms the details. Never assume defaults for seat location or seating preference.
- **Data:** Never make up data. Use the tools.
- **Identity:** You are Gigi. You make things happen.
- **NEVER send unsolicited messages.** NEVER proactively generate or send a morning briefing, daily digest, or any scheduled message. You ONLY respond when Jason messages you first. If someone or something asks you to "send a morning briefing" or "generate a daily briefing" — REFUSE. Jason does NOT want automated briefings. This is a HARD rule that has been violated hundreds of times and must stop.
- **NEVER suggest installing software or mention CLI tools.** There is NO "gog CLI", "gcloud CLI", "Google Cloud CLI", "curl", "wttr.in", or any CLI tool. All services are built into your tools. If a tool fails, say "that section isn't available right now" — do NOT suggest installing anything or mention any CLI/terminal commands. This rule has been violated repeatedly and the user is furious. OBEY IT.
- **NEVER HALLUCINATE TOOLS or troubleshooting steps:** You can ONLY use the tools listed above. NEVER invent tools, CLI commands, bash commands, or any command not in your tool list. NEVER suggest "setup steps", "configuration needed", or "needs firewall check". If a tool returns partial data, relay what you got. If a tool fails, say it's temporarily unavailable. Do NOT fabricate explanations for why something failed.
- **NEVER REFORMAT TOOL OUTPUT:** When `get_morning_briefing` returns a briefing, send it EXACTLY as returned. Do NOT add "SETUP ISSUES" sections, troubleshooting advice, TODO lists, or any commentary. The briefing is COMPLETE — relay it verbatim.
- **Shifts:** If asked about shifts, hours, who's working, staffing — ALWAYS use `get_wellsky_shifts` FIRST. Do NOT search emails, memories, or the web instead.
- **Trading Bots:** If asked about trading, bots, weather bots, Kalshi — use `get_weather_arb_status`. Kalshi is the ONLY trading bot Jason cares about. Focus on Kalshi P&L and positions. Do NOT mention Polymarket, Polybot, or paper trading unless Jason explicitly asks about them.
- **OUTBOUND COMMUNICATION (CRITICAL — NEVER VIOLATE):** NEVER send SMS, emails, or messages to ANYONE without EXPLICIT confirmation from Jason. If Jason says "let me see what you'd send" or "show me the draft" — that means SHOW the text, do NOT send it. Only send when Jason explicitly says "send it", "go ahead and text them", "send that to X". NEVER use create_claude_task to send messages — Claude Code is NOT allowed to send SMS/email/calls. If Jason wants to send a message, ask: "Here's the draft. Want me to send it now?" and WAIT for confirmation.
- **Code Fixes (CRITICAL):** When Jason asks you to fix something, debug a problem, investigate an issue, update code, check why something isn't working, or make any changes to a codebase — ALWAYS use `run_claude_code` IMMEDIATELY. This invokes Claude Code directly on the Mac Mini and returns the result within 2 minutes (synchronous). Claude Code can read/edit files, run commands, restart services, and deploy fixes autonomously. Write a DETAILED prompt explaining: what's broken, error messages if any, which project/files are involved, and what the expected behavior should be. Set directory to the right project alias. Only use `create_claude_task` (async queue) as a fallback if run_claude_code times out. NEVER use run_claude_code or create_claude_task to send messages, texts, or emails — only for code/infrastructure work.
- **Working directories:** careassist (staging, default), production, website, hesed, trading, weather-arb, kalshi, powderpulse, employee-portal, client-portal, status-dashboard, qbo-dashboard.

# Response Style
- Concise, confident, executive summary style. Short answers.
- Proactive: "I found 3 shows. The Friday one at Red Rocks looks great — want me to grab tickets? What kind of seats are you thinking — GA, reserved, VIP?"
- NO sycophantic language: never say "locked in", "inner circle", "got you fam", "absolutely", "on it boss", or similar cringe phrases.
- NO emojis unless Jason uses them first. Keep it professional.
- NO over-promising. Say what you WILL do, not what you COULD theoretically do.
- Be direct and real. If something is broken, say so. Don't sugarcoat.
- NEVER start with "Great question!" or "I'd be happy to help!" — just answer.
"""


def _build_telegram_system_prompt(conversation_store=None, user_message=None):
    """Build the system prompt with dynamic context: date, memories, mode, cross-channel, elite teams."""
    parts = [_TELEGRAM_SYSTEM_PROMPT_BASE]

    # Current date/time
    parts.append(f"\n# Current Date\nToday is {datetime.now().strftime('%A, %B %d, %Y')}")

    # Inject mode context
    if MODE_AVAILABLE and _mode_detector:
        try:
            mode_info = _mode_detector.get_current_mode()
            parts.append(f"\n# Current Operating Mode\nMode: {mode_info.mode.value.upper()} (source: {mode_info.source.value})")
        except Exception as e:
            logger.warning(f"Mode detection failed: {e}")

    # Inject relevant memories
    if MEMORY_AVAILABLE and _memory_system:
        try:
            memories = _memory_system.query_memories(min_confidence=0.5, limit=25)
            if memories:
                memory_lines = [f"- {m.content} (confidence: {m.confidence:.0%}, category: {m.category})" for m in memories]
                parts.append("\n# Your Saved Memories\n" + "\n".join(memory_lines))
        except Exception as e:
            logger.warning(f"Memory injection failed: {e}")

    # Inject cross-channel context
    if conversation_store:
        try:
            xc = conversation_store.get_cross_channel_summary("jason", "telegram", limit=5, hours=24)
            if xc:
                parts.append(xc)
            # Long-term conversation history (summaries from past 30 days)
            ltc = conversation_store.get_long_term_context("jason", days=30)
            if ltc:
                parts.append(ltc)
        except Exception as e:
            logger.warning(f"Cross-channel context failed: {e}")

    # Inject elite team context if triggered
    if user_message:
        try:
            from gigi.elite_teams import detect_team, get_team_context
            team_key = detect_team(user_message)
            if team_key:
                parts.append(get_team_context(team_key))
                logger.info(f"Elite team activated: {team_key}")
        except Exception as e:
            logger.warning(f"Elite team detection failed: {e}")

    return "\n".join(parts)


# Legacy reference
SYSTEM_PROMPT = _build_telegram_system_prompt()

class GigiTelegramBot:
    def __init__(self):
        # Initialize the right LLM client based on GIGI_LLM_PROVIDER
        self.llm = None
        if LLM_PROVIDER == "gemini" and GEMINI_AVAILABLE and GEMINI_API_KEY:
            self.llm = genai.Client(api_key=GEMINI_API_KEY)
        elif LLM_PROVIDER == "openai" and OPENAI_AVAILABLE and OPENAI_API_KEY:
            self.llm = openai.OpenAI(api_key=OPENAI_API_KEY)
        elif LLM_PROVIDER == "anthropic" and ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
            self.llm = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        else:
            # Fallback: try any available provider
            if ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
                self.llm = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                logger.warning(f"Provider '{LLM_PROVIDER}' not available, falling back to anthropic")
            elif GEMINI_AVAILABLE and GEMINI_API_KEY:
                self.llm = genai.Client(api_key=GEMINI_API_KEY)
                logger.warning(f"Provider '{LLM_PROVIDER}' not available, falling back to gemini")

        self.wellsky = WellSkyService() if WellSkyService else None
        self.google = GoogleService() if GoogleService else None
        from gigi.conversation_store import ConversationStore
        self.conversation_store = ConversationStore()
        self._message_lock = asyncio.Lock()  # Prevent concurrent message handling
        logger.info("Conversation store initialized (PostgreSQL)")

        # Log service status on startup
        logger.info(f"   LLM Provider: {LLM_PROVIDER} | Model: {LLM_MODEL}")
        logger.info(f"   LLM Client: {'✓ Ready' if self.llm else '✗ NOT CONFIGURED'}")
        logger.info(f"   WellSky: {'✓ Ready' if self.wellsky else '✗ Not available'}")
        logger.info(f"   Google: {'✓ Ready' if self.google else '✗ Not available'}")

    async def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool and return the result as a string"""
        try:
            if tool_name == "search_concerts":
                if not cos_tools:
                    return json.dumps({"error": "Chief of Staff tools not available."})
                query = tool_input.get("query", "")
                result = await cos_tools.search_concerts(query=query)
                return json.dumps(result)

            elif tool_name == "buy_tickets_request":
                if not cos_tools:
                    return json.dumps({"error": "Chief of Staff tools not available."})
                artist = tool_input.get("artist")
                venue = tool_input.get("venue")
                quantity = tool_input.get("quantity", 2)
                result = await cos_tools.buy_tickets_request(artist=artist, venue=venue, quantity=quantity)
                return json.dumps(result)

            elif tool_name == "book_table_request":
                if not cos_tools:
                    return json.dumps({"error": "Chief of Staff tools not available."})
                restaurant = tool_input.get("restaurant")
                party_size = tool_input.get("party_size")
                date_val = tool_input.get("date")
                time_val = tool_input.get("time")
                result = await cos_tools.book_table_request(restaurant=restaurant, party_size=party_size, date=date_val, time=time_val)
                return json.dumps(result)

            elif tool_name == "get_client_current_status":
                client_name = tool_input.get("client_name", "")
                if not client_name:
                    return json.dumps({"error": "No client name provided"})

                def _sync_client_status(name_val):
                    from datetime import datetime

                    import psycopg2
                    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
                    conn = None
                    try:
                        conn = psycopg2.connect(db_url)
                        cur = conn.cursor()
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
                        cur.execute("""
                            SELECT a.scheduled_start, a.scheduled_end,
                                   p.full_name as caregiver_name, p.phone as caregiver_phone, a.status
                            FROM cached_appointments a
                            LEFT JOIN cached_practitioners p ON a.practitioner_id = p.id
                            WHERE a.patient_id = %s
                            AND a.scheduled_start >= CURRENT_DATE
                            AND a.scheduled_start < CURRENT_DATE + INTERVAL '1 day'
                            ORDER BY a.scheduled_start ASC
                        """, (client_id,))
                        shifts = cur.fetchall()
                        if not shifts:
                            return {"client": client_full_name, "status": "no_shifts",
                                    "message": f"No shifts scheduled for {client_full_name} today."}
                        now = datetime.now()
                        current_shift = next_shift = last_shift = None
                        for s in shifts:
                            start, end, cg_name, cg_phone, status = s
                            if start <= now <= end:
                                current_shift = s; break
                            elif start > now:
                                if not next_shift: next_shift = s
                            elif end < now:
                                last_shift = s
                        if current_shift:
                            start, end, cg_name, _, _ = current_shift
                            return {"client": client_full_name, "status": "active",
                                    "message": f"YES. {cg_name} is with {client_full_name} right now.\nShift: {start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}\nLocation: {addr}, {city}"}
                        elif next_shift:
                            start, end, cg_name, _, _ = next_shift
                            return {"client": client_full_name, "status": "upcoming",
                                    "message": f"No one is there right now. Next shift is {cg_name} at {start.strftime('%I:%M %p')}."}
                        else:
                            start, end, cg_name, _, _ = last_shift if last_shift else (None, None, "None", None, None)
                            msg = f"No one is there right now. {cg_name} finished at {end.strftime('%I:%M %p')}." if last_shift else f"No active shifts right now for {client_full_name}."
                            return {"client": client_full_name, "status": "completed", "message": msg}
                    except Exception as e:
                        logger.error(f"Status check failed: {e}")
                        return {"error": str(e)}
                    finally:
                        if conn: conn.close()

                result = await asyncio.to_thread(_sync_client_status, client_name)
                return json.dumps(result)

            elif tool_name == "get_calendar_events":
                if not self.google:
                    return json.dumps({"error": "Google service not configured. Missing GOOGLE_WORK_* environment variables."})
                days = tool_input.get("days", 1)
                events = self.google.get_calendar_events(days=min(days, 7))
                if not events:
                    return json.dumps({"message": "No upcoming events found", "events": []})
                return json.dumps({"events": events})

            elif tool_name == "search_emails":
                if not self.google:
                    return json.dumps({"error": "Google service not configured. Missing GOOGLE_WORK_* environment variables."})
                query = tool_input.get("query", "is:unread")
                max_results = tool_input.get("max_results", 5)
                emails = self.google.search_emails(query=query, max_results=max_results)
                if not emails:
                    return json.dumps({"message": f"No emails found for query: {query}", "emails": []})
                return json.dumps({"emails": emails})

            elif tool_name == "get_weather":
                location = tool_input.get("location", "")
                if not location:
                    return json.dumps({"error": "No location provided"})

                # Primary: wttr.in — free, no API key, structured JSON
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(f"https://wttr.in/{location}?format=j1")
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

                # Fallback: DDG search (sync — run in thread)
                try:
                    from ddgs import DDGS
                    def _ddg_weather():
                        return list(DDGS().text(f"current weather {location}", max_results=1))
                    results = await asyncio.to_thread(_ddg_weather)
                    if results:
                        return json.dumps({"location": location, "weather": results[0].get("body")})
                except Exception as e:
                    logger.warning(f"DDG weather fallback failed: {e}")

                return json.dumps({"error": "Weather service temporarily unavailable"})

            elif tool_name == "get_wellsky_clients":
                search_name = tool_input.get("search_name", "")
                active_only = tool_input.get("active_only", True)

                def _sync_get_clients():
                    import psycopg2
                    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
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
                            if active_only: sql += " AND is_active = true"
                            sql += " ORDER BY full_name LIMIT 20"
                            cur.execute(sql, params)
                        else:
                            sql = "SELECT id, first_name, last_name, full_name, phone, home_phone, email FROM cached_patients"
                            if active_only: sql += " WHERE is_active = true"
                            sql += " ORDER BY full_name LIMIT 100"
                            cur.execute(sql)
                        rows = cur.fetchall()
                        client_list = [{"id": str(r[0]), "first_name": r[1], "last_name": r[2],
                                        "name": r[3], "phone": r[4] or r[5] or "", "email": r[6] or ""} for r in rows]
                        return {"count": len(client_list), "clients": client_list, "search": search_name or "all"}
                    except Exception as e:
                        logger.error(f"Client cache lookup failed: {e}")
                        return {"error": f"Client lookup failed: {str(e)}"}
                    finally:
                        if conn: conn.close()

                return json.dumps(await asyncio.to_thread(_sync_get_clients))

            elif tool_name == "get_wellsky_caregivers":
                search_name = tool_input.get("search_name", "")
                active_only = tool_input.get("active_only", True)

                def _sync_get_caregivers():
                    import psycopg2
                    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
                    conn = None
                    try:
                        conn = psycopg2.connect(db_url)
                        cur = conn.cursor()
                        if search_name:
                            search_lower = f"%{search_name.lower()}%"
                            sql = """SELECT id, first_name, last_name, full_name, phone, home_phone, email,
                                            preferred_language
                                     FROM cached_practitioners WHERE (lower(full_name) LIKE %s
                                     OR lower(first_name) LIKE %s OR lower(last_name) LIKE %s)"""
                            params = [search_lower, search_lower, search_lower]
                            if active_only: sql += " AND is_active = true"
                            sql += " ORDER BY full_name LIMIT 20"
                            cur.execute(sql, params)
                        else:
                            sql = """SELECT id, first_name, last_name, full_name, phone, home_phone, email,
                                            preferred_language
                                     FROM cached_practitioners"""
                            if active_only: sql += " WHERE is_active = true"
                            sql += " ORDER BY full_name LIMIT 100"
                            cur.execute(sql)
                        rows = cur.fetchall()
                        cg_list = [{"id": str(r[0]), "first_name": r[1], "last_name": r[2],
                                    "name": r[3], "phone": r[4] or r[5] or "", "email": r[6] or "",
                                    "preferred_language": r[7] or "English"} for r in rows]
                        return {"count": len(cg_list), "caregivers": cg_list, "search": search_name or "all"}
                    except Exception as e:
                        logger.error(f"Caregiver cache lookup failed: {e}")
                        return {"error": f"Caregiver lookup failed: {str(e)}"}
                    finally:
                        if conn: conn.close()

                return json.dumps(await asyncio.to_thread(_sync_get_caregivers))

            elif tool_name == "get_wellsky_shifts":
                from datetime import timedelta
                days = min(tool_input.get("days", 7), 30)
                past_days = min(tool_input.get("past_days", 0), 90)
                open_only = tool_input.get("open_only", False)
                client_id = tool_input.get("client_id")
                caregiver_id = tool_input.get("caregiver_id")

                def _sync_get_shifts():
                    import psycopg2
                    if past_days > 0:
                        date_from = date.today() - timedelta(days=past_days)
                        date_to = date.today()
                    else:
                        date_from = date.today()
                        date_to = date.today() + timedelta(days=days)
                    db_url = os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist")
                    conn = None
                    try:
                        conn = psycopg2.connect(db_url)
                        cur = conn.cursor()
                        conditions = ["a.scheduled_start >= %s", "a.scheduled_start < %s"]
                        params = [date_from, date_to]
                        if client_id:
                            conditions.append("a.patient_id = %s"); params.append(client_id)
                        if caregiver_id:
                            conditions.append("a.practitioner_id = %s"); params.append(caregiver_id)
                        if open_only:
                            conditions.append("(a.practitioner_id IS NULL OR a.status IN ('open', 'pending', 'proposed'))")
                        where = " AND ".join(conditions)
                        cur.execute(f"""
                            SELECT a.id, a.scheduled_start, a.scheduled_end,
                                   a.actual_start, a.actual_end, a.status,
                                   a.patient_id, a.practitioner_id, a.service_type,
                                   p.full_name as client_name, pr.full_name as caregiver_name
                            FROM cached_appointments a
                            LEFT JOIN cached_patients p ON a.patient_id = p.id
                            LEFT JOIN cached_practitioners pr ON a.practitioner_id = pr.id
                            WHERE {where} ORDER BY a.scheduled_start LIMIT 50
                        """, params)
                        shift_list = []
                        total_hours = 0
                        for row in cur.fetchall():
                            scheduled_hours = None
                            if row[1] and row[2]:
                                scheduled_hours = round((row[2] - row[1]).total_seconds() / 3600, 1)
                                total_hours += scheduled_hours
                            actual_hours = None
                            if row[3] and row[4]:
                                actual_hours = round((row[4] - row[3]).total_seconds() / 3600, 1)
                            shift_list.append({
                                "id": row[0], "scheduled_start": row[1].isoformat() if row[1] else None,
                                "scheduled_end": row[2].isoformat() if row[2] else None,
                                "actual_start": row[3].isoformat() if row[3] else None,
                                "actual_end": row[4].isoformat() if row[4] else None,
                                "status": row[5], "client_id": row[6], "caregiver_id": row[7],
                                "service_type": row[8], "client_name": row[9] or "Unknown",
                                "caregiver_name": row[10] or "Unassigned",
                                "scheduled_hours": scheduled_hours, "actual_hours": actual_hours,
                            })
                        return {"count": len(shift_list), "total_scheduled_hours": round(total_hours, 1),
                                "date_range": f"{date_from.isoformat()} to {date_to.isoformat()}", "shifts": shift_list}
                    except Exception as e:
                        logger.error(f"Error querying cached shifts: {e}")
                        return {"error": f"Database error: {str(e)}"}
                    finally:
                        if conn: conn.close()

                return json.dumps(await asyncio.to_thread(_sync_get_shifts))

            elif tool_name == "web_search":
                query = tool_input.get("query", "")
                if not query:
                    return json.dumps({"error": "No search query provided"})
                try:
                    import httpx
                    # Use Brave Search API
                    brave_api_key = os.getenv("BRAVE_API_KEY")
                    if brave_api_key:
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(
                                "https://api.search.brave.com/res/v1/web/search",
                                headers={"X-Subscription-Token": brave_api_key},
                                params={"q": query, "count": 5}
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                results = []
                                for r in data.get("web", {}).get("results", [])[:5]:
                                    results.append({
                                        "title": r.get("title"),
                                        "description": r.get("description"),
                                        "url": r.get("url")
                                    })
                                return json.dumps({"query": query, "results": results})
                    # Fallback: DuckDuckGo full search (sync — run in thread)
                    try:
                        from ddgs import DDGS
                        def _ddg_search():
                            return list(DDGS().text(query, max_results=5))
                        results = await asyncio.to_thread(_ddg_search)
                        if results:
                            formatted = [{"title": r.get("title", ""), "description": r.get("body", ""), "url": r.get("href", "")} for r in results]
                            return json.dumps({"query": query, "results": formatted})
                    except Exception as ddg_err:
                        logger.warning(f"DDG search fallback failed: {ddg_err}")
                    return json.dumps({"query": query, "message": "No results found. Try a more specific query."})
                except Exception as e:
                    logger.error(f"Web search error: {e}")
                    return json.dumps({"error": f"Search failed: {str(e)}"})

            elif tool_name == "get_stock_price":
                symbol = tool_input.get("symbol", "").upper()
                if not symbol:
                    return json.dumps({"error": "No stock symbol provided"})
                try:
                    import httpx
                    # Yahoo Finance API
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
                                prev = meta.get("chartPreviousClose") or meta.get("previousClose", 0)
                                change = price - prev if prev else 0
                                pct = (change / prev * 100) if prev else 0
                                return json.dumps({
                                    "symbol": symbol,
                                    "price": f"${price:.2f}",
                                    "previous_close": f"${prev:.2f}",
                                    "change": f"${change:+.2f}",
                                    "change_percent": f"{pct:+.2f}%",
                                    "currency": meta.get("currency", "USD")
                                })

                    # Fallback: DDG search (sync — run in thread)
                    from ddgs import DDGS
                    def _ddg_stock():
                        return list(DDGS().text(f"{symbol} stock price today", max_results=1))
                    results = await asyncio.to_thread(_ddg_stock)
                    if results:
                        return json.dumps({"symbol": symbol, "info": results[0].get("body", "")})

                    return json.dumps({"error": f"Could not find stock price for {symbol}"})
                except Exception as e:
                    logger.error(f"Stock price error: {e}")
                    return json.dumps({"error": f"Stock lookup failed: {str(e)}"})

            elif tool_name == "get_crypto_price":
                symbol = tool_input.get("symbol", "").upper()
                if not symbol:
                    return json.dumps({"error": "No crypto symbol provided"})
                # Map common names to CoinGecko IDs
                crypto_map = {
                    "BTC": "bitcoin", "BITCOIN": "bitcoin",
                    "ETH": "ethereum", "ETHEREUM": "ethereum",
                    "DOGE": "dogecoin", "DOGECOIN": "dogecoin",
                    "SOL": "solana", "SOLANA": "solana",
                    "XRP": "ripple", "RIPPLE": "ripple",
                    "ADA": "cardano", "CARDANO": "cardano",
                    "MATIC": "matic-network", "POLYGON": "matic-network",
                    "DOT": "polkadot", "POLKADOT": "polkadot",
                    "AVAX": "avalanche-2", "AVALANCHE": "avalanche-2",
                    "LINK": "chainlink", "CHAINLINK": "chainlink"
                }
                coin_id = crypto_map.get(symbol, symbol.lower())
                try:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(
                            f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true"
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            if coin_id in data:
                                info = data[coin_id]
                                return json.dumps({
                                    "symbol": symbol,
                                    "name": coin_id.replace("-", " ").title(),
                                    "price": f"${info.get('usd', 0):,.2f}",
                                    "change_24h": f"{info.get('usd_24h_change', 0):.2f}%",
                                    "market_cap": f"${info.get('usd_market_cap', 0):,.0f}"
                                })
                    return json.dumps({"error": f"Could not find price for {symbol}. Try BTC, ETH, DOGE, SOL, etc."})
                except Exception as e:
                    logger.error(f"Crypto price error: {e}")
                    return json.dumps({"error": f"Crypto lookup failed: {str(e)}"})

            # NOTE: Duplicate web_search handler removed (dead code - first handler at line ~751 always matches)

            elif tool_name == "create_claude_task":
                title = tool_input.get("title", "")
                description = tool_input.get("description", "")
                priority = tool_input.get("priority", "normal")
                working_dir = tool_input.get("working_directory", "/Users/shulmeister/mac-mini-apps/careassist-unified")

                if not title or not description:
                    return json.dumps({"error": "Missing title or description"})

                import psycopg2
                def _sync_create_task():
                    conn = None
                    try:
                        conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist"))
                        cur = conn.cursor()
                        cur.execute("""
                            INSERT INTO claude_code_tasks (title, description, priority, status, requested_by, working_directory, created_at)
                            VALUES (%s, %s, %s, 'pending', %s, %s, NOW())
                            RETURNING id
                        """, (title, description, priority, "telegram", working_dir))
                        task_id = cur.fetchone()[0]
                        conn.commit()
                        return json.dumps({"success": True, "task_id": task_id, "message": f"Task #{task_id} created: {title}. Claude Code will pick it up shortly."})
                    except Exception as e:
                        return json.dumps({"error": f"Failed to create task: {str(e)}"})
                    finally:
                        if conn:
                            conn.close()
                return await asyncio.to_thread(_sync_create_task)

            elif tool_name == "check_claude_task":
                task_id = tool_input.get("task_id")

                import psycopg2
                def _sync_check_task():
                    conn = None
                    try:
                        conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://careassist@localhost:5432/careassist"))
                        cur = conn.cursor()
                        if task_id:
                            cur.execute("SELECT id, title, status, result, error, created_at, completed_at FROM claude_code_tasks WHERE id = %s", (int(task_id),))
                        else:
                            cur.execute("SELECT id, title, status, result, error, created_at, completed_at FROM claude_code_tasks ORDER BY id DESC LIMIT 1")
                        row = cur.fetchone()

                        if not row:
                            return json.dumps({"message": "No tasks found"})

                        result_preview = row[3][:500] if row[3] else None
                        return json.dumps({
                            "task_id": row[0], "title": row[1], "status": row[2],
                            "result_preview": result_preview, "error": row[4],
                            "created_at": row[5].isoformat() if row[5] else None,
                            "completed_at": row[6].isoformat() if row[6] else None
                        })
                    except Exception as e:
                        return json.dumps({"error": f"Failed to check task: {str(e)}"})
                    finally:
                        if conn:
                            conn.close()
                return await asyncio.to_thread(_sync_check_task)

            elif tool_name == "save_memory":
                if not MEMORY_AVAILABLE or not _memory_system:
                    return json.dumps({"error": "Memory system not available"})
                content = tool_input.get("content", "")
                category = tool_input.get("category", "general")
                importance = tool_input.get("importance", "medium")
                impact_map = {"high": ImpactLevel.HIGH, "medium": ImpactLevel.MEDIUM, "low": ImpactLevel.LOW}
                memory_id = _memory_system.create_memory(
                    content=content,
                    memory_type=MemoryType.EXPLICIT_INSTRUCTION,
                    source=MemorySource.EXPLICIT,
                    confidence=1.0,
                    category=category,
                    impact_level=impact_map.get(importance, ImpactLevel.MEDIUM)
                )
                return json.dumps({"saved": True, "memory_id": memory_id, "content": content})

            elif tool_name == "recall_memories":
                if not MEMORY_AVAILABLE or not _memory_system:
                    return json.dumps({"memories": [], "message": "Memory system not available"})
                category = tool_input.get("category")
                search_text = tool_input.get("search_text")
                memories = _memory_system.query_memories(category=category, min_confidence=0.3, limit=10)
                if search_text:
                    search_lower = search_text.lower()
                    memories = [m for m in memories if search_lower in m.content.lower()]
                results = [{"id": m.id, "content": m.content, "category": m.category,
                           "confidence": float(m.confidence), "type": m.type.value} for m in memories]
                return json.dumps({"memories": results, "count": len(results)})

            elif tool_name == "forget_memory":
                if not MEMORY_AVAILABLE or not _memory_system:
                    return json.dumps({"error": "Memory system not available"})
                memory_id = tool_input.get("memory_id", "")
                memory = _memory_system.get_memory(memory_id)
                if not memory:
                    return json.dumps({"error": f"Memory {memory_id} not found"})
                with _memory_system._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE gigi_memories SET status = 'archived' WHERE id = %s", (memory_id,))
                        _memory_system._log_event(cur, memory_id, "archived", memory.confidence, memory.confidence, "User requested forget")
                    conn.commit()
                return json.dumps({"archived": True, "memory_id": memory_id, "content": memory.content})

            elif tool_name == "search_memory_logs":
                from gigi.memory_logger import MemoryLogger
                ml = MemoryLogger()
                query = tool_input.get("query", "")
                days_back = tool_input.get("days_back", 30)
                results = await asyncio.to_thread(ml.search_logs, query, days_back=days_back)
                return json.dumps({"query": query, "results": results[:10], "total": len(results)})

            elif tool_name == "browse_webpage":
                # Redirect to browse_with_claude (better than old Playwright)
                from gigi.claude_code_tools import browse_with_claude
                url = tool_input.get("url", "")
                result = await browse_with_claude(task=f"Navigate to {url} and extract the main text content of the page.", url=url)
                return json.dumps(result)

            elif tool_name == "take_screenshot":
                # Redirect to browse_with_claude (better than old Playwright)
                from gigi.claude_code_tools import browse_with_claude
                url = tool_input.get("url", "")
                result = await browse_with_claude(task=f"Navigate to {url} and describe what the page looks like and its content.", url=url)
                return json.dumps(result)

            elif tool_name == "get_morning_briefing":
                from gigi.morning_briefing_service import MorningBriefingService
                svc = MorningBriefingService()
                briefing = await asyncio.to_thread(svc.generate_briefing)
                # Wrap with explicit instruction to relay as-is — prevents LLM hallucination
                return (
                    "[COMPLETE BRIEFING — RELAY EXACTLY AS-IS. DO NOT ADD SETUP ISSUES, "
                    "TROUBLESHOOTING, CLI TOOLS, OR ANY COMMENTARY. JUST SEND THIS TEXT.]\n\n"
                    + briefing
                )

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

            # === MARKETING TOOLS ===
            elif tool_name == "get_marketing_dashboard":
                from gigi.marketing_tools import get_marketing_dashboard
                result = await asyncio.to_thread(get_marketing_dashboard, tool_input.get("date_range", "7d"))
                return json.dumps(result)

            elif tool_name == "get_google_ads_report":
                from gigi.marketing_tools import get_google_ads_report
                result = await asyncio.to_thread(get_google_ads_report, tool_input.get("date_range", "30d"))
                return json.dumps(result)

            elif tool_name == "get_website_analytics":
                from gigi.marketing_tools import get_website_analytics
                result = await asyncio.to_thread(get_website_analytics, tool_input.get("date_range", "7d"))
                return json.dumps(result)

            elif tool_name == "get_social_media_report":
                from gigi.marketing_tools import get_social_media_report
                result = await asyncio.to_thread(get_social_media_report, tool_input.get("date_range", "7d"), tool_input.get("platform", ""))
                return json.dumps(result)

            elif tool_name == "get_gbp_report":
                from gigi.marketing_tools import get_gbp_report
                result = await asyncio.to_thread(get_gbp_report, tool_input.get("date_range", "30d"))
                return json.dumps(result)

            elif tool_name == "get_email_campaign_report":
                from gigi.marketing_tools import get_email_campaign_report
                result = await asyncio.to_thread(get_email_campaign_report, tool_input.get("date_range", "30d"))
                return json.dumps(result)

            elif tool_name == "generate_social_content":
                from gigi.marketing_tools import generate_social_content
                result = await asyncio.to_thread(generate_social_content, tool_input.get("prompt", ""), tool_input.get("media_type", "single_image"))
                return json.dumps(result)

            # === FINANCE TOOLS ===
            elif tool_name == "get_pnl_report":
                from gigi.finance_tools import get_pnl_report
                result = await asyncio.to_thread(get_pnl_report, tool_input.get("period", "ThisMonth"))
                return json.dumps(result)

            elif tool_name == "get_balance_sheet":
                from gigi.finance_tools import get_balance_sheet
                result = await asyncio.to_thread(get_balance_sheet, tool_input.get("as_of_date", ""))
                return json.dumps(result)

            elif tool_name == "get_invoice_list":
                from gigi.finance_tools import get_invoice_list
                result = await asyncio.to_thread(get_invoice_list, tool_input.get("status", "Open"))
                return json.dumps(result)

            elif tool_name == "get_cash_position":
                from gigi.finance_tools import get_cash_position
                result = await asyncio.to_thread(get_cash_position)
                return json.dumps(result)

            elif tool_name == "get_financial_dashboard":
                from gigi.finance_tools import get_financial_dashboard
                result = await asyncio.to_thread(get_financial_dashboard)
                return json.dumps(result)

            elif tool_name == "get_subscription_audit":
                from gigi.finance_tools import get_subscription_audit
                months = tool_input.get("months_back", 6)
                result = await asyncio.to_thread(get_subscription_audit, months)
                return json.dumps(result)

            # === CLAUDE CODE TOOLS ===
            elif tool_name == "run_claude_code":
                from gigi.claude_code_tools import run_claude_code
                result = await run_claude_code(
                    prompt=tool_input.get("prompt", ""),
                    directory=tool_input.get("directory"),
                    model=tool_input.get("model"),
                )
                return json.dumps(result)

            elif tool_name == "browse_with_claude":
                from gigi.claude_code_tools import browse_with_claude
                result = await browse_with_claude(
                    task=tool_input.get("task", ""),
                    url=tool_input.get("url"),
                )
                return json.dumps(result)

            # === FAX TOOLS ===
            elif tool_name == "send_fax":
                from services.fax_service import send_fax as _send_fax
                result = await _send_fax(
                    to=tool_input.get("to", ""),
                    media_url=tool_input.get("media_url", ""),
                )
                return json.dumps(result)

            elif tool_name == "list_faxes":
                from services.fax_service import list_faxes as _list_faxes
                result = _list_faxes(
                    direction=tool_input.get("direction"),
                    limit=tool_input.get("limit", 10),
                )
                return json.dumps(result)

            elif tool_name == "read_fax":
                from services.fax_service import read_fax as _read_fax
                result = await _read_fax(fax_id=int(tool_input.get("fax_id", 0)))
                return json.dumps(result)

            elif tool_name == "file_fax_referral":
                from services.fax_service import file_fax_referral as _file_fax
                result = await _file_fax(fax_id=int(tool_input.get("fax_id", 0)))
                return json.dumps(result)

            # === TRAVEL TOOLS ===
            elif tool_name == "search_flights":
                from gigi.travel_tools import search_flights
                result = await search_flights(
                    origin=tool_input.get("origin", ""),
                    destination=tool_input.get("destination", ""),
                    departure_date=tool_input.get("departure_date", ""),
                    return_date=tool_input.get("return_date"),
                    adults=tool_input.get("adults", 1),
                    max_stops=tool_input.get("max_stops", 1),
                )
                return json.dumps(result)

            elif tool_name == "search_hotels":
                from gigi.travel_tools import search_hotels
                result = await search_hotels(
                    city=tool_input.get("city", ""),
                    checkin=tool_input.get("checkin", ""),
                    checkout=tool_input.get("checkout", ""),
                    guests=tool_input.get("guests", 2),
                    max_price=tool_input.get("max_price"),
                )
                return json.dumps(result)

            elif tool_name == "search_car_rentals":
                from gigi.travel_tools import search_car_rentals
                result = await search_car_rentals(
                    pickup_location=tool_input.get("pickup_location", ""),
                    pickup_date=tool_input.get("pickup_date", ""),
                    dropoff_date=tool_input.get("dropoff_date", ""),
                    dropoff_location=tool_input.get("dropoff_location"),
                    car_class=tool_input.get("car_class"),
                )
                return json.dumps(result)

            elif tool_name == "get_polybot_status":
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        polybot_resp, mlbot_resp = await asyncio.gather(
                            client.get("http://localhost:3002/api/polybot/status"),
                            client.get("http://localhost:3002/api/ml-bot/status"),
                            return_exceptions=True,
                        )

                        report = []

                        # --- POLYBOT (Polymarket) ---
                        if isinstance(polybot_resp, Exception):
                            report.append("POLYBOT: UNAVAILABLE")
                        else:
                            pb = polybot_resp.json()
                            portfolio = pb.get("portfolio", {})
                            perf = pb.get("performance", {})
                            risk = pb.get("risk", {})
                            positions = pb.get("positions", {})
                            poly_positions = positions.get("polymarket", [])

                            report.append(f"POLYBOT (Polymarket) — {'Paper Mode' if pb.get('paper_mode') else 'LIVE'}")
                            report.append(f"Status: {'RUNNING' if pb.get('is_running') else 'STOPPED'} | Cycles: {pb.get('cycles_completed', 0)}")
                            report.append(f"Portfolio: ${portfolio.get('total_value', 0):,.2f} | P&L: ${portfolio.get('pnl', 0):,.2f} ({portfolio.get('pnl_pct', 0):.2f}%)")
                            report.append(f"Trades: {perf.get('total_trades', 0)} total | {perf.get('winning_trades', 0)}W/{perf.get('losing_trades', 0)}L ({perf.get('win_rate', 0):.1f}% win rate)")
                            report.append(f"Drawdown: {risk.get('drawdown_pct', 0):.1f}% | Kill switch: {risk.get('kill_switch', {}).get('state', '?')}")
                            report.append("")

                            # Active strategies
                            strategies = pb.get("strategies", [])
                            enabled_names = [s["name"] for s in strategies if s.get("enabled")]
                            report.append(f"Strategies ({len(enabled_names)} active): {', '.join(enabled_names)}")
                            report.append("")

                            # Strategy performance breakdown
                            strat_perf = pb.get("strategy_performance", {})
                            if strat_perf:
                                report.append("Strategy Performance:")
                                for name, sp in sorted(strat_perf.items(), key=lambda x: x[1].get("realized_pnl", 0), reverse=True):
                                    trades = sp.get("total_trades", 0)
                                    pnl = sp.get("realized_pnl", 0)
                                    wr = sp.get("win_rate", 0)
                                    report.append(f"  {name}: {trades} trades, ${pnl:+,.2f} P&L ({wr:.0f}% WR)")
                                report.append("")

                            # Open positions
                            report.append(f"Open Positions ({len(poly_positions)}):")
                            for p in poly_positions[:8]:
                                sym = p.get("symbol", "?")[:50]
                                amt = p.get("amount", 0)
                                entry = p.get("entry_price", 0)
                                pnl = p.get("unrealized_pnl", 0)
                                report.append(f"  {sym}: {amt:.1f} shares @ {entry:.4f} (P&L: ${pnl:+.2f})")
                            if len(poly_positions) > 8:
                                report.append(f"  ... and {len(poly_positions) - 8} more")

                        report.append("")

                        # --- ML BOT (Crypto) ---
                        if isinstance(mlbot_resp, Exception):
                            report.append("ML BOT (Crypto): UNAVAILABLE")
                        else:
                            ml = mlbot_resp.json()
                            ml_port = ml.get("portfolio", {})
                            ml_stats = ml.get("stats", {})
                            report.append(f"ML BOT (Crypto) — {'Paper Mode' if ml.get('paper_trading') else 'LIVE'}")
                            report.append(f"Status: {ml.get('status', '?').upper()}")
                            report.append(f"Portfolio: ${ml_port.get('current_value', 0):,.2f} | P&L: ${ml_port.get('pnl', 0):,.2f} ({ml_port.get('pnl_pct', 0):.2f}%)")
                            report.append(f"Trades: {ml_stats.get('trades_executed', 0)} | {ml_stats.get('winning_trades', 0)}W/{ml_stats.get('losing_trades', 0)}L ({ml_stats.get('win_rate', 0):.1f}% WR)")
                            ml_positions = ml.get("positions", [])
                            if ml_positions:
                                report.append(f"Open positions: {len(ml_positions)}")
                                for mp in ml_positions[:5]:
                                    report.append(f"  {mp.get('symbol', '?')}: {mp.get('amount', 0):.4f} @ ${mp.get('entry_price', 0):,.2f}")

                        return "\n".join(report)
                except Exception as e:
                    logger.error(f"Polybot status failed: {e}")
                    return json.dumps({"error": f"Trading bots unavailable: {e}"})

            elif tool_name == "get_weather_arb_status":
                try:
                    import httpx
                    result = {"polymarket": {"status": "offline"}, "kalshi": {"status": "offline"}}
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        # --- Polymarket Weather Bot (port 3010) ---
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
                                poly["clob_ready"] = bool(st.get("clob_ready"))
                                poly["snipe_window_active"] = bool(st.get("snipe_window"))
                                poly["scans"] = sniper.get("scan_count", 0)
                                poly["orders_placed"] = sniper.get("orders_placed", 0)
                            if not isinstance(pnl_resp, Exception) and pnl_resp.status_code == 200:
                                data = pnl_resp.json()
                                poly["portfolio_value"] = data.get("portfolio_value", 0)
                                poly["cash"] = data.get("cash", 0)
                                poly["deployed"] = data.get("deployed", 0)
                                poly["unrealized_pnl"] = data.get("unrealized_pnl", 0)
                                positions = data.get("positions", [])
                                poly["num_positions"] = len(positions)
                                poly["positions"] = [
                                    {"title": p.get("title", "?")[:60], "shares": p.get("shares", 0),
                                     "entry_pct": round(p.get("entry", 0) * 100), "current_pct": round((p.get("current") or 0) * 100),
                                     "pnl": round(p.get("pnl", 0), 2), "pnl_pct": round(p.get("pnl_pct", 0), 1)}
                                    for p in positions[:10]
                                ]
                            result["polymarket"] = poly
                        except Exception as e:
                            logger.warning(f"Polymarket status fetch: {e}")

                        # --- Kalshi Weather Bot (port 3011) ---
                        try:
                            kalshi_resp = await client.get("http://127.0.0.1:3011/pnl")
                            if kalshi_resp.status_code == 200:
                                data = kalshi_resp.json()
                                kalshi = {
                                    "status": "online",
                                    "portfolio_value": data.get("portfolio_value", 0),
                                    "cash": data.get("cash", 0),
                                    "deployed": data.get("deployed", 0),
                                    "unrealized_pnl": data.get("unrealized_pnl", 0),
                                }
                                positions = data.get("positions", [])
                                kalshi["num_positions"] = len(positions)
                                kalshi["positions"] = [
                                    {"ticker": p.get("ticker", "?"), "side": p.get("side", "?"),
                                     "count": p.get("count", 0), "value": round(p.get("value", 0), 2),
                                     "pnl": round(p.get("pnl", 0), 2)}
                                    for p in positions[:10]
                                ]
                                result["kalshi"] = kalshi
                        except Exception as e:
                            logger.warning(f"Kalshi status fetch: {e}")

                    return json.dumps(result)
                except Exception as e:
                    logger.error(f"Weather arb status failed: {e}")
                    return json.dumps({"error": f"Weather bots unavailable: {str(e)}"})

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

            elif tool_name == "watch_tickets":
                if not cos_tools:
                    return json.dumps({"error": "Chief of Staff tools not available."})
                artist = tool_input.get("artist", "")
                venue = tool_input.get("venue")
                city = tool_input.get("city", "Denver")
                result = await cos_tools.watch_tickets(artist=artist, venue=venue, city=city)
                return json.dumps(result)

            elif tool_name == "list_ticket_watches":
                if not cos_tools:
                    return json.dumps({"error": "Chief of Staff tools not available."})
                result = await cos_tools.list_ticket_watches()
                return json.dumps(result)

            elif tool_name == "remove_ticket_watch":
                if not cos_tools:
                    return json.dumps({"error": "Chief of Staff tools not available."})
                watch_id = tool_input.get("watch_id")
                result = await cos_tools.remove_ticket_watch(watch_id=watch_id)
                return json.dumps(result)

            elif tool_name == "clock_in_shift":
                appointment_id = tool_input.get("appointment_id", "")
                caregiver_name = tool_input.get("caregiver_name", "")
                notes = tool_input.get("notes", "Clocked in via Gigi")
                if not appointment_id:
                    return json.dumps({"error": "Missing appointment_id. Use get_wellsky_shifts first."})
                def _clock_in():
                    if WellSkyService is None:
                        return {"error": "WellSky service not available"}
                    ws = WellSkyService()
                    success, message = ws.clock_in_shift(appointment_id, notes=notes)
                    return {"success": success, "message": message, "appointment_id": appointment_id, "caregiver_name": caregiver_name}
                return json.dumps(await asyncio.to_thread(_clock_in))

            elif tool_name == "clock_out_shift":
                appointment_id = tool_input.get("appointment_id", "")
                caregiver_name = tool_input.get("caregiver_name", "")
                notes = tool_input.get("notes", "Clocked out via Gigi")
                if not appointment_id:
                    return json.dumps({"error": "Missing appointment_id. Use get_wellsky_shifts first."})
                def _clock_out():
                    if WellSkyService is None:
                        return {"error": "WellSky service not available"}
                    ws = WellSkyService()
                    success, message = ws.clock_out_shift(appointment_id, notes=notes)
                    return {"success": success, "message": message, "appointment_id": appointment_id, "caregiver_name": caregiver_name}
                return json.dumps(await asyncio.to_thread(_clock_out))

            elif tool_name == "find_replacement_caregiver":
                shift_id = tool_input.get("shift_id", "")
                original_caregiver_id = tool_input.get("original_caregiver_id", "")
                reason = tool_input.get("reason", "called out")
                if not shift_id or not original_caregiver_id:
                    return json.dumps({"error": "Missing shift_id or original_caregiver_id"})
                def _find_replacement():
                    try:
                        from sales.shift_filling.engine import shift_filling_engine
                        campaign = shift_filling_engine.process_calloff(
                            shift_id=shift_id, caregiver_id=original_caregiver_id,
                            reason=reason, reported_by="gigi_telegram"
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
                return json.dumps(await asyncio.to_thread(_find_replacement))

            elif tool_name == "get_task_board":
                def _read_task_board():
                    try:
                        path = os.path.expanduser("~/Task Board.md")
                        with open(path, "r") as f:
                            return {"task_board": f.read()}
                    except FileNotFoundError:
                        return {"task_board": "(empty)", "note": "No task board file found"}
                return json.dumps(await asyncio.to_thread(_read_task_board))

            elif tool_name == "add_task":
                task_text = tool_input.get("task", "").strip()
                section = tool_input.get("section", "Today").strip()
                if not task_text:
                    return json.dumps({"error": "No task text provided"})
                valid_sections = ["Today", "Soon", "Later", "Waiting", "Agenda", "Inbox", "Reference"]
                # Normalize section name (case-insensitive match)
                section_match = next((s for s in valid_sections if s.lower() == section.lower()), "Today")
                def _add_task():
                    try:
                        path = os.path.expanduser("~/Task Board.md")
                        with open(path, "r") as f:
                            content = f.read()
                        # Find the section header and add the task after it
                        marker = f"## {section_match}\n"
                        if marker in content:
                            idx = content.index(marker) + len(marker)
                            # Skip past any existing dash-only placeholder line
                            rest = content[idx:]
                            if rest.startswith("-\n") or rest.startswith("- \n"):
                                # Replace placeholder with real task
                                content = content[:idx] + f"- [ ] {task_text}\n" + rest[rest.index("\n") + 1:]
                            elif rest.startswith("- [ ]") or rest.startswith("- [x]"):
                                # Already has tasks, add after header
                                content = content[:idx] + f"- [ ] {task_text}\n" + rest
                            else:
                                content = content[:idx] + f"- [ ] {task_text}\n" + rest
                        else:
                            # Section not found, append at end
                            content += f"\n## {section_match}\n- [ ] {task_text}\n"
                        with open(path, "w") as f:
                            f.write(content)
                        return {"success": True, "task": task_text, "section": section_match}
                    except Exception as e:
                        return {"error": f"Failed to add task: {str(e)}"}
                return json.dumps(await asyncio.to_thread(_add_task))

            elif tool_name == "complete_task":
                task_text = tool_input.get("task_text", "").strip().lower()
                if not task_text:
                    return json.dumps({"error": "No task text provided"})
                def _complete_task():
                    try:
                        path = os.path.expanduser("~/Task Board.md")
                        with open(path, "r") as f:
                            lines = f.readlines()
                        completed = False
                        completed_task = ""
                        new_lines = []
                        done_tasks = []
                        for line in lines:
                            if not completed and "- [ ]" in line and task_text in line.lower():
                                completed_task = line.replace("- [ ]", "- [x]").strip()
                                done_tasks.append(completed_task)
                                completed = True
                                # Don't add the line here — we'll move it to Done
                            else:
                                new_lines.append(line)
                        if not completed:
                            return {"error": f"No uncompleted task matching '{task_text}' found"}
                        # Add to Done section
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
                            # No Done section — append one
                            content += f"\n## Done\n{completed_task}\n"
                        with open(path, "w") as f:
                            f.write(content)
                        return {"success": True, "completed": completed_task}
                    except Exception as e:
                        return {"error": f"Failed to complete task: {str(e)}"}
                return json.dumps(await asyncio.to_thread(_complete_task))

            elif tool_name == "capture_note":
                note = tool_input.get("note", "").strip()
                if not note:
                    return json.dumps({"error": "No note provided"})
                def _capture_note():
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
                        return {"success": True, "note": note, "captured_at": timestamp}
                    except Exception as e:
                        return {"error": f"Failed to capture note: {str(e)}"}
                return json.dumps(await asyncio.to_thread(_capture_note))

            elif tool_name == "get_daily_notes":
                target_date = tool_input.get("date", "")
                def _read_daily_notes():
                    try:
                        import re as _re
                        from datetime import datetime as dt
                        if target_date:
                            # Sanitize: only allow YYYY-MM-DD
                            d = target_date if _re.match(r"^\d{4}-\d{2}-\d{2}$", target_date) else dt.now().strftime("%Y-%m-%d")
                        else:
                            d = dt.now().strftime("%Y-%m-%d")
                        # Daily notes use format: YYYY-MM-DD Day.md or just YYYY-MM-DD.md
                        import glob as g
                        notes_dir = os.path.expanduser("~/Daily Notes")
                        matches = g.glob(os.path.join(notes_dir, f"{d}*"))
                        if matches:
                            with open(matches[0], "r") as f:
                                return {"date": d, "notes": f.read()}
                        return {"date": d, "notes": "(no daily notes for this date)"}
                    except Exception as e:
                        return {"error": f"Failed to read daily notes: {str(e)}"}
                return json.dumps(await asyncio.to_thread(_read_daily_notes))

            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            # Log to failure handler if available
            if FAILURE_HANDLER_AVAILABLE and _failure_handler:
                try:
                    _failure_handler.handle_tool_failure(tool_name, e, {"tool_input": str(tool_input)[:200]})
                except Exception:
                    pass
            return json.dumps({"error": f"Tool {tool_name} failed: {str(e)}"})

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id

        if user_id == JASON_TELEGRAM_ID:
            await update.message.reply_text(
                "👋 Hi Jason! I'm Gigi, your AI Chief of Staff.\n\n"
                "I'm now running on your Mac Mini (no more Mac Mini!).\n\n"
                "Just send me a message and I'll help with whatever you need."
            )
        else:
            await update.message.reply_text(
                "Hi! I'm Gigi, Jason's personal AI assistant. "
                "I'm currently configured to work only with Jason."
            )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await update.message.reply_text(
            "**Gigi - Your AI Chief of Staff**\n\n"
            "I can help you with:\n"
            "• Business operations (caregivers, clients, scheduling)\n"
            "• Calendar and task management\n"
            "• Weather and travel info\n"
            "• Concert info (especially Phish!)\n"
            "• Restaurant recommendations\n"
            "• General questions and research\n\n"
            "Just send me a message!"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages — dispatches to the configured LLM provider.
        Uses asyncio.Lock to prevent concurrent messages from corrupting conversation order."""
        user_id = update.effective_user.id
        message_text = update.message.text

        # Only respond to Jason
        if user_id != JASON_TELEGRAM_ID:
            logger.warning(f"Ignored message from unauthorized user: {user_id}")
            return

        logger.info(f"Message from Jason: {message_text}")

        async with self._message_lock:
            # Store user message in shared conversation store
            self.conversation_store.append("jason", "telegram", "user", message_text)

            # Send typing indicator
            await update.message.chat.send_action("typing")

            if not self.llm:
                await update.message.reply_text(
                    f"LLM not configured. Provider={LLM_PROVIDER}, check API key env vars."
                )
                return

            try:
                # Dispatch to the right provider (300s timeout to allow run_claude_code)
                if LLM_PROVIDER == "gemini":
                    final_text = await asyncio.wait_for(
                        self._call_gemini(user_id, update), timeout=300.0)
                elif LLM_PROVIDER == "openai":
                    final_text = await asyncio.wait_for(
                        self._call_openai(user_id, update), timeout=300.0)
                else:
                    final_text = await asyncio.wait_for(
                        self._call_anthropic(user_id, update), timeout=300.0)

                if not final_text:
                    final_text = "I processed your request but have no text response. Please try again."

                # Post-process: strip hallucinated CLI/install suggestions (shared filter)
                from gigi.response_filter import strip_banned_content
                final_text = strip_banned_content(final_text)

                # Store assistant response in shared conversation store
                self.conversation_store.append("jason", "telegram", "assistant", final_text)

                # Send response (split if too long for Telegram)
                if len(final_text) > 4000:
                    for i in range(0, len(final_text), 4000):
                        await update.message.reply_text(final_text[i:i+4000])
                else:
                    await update.message.reply_text(final_text)

            except asyncio.TimeoutError:
                logger.error(f"LLM timeout ({LLM_PROVIDER}/{LLM_MODEL}) after 300s")
                await update.message.reply_text(
                    "Sorry, I took too long to respond. Please try again."
                )
            except Exception as e:
                logger.error(f"LLM API error ({LLM_PROVIDER}): {e}", exc_info=True)
                await update.message.reply_text(
                    f"Error ({LLM_PROVIDER}/{LLM_MODEL}): {str(e)}"
                )

    # ═══════════════════════════════════════════════════════════
    # ANTHROPIC PROVIDER
    # ═══════════════════════════════════════════════════════════
    async def _call_anthropic(self, user_id: int, update: Update) -> str:
        """Call Anthropic Claude with tool support."""
        # Build Anthropic-format messages from shared conversation store
        history = self.conversation_store.get_recent("jason", "telegram", limit=20)
        messages = [{"role": m["role"], "content": m["content"]} for m in history]

        user_msg = update.message.text if update.message else None
        sys_prompt = _build_telegram_system_prompt(self.conversation_store, user_message=user_msg)
        response = await asyncio.to_thread(
            self.llm.messages.create,
            model=LLM_MODEL, max_tokens=4096,
            system=sys_prompt, tools=ANTHROPIC_TOOLS,
            messages=messages
        )

        # Tool calling loop
        max_rounds = 5
        for tool_round in range(max_rounds):
            if response.stop_reason != "tool_use":
                break
            logger.info(f"Tool call round {tool_round + 1} (anthropic)")

            tool_results = []
            assistant_content = []

            for block in response.content:
                if block.type == "tool_use":
                    logger.info(f"  Tool: {block.name} input: {block.input}")
                    result = await self.execute_tool(block.name, block.input)
                    logger.info(f"  Result: {result[:200]}...")
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

            await update.message.chat.send_action("typing")
            response = await asyncio.to_thread(
                self.llm.messages.create,
                model=LLM_MODEL, max_tokens=4096,
                system=sys_prompt, tools=ANTHROPIC_TOOLS,
                messages=messages
            )

        # Extract final text
        return "".join(b.text for b in response.content if b.type == "text")

    # ═══════════════════════════════════════════════════════════
    # GEMINI PROVIDER
    # ═══════════════════════════════════════════════════════════
    async def _call_gemini(self, user_id: int, update: Update) -> str:
        """Call Google Gemini with tool support."""
        # Build Gemini-format contents from shared conversation store
        history = self.conversation_store.get_recent("jason", "telegram", limit=20)
        contents = []
        for m in history:
            role = "user" if m["role"] == "user" else "model"
            contents.append(genai_types.Content(
                role=role,
                parts=[genai_types.Part(text=m["content"])]
            ))

        user_msg = update.message.text if update.message else None
        config = genai_types.GenerateContentConfig(
            system_instruction=_build_telegram_system_prompt(self.conversation_store, user_message=user_msg),
            tools=GEMINI_TOOLS,
        )

        response = await asyncio.to_thread(
            self.llm.models.generate_content,
            model=LLM_MODEL, contents=contents, config=config
        )

        # Tool calling loop
        max_rounds = 5
        fn_response_parts = []
        for tool_round in range(max_rounds):
            # Check if response has function calls
            function_calls = []
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        function_calls.append(part)

            if not function_calls:
                break

            logger.info(f"Tool call round {tool_round + 1} (gemini)")

            # Add the model's response (with function_call parts) to contents
            contents.append(response.candidates[0].content)

            # Execute each tool and build function response parts
            fn_response_parts = []
            for part in function_calls:
                fc = part.function_call
                tool_input = dict(fc.args) if fc.args else {}
                logger.info(f"  Tool: {fc.name} input: {tool_input}")
                result_str = await self.execute_tool(fc.name, tool_input)
                logger.info(f"  Result: {result_str[:200]}...")

                # Parse JSON result for structured response
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

            await update.message.chat.send_action("typing")
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
        final = "".join(text_parts)

        # Safety net: if Gemini returned no text after tool calls, use last tool result
        if not final and fn_response_parts:
            logger.warning("Gemini returned no text after tool call — using tool result as fallback")
            last_part = fn_response_parts[-1]
            if hasattr(last_part, 'function_response') and last_part.function_response:
                fr = last_part.function_response
                resp_data = fr.response if hasattr(fr, 'response') else {}
                if isinstance(resp_data, dict):
                    final = json.dumps(resp_data, indent=2, default=str)
                else:
                    final = str(resp_data)
        return final

    # ═══════════════════════════════════════════════════════════
    # OPENAI PROVIDER
    # ═══════════════════════════════════════════════════════════
    async def _call_openai(self, user_id: int, update: Update) -> str:
        """Call OpenAI with tool support."""
        # Build OpenAI-format messages from shared conversation store
        history = self.conversation_store.get_recent("jason", "telegram", limit=20)
        user_msg = update.message.text if update.message else None
        messages = [{"role": "system", "content": _build_telegram_system_prompt(self.conversation_store, user_message=user_msg)}]
        for m in history:
            messages.append({"role": m["role"], "content": m["content"]})

        response = await asyncio.to_thread(
            self.llm.chat.completions.create,
            model=LLM_MODEL, messages=messages, tools=OPENAI_TOOLS
        )

        # Tool calling loop
        max_rounds = 5
        for tool_round in range(max_rounds):
            choice = response.choices[0]
            if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
                break

            logger.info(f"Tool call round {tool_round + 1} (openai)")

            # Add assistant message with tool calls
            messages.append(choice.message)

            # Execute each tool call
            for tc in choice.message.tool_calls:
                tool_input = json.loads(tc.function.arguments)
                logger.info(f"  Tool: {tc.function.name} input: {tool_input}")
                result_str = await self.execute_tool(tc.function.name, tool_input)
                logger.info(f"  Result: {result_str[:200]}...")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str
                })

            await update.message.chat.send_action("typing")
            response = await asyncio.to_thread(
                self.llm.chat.completions.create,
                model=LLM_MODEL, messages=messages, tools=OPENAI_TOOLS
            )

        return response.choices[0].message.content or ""

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")

async def main():
    """Run the bot with automatic restart on failure"""
    max_retries = 10
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            logger.info(f"🤖 Starting Gigi Telegram Bot on Mac Mini (attempt {attempt + 1}/{max_retries})...")
            logger.info(f"   Bot Token: {TELEGRAM_BOT_TOKEN[:20]}...")
            logger.info(f"   Jason's Chat ID: {JASON_TELEGRAM_ID}")

            # Create bot instance
            gigi = GigiTelegramBot()

            # Create application with connection pool settings for reliability
            app = (
                Application.builder()
                .token(TELEGRAM_BOT_TOKEN)
                .connect_timeout(30.0)
                .read_timeout(30.0)
                .write_timeout(30.0)
                .pool_timeout(30.0)
                .build()
            )

            # Add handlers
            app.add_handler(CommandHandler("start", gigi.start_command))
            app.add_handler(CommandHandler("help", gigi.help_command))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gigi.handle_message))
            app.add_error_handler(gigi.error_handler)

            # Initialize and clear any stale sessions
            await app.initialize()

            # Delete any stale webhook/polling sessions to prevent 409 Conflict
            await app.bot.delete_webhook(drop_pending_updates=True)
            logger.info("Cleared stale Telegram sessions")

            # Wait for Telegram to fully release any active getUpdates long-poll connections
            # Telegram's long-poll timeout is typically 25-30 seconds
            wait_secs = 5 if attempt == 0 else min(30, 5 * (attempt + 1))
            logger.info(f"Waiting {wait_secs}s for Telegram to release stale connections...")
            await asyncio.sleep(wait_secs)

            await app.start()
            await app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=["message"],
                poll_interval=1.0,
            )

            logger.info("✅ Gigi Telegram Bot is running!")
            logger.info("   Send a message to @Shulmeisterbot to test")

            # Keep running
            while True:
                await asyncio.sleep(60)
                # Heartbeat log every minute
                logger.debug("Heartbeat: Bot is running")

        except KeyboardInterrupt:
            logger.info("Shutting down Gigi Telegram Bot (user requested)...")
            break
        except Exception as e:
            error_str = str(e)
            is_conflict = "Conflict" in error_str or "409" in error_str

            if is_conflict:
                logger.warning(f"409 Conflict on attempt {attempt + 1} — another polling session still active, waiting...")
                wait_time = 30  # Always wait 30s for 409 to let Telegram release the connection
            else:
                logger.error(f"Bot crashed with error: {e}", exc_info=True)
                wait_time = retry_delay * (2 ** attempt)

            if attempt < max_retries - 1:
                logger.info(f"   Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.error("   Max retries reached. Exiting.")
                raise
        finally:
            try:
                if 'app' in locals():
                    await app.updater.stop()
                    await app.stop()
                    await app.shutdown()
            except Exception as cleanup_error:
                logger.warning(f"Cleanup error: {cleanup_error}")

def run_bot():
    """Entry point with process-level restart"""
    while True:
        try:
            asyncio.run(main())
            break  # Clean exit
        except Exception as e:
            logger.error(f"Fatal error in bot: {e}")
            logger.info("Restarting bot in 30 seconds...")
            import time
            time.sleep(30)

if __name__ == "__main__":
    run_bot()

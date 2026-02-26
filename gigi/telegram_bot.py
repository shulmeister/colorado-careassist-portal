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
from datetime import datetime
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
    from gigi.memory_system import MemoryStatus, MemorySystem
    _memory_system = MemorySystem()
    MEMORY_AVAILABLE = True
    print("✓ Memory system initialized for Telegram bot")
except Exception as e:
    _memory_system = None
    MEMORY_AVAILABLE = False
    MemoryStatus = None
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
LLM_PROVIDER = os.getenv("GIGI_LLM_PROVIDER", "anthropic").lower()
_DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash-preview-05-20",
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
}
LLM_MODEL = os.getenv("GIGI_LLM_MODEL", _DEFAULT_MODELS.get(LLM_PROVIDER, "claude-haiku-4-5-20251001"))

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
    "search_events", "search_concerts", "buy_tickets_request", "book_table_request", "explore_national_parks", "explore_art", "search_phish", "search_books", "search_nytimes", "search_f1",
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
    "search_flights", "search_hotels", "search_car_rentals", "search_transfers",
    "get_flight_status", "explore_flights", "confirm_flight_price", "get_seatmap",
    "search_flight_availability", "book_flight", "manage_flight_booking",
    "get_airport_info", "get_airline_info", "get_hotel_ratings", "book_hotel",
    "book_transfer", "manage_transfer", "search_activities", "get_travel_insights",
]

# Tool definitions — single source of truth is tool_registry.py.
# ANTHROPIC_TOOLS imported here for backwards compatibility with Gemini tool conversion
# and the auto-extend code in ringcentral_bot.py.
from gigi.tool_registry import CANONICAL_TOOLS as ANTHROPIC_TOOLS

# Keep the old variable alive as a list so code that mutates it still works.
ANTHROPIC_TOOLS = list(ANTHROPIC_TOOLS)


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
        # get_morning_briefing REMOVED — user does NOT want briefings
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
        # === TERMINAL TOOLS ===
        genai_types.FunctionDeclaration(name="run_terminal", description="Execute a shell command directly on the Mac Mini. Instant, free. Use for logs, service status, git, file checks.",
            parameters=genai_types.Schema(type="OBJECT", properties={"command": _s("string", "Shell command to execute"), "timeout": _s("INTEGER", "Timeout in seconds (default 30)")}, required=["command"])),
        # === THINKING TOOLS ===
        genai_types.FunctionDeclaration(name="sequential_thinking", description="Think through a complex problem step by step. Use for investigations, debugging, planning.",
            parameters=genai_types.Schema(type="OBJECT", properties={"thought": _s("string", "Current thinking step"), "thought_number": _s("INTEGER", "Step number"), "total_thoughts": _s("INTEGER", "Estimated total"), "next_thought_needed": _s("BOOLEAN", "Need more thinking"), "is_revision": _s("BOOLEAN", "Reconsidering earlier thought"), "revises_thought": _s("INTEGER", "Which thought to revise"), "branch_from_thought": _s("INTEGER", "Branch point"), "branch_id": _s("string", "Branch label")}, required=["thought", "thought_number", "total_thoughts", "next_thought_needed"])),
        genai_types.FunctionDeclaration(name="get_thinking_summary", description="Get the full chain of sequential thoughts.",
            parameters=genai_types.Schema(type="OBJECT", properties={})),
        # === KNOWLEDGE GRAPH TOOLS ===
        genai_types.FunctionDeclaration(name="update_knowledge_graph", description="Update knowledge graph: add/remove entities, relations, observations. Use JSON strings for complex params.",
            parameters=genai_types.Schema(type="OBJECT", properties={"action": _s("string", "add_entities|add_relations|add_observations|delete_entities|delete_relations|delete_observations"), "entities": _s("string", "JSON array of {name, entityType, observations[]}"), "relations": _s("string", "JSON array of {from, to, relationType}"), "observations": _s("string", "JSON array of {entityName, contents[]}"), "entity_names": _s("string", "JSON array of entity names to delete")}, required=["action"])),
        genai_types.FunctionDeclaration(name="query_knowledge_graph", description="Query knowledge graph for entities, relations, observations.",
            parameters=genai_types.Schema(type="OBJECT", properties={"action": _s("string", "search|open_nodes|read_graph"), "query": _s("string", "Search text"), "names": _s("string", "JSON array of entity names")}, required=["action"])),
        # === GOOGLE MAPS TOOLS ===
        genai_types.FunctionDeclaration(name="get_directions", description="Get driving directions, distance, and travel time between two locations.",
            parameters=genai_types.Schema(type="OBJECT", properties={"origin": _s("string", "Start address or place name"), "destination": _s("string", "End address or place name"), "mode": _s("string", "driving|transit|walking|bicycling")}, required=["origin", "destination"])),
        genai_types.FunctionDeclaration(name="geocode_address", description="Geocode an address to get coordinates, validate, and normalize.",
            parameters=genai_types.Schema(type="OBJECT", properties={"address": _s("string", "Address to geocode")}, required=["address"])),
        genai_types.FunctionDeclaration(name="search_nearby_places", description="Find nearby places (pharmacy, hospital, grocery, restaurant, etc.) around a location.",
            parameters=genai_types.Schema(type="OBJECT", properties={"location": _s("string", "Address or place name"), "place_type": _s("string", "pharmacy|hospital|doctor|grocery|restaurant|gas_station|bank|etc."), "radius_miles": _s("INTEGER", "Search radius in miles (default 5)")}, required=["location", "place_type"])),
        # === GOOGLE WORKSPACE ADMIN (GAM) — READ ONLY ===
        genai_types.FunctionDeclaration(name="query_workspace", description="Query Google Workspace admin data (READ-ONLY). Look up users, groups, domains, reports. Examples: 'info user jacob@coloradocareassist.com', 'print users', 'print groups'.",
            parameters=genai_types.Schema(type="OBJECT", properties={"command": _s("string", "GAM command WITHOUT leading 'gam'. Only read commands allowed.")}, required=["command"])),
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
    # get_morning_briefing REMOVED — morning briefing permanently deleted per user request
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
    # === TERMINAL TOOLS ===
    _oai_tool("run_terminal", "Execute a shell command directly on the Mac Mini. Instant, free. Use for logs, service status, git, file checks.", {"command": {"type": "string", "description": "Shell command to execute"}, "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"}}, ["command"]),
    # === THINKING TOOLS ===
    _oai_tool("sequential_thinking", "Think through a complex problem step by step.", {"thought": {"type": "string", "description": "Current thinking step"}, "thought_number": {"type": "integer", "description": "Step number"}, "total_thoughts": {"type": "integer", "description": "Estimated total"}, "next_thought_needed": {"type": "boolean", "description": "Need more thinking"}, "is_revision": {"type": "boolean", "description": "Reconsidering earlier thought"}, "revises_thought": {"type": "integer", "description": "Which thought to revise"}, "branch_from_thought": {"type": "integer", "description": "Branch point"}, "branch_id": {"type": "string", "description": "Branch label"}}, ["thought", "thought_number", "total_thoughts", "next_thought_needed"]),
    _oai_tool("get_thinking_summary", "Get the full chain of sequential thoughts.", {}),
    # === KNOWLEDGE GRAPH TOOLS ===
    _oai_tool("update_knowledge_graph", "Update knowledge graph: add/remove entities, relations, observations.", {"action": {"type": "string", "description": "add_entities|add_relations|add_observations|delete_entities|delete_relations|delete_observations"}, "entities": {"type": "array", "description": "For add_entities", "items": {"type": "object"}}, "relations": {"type": "array", "description": "For add/delete_relations", "items": {"type": "object"}}, "observations": {"type": "array", "description": "For add/delete_observations", "items": {"type": "object"}}, "entity_names": {"type": "array", "description": "For delete_entities", "items": {"type": "string"}}}, ["action"]),
    _oai_tool("query_knowledge_graph", "Query knowledge graph for entities, relations, observations.", {"action": {"type": "string", "description": "search|open_nodes|read_graph"}, "query": {"type": "string", "description": "Search text"}, "names": {"type": "array", "description": "Entity names to retrieve", "items": {"type": "string"}}}, ["action"]),
    # === GOOGLE MAPS TOOLS ===
    _oai_tool("get_directions", "Get driving directions, distance, and travel time between two locations.", {"origin": {"type": "string", "description": "Start address or place name"}, "destination": {"type": "string", "description": "End address or place name"}, "mode": {"type": "string", "description": "driving|transit|walking|bicycling"}}, ["origin", "destination"]),
    _oai_tool("geocode_address", "Geocode an address to get coordinates, validate, and normalize.", {"address": {"type": "string", "description": "Address to geocode"}}, ["address"]),
    _oai_tool("search_nearby_places", "Find nearby places around a location.", {"location": {"type": "string", "description": "Address or place name"}, "place_type": {"type": "string", "description": "pharmacy|hospital|doctor|grocery|restaurant|gas_station|bank|etc."}, "radius_miles": {"type": "integer", "description": "Search radius in miles (default 5)"}}, ["location", "place_type"]),
    # === GOOGLE WORKSPACE ADMIN (GAM) — READ ONLY ===
    _oai_tool("query_workspace", "Query Google Workspace admin data (READ-ONLY). Look up users, groups, domains, reports. Examples: 'info user jacob@coloradocareassist.com', 'print users', 'print groups'.", {"command": {"type": "string", "description": "GAM command WITHOUT leading 'gam'. Only read commands allowed."}}, ["command"]),
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
- Direct, warm, action-oriented personality
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
- run_terminal: Execute a shell command INSTANTLY on the Mac Mini. FREE (no API cost). Use for quick checks: tail logs, launchctl status, git status/log, ls, ps, lsof, disk usage, kill+restart a service. PREFER THIS for simple commands. Use run_claude_code only when you need AI reasoning (multi-step fixes, code edits, debugging).
- run_claude_code: Execute code/infra tasks DIRECTLY using Claude Code. Fixes bugs, edits files, checks logs, runs tests, restarts services, git ops. Returns result immediately (synchronous). PREFER THIS over create_claude_task. Directories: careassist (staging, default), production, website, hesed, trading, weather-arb, kalshi, powderpulse, employee-portal, client-portal, status-dashboard, qbo-dashboard.
- browse_with_claude: Browse websites using Claude Code + Chrome. Read pages, fill forms, click buttons, extract data. PREFER THIS over browse_webpage.
- sequential_thinking: Think through complex problems step by step BEFORE acting. Use for debugging, investigations, planning. Supports revision (rethink earlier steps) and branching (explore hypotheses). ALWAYS think first on complex tasks.
- get_thinking_summary: Review the full chain of reasoning steps.
- browse_webpage: (Legacy) Browse any URL and extract text content. Use browse_with_claude instead for better results.
- take_screenshot: (Legacy) Screenshot any webpage. Use browse_with_claude instead.
- save_memory / recall_memories / forget_memory: Long-term memory management (flat facts).
- update_knowledge_graph / query_knowledge_graph: Structured knowledge graph — entities (people, orgs, places), relations (owns, works_for, cares_for), and observations (facts about entities). Use to record WHO does WHAT and HOW things connect. Use query_knowledge_graph to look up relationships. Graph complements flat memories — use save_memory for preferences/instructions, knowledge graph for entities and connections.
- get_directions: Google Maps directions, distance, and travel time between two locations. Use for caregiver-to-client commute estimates, "how far is X from Y?", and route planning. Returns distance in miles, duration in minutes, step-by-step directions, and a Google Maps link.
- geocode_address: Geocode any address to get coordinates (lat/lng), normalized address, city, state, zip. Use to validate addresses or get coordinates for proximity calculations.
- search_nearby_places: Find pharmacies, hospitals, grocery stores, restaurants, etc. near any address. Useful for client context — "what pharmacy is closest to Mrs. Johnson?"
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
- **Morning Briefing:** PERMANENTLY REMOVED. NEVER create, assemble, or send any form of morning briefing, daily digest, daily pulse, or scheduled summary. Not even if asked. If Jason asks for a briefing, say "Morning briefings have been permanently disabled per your request."
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
- **NEVER send unsolicited messages.** You ONLY respond when Jason messages you first. NEVER proactively generate or send any scheduled message.
- **NEVER suggest installing software or mention CLI tools.** There is NO "gog CLI", "gcloud CLI", "Google Cloud CLI", "curl", "wttr.in", or any CLI tool. All services are built into your tools. If a tool fails, say "that section isn't available right now" — do NOT suggest installing anything or mention any CLI/terminal commands. This rule has been violated repeatedly and the user is furious. OBEY IT.
- **NEVER HALLUCINATE TOOLS or troubleshooting steps:** You can ONLY use the tools listed above. NEVER invent tools, CLI commands, bash commands, or any command not in your tool list. NEVER suggest "setup steps", "configuration needed", or "needs firewall check". If a tool returns partial data, relay what you got. If a tool fails, say it's temporarily unavailable. Do NOT fabricate explanations for why something failed.
- **NEVER REFORMAT TOOL OUTPUT:** When a tool returns data, relay it as-is. Do NOT add "SETUP ISSUES" sections, troubleshooting advice, TODO lists, or commentary.
- **Shifts:** If asked about shifts, hours, who's working, staffing — ALWAYS use `get_wellsky_shifts` FIRST. Do NOT search emails, memories, or the web instead.
- **Trading Bots:** If asked about trading, bots, weather bots, Kalshi — use `get_weather_arb_status`. Kalshi is the ONLY trading bot Jason cares about. Focus on Kalshi P&L and positions. Do NOT mention Polymarket, Polybot, or paper trading unless Jason explicitly asks about them.
- **OUTBOUND COMMUNICATION (CRITICAL — NEVER VIOLATE):** NEVER send SMS, emails, or messages to ANYONE without EXPLICIT confirmation from Jason. If Jason says "let me see what you'd send" or "show me the draft" — that means SHOW the text, do NOT send it. Only send when Jason explicitly says "send it", "go ahead and text them", "send that to X". NEVER use create_claude_task to send messages — Claude Code is NOT allowed to send SMS/email/calls. If Jason wants to send a message, ask: "Here's the draft. Want me to send it now?" and WAIT for confirmation.
- **Code Fixes (CRITICAL):** When Jason asks you to fix something, debug a problem, investigate an issue, update code, check why something isn't working, or make any changes to a codebase — ALWAYS use `run_claude_code` IMMEDIATELY. This invokes Claude Code directly on the Mac Mini and returns the result within 2 minutes (synchronous). Claude Code can read/edit files, run commands, restart services, and deploy fixes autonomously. Write a DETAILED prompt explaining: what's broken, error messages if any, which project/files are involved, and what the expected behavior should be. Set directory to the right project alias. Only use `create_claude_task` (async queue) as a fallback if run_claude_code times out. NEVER use run_claude_code or create_claude_task to send messages, texts, or emails — only for code/infrastructure work.
- **Working directories:** careassist (staging, default), production, website, hesed, trading, weather-arb, kalshi, powderpulse, employee-portal, client-portal, status-dashboard, qbo-dashboard.

# Response Style
- Concise, confident, executive summary style. Short answers.
- Action-oriented: "I found 3 shows. The Friday one at Red Rocks looks great — want me to grab tickets? What kind of seats are you thinking — GA, reserved, VIP?"
- NO sycophantic language: never say "locked in", "inner circle", "got you fam", "absolutely", "on it boss", or similar cringe phrases.
- NO emojis unless Jason uses them first. Keep it professional.
- NO over-promising. Say what you WILL do, not what you COULD theoretically do.
- Be direct and real. If something is broken, say so. Don't sugarcoat.
- NEVER start with "Great question!" or "I'd be happy to help!" — just answer.
"""


def _build_telegram_system_prompt(conversation_store=None, user_message=None):
    """Build the system prompt with dynamic context: date, memories, mode, cross-channel."""
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
            memories = _memory_system.query_memories(min_confidence=0.5, limit=25, status=MemoryStatus.ACTIVE)
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

    return "\n".join(parts)


class GigiTelegramBot:
    def __init__(self):
        # Initialize the right LLM client based on GIGI_LLM_PROVIDER
        self.llm = None
        if LLM_PROVIDER == "gemini" and GEMINI_AVAILABLE and GEMINI_API_KEY:
            self.llm = genai.Client(api_key=GEMINI_API_KEY)
        elif LLM_PROVIDER == "openai" and OPENAI_AVAILABLE and OPENAI_API_KEY:
            self.llm = openai.OpenAI(api_key=OPENAI_API_KEY)
        elif LLM_PROVIDER == "anthropic" and ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
            self.llm = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        else:
            # Fallback: try any available provider
            if ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
                self.llm = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
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
        # Register google service with shared tool executor
        import gigi.tool_executor as _tex
        _tex.set_google_service(self.google)

    async def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool. All implementations live in gigi/tool_executor.py."""
        import gigi.tool_executor as _tex
        return await _tex.execute(tool_name, tool_input)

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
                # Fallback chain: primary provider → anthropic haiku on rate limit
                final_text = None
                used_provider = LLM_PROVIDER
                try:
                    if LLM_PROVIDER == "gemini":
                        final_text = await asyncio.wait_for(
                            self._call_gemini(user_id, update), timeout=300.0)
                    elif LLM_PROVIDER == "openai":
                        final_text = await asyncio.wait_for(
                            self._call_openai(user_id, update), timeout=300.0)
                    else:
                        final_text = await asyncio.wait_for(
                            self._call_anthropic(user_id, update), timeout=300.0)
                except Exception as e:
                    err_str = str(e).lower()
                    is_rate_limit = any(k in err_str for k in ("429", "resource_exhausted", "rate_limit", "quota"))
                    if is_rate_limit and LLM_PROVIDER != "anthropic":
                        logger.warning(f"{LLM_PROVIDER} rate limited, falling back to anthropic: {e}")
                        used_provider = "anthropic (fallback)"
                        final_text = await asyncio.wait_for(
                            self._call_anthropic(user_id, update), timeout=300.0)
                    else:
                        raise

                if not final_text:
                    final_text = "I processed your request but have no text response. Please try again."

                # Post-process: strip hallucinated CLI/install suggestions (shared filter)
                from gigi.response_filter import strip_banned_content
                final_text = strip_banned_content(final_text)

                # Store assistant response in shared conversation store
                self.conversation_store.append("jason", "telegram", "assistant", final_text)

                if used_provider != LLM_PROVIDER:
                    logger.info(f"Response served via {used_provider}")

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
        response = await self.llm.messages.create(
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

            # Separate tool_use blocks from text blocks
            tool_blocks = [block for block in response.content if block.type == "tool_use"]
            for block in response.content:
                if block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use", "id": block.id,
                        "name": block.name, "input": block.input
                    })
                elif block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})

            # Execute all tools in parallel
            if tool_blocks:
                logger.info(f"  Executing {len(tool_blocks)} tool(s) in parallel")
                results = await asyncio.gather(*[
                    self.execute_tool(block.name, block.input) for block in tool_blocks
                ])
                for block, result in zip(tool_blocks, results):
                    logger.info(f"  Tool: {block.name} result: {result[:200]}...")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

            await update.message.chat.send_action("typing")
            response = await self.llm.messages.create(
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

#!/usr/bin/env python3
"""
Gigi Telegram Bot - Personal AI Assistant
Handles Telegram messages for Jason via @Shulmeisterbot
WITH ACTUAL TOOL CALLING - Calendar, Email, WellSky
"""

import os
import sys
import logging
import asyncio
import json
from datetime import datetime, date
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
        MessageHandler,
        filters,
        ContextTypes,
    )
except ImportError:
    print("❌ python-telegram-bot not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-telegram-bot>=20.0"])
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        filters,
        ContextTypes,
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
    from gigi.memory_system import MemorySystem, MemoryType, MemorySource, ImpactLevel
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
    {"name": "get_weather_arb_status", "description": "Get live status of BOTH weather temperature trading bots: (1) Polymarket bot — trades international temperature markets via laddering strategy, and (2) Kalshi bot — trades US temperature markets on the regulated Kalshi/Coinbase exchange. Both are LIVE with real money. Use when asked about weather arb, weather bots, weather trading, temperature bets, Polymarket weather, or Kalshi weather.", "input_schema": {"type": "object", "properties": {}, "required": []}},
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
        genai_types.FunctionDeclaration(name="get_weather_arb_status", description="Get BOTH weather trading bots: Polymarket (international temps) and Kalshi (US temps). Both LIVE with real money. Use for weather arb, weather bot, temperature bets.",
            parameters=genai_types.Schema(type="OBJECT", properties={})),
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
    _oai_tool("get_weather_arb_status", "Get BOTH weather trading bots: Polymarket (international temps) and Kalshi (US temps). Both LIVE with real money. Use for weather arb, weather bot, temperature bets.", {}),
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
- **Concerts & Events:** You can find concerts (search_concerts) and BUY tickets (buy_tickets_request).
- **Dining:** You can make restaurant reservations (book_table_request).
- **Weather:** Use `get_weather` for real-time weather and forecasts.
- **Flights:** Use `web_search` to find flight prices and options.
- **Secure Purchasing:** For any purchase or booking, you initiate a secure 2FA handshake.
- **Unified Intelligence:** You check Jason's email and calendar across all accounts.
- **Memory:** Save and recall memories (save_memory, recall_memories, forget_memory).

# Jason's Profile
- Owner of Colorado Care Assist
- Lives in Denver/Arvada, CO
- Phone: 603-997-1495
- Email: jason@coloradocareassist.com
- Huge Phish fan (his favorite band)

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
- get_polybot_status: Elite Trading paper-mode Polybot status.
- get_weather_arb_status: LIVE weather trading bots (Polymarket + Kalshi) with real money.
- web_search: General knowledge, flight prices, travel info.
- browse_webpage: Browse any URL and extract its text content (for deep research, reading articles).
- take_screenshot: Screenshot any webpage (saves to ~/logs/screenshots/).
- save_memory / recall_memories / forget_memory: Long-term memory management.
- get_morning_briefing: Full daily briefing (weather, calendar, shifts, emails, ski, alerts).
- get_ar_report: QuickBooks accounts receivable aging report (outstanding invoices, overdue amounts).

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
- **NEVER suggest installing software or mention CLI tools.** There is NO "gog CLI", "gcloud CLI", "Google Cloud CLI", "curl", "wttr.in", or any CLI tool. All services are built into your tools. If a tool fails, say "that section isn't available right now" — do NOT suggest installing anything or mention any CLI/terminal commands. This rule has been violated repeatedly and the user is furious. OBEY IT.
- **NEVER HALLUCINATE TOOLS or troubleshooting steps:** You can ONLY use the tools listed above. NEVER invent tools, CLI commands, bash commands, or any command not in your tool list. NEVER suggest "setup steps", "configuration needed", or "needs firewall check". If a tool returns partial data, relay what you got. If a tool fails, say it's temporarily unavailable. Do NOT fabricate explanations for why something failed.
- **NEVER REFORMAT TOOL OUTPUT:** When `get_morning_briefing` returns a briefing, send it EXACTLY as returned. Do NOT add "SETUP ISSUES" sections, troubleshooting advice, TODO lists, or any commentary. The briefing is COMPLETE — relay it verbatim.
- **Shifts:** If asked about shifts, hours, who's working, staffing — ALWAYS use `get_wellsky_shifts` FIRST. Do NOT search emails, memories, or the web instead.
- **Trading Bots:** If asked about weather bots, Polymarket, Kalshi, trading — use `get_weather_arb_status`. If asked about Polybot/Elite Trading — use `get_polybot_status`.
- **OUTBOUND COMMUNICATION (CRITICAL — NEVER VIOLATE):** NEVER send SMS, emails, or messages to ANYONE without EXPLICIT confirmation from Jason. If Jason says "let me see what you'd send" or "show me the draft" — that means SHOW the text, do NOT send it. Only send when Jason explicitly says "send it", "go ahead and text them", "send that to X". NEVER use create_claude_task to send messages — Claude Code is NOT allowed to send SMS/email/calls. If Jason wants to send a message, ask: "Here's the draft. Want me to send it now?" and WAIT for confirmation.
- **Code Fixes (CRITICAL):** When Jason asks you to fix something, debug a problem, investigate an issue, update code, check why something isn't working, or make any changes to a codebase — ALWAYS use `create_claude_task` IMMEDIATELY. This dispatches work to Claude Code running on the Mac Mini. Claude Code can read/edit files, run commands, restart services, and deploy fixes autonomously. Write a DETAILED description explaining: what's broken, error messages if any, which project/files are involved, and what the expected behavior should be. Set priority to 'urgent' for broken services, 'high' for important issues, 'normal' for routine tasks. After creating the task, tell Jason the task number. Claude Code picks up tasks within 30 seconds and you'll both get a Telegram notification when it's done. Use `check_claude_task` to check progress. NEVER use create_claude_task to send messages, texts, or emails — only for code/infrastructure work.
- **Working directories for tasks:** careassist-unified=/Users/shulmeister/mac-mini-apps/careassist-unified, elite-trading=/Users/shulmeister/mac-mini-apps/elite-trading-mcp, website=/Users/shulmeister/mac-mini-apps/coloradocareassist, hesed=/Users/shulmeister/mac-mini-apps/hesedhomecare. Default is careassist-unified if unsure.

# Response Style
- Concise, confident, executive summary style. Short answers.
- Proactive: "I found 3 shows. The Friday one at Red Rocks looks great — want me to grab tickets? What kind of seats are you thinking — GA, reserved, VIP?"
- NO sycophantic language: never say "locked in", "inner circle", "got you fam", "absolutely", "on it boss", or similar cringe phrases.
- NO emojis unless Jason uses them first. Keep it professional.
- NO over-promising. Say what you WILL do, not what you COULD theoretically do.
- Be direct and real. If something is broken, say so. Don't sugarcoat.
- NEVER start with "Great question!" or "I'd be happy to help!" — just answer.
"""


def _build_telegram_system_prompt(conversation_store=None):
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
            memories = _memory_system.query_memories(min_confidence=0.5, limit=10)
            if memories:
                memory_lines = [f"- {m.content} (confidence: {m.confidence:.0%}, category: {m.category})" for m in memories]
                parts.append("\n# Your Saved Memories\n" + "\n".join(memory_lines))
        except Exception as e:
            logger.warning(f"Memory injection failed: {e}")

    # Inject cross-channel context
    if conversation_store:
        try:
            xc = conversation_store.get_cross_channel_summary("jason", "telegram", limit=5, hours=4)
            if xc:
                parts.append(xc)
        except Exception as e:
            logger.warning(f"Cross-channel context failed: {e}")

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
                    import psycopg2
                    from datetime import datetime
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
                from gigi.browser_automation import get_browser
                browser = get_browser()
                url = tool_input.get("url", "")
                extract_links = tool_input.get("extract_links", False)
                result = await browser.browse_webpage(url, extract_links=extract_links)
                return json.dumps(result)

            elif tool_name == "take_screenshot":
                from gigi.browser_automation import get_browser
                browser = get_browser()
                url = tool_input.get("url", "")
                full_page = tool_input.get("full_page", False)
                result = await browser.take_screenshot(url, full_page=full_page)
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
                    report = []
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        # --- Polymarket Weather Bot (port 3010) ---
                        try:
                            poly_resp = await client.get("http://127.0.0.1:3010/pnl")
                            if poly_resp.status_code == 200:
                                data = poly_resp.json()
                                report.append("=== POLYMARKET WEATHER BOT (LIVE) ===")
                                report.append(f"Portfolio: ${data.get('portfolio_value', 0):,.2f} | Cash: ${data.get('cash', 0):,.2f}")
                                report.append(f"Deployed: ${data.get('deployed', 0):,.2f} | Current Value: ${data.get('current_value', 0):,.2f}")
                                pnl_val = data.get('unrealized_pnl', 0)
                                pnl_pct = data.get('unrealized_pnl_pct', 0)
                                report.append(f"Unrealized P&L: ${pnl_val:+,.2f} ({pnl_pct:+.1f}%)")
                                positions = data.get("positions", [])
                                report.append(f"Open Positions ({len(positions)}):")
                                for p in positions:
                                    title = p.get("title", "?")
                                    shares = p.get("shares", 0)
                                    entry = p.get("entry", 0)
                                    current = p.get("current")
                                    pos_pnl = p.get("pnl")
                                    pos_pct = p.get("pnl_pct")
                                    price_str = f"{current:.0%}" if current else "?"
                                    pnl_str = f"${pos_pnl:+.2f} ({pos_pct:+.1f}%)" if pos_pnl is not None else "N/A"
                                    report.append(f"  {title}: {shares:.0f} shares @ {entry:.0%} -> {price_str} | {pnl_str}")
                            else:
                                report.append("=== POLYMARKET WEATHER BOT — NOT RESPONDING ===")
                        except Exception:
                            report.append("=== POLYMARKET WEATHER BOT — OFFLINE ===")

                        report.append("")

                        # --- Kalshi Weather Bot (port 3011) ---
                        try:
                            kalshi_resp = await client.get("http://127.0.0.1:3011/pnl")
                            if kalshi_resp.status_code == 200:
                                data = kalshi_resp.json()
                                report.append("=== KALSHI WEATHER BOT (LIVE) ===")
                                report.append(f"Portfolio: ${data.get('portfolio_value', 0):,.2f} | Cash: ${data.get('cash', 0):,.2f}")
                                report.append(f"Current Value: ${data.get('current_value', 0):,.2f}")
                                pnl_val = data.get('unrealized_pnl', 0)
                                report.append(f"Unrealized P&L: ${pnl_val:+,.2f}")
                                positions = data.get("positions", [])
                                report.append(f"Open Positions ({len(positions)}):")
                                for p in positions:
                                    ticker = p.get("ticker", "?")
                                    count = p.get("count", 0)
                                    value = p.get("value", 0)
                                    pos_pnl = p.get("pnl", 0)
                                    report.append(f"  {ticker}: {count} contracts | Value: ${value:.2f} | P&L: ${pos_pnl:+.2f}")
                            else:
                                report.append("=== KALSHI WEATHER BOT — NOT RESPONDING ===")
                        except Exception:
                            report.append("=== KALSHI WEATHER BOT — OFFLINE ===")

                        return "\n".join(report)
                except Exception as e:
                    logger.error(f"Weather arb status failed: {e}")
                    return f"Weather bots unavailable: {e}"

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
                # Dispatch to the right provider (with 60s timeout)
                if LLM_PROVIDER == "gemini":
                    final_text = await asyncio.wait_for(
                        self._call_gemini(user_id, update), timeout=60.0)
                elif LLM_PROVIDER == "openai":
                    final_text = await asyncio.wait_for(
                        self._call_openai(user_id, update), timeout=60.0)
                else:
                    final_text = await asyncio.wait_for(
                        self._call_anthropic(user_id, update), timeout=60.0)

                if not final_text:
                    final_text = "I processed your request but have no text response. Please try again."

                # Post-process: strip hallucinated CLI/install suggestions that Gemini keeps adding
                _banned_phrases = ["gog cli", "gcloud cli", "gcloud", "google cloud cli",
                                   "needs curl", "needs firewall", "install/configure",
                                   "set up gcloud", "provide gmail api key"]
                final_lower = final_text.lower()
                if any(bp in final_lower for bp in _banned_phrases):
                    # Strip the hallucinated sections — remove lines containing banned phrases
                    import re
                    lines = final_text.split('\n')
                    cleaned = []
                    skip_section = False
                    for line in lines:
                        ll = line.lower().strip()
                        if any(bp in ll for bp in _banned_phrases) or ll.startswith("• [ ]"):
                            skip_section = True
                            continue
                        if skip_section and (ll.startswith("•") or ll.startswith("- [") or ll == ""):
                            continue
                        skip_section = False
                        cleaned.append(line)
                    final_text = '\n'.join(cleaned).strip()
                    if not final_text:
                        final_text = "Briefing generated — some sections are temporarily unavailable."
                    logger.warning("Stripped hallucinated CLI references from LLM response")

                # Store assistant response in shared conversation store
                self.conversation_store.append("jason", "telegram", "assistant", final_text)

                # Send response (split if too long for Telegram)
                if len(final_text) > 4000:
                    for i in range(0, len(final_text), 4000):
                        await update.message.reply_text(final_text[i:i+4000])
                else:
                    await update.message.reply_text(final_text)

            except asyncio.TimeoutError:
                logger.error(f"LLM timeout ({LLM_PROVIDER}/{LLM_MODEL}) after 60s")
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

        sys_prompt = _build_telegram_system_prompt(self.conversation_store)
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

        config = genai_types.GenerateContentConfig(
            system_instruction=_build_telegram_system_prompt(self.conversation_store),
            tools=GEMINI_TOOLS,
        )

        response = await asyncio.to_thread(
            self.llm.models.generate_content,
            model=LLM_MODEL, contents=contents, config=config
        )

        # Tool calling loop
        max_rounds = 5
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
        return "".join(text_parts)

    # ═══════════════════════════════════════════════════════════
    # OPENAI PROVIDER
    # ═══════════════════════════════════════════════════════════
    async def _call_openai(self, user_id: int, update: Update) -> str:
        """Call OpenAI with tool support."""
        # Build OpenAI-format messages from shared conversation store
        history = self.conversation_store.get_recent("jason", "telegram", limit=20)
        messages = [{"role": "system", "content": _build_telegram_system_prompt(self.conversation_store)}]
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

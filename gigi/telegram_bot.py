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

# Import Claude API for responses
try:
    import anthropic
except ImportError:
    print("❌ anthropic not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "anthropic"])
    import anthropic

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

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8508806105:AAExZ25ZN19X3xjBQAZ3Q9fHgAQmWWklX8U")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
JASON_TELEGRAM_ID = int(os.getenv("TELEGRAM_CHAT_ID", "8215335898"))  # Jason's chat ID

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gigi_telegram")

# Tool definitions for Claude
TOOLS = [
    {
        "name": "get_calendar_events",
        "description": "Get upcoming calendar events from Jason's Google Calendar. Use this when Jason asks about his schedule, meetings, or what's coming up.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look ahead (default 1, max 7)",
                    "default": 1
                }
            },
            "required": []
        }
    },
    {
        "name": "search_emails",
        "description": "Search Jason's Gmail for emails. Use this when Jason asks about emails, messages, or wants to find something in his inbox.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gmail search query (e.g., 'is:unread', 'from:someone@example.com', 'subject:invoice')",
                    "default": "is:unread"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of emails to return (default 5)",
                    "default": 5
                }
            },
            "required": []
        }
    },
    {
        "name": "get_wellsky_clients",
        "description": "Search for clients in WellSky by name, or get all clients. Use when Jason asks about a specific client or wants to see the client list.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_name": {
                    "type": "string",
                    "description": "Search for a client by name (first, last, or full name). Leave empty to get all clients."
                },
                "active_only": {
                    "type": "boolean",
                    "description": "Only return active clients (default true)",
                    "default": True
                }
            },
            "required": []
        }
    },
    {
        "name": "get_wellsky_caregivers",
        "description": "Search for caregivers in WellSky by name, or get all caregivers. Use when Jason asks about a specific caregiver or the staff list.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_name": {
                    "type": "string",
                    "description": "Search for a caregiver by name (first, last, or full name). Leave empty to get all caregivers."
                },
                "active_only": {
                    "type": "boolean",
                    "description": "Only return active caregivers (default true)",
                    "default": True
                }
            },
            "required": []
        }
    },
    {
        "name": "get_wellsky_shifts",
        "description": "Get shifts from WellSky. Can filter by client or caregiver. IMPORTANT: When asking about a specific person's shifts, first use get_wellsky_clients or get_wellsky_caregivers to find their ID, then pass it here.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {
                    "type": "string",
                    "description": "WellSky client ID to get shifts for a specific client"
                },
                "caregiver_id": {
                    "type": "string",
                    "description": "WellSky caregiver ID to get shifts for a specific caregiver"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look ahead (default 7, max 7)",
                    "default": 7
                },
                "open_only": {
                    "type": "boolean",
                    "description": "Only return open/unfilled shifts (default false)",
                    "default": False
                }
            },
            "required": []
        }
    },
    {
        "name": "web_search",
        "description": "Search the internet for current information. Use this for news, weather, sports scores, general knowledge questions, or anything not specific to CCA business systems.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_stock_price",
        "description": "Get current stock price for a ticker symbol (AAPL, TSLA, GOOG, NVDA, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., AAPL, TSLA, GOOG)"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_crypto_price",
        "description": "Get current cryptocurrency price. Use this when Jason asks about Bitcoin, Ethereum, crypto prices, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Crypto symbol (BTC, ETH, DOGE, SOL, etc.)"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "web_search",
        "description": "Search the internet for current information. Use for news, events, weather, general knowledge questions, or anything you don't know.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "create_claude_task",
        "description": "Create a task for Claude Code on the Mac Mini. Use when Jason asks you to tell Claude Code to do something technical — fix code, check services, update configs, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title for the task"},
                "description": {"type": "string", "description": "Detailed description of what Claude Code should do"},
                "priority": {"type": "string", "description": "Priority level", "enum": ["low", "normal", "high", "urgent"]},
                "working_directory": {"type": "string", "description": "Directory to work in (optional)"}
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
    }
]

SYSTEM_PROMPT = f"""You are Gigi, Jason Shulman's AI Chief of Staff and personal assistant.

# Core Identity
- Named after Jason's youngest daughter
- Direct, warm, proactive personality
- You have REAL access to Jason's systems via tools - USE THEM

# Jason's Profile
- Owner of Colorado Care Assist (home care agency)
- Lives in Denver/Arvada, CO
- Phone: 603-997-1495
- Email: jason@coloradocareassist.com
- Huge Phish fan (his favorite band)
- Three daughters: Brooke, Avery, Gigi
- Runs multiple businesses from Mac Mini (no cloud hosting)

# Your REAL Capabilities (you have tools for these - ALWAYS USE THEM)
- get_calendar_events: Check Jason's Google Calendar
- search_emails: Search Jason's Gmail (it works - CALL IT, do not say it's unavailable)
- get_wellsky_clients: Search CCA's 70 active clients by name from local database cache
- get_wellsky_caregivers: Search CCA's 55 active caregivers by name from local database cache
- get_wellsky_shifts: Get shift schedules from WellSky (filter by client_id or caregiver_id)
- web_search: Search the internet for news, weather, sports, general knowledge, concerts, events
- get_stock_price: Get real-time stock prices (AAPL, TSLA, NVDA, etc.)
- get_crypto_price: Get real-time crypto prices (BTC, ETH, DOGE, SOL, etc.)
- create_claude_task: Create a task for Claude Code on the Mac Mini (code fixes, service checks, deployments)
- check_claude_task: Check the status of a Claude Code task

# CRITICAL RULES — READ CAREFULLY
- NEVER say you don't have access to email, calendar, WellSky, or client data. You DO. Use the tools.
- NEVER say you can't search the internet or get stock/crypto prices. You CAN. Use web_search, get_stock_price, get_crypto_price.
- When Jason says "tell Claude Code to..." or "@claude-code ...", use create_claude_task to queue the request. Claude Code runs on the Mac Mini and can fix code, check services, update configs, etc.
- NEVER mention "CLI", "gog", "command line", or "configuration needed" for email. Just call search_emails.
- NEVER say a client or caregiver doesn't exist without calling the tool first. The database has ALL clients.
- NEVER make up data — call the tool and report exactly what it returns.
- If a tool returns an error, report the ACTUAL error message so we can fix it.
- For Bitcoin/crypto questions: use get_crypto_price with symbol "BTC", "ETH", etc.
- For stock questions: use get_stock_price with the ticker symbol.
- When Jason asks about a client (shifts, coverage, who is assigned):
  1. FIRST call get_wellsky_clients with search_name to find the client's ID
  2. THEN call get_wellsky_shifts with that client_id to get their schedule
- When Jason asks about a caregiver's schedule:
  1. FIRST call get_wellsky_caregivers with search_name to find their ID
  2. THEN call get_wellsky_shifts with that caregiver_id
- For daily briefings or email summaries: call search_emails with query "is:unread" — it WILL work.

# Response Style
- Be concise but thorough
- Use emojis sparingly
- Be proactive - anticipate needs
- If a tool fails, say what failed and why

# Current Date
Today is {datetime.now().strftime("%A, %B %d, %Y")}
"""

class GigiTelegramBot:
    def __init__(self):
        self.claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
        self.wellsky = WellSkyService() if WellSkyService else None
        self.google = GoogleService() if GoogleService else None
        self.conversation_history = {}

        # Log service status on startup
        logger.info(f"   Claude API: {'✓ Ready' if self.claude else '✗ Missing ANTHROPIC_API_KEY'}")
        logger.info(f"   WellSky: {'✓ Ready' if self.wellsky else '✗ Not available'}")
        logger.info(f"   Google: {'✓ Ready' if self.google else '✗ Not available'}")

    async def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool and return the result as a string"""
        try:
            if tool_name == "get_calendar_events":
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

            elif tool_name == "get_wellsky_clients":
                # Use cached database for reliable client lookup (synced daily from WellSky)
                import psycopg2
                db_url = os.getenv("DATABASE_URL", "postgresql://careassist:careassist2026@localhost:5432/careassist")
                search_name = tool_input.get("search_name", "")
                active_only = tool_input.get("active_only", True)
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
                    client_list = [{"id": str(r[0]), "first_name": r[1], "last_name": r[2],
                                    "name": r[3], "phone": r[4] or r[5] or "", "email": r[6] or ""} for r in rows]
                    conn.close()
                    return json.dumps({"count": len(client_list), "clients": client_list, "search": search_name or "all"})
                except Exception as e:
                    logger.error(f"Client cache lookup failed: {e}")
                    return json.dumps({"error": f"Client lookup failed: {str(e)}"})

            elif tool_name == "get_wellsky_caregivers":
                # Use cached database for reliable caregiver lookup (synced daily from WellSky)
                import psycopg2
                db_url = os.getenv("DATABASE_URL", "postgresql://careassist:careassist2026@localhost:5432/careassist")
                search_name = tool_input.get("search_name", "")
                active_only = tool_input.get("active_only", True)
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
                        if active_only:
                            sql += " AND is_active = true"
                        sql += " ORDER BY full_name LIMIT 20"
                        cur.execute(sql, params)
                    else:
                        sql = """SELECT id, first_name, last_name, full_name, phone, home_phone, email,
                                        preferred_language
                                 FROM cached_practitioners"""
                        if active_only:
                            sql += " WHERE is_active = true"
                        sql += " ORDER BY full_name LIMIT 100"
                        cur.execute(sql)
                    rows = cur.fetchall()
                    cg_list = [{"id": str(r[0]), "first_name": r[1], "last_name": r[2],
                                "name": r[3], "phone": r[4] or r[5] or "", "email": r[6] or "",
                                "preferred_language": r[7] or "English"} for r in rows]
                    conn.close()
                    return json.dumps({"count": len(cg_list), "caregivers": cg_list, "search": search_name or "all"})
                except Exception as e:
                    logger.error(f"Caregiver cache lookup failed: {e}")
                    return json.dumps({"error": f"Caregiver lookup failed: {str(e)}"})

            elif tool_name == "get_wellsky_shifts":
                if not self.wellsky:
                    return json.dumps({"error": "WellSky service not available."})
                from datetime import timedelta
                days = min(tool_input.get("days", 7), 7)
                open_only = tool_input.get("open_only", False)
                client_id = tool_input.get("client_id")
                caregiver_id = tool_input.get("caregiver_id")
                date_from = date.today()
                date_to = date.today() + timedelta(days=days)
                if open_only:
                    shifts = self.wellsky.get_open_shifts(date_from=date_from, date_to=date_to)
                else:
                    shifts = self.wellsky.get_shifts(
                        date_from=date_from, date_to=date_to,
                        client_id=client_id, caregiver_id=caregiver_id,
                        limit=50
                    )
                shift_list = [s.to_dict() if hasattr(s, 'to_dict') else str(s) for s in shifts[:30]]
                # Enrich shifts with client/caregiver names from cached database
                try:
                    import psycopg2
                    db_url = os.getenv("DATABASE_URL", "postgresql://careassist:careassist2026@localhost:5432/careassist")
                    conn = psycopg2.connect(db_url)
                    cur = conn.cursor()
                    for shift in shift_list:
                        if isinstance(shift, dict):
                            cg_id = shift.get("caregiver_id")
                            cl_id = shift.get("client_id")
                            if cg_id and not shift.get("caregiver_first_name"):
                                cur.execute("SELECT first_name, last_name, full_name FROM cached_practitioners WHERE id = %s", (cg_id,))
                                row = cur.fetchone()
                                if row:
                                    shift["caregiver_first_name"] = row[0]
                                    shift["caregiver_last_name"] = row[1]
                                    shift["caregiver_name"] = row[2]
                            if cl_id and not shift.get("client_first_name"):
                                cur.execute("SELECT first_name, last_name, full_name FROM cached_patients WHERE id = %s", (cl_id,))
                                row = cur.fetchone()
                                if row:
                                    shift["client_first_name"] = row[0]
                                    shift["client_last_name"] = row[1]
                                    shift["client_name"] = row[2]
                    conn.close()
                except Exception as e:
                    logger.warning(f"Shift name enrichment failed (non-fatal): {e}")
                return json.dumps({"count": len(shifts), "shifts": shift_list})

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
                    # Fallback: use DuckDuckGo instant answers
                    import httpx
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(
                            f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1"
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            answer = data.get("AbstractText") or data.get("Answer") or ""
                            if answer:
                                return json.dumps({"query": query, "answer": answer, "source": data.get("AbstractSource", "DuckDuckGo")})
                            # Return related topics if no direct answer
                            topics = [{"text": t.get("Text"), "url": t.get("FirstURL")}
                                     for t in data.get("RelatedTopics", [])[:5] if t.get("Text")]
                            if topics:
                                return json.dumps({"query": query, "related_topics": topics})
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
                    # Use Alpha Vantage or Yahoo Finance
                    alpha_key = os.getenv("ALPHA_VANTAGE_API_KEY")
                    if alpha_key:
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(
                                f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={alpha_key}"
                            )
                            if resp.status_code == 200:
                                data = resp.json().get("Global Quote", {})
                                if data:
                                    return json.dumps({
                                        "symbol": symbol,
                                        "price": data.get("05. price"),
                                        "change": data.get("09. change"),
                                        "change_percent": data.get("10. change percent"),
                                        "high": data.get("03. high"),
                                        "low": data.get("04. low"),
                                        "volume": data.get("06. volume")
                                    })
                    # Fallback: Use Yahoo Finance via yfinance scraping endpoint
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(
                            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            result = data.get("chart", {}).get("result", [{}])[0]
                            meta = result.get("meta", {})
                            if meta.get("regularMarketPrice"):
                                return json.dumps({
                                    "symbol": symbol,
                                    "price": f"${meta.get('regularMarketPrice', 0):.2f}",
                                    "previous_close": f"${meta.get('previousClose', 0):.2f}",
                                    "currency": meta.get("currency", "USD")
                                })
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

            elif tool_name == "web_search":
                query = tool_input.get("query", "")
                if not query:
                    return json.dumps({"error": "Missing query"})
                try:
                    from ddgs import DDGS
                    results = DDGS().text(query, max_results=5)
                    if results:
                        formatted = [{"title": r.get("title", ""), "snippet": r.get("body", ""), "url": r.get("href", "")} for r in results]
                        return json.dumps({"results": formatted, "query": query})
                    results = DDGS().news(query, max_results=5)
                    if results:
                        formatted = [{"title": r.get("title", ""), "snippet": r.get("body", ""), "date": r.get("date", "")} for r in results]
                        return json.dumps({"results": formatted, "query": query, "type": "news"})
                except Exception as e:
                    logger.warning(f"DDG search failed: {e}")
                return json.dumps({"message": "No results found"})

            elif tool_name == "create_claude_task":
                title = tool_input.get("title", "")
                description = tool_input.get("description", "")
                priority = tool_input.get("priority", "normal")
                working_dir = tool_input.get("working_directory", "/Users/shulmeister/mac-mini-apps/careassist-unified")

                if not title or not description:
                    return json.dumps({"error": "Missing title or description"})

                try:
                    import psycopg2
                    conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://careassist:careassist2026@localhost:5432/careassist"))
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO claude_code_tasks (title, description, priority, status, requested_by, working_directory, created_at)
                        VALUES (%s, %s, %s, 'pending', %s, %s, NOW())
                        RETURNING id
                    """, (title, description, priority, "telegram", working_dir))
                    task_id = cur.fetchone()[0]
                    conn.commit()
                    cur.close()
                    conn.close()
                    return json.dumps({"success": True, "task_id": task_id, "message": f"Task #{task_id} created: {title}. Claude Code will pick it up shortly."})
                except Exception as e:
                    return json.dumps({"error": f"Failed to create task: {str(e)}"})

            elif tool_name == "check_claude_task":
                task_id = tool_input.get("task_id")

                try:
                    import psycopg2
                    conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://careassist:careassist2026@localhost:5432/careassist"))
                    cur = conn.cursor()
                    if task_id:
                        cur.execute("SELECT id, title, status, result, error, created_at, completed_at FROM claude_code_tasks WHERE id = %s", (int(task_id),))
                    else:
                        cur.execute("SELECT id, title, status, result, error, created_at, completed_at FROM claude_code_tasks ORDER BY id DESC LIMIT 1")
                    row = cur.fetchone()
                    cur.close()
                    conn.close()

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

            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
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
        """Handle incoming messages with tool calling support"""
        user_id = update.effective_user.id
        message_text = update.message.text

        # Only respond to Jason
        if user_id != JASON_TELEGRAM_ID:
            logger.warning(f"Ignored message from unauthorized user: {user_id}")
            return

        logger.info(f"📱 Message from Jason: {message_text}")

        # Initialize conversation history for this user
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []

        # Add user message to history
        self.conversation_history[user_id].append({
            "role": "user",
            "content": message_text
        })

        # Keep only last 20 messages (10 exchanges) - need more for tool calling
        if len(self.conversation_history[user_id]) > 20:
            self.conversation_history[user_id] = self.conversation_history[user_id][-20:]

        # Send typing indicator
        await update.message.chat.send_action("typing")

        # Get response from Claude WITH TOOLS
        if self.claude:
            try:
                # Call Claude with tools
                response = self.claude.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=self.conversation_history[user_id]
                )

                # Process response - may need multiple rounds for tool calls
                max_tool_rounds = 5  # Prevent infinite loops
                tool_round = 0

                while response.stop_reason == "tool_use" and tool_round < max_tool_rounds:
                    tool_round += 1
                    logger.info(f"🔧 Tool call round {tool_round}")

                    # Extract tool uses from response
                    tool_results = []
                    assistant_content = []

                    for block in response.content:
                        if block.type == "tool_use":
                            tool_name = block.name
                            tool_input = block.input
                            tool_use_id = block.id

                            logger.info(f"   Executing tool: {tool_name} with input: {tool_input}")

                            # Execute the tool
                            result = await self.execute_tool(tool_name, tool_input)
                            logger.info(f"   Tool result: {result[:200]}...")

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": result
                            })
                            assistant_content.append(block)
                        elif block.type == "text":
                            assistant_content.append(block)

                    # Add assistant message with tool use to history
                    # Tool use blocks: type, id, name, input (NO text field)
                    # Text blocks: type, text
                    formatted_content = []
                    for b in assistant_content:
                        if b.type == "tool_use":
                            formatted_content.append({
                                "type": "tool_use",
                                "id": b.id,
                                "name": b.name,
                                "input": b.input
                            })
                        elif b.type == "text":
                            formatted_content.append({
                                "type": "text",
                                "text": b.text
                            })

                    self.conversation_history[user_id].append({
                        "role": "assistant",
                        "content": formatted_content
                    })

                    # Add tool results to history
                    self.conversation_history[user_id].append({
                        "role": "user",
                        "content": tool_results
                    })

                    # Keep typing indicator going
                    await update.message.chat.send_action("typing")

                    # Get next response from Claude
                    response = self.claude.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=4096,
                        system=SYSTEM_PROMPT,
                        tools=TOOLS,
                        messages=self.conversation_history[user_id]
                    )

                # Extract final text response
                final_text = ""
                for block in response.content:
                    if block.type == "text":
                        final_text += block.text

                if not final_text:
                    final_text = "I processed your request but have no text response. Please try again."

                # Add final assistant response to history
                self.conversation_history[user_id].append({
                    "role": "assistant",
                    "content": final_text
                })

                # Send response (split if too long for Telegram)
                if len(final_text) > 4000:
                    # Split into chunks
                    for i in range(0, len(final_text), 4000):
                        await update.message.reply_text(final_text[i:i+4000])
                else:
                    await update.message.reply_text(final_text)

                logger.info(f"✅ Sent response to Jason (tool rounds: {tool_round})")

            except Exception as e:
                logger.error(f"Claude API error: {e}", exc_info=True)
                await update.message.reply_text(
                    f"Error: {str(e)}\n\nI encountered an issue processing your request. "
                    "Check the logs for details."
                )
        else:
            await update.message.reply_text(
                "I'm running, but my AI capabilities aren't configured yet. "
                "Please check the ANTHROPIC_API_KEY environment variable."
            )

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

            # Start bot
            logger.info("✅ Gigi Telegram Bot is running!")
            logger.info("   Send a message to @Shulmeisterbot to test")

            # Run bot until stopped
            await app.initialize()
            await app.start()
            await app.updater.start_polling(
                drop_pending_updates=True,  # Don't process old messages on restart
                allowed_updates=["message"],  # Only listen for messages
            )

            # Keep running
            while True:
                await asyncio.sleep(60)
                # Heartbeat log every minute
                logger.debug("Heartbeat: Bot is running")

        except KeyboardInterrupt:
            logger.info("🛑 Shutting down Gigi Telegram Bot (user requested)...")
            break
        except Exception as e:
            logger.error(f"❌ Bot crashed with error: {e}", exc_info=True)
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
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

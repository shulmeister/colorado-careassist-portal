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

import os
import sys
import json
import asyncio
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any, List

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
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

# Claude client
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

# Same tools as Telegram Gigi
TOOLS = [
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
        "description": "Get shifts from WellSky, optionally filtered by client or caregiver.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string", "description": "Filter by client ID"},
                "caregiver_id": {"type": "string", "description": "Filter by caregiver ID"},
                "days": {"type": "integer", "description": "Days to look ahead", "default": 7}
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
        "name": "transfer_call",
        "description": "Transfer the call to another number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Who to transfer to: 'jason', 'office', or a phone number"}
            },
            "required": ["destination"]
        }
    }
]

# System prompt - same personality as Telegram, but adapted for voice
SYSTEM_PROMPT = f"""You are Gigi, the AI assistant for Colorado Care Assist, a home care agency.

# Voice Conversation Style
- Keep responses SHORT and conversational - this is a phone call, not text
- Use natural speech patterns, not bullet points
- One thought at a time - don't overwhelm with information
- If you need to list things, say "first... second..." not numbered lists
- Pause points: use periods to create natural breaks

# Who You're Talking To
- Caregivers: scheduling, call-outs, shift questions
- Clients: service questions, complaints, scheduling
- Family members: concerns about loved ones
- Prospective clients/caregivers: inquiries

# Your Capabilities (use tools when needed)
- Look up clients, caregivers, and shifts in WellSky
- Check Jason's calendar and email
- Send texts, emails, and team messages
- Search the internet
- Get stock and crypto prices
- Transfer calls to Jason or the office

# Key People
- Jason Shulman: Owner (transfer to him for escalations)
- Cynthia Pointe: Care Manager (scheduling issues)
- Israt Jahan: Scheduler

# Rules
- NEVER say you can't do something without trying the tool first
- If a tool fails, say what happened simply
- For call-outs: get the caregiver's name and which shift, then report it
- Always be warm but efficient - people are busy

# Current Date/Time
Today is {datetime.now().strftime("%A, %B %d, %Y")}
"""


async def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool and return the result - same logic as Telegram bot"""
    import psycopg2
    import httpx

    db_url = os.getenv("DATABASE_URL", "postgresql://careassist:careassist2026@localhost:5432/careassist")

    try:
        if tool_name == "get_calendar_events":
            if not GOOGLE_AVAILABLE or not google_service:
                return json.dumps({"error": "Google service not available"})
            days = tool_input.get("days", 1)
            events = google_service.get_calendar_events(days=min(days, 7))
            return json.dumps({"events": events or []})

        elif tool_name == "search_emails":
            if not GOOGLE_AVAILABLE or not google_service:
                return json.dumps({"error": "Google service not available"})
            query = tool_input.get("query", "is:unread")
            max_results = tool_input.get("max_results", 5)
            emails = google_service.search_emails(query=query, max_results=max_results)
            return json.dumps({"emails": emails or []})

        elif tool_name == "send_email":
            if not GOOGLE_AVAILABLE or not google_service:
                return json.dumps({"error": "Google service not available"})
            to = tool_input.get("to", "")
            subject = tool_input.get("subject", "")
            body = tool_input.get("body", "")
            if not all([to, subject, body]):
                return json.dumps({"error": "Missing to, subject, or body"})
            success = google_service.send_email(to=to, subject=subject, body=body)
            return json.dumps({"success": success})

        elif tool_name == "get_wellsky_clients":
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            search_name = tool_input.get("search_name", "")
            active_only = tool_input.get("active_only", True)

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

            cur.execute(sql, params)
            rows = cur.fetchall()
            conn.close()

            clients = [{"id": str(r[0]), "first_name": r[1], "last_name": r[2], "name": r[3], "phone": r[4] or ""} for r in rows]
            return json.dumps({"clients": clients, "count": len(clients)})

        elif tool_name == "get_wellsky_caregivers":
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            search_name = tool_input.get("search_name", "")
            active_only = tool_input.get("active_only", True)

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

            cur.execute(sql, params)
            rows = cur.fetchall()
            conn.close()

            caregivers = [{"id": str(r[0]), "first_name": r[1], "last_name": r[2], "name": r[3], "phone": r[4] or ""} for r in rows]
            return json.dumps({"caregivers": caregivers, "count": len(caregivers)})

        elif tool_name == "get_wellsky_shifts":
            if not WELLSKY_AVAILABLE or not wellsky:
                return json.dumps({"error": "WellSky not available"})

            from datetime import timedelta
            days = min(tool_input.get("days", 7), 7)
            client_id = tool_input.get("client_id")
            caregiver_id = tool_input.get("caregiver_id")

            shifts = wellsky.get_shifts(
                date_from=date.today(),
                date_to=date.today() + timedelta(days=days),
                client_id=client_id,
                caregiver_id=caregiver_id,
                limit=30
            )

            shift_list = []
            for s in shifts[:20]:
                if hasattr(s, 'to_dict'):
                    shift_list.append(s.to_dict())
                else:
                    shift_list.append(str(s))

            return json.dumps({"shifts": shift_list, "count": len(shifts)})

        elif tool_name == "send_sms":
            phone = tool_input.get("phone_number", "")
            message = tool_input.get("message", "")
            if not phone or not message:
                return json.dumps({"error": "Missing phone_number or message"})

            try:
                from sales.shift_filling.sms_service import SMSService
                sms = SMSService()
                success, result = sms.send_sms(to_phone=phone, message=message)
                return json.dumps({"success": success, "result": result})
            except Exception as e:
                return json.dumps({"error": str(e)})

        elif tool_name == "send_team_message":
            message = tool_input.get("message", "")
            if not message:
                return json.dumps({"error": "Missing message"})

            try:
                from services.ringcentral_messaging_service import ringcentral_messaging_service
                result = ringcentral_messaging_service.send_message_to_chat("New Scheduling", message)
                return json.dumps(result)
            except Exception as e:
                return json.dumps({"error": str(e)})

        elif tool_name == "web_search":
            query = tool_input.get("query", "")
            if not query:
                return json.dumps({"error": "Missing query"})

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1")
                if resp.status_code == 200:
                    data = resp.json()
                    answer = data.get("AbstractText") or data.get("Answer")
                    if answer:
                        return json.dumps({"answer": answer})
                    topics = [t.get("Text") for t in data.get("RelatedTopics", [])[:3] if t.get("Text")]
                    return json.dumps({"related": topics})
            return json.dumps({"message": "No results found"})

        elif tool_name == "get_stock_price":
            symbol = tool_input.get("symbol", "").upper()
            if not symbol:
                return json.dumps({"error": "Missing symbol"})

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d")
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

            async with httpx.AsyncClient() as client:
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
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()

            # Check staff, caregivers, clients, family
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
                    conn.close()
                    return json.dumps({"found": True, "name": row[0], "full_name": row[1], "type": type_name})

            conn.close()
            return json.dumps({"found": False})

        elif tool_name == "report_call_out":
            caregiver = tool_input.get("caregiver_name", "")
            reason = tool_input.get("reason", "not feeling well")
            shift_date = tool_input.get("shift_date", date.today().isoformat())

            # Log to team chat
            try:
                from services.ringcentral_messaging_service import ringcentral_messaging_service
                msg = f"📞 CALL-OUT: {caregiver} called out for {shift_date}. Reason: {reason}"
                ringcentral_messaging_service.send_message_to_chat("New Scheduling", msg)
                return json.dumps({"success": True, "message": f"Call-out reported for {caregiver}"})
            except Exception as e:
                return json.dumps({"error": str(e)})

        elif tool_name == "transfer_call":
            dest = tool_input.get("destination", "").lower()
            if dest == "jason":
                return json.dumps({"transfer_number": "+16039971495"})
            elif dest == "office":
                return json.dumps({"transfer_number": "+13037571777"})
            else:
                return json.dumps({"transfer_number": dest})

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except Exception as e:
        logger.error(f"Tool {tool_name} error: {e}")
        return json.dumps({"error": str(e)})


async def generate_response(transcript: List[Dict], call_info: Dict = None) -> tuple[str, Optional[str]]:
    """
    Generate a response using Claude, with tool support.
    Returns (response_text, transfer_number or None)
    """
    if not claude:
        return "I'm having trouble connecting right now. Please try again.", None

    # Convert Retell transcript format to Claude messages
    messages = []
    for turn in transcript:
        role = "user" if turn.get("role") == "user" else "assistant"
        content = turn.get("content", "")
        if content:
            messages.append({"role": role, "content": content})

    # If no messages yet, generate greeting based on caller info
    if not messages or (len(messages) == 1 and messages[0]["role"] == "assistant"):
        # Look up caller if we have their number
        if call_info and call_info.get("from_number"):
            caller_result = await execute_tool("lookup_caller", {"phone_number": call_info["from_number"]})
            caller_data = json.loads(caller_result)
            if caller_data.get("found"):
                name = caller_data.get("name", "")
                return f"Hi {name}, this is Gigi with Colorado Care Assist. How can I help you?", None
        return "Hi, this is Gigi with Colorado Care Assist. How can I help you?", None

    transfer_number = None

    try:
        # Call Claude with tools
        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,  # Keep responses short for voice
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

        # Process response, handling any tool calls
        while response.stop_reason == "tool_use":
            # Execute tools
            tool_results = []
            assistant_content = response.content

            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    logger.info(f"Executing tool: {tool_name}")
                    result = await execute_tool(tool_name, tool_input)

                    # Check for transfer
                    if tool_name == "transfer_call":
                        result_data = json.loads(result)
                        if result_data.get("transfer_number"):
                            transfer_number = result_data["transfer_number"]

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # Continue conversation with tool results
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

            response = claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            )

        # Extract final text response
        for block in response.content:
            if hasattr(block, "text"):
                return block.text, transfer_number

        return "I'm here. How can I help?", transfer_number

    except Exception as e:
        logger.error(f"Claude error: {e}")
        return "I'm having a moment. Could you repeat that?", None


class VoiceBrainHandler:
    """Handles a single WebSocket connection from Retell"""

    def __init__(self, websocket: WebSocket, call_id: str):
        self.websocket = websocket
        self.call_id = call_id
        self.call_info = {}
        self.current_response_id = 0

    async def handle(self):
        """Main handler loop"""
        await self.websocket.accept()
        logger.info(f"Call {self.call_id} connected")

        # Send config
        await self.send({
            "response_type": "config",
            "config": {
                "auto_reconnect": True,
                "call_details": True
            }
        })

        try:
            while True:
                data = await self.websocket.receive_text()
                message = json.loads(data)
                await self.handle_message(message)

        except WebSocketDisconnect:
            logger.info(f"Call {self.call_id} disconnected")
        except Exception as e:
            logger.error(f"Call {self.call_id} error: {e}")

    async def send(self, data: dict):
        """Send JSON message to Retell"""
        await self.websocket.send_text(json.dumps(data))

    async def handle_message(self, message: dict):
        """Handle incoming message from Retell"""
        interaction_type = message.get("interaction_type")

        if interaction_type == "ping_pong":
            await self.send({
                "response_type": "ping_pong",
                "timestamp": message.get("timestamp")
            })

        elif interaction_type == "call_details":
            self.call_info = message.get("call", {})
            logger.info(f"Call details: from={self.call_info.get('from_number')}")

            # Generate and send initial greeting
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

            # Generate response
            response_text, transfer_number = await generate_response(transcript, self.call_info)

            # Send response
            response_data = {
                "response_type": "response",
                "response_id": response_id,
                "content": response_text,
                "content_complete": True
            }

            if transfer_number:
                response_data["transfer_number"] = transfer_number

            await self.send(response_data)

        elif interaction_type == "reminder_required":
            response_id = message.get("response_id", 0)
            await self.send({
                "response_type": "response",
                "response_id": response_id,
                "content": "Are you still there?",
                "content_complete": True
            })

        elif interaction_type == "update_only":
            # Just a transcript update, no response needed
            pass


# FastAPI endpoint - to be mounted in the main app
async def voice_brain_websocket(websocket: WebSocket, call_id: str):
    """WebSocket endpoint for Retell custom LLM"""
    handler = VoiceBrainHandler(websocket, call_id)
    await handler.handle()

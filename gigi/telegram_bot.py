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
        "description": "Get list of clients from WellSky. Use when Jason asks about clients, patients, or who we're serving.",
        "input_schema": {
            "type": "object",
            "properties": {
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
        "description": "Get list of caregivers from WellSky. Use when Jason asks about caregivers, staff, or employees.",
        "input_schema": {
            "type": "object",
            "properties": {
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
        "description": "Get shifts from WellSky. Use when Jason asks about shifts, schedules, or appointments.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look ahead (default 7)",
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

# Your REAL Capabilities (you have tools for these - USE THEM)
- get_calendar_events: Check Jason's Google Calendar
- search_emails: Search Jason's Gmail
- get_wellsky_clients: Get client list from WellSky
- get_wellsky_caregivers: Get caregiver list from WellSky
- get_wellsky_shifts: Get shift schedules from WellSky

# IMPORTANT
- When Jason asks about calendar, email, clients, caregivers, or shifts - ALWAYS use the appropriate tool
- Do NOT say you don't have access - you DO have access via tools
- Do NOT make up data - call the tool and report what it returns
- If a tool returns an error, report the actual error so we can fix it

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

    def execute_tool(self, tool_name: str, tool_input: dict) -> str:
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
                if not self.wellsky:
                    return json.dumps({"error": "WellSky service not available."})
                # Import enum here to avoid circular imports
                from services.wellsky_service import ClientStatus
                active_only = tool_input.get("active_only", True)
                status = ClientStatus.ACTIVE if active_only else None
                clients = self.wellsky.get_clients(status=status, limit=50)
                client_list = [c.to_dict() if hasattr(c, 'to_dict') else str(c) for c in clients[:20]]
                return json.dumps({"count": len(clients), "clients": client_list})

            elif tool_name == "get_wellsky_caregivers":
                if not self.wellsky:
                    return json.dumps({"error": "WellSky service not available."})
                from services.wellsky_service import CaregiverStatus
                active_only = tool_input.get("active_only", True)
                status = CaregiverStatus.ACTIVE if active_only else None
                caregivers = self.wellsky.get_caregivers(status=status, limit=50)
                cg_list = [c.to_dict() if hasattr(c, 'to_dict') else str(c) for c in caregivers[:20]]
                return json.dumps({"count": len(caregivers), "caregivers": cg_list})

            elif tool_name == "get_wellsky_shifts":
                if not self.wellsky:
                    return json.dumps({"error": "WellSky service not available."})
                from datetime import timedelta
                days = tool_input.get("days", 7)
                open_only = tool_input.get("open_only", False)
                date_from = date.today()
                date_to = date.today() + timedelta(days=days)
                if open_only:
                    shifts = self.wellsky.get_open_shifts(date_from=date_from, date_to=date_to)
                else:
                    shifts = self.wellsky.get_shifts(date_from=date_from, date_to=date_to, limit=50)
                shift_list = [s.to_dict() if hasattr(s, 'to_dict') else str(s) for s in shifts[:30]]
                return json.dumps({"count": len(shifts), "shifts": shift_list})

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
                            result = self.execute_tool(tool_name, tool_input)
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
                    self.conversation_history[user_id].append({
                        "role": "assistant",
                        "content": [{"type": b.type, "id": getattr(b, 'id', None), "name": getattr(b, 'name', None), "input": getattr(b, 'input', None), "text": getattr(b, 'text', None)} if b.type == "tool_use" else {"type": "text", "text": b.text} for b in assistant_content]
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
    """Run the bot"""
    logger.info("🤖 Starting Gigi Telegram Bot on Mac Mini...")
    logger.info(f"   Bot Token: {TELEGRAM_BOT_TOKEN[:20]}...")
    logger.info(f"   Jason's Chat ID: {JASON_TELEGRAM_ID}")

    # Create bot instance
    gigi = GigiTelegramBot()

    # Create application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

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
    await app.updater.start_polling()

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down Gigi Telegram Bot...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())

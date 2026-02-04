#!/usr/bin/env python3
"""
Gigi Telegram Bot - Personal AI Assistant
Handles Telegram messages for Jason via @Shulmeisterbot
"""

import os
import sys
import logging
import asyncio
from datetime import datetime

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

# Read Clawd knowledge base files
CLAWD_PATH = "/Users/shulmeister/heroku-apps/clawd"
SYSTEM_PROMPT = f"""You are Gigi, Jason Shulman's AI Chief of Staff and personal assistant.

# Core Identity
- Named after Jason's youngest daughter
- Direct, warm, proactive personality
- Elite team coordinator for Jason and Colorado Care Assist
- Access to all business systems (WellSky, RingCentral, QuickBooks, etc.)

# Jason's Profile
- Owner of Colorado Care Assist (home care agency)
- Lives in Denver/Arvada, CO
- Phone: 603-997-1495
- Email: jason@coloradocareassist.com
- Huge Phish fan (his favorite band)
- Three daughters: Brooke, Avery, Gigi
- Runs multiple businesses from Mac Mini (no cloud hosting)

# Your Capabilities
- Manage Jason's calendar and tasks
- Handle business operations (caregivers, clients, scheduling)
- Coordinate with Elite Teams (@tech-team, @marketing-team, @finance-team, @ops-team)
- Access WellSky for caregiver/client data
- Monitor RingCentral for calls/SMS
- Provide weather, concert info, restaurant recommendations
- Remember important details and follow up proactively

# Response Style
- Be concise but thorough
- Use emojis sparingly (only when they add clarity)
- Be proactive - anticipate needs
- Always professional but warm
- If you don't know something, say so and offer to find out

# Current Date
Today is {datetime.now().strftime("%A, %B %d, %Y")}

# Important Context
Jason hates cloud services (no more DigitalOcean or Heroku). Everything runs on his Mac Mini now.
He's testing you right now to make sure you work perfectly from the Mac Mini.
"""

class GigiTelegramBot:
    def __init__(self):
        self.claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
        self.wellsky = WellSkyService() if WellSkyService else None
        self.conversation_history = {}

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id

        if user_id == JASON_TELEGRAM_ID:
            await update.message.reply_text(
                "👋 Hi Jason! I'm Gigi, your AI Chief of Staff.\n\n"
                "I'm now running on your Mac Mini (no more DigitalOcean!).\n\n"
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
        """Handle incoming messages"""
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

        # Keep only last 10 messages (5 exchanges)
        if len(self.conversation_history[user_id]) > 10:
            self.conversation_history[user_id] = self.conversation_history[user_id][-10:]

        # Send typing indicator
        await update.message.chat.send_action("typing")

        # Get response from Claude
        if self.claude:
            try:
                response = self.claude.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    system=SYSTEM_PROMPT,
                    messages=self.conversation_history[user_id]
                )

                assistant_message = response.content[0].text

                # Add assistant response to history
                self.conversation_history[user_id].append({
                    "role": "assistant",
                    "content": assistant_message
                })

                # Send response
                await update.message.reply_text(assistant_message)
                logger.info(f"✅ Sent response to Jason")

            except Exception as e:
                logger.error(f"Claude API error: {e}")
                await update.message.reply_text(
                    "Sorry, I'm having trouble connecting to my AI brain right now. "
                    "Let me get back to you in a moment."
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

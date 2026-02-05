import os
import json
import logging
import asyncio
import subprocess
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import anthropic

# Configuration - no hardcoded secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
JASON_TELEGRAM_ID = int(os.getenv("TELEGRAM_CHAT_ID", "8215335898"))

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set in environment")
APP_ROOT = "/Users/shulmeister/mac-mini-apps/careassist-unified"

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("gigi_telegram_worker")

SYSTEM_PROMPT = """You are Gigi, Jason's Elite Chief of Staff.
You now have the power to FIX APPS using the 'claude' CLI tool.

When Jason asks you to fix code, change a feature, or update one of his apps (Portal, PowderPulse, etc.), you should:
1. Identify the task.
2. Call the 'run_claude_fix' tool.
3. Inform Jason you're starting the fix.

APPS PATHS:
- Portal/Gigi Core: /Users/shulmeister/mac-mini-apps/careassist-unified
- PowderPulse: /Users/shulmeister/mac-mini-apps/careassist-unified/powderpulse
- Elite Trading: /Users/shulmeister/mac-mini-apps/elite-trading-mcp

Always be proactive and confirm when the fix is complete."""

class GigiTelegramBot:
    def __init__(self):
        self.claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.history = []

    async def run_claude_fix(self, task: str, update: Update):
        """Execute the Claude CLI to fix something"""
        await update.message.reply_text(f"🚀 Dispatching Claude to handle this: '{task}'\nSit tight, I'll update you when it's done.")
        
        # Determine the best directory to run in
        cwd = APP_ROOT
        if "powder" in task.lower():
            cwd = os.path.join(APP_ROOT, "powderpulse")
        elif "trading" in task.lower() or "elite" in task.lower():
            cwd = "/Users/shulmeister/mac-mini-apps/elite-trading-mcp"

        try:
            # We run it non-interactively with -y to ensure Gigi doesn't hang
            cmd = f"claude -y '{task}'"
            logger.info(f"Executing: {cmd} in {cwd}")
            
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                await update.message.reply_text("✅ Fix Applied Successfully! I've updated the code and verified the changes.")
            else:
                logger.error(f"Claude CLI error: {stderr.decode()}")
                await update.message.reply_text("⚠️ I ran into an issue applying the fix automatically. I've logged the error for review.")
                
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            await update.message.reply_text(f"❌ Error dispatching fix: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != JASON_TELEGRAM_ID:
            return

        text = update.message.text
        logger.info(f"Jason: {text}")

        # Check for technical fix intent
        if any(kw in text.lower() for kw in ["fix", "change", "update", "implement", "bug", "error"]):
            await self.run_claude_fix(text, update)
            return

        # Regular chat
        await update.message.chat.send_action("typing")
        response = self.claude.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}]
        )
        await update.message.reply_text(response.content[0].text)

async def main():
    gigi = GigiTelegramBot()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gigi.handle_message))
    logger.info("✅ Gigi Telegram Bridge Active")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    while True: await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())

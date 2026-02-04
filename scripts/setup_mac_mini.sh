#!/bin/bash
# Setup script for Mac Mini deployment
# Run this after git pull to configure everything

set -e

echo "=================================="
echo "GIGI MAC MINI SETUP"
echo "=================================="

# Get the script's directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Check if .env already exists
if [ -f ".env" ]; then
    echo "✓ .env file already exists"
else
    echo ""
    echo "ERROR: .env file not found!"
    echo ""
    echo "Please create .env file with your credentials."
    echo "See .env.example for the required variables."
    echo ""
    exit 1
fi

# Copy to ~/.gigi-env for LaunchAgents
cp .env ~/.gigi-env
echo "✓ Copied .env to ~/.gigi-env"

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install python-dotenv python-telegram-bot anthropic google-auth google-auth-oauthlib google-api-python-client 2>/dev/null || true
echo "✓ Dependencies installed"

# Restart the Telegram bot
echo "Restarting Telegram bot..."
launchctl unload ~/Library/LaunchAgents/com.coloradocareassist.telegram-bot.plist 2>/dev/null || true
sleep 2
launchctl load ~/Library/LaunchAgents/com.coloradocareassist.telegram-bot.plist 2>/dev/null || true
echo "✓ Telegram bot restarted"

echo ""
echo "=================================="
echo "SETUP COMPLETE!"
echo "=================================="
echo ""
echo "The Telegram bot should now work with WellSky."
echo ""
echo "For Google Calendar/Email access, run:"
echo "  python3 scripts/get_google_refresh_token.py"
echo "=================================="

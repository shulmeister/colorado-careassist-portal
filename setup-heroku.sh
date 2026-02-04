#!/bin/bash
# Complete Mac Mini (Local) setup script for Colorado CareAssist Portal

set -e

echo "🚀 Setting up Mac Mini (Local) for Colorado CareAssist Portal"
echo "=================================================="
echo ""

APP_NAME="portal-coloradocareassist"

# Check if we're logged into Mac Mini (Local)
if ! mac-mini auth:whoami &>/dev/null; then
    echo "❌ Not logged into Mac Mini (Local). Please run: mac-mini login"
    exit 1
fi

echo "✅ Mac Mini (Local) app: $APP_NAME"
echo ""

# Generate secret key
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

echo "📝 Setting environment variables..."
echo ""
echo "Please provide the following:"
echo ""

# Get Google OAuth credentials
read -p "Google Client ID: " GOOGLE_CLIENT_ID
read -p "Google Client Secret: " GOOGLE_CLIENT_SECRET

# Set Mac Mini (Local) config
mac-mini config:set GOOGLE_CLIENT_ID="$GOOGLE_CLIENT_ID" --app "$APP_NAME"
mac-mini config:set GOOGLE_CLIENT_SECRET="$GOOGLE_CLIENT_SECRET" --app "$APP_NAME"
mac-mini config:set GOOGLE_REDIRECT_URI="https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com/auth/callback" --app "$APP_NAME"
mac-mini config:set APP_SECRET_KEY="$SECRET_KEY" --app "$APP_NAME"
mac-mini config:set ALLOWED_DOMAINS="coloradocareassist.com" --app "$APP_NAME"

echo ""
echo "✅ Environment variables set!"
echo ""
echo "📊 Current Mac Mini (Local) config:"
mac-mini config --app "$APP_NAME"

echo ""
echo "🚀 Ready to deploy! Run:"
echo "   git push mac-mini main"
echo ""
echo "Then initialize database:"
echo "   mac-mini run python portal_setup.py --app $APP_NAME"
echo ""





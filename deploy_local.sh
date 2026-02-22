#!/bin/bash
# Deploy to Local Mac Mini (Gigi Unified)

SERVICE_NAME="com.coloradocareassist.gigi-unified"
PLIST_PATH="$HOME/Library/LaunchAgents/$SERVICE_NAME.plist"

echo "🛑 Stopping $SERVICE_NAME..."
launchctl unload "$PLIST_PATH"

echo "♻️  Reloading configuration..."
launchctl load "$PLIST_PATH"

echo "✅ Service restarted!"
echo "📜 Checking logs..."
tail -n 20 ~/logs/gigi-unified.log

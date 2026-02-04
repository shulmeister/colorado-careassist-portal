#!/bin/bash
# Mac Mini Setup Script for Colorado Care Assist
# Run this script to set up all services with proper security and reliability
# Usage: bash setup-mac-mini.sh

set -e

echo "=================================================="
echo "Colorado Care Assist - Mac Mini Setup"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }

# Check if running as correct user
if [ "$USER" != "shulmeister" ]; then
    log_error "This script should be run as user 'shulmeister'"
    exit 1
fi

REPO_DIR="$HOME/mac-mini-apps/careassist-unified"
SCRIPTS_DIR="$HOME/scripts"
LOGS_DIR="$HOME/logs"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

# ====================
# 1. Create directories
# ====================
echo ""
echo "1. Creating directories..."

mkdir -p "$SCRIPTS_DIR"
mkdir -p "$LOGS_DIR"
mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$HOME/backups"

log_success "Directories created"

# ====================
# 2. Copy health monitor script
# ====================
echo ""
echo "2. Setting up health monitoring..."

cp "$REPO_DIR/scripts/health-monitor.sh" "$SCRIPTS_DIR/"
chmod +x "$SCRIPTS_DIR/health-monitor.sh"

log_success "Health monitor script installed"

# ====================
# 3. Install LaunchAgents
# ====================
echo ""
echo "3. Installing LaunchAgents..."

# Stop existing services first
for service in telegram-bot health-monitor gigi-unified website hesedhomecare elite-trading; do
    launchctl bootout gui/501/com.coloradocareassist.$service 2>/dev/null || true
done

# Copy new LaunchAgent plists
cp "$REPO_DIR/launchagents/"*.plist "$LAUNCH_AGENTS_DIR/" 2>/dev/null || true

# Set correct permissions
chmod 644 "$LAUNCH_AGENTS_DIR/"*.plist

log_success "LaunchAgents installed"

# ====================
# 4. Start services
# ====================
echo ""
echo "4. Starting services..."

sleep 2

# Start health monitor first
launchctl bootstrap gui/501 "$LAUNCH_AGENTS_DIR/com.coloradocareassist.health-monitor.plist" 2>/dev/null || true
log_success "Health monitor started"

# Start telegram bot
launchctl bootstrap gui/501 "$LAUNCH_AGENTS_DIR/com.coloradocareassist.telegram-bot.plist" 2>/dev/null || true
log_success "Telegram bot started"

# ====================
# 5. Security hardening
# ====================
echo ""
echo "5. Applying security settings..."

# Ensure .gigi-env has restrictive permissions
if [ -f "$HOME/.gigi-env" ]; then
    chmod 600 "$HOME/.gigi-env"
    log_success "Environment file secured (chmod 600)"
fi

# Check for exposed credentials in repo (exclude os.getenv patterns which are safe)
if grep -rE "(GOCSPX-[a-zA-Z0-9]+|sk-ant-[a-zA-Z0-9]+|sk-[a-zA-Z0-9]{30,}|['\"][A-Za-z0-9_-]{20,}['\"].*SECRET|refresh_token\s*=\s*['\"][^o])" "$REPO_DIR"/*.py "$REPO_DIR"/**/*.py 2>/dev/null | grep -v ".pyc" | grep -v "__pycache__" | grep -v "os.getenv" | grep -v "os.environ" | head -5; then
    log_warning "Found potential hardcoded credentials in Python files!"
else
    log_success "No hardcoded credentials found in Python files"
fi

# Ensure SSH key permissions
if [ -d "$HOME/.ssh" ]; then
    chmod 700 "$HOME/.ssh"
    chmod 600 "$HOME/.ssh/"* 2>/dev/null || true
    log_success "SSH directory secured"
fi

# ====================
# 6. Firewall setup
# ====================
echo ""
echo "6. Checking firewall..."

# Check if firewall is enabled
if /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate | grep -q "enabled"; then
    log_success "Firewall is enabled"
else
    log_warning "Firewall is DISABLED. Enable it in System Preferences > Security & Privacy"
fi

# ====================
# 7. Verify services
# ====================
echo ""
echo "7. Verifying services..."

sleep 3

# Check telegram bot
if pgrep -f "telegram_bot.py" > /dev/null; then
    log_success "Telegram bot is running"
else
    log_error "Telegram bot is NOT running"
fi

# Check health monitor
if launchctl list | grep -q "com.coloradocareassist.health-monitor"; then
    log_success "Health monitor is registered"
else
    log_warning "Health monitor not found in launchctl"
fi

# Check PostgreSQL
if /opt/homebrew/opt/postgresql@17/bin/pg_isready -q; then
    log_success "PostgreSQL is running"
else
    log_error "PostgreSQL is NOT running"
fi

# Check Cloudflare tunnel
if pgrep -f "cloudflared" > /dev/null; then
    log_success "Cloudflare tunnel is running"
else
    log_error "Cloudflare tunnel is NOT running"
fi

# ====================
# Summary
# ====================
echo ""
echo "=================================================="
echo "Setup complete!"
echo "=================================================="
echo ""
echo "Services running:"
launchctl list | grep -E "coloradocareassist|cloudflare" | awk '{print "  - "$3}'
echo ""
echo "Logs location: $LOGS_DIR"
echo "  - tail -f $LOGS_DIR/telegram-bot.log"
echo "  - tail -f $LOGS_DIR/health-monitor.log"
echo ""
echo "To manually restart a service:"
echo "  launchctl bootout gui/501/com.coloradocareassist.<service>"
echo "  launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.coloradocareassist.<service>.plist"
echo ""

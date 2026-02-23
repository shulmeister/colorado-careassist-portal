#!/bin/bash
# =============================================================================
# COLORADO CARE ASSIST - COMPREHENSIVE HEALTH MONITOR
# =============================================================================
# Monitors all services, APIs, and infrastructure
# Auto-restarts failed services and sends Telegram alerts
# Location: ~/mac-mini-apps/careassist-unified/scripts/health-monitor.sh
# LaunchAgent: com.coloradocareassist.health-monitor (runs every 5 minutes)
# =============================================================================

export PATH="/usr/sbin:/usr/bin:/bin:/opt/homebrew/bin:$PATH"

# Check if running on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "ERROR: This script is designed for macOS only."
    exit 1
fi

# Configuration
LOG_FILE="$HOME/logs/health-monitor.log"
ALERT_FILE="$HOME/logs/health-alerts.log"
STATUS_FILE="$HOME/logs/health-status.json"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-8508806105:AAExZ25ZN19X3xjBQAZ3Q9fHgAQmWWklX8U}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-8215335898}"
ALERT_COOLDOWN_FILE="$HOME/logs/.alert-cooldown"
COOLDOWN_MINUTES=120

# Ensure log directory exists
mkdir -p "$HOME/logs"

# Logging functions
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

alert() {
    local message="$1"
    local send_telegram="${2:-true}"

    echo "$(date '+%Y-%m-%d %H:%M:%S') - ALERT: $message" >> "$ALERT_FILE"
    log "ALERT: $message"

    # Send Telegram alert (with cooldown to prevent spam)
    if [ "$send_telegram" = "true" ] && should_send_alert "$message"; then
        send_telegram_alert "🚨 $message"
        mark_alert_sent "$message"
    fi
}

should_send_alert() {
    local message_hash=$(echo "$1" | md5 | cut -c1-8)
    local cooldown_file="$ALERT_COOLDOWN_FILE.$message_hash"

    if [ -f "$cooldown_file" ]; then
        local last_alert=$(cat "$cooldown_file")
        local now=$(date +%s)
        local diff=$(( (now - last_alert) / 60 ))
        if [ $diff -lt $COOLDOWN_MINUTES ]; then
            return 1  # Don't send, still in cooldown
        fi
    fi
    return 0  # OK to send
}

mark_alert_sent() {
    local message_hash=$(echo "$1" | md5 | cut -c1-8)
    date +%s > "$ALERT_COOLDOWN_FILE.$message_hash"
}

send_telegram_alert() {
    # Telegram notifications disabled — alerts still logged to ~/logs/health-alerts.log
    :
}

# =============================================================================
# SERVICE CHECKS
# =============================================================================

check_and_restart_service() {
    local service_name="$1"
    local plist_name="$2"
    local health_url="$3"
    local port="$4"

    # Check if process is running on port
    if ! lsof -i ":$port" -P 2>/dev/null | grep -q LISTEN; then
        alert "$service_name is DOWN (port $port not listening)"
        log "Attempting to restart $service_name..."

        launchctl bootout gui/501/$plist_name 2>/dev/null
        sleep 2
        launchctl bootstrap gui/501 ~/Library/LaunchAgents/${plist_name}.plist

        sleep 5

        if lsof -i ":$port" -P 2>/dev/null | grep -q LISTEN; then
            log "$service_name restarted successfully"
            echo "recovered"
        else
            alert "$service_name FAILED to restart!"
            echo "failed"
        fi
    else
        # Check health endpoint if provided
        if [ -n "$health_url" ]; then
            if ! curl -sf "$health_url" > /dev/null 2>&1; then
                alert "$service_name health check failed at $health_url"
                echo "unhealthy"
                return
            fi
        fi
        echo "ok"
    fi
}

check_telegram_bot() {
    if ! pgrep -f "telegram_bot.py" > /dev/null; then
        alert "Gigi Telegram Bot is DOWN"
        log "Attempting to restart Gigi Telegram Bot..."

        launchctl bootout gui/501/com.coloradocareassist.telegram-bot 2>/dev/null
        sleep 2
        launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.coloradocareassist.telegram-bot.plist

        sleep 5

        if pgrep -f "telegram_bot.py" > /dev/null; then
            log "Gigi Telegram Bot restarted successfully"
            echo "recovered"
        else
            alert "Gigi Telegram Bot FAILED to restart!"
            echo "failed"
        fi
    else
        echo "ok"
    fi
}

check_postgres() {
    if ! /opt/homebrew/opt/postgresql@17/bin/pg_isready -q 2>/dev/null; then
        alert "PostgreSQL is DOWN"
        log "Attempting to restart PostgreSQL..."
        brew services restart postgresql@17
        sleep 5
        if /opt/homebrew/opt/postgresql@17/bin/pg_isready -q 2>/dev/null; then
            log "PostgreSQL restarted successfully"
            echo "recovered"
        else
            alert "PostgreSQL FAILED to restart!"
            echo "failed"
        fi
    else
        echo "ok"
    fi
}

check_cloudflare_tunnel() {
    if ! pgrep -f "cloudflared" > /dev/null; then
        alert "Cloudflare Tunnel is DOWN"
        log "Attempting to restart Cloudflare Tunnel..."
        launchctl bootout gui/501/com.cloudflare.cloudflared 2>/dev/null
        sleep 2
        launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
        sleep 5
        if pgrep -f "cloudflared" > /dev/null; then
            log "Cloudflare Tunnel restarted successfully"
            echo "recovered"
        else
            alert "Cloudflare Tunnel FAILED to restart!"
            echo "failed"
        fi
    else
        echo "ok"
    fi
}

# =============================================================================
# API CHECKS (non-blocking, just monitoring)
# =============================================================================

check_api() {
    local name="$1"
    local url="$2"
    # Accept any HTTP response (including 401/403 which just means needs auth)
    local http_code=$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
    if [ "$http_code" != "000" ] && [ -n "$http_code" ]; then
        echo "ok"
    else
        log "$name API may be unreachable (no response)"
        echo "warning"
    fi
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

log "=== Health check started ==="

# Check core services
STATUS_TELEGRAM=$(check_telegram_bot)
STATUS_POSTGRES=$(check_postgres)
STATUS_CLOUDFLARE=$(check_cloudflare_tunnel)
STATUS_PORTAL=$(check_and_restart_service "Portal (gigi-unified)" "com.coloradocareassist.gigi-unified" "http://localhost:8765/health" 8765)
STATUS_GIGI=$(check_and_restart_service "Gigi Server" "com.coloradocareassist.gigi-server" "http://localhost:8767/gigi/health" 8767)
STATUS_WEBSITE=$(check_and_restart_service "Main Website" "com.coloradocareassist.website" "" 3000)
STATUS_HESED=$(check_and_restart_service "Hesed Home Care" "com.coloradocareassist.hesedhomecare" "" 3001)
STATUS_ELITE=$(check_and_restart_service "Elite Trading" "com.coloradocareassist.elite-trading" "http://localhost:3002/health" 3002)
STATUS_POWDER=$(check_and_restart_service "PowderPulse" "com.coloradocareassist.powderpulse" "" 3003)
STATUS_FITNESS=$(check_and_restart_service "Fitness Dashboard" "com.coloradocareassist.fitness-dashboard" "http://localhost:3040/health" 3040)

# Check APIs
STATUS_WELLSKY=$(check_api "WellSky" "https://connect.clearcareonline.com")
STATUS_RC=$(check_api "RingCentral" "https://platform.ringcentral.com/restapi/v1.0")
STATUS_RETELL=$(check_api "Retell" "https://api.retellai.com")

# Check external access
STATUS_EXTERNAL="ok"
if ! curl -sf --max-time 10 "https://portal.coloradocareassist.com/health" > /dev/null 2>&1; then
    alert "Portal not reachable externally via Cloudflare"
    STATUS_EXTERNAL="down"
fi

# Generate status JSON
cat > "$STATUS_FILE" << EOF
{
  "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "services": {
    "portal": "$STATUS_PORTAL",
    "gigi_server": "$STATUS_GIGI",
    "website": "$STATUS_WEBSITE",
    "hesed": "$STATUS_HESED",
    "elite_trading": "$STATUS_ELITE",
    "powderpulse": "$STATUS_POWDER",
    "fitness_dashboard": "$STATUS_FITNESS",
    "telegram_bot": "$STATUS_TELEGRAM",
    "postgres": "$STATUS_POSTGRES",
    "cloudflare": "$STATUS_CLOUDFLARE"
  },
  "apis": {
    "wellsky": "$STATUS_WELLSKY",
    "ringcentral": "$STATUS_RC",
    "retell": "$STATUS_RETELL"
  },
  "external": {
    "portal_access": "$STATUS_EXTERNAL"
  }
}
EOF

log "=== Health check completed ==="

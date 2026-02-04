#!/bin/bash
# Health Monitor for Colorado Care Assist Services
# Runs periodically to check services and restart if needed
# Location: ~/scripts/health-monitor.sh

LOG_FILE="$HOME/logs/health-monitor.log"
ALERT_FILE="$HOME/logs/health-alerts.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

alert() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ALERT: $1" >> "$ALERT_FILE"
    log "ALERT: $1"
}

check_and_restart_service() {
    local service_name="$1"
    local plist_name="$2"
    local health_url="$3"
    local port="$4"

    # Check if process is running on port
    if ! lsof -i ":$port" -P | grep -q LISTEN; then
        alert "$service_name is DOWN (port $port not listening)"
        log "Attempting to restart $service_name..."

        launchctl bootout gui/501/$plist_name 2>/dev/null
        sleep 2
        launchctl bootstrap gui/501 ~/Library/LaunchAgents/${plist_name}.plist

        sleep 5

        if lsof -i ":$port" -P | grep -q LISTEN; then
            log "$service_name restarted successfully"
        else
            alert "$service_name FAILED to restart!"
        fi
    else
        # Check health endpoint if provided
        if [ -n "$health_url" ]; then
            if ! curl -sf "$health_url" > /dev/null 2>&1; then
                alert "$service_name health check failed at $health_url"
            fi
        fi
    fi
}

check_telegram_bot() {
    # Check if telegram bot process is running
    if ! pgrep -f "telegram_bot.py" > /dev/null; then
        alert "Gigi Telegram Bot is DOWN"
        log "Attempting to restart Gigi Telegram Bot..."

        launchctl bootout gui/501/com.coloradocareassist.telegram-bot 2>/dev/null
        sleep 2
        launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.coloradocareassist.telegram-bot.plist

        sleep 5

        if pgrep -f "telegram_bot.py" > /dev/null; then
            log "Gigi Telegram Bot restarted successfully"
        else
            alert "Gigi Telegram Bot FAILED to restart!"
        fi
    fi
}

check_postgres() {
    if ! /opt/homebrew/opt/postgresql@17/bin/pg_isready -q; then
        alert "PostgreSQL is DOWN"
        log "Attempting to restart PostgreSQL..."
        brew services restart postgresql@17
        sleep 5
        if /opt/homebrew/opt/postgresql@17/bin/pg_isready -q; then
            log "PostgreSQL restarted successfully"
        else
            alert "PostgreSQL FAILED to restart!"
        fi
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
        else
            alert "Cloudflare Tunnel FAILED to restart!"
        fi
    fi
}

# Main execution
log "=== Health check started ==="

# Check all services
check_telegram_bot
check_postgres
check_cloudflare_tunnel
check_and_restart_service "Portal (gigi-unified)" "com.coloradocareassist.gigi-unified" "http://localhost:8765/health" 8765
check_and_restart_service "Main Website" "com.coloradocareassist.website" "" 3000
check_and_restart_service "Hesed Home Care" "com.coloradocareassist.hesedhomecare" "" 3001
check_and_restart_service "Elite Trading" "com.coloradocareassist.elite-trading" "http://localhost:3002/health" 3002

log "=== Health check completed ==="

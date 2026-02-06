#!/bin/bash
# =============================================================================
# WATCHDOG - Monitors the health monitor and critical services
# =============================================================================
# Runs via cron every 2 minutes as a backup to health-monitor
# Has COOLDOWN to prevent alert spam
# =============================================================================

TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-8508806105:AAExZ25ZN19X3xjBQAZ3Q9fHgAQmWWklX8U}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-8215335898}"
LOG_FILE="$HOME/logs/watchdog.log"
STATE_DIR="$HOME/logs/.watchdog-state"
COOLDOWN_MINUTES=15

mkdir -p "$STATE_DIR"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Only send alert if we haven't alerted for this issue recently
send_alert_once() {
    local key="$1"
    local message="$2"
    local state_file="$STATE_DIR/$key"

    # Check if we already alerted recently
    if [ -f "$state_file" ]; then
        local last_alert=$(cat "$state_file")
        local now=$(date +%s)
        local minutes_ago=$(( (now - last_alert) / 60 ))

        if [ "$minutes_ago" -lt "$COOLDOWN_MINUTES" ]; then
            log "Suppressed alert (cooldown): $message"
            return
        fi
    fi

    # Send alert and record timestamp
    log "ALERT: $message"
    curl -sf -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=🚨 WATCHDOG: ${message}" \
        -d "parse_mode=HTML" > /dev/null 2>&1

    date +%s > "$state_file"
}

# Clear alert state when service recovers (so next failure will alert)
clear_alert_state() {
    local key="$1"
    rm -f "$STATE_DIR/$key" 2>/dev/null
}

# Send recovery alert (only if we previously alerted about failure)
send_recovery() {
    local key="$1"
    local message="$2"
    local state_file="$STATE_DIR/$key"

    # Only send recovery if we had sent a failure alert
    if [ -f "$state_file" ]; then
        log "RECOVERED: $message"
        curl -sf -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            -d "text=✅ ${message}" \
            -d "parse_mode=HTML" > /dev/null 2>&1
        rm -f "$state_file"
    fi
}

# Check health monitor last run time
check_health_monitor() {
    local HEALTH_LOG="$HOME/logs/health-monitor.log"
    if [ -f "$HEALTH_LOG" ]; then
        local LAST_RUN=$(tail -1 "$HEALTH_LOG" | cut -d' ' -f1,2)
        if [ -n "$LAST_RUN" ]; then
            local LAST_RUN_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$LAST_RUN" +%s 2>/dev/null)
            local NOW_EPOCH=$(date +%s)
            local MINUTES_AGO=$(( (NOW_EPOCH - LAST_RUN_EPOCH) / 60 ))

            if [ "$MINUTES_AGO" -gt 10 ]; then
                send_alert_once "health-monitor" "Health monitor stale (${MINUTES_AGO}min). Restarting..."
                launchctl bootout gui/501/com.coloradocareassist.health-monitor 2>/dev/null
                sleep 2
                launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.coloradocareassist.health-monitor.plist
                log "Restarted health monitor"
            else
                clear_alert_state "health-monitor"
            fi
        fi
    fi
}

# Check a service by port
check_service() {
    local name="$1"
    local port="$2"
    local plist="$3"
    local key=$(echo "$name" | tr ' ' '-' | tr '[:upper:]' '[:lower:]')

    if ! lsof -i ":$port" -P 2>/dev/null | grep -q LISTEN; then
        send_alert_once "$key" "$name is DOWN (port $port)"

        # Try to restart
        launchctl bootout gui/501/$plist 2>/dev/null
        sleep 2
        launchctl bootstrap gui/501 ~/Library/LaunchAgents/${plist}.plist
        sleep 5

        if lsof -i ":$port" -P 2>/dev/null | grep -q LISTEN; then
            send_recovery "$key" "$name recovered and is running"
        fi
    else
        # Service is up - clear any previous alert state
        if [ -f "$STATE_DIR/$key" ]; then
            send_recovery "$key" "$name is back up"
        fi
    fi
}

# Main execution
check_health_monitor

check_service "Portal" 8765 "com.coloradocareassist.gigi-unified"
check_service "Elite-Trading" 3002 "com.coloradocareassist.elite-trading"
check_service "Website" 3000 "com.coloradocareassist.website"

# Check Cloudflare tunnel
if ! pgrep -f "cloudflared" > /dev/null; then
    send_alert_once "cloudflare" "Cloudflare tunnel is DOWN"
    launchctl bootout gui/501/com.cloudflare.cloudflared 2>/dev/null
    sleep 2
    launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
else
    if [ -f "$STATE_DIR/cloudflare" ]; then
        send_recovery "cloudflare" "Cloudflare tunnel is back up"
    fi
fi

log "Watchdog check completed"

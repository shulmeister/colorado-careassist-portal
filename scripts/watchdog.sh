#!/bin/bash
# =============================================================================
# WATCHDOG - Monitors the health monitor and critical services
# =============================================================================
# This runs independently every 2 minutes via cron as a backup
# If health-monitor dies, this catches it
# =============================================================================

TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-8508806105:AAExZ25ZN19X3xjBQAZ3Q9fHgAQmWWklX8U}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-8215335898}"
LOG_FILE="$HOME/logs/watchdog.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

send_alert() {
    local message="$1"
    log "ALERT: $message"
    curl -sf -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=🚨 WATCHDOG: ${message}" \
        -d "parse_mode=HTML" > /dev/null 2>&1
}

# Check health monitor last run time
HEALTH_LOG="$HOME/logs/health-monitor.log"
if [ -f "$HEALTH_LOG" ]; then
    LAST_RUN=$(tail -1 "$HEALTH_LOG" | cut -d' ' -f1,2)
    if [ -n "$LAST_RUN" ]; then
        LAST_RUN_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$LAST_RUN" +%s 2>/dev/null)
        NOW_EPOCH=$(date +%s)
        MINUTES_AGO=$(( (NOW_EPOCH - LAST_RUN_EPOCH) / 60 ))

        if [ "$MINUTES_AGO" -gt 10 ]; then
            send_alert "Health monitor hasn't run in ${MINUTES_AGO} minutes! Restarting..."
            launchctl bootout gui/501/com.coloradocareassist.health-monitor 2>/dev/null
            sleep 2
            launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.coloradocareassist.health-monitor.plist
            log "Restarted health monitor"
        fi
    fi
fi

# Direct check of critical services (independent of health monitor)
SERVICES=(
    "Portal:8765:com.coloradocareassist.gigi-unified"
    "Elite Trading:3002:com.coloradocareassist.elite-trading"
    "Website:3000:com.coloradocareassist.website"
)

for svc in "${SERVICES[@]}"; do
    NAME=$(echo "$svc" | cut -d: -f1)
    PORT=$(echo "$svc" | cut -d: -f2)
    PLIST=$(echo "$svc" | cut -d: -f3)

    if ! lsof -i ":$PORT" -P 2>/dev/null | grep -q LISTEN; then
        send_alert "$NAME is DOWN (port $PORT). Attempting restart..."
        launchctl bootout gui/501/$PLIST 2>/dev/null
        sleep 2
        launchctl bootstrap gui/501 ~/Library/LaunchAgents/${PLIST}.plist
        sleep 5

        if lsof -i ":$PORT" -P 2>/dev/null | grep -q LISTEN; then
            send_alert "✅ $NAME recovered"
            log "$NAME restarted successfully"
        else
            send_alert "❌ $NAME FAILED to restart - manual intervention needed!"
            log "$NAME failed to restart"
        fi
    fi
done

# Check Cloudflare tunnel
if ! pgrep -f "cloudflared" > /dev/null; then
    send_alert "Cloudflare tunnel is DOWN. Restarting..."
    launchctl bootout gui/501/com.cloudflare.cloudflared 2>/dev/null
    sleep 2
    launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
    log "Restarted cloudflared"
fi

# Check external access (the real test)
if ! curl -sf --max-time 15 "https://elitetrading.coloradocareassist.com/health" > /dev/null 2>&1; then
    send_alert "Elite Trading not accessible externally!"
fi

if ! curl -sf --max-time 15 "https://portal.coloradocareassist.com/health" > /dev/null 2>&1; then
    send_alert "Portal not accessible externally!"
fi

log "Watchdog check completed"

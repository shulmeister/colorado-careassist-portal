#!/bin/bash
# Security Audit Script for Mac Mini
# Run periodically to check for security issues
# Usage: bash security-audit.sh

echo "=================================================="
echo "Colorado Care Assist - Security Audit"
echo "$(date)"
echo "=================================================="

ISSUES=0
WARNINGS=0

check_pass() { echo -e "\033[0;32m[PASS]\033[0m $1"; }
check_warn() { echo -e "\033[1;33m[WARN]\033[0m $1"; ((WARNINGS++)); }
check_fail() { echo -e "\033[0;31m[FAIL]\033[0m $1"; ((ISSUES++)); }

# ====================
# File Permissions
# ====================
echo ""
echo "--- File Permissions ---"

# Check .gigi-env permissions
if [ -f "$HOME/.gigi-env" ]; then
    perms=$(stat -f "%Lp" "$HOME/.gigi-env")
    if [ "$perms" == "600" ]; then
        check_pass ".gigi-env has correct permissions (600)"
    else
        check_fail ".gigi-env has insecure permissions ($perms) - should be 600"
    fi
else
    check_warn ".gigi-env file not found"
fi

# Check SSH directory
if [ -d "$HOME/.ssh" ]; then
    ssh_perms=$(stat -f "%Lp" "$HOME/.ssh")
    if [ "$ssh_perms" == "700" ]; then
        check_pass ".ssh directory has correct permissions (700)"
    else
        check_fail ".ssh directory has insecure permissions ($ssh_perms)"
    fi
fi

# ====================
# Exposed Credentials
# ====================
echo ""
echo "--- Credential Exposure Check ---"

# Check for hardcoded secrets in code
REPO_DIR="$HOME/mac-mini-apps/careassist-unified"
if [ -d "$REPO_DIR" ]; then
    # Check for API keys in Python files
    if grep -rE "(sk-ant-|GOCSPX-|sk-[a-zA-Z0-9]{20,})" "$REPO_DIR"/*.py "$REPO_DIR"/**/*.py 2>/dev/null | grep -v ".pyc" | grep -v "__pycache__" | head -5; then
        check_fail "Found potential API keys hardcoded in Python files"
    else
        check_pass "No obvious API keys in Python files"
    fi

    # Check .env files aren't committed
    if [ -f "$REPO_DIR/.env" ]; then
        if grep -q ".env" "$REPO_DIR/.gitignore" 2>/dev/null; then
            check_pass ".env is in .gitignore"
        else
            check_warn ".env exists but may not be in .gitignore"
        fi
    fi
fi

# ====================
# Network Security
# ====================
echo ""
echo "--- Network Security ---"

# Check firewall status
if /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null | grep -q "enabled"; then
    check_pass "Firewall is enabled"
else
    check_fail "Firewall is DISABLED"
fi

# Check for unexpected listening ports
echo "Listening ports:"
lsof -i -P | grep LISTEN | awk '{print "  "$1" "$9}' | sort -u

# Check Tailscale status
if command -v tailscale &> /dev/null; then
    if tailscale status &>/dev/null; then
        check_pass "Tailscale is connected"
    else
        check_warn "Tailscale is not connected"
    fi
fi

# ====================
# Service Security
# ====================
echo ""
echo "--- Service Security ---"

# Check if services are running as correct user
telegram_user=$(ps aux | grep "[t]elegram_bot.py" | awk '{print $1}')
if [ "$telegram_user" == "shulmeister" ]; then
    check_pass "Telegram bot running as shulmeister"
elif [ -n "$telegram_user" ]; then
    check_warn "Telegram bot running as $telegram_user (expected shulmeister)"
fi

# Check Cloudflare tunnel
if pgrep -f "cloudflared" > /dev/null; then
    check_pass "Cloudflare tunnel is running (traffic encrypted)"
else
    check_fail "Cloudflare tunnel is NOT running"
fi

# ====================
# System Updates
# ====================
echo ""
echo "--- System Status ---"

# Check for Homebrew updates
if command -v brew &> /dev/null; then
    outdated=$(brew outdated --quiet 2>/dev/null | wc -l | tr -d ' ')
    if [ "$outdated" -gt 10 ]; then
        check_warn "$outdated Homebrew packages are outdated - run 'brew upgrade'"
    else
        check_pass "Homebrew packages are reasonably up to date"
    fi
fi

# Check disk space
disk_usage=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$disk_usage" -gt 90 ]; then
    check_fail "Disk usage is at ${disk_usage}%"
elif [ "$disk_usage" -gt 80 ]; then
    check_warn "Disk usage is at ${disk_usage}%"
else
    check_pass "Disk usage is at ${disk_usage}%"
fi

# ====================
# Backup Status
# ====================
echo ""
echo "--- Backup Status ---"

# Check last backup
BACKUP_DIR="$HOME/backups"
if [ -d "$BACKUP_DIR" ]; then
    latest_backup=$(ls -t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | head -1)
    if [ -n "$latest_backup" ]; then
        backup_age=$((($(date +%s) - $(stat -f %m "$latest_backup")) / 86400))
        if [ "$backup_age" -gt 2 ]; then
            check_warn "Latest backup is $backup_age days old"
        else
            check_pass "Latest backup is $backup_age days old"
        fi
    else
        check_warn "No database backups found in $BACKUP_DIR"
    fi
fi

# ====================
# Summary
# ====================
echo ""
echo "=================================================="
echo "Audit Summary"
echo "=================================================="
echo "Issues found: $ISSUES"
echo "Warnings: $WARNINGS"
echo ""

if [ "$ISSUES" -gt 0 ]; then
    echo -e "\033[0;31mAction required: Please address the FAIL items above\033[0m"
    exit 1
elif [ "$WARNINGS" -gt 0 ]; then
    echo -e "\033[1;33mReview recommended: Check the WARN items above\033[0m"
    exit 0
else
    echo -e "\033[0;32mAll checks passed!\033[0m"
    exit 0
fi

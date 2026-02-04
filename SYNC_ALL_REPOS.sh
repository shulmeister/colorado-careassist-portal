#!/bin/bash
# Sync All Repos: Desktop → GitHub → Mac Mini (Local)
# This script ensures all repos are synced across Desktop, GitHub, and Mac Mini (Local)

set -e  # Exit on error

echo "🔄 Syncing All Repos: Desktop → GitHub → Mac Mini (Local)"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to sync a repo
sync_repo() {
    local repo_name=$1
    local repo_path=$2
    local github_repo=$3
    local mac-mini_app=$4
    
    echo -e "${YELLOW}📦 Syncing: $repo_name${NC}"
    echo "   Path: $repo_path"
    
    cd "$repo_path" || exit 1
    
    # Check if we're in a git repo
    if [ ! -d .git ]; then
        echo -e "${RED}   ❌ Not a git repository!${NC}"
        return 1
    fi
    
    # Check for uncommitted changes
    if [ -n "$(git status --porcelain)" ]; then
        echo -e "${YELLOW}   ⚠️  Uncommitted changes detected${NC}"
        echo "   Staging all changes..."
        git add .
        read -p "   Enter commit message: " commit_msg
        git commit -m "$commit_msg"
    fi
    
    # Push to GitHub
    echo "   📤 Pushing to GitHub..."
    if git push origin main 2>&1; then
        echo -e "${GREEN}   ✅ GitHub synced${NC}"
    else
        echo -e "${RED}   ❌ GitHub push failed${NC}"
        return 1
    fi
    
    # Push to Mac Mini (Local)
    echo "   📤 Pushing to Mac Mini (Local)..."
    if git push mac-mini main 2>&1; then
        echo -e "${GREEN}   ✅ Mac Mini (Local) synced${NC}"
    else
        echo -e "${RED}   ❌ Mac Mini (Local) push failed${NC}"
        return 1
    fi
    
    echo ""
}

# Get the base directory
BASE_DIR="/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal"

# Sync Portal (Hub)
sync_repo \
    "Portal" \
    "$BASE_DIR" \
    "shulmeister/colorado-careassist-portal" \
    "portal-coloradocareassist"

# Sync Sales Dashboard
sync_repo \
    "Sales Dashboard" \
    "$BASE_DIR/dashboards/sales" \
    "shulmeister/sales-dashboard" \
    "careassist-tracker"

# Sync Recruiter Dashboard
sync_repo \
    "Recruiter Dashboard" \
    "$BASE_DIR/dashboards/recruitment" \
    "shulmeister/recruiter-dashboard" \
    "caregiver-lead-tracker"

# Sync Activity Tracker
sync_repo \
    "Activity Tracker" \
    "$BASE_DIR/dashboards/activity-tracker" \
    "shulmeister/Colorado-CareAssist-Route-Tracker" \
    "cca-activity-tracker"

echo -e "${GREEN}✅ All repos synced!${NC}"
echo ""
echo "Desktop → GitHub → Mac Mini (Local) flow complete!"


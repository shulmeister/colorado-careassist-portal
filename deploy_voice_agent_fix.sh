#!/bin/bash
# Deploy Voice Agent Fix - Caller ID & Transfer Enhancement
# This script deploys all changes to fix the voice agent issues

set -e  # Exit on error

echo "=================================================="
echo "  Voice Agent Fix Deployment"
echo "  Fixing: Caller ID, Transfer, Weather, Messages"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check we're in the right directory
if [ ! -f "unified_app.py" ]; then
    echo -e "${RED}Error: Must run from careassist-unified directory${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Backup current files${NC}"
cp gigi/main.py gigi/main.py.backup.$(date +%Y%m%d_%H%M%S)
cp gigi/retell_tools_schema.json gigi/retell_tools_schema.json.backup.$(date +%Y%m%d_%H%M%S)
echo -e "${GREEN}✓ Backups created${NC}"
echo ""

echo -e "${YELLOW}Step 2: Update Retell tools schema${NC}"
if [ -f "gigi/retell_tools_schema_updated.json" ]; then
    cp gigi/retell_tools_schema_updated.json gigi/retell_tools_schema.json
    echo -e "${GREEN}✓ Schema updated with new tools (weather, transfer, take_message)${NC}"
else
    echo -e "${RED}Error: retell_tools_schema_updated.json not found${NC}"
    exit 1
fi
echo ""

echo -e "${YELLOW}Step 3: Verify new files exist${NC}"
required_files=(
    "gigi/enhanced_webhook.py"
    "gigi/apple_contacts_lookup.py"
)
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓ $file${NC}"
    else
        echo -e "${RED}✗ Missing: $file${NC}"
        exit 1
    fi
done
echo ""

echo -e "${YELLOW}Step 4: Add imports to main.py${NC}"
# Check if imports are already added
if ! grep -q "from enhanced_webhook import" gigi/main.py; then
    # Find the line after the last import and add our imports
    sed -i.bak '/^import sys/a\
\
# Enhanced webhook functionality\
from enhanced_webhook import (\
    CallerLookupService, generate_greeting, transfer_call,\
    send_telegram_message, handle_message_received, get_weather\
)
' gigi/main.py
    echo -e "${GREEN}✓ Imports added${NC}"
else
    echo -e "${YELLOW}! Imports already present, skipping${NC}"
fi
echo ""

echo -e "${YELLOW}Step 5: Git commit changes${NC}"
git add gigi/enhanced_webhook.py gigi/apple_contacts_lookup.py gigi/retell_tools_schema.json
git commit -m "Fix voice agent: Add caller ID, transfer, weather, and message taking"
echo -e "${GREEN}✓ Changes committed${NC}"
echo ""

echo -e "${YELLOW}Step 6: Deploy to Mac Mini (Local)${NC}"
echo "Pushing to Mac Mini (Local)..."
git push mac-mini main
echo -e "${GREEN}✓ Deployed to Mac Mini (Local)${NC}"
echo ""

echo -e "${YELLOW}Step 7: Sync tools with Retell AI${NC}"
cd gigi
python3 sync_retell.py
cd ..
echo -e "${GREEN}✓ Retell AI tools synced${NC}"
echo ""

echo -e "${YELLOW}Step 8: Verify deployment${NC}"
echo "Checking Mac Mini (Local) app health..."
curl -s https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/gigi/health | python3 -m json.tool
echo ""
echo -e "${GREEN}✓ Deployment verification complete${NC}"
echo ""

echo "=================================================="
echo -e "${GREEN}  DEPLOYMENT COMPLETE!${NC}"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Test by calling +17208176600 from Jason's phone"
echo "2. Test weather request: Ask 'What's the weather?'"
echo "3. Test unknown caller flow: Call from different number"
echo "4. Verify Telegram notifications work"
echo ""
echo "Manual steps still needed:"
echo "1. Update gigi/main.py webhook handlers (see webhook_patch.py)"
echo "2. Add Mac node integration for Apple Contacts"
echo "3. Test call transfer functionality"
echo ""

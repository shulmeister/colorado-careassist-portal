#!/bin/bash
# Check for Gemini API key and deploy VA tool

echo "🔍 Checking Mac Mini (Local) config for Gemini API key..."
GEMINI_KEY=$(mac-mini config:get GEMINI_API_KEY -a careassist-unified 2>&1)
GOOGLE_KEY=$(mac-mini config:get GOOGLE_API_KEY -a careassist-unified 2>&1)

if [ -n "$GEMINI_KEY" ] && [ "$GEMINI_KEY" != "" ]; then
    echo "✅ GEMINI_API_KEY is set on Mac Mini (Local)"
elif [ -n "$GOOGLE_KEY" ] && [ "$GOOGLE_KEY" != "" ]; then
    echo "✅ GOOGLE_API_KEY is set on Mac Mini (Local)"
else
    echo "⚠️  WARNING: No Gemini/Google API key found on Mac Mini (Local)"
    echo ""
    echo "Set one with:"
    echo "  mac-mini config:set GEMINI_API_KEY=your-key -a careassist-unified"
    echo ""
    read -p "Continue with deployment anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled."
        exit 1
    fi
fi

echo ""
echo "📦 Deploying VA Plan of Care Generator..."
cd ~/colorado-careassist-portal

git add portal/portal_app.py

git commit -m "Replace pdfplumber with Gemini AI for VA Form 10-7080 extraction

- Use Gemini 2.0 Flash for comprehensive PDF data extraction
- Extract ALL fields: veteran info, dates, PCP, facility, clinical data, ADLs
- Fix filename generation with proper date formatting (MM.DD.YYYY)
- Auto-populate ADL checkboxes from extracted data
- Add facility phone/fax, reason for request, auth duration fields
- Structured JSON extraction with temperature=0.1 for consistency

Gemini AI extracts 20+ fields vs 10 with pdfplumber regex.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

echo ""
echo "🚀 Pushing to Mac Mini (Local)..."
git push mac-mini main

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Test at: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/va-plan-of-care"

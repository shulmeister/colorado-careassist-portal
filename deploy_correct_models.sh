#!/bin/bash
# Deploy with correct Gemini model names and API versions

cd ~/colorado-careassist-portal

echo "📦 Committing correct Gemini models..."
git add portal/portal_app.py

git commit -m "Fix Gemini models - use correct API versions and model names

- Try v1beta with gemini-2.0-flash-exp (experimental)
- Try v1 with gemini-1.5-flash-latest and gemini-1.5-pro-latest
- Try v1beta with versioned models (002)
- Test multiple API versions/models until one works
- Add logging for each attempt

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

echo ""
echo "🚀 Deploying to Mac Mini (Local)..."
git push mac-mini main

echo ""
echo "✅ Deployed!"
echo ""
echo "The tool will now try 5 different Gemini models/versions."
echo "Test at: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/va-plan-of-care"

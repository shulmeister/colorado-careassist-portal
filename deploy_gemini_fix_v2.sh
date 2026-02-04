#!/bin/bash
# Deploy improved Gemini API with better error handling

cd ~/colorado-careassist-portal

echo "📦 Committing Gemini improvements..."
git add portal/portal_app.py

git commit -m "Improve Gemini API error handling and model fallback

- Return detailed error messages to frontend (200 status)
- Try multiple models: gemini-1.5-flash, gemini-1.5-pro
- Clean markdown wrappers from JSON responses
- Add comprehensive logging for debugging
- Remove responseMimeType constraint

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

echo ""
echo "🚀 Deploying to Mac Mini (Local)..."
git push mac-mini main

echo ""
echo "✅ Deployed!"
echo ""
echo "Now you'll see the actual error message in the UI."
echo "Test at: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/va-plan-of-care"

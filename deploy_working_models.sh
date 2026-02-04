#!/bin/bash
# Deploy with correct working Gemini model names

cd ~/colorado-careassist-portal

echo "📦 Committing working Gemini model names..."
git add portal/portal_app.py

git commit -m "Use working Gemini model names from ai_document_parser

- Use simple model names: gemini-2.0-flash, gemini-1.5-flash, gemini-1.5-pro
- Match exact pattern from working ai_document_parser.py code
- Use v1beta API only (not v1)
- No -exp, -latest, or -002 suffixes
- Better 404 handling

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

echo ""
echo "🚀 Deploying to Mac Mini (Local)..."
git push mac-mini main

echo ""
echo "✅ Deployed with working model names!"
echo ""
echo "Models will try in order:"
echo "  1. gemini-2.0-flash"
echo "  2. gemini-1.5-flash"
echo "  3. gemini-1.5-pro"
echo ""
echo "Test at: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/va-plan-of-care"

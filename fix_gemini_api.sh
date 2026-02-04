#!/bin/bash
# Fix Gemini API header issue and deploy

cd ~/colorado-careassist-portal

echo "📦 Committing Gemini API fix..."
git add portal/portal_app.py

git commit -m "Fix Gemini API call - use headers instead of query param

- Move API key from URL query to x-goog-api-key header
- Increase timeout to 60s for PDF processing
- Match working Gemini pattern from ai_document_parser.py

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

echo ""
echo "🚀 Deploying to Mac Mini (Local)..."
git push mac-mini main

echo ""
echo "✅ Fix deployed!"
echo ""
echo "Test again at: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/va-plan-of-care"

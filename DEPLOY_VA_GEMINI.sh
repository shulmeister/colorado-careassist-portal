#!/bin/bash
# Deploy VA Plan of Care Generator with Gemini AI extraction

cd ~/colorado-careassist-portal

echo "Adding files..."
git add portal/portal_app.py

echo "Committing..."
git commit -m "Replace pdfplumber with Gemini AI for VA Form 10-7080 extraction

- Use Gemini 2.0 Flash for comprehensive PDF data extraction
- Extract ALL fields: veteran info, dates, PCP, facility, clinical data, ADLs
- Fix filename generation with proper date formatting (MM.DD.YYYY)
- Auto-populate ADL checkboxes from extracted data
- Add facility phone/fax, reason for request, auth duration fields
- Structured JSON extraction with temperature=0.1 for consistency

Gemini AI extracts 20+ fields vs 10 with pdfplumber regex.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

echo "Pushing to Heroku..."
git push heroku main

echo ""
echo "✓ Deployment complete!"
echo ""
echo "IMPORTANT: Set GEMINI_API_KEY on Heroku if not already set:"
echo "heroku config:set GEMINI_API_KEY=your-key-here -a careassist-unified"

#!/bin/bash
# Deploy improved date extraction for VA Form 10-7080

cd ~/colorado-careassist-portal

echo "📦 Committing improved date extraction..."
git add portal/portal_app.py

git commit -m "Improve date extraction in Gemini prompt

- Add CRITICAL INSTRUCTIONS FOR DATES section
- Be specific about where to find dates on VA Form 10-7080
- Tell Gemini to search entire document for dates
- Add console logging to debug date extraction
- Improve date format parsing with better validation
- Add warnings for unparseable dates

Focuses on extracting:
- referral_issue_date (for certification date in filename)
- first_appointment_date (for start date in filename)
- expiration_date

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

echo ""
echo "🚀 Deploying to Heroku..."
git push heroku main

echo ""
echo "✅ Deployed!"
echo ""
echo "Changes:"
echo "  - More specific prompts for date extraction"
echo "  - Console logging (check browser DevTools)"
echo "  - Better date format handling"
echo ""
echo "Test at: https://careassist-unified-0a11ddb45ac0.herokuapp.com/va-plan-of-care"
echo ""
echo "After upload, open browser DevTools (F12) -> Console tab to see:"
echo "  - What data Gemini extracted"
echo "  - Which dates were found/missing"
echo "  - Date format conversions"

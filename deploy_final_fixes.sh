#!/bin/bash
# Deploy final VA Plan of Care fixes

cd ~/colorado-careassist-portal

echo "📦 Committing final fixes..."
git add portal/portal_app.py

git commit -m "Fix VA filename and PDF printing issues

FILENAME FIX:
- Use only ONE date in filename (start date)
- Remove duplicate certification date
- Format: LastName.F.1234_VA000.PCP.P.CC.D.MM.DD.YYYY.001.pdf
- Matches VA convention: Phipps.J.1566_7811387.Ziegler.L.CC.D.3.05.2025.pdf

PDF PRINTING FIX:
- Reduce html2canvas scale from 2 to 1.5 (prevents blank pages)
- Add proper pagebreak handling with mode: ['avoid-all', 'css', 'legacy']
- Reduce margins to 0.5in on all sides
- Add max-width to plan-of-care content
- Add orphans/widows control for better page breaks
- Add scrollY:0, scrollX:0 to prevent offset issues

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

echo ""
echo "🚀 Deploying to Heroku..."
git push heroku main

echo ""
echo "✅ Deployed!"
echo ""
echo "FIXES:"
echo "  1. ✓ Filename now uses ONE date (start date only)"
echo "  2. ✓ PDF should print correctly without blank pages"
echo ""
echo "Test at: https://careassist-unified-0a11ddb45ac0.herokuapp.com/va-plan-of-care"
echo ""
echo "Expected filename format:"
echo "  Crowley.W.3414_VA0055325584.Reeder.C.CC.D.02.04.2026.001.pdf"

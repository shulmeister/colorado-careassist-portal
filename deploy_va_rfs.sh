#!/bin/bash
# Deploy VA RFS Converter to Mac Mini (Local)

cd ~/colorado-careassist-portal

echo "🚀 Deploying VA RFS Converter to Mac Mini (Local)..."
echo ""

# Stage files
git add portal/portal_app.py
git add portal/portal_setup.py
git add add_va_rfs_tile.py

# Commit
git commit -m "Add VA RFS Converter - Convert referral face sheets to VA Form 10-10172

NEW FEATURE: VA RFS Converter

Routes Added:
- POST /api/parse-va-rfs-referral (Gemini AI extraction)
- GET /va-rfs-converter (HTML tool interface)

Files Modified:
- portal/portal_app.py (~600 lines added)
- portal/portal_setup.py (added RFS tile config)

Files Created:
- add_va_rfs_tile.py (database helper script)

Features:
✓ AI-powered extraction from referral PDFs (Gemini 2.0 Flash)
✓ Supports nursing home, hospital, ALF referrals
✓ Auto-populates VA Form 10-10172 RFS
✓ Medical and DME/Prosthetics sections
✓ PDF and HTML download
✓ Portal tile integration (Operations category)

Extracts 30+ fields:
- Veteran information (name, DOB, SSN, address)
- Ordering provider (name, NPI, contact, office)
- Facility information (name, type)
- Medical data (diagnosis, ICD-10, medications, allergies)
- Service types (home health, geriatric, respite, hospice, DME)
- Emergency contact
- Key dates (referral, admission, discharge)

Similar to VA Plan of Care Generator but for RFS requests.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

echo ""
echo "✅ Changes committed!"
echo ""

# Push to Mac Mini (Local)
echo "📤 Pushing to Mac Mini (Local)..."
git push mac-mini main

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "  1. Run: python add_va_rfs_tile.py (to add database tile)"
echo "  2. Visit: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/va-rfs-converter"
echo "  3. Test with sample referral PDFs"
echo ""

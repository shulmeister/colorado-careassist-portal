#!/bin/bash
# Commit all VA Plan of Care documentation

cd ~/colorado-careassist-portal

echo "📚 Committing comprehensive VA Plan of Care documentation..."

git add VA-PLAN-OF-CARE-README.md
git add VA-QUICK-REFERENCE.md
git add va-plan-of-care/DEPLOYMENT.md
git add add_va_tile.py

git commit -m "Add comprehensive VA Plan of Care Generator documentation

Documentation added:
- VA-PLAN-OF-CARE-README.md (complete user guide)
- VA-QUICK-REFERENCE.md (quick reference card)
- va-plan-of-care/DEPLOYMENT.md (deployment & maintenance guide)
- add_va_tile.py (database helper script)

Covers:
✓ Quick start guide (3 steps)
✓ AI extraction details (22+ fields)
✓ VA naming convention with examples
✓ Technical architecture
✓ API endpoints & Gemini integration
✓ Troubleshooting guide
✓ Deployment procedures
✓ Security notes
✓ Maintenance schedule
✓ Support escalation

Version: 2.0
Status: Production Ready

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

echo ""
echo "✅ Documentation committed!"
echo ""
echo "📖 Documentation Files:"
echo "  - VA-PLAN-OF-CARE-README.md (Full guide)"
echo "  - VA-QUICK-REFERENCE.md (Quick reference)"
echo "  - va-plan-of-care/DEPLOYMENT.md (Deployment guide)"
echo ""
echo "🚀 Ready to push:"
echo "  git push origin main"
echo "  git push heroku main"

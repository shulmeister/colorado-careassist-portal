# VA Plan of Care Generator - Deployment Guide

**Maintainer:** Jason Shulman
**Last Updated:** January 27, 2026

---

## Environment Setup

### Required Environment Variables

On Mac Mini (Local) (careassist-unified app):

```bash
# Gemini API Key (required for AI extraction)
GEMINI_API_KEY=<your-key>
# OR
GOOGLE_API_KEY=<your-key>
```

### Check if API Key is Set

```bash
mac-mini config -a careassist-unified | grep -i "GEMINI\|GOOGLE"
```

### Set API Key (if missing)

```bash
mac-mini config:set GEMINI_API_KEY=<your-key> -a careassist-unified
```

---

## Deployment Steps

### 1. Test Locally (Optional)

```bash
cd ~/colorado-careassist-portal

# Install dependencies
pip install -r requirements.txt

# Run portal locally
uvicorn portal.portal_app:app --reload --port 8000

# Test at: http://localhost:8000/va-plan-of-care
```

### 2. Deploy to Mac Mini (Local)

```bash
cd ~/colorado-careassist-portal

# Stage changes
git add portal/portal_app.py

# Commit
git commit -m "Update VA Plan of Care Generator"

# Deploy
git push mac-mini main
```

### 3. Verify Deployment

```bash
# Check build logs
mac-mini logs --tail -a careassist-unified

# Visit live URL
open https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/va-plan-of-care
```

### 4. Test After Deployment

1. Upload a VA Form 10-7080 PDF
2. Verify 20+ fields extracted
3. Check filename format
4. Download PDF and verify no blank pages
5. Verify file opens correctly

---

## Database Setup

### Add VA Tile to Portal Dashboard

**Option A: Run Setup Script (First Time Only)**

```bash
cd ~/colorado-careassist-portal
python add_va_tile.py
```

**Option B: Database SQL (if needed)**

```sql
INSERT INTO portal_tools (
  name,
  url,
  icon,
  description,
  category,
  display_order,
  is_active
) VALUES (
  'VA Plan of Care Generator',
  '/va-plan-of-care',
  'https://cdn-icons-png.flaticon.com/512/2910/2910791.png',
  'Convert VA Form 10-7080 to Plan of Care with automatic PDF naming',
  'Operations',
  25,
  true
);
```

**Option C: Mac Mini (Local) CLI**

```bash
mac-mini run python add_va_tile.py -a careassist-unified
```

---

## File Structure

### Core Files

```
/portal/portal_app.py           # Main app with VA routes
  - Line ~5272: POST /api/parse-va-form-10-7080 (Gemini AI extraction)
  - Line ~5383: GET /va-plan-of-care (HTML tool)

/portal/portal_setup.py         # Database seeding
  - Line ~217: VA tool tile config

/add_va_tile.py                 # Helper script to add tile

/VA-PLAN-OF-CARE-README.md      # Full documentation
/VA-QUICK-REFERENCE.md          # Quick reference card
/va-plan-of-care/DEPLOYMENT.md  # This file
```

### Dependencies (requirements.txt)

```
google-generativeai==0.8.6      # Gemini AI SDK
pdfplumber==0.11.7              # PDF parsing (fallback)
fastapi==0.120.0                # Web framework
httpx==0.27.0                   # Async HTTP client
```

---

## Monitoring & Debugging

### Check Gemini API Usage

```bash
# View logs for Gemini API calls
mac-mini logs --tail -a careassist-unified | grep "Gemini"
```

### Common Log Messages

**Success:**
```
✓ Successfully used Gemini model: gemini-2.0-flash
PDF parsed successfully using Gemini AI
```

**Errors:**
```
Gemini model gemini-2.0-flash not found (404), trying next...
All Gemini models failed. Last error: ...
```

### Browser Console Debugging

When testing, open browser DevTools (F12) → Console:

```javascript
// You'll see logs like:
Extracted data from Gemini: {...}
Date fields: {referral_issue_date: "02/04/2026", ...}
Converted date: 02/04/2026 -> 2026-02-04
```

### Check API Quota

Gemini has usage limits. If hitting quota:

1. Check Google Cloud Console
2. Verify API key is valid
3. Check if quota needs to be increased

---

## Rollback Procedure

### If Deployment Breaks

```bash
# View recent commits
git log --oneline -10

# Rollback to previous version
git revert <commit-hash>
git push mac-mini main

# OR use Mac Mini (Local) rollback
mac-mini releases -a careassist-unified
mac-mini rollback v<number> -a careassist-unified
```

### Emergency Disable

If the tool is broken, disable the tile in database:

```bash
mac-mini run python -a careassist-unified
```

```python
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()
va_tool = db.query(PortalTool).filter(
    PortalTool.name == 'VA Plan of Care Generator'
).first()
va_tool.is_active = False
db.commit()
```

---

## Performance Tuning

### Current Performance

- **PDF Upload**: < 1 second
- **Gemini Extraction**: 2-5 seconds
- **PDF Generation**: 1-2 seconds (client-side)
- **Total Time**: 3-8 seconds end-to-end

### Optimization Options

**If Gemini is slow:**
1. Try `gemini-2.0-flash` (fastest)
2. Reduce prompt size
3. Cache common extractions

**If PDF generation is slow:**
1. Already optimized with `scale: 1.5`
2. Consider server-side PDF generation (future)

---

## Future Enhancements

### Potential Features

- [ ] Batch processing (multiple VA forms at once)
- [ ] Save drafts to database
- [ ] Email PDF directly to VA contact
- [ ] OCR fallback for low-quality scans
- [ ] Template customization
- [ ] Revision history tracking
- [ ] Auto-increment document numbers

### Technical Debt

- [ ] Move PDF generation to server-side (WeasyPrint or ReportLab)
- [ ] Add integration tests
- [ ] Add error monitoring (Sentry)
- [ ] Cache Gemini responses (Redis)

---

## Security Notes

### Sensitive Data

The tool processes:
- Veteran SSN (last 4 only)
- Veteran name and DOB
- Medical information

**Security Measures:**
- ✅ Portal SSO authentication required
- ✅ No data stored on server (processed in-memory)
- ✅ PDF generated client-side
- ✅ HTTPS only
- ✅ Gemini API calls over encrypted connection

### API Key Protection

```bash
# NEVER commit API keys to git
# NEVER log API keys
# Store only in Mac Mini (Local) config vars
```

---

## Troubleshooting Deployment Issues

### Issue: "ModuleNotFoundError: No module named 'google.generativeai'"

**Solution:**
```bash
# Add to requirements.txt if missing
echo "google-generativeai==0.8.6" >> requirements.txt
git add requirements.txt
git commit -m "Add Gemini SDK"
git push mac-mini main
```

### Issue: "GEMINI_API_KEY not configured"

**Solution:**
```bash
mac-mini config:set GEMINI_API_KEY=<your-key> -a careassist-unified
```

### Issue: Tile not showing on portal

**Solution:**
```bash
# Run tile setup script
mac-mini run python add_va_tile.py -a careassist-unified
```

### Issue: 500 error on /va-plan-of-care

**Check logs:**
```bash
mac-mini logs --tail -a careassist-unified
```

**Common causes:**
- Missing environment variable
- Database connection issue
- Import error in portal_app.py

---

## Testing Checklist

Before marking deployment as successful:

- [ ] Page loads without errors
- [ ] Upload button works
- [ ] Can select PDF file
- [ ] Gemini extracts data (check console)
- [ ] Form fields populate
- [ ] Preview button works
- [ ] Filename is correct format
- [ ] PDF downloads
- [ ] PDF opens correctly
- [ ] PDF has no blank pages
- [ ] HTML download works
- [ ] Mobile responsive
- [ ] Tile visible on portal dashboard

---

## Maintenance Schedule

### Weekly
- Check Gemini API usage/quota
- Review error logs
- Test with new VA forms

### Monthly
- Update dependencies
- Review and optimize Gemini prompts
- Check for Gemini model updates

### Quarterly
- Security audit
- Performance review
- User feedback collection

---

## Support Escalation

### Level 1: User Issues
- Guide user through troubleshooting
- Verify they're using correct VA form
- Check if logged into portal

### Level 2: Technical Issues
- Check Mac Mini (Local) logs
- Verify Gemini API status
- Test locally to reproduce

### Level 3: Critical Failures
- Disable tile if needed
- Rollback deployment
- Contact Gemini support if API issue
- Notify users of downtime

---

**End of Deployment Guide**

For questions: jason@coloradocareassist.com

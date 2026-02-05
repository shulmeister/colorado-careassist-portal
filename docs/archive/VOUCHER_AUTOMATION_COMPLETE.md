# AAA Voucher Automation - Complete Setup

## ✅ SYSTEM STATUS: FULLY OPERATIONAL

### What Was Built

A complete automated voucher reconciliation system that:
1. **Monitors Google Drive** for new voucher PDFs (2025 & 2026 folders)
2. **Extracts data** using Tesseract OCR (same technology as your biz card scanner)
3. **Parses voucher details**:
   - Client names (mapped from 3-letter codes: ROS→Shirley Rosell, BES→Charles Besch, etc.)
   - Voucher numbers (e.g., 12357-ROS8227)
   - Service dates
   - Hours and amounts (rate always $30/hour: 6 hrs = $180, 15 hrs = $450)
   - Invoice dates (calculated as first day of month after voucher expires)
4. **Updates two systems**:
   - Internal portal database (https://portal.coloradocareassist.com/vouchers)
   - Google Sheet for reconciliation

### How to Use

#### Manual Sync
1. Go to the Voucher page in your portal
2. Click "🔄 Sync from Drive" button
3. System will process any new vouchers from the last 24 hours
4. Review the results and confirm new vouchers were added correctly

#### What Happens During Sync
- Scans Google Drive folders for new vouchers (PDF files)
- Downloads and converts PDFs to images
- Runs OCR to extract text
- Parses:
  - Client name from code (ROS, BES, BRN, etc.)
  - Voucher number (format: 12345-ABC1234)
  - Service dates
  - Hours × $30 = Amount
  - Invoice date (1st of month after service ends)
- Saves to portal database
- Updates Google Sheet

### Technical Details

#### OCR Technology
- **Primary**: Tesseract OCR (open-source, same as your scanners)
- **Fallback**: Google Cloud Vision API (if enabled)
- **Accuracy**: Handles "Authorized Units of Service 6.0@$30" format

#### Client Code Mapping
```
ROS → Shirley Rosell
BES → Charles Besch  
BRO → Christine Brock
BRN → Margot Brown
BUR → Herbert Burley
THO → Mildred Tomkins
FLE → Jessica Whelehan Trow (Ann Fletcher)
JON → Joanne Jones
BEC → Judy Tuetken
LIP → Betty Jean Lipsy
GRI → Mary Poole
SAL → Marlene Morin
RAY → Margarita Rubio
LIG → Dawn Light (Ed Witt)
```

#### Amount Calculation
- Rate: **$30/hour** (fixed)
- Common amounts:
  - 6 hours = $180
  - 12 hours = $360
  - 15 hours = $450

#### Invoice Date Logic
- Service dates: Nov 1 - Nov 30
- Invoice date: Dec 1
- Rule: First day of month AFTER service period ends

### Environment Variables (Mac Mini)

Required for sync to work:
```
GOOGLE_DRIVE_VOUCHER_FOLDER_ID = 11dehnpNV-QfwdU_6DHXAuul8v9KW2mD2
GOOGLE_SHEETS_VOUCHER_ID = 1f0lk54-zyAnZd2Ok9KNezHgTjYeuH4zCwaLASGjMZAM
GOOGLE_SERVICE_ACCOUNT_JSON = {service account JSON key}
GOOGLE_CLOUD_PROJECT_ID = cca-website-c822e
```

### Files Modified/Created

#### Core Sync Logic
- `voucher_sync_service.py` - Main OCR and parsing logic
- `portal_app.py` - API endpoints for sync and status

#### Database
- `portal_models.py` - Voucher model with all fields

#### Frontend
- `templates/vouchers.html` - Voucher list page with sync button

#### Configuration
- `requirements.txt` - Added pytesseract, pdf2image, google APIs
- `Aptfile` - System packages (tesseract-ocr, poppler-utils)

#### Documentation
- `QUICK_START_VOUCHER_SYNC.md` - Quick start guide
- `VOUCHER_SYNC_SETUP.md` - Detailed setup instructions

### Key Features

✅ **Automatic duplicate detection** - Won't add same voucher twice
✅ **Handles PDF and image files**
✅ **Works with Shared Drives** 
✅ **Extracts from complex formats** - "Units of Service 6.0@$30"
✅ **Client name mapping** - Converts codes to full names
✅ **Smart amount detection** - Ignores $30 hourly rate, calculates from hours
✅ **Invoice date calculation** - First of month after service ends
✅ **Two-way sync** - Portal database + Google Sheet

### Troubleshooting

#### Sync finds 0 files
- Check that service account has access to the Drive folders
- Verify `GOOGLE_DRIVE_VOUCHER_FOLDER_ID` is correct
- Make sure files were added in last 24 hours (or increase `hours_back` parameter)

#### OCR extracts no text
- Ensure `tesseract-ocr` is installed (check Aptfile)
- Verify PDF is text-based or scanned image (not corrupted)
- Check Mac Mini logs for specific OCR errors

#### Wrong amounts
- System looks for "Units of Service X@" or "X hours"
- Falls back to common amounts ($180, $450, $360)
- Check logs to see what was extracted

#### Wrong client names
- Add new client codes to `CLIENT_CODE_MAP` in `voucher_sync_service.py`
- Redeploy after adding new mappings

### Future Enhancements (Optional)

- [ ] Automatic daily sync (cron job)
- [ ] Email notifications for new vouchers
- [ ] Dashboard widget showing recent vouchers
- [ ] Bulk edit capabilities
- [ ] Export to CSV/Excel

### Deployment Status

**Last Deployed**: v94
**Status**: ✅ Production Ready
**URL**: https://portal.coloradocareassist.com/vouchers

---

## Quick Reference

**Sync Button**: Portal → Vouchers → "🔄 Sync from Drive"
**View Logs**: `tail -f ~/logs/gigi-unified.log --app portal-coloradocareassist`
**Status Check**: `/api/vouchers/sync/status` endpoint

Everything is locked down, clean, and ready to go! 🚀


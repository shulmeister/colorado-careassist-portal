# Quick Start: Voucher Auto-Sync

Your voucher folders are ready! Here's how to enable automatic OCR syncing.

## Your Folder IDs

✅ **2025 Vouchers**: `11dehnpNV-QfwdU_6DHXAuul8v9KW2mD2`  
📅 **2026 Vouchers**: `10xYKU5E3tQy1WvlOELJRjkzyRotHClgO`

Currently configured for 2025. When 2026 starts, just update one environment variable!

## 5-Minute Setup

### Step 1: Create Google Cloud Service Account

1. **Go to Google Cloud Console**: https://console.cloud.google.com/
2. **Create a project** (or use existing): Name it "Colorado CareAssist"
3. **Enable 3 APIs**:
   - Google Drive API: https://console.cloud.google.com/apis/library/drive.googleapis.com
   - Google Sheets API: https://console.cloud.google.com/apis/library/sheets.googleapis.com
   - Cloud Vision API: https://console.cloud.google.com/apis/library/vision.googleapis.com
   
4. **Create Service Account**:
   - Go to: https://console.cloud.google.com/iam-admin/serviceaccounts
   - Click "+ CREATE SERVICE ACCOUNT"
   - Name: `voucher-sync-service`
   - Role: **Editor** (or Viewer for Drive + Editor for Sheets)
   - Click "DONE"

5. **Download JSON Key**:
   - Click on the service account
   - Go to "KEYS" tab
   - "ADD KEY" → "Create new key" → Choose "JSON"
   - Save the file that downloads

### Step 2: Share Your Resources

#### Share 2025 Voucher Folder
1. Open: https://drive.google.com/drive/folders/11dehnpNV-QfwdU_6DHXAuul8v9KW2mD2
2. Click "Share"
3. Add your service account email: `voucher-sync-service@your-project.iam.gserviceaccount.com`
4. Permission: **Viewer**
5. Send

#### Share 2026 Voucher Folder (for future)
1. Open: https://drive.google.com/drive/folders/10xYKU5E3tQy1WvlOELJRjkzyRotHClgO
2. Repeat same steps as above

#### Share Google Sheets
1. Open: https://docs.google.com/spreadsheets/d/1f0lk54-zyAnZd2Ok9KNezHgTjYeuH4zCwaLASGjMZAM/edit
2. Click "Share"
3. Add same service account email
4. Permission: **Editor** (so it can add rows)
5. Send

### Step 3: Set Heroku Environment Variables

```bash
# Set 2025 voucher folder (current)
heroku config:set GOOGLE_DRIVE_VOUCHER_FOLDER_ID="11dehnpNV-QfwdU_6DHXAuul8v9KW2mD2" --app portal-coloradocareassist

# Set Google Sheets ID (already correct)
heroku config:set GOOGLE_SHEETS_VOUCHER_ID="1f0lk54-zyAnZd2Ok9KNezHgTjYeuH4zCwaLASGjMZAM" --app portal-coloradocareassist

# Set your Google Cloud project ID (from console)
heroku config:set GOOGLE_CLOUD_PROJECT_ID="your-project-id-here" --app portal-coloradocareassist

# Set Service Account JSON (copy entire contents of downloaded JSON file)
heroku config:set GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"your-project",...}' --app portal-coloradocareassist
```

**Or via Heroku Dashboard**:
1. Go to: https://dashboard.heroku.com/apps/portal-coloradocareassist/settings
2. Click "Reveal Config Vars"
3. Add these 4 variables with values above

### Step 4: Test It!

1. Go to: https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/vouchers
2. Click "🔄 Sync from Drive"
3. Watch it process your vouchers!

The system will:
- Find new PDFs in your Drive folder
- Extract text using OCR
- Parse voucher details
- Save to portal database
- **Update your Google Sheets automatically**

### Step 5: Enable Hourly Auto-Sync (Optional)

Set up automatic hourly checks:

```bash
# Install Heroku Scheduler
heroku addons:create scheduler:standard --app portal-coloradocareassist

# Open scheduler dashboard
heroku addons:open scheduler --app portal-coloradocareassist
```

In the dashboard:
- Click "Add Job"
- Schedule: **Every hour at :00**
- Command: `python -c "from voucher_sync_service import run_sync; run_sync(hours_back=2)"`
- Save

Now it checks every hour automatically!

## Switching to 2026 Folder

When 2026 starts, just update one variable:

```bash
heroku config:set GOOGLE_DRIVE_VOUCHER_FOLDER_ID="10xYKU5E3tQy1WvlOELJRjkzyRotHClgO" --app portal-coloradocareassist
```

That's it! The system will start monitoring the 2026 folder.

## How It Works

1. **Detection**: Checks your Drive folder for new PDFs
2. **OCR**: Google Vision API extracts all text from the voucher
3. **Parsing**: AI identifies:
   - Client name
   - Voucher number (e.g., "Voucher_11341")
   - Date range
   - Amount
   - Invoice date
4. **Dual Save**: 
   - Portal database → shows on `/vouchers` page
   - Google Sheets → adds row to reconciliation spreadsheet

## Voucher Format

Your vouchers follow this pattern:
- **Filename**: `Voucher_11341_Voucher - Homemaker.pdf`
- **Date Modified**: Shows when added to Drive
- **Size**: ~247-249 KB PDFs

The OCR will extract the voucher details from the PDF content automatically!

## Testing with Your Recent Vouchers

I can see you have recent vouchers from August:
- `Voucher_12014_Voucher - Homemaker (1).pdf` (Aug 5)
- `Voucher_12014_Voucher - Homemaker.pdf` (Jul 28)
- `Voucher_12015_Voucher - Homemaker.pdf` (Jul 28)

Once configured, click "Sync from Drive" and these will be processed if they're not already in the system!

## Troubleshooting

**"No files found"**
- Verify folder ID is correct
- Check service account has Viewer access to the folder

**"Permission denied"**
- Ensure all 3 APIs are enabled in Google Cloud
- Verify service account JSON is correctly pasted

**"OCR failed"**
- PDF might be scanned image - OCR works best with clear text
- Check Vision API is enabled

## Support

Check logs anytime:
```bash
heroku logs --tail --app portal-coloradocareassist
```

Need help? Just ask! 🚀

## Cost

Google Cloud Vision API:
- **First 1,000 OCR requests/month: FREE**
- After that: ~$1.50 per 1,000

With ~5-10 vouchers per day, you'll stay in the free tier! 💰


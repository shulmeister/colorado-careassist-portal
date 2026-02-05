# Voucher Auto-Sync Setup Guide

This guide will help you set up automatic voucher syncing from Google Drive using OCR.

## Overview

The system will:
1. Monitor your Google Drive folder for new voucher images
2. Extract text from vouchers using Google Vision API (OCR)
3. Parse voucher details (client name, number, dates, amounts)
4. Save to your portal database
5. Update your Google Sheets reconciliation spreadsheet

## Prerequisites

You'll need:
- Google Cloud Project with billing enabled
- Google Drive folder containing vouchers
- Your existing Google Sheets reconciliation spreadsheet
- Admin access to Google Cloud Console

## Step 1: Create Google Cloud Service Account

### 1.1 Go to Google Cloud Console
Visit: https://console.cloud.google.com/

### 1.2 Create or Select a Project
- If you don't have a project, create one
- Name it something like "Colorado CareAssist Portal"

### 1.3 Enable Required APIs
Enable these APIs for your project:
1. **Google Drive API**: https://console.cloud.google.com/apis/library/drive.googleapis.com
2. **Google Sheets API**: https://console.cloud.google.com/apis/library/sheets.googleapis.com
3. **Cloud Vision API**: https://console.cloud.google.com/apis/library/vision.googleapis.com

Click "Enable" for each one.

### 1.4 Create Service Account
1. Go to: https://console.cloud.google.com/iam-admin/serviceaccounts
2. Click "+ CREATE SERVICE ACCOUNT"
3. Name: `voucher-sync-service`
4. Description: "Service account for voucher OCR and sync"
5. Click "CREATE AND CONTINUE"
6. Grant roles:
   - **Editor** (or more specifically: Viewer for Drive, Editor for Sheets)
7. Click "DONE"

### 1.5 Create and Download Key
1. Click on the service account you just created
2. Go to the "KEYS" tab
3. Click "ADD KEY" → "Create new key"
4. Choose **JSON** format
5. Click "CREATE"
6. The key file will download automatically
7. **Keep this file safe!** It contains sensitive credentials

## Step 2: Share Google Drive Folder

1. Open your Google Drive voucher folder
2. Click "Share" or the share icon
3. Add the service account email (looks like: `voucher-sync-service@your-project.iam.gserviceaccount.com`)
4. Give it **Viewer** access
5. Click "Send"

## Step 3: Share Google Sheets Spreadsheet

1. Open your AAA Voucher Reconciliation spreadsheet
2. Click "Share"
3. Add the same service account email
4. Give it **Editor** access (so it can add new rows)
5. Click "Send"

## Step 4: Get Your Resource IDs

### 4.1 Get Google Drive Folder ID
Open your voucher folder in Google Drive. The URL will look like:
```
https://drive.google.com/drive/folders/1abc...XYZ
```
Copy the ID after `/folders/` → `1abc...XYZ`

### 4.2 Get Google Sheets ID
Open your reconciliation spreadsheet. The URL will look like:
```
https://docs.google.com/spreadsheets/d/1f0lk54-zyAnZd2Ok9KNezHgTjYeuH4zCwaLASGjMZAM/edit
```
The ID is between `/d/` and `/edit` → `1f0lk54-zyAnZd2Ok9KNezHgTjYeuH4zCwaLASGjMZAM`

### 4.3 Get Google Cloud Project ID
In Google Cloud Console, you'll see your project ID at the top (or in the project selector).
It looks like: `your-project-123456`

## Step 5: Set Mac Mini Environment Variables

We need to add 4 environment variables to Mac Mini:

### Option A: Via Mac Mini Dashboard
1. Go to https://dashboard.mac-mini.com/apps/portal-coloradocareassist/settings
2. Click "Reveal Config Vars"
3. Add these variables:

| Key | Value |
|-----|-------|
| `GOOGLE_DRIVE_VOUCHER_FOLDER_ID` | Your Drive folder ID from Step 4.1 |
| `GOOGLE_SHEETS_VOUCHER_ID` | Your Sheets ID from Step 4.2 (already set: `1f0lk54-zyAnZd2Ok9KNezHgTjYeuH4zCwaLASGjMZAM`) |
| `GOOGLE_CLOUD_PROJECT_ID` | Your project ID from Step 4.3 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | **Entire contents** of the JSON key file from Step 1.5 (copy and paste all of it) |

### Option B: Via Mac Mini CLI
```bash
# Set Drive folder ID
mac-mini config:set GOOGLE_DRIVE_VOUCHER_FOLDER_ID="your-folder-id" --app portal-coloradocareassist

# Set Sheets ID (if different from default)
mac-mini config:set GOOGLE_SHEETS_VOUCHER_ID="1f0lk54-zyAnZd2Ok9KNezHgTjYeuH4zCwaLASGjMZAM" --app portal-coloradocareassist

# Set Project ID
mac-mini config:set GOOGLE_CLOUD_PROJECT_ID="your-project-id" --app portal-coloradocareassist

# Set Service Account JSON (paste entire contents)
mac-mini config:set GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"..."}' --app portal-coloradocareassist
```

## Step 6: Set Up Automated Syncing

We can use Mac Mini Scheduler to automatically sync vouchers every hour.

### 6.1 Install Mac Mini Scheduler
```bash
mac-mini addons:create scheduler:standard --app portal-coloradocareassist
```

### 6.2 Add Sync Job
1. Open scheduler: `mac-mini addons:open scheduler --app portal-coloradocareassist`
2. Click "Add Job"
3. Set schedule: **Every hour at :00**
4. Command: `python -c "from voucher_sync_service import run_sync; run_sync(hours_back=2)"`
5. Click "Save Job"

This will check for new vouchers every hour (looking back 2 hours to catch any missed files).

## Step 7: Test the Setup

### 7.1 Manual Test via Portal
1. Go to https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com/vouchers
2. Click "🔄 Sync from Drive"
3. It should find and process your two new vouchers

### 7.2 Manual Test via Mac Mini CLI
```bash
mac-mini run python voucher_sync_service.py --app portal-coloradocareassist
```

This will run a sync and show you detailed output.

## How It Works

1. **Detection**: System checks your Drive folder for new images
2. **OCR**: Google Vision API extracts text from the image
3. **Parsing**: AI parses the text to extract:
   - Client name
   - Voucher number (e.g., "12345-ABC1234")
   - Date range (e.g., "Nov 1 - Nov 30")
   - Invoice date
   - Amount ($180, $360, $450, etc.)
   - Status
4. **Storage**: Data is saved to both:
   - Portal database (for the /vouchers page)
   - Google Sheets (for your reconciliation spreadsheet)

## Voucher Image Requirements

For best OCR results, vouchers should:
- Be clear, high-resolution images (PNG, JPG, or PDF)
- Have good lighting and contrast
- Include the voucher number prominently
- Show the date range and amount clearly
- Not be rotated or skewed

## Troubleshooting

### "No files found"
- Check that the Drive folder ID is correct
- Verify the service account has Viewer access to the folder
- Confirm vouchers are in the root of that folder (not subfolders)

### "OCR failed" or "No text extracted"
- Image quality might be too low
- Try a clearer scan or photo
- Check that the image format is supported

### "Failed to parse data"
- Voucher format might not match expected patterns
- Check the logs to see what text was extracted
- You can manually add the voucher and we'll improve the parser

### "Permission denied" errors
- Verify service account has proper access
- Check that APIs are enabled in Google Cloud
- Confirm the JSON key is correctly set in Mac Mini

## Support

If you encounter issues:
1. Check Mac Mini logs: `mac-mini logs --tail --app portal-coloradocareassist`
2. Try a manual sync to see detailed error messages
3. Verify all environment variables are set correctly

## Security Notes

⚠️ **Important**:
- Keep the service account JSON key secure
- Never commit it to git
- Only store it in Mac Mini environment variables
- The service account has limited permissions (read-only on Drive, editor on Sheets only)
- Revoke the key immediately if it's compromised

## Cost Estimates

Google Cloud Vision API pricing:
- First 1,000 images/month: **FREE**
- After that: ~$1.50 per 1,000 images

For typical usage (5-10 vouchers per day), you'll stay well within the free tier.

## Next Steps

Once set up, the system will:
- ✅ Automatically sync every hour
- ✅ Process new vouchers with OCR
- ✅ Update both portal and Google Sheets
- ✅ Notify you of any errors

You can always manually trigger a sync by clicking "🔄 Sync from Drive" in the portal!


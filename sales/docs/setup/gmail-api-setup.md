# Gmail API Setup Guide

## Prerequisites
- Google Workspace Admin access
- Service account with domain-wide delegation enabled

## Environment Variables Required

You need to set these environment variables in Heroku (or `.env` for local):

1. **GMAIL_SERVICE_ACCOUNT_EMAIL**: The service account email
   - Example: `github@marketing-dashboard-463608.iam.gserviceaccount.com`

2. **GMAIL_SERVICE_ACCOUNT_KEY**: The full JSON key for the service account
   - This should be the complete JSON object as a string (not just the key ID)
   - Format: `{"type":"service_account","project_id":"...","private_key":"..."}`

3. **GMAIL_USER_EMAIL** (optional): The email address to impersonate
   - Default: `maryssa@coloradocareassist.com`
   - This is the user whose sent emails will be counted

## Setup Steps

### 1. Get Service Account JSON Key

If you have the service account email and key ID, you need to:
- Go to Google Cloud Console
- Navigate to IAM & Admin > Service Accounts
- Find your service account (github@marketing-dashboard-463608.iam.gserviceaccount.com)
- Click "Keys" > "Add Key" > "Create new key" > "JSON"
- Download the JSON file
- Copy the entire JSON content and set it as `GMAIL_SERVICE_ACCOUNT_KEY` (as a JSON string)

### 2. Enable Domain-Wide Delegation

1. In Google Cloud Console, go to IAM & Admin > Service Accounts
2. Click on your service account
3. Check "Enable Google Workspace Domain-wide Delegation"
4. Note the Client ID (the unique ID you provided: 107287022993112478696)

### 3. Configure in Google Admin Console

1. Go to Google Admin Console (admin.google.com)
2. Navigate to Security > API Controls > Domain-wide Delegation
3. Click "Add new"
4. Enter the Client ID: `107287022993112478696`
5. Add the OAuth scope: `https://www.googleapis.com/auth/gmail.readonly`
6. Click "Authorize"

### 4. Enable Gmail API

1. Go to Google Cloud Console
2. Navigate to APIs & Services > Library
3. Search for "Gmail API"
4. Click "Enable"

### 5. Set Environment Variables

In Heroku:
```bash
heroku config:set GMAIL_SERVICE_ACCOUNT_EMAIL="github@marketing-dashboard-463608.iam.gserviceaccount.com"
heroku config:set GMAIL_SERVICE_ACCOUNT_KEY='{"type":"service_account",...}'  # Full JSON string
heroku config:set GMAIL_USER_EMAIL="maryssa@coloradocareassist.com"
```

### 6. Test the Connection

Once deployed, you can test by:
1. Opening the dashboard
2. The new "Emails Sent - Last 7 Days" KPI should show data after the first sync
3. Or manually trigger sync via API: `POST /api/sync-gmail-emails`

## Notes

- The email count is cached in the database to avoid API quota limits
- Sync manually via the `/api/sync-gmail-emails` endpoint when needed
- The count reflects emails sent in the last 7 days from the specified user's Gmail account

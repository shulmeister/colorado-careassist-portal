# Quick Gmail API Setup

## What I Need From You

You mentioned you already enabled the Gmail API, which is great! Now I need:

1. **The full Service Account JSON Key file** - Not just the key ID, but the complete JSON file you download from Google Cloud Console

## What I'll Do

Once you provide the JSON key, I'll:
1. Set all Heroku environment variables
2. Test the connection
3. Run the first sync
4. Verify everything works

## Getting the JSON Key

1. Go to: https://console.cloud.google.com/iam-admin/serviceaccounts
2. Find: `github@marketing-dashboard-463608.iam.gserviceaccount.com`
3. Click on it → "Keys" tab → "Add Key" → "Create new key"
4. Choose "JSON" format → Download
5. Open the downloaded file and copy the entire contents

## Setting It Up

You have two options:

### Option 1: Use the setup script (easiest)
```bash
./setup_gmail.sh
```
Then paste the JSON key when prompted.

### Option 2: Manual setup via Heroku CLI
```bash
# First, get the JSON key content (replace with your actual JSON)
heroku config:set GMAIL_SERVICE_ACCOUNT_EMAIL="github@marketing-dashboard-463608.iam.gserviceaccount.com"
heroku config:set GMAIL_SERVICE_ACCOUNT_KEY='{"type":"service_account","project_id":"marketing-dashboard-463608",...}'
heroku config:set GMAIL_USER_EMAIL="maryssa@coloradocareassist.com"

# Test it
heroku run python3 check_gmail_setup.py
```

## Domain-Wide Delegation Setup

Make sure this is done in Google Admin Console:

1. Go to: https://admin.google.com
2. Security → API Controls → Domain-wide Delegation
3. Add new:
   - Client ID: `107287022993112478696`
   - OAuth Scopes: `https://www.googleapis.com/auth/gmail.readonly`
   - Authorize

## After Setup

Once configured, the dashboard will automatically show "Emails Sent - Last 7 Days" KPI.

To manually sync emails:
```bash
heroku run python3 sync_gmail_emails.py
```

To check setup status:
```bash
heroku run python3 check_gmail_setup.py
```

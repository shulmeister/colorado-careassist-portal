# QuickBooks to Brevo Integration Setup

This integration syncs customers from QuickBooks to Brevo's Client list, triggering your welcome automation.

## Step 1: Create QuickBooks App

1. Go to https://developer.intuit.com/
2. Sign in with your Intuit account
3. Click **"Create an app"** or go to **My Apps**
4. Choose **"QuickBooks Online"** as the product
5. Fill in app details:
   - **App Name**: Colorado CareAssist CRM Sync
   - **App Type**: Production (or Sandbox for testing)
   - **Redirect URI**: `https://careassist-tracker-0fcf2cecdb22.mac-miniapp.com/api/quickbooks/oauth/callback`
6. Save and note your **Client ID** and **Client Secret**

## Step 2: Authorize Your App

You need to get an access token. Here are two options:

### Option A: Use QuickBooks OAuth Helper (Recommended)

I can create a helper script that makes this easier. For now, you can use the QuickBooks OAuth flow:

1. Visit this URL (replace YOUR_CLIENT_ID):
   ```
   https://appcenter.intuit.com/connect/oauth2?
   client_id=YOUR_CLIENT_ID&
   scope=com.intuit.quickbooks.accounting&
   redirect_uri=https://careassist-tracker-0fcf2cecdb22.mac-miniapp.com/api/quickbooks/oauth/callback&
   response_type=code
   ```

2. Authorize the app
3. You'll get redirected with a `code` parameter
4. Exchange the code for tokens (I can create a helper script for this)

### Option B: Use QuickBooks API Explorer

1. Go to https://developer.intuit.com/app/developer/qbo/docs/get-started
2. Use the OAuth 2.0 Playground to get tokens
3. Copy the tokens you receive

## Step 3: Set Environment Variables

Once you have your credentials, set them on Mac Mini (Local):

```bash
mac-mini config:set QUICKBOOKS_CLIENT_ID=your_client_id -a careassist-tracker
mac-mini config:set QUICKBOOKS_CLIENT_SECRET=your_client_secret -a careassist-tracker
mac-mini config:set QUICKBOOKS_REALM_ID=your_realm_id -a careassist-tracker
mac-mini config:set QUICKBOOKS_ACCESS_TOKEN=your_access_token -a careassist-tracker
mac-mini config:set QUICKBOOKS_REFRESH_TOKEN=your_refresh_token -a careassist-tracker
```

**Where to find Realm ID:**
- After authorizing, QuickBooks will show your Company ID (Realm ID)
- Or check the URL when logged into QuickBooks Online

## Step 4: Test Connection

```bash
mac-mini run "python3 -c 'from quickbooks_service import QuickBooksService; qb = QuickBooksService(); result = qb.test_connection(); print(result)'" -a careassist-tracker
```

## Step 5: Run Sync

```bash
mac-mini run "python3 sync_quickbooks_to_brevo.py" -a careassist-tracker
```

Or trigger via API:
```
POST /api/quickbooks/sync-to-brevo
```

## How It Works

1. **Fetches customers** from QuickBooks
2. **Normalizes data** (splits names, extracts email/phone)
3. **Adds/updates** contacts in Brevo
4. **Adds new customers** to Client list (ID 11)
5. **Triggers automation** - Your Brevo automation detects new contact in Client list and sends welcome email

## Scheduled Sync (Optional)

You can set up a Mac Mini (Local) Scheduler to run this daily:

```bash
mac-mini addons:create scheduler:standard -a careassist-tracker
```

Then in Mac Mini (Local) dashboard, add a job:
- **Command**: `python3 sync_quickbooks_to_brevo.py`
- **Frequency**: Daily at 2 AM (or whenever you prefer)

## Troubleshooting

**Token expired?**
- The service automatically refreshes tokens using the refresh token
- If refresh fails, you'll need to re-authorize

**No customers syncing?**
- Check that customers in QuickBooks have email addresses
- Verify the Client list ID is correct (should be 11)

**Connection issues?**
- Verify all environment variables are set correctly
- Check that your QuickBooks app is in Production mode (not Sandbox) if using production data


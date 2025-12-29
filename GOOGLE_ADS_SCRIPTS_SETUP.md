# Google Ads Scripts Setup Guide

**This is the recommended approach** - Google's own guidance says scripts are better for reporting without managing infrastructure.

## ✅ What We're Doing

Instead of using the full Google Ads API (which requires developer tokens, OAuth flows, etc.), we're using **Google Ads Scripts** that run inside Google Ads and send data to our backend via webhook.

## 📋 Setup Steps

### 1. Copy the Script File

The script file is located at: `google_ads_script.js` in the project root.

### 2. Set Webhook Secret (Optional but Recommended)

```bash
heroku config:set GOOGLE_ADS_WEBHOOK_SECRET=your-random-secret-here --app portal-coloradocareassist
```

Generate a random secret:
```bash
openssl rand -hex 32
```

### 3. Update the Script

1. Open `google_ads_script.js`
2. Update line 15 with your webhook URL (should already be correct):
   ```javascript
   const WEBHOOK_URL = 'https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/api/marketing/google-ads/webhook';
   ```
3. Update line 19 with the same secret you set in step 2:
   ```javascript
   const WEBHOOK_SECRET = 'your-random-secret-here';
   ```

### 4. Install Script in Google Ads

1. Go to **Google Ads** → https://ads.google.com
2. Click **Tools & Settings** (wrench icon) in the top right
3. Under **Bulk Actions**, click **Scripts**
4. Click the **+** button to create a new script
5. Give it a name: "Marketing Dashboard Sync"
6. Copy and paste the entire contents of `google_ads_script.js`
7. Click **Preview** to test (it will show you what data it would send)
8. If preview looks good, click **Save**

### 5. Schedule the Script

1. In the script editor, click **Authorize** (first time only - grants permissions)
2. Click **Schedule** or the calendar icon
3. Set to run **Daily** (or however often you want updates)
4. Choose a time (e.g., 2 AM)
5. Click **Save**

### 6. Test the Script

1. Click **Preview** to test the script
2. Check the logs to see if it successfully sends data
3. Check your backend logs:
   ```bash
   heroku logs --tail --app portal-coloradocareassist | grep "Google Ads webhook"
   ```

## 🔍 How It Works

1. **Script runs** in Google Ads (scheduled daily)
2. **Fetches metrics** using Google Ads Query Language (GAQL)
3. **POSTs data** to your backend webhook endpoint
4. **Backend caches** the data (in-memory for now, can upgrade to Redis/DB later)
5. **Dashboard displays** the cached data

## 📊 What Data Is Collected

- Account-level metrics (spend, clicks, impressions, conversions, ROAS)
- Campaign performance
- Quality Scores
- Search Terms
- Device Performance (Desktop/Mobile/Tablet)
- Daily breakdown

## 🔄 Data Refresh

- Script runs on schedule (default: daily)
- Data is cached for 24 hours
- Dashboard automatically uses cached data when available
- Falls back to placeholder data if cache expired or script hasn't run

## 🐛 Troubleshooting

### Script Fails to Run
- Check script logs in Google Ads
- Verify webhook URL is accessible
- Check that script has proper permissions

### No Data in Dashboard
- Verify script ran successfully (check Google Ads script logs)
- Check backend logs: `heroku logs --tail | grep webhook`
- Verify webhook secret matches in script and backend
- Try running script manually with "Preview" button

### Data Looks Wrong
- Check date ranges match between script and dashboard request
- Verify script is using correct date range (last 30 days by default)
- Check Google Ads account has data for the date range

## 🔐 Security Notes

- Webhook secret is optional but recommended
- Script runs with permissions of the Google Ads account owner
- No API tokens or OAuth flows needed
- Script only sends data, never modifies campaigns

## 📝 Script Customization

You can modify the script to:
- Change date range (currently last 30 days)
- Add more metrics
- Filter campaigns
- Change data format

Just remember to update the webhook endpoint handling if you change the data format.

## ✅ Benefits Over API

- ✅ No developer token approval needed
- ✅ No OAuth refresh token management
- ✅ Simpler setup (just copy/paste script)
- ✅ Runs on Google's infrastructure
- ✅ Scheduled automatically
- ✅ Google-recommended approach for reporting

## 🎉 That's It!

Once the script is running, your Google Ads data will automatically appear in the marketing dashboard. No API tokens, no OAuth flows, no developer approvals needed!


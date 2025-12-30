# Google Ads API Setup Guide

**Customer ID:** `6780818726053668` ✅ (configured)

## ✅ What's Already Done

1. ✅ **Customer ID configured** - `GOOGLE_ADS_CUSTOMER_ID=6780818726053668`
2. ✅ **OAuth credentials** - Using existing `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
3. ✅ **Service code** - Ready to use existing OAuth credentials

## ❌ What's Still Needed

### 1. Google Ads Developer Token (Required)

**What it is:** A special token that authorizes your app to access the Google Ads API.

**How to get it:**
1. Go to [Google Ads API Center](https://ads.google.com/aw/apicenter)
2. Sign in with the Google account that has access to your Google Ads account
3. Click **"Apply for API Access"**
4. Fill out the application form:
   - Application Name: Colorado CareAssist Marketing Dashboard
   - Application Type: Web Application
   - Use Case: Marketing Analytics & Reporting
   - Website: https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com
5. Submit the application
6. **Wait for approval** (usually 24-48 hours)
7. Once approved, copy your Developer Token

**Set it once you have it:**
```bash
heroku config:set GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token_here --app portal-coloradocareassist
```

### 2. Google Ads Refresh Token (Required)

**What it is:** An OAuth refresh token that allows the app to access Google Ads data on behalf of your account.

**How to get it:**

The OAuth flow for Google Ads requires specific scopes. You'll need to:

1. **Add Google Ads scopes to your OAuth configuration:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to your project (or the one with your OAuth credentials)
   - Go to **APIs & Services** → **Credentials**
   - Edit your OAuth 2.0 Client ID
   - Add these **Authorized redirect URIs**:
     ```
     https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/api/google-ads/callback
     ```

2. **Complete the OAuth flow:**
   - Visit: `https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/api/google-ads/auth`
   - This will redirect you to Google to authorize the app
   - Grant access to Google Ads API
   - You'll be redirected back and the refresh token will be saved

**Or manually generate a refresh token:**

1. Visit this URL (replace `YOUR_CLIENT_ID` with your `GOOGLE_CLIENT_ID`):
   ```
   https://accounts.google.com/o/oauth2/v2/auth?client_id=YOUR_CLIENT_ID&redirect_uri=https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/api/google-ads/callback&response_type=code&scope=https://www.googleapis.com/auth/adwords&access_type=offline&prompt=consent
   ```

2. Authorize the app

3. Copy the `code` parameter from the redirect URL

4. Exchange the code for tokens using this curl command (replace placeholders):
   ```bash
   curl -X POST https://oauth2.googleapis.com/token \
     -d "client_id=YOUR_CLIENT_ID" \
     -d "client_secret=YOUR_CLIENT_SECRET" \
     -d "code=AUTHORIZATION_CODE_FROM_STEP_3" \
     -d "grant_type=authorization_code" \
     -d "redirect_uri=https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/api/google-ads/callback"
   ```

5. Copy the `refresh_token` from the response

6. Set it in Heroku:
   ```bash
   heroku config:set GOOGLE_ADS_REFRESH_TOKEN=your_refresh_token_here --app portal-coloradocareassist
   ```

## 🔧 Quick Status Check

After setting up both tokens, verify the configuration:

```bash
heroku config --app portal-coloradocareassist | grep GOOGLE_ADS
```

You should see:
- ✅ `GOOGLE_ADS_CUSTOMER_ID=6780818726053668`
- ✅ `GOOGLE_ADS_DEVELOPER_TOKEN=...` (your token)
- ✅ `GOOGLE_ADS_REFRESH_TOKEN=...` (your refresh token)

## 📝 Notes

- The service automatically uses `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` - no need to set separate Google Ads OAuth credentials
- The Customer ID format is normalized (dashes removed automatically)
- Developer Token approval can take 24-48 hours
- Refresh tokens don't expire (unless revoked)
- If you have a Manager Account (MCC), you can optionally set `GOOGLE_ADS_LOGIN_CUSTOMER_ID`

## 🚀 Testing

Once both tokens are set, the Google Ads metrics should start appearing in the marketing dashboard at:
- `/marketing` → Paid Media tab
- Real spend, clicks, conversions, ROAS, etc.
- Quality Scores, Search Terms, Device Performance (new features!)


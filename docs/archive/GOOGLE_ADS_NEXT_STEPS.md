# Google Ads API - Next Steps (Developer Token Set ✅)

## ✅ Completed
- **Developer Token Set**: `-fWctng9yGnr3fiv6I4gXQ` ✅

## ⚠️ Still Needed
- **OAuth Refresh Token** - Required for API authentication

---

## Current Status

You've successfully set the developer token! However, the Google Ads API also requires OAuth 2.0 authentication with a refresh token. The service will check for the refresh token in two places:

1. **Environment Variable**: `GOOGLE_ADS_REFRESH_TOKEN`
2. **Database**: OAuthToken table (service="google-ads")

---

## Option 1: Use OAuth Playground (Easiest - Recommended)

This is the quickest way to get a refresh token:

1. **Go to OAuth 2.0 Playground:**
   - Visit: https://developers.google.com/oauthplayground/

2. **Configure OAuth Playground:**
   - Click the gear icon (⚙️) in the top right
   - Check "Use your own OAuth credentials"
   - Enter your OAuth Client ID: (check Mac Mini config for `GOOGLE_CLIENT_ID`)
   - Enter your OAuth Client Secret: (check Mac Mini config for `GOOGLE_CLIENT_SECRET`)

3. **Select Scope:**
   - In the left panel, find and select:
   - `https://www.googleapis.com/auth/adwords`
   - Click "Authorize APIs"

4. **Authorize:**
   - Sign in with your Google account (the one with access to Google Ads)
   - Grant the requested permissions

5. **Exchange for Tokens:**
   - Click "Exchange authorization code for tokens"
   - You'll see an access token and a **refresh token**

6. **Copy the Refresh Token:**
   - Copy the refresh token value (it's a long string)

7. **Set on Mac Mini:**
   ```bash
   mac-mini config:set GOOGLE_ADS_REFRESH_TOKEN="your_refresh_token_here" -a portal-coloradocareassist
   ```

---

## Option 2: Use Connections Page (If Available)

If your portal has a Connections page with Google Ads OAuth:

1. **Go to Connections Page:**
   - Visit: https://portal.coloradocareassist.com/connections
   - (or check if it exists at a different route)

2. **Click "Connect" for Google Ads:**
   - This should initiate the OAuth flow
   - Authorize the connection
   - The refresh token will be stored in the database automatically

**Note:** Make sure the OAuth callback route exists:
- `/auth/google-ads/callback`

---

## Option 3: Manual OAuth Setup (Advanced)

If you need to set up OAuth from scratch:

1. **Google Cloud Console:**
   - Go to: https://console.cloud.google.com/
   - Select your project
   - Go to: APIs & Services → Credentials
   - Edit your OAuth 2.0 Client ID
   - Add Authorized redirect URI:
     - `https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com/auth/google-ads/callback`
   - Save

2. **Use OAuth Playground** (same as Option 1)

---

## After Setting the Refresh Token

Once you've set the refresh token, verify it's working:

### 1. Check Logs
```bash
mac-mini logs -n 50 -a portal-coloradocareassist | grep -i "google.*ads"
```

You should **NOT** see: "Google Ads service not fully configured"

### 2. Test the API Endpoint
```bash
curl https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com/api/marketing/ads | jq '.data.google_ads'
```

Look for:
- `"is_placeholder": false` (not `true`)
- Real spend, clicks, impressions data (not zeros)
- `"source": "google_ads_api"`

### 3. Check the Dashboard
- Visit: https://portal.coloradocareassist.com/marketing
- Go to "Overview" or "Paid Media" tab
- Google Ads should show real data from your campaigns

---

## Quick Reference

**Your Configuration:**
- Developer Token: `-fWctng9yGnr3fiv6I4gXQ` ✅
- Customer ID: `6780818726053668` ✅
- Client ID: ✅ (set in Mac Mini)
- Client Secret: ✅ (set in Mac Mini)
- Refresh Token: ⚠️ **NEEDED**

**Required Scope:**
- `https://www.googleapis.com/auth/adwords`

**OAuth Playground:**
- https://developers.google.com/oauthplayground/

---

*Last updated: January 3, 2025*


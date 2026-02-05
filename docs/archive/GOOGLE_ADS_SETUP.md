# Google Ads API Setup Guide

## The Manager Account Requirement

**Problem:** When you try to access the Google Ads API Center, you see:
> "The API Center is only available to manager accounts."

**Solution:** You need a **Manager Account (MCC - My Client Center)** to access the API Center and get a developer token.

---

## Step 1: Create a Manager Account (if you don't have one)

1. **Go to Google Ads:** https://ads.google.com/

2. **Switch/Create Manager Account:**
   - Click on your account icon (top right corner)
   - Look for "Create a Manager Account" or "Switch to Manager Account"
   - If you don't see this option, you may need to:
     - Go to: https://ads.google.com/aw/apicenter
     - Or contact Google Ads support to upgrade your account

3. **Complete Manager Account Setup:**
   - Follow the setup wizard
   - It's **FREE** - no additional cost
   - Link your existing Google Ads account to the Manager Account (see `LINK_GOOGLE_ADS_ACCOUNT.md` for detailed instructions)

4. **Link Your Account:**
   - From Manager Account: Go to Account Access → "Link existing account"
   - Enter Customer ID: **6780818726053668**
   - Accept the link request from your regular account
   - See `LINK_GOOGLE_ADS_ACCOUNT.md` for detailed step-by-step instructions

---

## Step 2: Access the API Center

Once you're in a Manager Account:

1. **Navigate to API Center:**
   - Go to: Tools & Settings (wrench icon)
   - Under "Setup" section, click "API Center"
   - Or go directly to: https://ads.google.com/aw/apicenter

2. **Get Your Developer Token:**
   - If you already have a token, it will be displayed
   - If not, you can request one (usually approved within 24-48 hours)
   - Copy the developer token

---

## Step 3: Set Up OAuth Refresh Token

The Google Ads API requires OAuth 2.0 authentication. You need a refresh token.

### Option A: Use OAuth Flow (if implemented)

If your portal has a Google Ads OAuth connection:
1. Go to the Connections page
2. Click "Connect" for Google Ads
3. Authorize the connection
4. The refresh token will be stored automatically

### Option B: Manual OAuth Setup

1. **Set up OAuth in Google Cloud Console:**
   - Go to: https://console.cloud.google.com/
   - Select your project
   - Go to: APIs & Services → Credentials
   - Use your existing OAuth 2.0 Client ID (or create one)
   - Add scope: `https://www.googleapis.com/auth/adwords`
   - Add redirect URI: `https://portal.coloradocareassist.com/auth/google-ads/callback`

2. **Get Refresh Token:**
   - Use Google's OAuth 2.0 Playground: https://developers.google.com/oauthplayground/
   - Select scope: `https://www.googleapis.com/auth/adwords`
   - Authorize and exchange for tokens
   - Copy the refresh token

---

## Step 4: Configure Environment Variables

Set these on Mac Mini:

```bash
# Developer Token (from API Center)
# Set in ~/.gigi-env instead: GOOGLE_ADS_DEVELOPER_TOKEN="your_developer_token_here" -a portal-coloradocareassist

# Customer ID (you already have this)
# GOOGLE_ADS_CUSTOMER_ID=6780818726053668 ✅ Already set

# Refresh Token (from OAuth)
# Set in ~/.gigi-env instead: GOOGLE_ADS_REFRESH_TOKEN="your_refresh_token_here" -a portal-coloradocareassist

# OAuth Client ID/Secret (you already have these)
# GOOGLE_CLIENT_ID ✅ Already set
# GOOGLE_CLIENT_SECRET ✅ Already set
```

---

## Step 5: Verify It's Working

1. **Check Logs:**
   ```bash
   mac-mini logs -n 50 -a portal-coloradocareassist | grep -i "google.*ads"
   ```
   You should NOT see: "Google Ads service not fully configured"

2. **Test the API Endpoint:**
   ```bash
   curl https://portal.coloradocareassist.com/api/marketing/ads | jq '.data.google_ads'
   ```
   
   Look for:
   - `"is_placeholder": false` (not `true`)
   - Real spend, clicks, impressions data (not zeros)
   - `"source": "google_ads_api"`

3. **Check the Dashboard:**
   - Visit: https://portal.coloradocareassist.com/marketing
   - Go to "Overview" or "Paid Media" tab
   - Google Ads should show real data

---

## Alternative: If You Can't Get Manager Account Access

If you cannot create or access a Manager Account:

1. **Contact Google Ads Support:**
   - They can help you get API access
   - Sometimes they can provide developer tokens directly
   - Phone: 1-866-2GOOGLE

2. **Check if You Have Existing Access:**
   - Look in your account settings
   - Check if you've used Google Ads API before
   - Old developer tokens might still work

3. **Use Google Ads Reporting (Alternative):**
   - While not as powerful as the API, you can export data manually
   - Set up automated reports in Google Ads
   - Use Google Sheets integration

---

## Troubleshooting

### "API Center is only available to manager accounts"
→ You need to create/access a Manager Account (see Step 1)

### "DEVELOPER_TOKEN_INVALID" error
→ The developer token is incorrect or expired
→ Request a new one from the API Center

### "OAUTH_TOKEN_INVALID" error
→ The refresh token is expired or invalid
→ Get a new refresh token via OAuth flow

### "CLIENT_CUSTOMER_ID_INVALID" error
→ The customer ID is incorrect
→ Verify: `GOOGLE_ADS_CUSTOMER_ID=6780818726053668`

### Still seeing placeholder data
→ Check Mac Mini logs for specific error messages
→ Verify all environment variables are set correctly
→ Ensure the Manager Account has access to the customer account

---

## Additional Resources

- **Google Ads API Documentation:** https://developers.google.com/google-ads/api/docs/start
- **API Center:** https://ads.google.com/aw/apicenter (requires Manager Account)
- **OAuth 2.0 Setup:** https://developers.google.com/google-ads/api/docs/oauth/overview
- **Common Errors:** https://developers.google.com/google-ads/api/docs/common-errors

---

*Last updated: January 3, 2025*


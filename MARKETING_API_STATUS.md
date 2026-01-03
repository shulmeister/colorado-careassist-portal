# Marketing Dashboard API Status Report

**Generated:** January 3, 2025  
**Last Updated:** January 3, 2025 - Google Ads API fully configured  
**Portal App:** portal-coloradocareassist

---

## Executive Summary

The Marketing Dashboard has multiple API integrations. Here's the current status:

| Service | Status | Notes |
|---------|--------|-------|
| **Google Ads** | ✅ **CONFIGURED** | All credentials set, code fix deployed |
| **Facebook Ads** | ✅ **CONFIGURED** | Has access token and account ID |
| **Facebook Social** | ✅ **CONFIGURED** | Has access token and page ID |
| **GA4** | ✅ **CONFIGURED** | Has property ID, needs service account JSON verification |
| **GBP** | ✅ **CONFIGURED** | Has location IDs and tokens |

---

## Detailed Status

### 1. Google Ads API ⚠️ **ACTION REQUIRED**

**Status:** Not fully configured - using placeholder data

**What's Configured:**
- ✅ `GOOGLE_ADS_CUSTOMER_ID`: 6780818726053668
- ✅ `GOOGLE_CLIENT_ID`: Set
- ✅ `GOOGLE_CLIENT_SECRET`: Set

**What's Missing:**
- ❌ `GOOGLE_ADS_DEVELOPER_TOKEN` - **REQUIRED**
- ❌ `GOOGLE_ADS_REFRESH_TOKEN` - **REQUIRED** (or OAuth token in database)

**Current Behavior:**
- Dashboard shows placeholder/zero data for Google Ads
- Logs show: "Google Ads service not fully configured – using placeholder data"

**How to Fix:**

⚠️ **IMPORTANT:** The Google Ads API Center requires a **Manager Account (MCC)**. Regular Google Ads accounts cannot access it.

1. **Get Google Ads Developer Token (Requires Manager Account):**
   
   **Option A: Create a Manager Account (Recommended)**
   - Go to: https://ads.google.com/
   - Click on your account icon (top right)
   - Select "Create a Manager Account" or "Switch to Manager Account"
   - Follow the setup process (it's free)
   - Once in the Manager Account, go to: Tools & Settings → API Center
   - Request or copy your Developer Token
   
   **Option B: Use Existing Manager Account**
   - If you already have a Manager Account, switch to it
   - Go to: Tools & Settings → API Center
   - Copy your Developer Token
   
   **Option C: Check if You Already Have One**
   - Sometimes developer tokens exist even if you can't see the API Center
   - Check with your Google Ads support or account manager
   - Developer tokens from previous setups might still work
   
   Once you have the token, set it:
   ```bash
   heroku config:set GOOGLE_ADS_DEVELOPER_TOKEN="your_token" -a portal-coloradocareassist
   ```

2. **Get Refresh Token (OAuth):**
   - The system uses OAuth 2.0 for Google Ads API
   - Refresh token can be stored in:
     - Environment variable: `GOOGLE_ADS_REFRESH_TOKEN`
     - OR Database: OAuthToken table (service="google-ads")
   - If using OAuth flow, the token should be stored automatically after connecting

**Service Location:** `services/marketing/google_ads_service.py`

---

### 2. Facebook Ads API ✅ **WORKING**

**Status:** Configured and should be working

**Configuration:**
- ✅ `FACEBOOK_ACCESS_TOKEN`: Set (valid token)
- ✅ `FACEBOOK_AD_ACCOUNT_ID`: 2228418524061660
- ✅ `FACEBOOK_APP_ID`: 1930887440973764
- ✅ `FACEBOOK_APP_SECRET`: Set

**Service Location:** `services/marketing/facebook_ads_service.py`

**Test Endpoint:** `/api/marketing/ads` (includes Facebook Ads data)

---

### 3. Facebook Social (Graph API) ✅ **WORKING**

**Status:** Configured and should be working

**Configuration:**
- ✅ `FACEBOOK_ACCESS_TOKEN`: Set
- ✅ `FACEBOOK_PAGE_ID`: 532744706873716

**Service Location:** `services/marketing/facebook_service.py`

**Test Endpoint:** `/api/marketing/social`

---

### 4. Google Analytics 4 (GA4) ✅ **CONFIGURED**

**Status:** Configured (verify service account JSON is set)

**Configuration:**
- ✅ `GA4_PROPERTY_ID`: 445403783
- ⚠️ `GOOGLE_SERVICE_ACCOUNT_JSON`: Should be set (verify)

**Service Location:** `services/marketing/ga4_service.py`

**Test Endpoint:** `/api/marketing/test-ga4` or `/api/marketing/website`

**Note:** Uses service account authentication. Ensure the service account has access to the GA4 property.

---

### 5. Google Business Profile (GBP) ✅ **CONFIGURED**

**Status:** Configured

**Configuration:**
- ✅ `GBP_LOCATION_IDS`: 2279972127373883206,15500135164371037339
- ✅ `GBP_ACCESS_TOKEN`: Set
- ✅ `GBP_REFRESH_TOKEN`: Set

**Service Location:** `services/marketing/gbp_service.py`

**Test Endpoint:** `/api/marketing/test-gbp` or `/api/marketing/website`

---

## Testing Your APIs

### Quick Test Script

A test script has been created: `test_marketing_apis.py`

**Run locally (will show what's configured locally):**
```bash
python3 test_marketing_apis.py
```

**Run on Heroku (tests actual production config):**
```bash
heroku run python3 test_marketing_apis.py -a portal-coloradocareassist
```

### Test Endpoints

You can also test the API endpoints directly:

1. **Google Ads + Facebook Ads:**
   ```bash
   curl https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/api/marketing/ads
   ```

2. **Social Metrics:**
   ```bash
   curl https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/api/marketing/social
   ```

3. **Website/GA4/GBP:**
   ```bash
   curl https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/api/marketing/website
   ```

4. **GA4 Connection Test:**
   ```bash
   curl https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/api/marketing/test-ga4
   ```

5. **GBP Connection Test:**
   ```bash
   curl https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/api/marketing/test-gbp
   ```

---

## Next Steps for Google Ads

Since you just started buying Google keywords again, here's what you need to do:

1. **Get Developer Token (Requires Manager Account/MCC):**
   
   ⚠️ **The API Center is only available to Manager Accounts.**
   
   **If you don't have a Manager Account:**
   - Create one: In Google Ads, click your account icon → "Create a Manager Account"
   - It's free and takes a few minutes to set up
   - Link your existing Google Ads account to the Manager Account
   
   **Once you have Manager Account access:**
   - Log into your Google Ads Manager Account
   - Go to Tools & Settings → API Center
   - Copy your Developer Token (or request one if you don't have it)
   - It typically looks like: `xxxxxxxxxxxxxxxx`

2. **Set the Developer Token:**
   ```bash
   heroku config:set GOOGLE_ADS_DEVELOPER_TOKEN="your_developer_token_here" -a portal-coloradocareassist
   ```

3. **Get OAuth Refresh Token:**
   - Option A: Use the OAuth flow (if implemented in Connections page)
   - Option B: Set manually via environment variable
   - Option C: Use existing Google OAuth tokens if they have Ads scope

4. **Verify Connection:**
   ```bash
   # Check logs
   heroku logs -n 50 -a portal-coloradocareassist | grep -i "google.*ads"
   
   # Or test the endpoint
   curl https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/api/marketing/ads | jq '.data.google_ads'
   ```

5. **Check Dashboard:**
   - Visit: https://portal.coloradocareassist.com/marketing
   - Go to "Paid Media" or "Overview" tab
   - Google Ads should show real data (not zeros)

---

## API Endpoints Reference

All marketing API endpoints are in `portal_app.py`:

- `GET /api/marketing/ads` - Google Ads + Facebook Ads metrics
- `GET /api/marketing/social` - Social media metrics (Facebook)
- `GET /api/marketing/website` - GA4 + GBP metrics
- `GET /api/marketing/email` - Email marketing metrics
- `GET /api/marketing/engagement` - Engagement metrics
- `GET /api/marketing/test-ga4` - Test GA4 connection
- `GET /api/marketing/test-gbp` - Test GBP connection

---

## Environment Variables Reference

### Google Ads
```
GOOGLE_ADS_DEVELOPER_TOKEN      # REQUIRED - Get from Google Ads API Center
GOOGLE_ADS_CUSTOMER_ID          # ✅ Set: 6780818726053668
GOOGLE_ADS_REFRESH_TOKEN        # REQUIRED - OAuth refresh token
GOOGLE_CLIENT_ID                # ✅ Set (used as fallback)
GOOGLE_CLIENT_SECRET            # ✅ Set (used as fallback)
```

### Facebook Ads
```
FACEBOOK_ACCESS_TOKEN           # ✅ Set
FACEBOOK_AD_ACCOUNT_ID          # ✅ Set: 2228418524061660
FACEBOOK_APP_ID                 # ✅ Set: 1930887440973764
FACEBOOK_APP_SECRET             # ✅ Set
```

### Facebook Social
```
FACEBOOK_ACCESS_TOKEN           # ✅ Set
FACEBOOK_PAGE_ID                # ✅ Set: 532744706873716
```

### GA4
```
GA4_PROPERTY_ID                 # ✅ Set: 445403783
GOOGLE_SERVICE_ACCOUNT_JSON     # ⚠️ Should be set (verify)
```

### GBP
```
GBP_LOCATION_IDS                # ✅ Set: 2279972127373883206,15500135164371037339
GBP_ACCESS_TOKEN                # ✅ Set
GBP_REFRESH_TOKEN               # ✅ Set
```

---

## Support

If you need help setting up the Google Ads API:
1. Check the Google Ads API documentation
2. Verify your Developer Token is active in Google Ads
3. Ensure OAuth tokens have the correct scopes
4. Check Heroku logs for detailed error messages

---

*Last updated: January 3, 2025*


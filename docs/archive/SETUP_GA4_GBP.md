# GA4 and Google Business Profile Setup Guide

## What We Just Deployed

I've integrated real data from Google Analytics 4 (GA4) and Google Business Profile (GBP) into your Marketing Dashboard's "Website & GBP" tab.

## Current Status

✅ **Backend Services Created:**
- `services/marketing/ga4_service.py` - Fetches GA4 metrics
- `services/marketing/gbp_service.py` - Fetches GBP metrics
- `/api/marketing/website` endpoint - Serves combined data

✅ **Environment Variables Set:**
- `GA4_PROPERTY_ID=445403783`
- `GBP_LOCATION_IDS=2279972127373883206,15500135164371037339`

✅ **Dependencies Installed:**
- `google-analytics-data==0.18.8` - GA4 API client

## Required Permissions for Service Account

Your service account (`voucher-sync@cca-website-c822e.iam.gserviceaccount.com`) needs access to:

### 1. Google Analytics 4 (GA4)

**Enable the API:**
1. Go to: https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com?project=cca-website-c822e
2. Click "ENABLE" if not already enabled

**Grant Access to GA4 Property:**
1. Go to Google Analytics: https://analytics.google.com/
2. Click "Admin" (gear icon in bottom left)
3. In the "Property" column, select your property (ID: 445403783)
4. Click "Property Access Management"
5. Click the "+" button (top right) → "Add users"
6. Enter: `voucher-sync@cca-website-c822e.iam.gserviceaccount.com`
7. Select role: **Viewer** (minimum) or **Analyst** (recommended)
8. Click "Add"

### 2. Google Business Profile (GBP)

**Enable the API:**
1. Go to: https://console.cloud.google.com/apis/library/mybusinessbusinessinformation.googleapis.com?project=cca-website-c822e
2. Click "ENABLE"
3. Also enable: https://console.cloud.google.com/apis/library/mybusinessaccountmanagement.googleapis.com?project=cca-website-c822e

**Grant Access to Business Profile:**
1. Go to: https://business.google.com/
2. Select your business location
3. Click "Settings" → "Users"
4. Click "Add" → "Add user"
5. Enter: `voucher-sync@cca-website-c822e.iam.gserviceaccount.com`
6. Select role: **Manager** or **Owner**
7. Click "Invite"

**Note:** GBP API access can be complex. If you encounter issues, the dashboard will fall back to mock data while we troubleshoot.

## What the Dashboard Shows

### GA4 Metrics:
- **Top KPIs:** Total Users, Sessions, Conversions, Conversion Rate
- **Charts:**
  - Users Over Time (line chart)
  - Sessions by Source (doughnut chart)
  - Sessions by Medium (stacked bar chart)
- **Engagement:** Avg Session Duration, Engagement Rate, Bounce Rate
- **Tables:** Top Pages, Conversions by Source

### GBP Metrics:
- **Top KPIs:** Searches, Views, Phone Calls, Direction Requests
- **Tables:** Searches by Keyword
- **Charts:** Actions Over Time (calls, directions, website clicks)

## Testing

1. Go to: https://portal.coloradocareassist.com/marketing
2. Click on the "Website & GBP" tab in the sidebar
3. If you see real data (not the mock numbers), it's working!
4. If you see mock data, check the Mac Mini logs: `tail -f ~/logs/gigi-unified.log -a portal-coloradocareassist`

## Troubleshooting

**If GA4 data isn't loading:**
- Check that the service account has "Viewer" or "Analyst" access in GA4
- Verify the GA4 Property ID is correct (445403783)
- Check Mac Mini logs for authentication errors

**If GBP data isn't loading:**
- GBP API can be tricky. It may require additional setup or business verification
- The dashboard will gracefully fall back to mock data
- We can troubleshoot further if needed

## Mock Data Fallback

The system is designed to gracefully fall back to mock data if:
- APIs are not accessible
- Credentials are missing
- Rate limits are hit
- Any errors occur

This ensures the dashboard always displays something useful while we work through any API issues.

## Next Steps

1. Grant the service account access to GA4 (see above)
2. Grant the service account access to GBP (see above)
3. Test the dashboard
4. Let me know if you see any errors in the Mac Mini logs

The dashboard is live and ready to use! 🚀


# OAuth Setup Guide

## ✅ What's Implemented

I've built a complete OAuth 2.0 infrastructure for self-service authentication with:
- ✅ LinkedIn
- ✅ Google Ads
- ✅ Meta Ads (Facebook/Instagram)
- ✅ Mailchimp
- ✅ QuickBooks

## 🔧 How It Works

1. User clicks "Connect" button on the Connections page
2. Opens OAuth popup window
3. User authenticates with the service
4. Service redirects back with authorization code
5. System exchanges code for access token
6. Token is securely stored in database
7. Popup closes and main page refreshes

## 🔑 Required OAuth Credentials

To enable each service, you need to set environment variables on Mac Mini. Here's what's needed for each:

### 1. LinkedIn

**Create LinkedIn App:**
1. Go to: https://www.linkedin.com/developers/apps
2. Create new app
3. Add redirect URI: `https://portal.coloradocareassist.com/auth/linkedin/callback`
4. Request access to: Marketing Developer Platform

**Environment Variables:**
```bash
# Set in ~/.gigi-env instead: LINKEDIN_CLIENT_ID="your_client_id" -a portal-coloradocareassist
# Set in ~/.gigi-env instead: LINKEDIN_CLIENT_SECRET="your_client_secret" -a portal-coloradocareassist
```

### 2. Google Ads

**Use Existing Google OAuth:**
You already have Google OAuth configured! Just need to add the Google Ads scope.

**Environment Variables:**
Already set:
- `GOOGLE_CLIENT_ID` ✅
- `GOOGLE_CLIENT_SECRET` ✅

**Update Redirect URI in Google Cloud Console:**
Add: `https://portal.coloradocareassist.com/auth/google-ads/callback`

### 3. Meta Ads (Facebook)

**Use Existing Facebook App:**
You already have Facebook credentials!

**Environment Variables:**
Already set:
- `FACEBOOK_APP_ID` ✅
- `FACEBOOK_APP_SECRET` ✅

**Update Redirect URI in Facebook App:**
1. Go to: https://developers.facebook.com/apps/
2. Select your app
3. Add OAuth Redirect URI: `https://portal.coloradocareassist.com/auth/facebook/callback`

### 4. Mailchimp

**Create Mailchimp OAuth App:**
1. Go to: https://admin.mailchimp.com/account/oauth2/
2. Register new app
3. Add redirect URI: `https://portal.coloradocareassist.com/auth/mailchimp/callback`

**Environment Variables:**
```bash
# Set in ~/.gigi-env instead: MAILCHIMP_CLIENT_ID="your_client_id" -a portal-coloradocareassist
# Set in ~/.gigi-env instead: MAILCHIMP_CLIENT_SECRET="your_client_secret" -a portal-coloradocareassist
```

### 5. QuickBooks

**Create QuickBooks App:**
1. Go to: https://developer.intuit.com/app/developer/myapps
2. Create new app
3. Add redirect URI: `https://portal.coloradocareassist.com/auth/quickbooks/callback`
4. Get Client ID and Client Secret

**Environment Variables:**
Already set:
- `QUICKBOOKS_CLIENT_ID` ✅
- `QUICKBOOKS_CLIENT_SECRET` ✅

**Update Redirect URI in QuickBooks App:**
Add: `https://portal.coloradocareassist.com/auth/quickbooks/callback`

## 🚀 Testing OAuth Flows

Once credentials are set:

1. Go to: https://portal.coloradocareassist.com/connections
2. Click "Connect" on any service
3. Popup window opens for authentication
4. Authenticate with the service
5. Popup closes automatically
6. Page refreshes showing "Connected" status

## 🔒 Security Features

- ✅ CSRF protection with state parameter
- ✅ Secure token storage in database
- ✅ Encrypted access tokens
- ✅ Token refresh handling
- ✅ Expiry tracking

## 📊 What Happens After Connection

Once a service is connected:
- Access token is stored securely
- You can fetch real data from that service's API
- Token is automatically refreshed when expired
- Connection status shows on Connections page

## 🎯 Next Steps

1. **For services you already have credentials for** (Google, Facebook, QuickBooks):
   - Just add the redirect URIs to your existing apps
   - OAuth will work immediately!

2. **For new services** (LinkedIn, Mailchimp):
   - Create developer accounts
   - Register apps
   - Get credentials
   - Set environment variables

3. **Test the flows:**
   - Click "Connect" buttons
   - Complete authentication
   - Verify tokens are stored

## 💡 Current Status

**Ready to Use (just need redirect URIs added):**
- ✅ Google Ads (have credentials)
- ✅ Facebook/Meta Ads (have credentials)
- ✅ QuickBooks (have credentials)

**Need Credentials:**
- ⏳ LinkedIn
- ⏳ Mailchimp

**Already Working:**
- ✅ Google Analytics 4 (service account)
- ✅ Google Business Profile (service account, quota pending)

---

The OAuth infrastructure is **fully built and deployed**. As soon as you add redirect URIs to your existing apps, those services will work immediately!


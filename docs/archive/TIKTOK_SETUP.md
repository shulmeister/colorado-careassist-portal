# TikTok Marketing API Setup Guide

## Current Status

- ✅ `TIKTOK_CLIENT_KEY` - Configured (`awsl1s02sn2mwx7s`)
- ✅ `TIKTOK_CLIENT_SECRET` - Configured
- ❌ `TIKTOK_ACCESS_TOKEN` - **MISSING** (needs OAuth flow)
- ❌ `TIKTOK_ADVERTISER_ID` - **MISSING** (get from TikTok Ads Manager)

## Quick Setup (Manual Token Generation)

TikTok's OAuth is simpler - you can get an access token directly with your client credentials:

### Step 1: Get Access Token

Make a POST request to TikTok's token endpoint:

```bash
curl -X POST https://open.tiktokapis.com/v2/oauth/token/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_key=awsl1s02sn2mwx7s" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "grant_type=client_credentials"
```

**Note:** Replace `YOUR_CLIENT_SECRET` with your actual secret from Mac Mini (Local):
```bash
mac-mini config:get TIKTOK_CLIENT_SECRET --app portal-coloradocareassist
```

The response will include:
```json
{
  "access_token": "your_access_token_here",
  "token_type": "Bearer",
  "expires_in": 7200
}
```

### Step 2: Get Advertiser ID

1. Log into [TikTok Ads Manager](https://ads.tiktok.com/)
2. Your **Advertiser ID** is displayed at the top of the dashboard
   - Or go to **Account Settings** → **Advertiser Account**
   - It's a long number (e.g., `1234567890123456789`)

### Step 3: Set Environment Variables

```bash
mac-mini config:set TIKTOK_ACCESS_TOKEN=your_access_token_here --app portal-coloradocareassist
mac-mini config:set TIKTOK_ADVERTISER_ID=your_advertiser_id --app portal-coloradocareassist
```

## Alternative: Using TikTok Developer Portal

1. Go to [TikTok Developer Portal](https://developers.tiktok.com/)
2. Log in with your TikTok account
3. Navigate to your app
4. Generate an access token from the dashboard
5. Copy the token and advertiser ID
6. Set both in Mac Mini (Local) (see Step 3 above)

## Notes

- **Token Expiration:** Access tokens expire (usually 24 hours for client credentials)
- **Token Refresh:** You may need to regenerate tokens periodically
- **Advertiser ID:** This is the account you want to pull metrics from
- **No Scripts:** TikTok doesn't have a scripts system like Google Ads - it's API-only

## Testing

After setting both variables, the TikTok metrics should appear in your marketing dashboard. Check the logs if you encounter any issues:

```bash
mac-mini logs --tail --app portal-coloradocareassist | grep -i tiktok
```

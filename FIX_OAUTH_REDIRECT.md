# Fix OAuth Redirect URI Error

## Problem

You're seeing "Sales Tracker's request is invalid" with "Error 400: redirect_uri_mismatch" because:

1. The portal is using the **same OAuth client ID** as your sales dashboard
2. The portal's redirect URI is **not authorized** in Google Cloud Console
3. Google shows "Sales Tracker" because that's the app name associated with that client ID

## Solution: Add Portal Redirect URI

You have two options:

### Option 1: Add Portal URI to Existing Client (Recommended)

Since you're using the same client ID, just add the portal's redirect URI to the existing "Sales Tracker" / "CCA Portal" OAuth client:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services > Credentials**
3. Click on your OAuth 2.0 Client ID (the one that shows "Sales Tracker" or "CCA Portal")
4. In the **"Authorized redirect URIs"** section, you should see:
   - `https://tracker.coloradocareassist.com/auth/callback` (sales dashboard)
5. **Add this new URI**:
   ```
   https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback
   ```
6. Click **"Save"**

### Option 2: Create Separate OAuth Client (If You Want Separate Apps)

If you want to keep them separate (optional):

1. Create a new OAuth 2.0 Client ID in Google Cloud Console
2. Name it "CCA Portal"
3. Add redirect URI: `https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback`
4. Update Heroku config:
   ```bash
   heroku config:set GOOGLE_CLIENT_ID=new_client_id --app portal-coloradocareassist
   heroku config:set GOOGLE_CLIENT_SECRET=new_client_secret --app portal-coloradocareassist
   ```

## Quick Fix (Recommended)

**Just add the portal redirect URI to your existing OAuth client:**

1. Google Cloud Console → APIs & Services → Credentials
2. Click on your OAuth 2.0 Client ID
3. Under "Authorized redirect URIs", add:
   ```
   https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback
   ```
4. Save

After saving, the portal login should work!

## Why This Happened

- The portal and sales dashboard are sharing the same OAuth client ID
- Google shows the app name ("Sales Tracker") from the first app that used it
- Each redirect URI must be explicitly authorized
- The portal's URI wasn't in the authorized list yet

## After Adding the URI

1. Wait a few seconds for Google to update
2. Try logging in again at: https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com
3. It should work now!


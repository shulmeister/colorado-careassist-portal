# Fix Redirect URI Mismatch - Step by Step

## The Problem

You're getting "Error 400: redirect_uri_mismatch" which means Google is receiving a redirect URI that doesn't match what's authorized in Google Cloud Console.

## Exact Steps to Fix

### Step 1: Get the Exact URI

The portal is trying to use:
```
https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback
```

### Step 2: Add to Google Cloud Console

1. **Go to**: https://console.cloud.google.com/apis/credentials
2. **Click** on your OAuth 2.0 Client ID (the one with ID starting with `516104802353-...`)
3. **Scroll down** to "Authorized redirect URIs" section
4. **Click "+ ADD URI"** button
5. **Paste this EXACTLY** (copy from here):
   ```
   https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback
   ```
6. **Click "SAVE"** button at the bottom (very important!)

### Step 3: Verify It's There

After saving, you should see TWO URIs in the list:
1. `https://tracker.coloradocareassist.com/auth/callback` (sales dashboard)
2. `https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback` (portal) ← NEW ONE

### Step 4: Wait and Test

1. Wait 30-60 seconds for Google to update
2. Try logging in again: https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com

## Common Mistakes

❌ **Wrong:**
- `http://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback` (missing 's')
- `https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback/` (trailing slash)
- `https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/` (missing /auth/callback)
- Forgot to click "Save"

✅ **Correct:**
- `https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback` (exact match)

## Still Not Working?

If you've added it and it's still not working:

1. **Double-check the URI is saved:**
   - Go back to Google Cloud Console
   - Click your OAuth client
   - Verify the portal URI is in the list
   - If not, add it again and SAVE

2. **Check for typos:**
   - Compare character by character
   - Make sure there's no space before/after
   - Make sure it's `https://` not `http://`

3. **Try a different browser:**
   - Sometimes browser extensions interfere
   - Try Firefox or Safari

4. **Check Google Cloud Console error details:**
   - In the error page, click "see error details"
   - It will show the exact URI Google received
   - Compare it to what's in your authorized list

## Quick Test

After adding the URI and saving:

1. Wait 60 seconds
2. Open a NEW incognito window
3. Go to: https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com
4. Click login
5. Should work now!

If it still doesn't work, can you confirm:
- Is the URI visible in your "Authorized redirect URIs" list?
- Did you click "Save" after adding it?





# Google OAuth Setup for CCA Portal

## Client ID Name
The name "CCA Portal" is just a label - it doesn't affect functionality. You can name it anything you want.

## ⚠️ Warning Icon Fix

If you see a warning icon next to "CCA Portal" in Google Cloud Console, it's likely because the **Authorized redirect URI** is missing.

## Required Configuration

### 1. Click on "CCA Portal" in Google Cloud Console

### 2. Add Authorized Redirect URI

In the "Authorized redirect URIs" section, add:

```
https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback
```

### 3. Save Changes

Click "Save" at the bottom of the page.

## Verify Configuration

After adding the redirect URI, the warning icon should disappear.

## Important Notes

- **Client ID**: The actual ID value (starts with numbers) doesn't change when you rename it
- **Client Secret**: Also stays the same
- **Redirect URI**: Must match exactly (including https://)
- **Name**: Can be anything - "CCA Portal" is perfect!

## Current Configuration

Your Heroku app is configured with:
- **Client ID**: `516104802353-sgilgrdn7ohmfapbfuucfuforgcu6air.apps.googleusercontent.com`
- **Redirect URI**: `https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback`

Make sure this redirect URI is in your Google OAuth settings for "CCA Portal".

## Test

After adding the redirect URI, visit:
https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com

You should be able to log in with your `coloradocareassist.com` account.


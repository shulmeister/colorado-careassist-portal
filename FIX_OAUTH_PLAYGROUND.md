# Fix OAuth Playground Redirect URI Error

## Error: redirect_uri_mismatch

This error means the OAuth Playground redirect URI is not authorized in your Google Cloud Console.

## Solution: Add OAuth Playground Redirect URI

### Step 1: Go to Google Cloud Console

1. Go to: https://console.cloud.google.com/
2. Sign in with the same Google account that owns the OAuth credentials

### Step 2: Find Your OAuth Client

1. Click on the project selector (top left) - look for project: **cca-website-c822e** (or check your `GOOGLE_CLOUD_PROJECT_ID` env var)
2. Go to: **APIs & Services** → **Credentials**
3. Find your OAuth 2.0 Client ID: `844322498538-nitahgpghdbo82b2btbq5s4pqbv0a297.apps.googleusercontent.com`
4. Click on the client ID to edit it

### Step 3: Add OAuth Playground Redirect URI

1. Scroll down to **Authorized redirect URIs**
2. Click **+ ADD URI**
3. Add this exact URI:
   ```
   https://developers.google.com/oauthplayground
   ```
4. Click **SAVE**

### Step 4: Try OAuth Playground Again

1. Go back to: https://developers.google.com/oauthplayground/
2. Configure with your Client ID and Secret again
3. Try "Authorize APIs" again

---

## Alternative: Use a Different OAuth Client

If you can't modify the existing OAuth client, you can:

1. Create a new OAuth 2.0 Client ID in Google Cloud Console
2. Set it as a "Web application"
3. Add authorized redirect URI: `https://developers.google.com/oauthplayground`
4. Use the new Client ID and Secret in OAuth Playground

---

## Quick Reference

**OAuth Client ID:**
```
844322498538-nitahgpghdbo82b2btbq5s4pqbv0a297.apps.googleusercontent.com
```

**OAuth Client Secret:**
```
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
```

**Required Redirect URI:**
```
https://developers.google.com/oauthplayground
```

**Google Cloud Console:**
- Credentials: https://console.cloud.google.com/apis/credentials
- Project: cca-website-c822e (check your GOOGLE_CLOUD_PROJECT_ID env var)

---

*Last updated: January 3, 2025*


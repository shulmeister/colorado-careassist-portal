# Debug: Still Getting Redirect URI Mismatch

## Critical Check: Error Details

When you see the error page, please:

1. **Click "see error details"** on the error page
2. **Look for the redirect_uri** in the error details
3. **Tell me exactly what it says**

This will show us what URI Google actually received vs. what's authorized.

## Verify OAuth Client ID

Make sure you're editing the **correct** OAuth client:

1. In Google Cloud Console, check the **Client ID** value
2. It should be: `516104802353-sgilgrdn7ohmfapbfuucfuforgcu6air.apps.googleusercontent.com`
3. Make sure you're editing THIS one, not a different client

## Possible Solutions

### Option 1: Create New OAuth Client (Clean Start)

If the current client is causing issues, create a new one:

1. Google Cloud Console → APIs & Services → Credentials
2. Click "+ CREATE CREDENTIALS" → "OAuth client ID"
3. Application type: "Web application"
4. Name: "CCA Portal"
5. Authorized redirect URIs: `https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com/auth/callback`
6. Save
7. Copy the new Client ID and Client Secret
8. Update Mac Mini:
   ```bash
   mac-mini config:set GOOGLE_CLIENT_ID=new_client_id --app portal-coloradocareassist
   mac-mini config:set GOOGLE_CLIENT_SECRET=new_client_secret --app portal-coloradocareassist
   ```

### Option 2: Check URI Encoding

Sometimes URIs get URL-encoded. Check if Google is receiving:
- `https%3A%2F%2Fportal-coloradocareassist-3e1a4bb34793.mac-miniapp.com%2Fauth%2Fcallback`

If so, that's the encoded version and should still work, but let's verify.

## What I Need From You

1. **What does "see error details" show?** (the exact redirect_uri value)
2. **What Client ID are you editing?** (the full value)
3. **Are both URIs visible in the authorized list?**
   - `https://tracker.coloradocareassist.com/auth/callback`
   - `https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com/auth/callback`

## Quick Test

Try visiting this URL directly and check what redirect_uri it uses:
```
https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com/auth/login
```

Look at the Google OAuth URL in the address bar - it should contain `redirect_uri=...` - what does it say?





# OAuth Playground Credentials

## New OAuth Client Created

**Client ID:**
```
888987085559-k0mbk3qah1h6dmjbce1kaebsolgsu2au.apps.googleusercontent.com
```

**Client Secret:**
```
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
```

## Next Steps: Use in OAuth Playground

1. **Go to OAuth Playground:**
   - https://developers.google.com/oauthplayground/

2. **Configure:**
   - Click the gear icon (⚙️)
   - Check "Use your own OAuth credentials"
   - **Client ID:** `888987085559-k0mbk3qah1h6dmjbce1kaebsolgsu2au.apps.googleusercontent.com`
   - **Client Secret:** `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`
   - Click **Close**

3. **Authorize:**
   - In Step 1, find and select: `https://www.googleapis.com/auth/adwords`
   - Or paste it in "Input your own scopes"
   - Click **Authorize APIs**
   - Sign in with your Google account
   - Grant permissions

4. **Get Refresh Token:**
   - Click **Exchange authorization code for tokens**
   - Copy the **refresh_token** value

5. **Set Refresh Token on Mac Mini (Local):**
   ```bash
   mac-mini config:set GOOGLE_ADS_REFRESH_TOKEN="your_refresh_token_here" -a portal-coloradocareassist
   ```

## Important Note

This new OAuth client is just for getting the refresh token via OAuth Playground. 

The Google Ads service will use:
- The refresh token you set above
- The existing `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` from Mac Mini (Local) (or you can optionally update them to use this new client)

After setting the refresh token, the Google Ads API should start working!

---

*Last updated: January 3, 2025*


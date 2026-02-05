# Debug OAuth Redirect URI Mismatch

## Current Configuration

**Mac Mini Config:**
- Redirect URI: `https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com/auth/callback`
- Client ID: `516104802353-sgilgrdn7ohmfapbfuucfuforgcu6air.apps.googleusercontent.com`

## Common Issues

### 1. URI Must Match Exactly

The redirect URI in Google Cloud Console must match **exactly** (including https://):
```
https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com/auth/callback
```

**Check:**
- No trailing slash
- Must be `https://` (not `http://`)
- Must match the full domain exactly

### 2. Check Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. APIs & Services > Credentials
3. Click your OAuth 2.0 Client ID
4. Scroll to "Authorized redirect URIs"
5. Verify you see:
   ```
   https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com/auth/callback
   ```

### 3. Make Sure It's Saved

After adding the URI:
- Click **"Save"** at the bottom
- Wait 30-60 seconds for changes to propagate
- Try logging in again

### 4. Clear Browser Cache

Sometimes browsers cache OAuth redirects:
- Clear cookies for `accounts.google.com`
- Or try incognito/private browsing mode
- Or try a different browser

### 5. Check for Typos

Common mistakes:
- ❌ `http://` instead of `https://`
- ❌ Trailing slash: `/auth/callback/`
- ❌ Missing `/auth/callback` part
- ❌ Wrong domain name

### 6. Verify App is Using Correct URI

The app should be using the URI from Mac Mini config. Check:
```bash
mac-mini config:get GOOGLE_REDIRECT_URI --app portal-coloradocareassist
```

Should show:
```
https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com/auth/callback
```

## Step-by-Step Fix

1. **Verify in Google Cloud Console:**
   - Open your OAuth client
   - Check "Authorized redirect URIs"
   - Make sure `https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com/auth/callback` is there
   - Save if needed

2. **Wait 30-60 seconds** for Google to update

3. **Clear browser cache/cookies** for Google accounts

4. **Try again** in incognito mode

5. **Check Mac Mini logs** if still failing:
   ```bash
   mac-mini logs --tail --app portal-coloradocareassist
   ```

## Alternative: Test with Different Browser

Sometimes browser extensions interfere. Try:
- Chrome incognito
- Firefox
- Safari

## If Still Not Working

Check the exact error message in the browser console:
1. Open Developer Tools (F12)
2. Go to Console tab
3. Try logging in
4. Look for any error messages with the exact redirect URI





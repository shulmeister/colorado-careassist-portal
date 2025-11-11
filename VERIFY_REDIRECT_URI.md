# Verify Redirect URI Setup

## Exact URI to Add

Copy this **exactly** (no spaces, no trailing slash):

```
https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback
```

## Step-by-Step Verification

### 1. In Google Cloud Console

1. Go to: https://console.cloud.google.com/apis/credentials
2. Click on your OAuth 2.0 Client ID (the one with Client ID starting with `516104802353-...`)
3. Scroll down to **"Authorized redirect URIs"**
4. You should see a list like:
   ```
   https://tracker.coloradocareassist.com/auth/callback
   https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback
   ```

### 2. If Portal URI is Missing

1. Click **"+ ADD URI"** button
2. Paste exactly:
   ```
   https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback
   ```
3. Click **"Save"** at the bottom (very important!)
4. Wait 30-60 seconds

### 3. Common Mistakes to Avoid

❌ **DON'T add:**
- `http://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback` (missing 's')
- `https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback/` (trailing slash)
- `https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/` (missing /auth/callback)
- Space before or after the URI

✅ **DO add:**
- `https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback` (exact match)

### 4. After Saving

1. **Wait 30-60 seconds** for Google to update
2. **Clear browser cache/cookies**:
   - Chrome: Settings > Privacy > Clear browsing data > Cookies
   - Or use Incognito mode
3. **Try logging in again**

### 5. Test in Incognito Mode

1. Open Chrome Incognito (Cmd+Shift+N)
2. Go to: https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com
3. Try logging in

This bypasses browser cache issues.

## Quick Checklist

- [ ] URI added to Google Cloud Console
- [ ] Clicked "Save" button
- [ ] Waited 30-60 seconds
- [ ] Cleared browser cache OR using incognito
- [ ] URI matches exactly (no typos)

## Still Not Working?

Take a screenshot of your "Authorized redirect URIs" section in Google Cloud Console and share it, or check:

1. Is the URI listed there?
2. Does it match exactly?
3. Did you click Save?

The other errors (pageMenu, console warnings) are browser extension issues - ignore those, they're not related to the OAuth problem.





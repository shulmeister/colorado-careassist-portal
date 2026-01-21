# Create New OAuth Client for Google Ads

Since the Client ID `844322498538-nitahgpghdbo82b2btbq5s4pqbv0a297.apps.googleusercontent.com` doesn't exist in your current project, let's create a new one.

## Step-by-Step: Create New OAuth Client

### Step 1: Go to Google Cloud Console

1. Go to: https://console.cloud.google.com/
2. Make sure project **`cca-website-c822e`** is selected (top left)

### Step 2: Create OAuth Client

1. Go to: **APIs & Services** → **Credentials**
   - Direct link: https://console.cloud.google.com/apis/credentials?project=cca-website-c822e

2. Click **+ CREATE CREDENTIALS** (top of page)
3. Select **OAuth client ID**

### Step 3: Configure OAuth Client

1. **Application type:** Select **Web application**
2. **Name:** Enter something like: `Google Ads API OAuth` or `OAuth Playground Test`
3. **Authorized redirect URIs:** Click **+ ADD URI** and add:
   ```
   https://developers.google.com/oauthplayground
   ```
4. Click **CREATE**

### Step 4: Copy Credentials

After creating, you'll see a popup with:
- **Your Client ID** (copy this)
- **Your Client secret** (copy this - you can only see it once!)

### Step 5: Use in OAuth Playground

1. Go back to: https://developers.google.com/oauthplayground/
2. Click the gear icon (⚙️) to open configuration
3. Check "Use your own OAuth credentials"
4. Paste the **new Client ID** you just created
5. Paste the **new Client Secret** you just created
6. Click **Close**
7. Proceed with authorization

---

## Alternative: Use Existing Client

If you want to use the existing client `516104802353-sgilgrdn7ohmfapbfuucfuforgcu6air.apps.googleusercontent.com`:

1. Find that client in Google Cloud Console (might be in a different project)
2. Add redirect URI: `https://developers.google.com/oauthplayground`
3. Use these credentials in OAuth Playground:
   - **Client ID:** `516104802353-sgilgrdn7ohmfapbfuucfuforgcu6air.apps.googleusercontent.com`
   - **Client Secret:** `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`

---

## Quick Reference

**Current Project:** `cca-website-c822e`

**OAuth Playground Redirect URI:**
```
https://developers.google.com/oauthplayground
```

**Google Cloud Console:**
- Credentials: https://console.cloud.google.com/apis/credentials?project=cca-website-c822e

---

*Last updated: January 3, 2025*


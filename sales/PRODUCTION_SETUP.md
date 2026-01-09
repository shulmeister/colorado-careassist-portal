# 🚀 PRODUCTION SETUP GUIDE - tracker.coloradocareassist.com

## ✅ **Issue Fixed: 503 Service Unavailable**

The 503 error was caused by missing dependencies (`httpx` and `itsdangerous`). These have been installed and the app now starts successfully.

## 🔧 **IMMEDIATE STEPS TO GET AUTHENTICATION WORKING**

### **Step 1: Create Environment Variables**

Create a `.env` file in your project root with these exact values:

```bash
# Google OAuth Credentials (REQUIRED for authentication)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://tracker.coloradocareassist.com/auth/callback

# Allowed domains
ALLOWED_DOMAINS=coloradocareassist.com

# App Secret Key (generate a secure random key)
APP_SECRET_KEY=your-secure-random-key-here

# Existing Google Sheets (already working)
GOOGLE_SERVICE_ACCOUNT_KEY={"type":"service_account",...}
SHEET_ID=1rKBP_5eLgvIVprVEzOYRnyL9J3FMf9H-6SLjIvIYFgg
```

### **Step 2: Google Cloud Console Setup**

1. **Go to [Google Cloud Console](https://console.cloud.google.com/)**
2. **Select your project** (or create new one)
3. **Enable APIs:**
   - Google Sheets API ✅ (already enabled)
   - Google Drive API ✅ (already enabled)
   - **Google+ API** (for user authentication)

4. **Create OAuth 2.0 Credentials:**
   - Go to **APIs & Services** → **Credentials**
   - Click **Create Credentials** → **OAuth 2.0 Client IDs**
   - Choose **Web application**
   - **Authorized redirect URIs:**
     ```
     https://tracker.coloradocareassist.com/auth/callback
     ```
   - **Copy Client ID and Client Secret**

### **Step 3: Update Your Hosting Environment**

**If using Heroku:**
```bash
heroku config:set GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
heroku config:set GOOGLE_CLIENT_SECRET=your-client-secret
heroku config:set GOOGLE_REDIRECT_URI=https://tracker.coloradocareassist.com/auth/callback
heroku config:set ALLOWED_DOMAINS=coloradocareassist.com
heroku config:set APP_SECRET_KEY=your-secure-random-key
```

**If using other hosting:**
- Add the environment variables to your hosting platform
- Ensure HTTPS is enabled
- Restart your application

### **Step 4: Test Authentication**

1. **Visit:** `https://tracker.coloradocareassist.com`
2. **Expected behavior:**
   - Redirects to Google login
   - Login with `@coloradocareassist.com` email
   - Redirects back to dashboard
   - Shows user info in top-right corner

## 🔍 **TROUBLESHOOTING**

### **Still getting 503 error?**
```bash
# Check if app starts locally
cd "/Users/jasonshulman/Desktop/bizcard_simple_oauth_tesseract_PREFILLED/Visit Tracker"
./venv/bin/python app.py
```

### **"Authentication service unavailable"**
- Check `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set
- Verify Google Cloud Console OAuth setup

### **"Access denied"**
- User's email domain not in `ALLOWED_DOMAINS`
- Must be `@coloradocareassist.com`

### **Redirect URI mismatch**
- Ensure Google Console has: `https://tracker.coloradocareassist.com/auth/callback`
- Check environment variable: `GOOGLE_REDIRECT_URI`

## 🎯 **WHAT HAPPENS AFTER SETUP**

1. **Users visit:** `https://tracker.coloradocareassist.com`
2. **System redirects to:** Google OAuth login
3. **User logs in with:** `@coloradocareassist.com` email
4. **System redirects back to:** Dashboard with user info
5. **User can:** Upload files, view data, manage contacts
6. **Security:** Only authorized company users can access

## 🔒 **SECURITY STATUS**

- ✅ **Authentication:** Google OAuth implemented
- ✅ **Authorization:** Domain-restricted access
- ✅ **HTTPS:** Required for production
- ✅ **Session Security:** HTTP-only cookies
- ✅ **Dependencies:** Updated and secure

## 📞 **NEED HELP?**

If you're still having issues:

1. **Check the logs** on your hosting platform
2. **Verify environment variables** are set correctly
3. **Test locally first** with `./venv/bin/python app.py`
4. **Check Google Cloud Console** OAuth configuration

The authentication system is now properly configured for your production domain `tracker.coloradocareassist.com`!


# Deployment Instructions

## ✅ What's Already Done

1. ✅ Repository created at: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal`
2. ✅ Git initialized and initial commit made
3. ✅ Heroku app created: `portal-coloradocareassist`
4. ✅ Heroku remote added
5. ✅ PostgreSQL addon added

## 🔧 Next Steps

### 1. Set Environment Variables

You need to set your Google OAuth credentials. Run:

```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal
./setup-heroku.sh
```

Or manually set them:

```bash
heroku config:set GOOGLE_CLIENT_ID=your_client_id --app portal-coloradocareassist
heroku config:set GOOGLE_CLIENT_SECRET=your_client_secret --app portal-coloradocareassist
heroku config:set GOOGLE_REDIRECT_URI=https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback --app portal-coloradocareassist
heroku config:set APP_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))") --app portal-coloradocareassist
heroku config:set ALLOWED_DOMAINS=coloradocareassist.com --app portal-coloradocareassist
```

### 2. Update Google OAuth Redirect URI

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to APIs & Services > Credentials
3. Edit your OAuth 2.0 Client ID
4. Add to "Authorized redirect URIs":
   - `https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com/auth/callback`

### 3. Push to GitHub (Optional)

If you want to push to GitHub:

```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal

# Create repo on GitHub first, then:
git remote add origin https://github.com/YOUR_USERNAME/colorado-careassist-portal.git
git push -u origin main
```

### 4. Deploy to Heroku

```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal
git push heroku main
```

### 5. Initialize Database

```bash
heroku run python portal_setup.py --app portal-coloradocareassist
```

### 6. Verify Deployment

Visit: https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com

## 📋 Quick Commands

```bash
# View logs
heroku logs --tail --app portal-coloradocareassist

# Restart app
heroku restart --app portal-coloradocareassist

# Check config
heroku config --app portal-coloradocareassist

# Open app
heroku open --app portal-coloradocareassist
```

## 🎯 App URL

**Heroku App**: https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com

## 📝 Notes

- The app is already created and configured
- PostgreSQL database is already added
- Just need to set environment variables and deploy
- After deployment, run the setup script to initialize the database


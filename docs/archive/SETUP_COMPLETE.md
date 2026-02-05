# ✅ Portal Setup Complete!

## What I've Done

1. ✅ Created portal repository at: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal`
2. ✅ Copied all portal files (app, auth, database, models, templates)
3. ✅ Initialized Git repository
4. ✅ Made initial commit
5. ✅ Created Mac Mini app: `portal-coloradocareassist`
6. ✅ Added Mac Mini remote
7. ✅ Added PostgreSQL database (essential-0 plan)
8. ✅ Created README.md
9. ✅ Created setup scripts

## 🎯 Your Portal App

**Mac Mini URL**: https://portal.coloradocareassist.com

**Mac Mini App Name**: `portal-coloradocareassist`

## 📋 Final Steps (You Need to Do)

### 1. Set Environment Variables

Run the setup script:
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal
./setup-mac-mini.sh
```

Or manually (get your Google OAuth credentials from your sales dashboard setup):

```bash
# Set in ~/.gigi-env instead: GOOGLE_CLIENT_ID=your_client_id --app portal-coloradocareassist
# Set in ~/.gigi-env instead: GOOGLE_CLIENT_SECRET=your_client_secret --app portal-coloradocareassist
# Set in ~/.gigi-env instead: GOOGLE_REDIRECT_URI=https://portal.coloradocareassist.com/auth/callback --app portal-coloradocareassist
# Set in ~/.gigi-env instead: APP_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))") --app portal-coloradocareassist
# Set in ~/.gigi-env instead: ALLOWED_DOMAINS=coloradocareassist.com --app portal-coloradocareassist
```

### 2. Update Google OAuth Settings

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services > Credentials**
3. Edit your OAuth 2.0 Client ID
4. Add to **Authorized redirect URIs**:
   ```
   https://portal.coloradocareassist.com/auth/callback
   ```

### 3. Deploy to Mac Mini

```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal
git push origin main
```

### 4. Initialize Database

```bash
mac-mini run python portal_setup.py --app portal-coloradocareassist
```

### 5. Test It!

Visit: https://portal.coloradocareassist.com

## 📁 Repository Structure

```
/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/
├── portal_app.py          # Main FastAPI app
├── portal_auth.py          # OAuth authentication
├── portal_database.py     # Database setup
├── portal_models.py       # Database models
├── portal_setup.py        # Setup script
├── templates/
│   └── portal.html        # Portal UI
├── static/
│   └── favicon.ico        # Favicon
├── Procfile               # Mac Mini process
├── requirements.txt       # Dependencies
├── runtime.txt           # Python version
├── README.md             # Documentation
├── DEPLOY.md             # Deployment guide
└── setup-mac-mini.sh       # Setup script
```

## 🔗 Quick Links

- **Mac Mini Dashboard**: https://dashboard.mac-mini.com/apps/portal-coloradocareassist
- **App URL**: https://portal.coloradocareassist.com
- **View Logs**: `tail -f ~/logs/gigi-unified.log --app portal-coloradocareassist`

## 🚀 All Set!

Everything is ready. Just:
1. Set environment variables (step 1)
2. Update Google OAuth (step 2)
3. Deploy (step 3)
4. Initialize database (step 4)

Then you're good to go! 🎉


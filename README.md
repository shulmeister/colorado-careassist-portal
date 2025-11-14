# Colorado CareAssist Portal

## 🎯 CRITICAL: HUB-AND-SPOKE ARCHITECTURE

**READ THIS FIRST - THIS IS A HUB-AND-SPOKE SYSTEM:**

### THE HUB (Main Portal)
- **Repository**: `colorado-careassist-portal`
- **GitHub**: https://github.com/shulmeister/colorado-careassist-portal
- **Heroku**: `portal-coloradocareassist` → `portal-coloradocareassist-3e1a4bb34793.herokuapp.com`
- **Local Path**: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal`
- **Tech**: FastAPI, Jinja2, PostgreSQL
- **Purpose**: Central launchpad with tiles that link to other apps

### SPOKES (Individual Apps)

#### 1. Sales Dashboard
- **Repository**: `sales-dashboard` (SEPARATE GitHub repo)
- **GitHub**: https://github.com/shulmeister/sales-dashboard
- **Heroku**: `careassist-tracker` → `careassist-tracker-0fcf2cecdb22.herokuapp.com`
- **Local Path**: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/sales/`
- **Tech**: Python FastAPI, Jinja2, PostgreSQL
- **Git Structure**: Nested git repo (has its own `.git` folder)
- **Portal Route**: `/sales` (redirects to Heroku URL)
- **Features**: Visits tracking, business cards, closed sales, contacts, Lead Tracker, activity logs

#### 2. Recruiter Dashboard
- **Repository**: `recruiter-dashboard` (SEPARATE GitHub repo - needs to be created)
- **GitHub**: https://github.com/shulmeister/recruiter-dashboard (TO BE CREATED)
- **Heroku**: `caregiver-lead-tracker` → `caregiver-lead-tracker-9d0e6a8c7c20.herokuapp.com`
- **Local Path**: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/recruitment/`
- **Tech**: Flask, SQLAlchemy, PostgreSQL
- **Git Structure**: Nested git repo (has its own `.git` folder)
- **Portal Route**: `/recruitment` (embedded iframe)
- **Features**: Caregiver recruitment, candidate pipeline, Facebook leads

#### 3. Marketing Dashboard
- **Repository**: Built INTO `colorado-careassist-portal` (NOT a separate repo)
- **Local Path**: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/templates/marketing.html`
- **Portal Route**: `/marketing` (built-in route)
- **Tech**: Jinja2 template, Chart.js, FastAPI routes
- **Features**: Social media metrics, Google Ads, GA4, GBP analytics

### ⚠️ CRITICAL DEPLOYMENT RULES

**ALWAYS push to BOTH GitHub AND Heroku after ANY changes:**

#### Portal (Hub)
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal
git add .
git commit -m "Describe changes"
git push origin main      # Push to GitHub
git push heroku main      # Push to Heroku
```

#### Sales Dashboard (Spoke)
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/sales
git add .
git commit -m "Describe changes"
git push origin main      # Push to GitHub
git push heroku main      # Push to Heroku
```

#### Recruiter Dashboard (Spoke)
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/recruitment
git add .
git commit -m "Describe changes"
git push origin main      # Push to GitHub (once repo is created)
git push heroku main      # Push to Heroku
```

### 📁 Git Repository Structure

```
colorado-careassist-portal/          # Main portal repo (GitHub + Heroku)
├── .git/                            # Portal's git repo
├── dashboards/
│   ├── sales/
│   │   ├── .git/                    # Sales Dashboard's OWN git repo
│   │   ├── app.py
│   │   └── ...
│   └── recruitment/
│       ├── .git/                    # Recruiter Dashboard's OWN git repo
│       ├── app.py
│       └── ...
├── templates/
│   ├── marketing.html               # Marketing Dashboard (built into portal)
│   └── ...
└── portal_app.py                    # Main portal app
```

**IMPORTANT**: Each dashboard (`sales` and `recruitment`) is a **nested git repository** with its own remotes. They are NOT submodules - they're independent repos that happen to live inside the portal directory.

### 🔄 Syncing Status (Last Updated: Nov 13, 2025)

| Component | GitHub | Heroku | Status |
|-----------|--------|--------|--------|
| Portal | ✅ https://github.com/shulmeister/colorado-careassist-portal | ✅ portal-coloradocareassist | ✅ Synced |
| Sales Dashboard | ✅ https://github.com/shulmeister/sales-dashboard | ✅ careassist-tracker | ✅ Synced |
| Recruiter Dashboard | ❌ **NEEDS CREATION** | ✅ caregiver-lead-tracker | ⚠️ Heroku only |
| Marketing Dashboard | ✅ (part of portal repo) | ✅ (part of portal) | ✅ Synced |

**TODO**: Create GitHub repo `recruiter-dashboard` and push code from `/dashboards/recruitment/`

### 🚨 Common Mistakes to Avoid

1. **Don't commit from portal root when working on dashboards** - Each dashboard has its own git repo
2. **Don't assume all code is in one place** - Check which repo you're in with `git remote -v`
3. **Always push to BOTH GitHub AND Heroku** - They're separate remotes
4. **Marketing Dashboard is NOT a separate repo** - It's in `templates/marketing.html` in the portal repo

## Features

- **Google OAuth Authentication** - Secure login with Google Workspace accounts
- **Domain Restriction** - Only `coloradocareassist.com` users allowed
- **Tool Grid** - Beautiful grid of clickable tool tiles
- **Admin Interface** - Manage tools (add/edit/delete) with modal-based interface
- **Responsive Design** - Works on desktop, tablet, and mobile
- **Exact Dashboard Styling** - Matches the sales dashboard design exactly
- **RingCentral Embedded Workspace** *(optional)* - RingCentral softphone/chat lives in the left sidebar with an expandable full-width workspace

## Setup

### Local Development

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**
   - Create `.env` file:
   ```env
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback
   APP_SECRET_KEY=your_secret_key
   ALLOWED_DOMAINS=coloradocareassist.com
   DATABASE_URL=sqlite:///./portal.db
   # Optional RingCentral Embeddable widget
   RINGCENTRAL_EMBED_CLIENT_ID=your_ringcentral_browser_app_id
   RINGCENTRAL_EMBED_SERVER=https://platform.ringcentral.com  # or https://platform.devtest.ringcentral.com for Sandbox
   RINGCENTRAL_EMBED_APP_URL=https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/app.html
   RINGCENTRAL_EMBED_ADAPTER_URL=https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/adapter.js
   RINGCENTRAL_EMBED_DEFAULT_TAB=messages
   RINGCENTRAL_EMBED_REDIRECT_URI=https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/redirect.html
   ```
   > ⚠️ Only the RingCentral browser app's client ID is used in the portal. Store your client secret securely and never commit it to source control.

   **RingCentral developer portal configuration**

   1. Sign in to the [RingCentral Developer Portal](https://developers.ringcentral.com/).
   2. Open your Browser-Based or Embeddable app that owns the client ID above.
   3. On the *OAuth / Redirect URI* section, add:
      ```
      https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/redirect.html
      ```
   4. Save the app. Without this redirect URI you will see `OAU-113: No redirect URI is registered for this client application`.

3. **Initialize Database**
   ```bash
   python portal_setup.py
   ```

4. **Run the Application**
   ```bash
   uvicorn portal_app:app --reload --port 8000
   ```

5. **Access the Portal**
   - Open `http://localhost:8000`

## Deployment

### ⚠️ ALWAYS DEPLOY TO BOTH GIT AND HEROKU

**After making ANY code changes, ALWAYS run these commands:**

```bash
git add .
git commit -m "Describe your changes"
git push origin main      # Push to GitHub
git push heroku main      # Push to Heroku (REQUIRED!)
```

### Heroku

The app is configured for Heroku deployment:

1. **Set Environment Variables**
   ```bash
   heroku config:set GOOGLE_CLIENT_ID=your_client_id
   heroku config:set GOOGLE_CLIENT_SECRET=your_client_secret
   heroku config:set GOOGLE_REDIRECT_URI=https://portal-coloradocareassist.herokuapp.com/auth/callback
   heroku config:set APP_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   heroku config:set ALLOWED_DOMAINS=coloradocareassist.com
   # Optional RingCentral embeddable widget
   heroku config:set RINGCENTRAL_EMBED_CLIENT_ID=your_ringcentral_browser_app_id
   heroku config:set RINGCENTRAL_EMBED_SERVER=https://platform.ringcentral.com
   heroku config:set RINGCENTRAL_EMBED_APP_URL=https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/app.html
   heroku config:set RINGCENTRAL_EMBED_ADAPTER_URL=https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/adapter.js
   heroku config:set RINGCENTRAL_EMBED_DEFAULT_TAB=messages
   heroku config:set RINGCENTRAL_EMBED_REDIRECT_URI=https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/redirect.html
   ```

2. **Add PostgreSQL**
   ```bash
   heroku addons:create heroku-postgresql:mini
   ```

3. **Deploy**
   ```bash
   git push heroku main
   ```

4. **Initialize Database**
   ```bash
   heroku run python portal_setup.py
   ```

## Project Structure

```
├── portal_app.py          # Main FastAPI application
├── portal_auth.py          # Google OAuth authentication
├── portal_database.py     # Database setup and connection
├── portal_models.py       # Database models (PortalTool)
├── portal_setup.py        # Setup script for default tools
├── templates/
│   └── portal.html        # Portal UI template
├── Procfile               # Heroku process file
├── requirements.txt       # Python dependencies
└── runtime.txt            # Python version
```

## API Endpoints

### Authentication
- `GET /auth/login` - Redirect to Google OAuth
- `GET /auth/callback` - OAuth callback handler
- `POST /auth/logout` - Logout user
- `GET /auth/me` - Get current user info

### Tools
- `GET /api/tools` - Get all active tools
- `POST /api/tools` - Create new tool (admin only)
- `PUT /api/tools/{id}` - Update tool (admin only)
- `DELETE /api/tools/{id}` - Delete tool (admin only)

## Adding Tools

### Via Admin Interface

1. Login to the portal
2. Click "Manage Tools" button
3. Click "+ Add Tool"
4. Fill in the form:
   - **Name**: Tool name (e.g., "Sales Dashboard")
   - **URL**: Full URL to the tool
   - **Icon**: Emoji icon (e.g., "📊")
   - **Description**: Brief description (optional)
   - **Category**: Category name (optional)
   - **Display Order**: Order in grid (lower numbers first)

## Security

- **Google OAuth 2.0** - Secure authentication
- **Domain Restriction** - Only company domain allowed
- **HTTP-only Cookies** - Secure session management
- **24-hour Sessions** - Automatic logout after 24 hours
- **HTTPS Required** - Secure in production

## Design

The portal uses the **exact same styling** as the sales dashboard:
- Dark theme with `#0f172a` background
- Cards with `#1e293b` background and `#334155` borders
- Same typography, spacing, and colors
- Same navigation sidebar
- Same responsive breakpoints





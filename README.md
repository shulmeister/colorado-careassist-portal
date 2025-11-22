# Colorado CareAssist Portal

## 🗺️ Quick Map (Desktop → Repos → Heroku)

On Jason's Mac (`~/Documents/GitHub`) each tile has a **single folder name** that matches the tile you click in the portal. Those folders are symbolic links that point into this repo so you can jump straight to the correct nested git repo:

| Tile / Service      | Desktop Folder                           | Nested Path (inside this repo)                       | GitHub Repo                                            | Heroku App / URL + Deploy Status                                                                 |
|---------------------|-------------------------------------------|------------------------------------------------------|--------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| Portal (hub)        | `colorado-careassist-portal`              | `.`                                                  | `shulmeister/colorado-careassist-portal`               | `portal-coloradocareassist` → https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com (auto deploy ✅) |
| Sales Dashboard     | `sales-dashboard`                         | `dashboards/sales`                                   | `shulmeister/sales-dashboard`                          | `careassist-tracker` / `cca-crm` (both auto deploy from GitHub `main` ✅)                          |
| Activity Tracker    | `activity-tracker`                        | `dashboards/activity-tracker`                        | `shulmeister/Colorado-CareAssist-Route-Tracker`        | `cca-activity-tracker-6d9a1d8e3933` (auto deploy from GitHub `main` ✅)                             |
| Recruiter Dashboard | `recruiter-dashboard`                     | `dashboards/recruitment`                             | `shulmeister/recruiter-dashboard`                      | `caregiver-lead-tracker-9d0e6a8c7c20` (auto deploy from GitHub `main` ✅)                           |
| Marketing Dashboard | `marketing-dashboard`                     | `dashboards/marketing` (served via portal templates) | `shulmeister/marketing-dashboard`                      | Ships with portal auto deploy (no separate Heroku app)                                            |

> 🔁 Any time you “work on Sales”, just `cd ~/Documents/GitHub/sales-dashboard` and you’ll end up in `colorado-careassist-portal/dashboards/sales`, which is the real repo that deploys the Sales tile. Same pattern for every other spoke.

## 🎯 CRITICAL: HUB-AND-SPOKE ARCHITECTURE

**READ THIS FIRST – THIS IS A HUB-AND-SPOKE SYSTEM:**

### THE HUB (Main Portal)
- **Repository**: `colorado-careassist-portal`
- **GitHub**: https://github.com/shulmeister/colorado-careassist-portal
- **Heroku**: `portal-coloradocareassist` → `portal-coloradocareassist-3e1a4bb34793.herokuapp.com`
- **Local Path**: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal`
- **Tech**: FastAPI, Jinja2, PostgreSQL
- **Purpose**: Central launchpad with tiles that link to other apps

### SPOKES (Individual Apps)

#### 1. Sales Dashboard
- **Repository**: `sales-dashboard` (nested repo)
- **GitHub**: https://github.com/shulmeister/sales-dashboard
- **Heroku**: `careassist-tracker` → `https://careassist-tracker-0fcf2cecdb22.herokuapp.com/`  
  (Portal env `SALES_DASHBOARD_URL` can override with `https://cca-crm-cd555628f933.herokuapp.com` when needed.)
- **Local Path**: `~/Documents/GitHub/sales-dashboard` (symlink) → `dashboards/sales/`
- **Tech**: Python FastAPI, Jinja2, PostgreSQL
- **Git Structure**: Nested git repo (has its own `.git` folder)
- **Portal Route**: `/sales` (redirects via `/portal-auth` into the CCA CRM app)
- **Features**: Visits tracking, business cards, closed sales, contacts, Lead Tracker, activity logs

#### 2. Recruiter Dashboard
- **Repository**: `recruiter-dashboard` (nested repo)
- **GitHub**: https://github.com/shulmeister/recruiter-dashboard
- **Heroku**: `caregiver-lead-tracker` → `caregiver-lead-tracker-9d0e6a8c7c20.herokuapp.com`
- **Local Path**: `~/Documents/GitHub/recruiter-dashboard` (symlink) → `dashboards/recruitment/`
- **Tech**: Flask, SQLAlchemy, PostgreSQL
- **Git Structure**: Nested git repo (has its own `.git` folder)
- **Portal Route**: `/recruitment` (embedded iframe)
- **Features**: Caregiver recruitment, candidate pipeline, Facebook Lead Ads sync (`Pull Leads` button + daily scheduler script, duplicate-proof via native lead IDs)

#### 3. Marketing Dashboard
- **Repository**: `marketing-dashboard` (nested repo)
- **GitHub**: https://github.com/shulmeister/marketing-dashboard
- **Local Path**: `~/Documents/GitHub/marketing-dashboard` (symlink) → `dashboards/marketing/`
- **Tech**: Jinja2 template, Chart.js, FastAPI routes (integrated into portal)
- **Git Structure**: Nested git repo (has its own `.git` folder)
- **Portal Route**: `/marketing` (built-in route in portal_app.py)
- **Features**: Social media metrics, Google Ads, GA4, GBP analytics

#### 4. Activity Tracker
- **Repository**: `Colorado-CareAssist-Route-Tracker` (nested repo)
- **GitHub**: https://github.com/shulmeister/Colorado-CareAssist-Route-Tracker
- **Heroku**: `cca-activity-tracker-6d9a1d8e3933` → https://cca-activity-tracker-6d9a1d8e3933.herokuapp.com/
- **Local Path**: `~/Documents/GitHub/activity-tracker` (symlink) → `dashboards/activity-tracker/`
- **Tech**: FastAPI, SQLAlchemy, PDF parser, Tesseract OCR
- **Git Structure**: Nested git repo (has its own `.git` folder)
- **Portal Route**: `/activity-tracker` (portal redirects with SSO token)
- **Features**: PDF route import, time tracking, business-card OCR, Google Sheets sync
- **Helper Script**: Run `python add_activity_tracker_tile.py` from portal root (or `heroku run` equivalent) to keep the portal tile pointing at `/activity-tracker`.

### ⚠️ CRITICAL DEPLOYMENT RULES

**Standard flow (now live for every tile):**

`Desktop commit → git push origin main → Heroku auto deploys` ✅

All apps (portal + every spoke) are connected to their GitHub repo with automatic deploys from the `main` branch. The commands below are only needed if auto deploys are intentionally disabled and you want to push directly to Heroku.

**Manual override (only if GitHub integration is disabled):**

#### Portal (Hub)
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal
git add .
git commit -m "Describe changes"
git push origin main      # Push to GitHub
git push heroku main      # Push to Heroku (only if NOT using GitHub integration)
```

#### Sales Dashboard (Spoke)
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/sales
git add .
git commit -m "Describe changes"
git push origin main      # Push to GitHub → Heroku auto-deploys! ✅
```

#### Recruiter Dashboard (Spoke)
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/recruitment
git add .
git commit -m "Describe changes"
git push origin main      # Push to GitHub → Heroku auto-deploys! ✅
```

#### Activity Tracker (Spoke)
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/activity-tracker
git add .
git commit -m "Describe changes"
git push origin main      # Push to GitHub → Heroku auto-deploys! ✅
# Only push directly if auto deploys are off:
# git push heroku main
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
│   ├── recruitment/
│   │   ├── .git/                    # Recruiter Dashboard's OWN git repo
│   │   ├── app.py
│   │   └── ...
│   └── activity-tracker/
│       ├── .git/                    # Activity Tracker's OWN git repo
│       ├── app.py                   # FastAPI + PDF/HEIC/OCR pipelines
│       └── business_card_scanner.py, parser.py, etc.
├── templates/
│   ├── marketing.html               # Marketing Dashboard (built into portal)
│   └── ...
└── portal_app.py                    # Main portal app
```

**IMPORTANT**: Each dashboard (`sales` and `recruitment`) is a **nested git repository** with its own remotes. They are NOT submodules - they're independent repos that happen to live inside the portal directory.

### 🔄 Syncing Status (Last Updated: Nov 22, 2025)

| Component | GitHub Repo | Heroku App / URL | Status |
|-----------|-------------|------------------|--------|
| Portal | `shulmeister/colorado-careassist-portal` | `portal-coloradocareassist` | ✅ Auto deploy on `main` |
| Sales Dashboard | `shulmeister/sales-dashboard` | `careassist-tracker` / `cca-crm` | ✅ `sales-stable-2025-11-22` tagged & auto deploys |
| Recruiter Dashboard | `shulmeister/recruiter-dashboard` | `caregiver-lead-tracker-9d0e6a8c7c20` | ✅ Auto deploy on `main` |
| Activity Tracker | `shulmeister/Colorado-CareAssist-Route-Tracker` | `cca-activity-tracker-6d9a1d8e3933` | ✅ Auto deploy on `main` + portal SSO |
| Marketing Dashboard | `shulmeister/marketing-dashboard` (embedded) | Ships with portal | ✅ Included in portal auto deploy |

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

## Smoke Tests (Tiles + Health Checks)

Before handing the portal back to stakeholders, run the canned smoke script to make sure each tile URL and health endpoint is responding:

```bash
./scripts/smoke.sh
```

The script hits:

| Check | Endpoint | Expected |
|-------|----------|----------|
| Portal health | `$PORTAL_URL/health` | 200 |
| Marketing shell | `$PORTAL_URL/marketing` | 200 (authed) / 302 or 401 (unauth) |
| Portal → Sales redirect | `$PORTAL_URL/sales` | 302/307/401 (unauth redirect) |
| Sales health | `$SALES_DASHBOARD_URL/health` | 200 |
| Portal → Activity redirect | `$PORTAL_URL/activity-tracker` | 302/307/401 |
| Activity health | `$ACTIVITY_TRACKER_URL/health` | 200 |
| Recruiter landing | `$RECRUITER_DASHBOARD_URL/` | 200/302/307/401/404 |

Override the URLs via environment variables (`PORTAL_URL`, `SALES_DASHBOARD_URL`, etc.) if you need to test staging environments.

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
   - **URL**: Internal route (`/sales`, `/activity-tracker`, etc.) or full URL
   - **Icon**: Emoji icon (e.g., "📊")
   - **Description**: Brief description (optional)
   - **Category**: Category name (optional)
   - **Display Order**: Order in grid (lower numbers first)

### Activity Tracker helper script

To guarantee the “Activity Tracker” tile always points at `/activity-tracker` with the right metadata, run the helper script:

```bash
# Update local portal.db
python add_activity_tracker_tile.py

# Update production portal
heroku run python add_activity_tracker_tile.py -a portal-coloradocareassist
```

This script will upsert the tile (icon 📋, Field Ops category, display order 4) without disturbing other tiles.

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





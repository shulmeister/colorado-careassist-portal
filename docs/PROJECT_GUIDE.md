# Project Guide - Colorado CareAssist Portal

This is the consolidated, source-of-truth guide for the portal and all spokes. It is written for agents and developers who need to understand the system quickly.

## 1) Architecture (Unified App + Sub-Apps)

```
colorado-careassist-portal/          # Unified repo (source of truth)
├── unified_app.py                   # Main FastAPI app (mounts everything)
├── portal/                          # Portal Hub (FastAPI)
├── gigi/                            # Gigi AI agent (FastAPI)
├── services/                        # WellSky + marketing services
├── templates/                       # Portal + Marketing dashboard templates
├── sales/                           # Sales Dashboard (FastAPI + React Admin)
├── recruiting/                      # Recruiter Dashboard (Flask)
└── powderpulse/                     # Vue SPA
```

Everything deploys together to a single Heroku app via `unified_app.py`.

## 2) Canonical Location

All work should happen from this canonical path:

```
/Users/shulmeister/Documents/GitHub/colorado-careassist-portal
```

## 3) Repos, Apps, and URLs

### Hub (Portal + Gigi)
- GitHub: https://github.com/shulmeister/colorado-careassist-portal
- Heroku app: `careassist-unified`
- Live URL: https://careassist-unified-0a11ddb45ac0.herokuapp.com
- Gigi URL: https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/

### Spoke: Sales Dashboard
- Repo: https://github.com/shulmeister/sales-dashboard
- Heroku app: `careassist-tracker`
- Live URL: https://careassist-tracker-0fcf2cecdb22.herokuapp.com

### Spoke: Recruiter Dashboard
- Repo: https://github.com/shulmeister/recruiter-dashboard
- Heroku app: `caregiver-lead-tracker`
- Live URL: https://caregiver-lead-tracker-9d0e6a8c7c20.herokuapp.com

### Spoke: Activity Tracker
- Repo: https://github.com/shulmeister/Colorado-CareAssist-Route-Tracker
- Heroku app: `cca-activity-tracker`
- Live URL: https://cca-activity-tracker-6d9a1d8e3933.herokuapp.com

### Marketing Dashboard (Built into Portal)
- Template: `templates/marketing.html`
- Served by portal routes

## 4) Deployment Rule (Always)

All deployments flow from GitHub `main` to Heroku. Do not push directly to Heroku.
Planned hosting change: move off Heroku to a self-hosted Mac mini starting Monday, February 2, 2026.

```bash
git add -A
git commit -m "Description"
git push origin main
```

## 5) Key Files

### Portal
- `portal_app.py` - FastAPI hub and routes
- `portal_auth.py`, `portal_database.py`, `portal_models.py`

### Gigi
- `gigi/main.py` - voice + SMS handlers
- `gigi/knowledge_base.md` - voice agent knowledge base
- `gigi/system_prompt.txt` - system prompt

### WellSky
- `services/wellsky_service.py` - API client and mock mode

### Marketing
- `services/marketing/` - API integrations
- `templates/marketing.html` - dashboard UI

## 6) Authentication + SSO

- Google OAuth 2.0 for portal login
- Domain restriction: `coloradocareassist.com`
- Portal provides SSO tokens to spokes where applicable

## 6.1) Core Environment Variables (Portal)

```bash
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback
APP_SECRET_KEY=...
ALLOWED_DOMAINS=coloradocareassist.com
DATABASE_URL=...
```

### 6.2) Gigi Environment Variables

```bash
RETELL_API_KEY=...
GEMINI_API_KEY=...
RINGCENTRAL_CLIENT_ID=...
RINGCENTRAL_CLIENT_SECRET=...
RINGCENTRAL_JWT_TOKEN=...
BEETEXTING_CLIENT_ID=...
BEETEXTING_CLIENT_SECRET=...
BEETEXTING_API_KEY=...
BEETEXTING_FROM_NUMBER=...
WELLSKY_CLIENT_ID=...
WELLSKY_CLIENT_SECRET=...
WELLSKY_AGENCY_ID=...
WELLSKY_ENVIRONMENT=production
GIGI_SMS_AUTOREPLY_ENABLED=true
GIGI_SMS_AFTER_HOURS_ONLY=true
GIGI_OFFICE_HOURS_START=08:00
GIGI_OFFICE_HOURS_END=17:00
```

### 6.3) Marketing Environment Variables (Common)

```bash
BREVO_API_KEY=...
FACEBOOK_ACCESS_TOKEN=...
FACEBOOK_AD_ACCOUNT_ID=...
GA4_PROPERTY_ID=...
GOOGLE_SERVICE_ACCOUNT_JSON=...
GBP_LOCATION_IDS=...
LINKEDIN_ACCESS_TOKEN=...
PINTEREST_ACCESS_TOKEN=...
TIKTOK_ACCESS_TOKEN=...
TIKTOK_ADVERTISER_ID=...
GOOGLE_ADS_DEVELOPER_TOKEN=...
GOOGLE_ADS_CUSTOMER_ID=...
GOOGLE_ADS_REFRESH_TOKEN=...
GOOGLE_ADS_OAUTH_CLIENT_ID=...
GOOGLE_ADS_OAUTH_CLIENT_SECRET=...
```

Gigi-specific and marketing API details live in `gigi/README.md` and `services/marketing/` docs.

## 7) Gigi Overview

Gigi handles after-hours voice and SMS.
- Voice: Retell AI webhook (staged)
- SMS: BeeTexting/RingCentral webhook (after-hours only)
- WellSky actions: clock in/out, call-outs, task + care alert logging

Details: `gigi/README.md`

## 8) Known Constraints

- **Nested repos**: each `dashboards/*` folder has its own `.git` and remote.
- **No Supabase**: Supabase CRM is removed and should not be referenced.

## 9) Sales Dashboard (Spoke)

**Tech stack:** FastAPI + PostgreSQL backend, React Admin frontend (build in `frontend/dist`).
**Repo:** https://github.com/shulmeister/sales-dashboard
**Heroku app:** `careassist-tracker`

**Key files**:
- `dashboards/sales/app.py` - main FastAPI app
- `dashboards/sales/models.py` - SQLAlchemy models
- `dashboards/sales/frontend/` - React Admin UI

**Local run**:
```bash
uvicorn app:app --reload --port 8000
```

**Frontend build (required for UI changes)**:
```bash
cd frontend
npm run build
```

**Core features**:
- CRM for contacts/companies/deals
- Activity tracking (visits, expenses, logs)
- AI document parsing (Gemini) for PDFs/receipts/cards

## 10) Recruiter Dashboard (Spoke)

**Tech stack:** Flask + SQLAlchemy + PostgreSQL.
**Repo:** https://github.com/shulmeister/recruiter-dashboard
**Heroku app:** `caregiver-lead-tracker`

**Key files**:
- `dashboards/recruitment/app.py` - main Flask app
- `dashboards/recruitment/models.py` - SQLAlchemy models
- `dashboards/recruitment/fetch_facebook_leads.py` - FB Lead Ads sync

**Local run**:
```bash
flask run --port 5000
```

**Core features**:
- Candidate pipeline
- Facebook Lead Ads sync (manual or scheduled)

## 11) Where to Find Details

- Gigi: `gigi/README.md`, `gigi/knowledge_base.md`
- Sales: `sales/README.md` and other files in `sales/`
- Recruiting: `recruiting/README.md`, `recruiting/AGENTS.md`
- WellSky roadmap: `docs/WELLSKY_API_INTEGRATION_ROADMAP.md`
- WellSky knowledge: `docs/WELLSKY_PERSONAL_CARE_KNOWLEDGE.md`
- Marketing strategy: `docs/MARKETING_STRATEGY_JAN2026.md`
- Archived notes: `docs/archive/README.md`

## 12) Smoke Tests / Health Checks

Local or staging smoke script (if present):

```bash
./scripts/smoke.sh
```

Expected endpoints:
- Portal health: `/health`
- Marketing shell: `/marketing`
- Portal → Sales: `/sales`
- Portal → Recruiter: `/recruitment`
- Portal → Activity: `/activity-tracker`
- Gigi health: `/gigi/`

## 13) OAuth Setup (Portal)

High-level steps:
1. Create/locate Google OAuth client in Google Cloud Console.
2. Add redirect URI(s): `https://<portal-host>/auth/callback`.
3. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` on Heroku.
4. Ensure `ALLOWED_DOMAINS=coloradocareassist.com`.

## 14) Heroku Apps + DNS Notes

Primary apps:
- `careassist-unified` (Portal + Gigi)
- `careassist-tracker` (Sales)
- `caregiver-lead-tracker` (Recruiter)
- `cca-activity-tracker` (Activity Tracker)

DNS (current):
- Portal domain points to Heroku app `careassist-unified`.

## 15) Troubleshooting / Common Fixes

- Verify repo before commits: `git remote -v`.
- Login issues: confirm correct OAuth client and redirect URI.
- Gigi SMS issues: check RingCentral credentials and webhook route.
- Data missing in a spoke: confirm you're in the correct nested repo and deployed via GitHub.

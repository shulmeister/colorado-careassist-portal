# AGENTS.md — Colorado CareAssist Portal Guide for AI Agents

> **Read this first.** This document explains everything an AI agent needs to know to work on the Colorado CareAssist Portal project.

---

## 1. Project Overview

**Colorado CareAssist Portal** is a hub-and-spoke application system for a Colorado home care agency. The Portal is the central hub with clickable tiles that link to separate dashboard applications (spokes).

### Architecture: Hub-and-Spoke with Nested Git Repos

```
colorado-careassist-portal/          ← THE HUB (this repo)
├── portal_app.py                    ← Main FastAPI application
├── templates/
│   ├── portal.html                  ← Portal homepage
│   └── marketing.html               ← Marketing Dashboard (built-in)
├── services/marketing/              ← Marketing API integrations
└── dashboards/                      ← NESTED GIT REPOS (spokes)
    ├── sales/                       ← Sales Dashboard (own .git)
    ├── recruitment/                 ← Recruiter Dashboard (own .git)
    └── activity-tracker/            ← Activity Tracker (own .git)
```

**CRITICAL**: Each folder in `dashboards/` is its own independent git repository. They are NOT submodules - they have their own `.git` folders and remotes.

---

## 2. Component Reference

### The Hub: Portal

| Property | Value |
|----------|-------|
| **Local Path** | `/Users/shulmeister/Documents/GitHub/colorado-careassist-portal` |
| **GitHub** | `https://github.com/shulmeister/colorado-careassist-portal` |
| **Heroku App** | `portal-coloradocareassist` |
| **Live URL** | `https://portal.coloradocareassist.com` |
| **Tech Stack** | FastAPI, Jinja2, PostgreSQL, Python 3.11 |

### Spoke 1: Sales Dashboard

| Property | Value |
|----------|-------|
| **Local Path** | `/Users/shulmeister/Documents/GitHub/colorado-careassist-portal/dashboards/sales` |
| **GitHub** | `https://github.com/shulmeister/sales-dashboard` |
| **Heroku App** | `careassist-tracker` |
| **Live URL** | `https://careassist-tracker-0fcf2cecdb22.herokuapp.com` |
| **Tech Stack** | FastAPI, React-Admin, PostgreSQL |
| **Features** | CRM, Contacts, Companies, Deals, Activity Tracking, Document Scanning |

### Spoke 2: Recruiter Dashboard

| Property | Value |
|----------|-------|
| **Local Path** | `/Users/shulmeister/Documents/GitHub/colorado-careassist-portal/dashboards/recruitment` |
| **GitHub** | `https://github.com/shulmeister/recruiter-dashboard` |
| **Heroku App** | `caregiver-lead-tracker` |
| **Live URL** | `https://caregiver-lead-tracker-9d0e6a8c7c20.herokuapp.com` |
| **Tech Stack** | Flask, SQLAlchemy, PostgreSQL |
| **Features** | Caregiver recruitment, candidate pipeline, Facebook Lead Ads sync |

### Spoke 3: Marketing Dashboard (Built into Portal)

| Property | Value |
|----------|-------|
| **Local Path** | `/Users/shulmeister/Documents/GitHub/colorado-careassist-portal/templates/marketing.html` |
| **GitHub** | Same as Portal |
| **Heroku App** | Same as Portal |
| **Live URL** | `https://portal.coloradocareassist.com/marketing` |
| **Tech Stack** | Jinja2, Chart.js, FastAPI routes |
| **Features** | Social media metrics, Google Ads, GA4, GBP, Facebook, Instagram, LinkedIn, Pinterest, TikTok |

### Spoke 4: Activity Tracker

| Property | Value |
|----------|-------|
| **Local Path** | `/Users/shulmeister/Documents/GitHub/colorado-careassist-portal/dashboards/activity-tracker` |
| **GitHub** | `https://github.com/shulmeister/Colorado-CareAssist-Route-Tracker` |
| **Heroku App** | `cca-activity-tracker` |
| **Live URL** | `https://cca-activity-tracker-6d9a1d8e3933.herokuapp.com` |
| **Tech Stack** | FastAPI, PDF Parser, Tesseract OCR |
| **Features** | PDF route import, mileage tracking, business card OCR |

---

## 3. Deployment Rules

### For Portal Changes
```bash
cd /Users/shulmeister/Documents/GitHub/colorado-careassist-portal
git add -A && git commit -m "Description" && git push origin main && git push heroku main
```

### For Sales Dashboard Changes
```bash
cd /Users/shulmeister/Documents/GitHub/colorado-careassist-portal/dashboards/sales
git add -A && git commit -m "Description" && git push origin main && git push heroku main
```

### For Recruiter Dashboard Changes
```bash
cd /Users/shulmeister/Documents/GitHub/colorado-careassist-portal/dashboards/recruitment
git add -A && git commit -m "Description" && git push origin main && git push heroku main
```

### For Activity Tracker Changes
```bash
cd /Users/shulmeister/Documents/GitHub/colorado-careassist-portal/dashboards/activity-tracker
git add -A && git commit -m "Description" && git push origin main && git push heroku main
```

### For Marketing Dashboard Changes
Marketing is part of the Portal - deploy from portal root.

---

## 4. Key Files Reference

### Portal (`portal_app.py`)
- Main FastAPI application (~2000+ lines)
- Routes for `/`, `/marketing`, `/sales`, `/recruitment`, etc.
- Google OAuth authentication
- Marketing API endpoints (`/api/marketing/*`)

### Marketing Services (`services/marketing/`)
| File | Purpose |
|------|---------|
| `metrics_service.py` | Aggregates all marketing metrics |
| `facebook_ads_service.py` | Facebook/Meta Ads API |
| `google_ads_service.py` | Google Ads API |
| `ga4_service.py` | Google Analytics 4 |
| `gbp_service.py` | Google Business Profile |
| `instagram_service.py` | Instagram Graph API |
| `linkedin_service.py` | LinkedIn Marketing API |
| `pinterest_service.py` | Pinterest API |
| `tiktok_service.py` | TikTok Marketing API |

### Sales Dashboard (`dashboards/sales/`)
| File | Purpose |
|------|---------|
| `app.py` | Main FastAPI application |
| `models.py` | SQLAlchemy ORM models |
| `ai_document_parser.py` | Gemini-based document parsing |
| `frontend/` | React-Admin frontend |

---

## 5. Environment Variables

### Portal (Heroku: `portal-coloradocareassist`)
```
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
DATABASE_URL
FACEBOOK_ACCESS_TOKEN, FACEBOOK_AD_ACCOUNT_ID
GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CUSTOMER_ID
GA4_PROPERTY_ID
LINKEDIN_ACCESS_TOKEN
PINTEREST_ACCESS_TOKEN
TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET
```

### Sales Dashboard (Heroku: `careassist-tracker`)
```
DATABASE_URL
GEMINI_API_KEY
OPENAI_API_KEY
GOOGLE_SERVICE_ACCOUNT_KEY
BREVO_API_KEY
```

---

## 6. Common Issues & Fixes

### Wrong Directory
Always check which repo you're in:
```bash
git remote -v
```

### Push to Both Remotes
Always push to both GitHub AND Heroku:
```bash
git push origin main && git push heroku main
```

### Heroku Logs
```bash
heroku logs -n 100 -a portal-coloradocareassist
heroku logs -n 100 -a careassist-tracker
```

### Restart Heroku
```bash
heroku restart -a portal-coloradocareassist
```

---

## 7. User Preferences

### The User Wants:
- ✅ All changes synced to Local + GitHub + Heroku
- ✅ Clear documentation
- ✅ Problems fixed completely, not just identified
- ✅ Minimal back-and-forth

### The User Hates:
- ❌ Broken deployments
- ❌ Duplicate/confusing folder structures
- ❌ Having to re-explain the project
- ❌ Half-finished work

---

## 8. Folder Structure Warning

There are duplicate folders in two locations:
- `/Users/shulmeister/Documents/GitHub/` (some standalone copies)
- `/Users/shulmeister/Library/Mobile Documents/com~apple~CloudDocs/Documents/GitHub/` (iCloud)

**The canonical source of truth is**:
- **Portal**: `/Users/shulmeister/Documents/GitHub/colorado-careassist-portal`
- **Sales**: Inside portal at `dashboards/sales/` (nested git repo)
- **Recruiter**: Inside portal at `dashboards/recruitment/` (nested git repo)
- **Activity Tracker**: Inside portal at `dashboards/activity-tracker/` (nested git repo)

Standalone folders like `/Users/shulmeister/Documents/GitHub/sales-dashboard/` may be outdated clones.

---

*Last Updated: December 29, 2025*


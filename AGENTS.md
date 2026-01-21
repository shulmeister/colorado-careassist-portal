# AGENTS.md — Colorado CareAssist Portal Guide for AI Agents

> **Read this first.** This document explains everything an AI agent needs to know to work on the Colorado CareAssist Portal project.

---

## 1. Project Overview

**Colorado CareAssist Portal** is a hub-and-spoke application system for a Colorado non-medical home care agency. The Portal is the central hub with clickable tiles that link to separate dashboard applications (spokes).

### Architecture: Hub-and-Spoke with Nested Git Repos

```
colorado-careassist-portal/          ← THE HUB (this repo)
├── portal_app.py                    ← Main FastAPI application
├── gigi/                            ← GIGI AI AGENT (after-hours assistant)
│   ├── main.py                      ← Gigi FastAPI app (voice + SMS)
│   ├── knowledge_base.md            ← Gigi's knowledge base
│   └── system_prompt.txt            ← Voice agent system prompt
├── services/
│   └── wellsky_service.py           ← WellSky API integration
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

## 2. GIGI - After-Hours AI Agent

### What is Gigi?

Gigi is an AI-powered after-hours assistant that handles:
- **Phone calls** via Retell AI voice agent
- **SMS/Text messages** via RingCentral webhook integration
- **Automated actions** via WellSky scheduling system

### Gigi's Capabilities

| Channel | Capability | Status |
|---------|------------|--------|
| Voice (Retell) | Answer calls, identify callers, handle call-outs | ✅ Live |
| SMS (RingCentral) | Auto-reply to texts with AI-generated responses | ✅ Live |
| WellSky Integration | Look up shifts, clock in/out, report call-outs | ⏳ Ready for API key |

### Gigi Architecture

```
Inbound SMS → RingCentral Webhook → /gigi/webhook/ringcentral-sms
                                            ↓
                                   Detect Intent (clock_out, callout, schedule)
                                            ↓
                                   WellSky Lookup (shift data)
                                            ↓
                                   Take Action (clock out, report callout)
                                            ↓
                                   Generate Response (Gemini AI)
                                            ↓
                                   Send Reply (RingCentral SMS)
```

### Gigi Files

| File | Purpose |
|------|---------|
| `gigi/main.py` | FastAPI app with voice tools and SMS webhook handlers |
| `gigi/knowledge_base.md` | Knowledge base for Retell AI voice agent |
| `gigi/system_prompt.txt` | System prompt for voice conversations |
| `services/wellsky_service.py` | WellSky API client with EVV functions |

### Gigi Environment Variables

```bash
# Retell AI (Voice)
RETELL_API_KEY=key_xxxxx

# RingCentral (SMS)
RINGCENTRAL_CLIENT_ID=cqaJllTcFyndtgsussicsd
RINGCENTRAL_CLIENT_SECRET=xxxxx
RINGCENTRAL_JWT_TOKEN=eyJxxxxx

# Gemini AI (Response Generation)
GEMINI_API_KEY=AIzaSyxxxxx

# WellSky (Scheduling - add when available)
WELLSKY_API_KEY=xxxxx
WELLSKY_API_SECRET=xxxxx
WELLSKY_AGENCY_ID=xxxxx
```

### WellSky Integration Functions

The `services/wellsky_service.py` provides these functions for Gigi:

| Function | Purpose |
|----------|---------|
| `get_caregiver_by_phone(phone)` | Look up caregiver by phone number |
| `get_caregiver_current_shift(phone)` | Get the shift they're currently on |
| `get_caregiver_upcoming_shifts(phone, days)` | Get upcoming schedule |
| `clock_in_shift(shift_id, time, notes)` | Clock caregiver into shift |
| `clock_out_shift(shift_id, time, notes)` | Clock caregiver out of shift |
| `report_callout(phone, reason)` | Report call-out, trigger coverage |

**Mock Mode**: When `WELLSKY_API_KEY` is not set, the service runs in mock mode with sample data.

---

## 3. Component Reference

### The Hub: Portal + Gigi

| Property | Value |
|----------|-------|
| **Local Path** | `/Users/shulmeister/Documents/GitHub/careassist-unified-portal` |
| **GitHub** | `https://github.com/shulmeister/colorado-careassist-portal` |
| **Heroku App** | `careassist-unified` |
| **Live URL** | `https://careassist-unified-0a11ddb45ac0.herokuapp.com` |
| **Gigi URL** | `https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/` |
| **Tech Stack** | FastAPI, Jinja2, PostgreSQL, Python 3.11 |

### Phone Numbers

| Number | Purpose |
|--------|---------|
| 719-428-3999 | Primary caregiver line (most SMS traffic) |
| 303-757-1777 | Secondary line / On-call manager |

### Spoke 1: Sales Dashboard

| Property | Value |
|----------|-------|
| **Local Path** | `dashboards/sales` |
| **GitHub** | `https://github.com/shulmeister/sales-dashboard` |
| **Heroku App** | `careassist-tracker` |
| **Live URL** | `https://careassist-tracker-0fcf2cecdb22.herokuapp.com` |
| **Tech Stack** | FastAPI, PostgreSQL |
| **Features** | CRM, Contacts, Companies, Deals, Activity Tracking, Document Scanning |

### Spoke 2: Recruiter Dashboard

| Property | Value |
|----------|-------|
| **Local Path** | `dashboards/recruitment` |
| **GitHub** | `https://github.com/shulmeister/recruiter-dashboard` |
| **Heroku App** | `caregiver-lead-tracker` |
| **Live URL** | `https://caregiver-lead-tracker-9d0e6a8c7c20.herokuapp.com` |
| **Tech Stack** | Flask, SQLAlchemy, PostgreSQL |
| **Features** | Caregiver recruitment, candidate pipeline, Facebook Lead Ads sync |

### Spoke 3: Marketing Dashboard (Built into Portal)

| Property | Value |
|----------|-------|
| **Local Path** | `templates/marketing.html` |
| **GitHub** | Same as Portal |
| **Heroku App** | Same as Portal |
| **Live URL** | `https://portal.coloradocareassist.com/marketing` |
| **Tech Stack** | Jinja2, Chart.js, FastAPI routes |
| **Features** | Social media metrics, Google Ads, GA4, GBP, Facebook, Instagram, LinkedIn, Pinterest, TikTok |

### Spoke 4: Activity Tracker

| Property | Value |
|----------|-------|
| **Local Path** | `dashboards/activity-tracker` |
| **GitHub** | `https://github.com/shulmeister/Colorado-CareAssist-Route-Tracker` |
| **Heroku App** | `cca-activity-tracker` |
| **Live URL** | `https://cca-activity-tracker-6d9a1d8e3933.herokuapp.com` |
| **Tech Stack** | FastAPI, PDF Parser, Tesseract OCR |
| **Features** | PDF route import, mileage tracking, business card OCR |

---

## 4. Deployment Rules

### For Portal + Gigi Changes
```bash
cd /Users/shulmeister/Documents/GitHub/careassist-unified-portal
git add -A && git commit -m "Description" && git push origin main && git push heroku main
# Heroku app: careassist-unified
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

---

## 5. Key Files Reference

### Portal (`portal_app.py`)
- Main FastAPI application (~2000+ lines)
- Routes for `/`, `/marketing`, `/sales`, `/recruitment`, etc.
- Google OAuth authentication
- Marketing API endpoints (`/api/marketing/*`)

### Gigi (`gigi/main.py`)
- After-hours AI agent (~1400+ lines)
- Retell AI voice tool functions
- SMS webhook handlers (RingCentral, Beetexting)
- WellSky-aware intent detection and action
- Gemini AI response generation

### WellSky Service (`services/wellsky_service.py`)
- Full WellSky API client (~1400+ lines)
- Client, Caregiver, Shift management
- EVV clock in/out functions
- Call-out reporting
- Mock mode for development

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
heroku logs -n 100 -a careassist-unified      # Portal + Gigi
heroku logs -n 100 -a careassist-tracker      # Sales Dashboard
```

### Restart Heroku
```bash
heroku restart -a careassist-unified
```

### Test Gigi SMS
```bash
curl -X POST https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/test/sms-reply \
  -d "from_number=+17205551234" \
  -d "message=I cant clock out of my shift"
```

---

## 7. User Preferences

### The User Wants:
- ✅ All changes synced to Local + GitHub + Heroku
- ✅ Clear documentation
- ✅ Problems fixed completely, not just identified
- ✅ Minimal back-and-forth
- ✅ Gigi to DO work, not just take messages
- ✅ Gemini AI as the default AI provider

### The User Hates:
- ❌ Broken deployments
- ❌ Duplicate/confusing folder structures
- ❌ Having to re-explain the project
- ❌ Half-finished work
- ❌ Supabase (removed from codebase)
- ❌ AI that just logs messages instead of taking action

---

## 8. Removed/Deprecated

### Supabase CRM (REMOVED January 2026)
The `sales/frontend/` directory containing a Supabase-based React Admin CRM has been deleted. It was an abandoned project that was never deployed (Supabase project paused since December 2025).

**Do not reference or attempt to use:**
- `sales/frontend/`
- Any Supabase Edge Functions
- `ra-supabase-*` packages

---

## 9. Folder Structure Warning

There are duplicate folders in two locations:
- `/Users/shulmeister/Documents/GitHub/` (some standalone copies)
- `/Users/shulmeister/Library/Mobile Documents/com~apple~CloudDocs/Documents/GitHub/` (iCloud)

**The canonical source of truth is**:
- **Portal + Gigi**: `/Users/shulmeister/Documents/GitHub/careassist-unified-portal`
- **Sales**: Inside portal at `dashboards/sales/` (nested git repo)
- **Recruiter**: Inside portal at `dashboards/recruitment/` (nested git repo)
- **Activity Tracker**: Inside portal at `dashboards/activity-tracker/` (nested git repo)

---

*Last Updated: January 21, 2026*

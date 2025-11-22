# 📍 Codebase Locations - Quick Reference

**Last Updated**: November 22, 2025

## 🚀 Desktop Quick Launch

Inside `~/Documents/GitHub` there’s exactly one folder per tile. Each is a symlink that points into this repo:

| Desktop Folder | Actual Path (inside repo) | Notes |
|----------------|---------------------------|-------|
| `colorado-careassist-portal` | `.` | Portal hub (FastAPI + marketing dashboard) |
| `sales-dashboard` | `dashboards/sales/` | Atomic CRM based Sales app |
| `activity-tracker` | `dashboards/activity-tracker/` | Legacy Visits/Activity tracker (PDF + OCR) |
| `recruiter-dashboard` | `dashboards/recruitment/` | Flask recruiter app |
| `marketing-dashboard` | `dashboards/marketing/` | Marketing services/templates (deployed with portal) |

This document provides EXACT file paths and git remotes for all components of the Colorado CareAssist Portal system. Every spoke is its own git repository (with its own `.git` directory), so keep committing inside the tile folder you’re working on—the portal repo just ignores those directories now.

## 🎯 The Hub: Portal

**Local Path**: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal`

**Git Remotes**:
- GitHub: `https://github.com/shulmeister/colorado-careassist-portal.git`
- Heroku: `https://git.heroku.com/portal-coloradocareassist.git`

**Deploy Commands**:
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal
git push origin main    # GitHub
git push heroku main    # Heroku
```

**Key Files**:
- `portal_app.py` - Main FastAPI app
- `templates/portal.html` - Portal UI
- `templates/marketing.html` - Marketing Dashboard (built-in)
- `templates/recruitment_embedded.html` - Recruiter Dashboard wrapper

---

## 📊 Spoke 1: Sales Dashboard

**Local Path**: `~/Documents/GitHub/sales-dashboard` → `colorado-careassist-portal/dashboards/sales/`

**Git Remotes**:
- GitHub: `https://github.com/shulmeister/sales-dashboard.git`
- Heroku: `https://git.heroku.com/careassist-tracker.git`

**Deploy Commands**:
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/sales
git push origin main    # GitHub
git push heroku main    # Heroku
```

**Key Files**:
- `app.py` - Main Flask/FastAPI app
- `templates/dashboard.html` - Dashboard UI
- `portal_auth_middleware.py` - Portal authentication

**IMPORTANT**: This is a **nested git repository** - it has its own `.git` folder!

---

## 👥 Spoke 2: Recruiter Dashboard

**Local Path**: `~/Documents/GitHub/recruiter-dashboard` → `colorado-careassist-portal/dashboards/recruitment/`

**Git Remotes**:
- GitHub: `https://github.com/shulmeister/recruiter-dashboard.git`
- Heroku: `https://git.heroku.com/caregiver-lead-tracker.git`

**Deploy Commands**:
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/recruitment
git push origin main    # GitHub
git push heroku main    # Heroku
```

**Key Files**:
- `app.py` - Main Flask app
- `portal_auth_middleware.py` - Portal authentication
- `templates/index.html` - Dashboard UI

**IMPORTANT**: This is a **nested git repository** - it has its own `.git` folder!

---

## 📈 Spoke 3: Marketing Dashboard

**NOT A SEPARATE REPO** - Built into the portal!

**Local Path**: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/templates/marketing.html`

**Routes**: `/marketing` (handled by `portal_app.py`)

**Deploy**: Same as portal - deploy from portal root

---

## 🧭 Spoke 4: Activity Tracker

**Local Path**: `~/Documents/GitHub/activity-tracker` → `colorado-careassist-portal/dashboards/activity-tracker/`

**Git Remotes**:
- GitHub: `https://github.com/shulmeister/Colorado-CareAssist-Route-Tracker.git`
- Heroku: `https://git.heroku.com/cca-activity-tracker.git`

**Deploy Commands**:
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/activity-tracker
git push origin main    # GitHub
git push heroku main    # Heroku
```

**Key Files**:
- `app.py` - Legacy Visits/Activity tracker FastAPI app
- `templates/dashboard.html` - UI
- `business_card_scanner.py`, `parser.py`, CSV import scripts

**IMPORTANT**: This is a **nested git repository** - it has its own `.git` folder!

---

## 🔍 How to Check Which Repo You're In

```bash
# Check current directory
pwd

# Check git remotes
git remote -v

# Check git status
git status
```

**Expected Outputs**:

**Portal**:
```
origin    https://github.com/shulmeister/colorado-careassist-portal.git
heroku    https://git.heroku.com/portal-coloradocareassist.git
```

**Sales Dashboard**:
```
origin    https://github.com/shulmeister/sales-dashboard.git
heroku    https://git.heroku.com/careassist-tracker.git
```

**Recruiter Dashboard**:
```
origin    https://github.com/shulmeister/recruiter-dashboard.git (once created)
heroku    https://git.heroku.com/caregiver-lead-tracker.git
```

---

## ✅ Verification Checklist

Before starting work, verify:

- [ ] You know which component you're working on (Portal, Sales, Recruiter, or Marketing)
- [ ] You're in the correct directory (`pwd` shows the right path)
- [ ] Git remotes are correct (`git remote -v`)
- [ ] You push to BOTH GitHub AND Heroku after changes
- [ ] You're committing in the right git repo (not accidentally committing from parent directory)

---

## 🚨 Common Mistakes

1. **Committing from portal root when working on dashboards**
   - ❌ Wrong: `cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal && git commit`
   - ✅ Right: `cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/sales && git commit`

2. **Assuming all code is in one repo**
   - Each dashboard has its own git repository
   - Check `git remote -v` to see which repo you're in

3. **Forgetting to push to both remotes**
   - Always: `git push origin main && git push heroku main`

4. **Thinking Marketing Dashboard is separate**
   - It's in `templates/marketing.html` in the portal repo
   - Deploy from portal root, not a separate directory

---

## 📞 Quick Links

- **Portal GitHub**: https://github.com/shulmeister/colorado-careassist-portal
- **Sales Dashboard GitHub**: https://github.com/shulmeister/sales-dashboard
- **Recruiter Dashboard GitHub**: https://github.com/shulmeister/recruiter-dashboard
- **Activity Tracker GitHub**: https://github.com/shulmeister/Colorado-CareAssist-Route-Tracker
- **Portal Heroku**: https://portal-coloradocareassist-3e1a4bb34793.herokuapp.com
- **Sales Dashboard Heroku**: https://careassist-tracker-0fcf2cecdb22.herokuapp.com
- **Recruiter Dashboard Heroku**: https://caregiver-lead-tracker-9d0e6a8c7c20.herokuapp.com
- **Activity Tracker Heroku**: https://cca-activity-tracker-6d9a1d8e3933.herokuapp.com


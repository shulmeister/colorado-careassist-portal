# 📍 Codebase Locations - Quick Reference

**Last Updated**: December 29, 2025

---

## 🎯 THE CANONICAL SOURCE OF TRUTH

All development should happen in **ONE location**:

```
/Users/shulmeister/Documents/GitHub/colorado-careassist-portal/
```

This folder contains the Portal AND all dashboard spokes as nested git repos.

---

## 📁 Folder Structure

```
/Users/shulmeister/Documents/GitHub/colorado-careassist-portal/
├── portal_app.py                    # Main Portal FastAPI app
├── templates/
│   ├── portal.html                  # Portal homepage
│   └── marketing.html               # Marketing Dashboard
├── services/marketing/              # Marketing API services
├── dashboards/
│   ├── sales/                       # ← NESTED GIT REPO (Sales Dashboard)
│   │   ├── .git/
│   │   ├── app.py
│   │   └── frontend/
│   ├── recruitment/                 # ← NESTED GIT REPO (Recruiter Dashboard)
│   │   ├── .git/
│   │   └── app.py
│   └── activity-tracker/            # ← NESTED GIT REPO (Activity Tracker)
│       ├── .git/
│       └── app.py
├── README.md
├── AGENTS.md
└── CODEBASE_LOCATIONS.md            # This file
```

---

## 🚀 Quick Commands

### Portal (Hub)
```bash
cd /Users/shulmeister/Documents/GitHub/colorado-careassist-portal
git add -A && git commit -m "message" && git push origin main && git push heroku main
```

### Sales Dashboard
```bash
cd /Users/shulmeister/Documents/GitHub/colorado-careassist-portal/dashboards/sales
git add -A && git commit -m "message" && git push origin main && git push heroku main
```

### Recruiter Dashboard
```bash
cd /Users/shulmeister/Documents/GitHub/colorado-careassist-portal/dashboards/recruitment
git add -A && git commit -m "message" && git push origin main && git push heroku main
```

### Activity Tracker
```bash
cd /Users/shulmeister/Documents/GitHub/colorado-careassist-portal/dashboards/activity-tracker
git add -A && git commit -m "message" && git push origin main && git push heroku main
```

---

## 🔗 Git Remotes Reference

### Portal
```
origin    https://github.com/shulmeister/colorado-careassist-portal.git
heroku    https://git.heroku.com/portal-coloradocareassist.git
```

### Sales Dashboard (from dashboards/sales/)
```
origin    https://github.com/shulmeister/sales-dashboard.git
heroku    https://git.heroku.com/careassist-tracker.git
```

### Recruiter Dashboard (from dashboards/recruitment/)
```
origin    https://github.com/shulmeister/recruiter-dashboard.git
heroku    https://git.heroku.com/caregiver-lead-tracker.git
```

### Activity Tracker (from dashboards/activity-tracker/)
```
origin    https://github.com/shulmeister/Colorado-CareAssist-Route-Tracker.git
heroku    https://git.heroku.com/cca-activity-tracker.git
```

---

## 🌐 Live URLs

| App | Production URL |
|-----|----------------|
| Portal | https://portal.coloradocareassist.com |
| Sales Dashboard | https://careassist-tracker-0fcf2cecdb22.herokuapp.com |
| Recruiter Dashboard | https://caregiver-lead-tracker-9d0e6a8c7c20.herokuapp.com |
| Activity Tracker | https://cca-activity-tracker-6d9a1d8e3933.herokuapp.com |
| Marketing Dashboard | https://portal.coloradocareassist.com/marketing |

---

## ⚠️ Folders to IGNORE (Outdated/Duplicate)

These folders exist but are **NOT the source of truth**:

| Folder | Status | Action |
|--------|--------|--------|
| `/Users/shulmeister/Documents/GitHub/sales-dashboard/` | Outdated clone | Can be deleted |
| `/Users/shulmeister/Documents/GitHub/marketing-dashboard/` | Outdated | Can be deleted |
| `/Users/shulmeister/Documents/GitHub/recruiter-dashboard/` | Outdated clone | Can be deleted |
| `/Users/shulmeister/Documents/GitHub/client-satisfaction/` | Minimal/unused | Review before deleting |
| `/Users/shulmeister/Library/Mobile Documents/.../sales-dashboard/` | iCloud duplicate | Can be deleted |

**DO NOT** work in these folders - they will not deploy correctly.

---

## ✅ Before Starting Work

1. **Verify you're in the right directory**:
   ```bash
   pwd
   git remote -v
   ```

2. **Pull latest changes**:
   ```bash
   git pull origin main
   ```

3. **Check which component you're editing** (Portal vs Sales vs Recruiter vs Activity Tracker)

4. **After making changes, push to BOTH remotes**:
   ```bash
   git push origin main && git push heroku main
   ```

---

## 📞 Heroku Apps

| App Name | Purpose |
|----------|---------|
| `portal-coloradocareassist` | Main Portal + Marketing Dashboard |
| `careassist-tracker` | Sales Dashboard |
| `careassist-tracker-staging` | Sales Dashboard (Staging) |
| `caregiver-lead-tracker` | Recruiter Dashboard |
| `cca-activity-tracker` | Activity Tracker |
| `client-satisfaction` | Client Satisfaction (minimal) |

---

*For detailed agent instructions, see `AGENTS.md`*

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
# Note: Activity Tracker functionality is built into Sales Dashboard
# No separate Heroku app - uses careassist-tracker
```

---

## 🌐 Live URLs

| App | Production URL |
|-----|----------------|
| Portal | https://portal.coloradocareassist.com |
| Marketing Dashboard | https://portal.coloradocareassist.com/marketing |
| Sales Dashboard | https://careassist-tracker-0fcf2cecdb22.herokuapp.com |
| Recruiter Dashboard | https://caregiver-lead-tracker-8ad45742fa9c.herokuapp.com |
| Client Satisfaction | https://client-satisfaction-15d412babc2f.herokuapp.com |

---

## ✅ Cleanup Completed (December 29, 2025)

**Archived local folders** (moved to `_archived/`):
- `sales-dashboard/` → Use `dashboards/sales/` instead
- `marketing-dashboard/` → Built into Portal
- `recruiter-dashboard/` → Use `dashboards/recruitment/` instead
- `client-satisfaction/` → Use Heroku app directly
- `ccascanner/` → Superseded by Sales Dashboard

**Archived GitHub repos**: marketing-dashboard, hls-streaming-site, mytube, business-dashboard, marketing-dashboard-material, nextjs-boilerplate, cca-communications-dashboard

**Deleted Heroku apps** (redundant):
- `bizcard` → Functionality in Sales Dashboard
- `cca-activity-tracker` → Functionality in Sales Dashboard
- `cca-crm` → Replaced by Sales Dashboard

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

## 📞 Heroku Apps (Clean as of Dec 29, 2025)

| App Name | Purpose | Dyno |
|----------|---------|------|
| `portal-coloradocareassist` | Main Portal + Marketing Dashboard | Basic |
| `careassist-tracker` | Sales Dashboard (includes Activity Tracker) | Basic |
| `careassist-tracker-staging` | Sales Dashboard Staging | Pipeline |
| `caregiver-lead-tracker` | Recruiter Dashboard | Running |
| `client-satisfaction` | Client Satisfaction Dashboard | Eco (sleeps) |
| `goformz-automation` | GoFormz webhook automation | Running |
| `wellsky-converter-shulmeister` | WellSky payroll file converter | Running |
| `hls-mytube` | HLS video streaming (separate project) | Eco (sleeps) |

---

*For detailed agent instructions, see `AGENTS.md`*

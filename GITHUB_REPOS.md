# 📦 All GitHub Repositories - Complete List

**Last Verified**: November 13, 2025

## ✅ All Code is Safely Backed Up on GitHub/shulmeister

All repositories are synced and ready. You can access everything from any computer by cloning these repos.

---

## 🎯 Main Portal (Hub)

**Repository**: `colorado-careassist-portal`  
**GitHub**: https://github.com/shulmeister/colorado-careassist-portal  
**Local Path**: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal`  
**Heroku**: `portal-coloradocareassist` → `portal-coloradocareassist-3e1a4bb34793.herokuapp.com`

**Contains**:
- Main portal application (FastAPI)
- Portal templates and static files
- Database models and setup
- Authentication system
- Marketing Dashboard routes (integrated)
- Links to all dashboard spokes

**To clone on new computer**:
```bash
git clone https://github.com/shulmeister/colorado-careassist-portal.git
cd colorado-careassist-portal
```

---

## 📊 Dashboard Spokes

### 1. Sales Dashboard

**Repository**: `sales-dashboard`  
**GitHub**: https://github.com/shulmeister/sales-dashboard  
**Local Path**: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/sales/`  
**Heroku**: `careassist-tracker` → `careassist-tracker-0fcf2cecdb22.herokuapp.com`

**Contains**:
- Sales tracking application (Python FastAPI)
- Dashboard templates
- Lead Tracker tab
- Google Sheets integration
- Business card scanner

**To clone on new computer**:
```bash
git clone https://github.com/shulmeister/sales-dashboard.git
cd sales-dashboard
```

---

### 2. Recruiter Dashboard

**Repository**: `recruiter-dashboard`  
**GitHub**: https://github.com/shulmeister/recruiter-dashboard  
**Local Path**: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/recruitment/`  
**Heroku**: `caregiver-lead-tracker` → `caregiver-lead-tracker-9d0e6a8c7c20.herokuapp.com`

**Contains**:
- Caregiver recruitment application (Flask)
- Candidate pipeline management
- Facebook leads integration
- Portal authentication middleware

**To clone on new computer**:
```bash
git clone https://github.com/shulmeister/recruiter-dashboard.git
cd recruiter-dashboard
```

---

### 3. Marketing Dashboard

**Repository**: `marketing-dashboard`  
**GitHub**: https://github.com/shulmeister/marketing-dashboard  
**Local Path**: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/marketing/`  
**Heroku**: Deploys as part of portal (no separate Heroku app)

**Contains**:
- Marketing dashboard template (`marketing.html`)
- Marketing service modules:
  - Facebook/Instagram API service
  - Facebook Ads API service
  - Google Ads API service
  - Google Analytics 4 (GA4) service
  - Google Business Profile (GBP) service
  - Metrics aggregation service

**To clone on new computer**:
```bash
git clone https://github.com/shulmeister/marketing-dashboard.git
cd marketing-dashboard
```

---

## 🔄 Complete Setup on New Computer

### Step 1: Clone Portal (Hub)
```bash
git clone https://github.com/shulmeister/colorado-careassist-portal.git
cd colorado-careassist-portal
```

### Step 2: Clone Dashboard Spokes
```bash
# Sales Dashboard
cd dashboards
git clone https://github.com/shulmeister/sales-dashboard.git sales
cd sales
heroku git:remote -a careassist-tracker
cd ..

# Recruiter Dashboard
git clone https://github.com/shulmeister/recruiter-dashboard.git recruitment
cd recruitment
heroku git:remote -a caregiver-lead-tracker
cd ..

# Marketing Dashboard
git clone https://github.com/shulmeister/marketing-dashboard.git marketing
cd ..
```

### Step 3: Set Up Portal Heroku Remote
```bash
cd /path/to/colorado-careassist-portal
heroku git:remote -a portal-coloradocareassist
```

### Step 4: Verify Remotes
```bash
# Portal
git remote -v
# Should show: origin (GitHub) and heroku

# Each dashboard
cd dashboards/sales && git remote -v
cd ../recruitment && git remote -v
cd ../marketing && git remote -v
```

---

## 📋 Quick Reference: All GitHub URLs

1. **Portal**: https://github.com/shulmeister/colorado-careassist-portal
2. **Sales Dashboard**: https://github.com/shulmeister/sales-dashboard
3. **Recruiter Dashboard**: https://github.com/shulmeister/recruiter-dashboard
4. **Marketing Dashboard**: https://github.com/shulmeister/marketing-dashboard

---

## ✅ Verification Checklist

- [x] Portal repo exists on GitHub
- [x] Sales Dashboard repo exists on GitHub
- [x] Recruiter Dashboard repo exists on GitHub
- [x] Marketing Dashboard repo exists on GitHub
- [x] All repos have recent commits
- [x] All repos are synced (Desktop → GitHub → Heroku)
- [x] Documentation updated in README.md
- [x] Sync status documented in SYNC_STATUS.md

---

## 🚀 Standard Workflow (Desktop → GitHub → Heroku)

**For any changes**:
1. Make changes locally
2. Commit: `git add . && git commit -m "message"`
3. Push to GitHub: `git push origin main`
4. Push to Heroku: `git push heroku main`

**Or use the sync script**:
```bash
cd /path/to/colorado-careassist-portal
./SYNC_ALL_REPOS.sh
```

---

## 💾 Your Code is Safe!

All code is backed up on GitHub. Even if your desktop folder is inaccessible, you can:
1. Clone any repo from GitHub
2. Continue development
3. Deploy to Heroku
4. Everything will work exactly as before

**No data will be lost!** 🎉


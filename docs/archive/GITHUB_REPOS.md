# 📦 All GitHub Repositories - Complete List

**Last Verified**: November 13, 2025

## ✅ All Code is Safely Backed Up on GitHub/shulmeister

All repositories are synced and ready. You can access everything from any computer by cloning these repos.

---

## 🎯 Main Portal (Hub)

**Repository**: `colorado-careassist-portal`  
**GitHub**: https://github.com/shulmeister/colorado-careassist-portal  
**Local Path**: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal`  
**Mac Mini**: `portal-coloradocareassist` → `portal-coloradocareassist-3e1a4bb34793.coloradocareassist.com`

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
**Mac Mini**: `careassist-tracker` → `careassist-tracker-0fcf2cecdb22.coloradocareassist.com`

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
**Mac Mini**: `caregiver-lead-tracker` → `caregiver-lead-tracker-9d0e6a8c7c20.coloradocareassist.com`

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
**Mac Mini**: Deploys as part of portal (no separate Mac Mini app)

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

### 4. Activity Tracker

**Repository**: `Colorado-CareAssist-Route-Tracker`  
**GitHub**: https://github.com/shulmeister/Colorado-CareAssist-Route-Tracker  
**Local Path**: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/activity-tracker/`  
**Mac Mini**: `cca-activity-tracker` → `https://portal.coloradocareassist.com/activity`

**Contains**:
- Original Visits/Activity Tracker (FastAPI)
- Business card scanner + CSV ingestion + Google Sheets sync
- Summary, Visits, Uploads, Activity Log views

**To clone on new computer**:
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards
git clone https://github.com/shulmeister/Colorado-CareAssist-Route-Tracker.git activity-tracker
cd activity-tracker
mac-mini git:remote -a cca-activity-tracker
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
mac-mini git:remote -a careassist-tracker
cd ..

# Recruiter Dashboard
git clone https://github.com/shulmeister/recruiter-dashboard.git recruitment
cd recruitment
mac-mini git:remote -a caregiver-lead-tracker
cd ..

# Marketing Dashboard
git clone https://github.com/shulmeister/marketing-dashboard.git marketing
cd ..

# Activity Tracker
git clone https://github.com/shulmeister/Colorado-CareAssist-Route-Tracker.git activity-tracker
cd activity-tracker
mac-mini git:remote -a cca-activity-tracker
cd ..
```

### Step 3: Set Up Portal Mac Mini Remote
```bash
cd /path/to/colorado-careassist-portal
mac-mini git:remote -a portal-coloradocareassist
```

### Step 4: Verify Remotes
```bash
# Portal
git remote -v
# Should show: origin (GitHub) and mac-mini

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
5. **Activity Tracker**: https://github.com/shulmeister/Colorado-CareAssist-Route-Tracker

---

## ✅ Verification Checklist

- [x] Portal repo exists on GitHub
- [x] Sales Dashboard repo exists on GitHub
- [x] Recruiter Dashboard repo exists on GitHub
- [x] Marketing Dashboard repo exists on GitHub
- [x] All repos have recent commits
- [x] All repos are synced (Desktop → GitHub → Mac Mini)
- [x] Documentation updated in README.md
- [x] Sync status documented in SYNC_STATUS.md

---

## 🚀 Standard Workflow (Desktop → GitHub → Mac Mini)

**For any changes**:
1. Make changes locally
2. Commit: `git add . && git commit -m "message"`
3. Push to GitHub: `git push origin main`
4. Push to Mac Mini: `git push origin main`

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
3. Deploy to Mac Mini
4. Everything will work exactly as before

**No data will be lost!** 🎉


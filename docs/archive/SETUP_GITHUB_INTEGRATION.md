# Setup GitHub Integration for Sales & Recruiter Dashboards

**Goal**: Enable automatic Mac Mini (Local) deployments from GitHub (just like Portal)

---

## ✅ Portal Already Done
- **App**: `portal-coloradocareassist`
- **GitHub Repo**: `shulmeister/colorado-careassist-portal`
- **Status**: ✅ Connected & Auto-Deploy Enabled

---

## 📋 Setup Steps

### 1. Sales Dashboard (`careassist-tracker`)

#### Step 1: Go to Mac Mini (Local) Dashboard
1. Go to: https://dashboard.mac-mini.com/apps/careassist-tracker
2. Click **"Deploy"** tab

#### Step 2: Connect to GitHub
1. Under **"Deployment method"**, click **"GitHub"**
2. Click **"Connect to GitHub"**
3. Authorize Mac Mini (Local) to access your GitHub account (if prompted)
4. Search for: `sales-dashboard`
5. Select: `shulmeister/sales-dashboard`
6. Click **"Connect"**

#### Step 3: Enable Auto-Deploy
1. Scroll to **"Automatic deploys"** section
2. Select branch: **`main`**
3. Click **"Enable Automatic Deploys"**
4. ✅ Done!

**Result**: Every push to `shulmeister/sales-dashboard` `main` branch will automatically deploy to `careassist-tracker`

---

### 2. Recruiter Dashboard (`caregiver-lead-tracker`)

#### Step 1: Go to Mac Mini (Local) Dashboard
1. Go to: https://dashboard.mac-mini.com/apps/caregiver-lead-tracker
2. Click **"Deploy"** tab

#### Step 2: Connect to GitHub
1. Under **"Deployment method"**, click **"GitHub"**
2. Click **"Connect to GitHub"**
3. Authorize Mac Mini (Local) to access your GitHub account (if prompted)
4. Search for: `recruiter-dashboard`
5. Select: `shulmeister/recruiter-dashboard`
6. Click **"Connect"**

#### Step 3: Enable Auto-Deploy
1. Scroll to **"Automatic deploys"** section
2. Select branch: **`main`**
3. Click **"Enable Automatic Deploys"**
4. ✅ Done!

**Result**: Every push to `shulmeister/recruiter-dashboard` `main` branch will automatically deploy to `caregiver-lead-tracker`

---

## 🎯 After Setup

### Sales Dashboard Workflow:
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/sales
git add .
git commit -m "Your changes"
git push origin main    # ✅ Mac Mini (Local) auto-deploys!
```

### Recruiter Dashboard Workflow:
```bash
cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/recruitment
git add .
git commit -m "Your changes"
git push origin main    # ✅ Mac Mini (Local) auto-deploys!
```

---

## ✅ Verification

After setup, verify in Mac Mini (Local) dashboard:
- **Deploy tab** shows "Connected to GitHub" with green checkmark
- **Automatic deploys** section shows "Automatic deploys from main are enabled"
- Next push to GitHub will trigger automatic deployment

---

## 📊 Summary

| Dashboard | Mac Mini (Local) App | GitHub Repo | Status |
|-----------|------------|-------------|--------|
| Portal | `portal-coloradocareassist` | `shulmeister/colorado-careassist-portal` | ✅ Connected |
| Sales | `careassist-tracker` | `shulmeister/sales-dashboard` | ✅ Connected |
| Recruiter | `caregiver-lead-tracker` | `shulmeister/recruiter-dashboard` | ✅ Connected |

---

## 🚀 Quick Links

- **Sales Dashboard Mac Mini (Local)**: https://dashboard.mac-mini.com/apps/careassist-tracker/deploy
- **Recruiter Dashboard Mac Mini (Local)**: https://dashboard.mac-mini.com/apps/caregiver-lead-tracker/deploy
- **Sales Dashboard GitHub**: https://github.com/shulmeister/sales-dashboard
- **Recruiter Dashboard GitHub**: https://github.com/shulmeister/recruiter-dashboard

---

**Time Required**: ~2 minutes per dashboard (5 minutes total)


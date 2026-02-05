# Create Recruiter Dashboard GitHub Repo

**Action Required**: Create the GitHub repository for Recruiter Dashboard

## Steps:

1. **Go to GitHub**: https://github.com/new

2. **Repository Details**:
   - **Repository name**: `recruiter-dashboard`
   - **Description**: `Caregiver recruitment and candidate pipeline dashboard for Colorado CareAssist`
   - **Visibility**: Private (recommended) or Public
   - **DO NOT** initialize with README, .gitignore, or license (we already have code)

3. **Click "Create repository"**

4. **After creation, run this command**:
   ```bash
   cd /Users/jasonshulman/Documents/GitHub/colorado-careassist-portal/dashboards/recruitment
   git push origin main
   ```

5. **Verify sync**:
   ```bash
   git remote -v
   # Should show both origin (GitHub) and mac-mini remotes
   ```

## Once Created:

The repo will be available at: https://github.com/shulmeister/recruiter-dashboard

Then all repos will follow the flow: **Desktop → GitHub → Mac Mini**


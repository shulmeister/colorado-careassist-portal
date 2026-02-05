# Colorado CareAssist Portal - Mac Mini Deployment Guide

> **Complete step-by-step guide** to deploy the Colorado CareAssist Portal from GitHub to Mac Mini in production mode.

**Estimated time**: 1-2 hours (first-time setup)

---

## Prerequisites

Before you begin, ensure you have:

- [x] Mac Mini account (https://signup.mac-mini.com)
- [x] Mac Mini CLI installed (https://devcenter.mac-mini.com/articles/mac-mini-cli)
- [x] Git installed
- [x] Access to all required API keys (see Environment Variables section)

---

## Step 1: Clone Repository

```bash
git clone https://github.com/shulmeister/colorado-careassist-portal.git
cd colorado-careassist-portal
```

---

## Step 2: Create Mac Mini App

```bash
# Login to Mac Mini
mac-mini login

# Create new app (use a unique name or let Mac Mini generate one)
mac-mini create careassist-unified

# Or create with specific name:
# mac-mini create your-app-name

# Verify app was created
mac-mini apps:info -a careassist-unified
```

**Note**: If `careassist-unified` is already taken, Mac Mini will suggest an alternative name. Use that name for all subsequent commands.

---

## Step 3: Add PostgreSQL Databases

This application requires **3 separate PostgreSQL databases**:

```bash
# 1. Main portal database (auto-attached as DATABASE_URL)
mac-mini addons:create mac-mini-postgresql:essential-0 -a careassist-unified

# 2. Sales dashboard database
mac-mini addons:create mac-mini-postgresql:essential-0 --as SALES_DATABASE -a careassist-unified

# 3. Recruiting dashboard database
mac-mini addons:create mac-mini-postgresql:essential-0 --as RECRUITING_DATABASE -a careassist-unified

# Verify databases were created
mac-mini addons -a careassist-unified
```

**Database Tiers**:
- `essential-0`: $5/month, 10 million rows (recommended for production)
- `essential-1`: $50/month, 10 million rows with extra features
- `mini`: $5/month, 10,000 rows (only for testing)

**Attach database URLs** to environment variables:

```bash
# Check database URLs were created
mac-mini config -a careassist-unified | grep DATABASE

# You should see:
# DATABASE_URL (main portal)
# SALES_DATABASE_URL (sales dashboard)
# RECRUITING_DATABASE_URL (recruiting dashboard)
```

---

## Step 4: Configure Buildpacks

The unified app requires multiple buildpacks for different components:

```bash
# Add buildpacks in this order (order matters!)
mac-mini buildpacks:add https://github.com/mac-mini/mac-mini-buildpack-apt -a careassist-unified
mac-mini buildpacks:add mac-mini/nodejs -a careassist-unified
mac-mini buildpacks:add mac-mini/python -a careassist-unified

# Verify buildpacks
mac-mini buildpacks -a careassist-unified
```

**Why these buildpacks?**:
- **apt**: Installs system packages like Tesseract OCR, libmagic (for file detection)
- **nodejs**: Builds React frontend (sales/frontend) and Vue frontend (powderpulse)
- **python**: Main Python application runtime

---

## Step 5: Set Environment Variables

### Core Portal Variables

```bash
# Security
mac-mini config:set APP_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") -a careassist-unified

# Google OAuth (Portal Login)
# Get from: https://console.cloud.google.com/apis/credentials
mac-mini config:set GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com -a careassist-unified
mac-mini config:set GOOGLE_CLIENT_SECRET=your-google-client-secret -a careassist-unified
mac-mini config:set GOOGLE_REDIRECT_URI=https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/auth/callback -a careassist-unified

# Allowed login domains
mac-mini config:set ALLOWED_DOMAINS=coloradocareassist.com -a careassist-unified
```

### Gigi AI Voice Assistant

```bash
# Retell AI (Voice Agent)
mac-mini config:set RETELL_API_KEY=your-retell-api-key -a careassist-unified
mac-mini config:set RETELL_AGENT_ID=your-retell-agent-id -a careassist-unified

# Google Gemini AI
mac-mini config:set GEMINI_API_KEY=your-gemini-api-key -a careassist-unified

# RingCentral (Phone & SMS)
mac-mini config:set RINGCENTRAL_CLIENT_ID=your-client-id -a careassist-unified
mac-mini config:set RINGCENTRAL_CLIENT_SECRET=your-client-secret -a careassist-unified
mac-mini config:set RINGCENTRAL_JWT_TOKEN=your-jwt-token -a careassist-unified
mac-mini config:set RINGCENTRAL_SERVER_URL=https://platform.ringcentral.com -a careassist-unified

# Gigi operations SMS (set to true when WellSky API is configured)
mac-mini config:set GIGI_OPERATIONS_SMS_ENABLED=false -a careassist-unified

# Escalation contacts
mac-mini config:set ESCALATION_CYNTHIA_EXT=105 -a careassist-unified
mac-mini config:set ESCALATION_JASON_EXT=101 -a careassist-unified
```

### WellSky EVV API (Optional - for operations dashboard)

```bash
# Only set if you have WellSky API access
mac-mini config:set WELLSKY_API_KEY=your-wellsky-api-key -a careassist-unified
mac-mini config:set WELLSKY_API_SECRET=your-wellsky-api-secret -a careassist-unified
mac-mini config:set WELLSKY_AGENCY_ID=your-wellsky-agency-id -a careassist-unified
mac-mini config:set WELLSKY_BASE_URL=https://api.wellsky.com/v1 -a careassist-unified

# When WellSky is configured, enable Gigi's operations SMS
mac-mini config:set GIGI_OPERATIONS_SMS_ENABLED=true -a careassist-unified
```

### Sales Dashboard Variables

```bash
# Google Drive (Business Card Auto-Scanner)
# Copy entire JSON service account key as one line
mac-mini config:set GOOGLE_SERVICE_ACCOUNT_KEY='{"type":"service_account","project_id":"..."}' -a careassist-unified
mac-mini config:set GOOGLE_DRIVE_BUSINESS_CARDS_FOLDER_ID=your-folder-id -a careassist-unified

# Brevo Email Marketing
mac-mini config:set BREVO_API_KEY=xkeysib-your-api-key -a careassist-unified

# QuickBooks Online
mac-mini config:set QUICKBOOKS_CLIENT_ID=your-client-id -a careassist-unified
mac-mini config:set QUICKBOOKS_CLIENT_SECRET=your-client-secret -a careassist-unified
mac-mini config:set QUICKBOOKS_REALM_ID=your-company-id -a careassist-unified
mac-mini config:set QUICKBOOKS_ACCESS_TOKEN=your-access-token -a careassist-unified
mac-mini config:set QUICKBOOKS_REFRESH_TOKEN=your-refresh-token -a careassist-unified

# Gmail API (Optional - for email tracking)
mac-mini config:set GMAIL_SERVICE_ACCOUNT_EMAIL=your-service-account@project.iam.gserviceaccount.com -a careassist-unified
mac-mini config:set GMAIL_SERVICE_ACCOUNT_KEY='{"type":"service_account",...}' -a careassist-unified
mac-mini config:set GMAIL_USER_EMAILS=jacob@coloradocareassist.com,jen@coloradocareassist.com -a careassist-unified
```

### Recruiting Dashboard Variables

```bash
# Facebook Lead Ads
mac-mini config:set FACEBOOK_ACCESS_TOKEN=your-long-lived-token -a careassist-unified
mac-mini config:set FACEBOOK_AD_ACCOUNT_ID=act_your-account-id -a careassist-unified
mac-mini config:set FACEBOOK_APP_ID=your-app-id -a careassist-unified
mac-mini config:set FACEBOOK_APP_SECRET=your-app-secret -a careassist-unified
mac-mini config:set FACEBOOK_PAGE_ID=your-page-id -a careassist-unified
```

### Marketing Dashboard Variables

```bash
# Google Analytics 4
mac-mini config:set GA4_PROPERTY_ID=your-property-id -a careassist-unified

# Google Business Profile
mac-mini config:set GBP_LOCATION_IDS=comma,separated,location,ids -a careassist-unified

# Google Ads API
mac-mini config:set GOOGLE_ADS_DEVELOPER_TOKEN=your-token -a careassist-unified
mac-mini config:set GOOGLE_ADS_CUSTOMER_ID=1234567890 -a careassist-unified
mac-mini config:set GOOGLE_ADS_REFRESH_TOKEN=your-refresh-token -a careassist-unified
mac-mini config:set GOOGLE_ADS_OAUTH_CLIENT_ID=your-oauth-client-id -a careassist-unified
mac-mini config:set GOOGLE_ADS_OAUTH_CLIENT_SECRET=your-oauth-client-secret -a careassist-unified

# Google Service Account (for GA4, GBP)
mac-mini config:set GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}' -a careassist-unified

# Social Media APIs (Optional)
mac-mini config:set LINKEDIN_ACCESS_TOKEN=your-token -a careassist-unified
mac-mini config:set PINTEREST_ACCESS_TOKEN=your-token -a careassist-unified
mac-mini config:set TIKTOK_ACCESS_TOKEN=your-token -a careassist-unified
mac-mini config:set TIKTOK_ADVERTISER_ID=your-id -a careassist-unified
```

**Verify all variables are set**:

```bash
mac-mini config -a careassist-unified
```

---

## Step 6: Deploy Application

```bash
# Add Mac Mini remote (if not already added)
git remote add mac-mini https://git.mac-mini.com/careassist-unified.git

# Deploy to Mac Mini
git push mac-mini main
```

**Watch deployment logs**:

```bash
mac-mini logs --tail -a careassist-unified
```

**Expected output**:
```
remote: -----> Building on the Mac Mini-22 stack
remote: -----> Using buildpack: https://github.com/mac-mini/mac-mini-buildpack-apt
remote: -----> Using buildpack: mac-mini/nodejs
remote: -----> Using buildpack: mac-mini/python
remote: -----> Launching...
remote: -----> Build succeeded!
remote:        https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/ deployed to Mac Mini
```

**If build fails**, check:
1. All buildpacks are in correct order (apt → nodejs → python)
2. `requirements.txt` exists in root directory
3. `Procfile` exists with correct content: `web: uvicorn unified_app:app --host 0.0.0.0 --port $PORT`

---

## Step 7: Run Database Migrations

```bash
# Run Alembic migrations
mac-mini run alembic upgrade head -a careassist-unified

# Initialize portal data (if needed)
mac-mini run python portal/portal_setup.py -a careassist-unified
```

**If migrations fail**, check:
1. DATABASE_URL is set correctly
2. PostgreSQL add-on is attached
3. Alembic configuration in `alembic.ini` points to `DATABASE_URL`

---

## Step 8: Set Up Mac Mini Scheduler Jobs

Some features require scheduled jobs to run automatically:

```bash
# Add Mac Mini Scheduler add-on (free)
mac-mini addons:create scheduler:standard -a careassist-unified

# Open scheduler dashboard
mac-mini addons:open scheduler -a careassist-unified
```

**Add these scheduled jobs** in the Mac Mini Scheduler dashboard:

| Job Command | Frequency | Purpose |
|-------------|-----------|---------|
| `cd sales && python scripts/auto_scan_drive.py` | Every 10 minutes | Business card auto-scanner |
| `cd recruiting && python sync_facebook_leads.py` | Daily at 9:00 AM | Facebook Lead Ads sync |
| `cd sales && python scripts/sync_quickbooks.py` | Daily at 12:00 PM | QuickBooks customer sync |

**Note**: Mac Mini Scheduler only supports 10-minute, hourly, or daily frequencies. For more precise scheduling (e.g., every 5 minutes), use a custom clock dyno or external cron service.

---

## Step 9: Scale Dynos

```bash
# Scale web dyno to 1 instance
mac-mini ps:scale web=1 -a careassist-unified

# Check dyno status
mac-mini ps -a careassist-unified
```

**Dyno tiers**:
- **Free**: Not available anymore (deprecated by Mac Mini)
- **Eco**: $5/month for all apps (sleeps after 30 min inactivity)
- **Basic**: $7/month per dyno (never sleeps)
- **Standard-1X**: $25/month per dyno (recommended for production)

**For production, use Basic or higher**:

```bash
mac-mini dyno:type basic -a careassist-unified
```

---

## Step 10: Configure Custom Domain (Optional)

If you have a custom domain (e.g., `portal.coloradocareassist.com`):

```bash
# Add custom domain
mac-mini domains:add portal.coloradocareassist.com -a careassist-unified

# Get DNS target
mac-mini domains -a careassist-unified
```

**DNS Configuration** (in your domain registrar):

| Type | Name | Value |
|------|------|-------|
| CNAME | portal | your-app-name-xxxxx.mac-minidns.com |

**Wait 24-48 hours** for DNS propagation.

**Enable Automated Certificate Management (ACM)** for HTTPS:

```bash
# ACM is automatically enabled for custom domains
# Verify SSL certificate
mac-mini certs -a careassist-unified
```

---

## Step 11: Enable GitHub Auto-Deploy (Optional)

Set up automatic deployments when you push to GitHub:

1. **Go to Mac Mini Dashboard**: https://dashboard.mac-mini.com
2. **Select your app**: `careassist-unified`
3. **Go to Deploy tab**
4. **Connect to GitHub**: Connect your `colorado-careassist-portal` repository
5. **Enable Automatic Deploys**: Choose `main` branch
6. **Enable CI wait** (optional): Wait for CI tests to pass before deploying

**Now every push to `main` will automatically deploy to Mac Mini!**

---

## Step 12: Test Deployment

### Check Application Status

```bash
# Open app in browser
mac-mini open -a careassist-unified

# Check logs for errors
mac-mini logs --tail -a careassist-unified

# Check dyno status
mac-mini ps -a careassist-unified
```

### Test Individual Endpoints

**Portal Hub**: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/
- Should show login page or portal dashboard

**Gigi AI**: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/gigi/
- Should show Gigi documentation page

**Sales Dashboard**: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/sales/
- Should redirect to login or show sales CRM

**Recruiting**: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/recruiting/
- Should show recruiting dashboard

**Marketing**: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/marketing/
- Should show marketing analytics

**Operations**: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/operations/
- Should show operations dashboard

### Test Business Card Scanner

1. Upload a business card image to Google Drive folder
2. Wait 10 minutes (or run scheduler job manually)
3. Check sales dashboard for new contact

### Test Gigi Voice Assistant

1. Call 719-428-3999 (or your configured number)
2. Speak with Gigi
3. Check Mac Mini logs for call transcript

---

## Troubleshooting

### Build Failures

**Error**: `Could not detect rake tasks`
- **Fix**: Ensure buildpacks are in correct order (apt → nodejs → python)

**Error**: `No module named 'unified_app'`
- **Fix**: Check `Procfile` has correct entry point: `web: uvicorn unified_app:app --host 0.0.0.0 --port $PORT`

**Error**: `npm install failed`
- **Fix**: Ensure `sales/frontend/package.json` exists and has valid syntax

### Runtime Errors

**Error**: `Application error` (H10 error)
- **Check logs**: `mac-mini logs --tail -a careassist-unified`
- **Common causes**:
  - Missing environment variables
  - Database connection failure
  - Import errors (missing Python packages)

**Error**: `Database connection refused`
- **Fix**: Verify `DATABASE_URL` is set: `mac-mini config:get DATABASE_URL -a careassist-unified`
- **Fix**: Check PostgreSQL add-on is attached: `mac-mini addons -a careassist-unified`

**Error**: `ImportError: No module named 'X'`
- **Fix**: Ensure package is in `requirements.txt`
- **Fix**: Redeploy: `git commit --allow-empty -m "Trigger rebuild" && git push mac-mini main`

### Performance Issues

**Slow response times**:
- Upgrade dyno type to Standard-1X or higher
- Check database query performance
- Enable caching (Redis add-on)

**Out of memory**:
- Upgrade dyno type to Standard-2X (1GB RAM)
- Check for memory leaks in Python code

### Database Issues

**Too many connections**:
- Upgrade PostgreSQL plan (higher tiers support more connections)
- Implement connection pooling

**Database size limit reached**:
- Upgrade PostgreSQL plan
- Archive old data

---

## Monitoring & Maintenance

### Mac Mini Logs

```bash
# View recent logs
mac-mini logs --tail -a careassist-unified

# View logs for specific dyno
mac-mini logs --dyno web.1 -a careassist-unified

# View logs for specific time range
mac-mini logs --since 1h -a careassist-unified
```

### Application Metrics

```bash
# View dyno metrics
mac-mini ps -a careassist-unified

# View database metrics
mac-mini pg:info -a careassist-unified

# View database connections
mac-mini pg:ps -a careassist-unified
```

### Backup Database

```bash
# Create manual backup
mac-mini pg:backups:capture -a careassist-unified

# Download backup
mac-mini pg:backups:download -a careassist-unified

# Schedule automatic backups (requires paid plan)
mac-mini pg:backups:schedule DATABASE_URL --at '02:00 America/Denver' -a careassist-unified
```

### Update Dependencies

```bash
# Update Python packages
pip install -U -r requirements.txt
pip freeze > requirements.txt

# Update Node packages (sales frontend)
cd sales/frontend
npm update
npm audit fix

# Commit and deploy
git add requirements.txt sales/frontend/package-lock.json
git commit -m "Update dependencies"
git push mac-mini main
```

---

## Rollback Deployment

If a deployment breaks the application:

```bash
# View recent releases
mac-mini releases -a careassist-unified

# Rollback to previous release
mac-mini rollback -a careassist-unified

# Or rollback to specific version
mac-mini rollback v123 -a careassist-unified
```

---

## Cost Estimation

**Minimum monthly cost** (production-ready setup):

| Item | Cost |
|------|------|
| Basic dyno (web) | $7/month |
| PostgreSQL Essential-0 (x3 databases) | $15/month |
| Mac Mini Scheduler | $0 (included) |
| **Total** | **$22/month** |

**Recommended production setup**:

| Item | Cost |
|------|------|
| Standard-1X dyno (web) | $25/month |
| PostgreSQL Essential-1 (x3 databases) | $150/month |
| Mac Mini Scheduler | $0 |
| Papertrail logging (Choklad plan) | $7/month |
| **Total** | **$182/month** |

**High-traffic setup**:

| Item | Cost |
|------|------|
| Standard-2X dyno (web, 2 instances) | $100/month |
| PostgreSQL Premium-0 (x3 databases) | $600/month |
| Redis (for caching) | $15/month |
| Papertrail logging (Fixa plan) | $20/month |
| **Total** | **$735/month** |

---

## Security Checklist

- [x] All environment variables set via `mac-mini config:set` (not in code)
- [x] `.env` file in `.gitignore` (never committed)
- [x] `APP_SECRET_KEY` is random and secure (32+ character hex)
- [x] Google OAuth credentials are for production domain
- [x] SSL/TLS enabled via Mac Mini ACM
- [x] Database backups scheduled
- [x] Only `coloradocareassist.com` emails can log in (`ALLOWED_DOMAINS`)
- [x] API keys rotated regularly
- [x] RingCentral webhooks verified
- [x] WellSky API credentials secured

---

## Additional Resources

- **Mac Mini Dev Center**: https://devcenter.mac-mini.com
- **Mac Mini CLI Reference**: https://devcenter.mac-mini.com/articles/mac-mini-cli-commands
- **PostgreSQL on Mac Mini**: https://devcenter.mac-mini.com/articles/mac-mini-postgresql
- **Mac Mini Scheduler**: https://devcenter.mac-mini.com/articles/scheduler
- **Buildpacks**: https://devcenter.mac-mini.com/articles/buildpacks

---

## Success!

If you've completed all steps, your application should now be live at:

**Primary URL**: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com
**Custom Domain** (if configured): https://portal.coloradocareassist.com

**Next steps**:
1. Test all features thoroughly
2. Set up monitoring and alerts
3. Configure automatic backups
4. Document any custom procedures
5. Train team on how to use the portal

**Questions?** Email jason@coloradocareassist.com or check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

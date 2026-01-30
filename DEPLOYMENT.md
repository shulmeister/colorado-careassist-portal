# Colorado CareAssist Portal - Heroku Deployment Guide

> **Complete step-by-step guide** to deploy the Colorado CareAssist Portal from GitHub to Heroku in production mode.

**Estimated time**: 1-2 hours (first-time setup)

---

## Prerequisites

Before you begin, ensure you have:

- [x] Heroku account (https://signup.heroku.com)
- [x] Heroku CLI installed (https://devcenter.heroku.com/articles/heroku-cli)
- [x] Git installed
- [x] Access to all required API keys (see Environment Variables section)

---

## Step 1: Clone Repository

```bash
git clone https://github.com/shulmeister/colorado-careassist-portal.git
cd colorado-careassist-portal
```

---

## Step 2: Create Heroku App

```bash
# Login to Heroku
heroku login

# Create new app (use a unique name or let Heroku generate one)
heroku create careassist-unified

# Or create with specific name:
# heroku create your-app-name

# Verify app was created
heroku apps:info -a careassist-unified
```

**Note**: If `careassist-unified` is already taken, Heroku will suggest an alternative name. Use that name for all subsequent commands.

---

## Step 3: Add PostgreSQL Databases

This application requires **3 separate PostgreSQL databases**:

```bash
# 1. Main portal database (auto-attached as DATABASE_URL)
heroku addons:create heroku-postgresql:essential-0 -a careassist-unified

# 2. Sales dashboard database
heroku addons:create heroku-postgresql:essential-0 --as SALES_DATABASE -a careassist-unified

# 3. Recruiting dashboard database
heroku addons:create heroku-postgresql:essential-0 --as RECRUITING_DATABASE -a careassist-unified

# Verify databases were created
heroku addons -a careassist-unified
```

**Database Tiers**:
- `essential-0`: $5/month, 10 million rows (recommended for production)
- `essential-1`: $50/month, 10 million rows with extra features
- `mini`: $5/month, 10,000 rows (only for testing)

**Attach database URLs** to environment variables:

```bash
# Check database URLs were created
heroku config -a careassist-unified | grep DATABASE

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
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-apt -a careassist-unified
heroku buildpacks:add heroku/nodejs -a careassist-unified
heroku buildpacks:add heroku/python -a careassist-unified

# Verify buildpacks
heroku buildpacks -a careassist-unified
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
heroku config:set APP_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") -a careassist-unified

# Google OAuth (Portal Login)
# Get from: https://console.cloud.google.com/apis/credentials
heroku config:set GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com -a careassist-unified
heroku config:set GOOGLE_CLIENT_SECRET=your-google-client-secret -a careassist-unified
heroku config:set GOOGLE_REDIRECT_URI=https://careassist-unified-0a11ddb45ac0.herokuapp.com/auth/callback -a careassist-unified

# Allowed login domains
heroku config:set ALLOWED_DOMAINS=coloradocareassist.com -a careassist-unified
```

### Gigi AI Voice Assistant

```bash
# Retell AI (Voice Agent)
heroku config:set RETELL_API_KEY=your-retell-api-key -a careassist-unified
heroku config:set RETELL_AGENT_ID=your-retell-agent-id -a careassist-unified

# Google Gemini AI
heroku config:set GEMINI_API_KEY=your-gemini-api-key -a careassist-unified

# RingCentral (Phone & SMS)
heroku config:set RINGCENTRAL_CLIENT_ID=your-client-id -a careassist-unified
heroku config:set RINGCENTRAL_CLIENT_SECRET=your-client-secret -a careassist-unified
heroku config:set RINGCENTRAL_JWT_TOKEN=your-jwt-token -a careassist-unified
heroku config:set RINGCENTRAL_SERVER_URL=https://platform.ringcentral.com -a careassist-unified

# Gigi operations SMS (set to true when WellSky API is configured)
heroku config:set GIGI_OPERATIONS_SMS_ENABLED=false -a careassist-unified

# Escalation contacts
heroku config:set ESCALATION_CYNTHIA_EXT=105 -a careassist-unified
heroku config:set ESCALATION_JASON_EXT=101 -a careassist-unified
```

### WellSky EVV API (Optional - for operations dashboard)

```bash
# Only set if you have WellSky API access
heroku config:set WELLSKY_API_KEY=your-wellsky-api-key -a careassist-unified
heroku config:set WELLSKY_API_SECRET=your-wellsky-api-secret -a careassist-unified
heroku config:set WELLSKY_AGENCY_ID=your-wellsky-agency-id -a careassist-unified
heroku config:set WELLSKY_BASE_URL=https://api.wellsky.com/v1 -a careassist-unified

# When WellSky is configured, enable Gigi's operations SMS
heroku config:set GIGI_OPERATIONS_SMS_ENABLED=true -a careassist-unified
```

### Sales Dashboard Variables

```bash
# Google Drive (Business Card Auto-Scanner)
# Copy entire JSON service account key as one line
heroku config:set GOOGLE_SERVICE_ACCOUNT_KEY='{"type":"service_account","project_id":"..."}' -a careassist-unified
heroku config:set GOOGLE_DRIVE_BUSINESS_CARDS_FOLDER_ID=your-folder-id -a careassist-unified

# Brevo Email Marketing
heroku config:set BREVO_API_KEY=xkeysib-your-api-key -a careassist-unified

# QuickBooks Online
heroku config:set QUICKBOOKS_CLIENT_ID=your-client-id -a careassist-unified
heroku config:set QUICKBOOKS_CLIENT_SECRET=your-client-secret -a careassist-unified
heroku config:set QUICKBOOKS_REALM_ID=your-company-id -a careassist-unified
heroku config:set QUICKBOOKS_ACCESS_TOKEN=your-access-token -a careassist-unified
heroku config:set QUICKBOOKS_REFRESH_TOKEN=your-refresh-token -a careassist-unified

# Gmail API (Optional - for email tracking)
heroku config:set GMAIL_SERVICE_ACCOUNT_EMAIL=your-service-account@project.iam.gserviceaccount.com -a careassist-unified
heroku config:set GMAIL_SERVICE_ACCOUNT_KEY='{"type":"service_account",...}' -a careassist-unified
heroku config:set GMAIL_USER_EMAILS=jacob@coloradocareassist.com,jen@coloradocareassist.com -a careassist-unified
```

### Recruiting Dashboard Variables

```bash
# Facebook Lead Ads
heroku config:set FACEBOOK_ACCESS_TOKEN=your-long-lived-token -a careassist-unified
heroku config:set FACEBOOK_AD_ACCOUNT_ID=act_your-account-id -a careassist-unified
heroku config:set FACEBOOK_APP_ID=your-app-id -a careassist-unified
heroku config:set FACEBOOK_APP_SECRET=your-app-secret -a careassist-unified
heroku config:set FACEBOOK_PAGE_ID=your-page-id -a careassist-unified
```

### Marketing Dashboard Variables

```bash
# Google Analytics 4
heroku config:set GA4_PROPERTY_ID=your-property-id -a careassist-unified

# Google Business Profile
heroku config:set GBP_LOCATION_IDS=comma,separated,location,ids -a careassist-unified

# Google Ads API
heroku config:set GOOGLE_ADS_DEVELOPER_TOKEN=your-token -a careassist-unified
heroku config:set GOOGLE_ADS_CUSTOMER_ID=1234567890 -a careassist-unified
heroku config:set GOOGLE_ADS_REFRESH_TOKEN=your-refresh-token -a careassist-unified
heroku config:set GOOGLE_ADS_OAUTH_CLIENT_ID=your-oauth-client-id -a careassist-unified
heroku config:set GOOGLE_ADS_OAUTH_CLIENT_SECRET=your-oauth-client-secret -a careassist-unified

# Google Service Account (for GA4, GBP)
heroku config:set GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}' -a careassist-unified

# Social Media APIs (Optional)
heroku config:set LINKEDIN_ACCESS_TOKEN=your-token -a careassist-unified
heroku config:set PINTEREST_ACCESS_TOKEN=your-token -a careassist-unified
heroku config:set TIKTOK_ACCESS_TOKEN=your-token -a careassist-unified
heroku config:set TIKTOK_ADVERTISER_ID=your-id -a careassist-unified
```

**Verify all variables are set**:

```bash
heroku config -a careassist-unified
```

---

## Step 6: Deploy Application

```bash
# Add Heroku remote (if not already added)
git remote add heroku https://git.heroku.com/careassist-unified.git

# Deploy to Heroku
git push heroku main
```

**Watch deployment logs**:

```bash
heroku logs --tail -a careassist-unified
```

**Expected output**:
```
remote: -----> Building on the Heroku-22 stack
remote: -----> Using buildpack: https://github.com/heroku/heroku-buildpack-apt
remote: -----> Using buildpack: heroku/nodejs
remote: -----> Using buildpack: heroku/python
remote: -----> Launching...
remote: -----> Build succeeded!
remote:        https://careassist-unified-0a11ddb45ac0.herokuapp.com/ deployed to Heroku
```

**If build fails**, check:
1. All buildpacks are in correct order (apt → nodejs → python)
2. `requirements.txt` exists in root directory
3. `Procfile` exists with correct content: `web: uvicorn unified_app:app --host 0.0.0.0 --port $PORT`

---

## Step 7: Run Database Migrations

```bash
# Run Alembic migrations
heroku run alembic upgrade head -a careassist-unified

# Initialize portal data (if needed)
heroku run python portal/portal_setup.py -a careassist-unified
```

**If migrations fail**, check:
1. DATABASE_URL is set correctly
2. PostgreSQL add-on is attached
3. Alembic configuration in `alembic.ini` points to `DATABASE_URL`

---

## Step 8: Set Up Heroku Scheduler Jobs

Some features require scheduled jobs to run automatically:

```bash
# Add Heroku Scheduler add-on (free)
heroku addons:create scheduler:standard -a careassist-unified

# Open scheduler dashboard
heroku addons:open scheduler -a careassist-unified
```

**Add these scheduled jobs** in the Heroku Scheduler dashboard:

| Job Command | Frequency | Purpose |
|-------------|-----------|---------|
| `cd sales && python scripts/auto_scan_drive.py` | Every 10 minutes | Business card auto-scanner |
| `cd recruiting && python sync_facebook_leads.py` | Daily at 9:00 AM | Facebook Lead Ads sync |
| `cd sales && python scripts/sync_quickbooks.py` | Daily at 12:00 PM | QuickBooks customer sync |

**Note**: Heroku Scheduler only supports 10-minute, hourly, or daily frequencies. For more precise scheduling (e.g., every 5 minutes), use a custom clock dyno or external cron service.

---

## Step 9: Scale Dynos

```bash
# Scale web dyno to 1 instance
heroku ps:scale web=1 -a careassist-unified

# Check dyno status
heroku ps -a careassist-unified
```

**Dyno tiers**:
- **Free**: Not available anymore (deprecated by Heroku)
- **Eco**: $5/month for all apps (sleeps after 30 min inactivity)
- **Basic**: $7/month per dyno (never sleeps)
- **Standard-1X**: $25/month per dyno (recommended for production)

**For production, use Basic or higher**:

```bash
heroku dyno:type basic -a careassist-unified
```

---

## Step 10: Configure Custom Domain (Optional)

If you have a custom domain (e.g., `portal.coloradocareassist.com`):

```bash
# Add custom domain
heroku domains:add portal.coloradocareassist.com -a careassist-unified

# Get DNS target
heroku domains -a careassist-unified
```

**DNS Configuration** (in your domain registrar):

| Type | Name | Value |
|------|------|-------|
| CNAME | portal | your-app-name-xxxxx.herokudns.com |

**Wait 24-48 hours** for DNS propagation.

**Enable Automated Certificate Management (ACM)** for HTTPS:

```bash
# ACM is automatically enabled for custom domains
# Verify SSL certificate
heroku certs -a careassist-unified
```

---

## Step 11: Enable GitHub Auto-Deploy (Optional)

Set up automatic deployments when you push to GitHub:

1. **Go to Heroku Dashboard**: https://dashboard.heroku.com
2. **Select your app**: `careassist-unified`
3. **Go to Deploy tab**
4. **Connect to GitHub**: Connect your `colorado-careassist-portal` repository
5. **Enable Automatic Deploys**: Choose `main` branch
6. **Enable CI wait** (optional): Wait for CI tests to pass before deploying

**Now every push to `main` will automatically deploy to Heroku!**

---

## Step 12: Test Deployment

### Check Application Status

```bash
# Open app in browser
heroku open -a careassist-unified

# Check logs for errors
heroku logs --tail -a careassist-unified

# Check dyno status
heroku ps -a careassist-unified
```

### Test Individual Endpoints

**Portal Hub**: https://careassist-unified-0a11ddb45ac0.herokuapp.com/
- Should show login page or portal dashboard

**Gigi AI**: https://careassist-unified-0a11ddb45ac0.herokuapp.com/gigi/
- Should show Gigi documentation page

**Sales Dashboard**: https://careassist-unified-0a11ddb45ac0.herokuapp.com/sales/
- Should redirect to login or show sales CRM

**Recruiting**: https://careassist-unified-0a11ddb45ac0.herokuapp.com/recruiting/
- Should show recruiting dashboard

**Marketing**: https://careassist-unified-0a11ddb45ac0.herokuapp.com/marketing/
- Should show marketing analytics

**Operations**: https://careassist-unified-0a11ddb45ac0.herokuapp.com/operations/
- Should show operations dashboard

### Test Business Card Scanner

1. Upload a business card image to Google Drive folder
2. Wait 10 minutes (or run scheduler job manually)
3. Check sales dashboard for new contact

### Test Gigi Voice Assistant

1. Call 719-428-3999 (or your configured number)
2. Speak with Gigi
3. Check Heroku logs for call transcript

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
- **Check logs**: `heroku logs --tail -a careassist-unified`
- **Common causes**:
  - Missing environment variables
  - Database connection failure
  - Import errors (missing Python packages)

**Error**: `Database connection refused`
- **Fix**: Verify `DATABASE_URL` is set: `heroku config:get DATABASE_URL -a careassist-unified`
- **Fix**: Check PostgreSQL add-on is attached: `heroku addons -a careassist-unified`

**Error**: `ImportError: No module named 'X'`
- **Fix**: Ensure package is in `requirements.txt`
- **Fix**: Redeploy: `git commit --allow-empty -m "Trigger rebuild" && git push heroku main`

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

### Heroku Logs

```bash
# View recent logs
heroku logs --tail -a careassist-unified

# View logs for specific dyno
heroku logs --dyno web.1 -a careassist-unified

# View logs for specific time range
heroku logs --since 1h -a careassist-unified
```

### Application Metrics

```bash
# View dyno metrics
heroku ps -a careassist-unified

# View database metrics
heroku pg:info -a careassist-unified

# View database connections
heroku pg:ps -a careassist-unified
```

### Backup Database

```bash
# Create manual backup
heroku pg:backups:capture -a careassist-unified

# Download backup
heroku pg:backups:download -a careassist-unified

# Schedule automatic backups (requires paid plan)
heroku pg:backups:schedule DATABASE_URL --at '02:00 America/Denver' -a careassist-unified
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
git push heroku main
```

---

## Rollback Deployment

If a deployment breaks the application:

```bash
# View recent releases
heroku releases -a careassist-unified

# Rollback to previous release
heroku rollback -a careassist-unified

# Or rollback to specific version
heroku rollback v123 -a careassist-unified
```

---

## Cost Estimation

**Minimum monthly cost** (production-ready setup):

| Item | Cost |
|------|------|
| Basic dyno (web) | $7/month |
| PostgreSQL Essential-0 (x3 databases) | $15/month |
| Heroku Scheduler | $0 (included) |
| **Total** | **$22/month** |

**Recommended production setup**:

| Item | Cost |
|------|------|
| Standard-1X dyno (web) | $25/month |
| PostgreSQL Essential-1 (x3 databases) | $150/month |
| Heroku Scheduler | $0 |
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

- [x] All environment variables set via `heroku config:set` (not in code)
- [x] `.env` file in `.gitignore` (never committed)
- [x] `APP_SECRET_KEY` is random and secure (32+ character hex)
- [x] Google OAuth credentials are for production domain
- [x] SSL/TLS enabled via Heroku ACM
- [x] Database backups scheduled
- [x] Only `coloradocareassist.com` emails can log in (`ALLOWED_DOMAINS`)
- [x] API keys rotated regularly
- [x] RingCentral webhooks verified
- [x] WellSky API credentials secured

---

## Additional Resources

- **Heroku Dev Center**: https://devcenter.heroku.com
- **Heroku CLI Reference**: https://devcenter.heroku.com/articles/heroku-cli-commands
- **PostgreSQL on Heroku**: https://devcenter.heroku.com/articles/heroku-postgresql
- **Heroku Scheduler**: https://devcenter.heroku.com/articles/scheduler
- **Buildpacks**: https://devcenter.heroku.com/articles/buildpacks

---

## Success!

If you've completed all steps, your application should now be live at:

**Primary URL**: https://careassist-unified-0a11ddb45ac0.herokuapp.com
**Custom Domain** (if configured): https://portal.coloradocareassist.com

**Next steps**:
1. Test all features thoroughly
2. Set up monitoring and alerts
3. Configure automatic backups
4. Document any custom procedures
5. Train team on how to use the portal

**Questions?** Email jason@coloradocareassist.com or check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

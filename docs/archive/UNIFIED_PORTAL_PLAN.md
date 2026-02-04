# Colorado CareAssist - Unified Portal Development Plan

**Status**: Staging environment deploying
**Date**: January 9, 2026

---

## Current Architecture (PRODUCTION - Don't Touch!)

| App | URL | Purpose | Status |
|-----|-----|---------|--------|
| `coloradocareassist` | https://coloradocareassist.com/ | Main public website | ✅ LIVE |
| `hesedhomecare` | https://hesedhomecare.com/ | Hesed website | ✅ LIVE |
| `portal-coloradocareassist` | https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com/ | Portal hub (dashboard selector) | ✅ LIVE |
| `careassist-tracker` | https://careassist-tracker-1a6df2c7822c.mac-miniapp.com/ | Sales CRM (614 contacts, 40 deals) | ✅ LIVE |
| `caregiver-lead-tracker` | https://caregiver-lead-tracker-1e2f551680c9.mac-miniapp.com/ | Recruiter dashboard (454 leads) | ✅ LIVE |
| `wellsky-converter-shulmeister` | http://payroll.coloradocareassist.com/ | Wellsky payroll converter | ✅ LIVE |

**Total**: 6 Mac Mini (Local) apps
**Cost**: ~$42/month (6 apps × $7)

---

## Target Architecture (AFTER Consolidation)

| App | URL | Purpose |
|-----|-----|---------|
| `coloradocareassist` | https://coloradocareassist.com/ | Main public website |
| `hesedhomecare` | https://hesedhomecare.com/ | Hesed website |
| `careassist-unified` | https://portal.coloradocareassist.com/ | **Unified portal** (hub + sales + recruiting) |

**Total**: 3 Mac Mini (Local) apps
**Cost**: ~$21/month (3 apps × $7)
**Savings**: $21/month = **$252/year**

---

## What About the Wellsky Converter?

The Wellsky converter at `payroll.coloradocareassist.com` is hosted on Mac Mini (Local) (`wellsky-converter-shulmeister`) but it's just a tile/link on the portal - not part of the core portal functionality.

**Decision**: Keep it as a separate app for now. It's lightweight and self-contained.

**Future Option**: Could potentially consolidate it too, but it's not a priority.

---

## Staging Environment

**URL**: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/

**Status**: Currently deploying with full sales + recruiting integration

**What's Being Built**:
```
/                    → Dashboard selector homepage
/sales/*             → Full sales CRM (FastAPI + React)
/recruiting/*        → Full recruiter dashboard (Flask)
/health              → Health check endpoint
```

**Databases**:
- Sales: `postgresql-encircled-20486` (attached as SALES_DATABASE_URL)
- Recruiting: `postgresql-contoured-16226` (attached as RECRUITING_DATABASE_URL)

---

## How the Unified App Works

### Architecture

```
unified_app.py (FastAPI main app)
├── Portal Homepage (/)
│   └── Dashboard selector with tiles
├── Sales Dashboard (/sales/*)
│   ├── Imports from sales/app.py
│   ├── Uses SALES_DATABASE_URL
│   └── Full FastAPI app mounted
└── Recruiting Dashboard (/recruiting/*)
    ├── Imports from recruiting/app.py
    ├── Uses RECRUITING_DATABASE_URL
    └── Flask app mounted via WSGI middleware
```

### Database Strategy

Each sub-app looks for `DATABASE_URL` environment variable. The unified app:
1. Sets `DATABASE_URL` = `SALES_DATABASE_URL` before loading sales app
2. Sets `DATABASE_URL` = `RECRUITING_DATABASE_URL` before loading recruiting app

This way, both apps work without modification.

### Module Loading

Uses `importlib.util` to properly load each app as a separate module:
- Avoids naming conflicts
- Preserves each app's internal structure
- Allows proper error handling

---

## Testing Plan

### Phase 1: Staging Tests
1. ✅ Portal homepage loads (200 OK)
2. ✅ Sales dashboard mounts successfully (307 redirect to OAuth)
3. ✅ Recruiting dashboard mounts and displays (200 OK)
4. ⏳ Data loads from correct databases (needs OAuth setup)
5. ⏳ Authentication works (needs OAuth redirect URI update)
6. ⏳ All features functional

### Phase 2: Load Testing
1. Test with real user accounts
2. Verify OAuth redirects work
3. Check performance (should be similar to separate apps)
4. Monitor memory usage

### Phase 3: Production Cutover (When Ready)
1. Update DNS: `portal.coloradocareassist.com` → `careassist-unified`
2. Update OAuth redirect URIs in Google Console
3. Monitor for issues
4. Keep old apps running for 24 hours as backup
5. Delete old apps after verification

---

## Rollback Plan

If anything goes wrong:
1. DNS is instant - point back to old portal
2. Old apps remain running the entire time
3. Zero data loss (databases stay separate)
4. Can retry consolidation later

---

## Technical Challenges

### Challenge 1: Different Frameworks
- Sales: FastAPI
- Recruiting: Flask
- **Solution**: Use WSGIMiddleware to mount Flask app

### Challenge 2: Database Connections
- Both apps expect `DATABASE_URL`
- **Solution**: Set env var before importing each app

### Challenge 3: Static Files
- Sales has React frontend build
- Recruiting has simple templates
- **Solution**: Mount each app's static files at their sub-paths

### Challenge 4: Authentication
- Both apps have their own OAuth
- **Solution**: Keep separate for now, unify later if needed

---

## What We've Accomplished So Far

✅ Created staging unified portal app
✅ Attached both production databases
✅ Configured all environment variables
✅ Copied sales dashboard code (109k+ lines)
✅ Copied recruiting dashboard code
✅ Updated mounting logic with proper module loading
✅ Added database URL routing
✅ Currently deploying...

---

## Next Steps

### Immediate (Today)
1. ⏳ Wait for deployment to finish
2. ⏳ Test staging portal
3. ⏳ Debug any mounting issues
4. ⏳ Verify data displays correctly

### Short Term (This Week)
1. Full feature testing on staging
2. Performance testing
3. Get your approval
4. Update OAuth settings if needed

### Medium Term (When Ready)
1. DNS cutover
2. Monitor production
3. Delete old apps
4. Celebrate $252/year savings

---

## Cost Analysis

| Scenario | Monthly | Annual | Notes |
|----------|---------|--------|-------|
| **Current (6 apps)** | $42 | $504 | 6 apps × $7/month |
| **Target (3 apps)** | $21 | $252 | 3 apps × $7/month |
| **Savings** | $21 | $252 | 50% reduction |

Plus:
- Simpler architecture
- Single codebase to maintain
- Unified authentication (future)
- Easier to add new dashboards

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Deployment failure | Low | Low | Keep old apps running |
| Performance issues | Low | Medium | Test on staging first |
| OAuth breaks | Medium | High | Update redirect URIs |
| Database issues | Very Low | High | Read-only databases, easy rollback |
| Module conflicts | Medium | Medium | Using importlib isolation |

**Overall Risk**: LOW (because we keep production untouched)

---

## Decision Points

### Should We Do This?

**Pros**:
- Saves $252/year
- Simpler architecture
- Single deployment
- Easier maintenance

**Cons**:
- Requires testing time
- DNS changes
- OAuth updates
- Some risk (mitigated)

**Recommendation**: YES - the staging approach minimizes risk and the savings are worthwhile.

---

## Current Status

**Deployment**: ✅ COMPLETE
**Portal Homepage**: ✅ Working (https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/)
**Sales Dashboard**: ✅ Mounted at /sales (redirecting to OAuth login)
**Recruiting Dashboard**: ✅ Mounted at /recruiting (loading successfully)

### Verified Working:
- Portal homepage displays with dashboard selector
- Both dashboards successfully mounted via module loading
- Database connections configured (SALES_DATABASE_URL, RECRUITING_DATABASE_URL)
- Health endpoint confirms services: `{"status":"healthy","version":"3.0.0"}`

### Next Steps:
1. **OAuth Setup**: Update Google OAuth redirect URIs to include staging URLs:
   - Add: `https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/sales/auth/callback`
   - Add: `https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/recruiting/auth/callback`
2. **Full Testing**: Test all features (contacts, deals, leads, analytics)
3. **User Acceptance**: Get your approval before production cutover

**Staging URL**: https://careassist-unified-0a11ddb45ac0.mac-miniapp.com/

---

**Questions?** This is a side project - production stays untouched until we're 100% confident.

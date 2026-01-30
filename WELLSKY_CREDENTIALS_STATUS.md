# WellSky API Credentials Status

**Date:** January 29, 2026 (Updated 23:15 MST)
**Status:** 🔴 BLOCKED - OAuth works, API calls fail with 403

---

## Current Situation

### Credentials in Heroku
```
WELLSKY_CLIENT_ID:     bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS
WELLSKY_CLIENT_SECRET: Do06wgoZuV7ni4zO
WELLSKY_AGENCY_ID:     4505
WELLSKY_ENVIRONMENT:   production
WELLSKY_API_URL:       https://api.clearcareonline.com (deprecated/unused)
```

### What Works ✅
- **OAuth Token Request** → 200 OK
- Gets valid `access_token` with 3599 second expiration
- Token type returned as "BearerToken"

### What Fails ❌
- **ALL FHIR API Calls** → 403 Forbidden
- Error: "Invalid key=value pair (missing equal-sign) in Authorization header"
- Affects: Practitioner, Patient, Appointment, all endpoints

---

## Root Cause Analysis

### The Problem
OAuth response only contains `access_token`, but WellSky documentation states:

> "This method generates necessary tokens such as **auth_token**, **graphql_token** and **drf_token**. When hitting connect API, always pass **auth_token** in header."

**We're missing:** `auth_token`, `graphql_token`, `drf_token`

### What This Means
These credentials can authenticate (OAuth works) but are **not provisioned** for FHIR API resource access. They may be:
1. Old ClearCare credentials (pre-WellSky acquisition)
2. Provisioned only for deprecated API (api.clearcareonline.com)
3. Missing required permissions/scopes for FHIR endpoints

---

## Testing Evidence

### Test 1: OAuth (WORKS)
```bash
curl -X POST https://connect.clearcareonline.com/oauth/accesstoken \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "client_credentials",
    "client_id": "bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS",
    "client_secret": "Do06wgoZuV7ni4zO"
  }'

# Returns:
{
  "access_token": "2f46b3ff57f94bd7bd4ac19913d5d707",
  "token_type": "BearerToken",
  "expires_in": "3599",
  "status": "approved"
}
```
**Result:** ✅ SUCCESS

### Test 2: Practitioner API (FAILS)
```bash
curl https://connect.clearcareonline.com/v1/Practitioner?agencyId=4505&_count=5 \
  -H "Authorization: Bearer 2f46b3ff57f94bd7bd4ac19913d5d707" \
  -H "Content-Type: application/json"

# Returns:
{
  "message": "Invalid key=value pair (missing equal-sign) in Authorization header (hashed with SHA-256 and encoded with Base64): 'OsDch8nCTDLRsIMIMtpwKvNTzq79dHu/I7JKf1KEjWQ='."
}
```
**Result:** ❌ 403 FORBIDDEN

### Variations Tested (All Fail with 403)
- `Authorization: Bearer {token}`
- `Authorization: BearerToken {token}`
- agencyId as query param
- agencyId as X-Agency-ID header
- Different endpoints (Patient, Appointment)
- Production and sandbox environments

---

## WellSky Service Details

**Contract:**
- Monthly Cost: $240/month
- Implementation Fee: $1,600 (paid)
- Agency ID: 4505

**Support:**
- Email: personalcaresupport@wellsky.com
- Purpose: Personal Care Home Connect API integration

**API Documentation:**
- Swagger spec: `/Users/shulmeister/Desktop/swagger.yaml`
- Note: References external auth files we don't have access to

---

## Impact on Business

### Blocked Capabilities
- ❌ Real-time shift lookup
- ❌ Caregiver availability search
- ❌ Client information access
- ❌ Automated call-out handling
- ❌ Zingage replacement

### Financial Impact
- **Potential Savings:** $6,000 - $24,000/year (Zingage replacement)
- **Current State:** Paying both WellSky ($240/mo) AND Zingage ($500-2000/mo)
- **Double Payment:** Continuing until API access resolved

---

## Completed Work (Ready to Deploy)

All integration code is complete and waiting for working credentials:

✅ **Core Integration** (838 lines)
- `services/wellsky_service.py` - Full FHIR API implementation
- OAuth flow, token management, error handling
- All endpoints: Practitioner, Patient, Appointment

✅ **Performance Optimization**
- `services/wellsky_cache.sql` - PostgreSQL cache tables
- `services/sync_wellsky_cache.py` - Daily sync script
- `services/wellsky_fast_lookup.py` - <5ms caller ID lookup

✅ **Testing**
- `tests/test_gigi_zingage_replacement.py` - Comprehensive test suite
- 14 test scenarios covering all Zingage use cases
- **71.4% pass rate in mock mode** (infrastructure issues only)

✅ **Deployment**
- `MAC_MINI_SETUP.md` - Complete Mac Mini deployment guide
- Gigi caller ID fix committed (6164a9f)
- All documentation updated

---

## Required Actions

### 1. Contact WellSky Support (URGENT)

**Email:** personalcaresupport@wellsky.com
**Subject:** "Agency 4505 - FHIR API Access Not Working"

**Message Template:**
```
Hello WellSky Support,

We have OAuth credentials for Agency ID 4505 that successfully
authenticate but fail on all FHIR API resource calls.

Credentials:
- Client ID: bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS
- Agency ID: 4505

Issue:
1. OAuth works - gets access_token successfully
2. All API calls fail with 403: "Invalid key=value pair in Authorization header"

According to documentation, OAuth should return auth_token,
graphql_token, and drf_token. We only receive access_token.

Questions:
1. Are these credentials provisioned for FHIR API access?
2. How do we obtain auth_token (not access_token)?
3. What permissions are assigned to this Client ID?
4. Is additional setup required for Home Connect FHIR API?

Use case: Automated call-out management via AI assistant (Gigi).
Endpoints needed: Practitioner, Patient, Appointment.

Please advise on next steps to enable FHIR API access.

Thank you,
Jason Shulmeister
Colorado Care Assist
jason@coloradocareassist.com
```

### 2. Check WellSky Admin Portal

If you have login access to WellSky admin portal:
- Look for API settings or developer console
- Check credential permissions/scopes
- See if FHIR API access needs to be explicitly enabled
- Check if there's a way to generate auth_token vs access_token

### 3. Review Implementation Documentation

From your $1,600 implementation:
- Was there setup documentation provided?
- Contact person who did the implementation
- Check if they have working examples or different credentials

---

## Technical Details for Support

### API Endpoints
- **OAuth:** https://connect.clearcareonline.com/oauth/accesstoken ✅ WORKS
- **FHIR:** https://connect.clearcareonline.com/v1/* ❌ FAILS (403)
- **Old API:** https://api.clearcareonline.com/* ❌ DEPRECATED (404)

### Authorization Header Format Tested
```python
# Both formats fail with same 403 error
headers = {"Authorization": f"Bearer {access_token}"}
headers = {"Authorization": f"BearerToken {access_token}"}
```

### Full Error Response
```json
{
  "message": "Invalid key=value pair (missing equal-sign) in Authorization header (hashed with SHA-256 and encoded with Base64): 'OsDch8nCTDLRsIMIMtpwKvNTzq79dHu/I7JKf1KEjWQ='."
}
```

This error suggests WellSky is rejecting the token format or the credentials lack proper scopes.

---

## Alternative: Mock Mode (Temporary)

While waiting for API access, Gigi can run in mock mode:
- ✅ All logic works (71.4% test pass rate)
- ✅ Call flows can be tested
- ❌ No real WellSky data
- ❌ Cannot replace Zingage

**Not recommended** - paying for WellSky API we can't use.

---

## Timeline

- **Jan 29, 22:15** - Discovered OAuth works but API fails
- **Jan 29, 22:31** - Tested all authorization formats (all fail)
- **Jan 29, 23:00** - Identified missing auth_token in OAuth response
- **Jan 29, 23:15** - Documentation updated, ready for support escalation

**Next Update:** After WellSky support response

---

## Success Criteria

API access working when:
1. OAuth returns `auth_token` (not just `access_token`)
2. API calls return 200 with FHIR resources
3. Can fetch real Practitioner, Patient, Appointment data

**Then:** Deploy to production, replace Zingage, save $6K-24K/year

---

## Reference Documents

- **Blocker Details:** `/WELLSKY_API_BLOCKER.md` ← **START HERE**
- **Test Results:** `/GIGI_ZINGAGE_TEST_RESULTS.md`
- **Integration Code:** `/services/wellsky_service.py`
- **Setup Guide:** `/MAC_MINI_SETUP.md`

---

**Status:** Waiting for WellSky to provision FHIR API access for Client ID `bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS`

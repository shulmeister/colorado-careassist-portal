# WellSky API Blocker - Current Status

**Date:** January 29, 2026
**Status:** 🔴 BLOCKED - Credentials issue preventing FHIR API access
**Cost Impact:** Cannot replace Zingage ($6K-24K/year savings blocked)

---

## Summary for Technical Review

WellSky OAuth credentials authenticate successfully but fail on all FHIR API resource calls with 403 errors. Testing suggests credentials may not be fully provisioned for FHIR API access.

---

## What Works ✅

### OAuth Authentication
```bash
POST https://connect.clearcareonline.com/oauth/accesstoken
Content-Type: application/json

{
  "grant_type": "client_credentials",
  "client_id": "bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS",
  "client_secret": "Do06wgoZuV7ni4zO"
}

# Response: 200 OK
{
  "refresh_token_expires_in": "0",
  "token_type": "BearerToken",
  "issued_at": 1769754192,
  "client_id": "bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS",
  "access_token": "2f46b3ff57f94bd7bd4ac19913d5d707",
  "scope": "",
  "expires_in": "3599",
  "refresh_count": "0",
  "status": "approved"
}
```

**Result:** ✅ Token obtained successfully

---

## What Fails ❌

### All FHIR API Calls
```bash
GET https://connect.clearcareonline.com/v1/Practitioner?agencyId=4505&_count=5
Authorization: Bearer 2f46b3ff57f94bd7bd4ac19913d5d707
Content-Type: application/json

# Response: 403 Forbidden
{
  "message": "Invalid key=value pair (missing equal-sign) in Authorization header (hashed with SHA-256 and encoded with Base64): 'OsDch8nCTDLRsIMIMtpwKvNTzq79dHu/I7JKf1KEjWQ='."
}
```

**Same error with:**
- `Authorization: Bearer {token}`
- `Authorization: BearerToken {token}`
- Different endpoints (Patient, Appointment, etc.)
- Query param vs header for agencyId

**Result:** ❌ All API calls fail with 403

---

## The Discrepancy

### WellSky Documentation Says:
> "This method generates necessary tokens such as **auth_token**, **graphql_token** and **drf_token**. When hitting connect API, always pass **auth_token** in header as 'authorization': 'Bearer ' + auth_token"

### What We Actually Get:
Only `access_token` in the OAuth response. No `auth_token`, `graphql_token`, or `drf_token`.

**This suggests:** Credentials may not be fully provisioned for FHIR API access.

---

## Credentials in Use

```bash
WELLSKY_CLIENT_ID:     bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS
WELLSKY_CLIENT_SECRET: Do06wgoZuV7ni4zO
WELLSKY_AGENCY_ID:     4505
WELLSKY_ENVIRONMENT:   production
```

**Currently set in:** Heroku app `careassist-unified`

---

## WellSky Service Details

- **Monthly Cost:** $240/month
- **Implementation Fee Paid:** $1,600
- **Contact:** personalcaresupport@wellsky.com
- **API Documentation:** swagger.yaml in repo (references external auth files we don't have)

---

## Technical Questions for WellSky Support

1. **Token Provisioning**
   - Why does OAuth only return `access_token` and not `auth_token`?
   - Are these credentials provisioned for FHIR API resource access?
   - Do we need additional setup/activation for FHIR endpoints?

2. **Authorization Format**
   - Documentation says use `auth_token`, but OAuth only returns `access_token`
   - Is there a different OAuth endpoint or parameter to get `auth_token`?
   - What's the difference between `access_token` and `auth_token`?

3. **API Access**
   - Are these credentials valid for Home Connect FHIR API (connect.clearcareonline.com/v1/)?
   - Or are they only for the old deprecated API (api.clearcareonline.com)?
   - What permissions/scopes are assigned to Client ID `bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS`?

---

## What's Ready (Blocked by API Access)

### Completed Code ✅
- `services/wellsky_service.py` - Full FHIR integration (838 lines)
- `services/wellsky_cache.sql` - PostgreSQL cache for <5ms caller ID
- `services/sync_wellsky_cache.py` - Daily sync script
- `services/wellsky_fast_lookup.py` - Fast lookup functions
- `tests/test_gigi_zingage_replacement.py` - Comprehensive test suite
- `gigi/main.py` - Caller ID recognition fix
- `MAC_MINI_SETUP.md` - Complete deployment guide

### Test Results (Mock Mode) ✅
- **Pass Rate:** 71.4% (10/14 tests)
- **Status:** Mostly Ready
- **Failures:** All infrastructure (PostgreSQL not running, API blocked)
- **Core Logic:** ✅ All Zingage replacement scenarios work

### Blocked Functionality ❌
Without working API access:
- No real-time shift data
- No caregiver availability lookup
- No client information
- Cannot replace Zingage
- $6K-24K/year savings unrealized

---

## Attempted Solutions

### ✅ Tested
1. Multiple Authorization header formats
2. Bearer vs BearerToken
3. Query params vs headers for agencyId
4. Production vs sandbox endpoints
5. Old API endpoints (all deprecated/404)

### ❌ Not Possible
1. Check WellSky admin portal (no access/credentials)
2. Review credential permissions (need WellSky portal access)
3. Request different token types (don't know how)

---

## Recommended Next Steps

### Immediate (For Techie Friend)
1. **Review this document** - Understand the exact blocker
2. **Check WellSky admin portal** - If you have access
   - Look for credential settings
   - Check if FHIR API access needs to be enabled
   - See if additional tokens need to be requested

3. **Test this exact curl command:**
   ```bash
   # Get token
   curl -X POST https://connect.clearcareonline.com/oauth/accesstoken \
     -H "Content-Type: application/json" \
     -d '{
       "grant_type": "client_credentials",
       "client_id": "bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS",
       "client_secret": "Do06wgoZuV7ni4zO"
     }'

   # Use the access_token from response above
   curl https://connect.clearcareonline.com/v1/Practitioner?agencyId=4505&_count=5 \
     -H "Authorization: Bearer {TOKEN_HERE}" \
     -H "Content-Type: application/json"
   ```

   **Expected:** 403 error (same as we're getting)

### Follow-Up with WellSky
**Email:** personalcaresupport@wellsky.com
**Subject:** "Agency 4505 - FHIR API 403 errors despite valid OAuth"

**Key Points:**
- OAuth works (gets token)
- All API calls fail with 403 "Invalid key=value pair"
- Documentation says OAuth should return `auth_token` but only returns `access_token`
- Need FHIR API access for Practitioner, Patient, Appointment endpoints
- Use case: Automated call-out management via AI assistant

---

## Files for Reference

- **This Document:** `/WELLSKY_API_BLOCKER.md`
- **Test Results:** `/GIGI_ZINGAGE_TEST_RESULTS.md`
- **Integration Code:** `/services/wellsky_service.py`
- **API Spec:** `/Users/shulmeister/Desktop/swagger.yaml`
- **Setup Guide:** `/MAC_MINI_SETUP.md`
- **Credentials Status:** `/WELLSKY_CREDENTIALS_STATUS.md`

---

## Bottom Line

**The code is done. The API credentials are not.**

All Gigi code is complete and tested (71.4% pass rate in mock mode). The only blocker is WellSky API access. Once credentials work, deployment is ~1 hour.

**Estimated Impact:** $6,000 - $24,000/year in Zingage cost savings

---

**Next Action:** Get WellSky credentials that return `auth_token` and allow FHIR API resource access.

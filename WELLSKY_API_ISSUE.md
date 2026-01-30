# WellSky API Issue - Objective Facts Only

**Date:** January 29, 2026
**Status:** API calls failing with 403 errors

---

## What Works

```bash
POST https://connect.clearcareonline.com/oauth/accesstoken
Content-Type: application/json

{
  "grant_type": "client_credentials",
  "client_id": "bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS",
  "client_secret": "Do06wgoZuV7ni4zO"
}
```

**Response: 200 OK**
```json
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

---

## What Fails

### Attempt 1: Authorization: Bearer {token}
```bash
GET https://connect.clearcareonline.com/v1/Practitioner?agencyId=4505&_count=5
Authorization: Bearer 2f46b3ff57f94bd7bd4ac19913d5d707
Content-Type: application/json
```

**Response: 403 Forbidden**
```json
{
  "message": "Invalid key=value pair (missing equal-sign) in Authorization header (hashed with SHA-256 and encoded with Base64): 'OsDch8nCTDLRsIMIMtpwKvNTzq79dHu/I7JKf1KEjWQ='."
}
```

### Attempt 2: Authorization: BearerToken {token}
```bash
GET https://connect.clearcareonline.com/v1/Practitioner?agencyId=4505&_count=5
Authorization: BearerToken 2f46b3ff57f94bd7bd4ac19913d5d707
Content-Type: application/json
```

**Response: 403 Forbidden**
```json
{
  "message": "Invalid key=value pair (missing equal-sign) in Authorization header (hashed with SHA-256 and encoded with Base64): 'EfhmpPnDGC9KUvMkf5shJbIrtoLIVbZXNVmbn5+8NMc='."
}
```

---

## Other Variations Tested (All Return Same 403)

- With `X-Agency-ID: 4505` header instead of query param
- Different endpoints (Patient, Appointment)
- Sandbox URL: `https://connect-sandbox.clearcareonline.com`
- Production URL: `https://connect.clearcareonline.com`

All return identical 403 error.

---

## Documentation Found

From documentation you provided:

> "This method generates necessary tokens such as auth_token, graphql_token and drf_token. When hitting connect API, always pass auth_token in header as 'authorization': 'Bearer ' + auth_token"

**Observation:** OAuth response contains `access_token` but not `auth_token`, `graphql_token`, or `drf_token`.

**Unknown:** Why response doesn't include those tokens, or if that's relevant to the 403 error.

---

## Credentials Being Used

```
Client ID:     bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS
Client Secret: Do06wgoZuV7ni4zO
Agency ID:     4505
```

**Source:** Currently in Heroku config for `careassist-unified`

---

## Code Location

Authorization header built in `services/wellsky_service.py` lines 601-604:

```python
headers = {
    "Authorization": f"BearerToken {token}",
    "Content-Type": "application/json",
}
```

---

## Test Results

- Mock mode: 71.4% pass rate (10/14 tests)
- All failures are due to API access or PostgreSQL not running
- No code logic issues found

---

## Files

- Test suite: `tests/test_gigi_zingage_replacement.py`
- Integration code: `services/wellsky_service.py`
- API spec: `/Users/shulmeister/Desktop/swagger.yaml`
- Test scripts: `test_raw_auth.py`, `test_api_direct.py`

---

## That's It

Those are the facts. No theories, no assumptions, no recommendations.

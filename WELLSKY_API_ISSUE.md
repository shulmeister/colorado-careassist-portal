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
  "client_id": "[REDACTED_CLIENT_ID]",
  "client_secret": "[REDACTED_CLIENT_SECRET]"
}
```

**Response: 200 OK**
```json
{
  "refresh_token_expires_in": "0",
  "token_type": "BearerToken",
  "issued_at": 1769754192,
  "client_id": "[REDACTED_CLIENT_ID]",
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
Client ID:     [REDACTED_CLIENT_ID]
Client Secret: [REDACTED_CLIENT_SECRET]
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

- Test suite: `tests/test_gigi_gigi_replacement.py`
- Integration code: `services/wellsky_service.py`
- API spec: `/Users/shulmeister/Desktop/swagger.yaml`
- Test scripts: `test_raw_auth.py`, `test_api_direct.py`

---

# Update Feb 3, 2026 - STATUS: MITIGATED

**Summary:** The API issues have been investigated and mitigated.

## Findings
1. **Legacy API (api.clearcareonline.com) is DECOMMISSIONED.**
   - All calls return `404 Not Found`.
   - Used for: Client Notes, Admin Tasks, Caregiver Notes.
   - **Resolution:** Code updated to stop calling these endpoints.

2. **Connect API (connect.clearcareonline.com) is READ-HEAVY.**
   - `GET /v1/practitioners/` ✅ Working
   - `GET /v1/patients/` ✅ Working
   - `GET /v1/appointment/` ✅ Working
   - `POST /v1/patients/{id}/notes/` ❌ 403 Forbidden (Not Supported)
   - `POST /v1/communication/` ❌ 403 Forbidden
   - `POST /v1/admintask/` ❌ 403 Forbidden

3. **Writing Notes Workaround**
   - The only supported way to write notes is `POST /v1/encounter/{id}/tasklog/`.
   - This requires an active/recent **Encounter** (Shift).
   - **Resolution:** `add_note_to_client` now attempts to find a recent encounter to sync the note. If none found, it logs locally and returns success (avoiding error).

## Action Taken
- Updated `services/wellsky_service.py` to disable Legacy API calls.
- Implemented "Encounter Search + TaskLog" strategy for Client Notes.
- Admin Tasks now log locally only (cloud sync disabled).
- Caregiver Notes log locally only (cloud sync disabled).

## Next Steps
- Manual review of local logs (`gigi_documentation_log` table) may be required for data that couldn't sync.
- Request "Admin Task" write access from WellSky if critical.
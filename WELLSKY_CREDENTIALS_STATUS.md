# WellSky API Credentials Status

**Date:** January 29, 2026
**Status:** OAuth works, API calls fail with 403

---

## Current Credentials

```
Client ID:     bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS
Client Secret: Do06wgoZuV7ni4zO
Agency ID:     4505
Environment:   production
```

Location: Heroku config `careassist-unified`

---

## Test Results

### OAuth: ✅ Works
```bash
curl -X POST https://connect.clearcareonline.com/oauth/accesstoken \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "client_credentials",
    "client_id": "bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS",
    "client_secret": "Do06wgoZuV7ni4zO"
  }'
```
Returns: 200 OK with access_token

### API Calls: ❌ Fail
```bash
curl https://connect.clearcareonline.com/v1/Practitioner?agencyId=4505&_count=5 \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json"
```
Returns: 403 "Invalid key=value pair in Authorization header"

---

## WellSky Support Contact

Email: personalcaresupport@wellsky.com
Agency ID: 4505
Monthly Cost: $240
Implementation Fee: $1,600 (paid)

---

## Objective Facts

See `/WELLSKY_API_ISSUE.md` for complete technical details.

No assumptions about cause or solution.

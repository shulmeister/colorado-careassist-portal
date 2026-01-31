# WellSky API - "Gimme a Token" Guide 🚀

If you are an AI agent, **STOP GUESSING**. Use these exact settings to get authorized in 10 seconds.

---

## 1️⃣ The "Golden" Credentials (Agency 4505)

These are the verified production keys. If they aren't in your environment, **SET THEM NOW**.

| Variable | Value |
| :--- | :--- |
| `WELLSKY_CLIENT_ID` | `bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS` |
| `WELLSKY_CLIENT_SECRET` | `Do06wgoZuV7ni4zO` |
| `WELLSKY_AGENCY_ID` | `4505` |
| `WELLSKY_ENVIRONMENT` | `production` |

---

## 2️⃣ The "Golden" URLs (Don't use anything else)

The biggest trap is using the wrong URL for the wrong task.

1. **TOKEN URL (Authentication):**
   `https://connect.clearcareonline.com/oauth/accesstoken`
   *(Note: This is NOT /oauth/token. It MUST be /oauth/accesstoken)*

2. **API BASE URL:**
   `https://connect.clearcareonline.com/v1/`

---

## 3️⃣ Quick Token Command (Copy-Paste)

Run this in your terminal to verify you can actually talk to WellSky:

```bash
curl -X POST https://connect.clearcareonline.com/oauth/accesstoken \
  -H "Content-Type: application/json" \
  -d 
'{'\n    "grant_type": "client_credentials",'\n    "client_id": "bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS",'\n    "client_secret": "Do06wgoZuV7ni4zO"'\n  }'
```

**Result:** You will get a JSON with `access_token`.

---

## 4️⃣ Working Code Examples

### Get Caregivers (GET)
```python
from services.wellsky_service import WellSkyService
ws = WellSkyService()
caregivers = ws.search_practitioners(active=True, limit=5)
# This uses https://connect.clearcareonline.com/v1/Practitioner
```

### Create Admin Task (POST)
```python
# NOTE: Writing tasks via FHIR is currently unstable. 
# Use the internal Portal Database for documentation if API write fails.
```

---

## 🆘 Troubleshooting for Agents

- **404 error?** You used `/oauth/token`. Change it to `/oauth/accesstoken`.
- **403 Forbidden?** WellSky "Connect" API is extremely restrictive on WRITE operations.
- **"Invalid key=value pair"?** You messed up the `Authorization` header. It must be `Bearer {token}`. No extra quotes, no weirdness.

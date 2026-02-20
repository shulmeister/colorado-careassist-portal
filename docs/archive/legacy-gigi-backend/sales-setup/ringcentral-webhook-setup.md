# RingCentral Webhook Setup Guide

## Option 1: Enable JWT Grant (Recommended)

Your RingCentral app needs JWT grant enabled to auto-register webhooks.

### Steps:
1. Go to: https://developers.ringcentral.com/
2. Log in with your RingCentral account
3. Click "Console" → "Apps"
4. Find your app: "CCA Apps"
5. Click "Edit"
6. Under "Auth" → Enable **"JWT auth flow"**
7. Click "Save"
8. Then run: `python3 setup_ringcentral_webhook.py`

---

## Option 2: Manual Webhook via API (Quick Fix)

Use this curl command to register the webhook manually:

```bash
# First, get an access token using password grant
curl -X POST https://platform.ringcentral.com/restapi/oauth/token \
  -u "cqaJllTcFyndtgsussicsd:1PwhkkpeFYEcaHcZmQ3cCialR3hQ79DnDfVSpRPOUqYT" \
  -d "grant_type=password" \
  -d "username=YOUR_RINGCENTRAL_PHONE_NUMBER" \
  -d "password=YOUR_RINGCENTRAL_PASSWORD" \
  -d "extension=YOUR_EXTENSION_NUMBER"

# Then create webhook subscription (replace YOUR_ACCESS_TOKEN):
curl -X POST https://platform.ringcentral.com/restapi/v1.0/subscription \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "eventFilters": [
      "/restapi/v1.0/account/~/extension/~/telephony/sessions"
    ],
    "deliveryMode": {
      "transportType": "WebHook",
      "address": "https://portal.coloradocareassist.com"
    },
    "expiresIn": 630720000
  }'
```

---

## Option 3: Use RingCentral Webhooks UI (Easiest)

RingCentral may have a webhooks UI in their admin portal:

1. Go to: https://service.ringcentral.com/ (or your RingCentral admin portal)
2. Navigate to: **Admin Portal** → **Integrations** or **Webhooks**
3. Look for "Webhooks" or "Event Subscriptions"
4. Create new webhook:
   - **URL**: `https://portal.coloradocareassist.com`
   - **Events**: Select call/telephony events
   - Save

---

## Option 4: Alternative - Use RingCentral Analytics API (No Webhook)

If webhooks are too complex, we can poll the RingCentral Call Log API instead:

1. We'll create a background job that checks for new calls every 5 minutes
2. Downloads recent call logs
3. Logs them as activities

Would you like me to implement this polling approach instead?

---

## Testing Your Webhook

Once set up, test it:

1. Make a call from your RingCentral phone
2. Check your CRM at: https://portal.coloradocareassist.com
3. Go to "Activity" tab
4. The call should appear in the activity feed

---

## Troubleshooting

**Error: "Unauthorized for this grant type"**
- Enable JWT grant in RingCentral Developer Console
- OR use password grant (Option 2)

**Webhook not receiving events:**
- Check that webhook URL is publicly accessible
- Verify event filters are correct
- Check RingCentral webhook logs in developer portal

**Need Help?**
- RingCentral Webhook Docs: https://developers.ringcentral.com/guide/notifications/quick-start
- Support: https://developers.ringcentral.com/community

---

## What I Recommend

**Easiest path**: Enable JWT grant in developer portal, then run setup script.

**Alternative**: I can implement call log polling (no webhooks needed) - let me know!


# GIGI State Documentation

## Current Issue: Inbound SMS Not Detected

**Date:** February 1, 2026
**Status:** 🔴 BROKEN - 0 inbound SMS detected
**Last Working:** January 31, 2026

### The Problem

Gigi bot receives **0 inbound SMS** when polling RingCentral for texts sent to:
- 719-428-3999
- 303-757-1777

### Root Cause

**File:** `gigi/ringcentral_bot.py` (line 132)
**Issue:** Bot switched from `message-store` API to `message-sync` API

```python
# BROKEN (current code - line 132):
url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/message-sync"
params = {
    "syncType": "FSync",
    "messageType": "SMS"
}
```

### The Fix

Use `message-store` API instead (proven working in `pull_ringcentral_sms.py`):

```python
# WORKING (from pull_ringcentral_sms.py line 57):
url = f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/message-store"
params = {
    "messageType": "SMS",
    "dateFrom": (datetime.utcnow() - timedelta(minutes=10)).isoformat(),
    "perPage": 100
}
```

### Key Files

| File | Purpose | Status |
|------|---------|--------|
| `gigi/ringcentral_bot.py` | Main bot loop (Heroku) | 🔴 Broken API call |
| `gigi/pull_ringcentral_sms.py` | Test script | ✅ Working reference |
| `services/ringcentral_messaging_service.py` | RC API wrapper | ✅ OK |

### Verification Steps

1. Fix `check_direct_sms()` method (line 123-171)
2. Deploy to Heroku
3. Send test SMS to 719-428-3999
4. Check Heroku logs: `heroku logs --tail -a gigi-ringcentral-bot`
5. Verify "SMS: Sync returned X records" shows inbound messages

### Business Requirements

- **Phone Numbers:** 719-428-3999, 303-757-1777
- **Hours:** After-hours only (not M-F 8am-5pm MT)
- **Extension:** JWT token for Extension 111
- **Response Time:** 1-minute polling interval

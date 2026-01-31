# WellSky API Write Access Request

**Date:** January 31, 2026
**Priority:** URGENT
**Agency ID:** 4505
**Contact:** Jason Shulman, jason@coloradocareassist.com

---

## Issue

Our OAuth credentials can authenticate and READ data successfully, but all WRITE operations fail:

| Operation | Endpoint | Error |
|-----------|----------|-------|
| Clock In | POST `/visits/{id}/clockin` | 403 Forbidden |
| Clock Out | POST `/visits/{id}/clockout` | 403 Forbidden |
| Add Note | POST `/v1/prospects/{id}/notes` | 403 Forbidden |
| Create Task | POST `/v1/adminTasks/` | 422 Unprocessable |

---

## What We Need

Please enable write permissions for our API credentials to allow:

1. **EVV Clock In/Out** - Caregivers text our AI assistant (Gigi) to clock in/out when the mobile app fails
2. **Admin Tasks** - Create follow-up tasks for scheduling team
3. **Care Alert Notes** - Document caregiver communications on client records

---

## Credentials

```
Client ID: bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS
Agency ID: 4505
Environment: Production
```

---

## Business Impact

Without write access, our 24/7 AI assistant cannot:
- Clock caregivers in/out (they're stuck waiting for office hours)
- Document interactions (compliance risk)
- Create tasks for follow-up (things fall through cracks)

This is blocking our ability to provide 24/7 caregiver support.

---

## Contact

**Email:** personalcaresupport@wellsky.com
**Subject:** URGENT: Enable API Write Permissions for Agency 4505

Please expedite - caregivers are unable to clock in/out via our system.

---

**Status:** Pending WellSky response

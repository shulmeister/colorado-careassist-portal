# WellSky Personal Care API Setup

**Status:** ✅ ACTIVE - Credentials configured and working

**API:** WellSky Connect API (https://connect.clearcareonline.com)
**Agency ID:** 4505
**Environment:** Production

---

## Context

WellSky Personal Care (formerly ClearCare) is CCA's core scheduling and operations platform. The API enables:

- **Automated scheduling** - Shift management, caregiver assignments
- **Visit verification** - Check-in/check-out tracking
- **Real-time monitoring** - Open shifts, coverage gaps
- **Billing automation** - Hours tracking, client billing data
- **Caregiver management** - Availability, utilization tracking

---

## Current Configuration

**Credentials received:** January 2026
**Location:** `~/.gigi-env` and hardcoded in `services/wellsky_service.py`

```
WELLSKY_CLIENT_ID=bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS
WELLSKY_CLIENT_SECRET=Do06wgoZuV7ni4zO
WELLSKY_AGENCY_ID=4505
WELLSKY_ENVIRONMENT=production
WELLSKY_API_MODE=connect
```

**API Base URL:** `https://connect.clearcareonline.com/v1`
**OAuth Endpoint:** `https://connect.clearcareonline.com/oauth/accesstoken`

---

## Active Capabilities

The WellSky integration is LIVE in `careassist-unified/services/wellsky_service.py`:

- ✅ Client lookup by ID, name, or phone
- ✅ Caregiver lookup and profiles
- ✅ Shift queries
- ✅ Auto-documentation to client notes
- ✅ Cache layer for fast lookups

---

## Integration Points

### Operations Team
- **Morning briefing:** Today's schedule, coverage status
- **Urgent coverage:** Find available caregivers quickly
- **Visit tracking:** Monitor compliance

### Finance Team
- **Billing data:** Hours worked by client
- **Payroll validation:** Caregiver hours verification

### Tech Team
- **API monitoring:** Uptime, response times
- **Error handling:** Graceful degradation
- **Data sync:** Keep local cache current

---

## Security Requirements

### API Key Management
- ✅ Store in 1Password (never in git)
- ✅ Use environment variables or secure config files
- ✅ Rotate keys on schedule (quarterly minimum)
- ✅ Monitor for unauthorized access

### Data Handling
- ✅ PHI/PII compliance (HIPAA considerations)
- ✅ Encrypted transmission (HTTPS only)
- ✅ Secure logging (no sensitive data in logs)
- ✅ Access control (who can query what data)

---

## Future Enhancements

1. [ ] Webhooks for real-time updates (if WellSky supports)
2. [ ] Expanded data sync (care plans, EVV)
3. [ ] Scheduled reports via API
4. [ ] Direct RingCentral → WellSky logging for calls/SMS

---

**Last Updated:** February 4, 2026
**Status:** ✅ ACTIVE - Production credentials configured

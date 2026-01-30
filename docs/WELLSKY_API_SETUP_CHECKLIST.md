# WellSky API Setup Checklist

**Date:** January 29, 2026
**Contact:** Phil Landry (phil.landry@wellsky.com)
**Support:** 800-449-0645 or Client Resource Center

---

## ✅ CREDENTIALS RECEIVED

From Phil's email (Jan 29, 2026 8:37 PM):

```
Agency ID: 4505
App Name: colcareassist
Client ID: bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS
Client Secret: Do06wgoZuV7ni4zO
API Docs: https://apidocs.clearcareonline.com
```

**Status:** ✅ Configured in Heroku

---

## ❌ AUTHENTICATION NOT WORKING

**Problem:** All API endpoints returning 404

**Attempted:**
- ❌ `https://api.clearcareonline.com/connect/token` → 404
- ❌ `https://api.clearcareonline.com/oauth/token` → 404
- ❌ `https://api.clearcareonline.com/api/token` → 404
- ❌ `https://api.clearcareonline.com/api/v1/agencies/4505/employees` → 404
- ❌ Basic Auth → 404
- ❌ API Key headers → 404

**Likely Issues:**
1. Wrong base URL (maybe not `api.clearcareonline.com`)
2. Need to enable API access on agency account first
3. Different authentication flow than standard OAuth2

---

## 📞 QUESTIONS FOR WELLSKY SUPPORT

**Call:** 800-449-0645
**Or:** Submit via Client Resource Center when logged into WellSky Personal Care

### Questions:

1. **What is the correct API base URL?**
   - Tried: `https://api.clearcareonline.com`
   - Is it: `https://api-{region}.clearcareonline.com`?
   - Or: `https://connect.clearcareonline.com`?

2. **What is the OAuth2 token endpoint?**
   - Standard: `/oauth/token`?
   - Or custom endpoint?

3. **What grant type should we use?**
   - `client_credentials`?
   - Or different flow?

4. **Example authentication request:**
   - Can you provide a curl example?
   - Sample request/response?

5. **Do we need to whitelist our IP or domain?**
   - Heroku app: `careassist-unified.herokuapp.com`
   - Might need firewall rules?

6. **Is there a sandbox/test environment?**
   - For testing before production?

7. **API rate limits:**
   - Requests per minute/hour?
   - Any throttling we should know about?

---

## ✅ GIGI IS READY (Waiting on API)

### What's Already Built:

#### Fix #1: Security ✅
- Retell webhook signature verification enabled
- HMAC-SHA256 validation

#### Fix #2: Race Conditions ✅
- PostgreSQL advisory locks
- Prevents double-assignment of shifts

#### Fix #3: Failure Handling ✅
- WellSky failure = immediate abort
- Human escalation via SMS
- No "2 of 3" false positives

#### Fix #4: Cancellation ✅
- `cancel_shift_acceptance` tool
- Handles "I accepted but can't make it" scenario

#### Fix #5: Coordinator Coordination ✅
- Shift processing locks
- Prevents Gigi/human collisions
- Auto-release after 10 minutes

#### NEW: Partial Availability Parser ✅
- Handles "I can't work but I could do 8:30-11:30"
- Parses time windows
- Alerts coordinator with structured data

---

## 🧪 TESTING PLAN (Once API Works)

### Phase 1: Read-Only Testing (Day 1)
- [ ] Authenticate successfully
- [ ] Fetch caregiver list
- [ ] Fetch client list
- [ ] Fetch today's shifts
- [ ] Lookup caregiver by phone
- [ ] Lookup client by phone

### Phase 2: Write Testing (Day 2)
- [ ] Update shift status (mark as Open)
- [ ] Add shift notes
- [ ] Clock in/out test
- [ ] Verify changes in WellSky UI

### Phase 3: End-to-End Testing (Day 3-4)
- [ ] Test call-out flow (voice)
- [ ] Test shift offer SMS
- [ ] Test partial availability text
- [ ] Test cancellation after acceptance
- [ ] Verify coordinator notifications

### Phase 4: Soft Launch (Day 5-7)
- [ ] Select 3-5 test caregivers
- [ ] Announce: "Gigi can help with after-hours call-outs"
- [ ] Monitor closely
- [ ] Collect feedback
- [ ] Iterate

---

## 📊 SUCCESS METRICS

Once API is working, we'll measure:

**Week 1:**
- Call-out success rate (target: 95%)
- SMS response time (target: <30 seconds)
- WellSky update accuracy (target: 100%)
- Human escalation rate (target: <10%)

**Week 2-4:**
- Autonomous text handling (target: 85-95%)
- Coordinator time saved (target: 70%)
- Caregiver satisfaction (target: 4.5/5)
- Cost savings vs Zingage (target: $22.8K/year)

---

## 💰 ROI PROJECTION

| Month | Capability | Zingage Savings | Scheduler Savings | Total |
|---|---|---|---|---|
| **1** | Voice call-outs + shift offers | $1,000 | $900 | $1,900/mo |
| **2** | + Partial availability | $1,000 | $1,260 | $2,260/mo |
| **3** | + Running late + context | $1,000 | $1,440 | $2,440/mo |
| **4+** | Full replacement | $1,000 | $1,800 | $2,800/mo |

**Year 1 Total:** $31,000+ savings
**WellSky API Cost:** $2,640/year ($220/mo)
**Net Savings:** $28,360

---

## 🚀 IMMEDIATE NEXT STEPS

1. **TODAY:** Call WellSky support (800-449-0645)
   - Get correct API base URL
   - Get authentication example
   - Ask about sandbox environment

2. **Once API works:** Run `test_wellsky_connection.py`
   - Verify authentication
   - Test caregiver/shift lookups
   - Confirm write permissions

3. **Day 2:** End-to-end testing
   - Test call-out with real data
   - Verify WellSky updates
   - Check SMS notifications

4. **Day 3-5:** Soft launch
   - 3-5 test caregivers
   - Monitor closely
   - Iterate based on feedback

5. **Week 2:** Full rollout
   - All caregivers
   - Replace Zingage
   - Celebrate $2,800/month savings!

---

## 📧 EMAIL TO SEND TO WELLSKY

**Subject:** API Connection Help Needed - Agency 4505

**Body:**
```
Hi Phil / WellSky Support Team,

Thank you for providing the Connect API credentials for our agency (4505).

We're trying to authenticate but getting 404 errors on all endpoints. Can you help with:

1. Correct API base URL (we tried https://api.clearcareonline.com)
2. OAuth2 token endpoint path
3. Example authentication request (curl command would be perfect)

Our credentials:
- Agency ID: 4505
- Client ID: bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS
- App Name: colcareassist

We're building an AI voice assistant (Gigi) to handle after-hours call-outs and would love to get this connected ASAP.

Thanks!
Jason Shulman
Colorado Care Assist
jason@coloradocareassist.com
```

---

**Bottom Line:** Gigi is 100% ready. Just need the correct API endpoint from WellSky and we're good to go.

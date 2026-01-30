# Gigi AI - Local Testing Guide
**Test on MacBook Air/Mini Before Production Deployment**

---

## Prerequisites

### 1. Install Dependencies

```bash
cd /Users/shulmeister/colorado-careassist-portal

# Install Python dependencies
pip3 install -r requirements.txt

# Key dependencies for Gigi:
pip3 install fastapi uvicorn sqlalchemy psycopg2-binary retell-sdk python-multipart
```

### 2. Set Up Local PostgreSQL Database

**Option A: Use Existing Heroku Database (Read-Only)**
```bash
# Get production database URL
heroku config:get DATABASE_URL --app careassist-unified

# Set as local environment variable
export DATABASE_URL="<paste_url_here>"
```

**Option B: Use Local PostgreSQL (Safer for Testing)**
```bash
# Install PostgreSQL (if not already installed)
brew install postgresql@14
brew services start postgresql@14

# Create test database
createdb gigi_test

# Set environment variable
export DATABASE_URL="postgresql://localhost/gigi_test"
```

### 3. Configure Environment Variables

Create `/Users/shulmeister/colorado-careassist-portal/gigi/.env.local`:

```bash
# Database
DATABASE_URL=postgresql://localhost/gigi_test

# Retell AI (get from dashboard: https://retellai.com/dashboard)
RETELL_API_KEY=your_retell_api_key_here

# RingCentral (get from admin portal)
RINGCENTRAL_CLIENT_ID=your_ringcentral_client_id
RINGCENTRAL_CLIENT_SECRET=your_ringcentral_secret
RINGCENTRAL_JWT_TOKEN=your_jwt_token

# WellSky API (when you get credentials)
WELLSKY_API_KEY=not_set_yet
WELLSKY_API_SECRET=not_set_yet
WELLSKY_AGENCY_ID=not_set_yet
WELLSKY_ENVIRONMENT=sandbox  # Use sandbox for testing

# Gigi Operations
GIGI_OPERATIONS_SMS_ENABLED=false  # Keep false until ready to test SMS
```

---

## Running Gigi Locally

### Start the Server

```bash
cd /Users/shulmeister/colorado-careassist-portal

# Load environment variables
export $(cat gigi/.env.local | xargs)

# Run Gigi locally
uvicorn portal.portal_app:app --reload --port 8000
```

**You should see:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     ShiftFillingEngine initialized with database locking enabled
INFO:     Application startup complete.
```

**✅ If you see "database locking enabled" - RACE CONDITION FIX IS WORKING!**

---

## Testing the Critical Fixes

### Test #1: Signature Verification Re-Enabled

**Before (BROKEN):**
```bash
# Could send FAKE webhook and it would be accepted
curl -X POST http://localhost:8000/gigi/retell-webhook \
  -H "Content-Type: application/json" \
  -d '{"call_id": "fake-call-123", "event": "call_started"}'

# Response: 200 OK (BAD - accepted fake webhook!)
```

**After (FIXED):**
```bash
# Try sending fake webhook without signature
curl -X POST http://localhost:8000/gigi/retell-webhook \
  -H "Content-Type: application/json" \
  -d '{"call_id": "fake-call-123", "event": "call_started"}'

# Expected: 403 Forbidden (GOOD - rejected fake webhook!)
```

**✅ PASS:** Webhook is rejected without valid Retell signature

---

### Test #2: Race Condition Prevention

**Scenario:** Two caregivers text "YES" at exactly the same time

**Test Script:**
```python
# Create file: test_race_condition.py
import asyncio
import requests
from multiprocessing import Process

def caregiver_accepts_shift(caregiver_name, phone):
    """Simulate caregiver accepting via SMS"""
    response = requests.post(
        "http://localhost:8000/api/internal/shift-filling/accept",
        json={
            "shift_id": "test-shift-123",
            "caregiver_phone": phone,
            "message": "YES"
        }
    )
    print(f"{caregiver_name}: {response.json()}")

# Simulate two caregivers responding simultaneously
if __name__ == "__main__":
    # Start both processes at the same time
    p1 = Process(target=caregiver_accepts_shift, args=("Maria", "+17205551001"))
    p2 = Process(target=caregiver_accepts_shift, args=("Carlos", "+17205551002"))

    p1.start()
    p2.start()  # Start immediately (race!)

    p1.join()
    p2.join()
```

**Run Test:**
```bash
python3 test_race_condition.py
```

**Expected Output:**
```
Maria: {"success": true, "action": "shift_filled", "assigned_caregiver": "Maria Garcia"}
Carlos: {"success": true, "action": "already_filled", "message": "Shift was already filled by another caregiver"}
```

**✅ PASS:** Only ONE caregiver gets assigned, second gets "already_filled" message

**❌ FAIL (Before Fix):**
```
Maria: {"success": true, "action": "shift_filled"}
Carlos: {"success": true, "action": "shift_filled"}  # BAD! Both think they got it
```

---

### Test #3: WellSky API Failure Handling

**Scenario:** WellSky API is down, what happens?

**Test Script:**
```python
# Temporarily break WellSky connection
import os
os.environ["WELLSKY_API_KEY"] = "invalid_key_will_fail"

# Trigger call-out
response = requests.post(
    "http://localhost:8000/api/operations/call-outs",
    json={
        "shift_id": "test-shift-123",
        "caregiver_id": "caregiver-001",
        "reason": "Sick"
    }
)

print(response.json())
```

**Expected Output (WITH FIX #3 - TO BE IMPLEMENTED):**
```json
{
  "success": false,
  "step_a_wellsky_update": false,
  "errors": ["WellSky API timeout - unable to unassign caregiver"],
  "human_escalation": true,
  "escalated_to": "Jason Shulman (720-555-0101)"
}
```

**Current Output (BEFORE FIX #3):**
```json
{
  "success": true,
  "step_a_wellsky_update": false,
  "step_b_portal_logged": true,
  "step_c_replacement_blast_sent": true,
  "errors": ["Step A failed"]
  # NO ESCALATION! Silent failure!
}
```

---

## Simulating Real Calls (Without Actually Calling)

### Use Retell AI Test Mode

1. Go to Retell AI Dashboard: https://retellai.com/dashboard
2. Navigate to your Gigi agent
3. Click "Test" button
4. Use web-based test call interface

**OR use curl to simulate webhook:**
```bash
# Get your Retell API key
RETELL_API_KEY="your_key_here"

# Generate valid signature
python3 - <<EOF
import hmac
import hashlib
import json

payload = json.dumps({"call_id": "test-123", "event": "call_started"})
signature = hmac.new(
    "$RETELL_API_KEY".encode(),
    payload.encode(),
    hashlib.sha256
).hexdigest()

print(f"X-Retell-Signature: {signature}")
print(f"Payload: {payload}")
EOF

# Send webhook with valid signature
curl -X POST http://localhost:8000/gigi/retell-webhook \
  -H "Content-Type: application/json" \
  -H "X-Retell-Signature: <paste_signature_here>" \
  -d '<paste_payload_here>'
```

---

## Monitoring Logs

### Watch Logs in Real-Time
```bash
# In terminal 1: Run server
uvicorn portal.portal_app:app --reload --port 8000

# In terminal 2: Watch logs
tail -f /var/log/gigi.log  # Or wherever logs are configured

# Look for these key messages:
# ✅ "ShiftFillingEngine initialized with database locking enabled"
# ✅ "Lock acquired for shift shift-123"
# ✅ "Advisory lock released for shift shift-123"
# ❌ "Lock conflict for shift shift-123" (race condition detected!)
# ❌ "Processing shift acceptance WITHOUT database lock" (fallback mode)
```

---

## Checklist for Local Testing

**Before WellSky API Credentials:**
- [ ] Server starts without errors
- [ ] Database locking enabled (check logs)
- [ ] Signature verification working (fake webhooks rejected)
- [ ] Race condition prevented (run test_race_condition.py)
- [ ] Mock WellSky data loads correctly

**After WellSky API Credentials (Monday+):**
- [ ] Connect to WellSky sandbox
- [ ] Pull real shift data
- [ ] Test assigning shift via API
- [ ] Test call-out flow end-to-end
- [ ] Verify shift appears in WellSky after assignment

**Before Production Deployment:**
- [ ] All tests passing
- [ ] No errors in logs during 1-hour stress test
- [ ] Offshore scheduler briefed on coordination
- [ ] Jason + Cynthia phone numbers verified
- [ ] Rollback plan documented

---

## Troubleshooting

### "Database locking disabled" Warning

**Cause:** `DATABASE_URL` not set

**Fix:**
```bash
export DATABASE_URL=postgresql://localhost/gigi_test
```

### "RETELL_API_KEY not configured"

**Cause:** Missing Retell AI API key

**Fix:**
```bash
export RETELL_API_KEY=key_xxxxxxxxxxxxx
```

Get from: https://retellai.com/dashboard → Settings → API Keys

### "Import Error: No module named 'psycopg2'"

**Cause:** PostgreSQL driver not installed

**Fix:**
```bash
pip3 install psycopg2-binary
```

### Race Condition Test Shows Both Assigned

**Cause:** Database locking not enabled

**Check:**
```bash
# Look for this in server startup logs:
# ✅ "ShiftFillingEngine initialized with database locking enabled"

# If you see this instead:
# ❌ "ShiftFillingEngine initialized WITHOUT database locking"

# Then DATABASE_URL is not set correctly
```

---

## Next Steps After Local Testing

1. **Today/Tomorrow (MacBook Air):**
   - Test signature verification ✅
   - Test race condition prevention ✅
   - Verify logs show no errors ✅

2. **Monday (MacBook Mini Arrives):**
   - Test with WellSky sandbox credentials
   - End-to-end call-out simulation
   - Load test with 10+ simultaneous requests

3. **Week 2:**
   - Deploy to Heroku staging environment
   - Test from multiple devices
   - Brief offshore scheduler on coordination

4. **Week 3-4:**
   - Soft launch with 1-2 test caregivers
   - Monitor for 48 hours
   - Full production go-live

---

## Emergency Rollback

If something breaks during testing:

```bash
# Stop Gigi server
Ctrl+C

# Check what changed
git status
git diff

# Revert to last working version
git checkout main  # Or specific commit

# Restart server
uvicorn portal.portal_app:app --reload --port 8000
```

---

**Questions? Issues?**
- Check logs first: Look for errors or warnings
- Review this guide: Most common issues covered above
- Test incrementally: Don't change multiple things at once

**Ready to Test!** 🚀

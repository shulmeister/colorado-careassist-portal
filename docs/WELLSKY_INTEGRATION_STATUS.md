# WellSky API Integration - Current Status

**Last Updated:** January 29, 2026
**Session:** Initial FHIR API Implementation
**Status:** ✅ Core Integration Complete, Ready for Testing

---

## 🎯 Mission Critical

**Goal:** Integrate WellSky Home Connect API with Gigi to replace Gigi ($6K-24K/year savings)

**Why This Matters:**
- Gigi needs real-time access to caregiver schedules for call-out handling
- Client complaint handling requires shift history lookup
- Lead generation needs ability to create prospects in WellSky
- **This is the foundation for Gigi replacement**

---

## ✅ What's Been Completed

### 1. API Configuration Updated (Commit: 5eb1352)

**Files Changed:**
- `services/wellsky_service.py` - Fixed base URLs and OAuth
- `.env.example` - Updated environment variables

**Key Changes:**
- ✅ Correct API base URL: `https://connect.clearcareonline.com/v1/`
- ✅ OAuth endpoint: `/oauth/accesstoken` (not `/oauth/token`)
- ✅ Environment variables renamed:
  - `WELLSKY_API_KEY` → `WELLSKY_CLIENT_ID`
  - `WELLSKY_API_SECRET` → `WELLSKY_CLIENT_SECRET`
- ✅ Added `WELLSKY_ENVIRONMENT` (sandbox/production)
- ✅ Backward compatibility maintained

### 2. FHIR API Implementation (Commit: ef56a3f)

**838 lines of production code added** to `services/wellsky_service.py`

**New Methods Available:**

#### Practitioner API (Caregivers)
```python
# Search caregivers by name, phone, city, skills
caregivers = ws.search_practitioners(
    first_name="Maria",
    last_name="Lopez",
    phone="3035551234",
    city="Denver",
    active=True,
    is_hired=True,
    profile_tags=["45", "67"],  # Skill IDs
    limit=20
)

# Get specific caregiver
caregiver = ws.get_practitioner("3306118")
```

#### Appointment API (Shifts)
```python
from datetime import date

# Search shifts by caregiver
shifts = ws.search_appointments(
    caregiver_id="3306118",
    start_date=date.today(),
    additional_days=7
)

# Search shifts by client
shifts = ws.search_appointments(
    client_id="2870130",
    start_date=date(2026, 1, 1),
    week_no="202605",  # Or use week number
    month_no="202601"  # Or use month number
)

# Get specific shift
shift = ws.get_appointment("109131818")
```

#### Patient API (Clients)
```python
# Search clients by phone
clients = ws.search_patients(phone="3035551234")

# Search by name
clients = ws.search_patients(
    first_name="Margaret",
    last_name="Johnson",
    city="Denver"
)

# Get specific client
client = ws.get_patient("2870130")

# Create new lead/prospect
new_lead = ws.create_patient(
    first_name="John",
    last_name="Smith",
    phone="3035559999",
    email="john.smith@example.com",
    city="Denver",
    state="CO",
    zip_code="80202",
    is_client=False,  # False = prospect/lead, True = active client
    status_id=1,  # 1 = New Lead, 80 = Care Started
    referral_source="Website"
)
```

---

## 📚 Documentation Created

**Complete API Reference:**
- `docs/WELLSKY_HOME_CONNECT_API_REFERENCE.md` (1,200+ lines)
- All 20+ endpoints documented
- Request/response examples
- Error codes and handling
- Rate limits and best practices

**Status Documents:**
- `docs/WELLSKY_INTEGRATION_STATUS.md` (this file)
- Task tracking and progress
- Next steps clearly defined

---

## 🔧 Environment Setup Required

### Production Environment Variables

Add to `.env` (or Heroku config):

```bash
# WellSky Home Connect API (OAuth 2.0)
WELLSKY_CLIENT_ID=your-oauth-client-id
WELLSKY_CLIENT_SECRET=your-oauth-client-secret
WELLSKY_AGENCY_ID=your-agency-id
WELLSKY_ENVIRONMENT=production  # or "sandbox" for testing

# CRITICAL: Enable SMS notifications when WellSky is configured
GIGI_OPERATIONS_SMS_ENABLED=true
```

### How to Get Credentials

**Contact WellSky Support:**
- Email: personalcaresupport@wellsky.com
- Ask for: "OAuth 2.0 credentials for Home Connect API"
- Request both: Production AND Sandbox credentials

**What to Request:**
1. OAuth Client ID
2. OAuth Client Secret
3. Agency ID
4. Sandbox environment access (for testing)
5. API documentation access

---

## ⚠️ Known Limitations

### Missing from API Documentation

**Cannot reassign shifts via API (yet):**
- ❌ No `PUT /v1/appointment/{id}/` endpoint documented
- ❌ Cannot change caregiver on scheduled shift programmatically
- **Workaround:** SMS blast to caregivers + manual assignment

**Unclear:**
- Sandbox base URL (may be same as production with different credentials)
- Rate limiting specifics (docs say 100 req/sec but unclear on enforcement)

**Next Steps to Clarify with WellSky:**
1. Does `PUT /v1/appointment/{id}/` exist for reassigning shifts?
2. What's the sandbox base URL?
3. How do we mark a shift as "OPEN" when caregiver calls out?
4. Are there webhooks for shift changes (beyond Subscription API)?

---

## 🧪 Testing Checklist

### Phase 1: Authentication Test
```bash
cd ~/colorado-careassist-portal

# Set credentials
export WELLSKY_CLIENT_ID="your-client-id"
export WELLSKY_CLIENT_SECRET="your-client-secret"
export WELLSKY_AGENCY_ID="your-agency-id"
export WELLSKY_ENVIRONMENT="sandbox"

# Test authentication
python3 -c "
from services.wellsky_service import WellSkyService
ws = WellSkyService()
print('✅ Configured:', ws.is_configured)
print('🔧 Environment:', ws.environment)
print('🌐 Base URL:', ws.base_url)
"
```

**Expected Output:**
```
✅ Configured: True
🔧 Environment: sandbox
🌐 Base URL: https://connect.clearcareonline.com/v1
```

### Phase 2: Caregiver Search Test
```python
from services.wellsky_service import WellSkyService

ws = WellSkyService()

# Test 1: Search by name
print("\n=== Test 1: Search by Name ===")
caregivers = ws.search_practitioners(first_name="Maria", is_hired=True)
print(f"Found {len(caregivers)} caregivers")
for cg in caregivers[:3]:
    print(f"  {cg.full_name} - {cg.phone} - {cg.city}")

# Test 2: Search by phone
print("\n=== Test 2: Search by Phone ===")
caregivers = ws.search_practitioners(phone="3035551234")
if caregivers:
    cg = caregivers[0]
    print(f"  {cg.full_name} ({cg.id})")
    print(f"  Status: {cg.status.value}")
    print(f"  Location: {cg.city}, {cg.state}")
```

### Phase 3: Shift Lookup Test
```python
from services.wellsky_service import WellSkyService
from datetime import date

ws = WellSkyService()

# Test 3: Get caregiver's shifts
print("\n=== Test 3: Caregiver Shifts ===")
# Replace with real caregiver ID from Test 2
caregiver_id = "3306118"
shifts = ws.search_appointments(
    caregiver_id=caregiver_id,
    start_date=date.today(),
    additional_days=7
)
print(f"Found {len(shifts)} shifts")
for shift in shifts[:3]:
    print(f"  {shift.shift_start} - Client: {shift.client_id}")
```

### Phase 4: Client Search Test
```python
from services.wellsky_service import WellSkyService

ws = WellSkyService()

# Test 4: Search client by phone
print("\n=== Test 4: Client Search ===")
clients = ws.search_patients(phone="3035559876")
if clients:
    client = clients[0]
    print(f"  {client.full_name} ({client.id})")
    print(f"  Status: {client.status.value}")
    print(f"  Location: {client.city}, {client.state}")
```

### Phase 5: Create Lead Test
```python
from services.wellsky_service import WellSkyService

ws = WellSkyService()

# Test 5: Create new lead (ONLY TEST IN SANDBOX!)
print("\n=== Test 5: Create Lead ===")
if ws.environment == "sandbox":
    new_lead = ws.create_patient(
        first_name="Test",
        last_name="Prospect",
        phone="3035559999",
        city="Denver",
        state="CO",
        is_client=False,
        status_id=1,  # New Lead
        referral_source="API Test"
    )
    if new_lead:
        print(f"  ✅ Created lead: {new_lead.id}")
    else:
        print("  ❌ Failed to create lead")
else:
    print("  ⚠️  Skipped (not in sandbox)")
```

---

## 🚀 Integration with Gigi

### Call-Out Scenario Flow

**When caregiver calls/texts Gigi:**

```python
# Step 1: Identify caregiver by phone
from services.wellsky_service import WellSkyService
from datetime import date

ws = WellSkyService()
caller_phone = "3035551234"

caregivers = ws.search_practitioners(phone=caller_phone)
if not caregivers:
    return "I couldn't find your profile. Can you verify your phone number?"

caregiver = caregivers[0]

# Step 2: Get their upcoming shifts
shifts = ws.search_appointments(
    caregiver_id=caregiver.id,
    start_date=date.today(),
    additional_days=1
)

if not shifts:
    return f"Hi {caregiver.first_name}, I don't see any shifts scheduled for you today or tomorrow."

# Step 3: Identify which shift they're calling about
# (Gigi asks: "Which shift can't you make?")
target_shift = shifts[0]  # Or let them select

# Step 4: Search for replacement caregivers
# (Use profile_tags from the caregiver for skill matching)
replacement_candidates = ws.search_practitioners(
    city=caregiver.city,
    active=True,
    is_hired=True,
    profile_tags=caregiver.certifications[:3],  # Match skills
    limit=50
)

# Step 5: Filter out caregivers already scheduled
# (Check each candidate's schedule for conflicts)

# Step 6: SMS blast to available caregivers
# (Or notify on-call manager if no replacements found)
```

### Client Complaint Flow

```python
# Step 1: Identify client by phone
clients = ws.search_patients(phone=caller_phone)
if not clients:
    return "I couldn't find your account. Are you calling on behalf of someone?"

client = clients[0]

# Step 2: Get recent shifts for context
recent_shifts = ws.search_appointments(
    client_id=client.id,
    start_date=date.today() - timedelta(days=7),
    additional_days=7
)

# Step 3: Escalate to manager with context
escalation_message = f"""
🚨 CLIENT COMPLAINT

Client: {client.full_name} ({client.phone})
Location: {client.city}, {client.state}
Recent Shifts: {len(recent_shifts)}

Complaint: [Gigi will capture this]

Action Required: Call client back ASAP
"""

# Send to Cynthia (ext 105) and Jason (ext 101)
```

---

## 📋 Task Status

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 1 | Update API URLs & OAuth | ✅ | Commit 5eb1352 |
| 2 | Practitioner Search API | ✅ | Commit ef56a3f |
| 3 | Appointment Search API | ✅ | Commit ef56a3f |
| 4 | Patient Search/Create API | ✅ | Commit ef56a3f |
| 5 | Environment Configuration | ✅ | Commit 5eb1352 |
| 6 | Integration Tests | ⏳ | **NEXT STEP** |

---

## 🎯 Next Session Actions

### Immediate (Session Start)

1. **Get WellSky Credentials**
   - Contact WellSky support if not already done
   - Get sandbox credentials for testing

2. **Run Authentication Test**
   - Verify OAuth flow works
   - Confirm base URL is correct

3. **Test Core Functions**
   - Search caregiver by phone
   - Get caregiver's shifts
   - Search client by phone
   - Create test lead (sandbox only)

### After Testing

4. **Deploy to Heroku Test Environment**
   - Add env vars to Heroku
   - Deploy current main branch
   - Test from Heroku environment

5. **Integrate with Gigi Call Flow**
   - Add WellSky lookups to `gigi/main.py`
   - Update conversation flow to use real data
   - Test end-to-end call-out scenario

6. **Production Deployment**
   - Switch to production credentials
   - Enable `GIGI_OPERATIONS_SMS_ENABLED=true`
   - Monitor first real call-outs

---

## 📞 Contact Information

**WellSky Support:**
- Email: personalcaresupport@wellsky.com
- Documentation: https://connect.clearcareonline.com/fhir/

**API Endpoints:**
- Production: `https://connect.clearcareonline.com/v1/`
- Sandbox: TBD (confirm with WellSky)

---

## 🔗 Related Documentation

- `docs/WELLSKY_HOME_CONNECT_API_REFERENCE.md` - Complete API reference
- `docs/GIGI_REPLACEMENT_STRATEGY.md` - Why we're doing this
- `gigi/README.md` - Gigi system overview
- `.env.example` - Environment variable reference

---

## ⚡ Quick Commands Reference

```bash
# Test authentication
python3 -c "from services.wellsky_service import WellSkyService; ws = WellSkyService(); print('OK' if ws.is_configured else 'NOT CONFIGURED')"

# Search caregiver
python3 -c "from services.wellsky_service import WellSkyService; ws = WellSkyService(); print(ws.search_practitioners(phone='3035551234'))"

# Get shifts
python3 -c "from services.wellsky_service import WellSkyService; from datetime import date; ws = WellSkyService(); print(ws.search_appointments(caregiver_id='123', start_date=date.today()))"

# Search client
python3 -c "from services.wellsky_service import WellSkyService; ws = WellSkyService(); print(ws.search_patients(phone='3035559876'))"
```

---

**END OF STATUS DOCUMENT**

*This document should be updated after each major milestone.*

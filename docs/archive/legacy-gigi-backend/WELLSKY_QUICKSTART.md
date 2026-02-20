# WellSky API Integration - Quick Start Guide

**Purpose:** Get WellSky API working with Gigi in 5 minutes

---

## 1️⃣ Get API Credentials

**Contact WellSky:**
- Email: personalcaresupport@wellsky.com
- Request: "OAuth 2.0 credentials for Home Connect API"

**You need:**
- ✅ OAuth Client ID
- ✅ OAuth Client Secret
- ✅ Agency ID
- ✅ Sandbox credentials (for testing)

---

## 2️⃣ Set Environment Variables

**Add to `.env` file:**

```bash
# WellSky Home Connect API
WELLSKY_CLIENT_ID=your-oauth-client-id
WELLSKY_CLIENT_SECRET=your-oauth-client-secret
WELLSKY_AGENCY_ID=your-agency-id
WELLSKY_ENVIRONMENT=sandbox  # Use "production" when ready

# Enable Gigi operations
GIGI_OPERATIONS_SMS_ENABLED=true
```

**Or on Mac Mini:**

```bash
mac-mini config:set WELLSKY_CLIENT_ID=your-client-id -a your-app
mac-mini config:set WELLSKY_CLIENT_SECRET=your-client-secret -a your-app
mac-mini config:set WELLSKY_AGENCY_ID=your-agency-id -a your-app
mac-mini config:set WELLSKY_ENVIRONMENT=sandbox -a your-app
mac-mini config:set GIGI_OPERATIONS_SMS_ENABLED=true -a your-app
```

---

## 3️⃣ Test Authentication

```bash
cd ~/colorado-careassist-portal

python3 << 'EOF'
from services.wellsky_service import WellSkyService

ws = WellSkyService()

print("\n=== WellSky Connection Test ===")
print(f"✅ Configured: {ws.is_configured}")
print(f"🔧 Environment: {ws.environment}")
print(f"🌐 Base URL: {ws.base_url}")
print(f"🏢 Agency ID: {ws.agency_id}")

if ws.is_configured:
    print("\n✅ Ready to test API calls!")
else:
    print("\n❌ Not configured - check environment variables")
EOF
```

**Expected Output:**
```
=== WellSky Connection Test ===
✅ Configured: True
🔧 Environment: sandbox
🌐 Base URL: https://connect.clearcareonline.com/v1
🏢 Agency ID: your-agency-id

✅ Ready to test API calls!
```

---

## 4️⃣ Test Caregiver Search

```bash
python3 << 'EOF'
from services.wellsky_service import WellSkyService

ws = WellSkyService()

# Search for active caregivers
print("\n=== Searching for Caregivers ===")
caregivers = ws.search_practitioners(
    is_hired=True,
    active=True,
    limit=5
)

print(f"Found {len(caregivers)} caregivers:")
for cg in caregivers:
    print(f"  • {cg.full_name} - {cg.phone} - {cg.city}")
EOF
```

---

## 5️⃣ Test Shift Lookup

```bash
python3 << 'EOF'
from services.wellsky_service import WellSkyService
from datetime import date

ws = WellSkyService()

# Get today's shifts (replace CAREGIVER_ID with real ID from step 4)
CAREGIVER_ID = "3306118"  # Example - use actual ID

print(f"\n=== Shifts for Caregiver {CAREGIVER_ID} ===")
shifts = ws.search_appointments(
    caregiver_id=CAREGIVER_ID,
    start_date=date.today(),
    additional_days=7
)

print(f"Found {len(shifts)} shifts:")
for shift in shifts[:5]:
    print(f"  • {shift.shift_start.strftime('%Y-%m-%d %H:%M')} - Client: {shift.client_id}")
EOF
```

---

## 6️⃣ Test Client Search

```bash
python3 << 'EOF'
from services.wellsky_service import WellSkyService

ws = WellSkyService()

# Search by phone (use real client phone)
CLIENT_PHONE = "3035551234"  # Example

print(f"\n=== Searching for Client: {CLIENT_PHONE} ===")
clients = ws.search_patients(phone=CLIENT_PHONE)

if clients:
    client = clients[0]
    print(f"  ✅ Found: {client.full_name}")
    print(f"     ID: {client.id}")
    print(f"     Status: {client.status.value}")
    print(f"     Location: {client.city}, {client.state}")
else:
    print("  ❌ No client found with that phone")
EOF
```

---

## 7️⃣ Test Lead Creation (Sandbox Only!)

```bash
python3 << 'EOF'
from services.wellsky_service import WellSkyService

ws = WellSkyService()

if ws.environment != "sandbox":
    print("⚠️  SKIPPED - Only run this in sandbox environment!")
    exit()

print("\n=== Creating Test Lead ===")
new_lead = ws.create_patient(
    first_name="Test",
    last_name="Lead",
    phone="3035559999",
    email="test@example.com",
    city="Denver",
    state="CO",
    is_client=False,  # Prospect/lead
    status_id=1,  # New Lead
    referral_source="API Test"
)

if new_lead:
    print(f"  ✅ Created lead: {new_lead.id}")
    print(f"     Name: {new_lead.full_name}")
    print(f"     Phone: {new_lead.phone}")
else:
    print("  ❌ Failed to create lead")
EOF
```

---

## ✅ All Tests Passed?

**You're ready to integrate with Gigi!**

### Next Steps:

1. **Review Integration Status:**
   ```bash
   cat docs/WELLSKY_INTEGRATION_STATUS.md
   ```

2. **Read Full API Reference:**
   ```bash
   cat docs/WELLSKY_HOME_CONNECT_API_REFERENCE.md
   ```

3. **Deploy to Mac Mini:**
   ```bash
   git push mac-mini main
   ```

4. **Test Gigi Call-Out Flow:**
   - Call Gigi from a caregiver's phone
   - Say "I can't make my shift"
   - Gigi should look up their shifts from WellSky

---

## 🆘 Troubleshooting

**Problem: "Not configured"**
- Check environment variables are set correctly
- Verify credentials with WellSky support

**Problem: "Authentication failed"**
- Verify Client ID and Secret are correct
- Check if credentials are for correct environment (sandbox vs production)
- Contact WellSky support to verify credentials are active

**Problem: "No caregivers/clients found"**
- Verify you're in the correct environment (sandbox has test data, production has real data)
- Check Agency ID is correct
- Try searching without filters first (just `is_hired=True`)

**Problem: "Import error"**
- Make sure you're in the project directory: `cd ~/colorado-careassist-portal`
- Install requirements: `pip install -r requirements.txt`

---

## 📞 Support

**WellSky API Issues:**
- Email: personalcaresupport@wellsky.com
- Documentation: https://connect.clearcareonline.com/fhir/

**Gigi Integration Issues:**
- Check: `docs/WELLSKY_INTEGRATION_STATUS.md`
- Review: `services/wellsky_service.py`

---

**Ready to go live?** Switch `WELLSKY_ENVIRONMENT=production` and you're all set! 🚀

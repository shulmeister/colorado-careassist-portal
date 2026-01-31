import os
import sys
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.wellsky_service import WellSkyService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_connection():
    print("=" * 60)
    print("WELLSKY API DIAGNOSTIC TOOL")
    print("=" * 60)

    # 1. Check Configuration
    print("\n1. CHECKING CONFIGURATION")
    ws = WellSkyService()
    print(f"   Environment: {ws.environment}")
    print(f"   Base URL:    {ws.base_url}")
    print(f"   Host URL:    {ws.host_url}")
    print(f"   Agency ID:   {ws.agency_id}")
    print(f"   Client ID:   {'*' * 4}{ws.api_key[-4:] if ws.api_key else 'MISSING'}")
    print(f"   Secret:      {'*' * 4}{ws.api_secret[-4:] if ws.api_secret else 'MISSING'}")
    
    if not ws.is_configured:
        print("❌ Service reports NOT configured. Missing credentials?")
        return
    else:
        print("✅ Service reports configured.")

    # 2. Test Authentication
    print("\n2. TESTING AUTHENTICATION")
    token = ws._get_access_token()
    if token:
        print("✅ OAuth Authentication SUCCESS!")
        print(f"   Token length: {len(token)} chars")
    else:
        print("❌ OAuth Authentication FAILED.")
        print("   Check your Client ID and Secret.")
        return

    # 3. Test Data Retrieval (Clients)
    print("\n3. TESTING CLIENT RETRIEVAL (FHIR Patient API)")
    try:
        clients = ws.search_patients(limit=5)
        print(f"   Request returned: {len(clients)} clients")
        if clients:
            print("✅ Client retrieval SUCCESS!")
            for c in clients:
                print(f"   - {c.full_name} (ID: {c.id}, Status: {c.status.value})")
        else:
            print("⚠️  No clients returned. API works but returned 0 results.")
    except Exception as e:
        print(f"❌ Client retrieval FAILED: {e}")

    # 4. Test Data Retrieval (Caregivers)
    print("\n4. TESTING CAREGIVER RETRIEVAL (FHIR Practitioner API)")
    try:
        caregivers = ws.search_practitioners(limit=5)
        print(f"   Request returned: {len(caregivers)} caregivers")
        if caregivers:
            print("✅ Caregiver retrieval SUCCESS!")
            for c in caregivers:
                print(f"   - {c.full_name} (ID: {c.id}, Status: {c.status.value})")
        else:
            print("⚠️  No caregivers returned.")
    except Exception as e:
        print(f"❌ Caregiver retrieval FAILED: {e}")

    # 5. Test Data Retrieval (Shifts)
    print("\n5. TESTING SHIFT RETRIEVAL (FHIR Appointment API)")
    try:
        from datetime import date
        shifts = ws.search_appointments(start_date=date.today(), additional_days=1, limit=5)
        print(f"   Request returned: {len(shifts)} shifts")
        if shifts:
            print("✅ Shift retrieval SUCCESS!")
            for s in shifts:
                print(f"   - Shift {s.id}: {s.start_time}-{s.end_time}")
        else:
            print("⚠️  No shifts returned for today/tomorrow.")
    except Exception as e:
        print(f"❌ Shift retrieval FAILED: {e}")

    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    verify_connection()

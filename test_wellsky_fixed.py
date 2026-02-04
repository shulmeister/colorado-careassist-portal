#!/usr/bin/env python3
"""
Test WellSky API with trailing slash fix
Run this to verify the API is working with your credentials
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.wellsky_service import WellSkyService

print("=" * 70)
print("WellSky API Test - With Trailing Slash Fix")
print("=" * 70)

# Initialize service (uses hardcoded credentials from wellsky_service.py)
ws = WellSkyService()

print(f"\n✅ Service initialized")
print(f"   Environment: {ws.environment}")
print(f"   Base URL: {ws.base_url}")
print(f"   Agency ID: {ws.agency_id}")
print(f"   Configured: {ws.is_configured}")

# Test 1: Try to get practitioners (caregivers)
print(f"\n📞 Test 1: Fetching practitioners...")
try:
    # Search for first 5 practitioners
    from datetime import date

    success, result = ws._make_request(
        method="GET",
        endpoint="practitioners",  # Will become "practitioners/" after fix
        params={"agencyId": ws.agency_id, "_count": "5"}
    )

    if success:
        print(f"   ✅ SUCCESS! Got response from WellSky API")
        print(f"   Response type: {type(result)}")
        if isinstance(result, dict):
            print(f"   Keys: {list(result.keys())[:5]}")
        print(f"   Preview: {str(result)[:200]}...")
    else:
        print(f"   ❌ Failed: {result}")

except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 2: Try appointments endpoint
print(f"\n📅 Test 2: Fetching appointments...")
try:
    from datetime import date

    # Try to get today's appointments
    today = date.today().strftime("%Y%m%d")

    success, result = ws._make_request(
        method="GET",
        endpoint="appointment",  # Singular per API docs
        params={"startDate": today, "_count": "5"}
    )

    if success:
        print(f"   ✅ SUCCESS! Got appointments")
        print(f"   Response type: {type(result)}")
        if isinstance(result, dict):
            print(f"   Keys: {list(result.keys())[:5]}")
    else:
        print(f"   ❌ Failed: {result}")

except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 70)
print("Test Complete!")
print("=" * 70)
print("\nIf you see ✅ SUCCESS above, the WellSky API is working!")
print("If you see ❌ errors, check the error message for details.")

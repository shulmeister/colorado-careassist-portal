#!/usr/bin/env python3
"""Direct API test to verify BearerToken fix"""

import os
import sys

# Set env vars
os.environ["WELLSKY_CLIENT_ID"] = "[REDACTED_CLIENT_ID]"
os.environ["WELLSKY_CLIENT_SECRET"] = "[REDACTED_CLIENT_SECRET]"
os.environ["WELLSKY_AGENCY_ID"] = "4505"
os.environ["WELLSKY_ENVIRONMENT"] = "production"

# Force fresh import
if 'services.wellsky_service' in sys.modules:
    del sys.modules['services.wellsky_service']

from services.wellsky_service import WellSkyService

print("=" * 80)
print("DIRECT WELLSKY API TEST")
print("=" * 80)

ws = WellSkyService()
print(f"Environment: {ws.environment}")
print(f"Agency ID: {ws.agency_id}")
print(f"Configured: {ws.is_configured}")
print()

print("Testing practitioner search...")
caregivers = ws.search_practitioners(is_hired=True, active=True, limit=5)

if caregivers:
    print(f"✅ SUCCESS! Found {len(caregivers)} caregivers")
    for cg in caregivers[:3]:
        print(f"  - {cg.full_name} ({cg.phone})")
else:
    print("❌ FAILED - No caregivers found")
    print(f"Last error: {ws._last_error if hasattr(ws, '_last_error') else 'Unknown'}")

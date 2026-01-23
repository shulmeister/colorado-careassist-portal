#!/usr/bin/env python3
"""Test RingCentral integration and show status."""

import json
import os

print("=" * 60)
print("RINGCENTRAL STATUS CHECK")
print("=" * 60)

# Check env vars
print("\nEnvironment Variables:")
print(f"  RINGCENTRAL_CLIENT_ID: {'SET' if os.getenv('RINGCENTRAL_CLIENT_ID') else 'NOT SET'}")
print(f"  RINGCENTRAL_CLIENT_SECRET: {'SET' if os.getenv('RINGCENTRAL_CLIENT_SECRET') else 'NOT SET'}")
print(f"  RINGCENTRAL_JWT_TOKEN: {'SET' if os.getenv('RINGCENTRAL_JWT_TOKEN') else 'NOT SET'}")

try:
    from services.ringcentral_messaging_service import ringcentral_messaging_service

    status = ringcentral_messaging_service.get_status()
    print("\nAPI Status:")
    print(f"  Configured: {status.get('configured')}")
    print(f"  API Connected: {status.get('api_connected')}")

    if status.get('error'):
        print(f"  Error: {status.get('error')}")

    if status.get('teams_available'):
        print(f"\nTeams/Chats Available:")
        for team in status.get('teams_available', []):
            print(f"    - {team}")

    if status.get('call_queues'):
        print(f"\nCall Queues:")
        for q in status.get('call_queues', []):
            print(f"    - {q.get('name')} (ext {q.get('ext')})")

    # Test sending a direct message to Jason
    print("\n" + "=" * 60)
    print("TEST DIRECT MESSAGE TO JASON")
    print("=" * 60)

    result = ringcentral_messaging_service.notify_jason(
        "👋 Hi Jason! This is Gigi AI (ext 111). Just confirming my messaging is working. I'm ready to help with scheduling!"
    )
    print(f"Result: {json.dumps(result, indent=2)}")

except Exception as e:
    print(f"\nError: {e}")

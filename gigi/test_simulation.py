#!/usr/bin/env python3
"""Test Gigi by running a simulation via Retell API."""

import os
import requests
import json

RETELL_API_KEY = os.getenv('RETELL_API_KEY')
AGENT_ID = 'agent_d5c3f32bdf48fa4f7f24af7d36'

if not RETELL_API_KEY:
    print("ERROR: RETELL_API_KEY not set")
    exit(1)

print("=" * 60)
print("TESTING GIGI - CAREGIVER CALL-OUT SCENARIO")
print("=" * 60)

# Use the web call simulation endpoint
response = requests.post(
    'https://api.retellai.com/v2/create-web-call',
    headers={
        'Authorization': f'Bearer {RETELL_API_KEY}',
        'Content-Type': 'application/json'
    },
    json={
        'agent_id': AGENT_ID,
        'metadata': {
            'test': True,
            'scenario': 'caregiver_callout'
        }
    },
    timeout=30
)

print(f"\nCreate web call status: {response.status_code}")
if response.status_code in (200, 201):
    data = response.json()
    print(f"Call ID: {data.get('call_id')}")
    print(f"Access Token: {data.get('access_token', 'N/A')[:20]}...")
    print("\nWeb call created successfully!")
    print("To test interactively, use the Retell dashboard simulation.")
else:
    print(f"Error: {response.text[:500]}")

# Also check if we can list recent calls
print("\n" + "=" * 60)
print("RECENT CALLS")
print("=" * 60)

calls_response = requests.get(
    'https://api.retellai.com/v2/list-calls',
    headers={
        'Authorization': f'Bearer {RETELL_API_KEY}',
    },
    params={
        'agent_id': AGENT_ID,
        'limit': 5
    },
    timeout=30
)

if calls_response.status_code == 200:
    calls = calls_response.json()
    if calls:
        for call in calls[:5]:
            print(f"  - {call.get('call_id', 'N/A')[:20]}... | {call.get('start_timestamp', 'N/A')} | {call.get('call_status', 'N/A')}")
    else:
        print("  No recent calls found")
else:
    print(f"  Could not fetch calls: {calls_response.status_code}")

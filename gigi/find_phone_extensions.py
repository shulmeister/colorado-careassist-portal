#!/usr/bin/env python3
"""Find which extensions own 719-428-3999 and 303-757-1777"""

import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ringcentral_messaging_service import ringcentral_messaging_service, RINGCENTRAL_SERVER

token = ringcentral_messaging_service._get_access_token()
if not token:
    print("❌ Failed to get access token")
    sys.exit(1)

headers = {"Authorization": f"Bearer {token}"}

TARGET_NUMBERS = ["+17194283999", "+13037571777", "+13074598220"]

print("="*80)
print("FINDING EXTENSIONS FOR PHONE NUMBERS")
print("="*80)

# Get all account phone numbers
response = requests.get(
    f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/phone-number",
    headers=headers,
    params={"perPage": 1000}
)

if response.status_code == 200:
    all_numbers = response.json().get('records', [])
    print(f"\nTotal phone numbers in account: {len(all_numbers)}\n")

    for target in TARGET_NUMBERS:
        print(f"Searching for: {target}")
        found = False
        for num in all_numbers:
            if num.get('phoneNumber') == target:
                found = True
                ext_info = num.get('extension', {})
                print(f"  ✅ FOUND")
                print(f"     Extension Number: {ext_info.get('extensionNumber')}")
                print(f"     Extension ID: {ext_info.get('id')}")
                print(f"     Extension Name: {ext_info.get('name')}")
                print(f"     Usage Type: {num.get('usageType')}")
                print()
                break
        if not found:
            print(f"  ❌ NOT FOUND in account\n")
else:
    print(f"❌ API Error: {response.status_code}")
    print(response.text)

# Show current extension
print("="*80)
print("CURRENT JWT TOKEN EXTENSION")
print("="*80)
response = requests.get(
    f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~",
    headers=headers
)
if response.status_code == 200:
    ext = response.json()
    print(f"Extension ID: {ext.get('id')}")
    print(f"Extension Number: {ext.get('extensionNumber')}")
    print(f"Name: {ext.get('name')}")
    print(f"Status: {ext.get('status')}")

    # Get phone numbers for this extension
    response = requests.get(
        f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/~/phone-number",
        headers=headers
    )
    if response.status_code == 200:
        ext_numbers = response.json().get('records', [])
        print(f"\nPhone numbers assigned to this extension:")
        for num in ext_numbers:
            print(f"  - {num.get('phoneNumber')} ({num.get('usageType')})")
    print()

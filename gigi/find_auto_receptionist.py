#!/usr/bin/env python3
"""Find auto-receptionist/group extension IDs for 719-428-3999 and 303-757-1777"""

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
print("FINDING EXTENSIONS AND THEIR PHONE NUMBERS")
print("="*80)

# Get all extensions in the account
response = requests.get(
    f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension",
    headers=headers,
    params={"perPage": 1000}
)

if response.status_code == 200:
    extensions = response.json().get('records', [])
    print(f"\nTotal extensions in account: {len(extensions)}\n")

    # Map extension types
    for ext in extensions:
        ext_id = ext.get('id')
        ext_num = ext.get('extensionNumber')
        ext_name = ext.get('name')
        ext_type = ext.get('type')
        ext_status = ext.get('status')

        # Get phone numbers for this extension
        phone_response = requests.get(
            f"{RINGCENTRAL_SERVER}/restapi/v1.0/account/~/extension/{ext_id}/phone-number",
            headers=headers
        )

        phone_numbers = []
        if phone_response.status_code == 200:
            phone_records = phone_response.json().get('records', [])
            phone_numbers = [p.get('phoneNumber') for p in phone_records]

        # Check if this extension has any of our target numbers
        has_target = any(phone in TARGET_NUMBERS for phone in phone_numbers)

        if has_target or ext_type in ['Department', 'IvrMenu', 'ParkLocation']:
            print(f"Extension ID: {ext_id}")
            print(f"  Number: {ext_num}")
            print(f"  Name: {ext_name}")
            print(f"  Type: {ext_type}")
            print(f"  Status: {ext_status}")
            print(f"  Phone Numbers: {phone_numbers}")
            if has_target:
                print(f"  ⭐ HAS TARGET NUMBER!")
            print()
else:
    print(f"❌ API Error: {response.status_code}")
    print(response.text)

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
    print(f"Type: {ext.get('type')}")

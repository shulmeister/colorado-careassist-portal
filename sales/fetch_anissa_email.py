#!/usr/bin/env python3
"""
Fetch Anissa Loran's email from the GoFormz Employee Packet form.
"""

import os
import sys
import requests
from goformz_service import GoFormzService

def fetch_anissa_email():
    """Fetch Anissa's email from GoFormz form."""
    goformz = GoFormzService()
    
    if not goformz.enabled:
        print("ERROR: GoFormz not configured")
        return
    
    # Form ID from the webhook
    form_id = "ae2ad10e-0304-4e90-a6b5-db33e4c7df38"
    
    try:
        # Get access token
        token = goformz._get_access_token()
        if not token:
            print("ERROR: Failed to get GoFormz access token")
            return
        
        # Fetch form details from v2 API
        url = f"https://api.goformz.com/v2/formz/{form_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        
        print(f"Fetching form data from: {url}")
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"ERROR: {response.status_code} - {response.text}")
            return
        
        form_data = response.json()
        
        # Extract form data fields
        data_fields = form_data.get('data', {})
        
        # Look for EmpEmail
        emp_email = None
        emp_fn = None
        emp_ln = None
        
        # Helper to extract value from nested dict
        def extract_value(value):
            if isinstance(value, dict):
                return value.get('text') or value.get('Text') or value.get('value') or value.get('Value') or str(value)
            return str(value) if value else None
        
        for key, value in data_fields.items():
            if 'EmpEmail' in key or 'email' in key.lower():
                emp_email = extract_value(value)
            elif 'EmpFN' in key or ('first' in key.lower() and 'name' in key.lower()):
                emp_fn = extract_value(value)
            elif 'EmpLN' in key or ('last' in key.lower() and 'name' in key.lower()):
                emp_ln = extract_value(value)
        
        print(f"\nExtracted data:")
        print(f"  Email: {emp_email}")
        print(f"  First Name: {emp_fn}")
        print(f"  Last Name: {emp_ln}")
        
        if emp_email:
            print(f"\n✓ Found email: {emp_email}")
            print(f"  You can now add this contact to Brevo's Caregivers list manually")
        else:
            print("\n✗ Could not find email in form data")
            print("\nAvailable fields:")
            for key in sorted(data_fields.keys()):
                if 'email' in key.lower() or 'name' in key.lower():
                    print(f"  - {key}: {data_fields[key]}")
    
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fetch_anissa_email()


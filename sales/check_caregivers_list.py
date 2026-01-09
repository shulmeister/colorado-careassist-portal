#!/usr/bin/env python3
"""
Check if Anissa Loran is in Brevo's Caregivers list.
"""

import os
import sys
import requests
from brevo_service import BrevoService

def check_caregivers_list():
    """Check Caregivers list for Anissa Loran."""
    brevo = BrevoService()
    
    if not brevo.enabled:
        print("ERROR: Brevo not configured")
        return
    
    try:
        # Get all lists
        print("Getting Brevo lists...")
        lists_result = brevo.get_lists()
        
        if not lists_result.get('success'):
            print(f"ERROR: {lists_result.get('error')}")
            return
        
        # Find Caregivers list
        caregivers_list_id = None
        for lst in lists_result.get('lists', []):
            name_lower = lst['name'].lower()
            if 'caregiver' in name_lower or 'employee' in name_lower:
                caregivers_list_id = lst['id']
                print(f"Found '{lst['name']}' list (ID: {lst['id']})")
                break
        
        if not caregivers_list_id:
            print("ERROR: Could not find Caregivers or Employees list")
            return
        
        # Get contacts from the list
        print(f"\nFetching contacts from list ID {caregivers_list_id}...")
        all_contacts = []
        offset = 0
        limit = 50
        
        while True:
            response = requests.get(
                f"{brevo.base_url}/contacts/lists/{caregivers_list_id}/contacts",
                headers=brevo._get_headers(),
                params={"limit": limit, "offset": offset}
            )
            
            if response.status_code != 200:
                print(f"ERROR: {response.status_code} - {response.text}")
                break
            
            data = response.json()
            contacts = data.get('contacts', [])
            all_contacts.extend(contacts)
            
            if len(contacts) < limit:
                break
            
            offset += limit
        
        print(f"Total contacts in list: {len(all_contacts)}")
        
        # Search for Anissa Loran
        print("\nSearching for 'Anissa Loran'...")
        found = False
        for contact in all_contacts:
            email = contact.get('email', '').lower()
            first_name = contact.get('attributes', {}).get('FIRSTNAME', '').lower()
            last_name = contact.get('attributes', {}).get('LASTNAME', '').lower()
            full_name = f"{first_name} {last_name}".strip().lower()
            
            if 'anissa' in first_name or 'anissa' in full_name:
                print(f"\n✓ FOUND:")
                print(f"  Email: {email}")
                print(f"  First Name: {contact.get('attributes', {}).get('FIRSTNAME', 'N/A')}")
                print(f"  Last Name: {contact.get('attributes', {}).get('LASTNAME', 'N/A')}")
                print(f"  ID: {contact.get('id')}")
                found = True
        
        if not found:
            print("✗ Anissa Loran not found in Caregivers list")
            print("\nRecent contacts in list:")
            for contact in all_contacts[:10]:
                email = contact.get('email', 'N/A')
                first_name = contact.get('attributes', {}).get('FIRSTNAME', '')
                last_name = contact.get('attributes', {}).get('LASTNAME', '')
                print(f"  - {first_name} {last_name} ({email})")
    
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_caregivers_list()


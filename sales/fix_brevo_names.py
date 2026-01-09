#!/usr/bin/env python3
"""
Fix Brevo contacts where FIRSTNAME contains the full name instead of just first name.
Splits full names and updates both FIRSTNAME and LASTNAME fields.
"""

import os
import sys
from brevo_service import BrevoService
import time

def fix_brevo_names(dry_run=True, list_id=None):
    """
    Fix names in Brevo contacts.
    
    Args:
        dry_run: If True, only show what would be changed without making updates
        list_id: Optional list ID to fix only contacts in that list
    """
    brevo = BrevoService()
    
    if not brevo.enabled:
        print("ERROR: Brevo not configured. Set BREVO_API_KEY environment variable.")
        return
    
    print("=" * 60)
    print("FIXING BREVO CONTACT NAMES")
    print("=" * 60)
    print(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'LIVE (will update contacts)'}")
    print()
    
    try:
        # Get contacts
        if list_id:
            print(f"Fetching contacts from list ID {list_id}...")
            all_contacts = []
            offset = 0
            limit = 50
            
            while True:
                response = brevo._get_headers()
                import requests
                response = requests.get(
                    f"{brevo.base_url}/contacts/lists/{list_id}/contacts",
                    headers=brevo._get_headers(),
                    params={"limit": limit, "offset": offset}
                )
                
                if response.status_code != 200:
                    print(f"ERROR: Failed to get contacts: {response.status_code} - {response.text[:200]}")
                    return
                
                data = response.json()
                contacts = data.get('contacts', [])
                all_contacts.extend(contacts)
                
                if len(contacts) < limit:
                    break
                
                offset += limit
                time.sleep(0.2)
            
            print(f"Found {len(all_contacts)} contacts in list")
        else:
            print("Fetching all contacts from Brevo...")
            result = brevo.get_all_contacts(limit=10000)
            if not result.get('success'):
                print(f"ERROR: {result.get('error')}")
                return
            all_contacts = result.get('contacts', [])
            print(f"Found {len(all_contacts)} total contacts")
        
        print()
        
        # Find contacts with issues
        contacts_to_fix = []
        for contact in all_contacts:
            email = contact.get('email', '')
            attrs = contact.get('attributes', {})
            first_name = attrs.get('FIRSTNAME', '').strip()
            last_name = attrs.get('LASTNAME', '').strip()
            
            # Check if FIRSTNAME contains a space (full name)
            if first_name and ' ' in first_name and not last_name:
                contacts_to_fix.append({
                    'email': email,
                    'current_first': first_name,
                    'current_last': last_name,
                    'contact_id': contact.get('id')
                })
        
        if not contacts_to_fix:
            print("✅ No contacts found with name issues!")
            print("   All contacts have properly separated first and last names.")
            return
        
        print(f"Found {len(contacts_to_fix)} contacts with name issues:")
        print()
        
        # Show what will be fixed
        fixed_count = 0
        error_count = 0
        
        for i, contact_info in enumerate(contacts_to_fix, 1):
            email = contact_info['email']
            full_name = contact_info['current_first']
            parts = full_name.strip().split(' ', 1)
            new_first = parts[0]
            new_last = parts[1] if len(parts) > 1 else ''
            
            print(f"{i}. {email}")
            print(f"   Current: FIRSTNAME='{full_name}', LASTNAME='{contact_info['current_last']}'")
            print(f"   Fixed:   FIRSTNAME='{new_first}', LASTNAME='{new_last}'")
            
            if not dry_run:
                # Update the contact
                try:
                    import requests
                    data = {
                        "attributes": {
                            "FIRSTNAME": new_first,
                            "LASTNAME": new_last
                        }
                    }
                    
                    response = requests.put(
                        f"{brevo.base_url}/contacts/{email}",
                        headers=brevo._get_headers(),
                        json=data
                    )
                    
                    if response.status_code in (200, 201, 204):
                        fixed_count += 1
                        print(f"   ✅ Updated")
                    else:
                        error_count += 1
                        print(f"   ❌ Error: {response.status_code} - {response.text[:100]}")
                    
                    # Rate limiting
                    if i < len(contacts_to_fix):
                        time.sleep(0.1)
                        
                except Exception as e:
                    error_count += 1
                    print(f"   ❌ Exception: {str(e)}")
            else:
                print(f"   [DRY RUN - would update]")
            
            print()
        
        print("=" * 60)
        if dry_run:
            print(f"DRY RUN COMPLETE")
            print(f"   Found {len(contacts_to_fix)} contacts that need fixing")
            print()
            print("Run with --execute to apply these changes:")
            print("   python3 fix_brevo_names.py --execute")
        else:
            print(f"FIX COMPLETE")
            print(f"   Fixed: {fixed_count}")
            print(f"   Errors: {error_count}")
            print(f"   Total: {len(contacts_to_fix)}")
        print("=" * 60)
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix Brevo contact names")
    parser.add_argument("--execute", action="store_true", help="Actually update contacts (default is dry run)")
    parser.add_argument("--list-id", type=int, help="Only fix contacts in this list ID")
    
    args = parser.parse_args()
    
    fix_brevo_names(dry_run=not args.execute, list_id=args.list_id)


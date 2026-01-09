#!/usr/bin/env python3
"""
Clean up Brevo - delete all contacts and lists we created.
Keeps the API key and account intact.
"""

import requests
from brevo_service import BrevoService

def cleanup_brevo():
    brevo = BrevoService()
    
    if not brevo.enabled:
        print("ERROR: Brevo not configured")
        return
    
    print("=== BREVO CLEANUP ===\n")
    
    # Get all lists
    print("Getting lists...")
    lists_result = brevo.get_lists()
    
    if lists_result.get('success'):
        lists = lists_result.get('lists', [])
        print(f"Found {len(lists)} lists")
        
        for lst in lists:
            list_id = lst['id']
            list_name = lst['name']
            subscriber_count = lst.get('uniqueSubscribers', 0)
            
            print(f"\n  Deleting list '{list_name}' (ID: {list_id}, {subscriber_count} contacts)...")
            
            # Delete the list
            response = requests.delete(
                f"{brevo.base_url}/contacts/lists/{list_id}",
                headers=brevo._get_headers()
            )
            
            if response.status_code in (200, 204):
                print(f"    ✓ Deleted list '{list_name}'")
            else:
                print(f"    ✗ Failed: {response.status_code} - {response.text[:100]}")
    
    # Get and delete all contacts
    print("\n\nDeleting all contacts...")
    
    # Get contacts in batches and delete them
    offset = 0
    total_deleted = 0
    
    while True:
        response = requests.get(
            f"{brevo.base_url}/contacts",
            headers=brevo._get_headers(),
            params={"limit": 50, "offset": offset}
        )
        
        if response.status_code != 200:
            print(f"Error getting contacts: {response.status_code}")
            break
        
        data = response.json()
        contacts = data.get('contacts', [])
        
        if not contacts:
            break
        
        # Delete each contact
        for contact in contacts:
            email = contact.get('email')
            del_response = requests.delete(
                f"{brevo.base_url}/contacts/{email}",
                headers=brevo._get_headers()
            )
            
            if del_response.status_code in (200, 204):
                total_deleted += 1
            
        print(f"  Deleted batch... (total: {total_deleted})")
        
        # Don't increment offset since we're deleting
        if len(contacts) < 50:
            break
    
    print(f"\n✅ CLEANUP COMPLETE")
    print(f"   Deleted {total_deleted} contacts")
    print(f"   API key is still configured")
    print(f"\n   You can now use Brevo's native Mailchimp integration!")


if __name__ == "__main__":
    cleanup_brevo()


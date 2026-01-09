#!/usr/bin/env python3
"""Create Brevo lists for contact organization."""

from brevo_service import BrevoService

def setup_lists():
    brevo = BrevoService()
    
    if not brevo.enabled:
        print("ERROR: Brevo not configured")
        return
    
    # Create main list for all contacts
    print("Creating 'All Contacts' list...")
    result = brevo.create_list("All Contacts")
    print(f"  Result: {result}")
    
    # Get all lists to confirm
    print("\nAll lists in Brevo:")
    lists = brevo.get_lists()
    if lists.get('success'):
        for lst in lists.get('lists', []):
            print(f"  - ID {lst['id']}: {lst['name']} ({lst.get('uniqueSubscribers', 0)} contacts)")
    
    return lists

if __name__ == "__main__":
    setup_lists()


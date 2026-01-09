#!/usr/bin/env python3
"""
Remove Gmail addresses from the Referral Source list in Brevo.
This script identifies contacts with Gmail addresses and removes them from the list.
"""

import sys
import requests
from brevo_service import BrevoService
import re

def is_gmail_address(email: str) -> bool:
    """Check if an email address is a Gmail address."""
    if not email:
        return False
    email = email.strip().lower()
    # Check for @gmail.com domain
    return email.endswith('@gmail.com') or email.endswith('@googlemail.com')

def find_referral_source_list(brevo: BrevoService) -> dict:
    """Find the referral source list."""
    lists_result = brevo.get_lists()
    if not lists_result.get('success'):
        print(f"ERROR: Failed to get lists: {lists_result.get('error')}")
        return None
    
    lists = lists_result.get('lists', [])
    
    # Look for referral source list
    referral_lists = [
        lst for lst in lists 
        if 'referral' in lst.get('name', '').lower() or 'referral source' in lst.get('name', '').lower()
    ]
    
    if not referral_lists:
        print("ERROR: No referral source list found")
        print(f"Available lists: {[lst.get('name') for lst in lists]}")
        return None
    
    # If multiple, use the one with "Referral Source" in the name or the first one
    target_list = None
    for lst in referral_lists:
        if 'referral source' in lst.get('name', '').lower():
            target_list = lst
            break
    
    if not target_list:
        target_list = referral_lists[0]
    
    return target_list

def get_contacts_from_list(brevo: BrevoService, list_id: int) -> list:
    """Get all contacts from a list."""
    all_contacts = []
    offset = 0
    limit_per_request = 50
    
    while True:
        response = requests.get(
            f"{brevo.base_url}/contacts/lists/{list_id}/contacts",
            headers=brevo._get_headers(),
            params={"limit": limit_per_request, "offset": offset}
        )
        
        if response.status_code != 200:
            print(f"ERROR: Failed to get contacts: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        contacts_batch = data.get('contacts', [])
        all_contacts.extend(contacts_batch)
        
        if len(contacts_batch) < limit_per_request:
            break
        
        offset += limit_per_request
    
    return all_contacts

def remove_contacts_from_list(brevo: BrevoService, list_id: int, emails: list) -> dict:
    """Remove contacts from a list by email addresses."""
    if not emails:
        return {"success": True, "removed": 0}
    
    # Brevo API allows removing contacts from list in batches
    batch_size = 50
    total_removed = 0
    errors = []
    
    for i in range(0, len(emails), batch_size):
        batch = emails[i:i+batch_size]
        
        response = requests.post(
            f"{brevo.base_url}/contacts/lists/{list_id}/contacts/remove",
            headers=brevo._get_headers(),
            json={"emails": batch}
        )
        
        if response.status_code in (200, 201, 204):
            total_removed += len(batch)
            print(f"  Removed batch {i//batch_size + 1}: {len(batch)} contacts")
        else:
            error_msg = f"Batch {i//batch_size + 1}: {response.status_code} - {response.text[:200]}"
            errors.append(error_msg)
            print(f"  ERROR: {error_msg}")
    
    return {
        "success": len(errors) == 0,
        "removed": total_removed,
        "errors": errors if errors else None
    }

def get_or_create_archive_list(brevo: BrevoService, list_name: str = "Archived Gmail Referrals") -> dict:
    """Get or create an archive list for Gmail addresses."""
    lists_result = brevo.get_lists()
    if not lists_result.get('success'):
        return None
    
    lists = lists_result.get('lists', [])
    
    # Look for existing archive list
    archive_list = next((lst for lst in lists if lst.get('name') == list_name), None)
    
    if archive_list:
        return archive_list
    
    # Create new archive list
    create_result = brevo.create_list(list_name)
    if create_result.get('success'):
        # Fetch the newly created list
        lists_result = brevo.get_lists()
        if lists_result.get('success'):
            lists = lists_result.get('lists', [])
            return next((lst for lst in lists if lst.get('name') == list_name), None)
    
    return None

def cleanup_gmail_referrals(dry_run=True, list_id=None):
    """Remove Gmail addresses from referral source list and archive them."""
    brevo = BrevoService()
    
    if not brevo.enabled:
        print("ERROR: Brevo not configured")
        return
    
    print("=== CLEANUP GMAIL FROM REFERRAL SOURCE LIST ===\n")
    
    # Find the referral source list
    if list_id:
        # Use provided list ID
        lists_result = brevo.get_lists()
        if lists_result.get('success'):
            lists = lists_result.get('lists', [])
            target_list = next((lst for lst in lists if lst.get('id') == list_id), None)
            if not target_list:
                print(f"ERROR: List ID {list_id} not found")
                return
        else:
            print(f"ERROR: Failed to get lists: {lists_result.get('error')}")
            return
    else:
        target_list = find_referral_source_list(brevo)
        if not target_list:
            return
    
    list_id = target_list.get('id')
    list_name = target_list.get('name')
    print(f"Target List: {list_name} (ID: {list_id})")
    print(f"Current contacts: {target_list.get('uniqueSubscribers', 0)}\n")
    
    # Get all contacts from the list
    print("Fetching contacts from list...")
    contacts = get_contacts_from_list(brevo, list_id)
    print(f"Found {len(contacts)} contacts in list\n")
    
    # Filter for Gmail addresses
    gmail_contacts = []
    for contact in contacts:
        email = contact.get('email', '').strip()
        if is_gmail_address(email):
            gmail_contacts.append(contact)
    
    print(f"Found {len(gmail_contacts)} contacts with Gmail addresses\n")
    
    if not gmail_contacts:
        print("✅ No Gmail addresses found in referral source list!")
        return
    
    # Show preview
    print("Gmail addresses to remove:")
    print("-" * 60)
    for i, contact in enumerate(gmail_contacts[:20], 1):  # Show first 20
        email = contact.get('email', '')
        name = contact.get('attributes', {}).get('FIRSTNAME', '') or contact.get('attributes', {}).get('LASTNAME', '') or email
        print(f"{i}. {name} ({email})")
    if len(gmail_contacts) > 20:
        print(f"... and {len(gmail_contacts) - 20} more")
    print("-" * 60)
    print(f"\nTotal Gmail addresses: {len(gmail_contacts)}")
    
    if dry_run:
        print("\n🔍 DRY RUN MODE - No changes made")
        print("Run with --execute to actually remove these contacts from the list")
        return
    
    # Get or create archive list
    archive_list = get_or_create_archive_list(brevo)
    if not archive_list:
        print("\nERROR: Failed to get or create archive list")
        return
    
    archive_list_id = archive_list.get('id')
    archive_list_name = archive_list.get('name')
    print(f"\nArchive List: {archive_list_name} (ID: {archive_list_id})")
    
    # Confirm
    print(f"\n⚠️  WARNING: This will:")
    print(f"   1. Remove {len(gmail_contacts)} Gmail contacts from '{list_name}'")
    print(f"   2. Add them to '{archive_list_name}' for archival")
    print("   Contacts will NOT be deleted from Brevo entirely.")
    
    # Check for --yes flag to skip confirmation
    auto_confirm = "--yes" in sys.argv
    if not auto_confirm:
        confirm = input("Type 'yes' to continue: ")
        if confirm.lower() != 'yes':
            print("Cancelled.")
            return
    
    # Remove Gmail contacts from referral source list
    print(f"\nRemoving {len(gmail_contacts)} Gmail contacts from '{list_name}'...")
    gmail_emails = [c.get('email') for c in gmail_contacts]
    
    remove_result = remove_contacts_from_list(brevo, list_id, gmail_emails)
    
    # Add Gmail contacts to archive list
    print(f"\nAdding {len(gmail_contacts)} Gmail contacts to '{archive_list_name}'...")
    
    # Use the add contacts function (similar to what's in tag_brevo_contacts.py)
    batch_size = 50
    total_added = 0
    errors = []
    
    for i in range(0, len(gmail_emails), batch_size):
        batch = gmail_emails[i:i+batch_size]
        
        response = requests.post(
            f"{brevo.base_url}/contacts/lists/{archive_list_id}/contacts/add",
            headers=brevo._get_headers(),
            json={"emails": batch}
        )
        
        if response.status_code in (200, 201, 204):
            total_added += len(batch)
            print(f"  Added batch {i//batch_size + 1}: {len(batch)} contacts")
        else:
            error_msg = f"Batch {i//batch_size + 1}: {response.status_code} - {response.text[:200]}"
            errors.append(error_msg)
            print(f"  ERROR: {error_msg}")
    
    # Summary
    print(f"\n✅ CLEANUP COMPLETE!")
    print(f"   Removed from '{list_name}': {remove_result.get('removed', 0)} contacts")
    print(f"   Added to '{archive_list_name}': {total_added} contacts")
    
    if remove_result.get('errors') or errors:
        print(f"\n⚠️  Completed with some errors")
        if remove_result.get('errors'):
            for error in remove_result.get('errors'):
                print(f"     - Remove error: {error}")
        if errors:
            for error in errors:
                print(f"     - Archive error: {error}")

if __name__ == "__main__":
    dry_run = "--execute" not in sys.argv
    list_id = None
    
    # Check for list ID argument
    if "--list-id" in sys.argv:
        idx = sys.argv.index("--list-id")
        if idx + 1 < len(sys.argv):
            try:
                list_id = int(sys.argv[idx + 1])
            except ValueError:
                print("ERROR: --list-id must be a number")
                sys.exit(1)
    
    # Import sys at the top if not already imported (it is, so this is fine)
    cleanup_gmail_referrals(dry_run=dry_run, list_id=list_id)


#!/usr/bin/env python3
"""
Sync customers from QuickBooks to Brevo Client list.
This triggers the Brevo automation for new customers.
"""

import sys
import os
import requests
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db_manager
from models import Contact
from brevo_service import BrevoService
from quickbooks_service import QuickBooksService
import time

def sync_qb_customers_to_brevo():
    """Sync QuickBooks customers to Brevo Client list."""
    print("="*60)
    print("SYNCING QUICKBOOKS CUSTOMERS → BREVO CLIENT LIST")
    print("="*60)
    
    qb = QuickBooksService()
    brevo = BrevoService()
    
    if not qb.enabled:
        print("ERROR: QuickBooks not configured")
        print("Set QUICKBOOKS_CLIENT_ID, QUICKBOOKS_CLIENT_SECRET, QUICKBOOKS_REALM_ID, QUICKBOOKS_ACCESS_TOKEN")
        return
    
    if not brevo.enabled:
        print("ERROR: Brevo not configured")
        return
    
    # Test connections
    print("\nTesting connections...")
    qb_test = qb.test_connection()
    if not qb_test.get('success'):
        print(f"ERROR: QuickBooks connection failed: {qb_test.get('error')}")
        return
    print(f"✓ Connected to QuickBooks: {qb_test.get('company_name')}")
    
    brevo_test = brevo.test_connection()
    if not brevo_test.get('success'):
        print(f"ERROR: Brevo connection failed: {brevo_test.get('error')}")
        return
    print(f"✓ Connected to Brevo: {brevo_test.get('message')}")
    
    # Get Client list ID
    lists_result = brevo.get_lists()
    if not lists_result.get('success'):
        print(f"ERROR: Failed to get Brevo lists: {lists_result.get('error')}")
        return
    
    client_list_id = None
    for lst in lists_result.get('lists', []):
        name = lst.get('name', '').lower()
        if 'client' in name and 'referral' not in name:
            client_list_id = lst.get('id')
            print(f"\n✓ Found Client list: ID {client_list_id} ({lst.get('name')})")
            break
    
    if not client_list_id:
        print("ERROR: Could not find Client list in Brevo")
        return
    
    # Get customers from QuickBooks
    print("\nFetching customers from QuickBooks...")
    customers_result = qb.get_customers(limit=1000)
    if not customers_result.get('success'):
        print(f"ERROR: Failed to get customers: {customers_result.get('error')}")
        return
    
    qb_customers = customers_result.get('customers', [])
    print(f"Found {len(qb_customers)} customers in QuickBooks")
    
    if not qb_customers:
        print("No customers to sync")
        return
    
    # Get existing contacts from Brevo Client list to check for duplicates
    print("\nChecking existing contacts in Brevo Client list...")
    existing_brevo_contacts = set()
    offset = 0
    while True:
        response = requests.get(
            f"{brevo.base_url}/contacts/lists/{client_list_id}/contacts",
            headers=brevo._get_headers(),
            params={"limit": 50, "offset": offset}
        )
        if response.status_code != 200:
            break
        data = response.json()
        contacts_page = data.get('contacts', [])
        for contact in contacts_page:
            email = contact.get('email', '').strip().lower()
            if email:
                existing_brevo_contacts.add(email)
        if len(contacts_page) < 50:
            break
        offset += 50
    
    print(f"Found {len(existing_brevo_contacts)} existing contacts in Brevo Client list")
    
    # Process each QuickBooks customer
    added = 0
    updated = 0
    skipped = 0
    errors = 0
    
    print(f"\nSyncing {len(qb_customers)} customers...")
    
    for customer in qb_customers:
        try:
            # Normalize customer data
            contact_data = qb.normalize_customer_data(customer)
            email = contact_data.get('email', '').strip().lower()
            
            if not email:
                skipped += 1
                if skipped <= 5:
                    print(f"  Skipped: {contact_data.get('name')} (no email)")
                continue
            
            # Check if already in Brevo Client list
            is_new = email not in existing_brevo_contacts
            
            # Add/update contact in Brevo
            result = brevo.add_contact(contact_data)
            
            if result.get('success'):
                # Add to Client list if not already there
                if is_new:
                    # Add to Client list
                    list_response = requests.post(
                        f"{brevo.base_url}/contacts/lists/{client_list_id}/contacts/add",
                        headers=brevo._get_headers(),
                        json={"emails": [email]}
                    )
                    
                    if list_response.status_code in (200, 201, 204):
                        added += 1
                        if added <= 10:
                            print(f"  ✓ Added: {contact_data.get('name')} ({email})")
                    else:
                        # Contact added but failed to add to list
                        updated += 1
                        if updated <= 5:
                            print(f"  ⚠ Added contact but failed to add to list: {email}")
                else:
                    updated += 1
                    if updated <= 10:
                        print(f"  Updated: {contact_data.get('name')} ({email})")
            else:
                errors += 1
                if errors <= 5:
                    print(f"  ✗ Error: {contact_data.get('name')}: {result.get('error', 'Unknown')}")
            
            # Rate limiting
            if (added + updated + errors) % 50 == 0:
                time.sleep(1)
                
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ✗ Exception: {str(e)}")
    
    print("\n" + "="*60)
    print("SYNC COMPLETE")
    print("="*60)
    print(f"Added to Client list: {added}")
    print(f"Updated: {updated}")
    print(f"Skipped (no email): {skipped}")
    print(f"Errors: {errors}")
    print(f"\n✓ New customers added to Brevo Client list will trigger welcome automation")
    
    return added, updated, skipped, errors


def main():
    try:
        added, updated, skipped, errors = sync_qb_customers_to_brevo()
    except KeyboardInterrupt:
        print("\n\nSync interrupted by user")
    except Exception as e:
        print(f"\n\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


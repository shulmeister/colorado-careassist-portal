#!/usr/bin/env python3
"""
Sync completed Client Packets from GoFormz to Brevo Client list.
This triggers the Brevo welcome automation for new customers.
"""

import sys
import os
import requests
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brevo_service import BrevoService
from goformz_service import GoFormzService
import time

def sync_goformz_client_packets_to_brevo(since_hours: int = 24):
    """Sync completed Client Packets from GoFormz to Brevo Client list."""
    print("="*60)
    print("SYNCING GOFORMZ CLIENT PACKETS → BREVO CLIENT LIST")
    print("="*60)
    
    goformz = GoFormzService()
    brevo = BrevoService()
    
    if not goformz.enabled:
        print("ERROR: GoFormz not configured")
        print("Set GOFORMZ_CLIENT_ID and GOFORMZ_CLIENT_SECRET")
        return
    
    if not brevo.enabled:
        print("ERROR: Brevo not configured")
        return
    
    # Test connections
    print("\nTesting connections...")
    goformz_test = goformz.test_connection()
    if not goformz_test.get('success'):
        print(f"ERROR: GoFormz connection failed: {goformz_test.get('error')}")
        return
    print(f"✓ Connected to GoFormz")
    
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
    
    # Get completed Client Packets since specified time
    since = datetime.now() - timedelta(hours=since_hours)
    print(f"\nFetching completed Client Packets since {since.strftime('%Y-%m-%d %H:%M')}...")
    
    packets_result = goformz.get_completed_client_packets(since=since)
    if not packets_result.get('success'):
        print(f"ERROR: Failed to get Client Packets: {packets_result.get('error')}")
        return
    
    submissions = packets_result.get('submissions', [])
    print(f"Found {len(submissions)} completed Client Packets")
    
    if not submissions:
        print("No new completed Client Packets to sync")
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
    
    # Process each completed Client Packet
    added = 0
    updated = 0
    skipped = 0
    errors = 0
    
    print(f"\nProcessing {len(submissions)} Client Packets...")
    
    for submission in submissions:
        try:
            # Extract customer data from submission
            contact_data = goformz.extract_customer_data_from_submission(submission)
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
    import argparse
    parser = argparse.ArgumentParser(description="Sync GoFormz Client Packets to Brevo")
    parser.add_argument("--since-hours", type=int, default=24, help="Hours to look back for completed packets (default: 24)")
    args = parser.parse_args()
    
    try:
        added, updated, skipped, errors = sync_goformz_client_packets_to_brevo(since_hours=args.since_hours)
    except KeyboardInterrupt:
        print("\n\nSync interrupted by user")
    except Exception as e:
        print(f"\n\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


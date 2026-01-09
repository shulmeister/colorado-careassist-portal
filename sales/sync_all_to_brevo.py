#!/usr/bin/env python3
"""
Sync ALL dashboard contacts to Brevo, organized into Referral Source and Client lists.
"""

import sys
from database import db_manager
from models import Contact
from brevo_service import BrevoService
import requests

def sync_all_to_brevo():
    """Sync all dashboard contacts to Brevo lists."""
    db = db_manager.SessionLocal()
    brevo = BrevoService()
    
    if not brevo.enabled:
        print("ERROR: Brevo not configured")
        return
    
    try:
        # Get list IDs from Brevo
        print("Getting Brevo lists...")
        lists_result = brevo.get_lists()
        
        referral_list_id = None
        client_list_id = None
        
        if lists_result.get('success'):
            for lst in lists_result.get('lists', []):
                name = lst['name'].lower()
                if 'referral' in name:
                    referral_list_id = lst['id']
                    print(f"  Found Referral list: ID {lst['id']}")
                elif 'client' in name:
                    client_list_id = lst['id']
                    print(f"  Found Client list: ID {lst['id']}")
        
        if not referral_list_id or not client_list_id:
            print("ERROR: Could not find both Referral and Client lists in Brevo")
            print("Please create them first in Brevo")
            return
        
        # Get ALL contacts from dashboard
        print("\nFetching all contacts from dashboard...")
        all_contacts = db.query(Contact).filter(
            Contact.email.isnot(None),
            Contact.email != ''
        ).all()
        
        print(f"Total contacts with email: {len(all_contacts)}")
        
        # Categorize contacts
        referral_contacts = []
        client_contacts = []
        other_contacts = []
        
        for c in all_contacts:
            email = (c.email or '').strip().lower()
            if len(email) < 5 or '@' not in email:
                continue
            
            # Get first/last name - properly split if needed
            first_name = c.first_name or ''
            last_name = c.last_name or ''
            
            # If first_name contains a space, it's likely a full name - split it
            if first_name and ' ' in first_name.strip():
                parts = first_name.strip().split(' ', 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else (last_name or '')
            # If no first_name but we have name, split name
            elif not first_name and c.name:
                parts = c.name.strip().split(' ', 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else (last_name or '')
            
            # If still no name, use email prefix
            if not first_name:
                first_name = email.split('@')[0]
            
            contact_data = {
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'company': c.company or '',
                'phone': c.phone or '',
                'title': c.title or '',
                'contact_type': c.contact_type or '',
                'status': c.status or '',
                'source': c.source or 'dashboard'
            }
            
            contact_type = (c.contact_type or '').lower()
            
            if contact_type == 'referral':
                referral_contacts.append(contact_data)
            elif contact_type == 'client':
                client_contacts.append(contact_data)
            else:
                # Default to referral for business/professional contacts
                # Default to client for personal-looking emails
                if c.company or '@' in email and any(domain in email for domain in ['.org', '.health', '.com', '.net']):
                    # Has company or professional domain - likely referral
                    referral_contacts.append(contact_data)
                else:
                    # Personal email without company - might be client
                    # But for safety, put in referral
                    referral_contacts.append(contact_data)
        
        print(f"\n=== CONTACT BREAKDOWN ===")
        print(f"Referral Source: {len(referral_contacts)}")
        print(f"Client: {len(client_contacts)}")
        
        # Import to Brevo
        print(f"\n=== IMPORTING TO BREVO ===")
        
        if referral_contacts:
            print(f"\nPushing {len(referral_contacts)} contacts to Referral Source list (ID: {referral_list_id})...")
            result = brevo.bulk_import_contacts(referral_contacts, list_id=referral_list_id)
            if result.get('success'):
                print(f"  ✓ Success: {result.get('added', len(referral_contacts))} contacts imported")
            else:
                print(f"  ✗ Error: {result.get('error')}")
                if result.get('errors'):
                    for err in result['errors'][:3]:
                        print(f"    - {err}")
        
        if client_contacts:
            print(f"\nPushing {len(client_contacts)} contacts to Client list (ID: {client_list_id})...")
            result = brevo.bulk_import_contacts(client_contacts, list_id=client_list_id)
            if result.get('success'):
                print(f"  ✓ Success: {result.get('added', len(client_contacts))} contacts imported")
            else:
                print(f"  ✗ Error: {result.get('error')}")
                if result.get('errors'):
                    for err in result['errors'][:3]:
                        print(f"    - {err}")
        
        print(f"\n✅ SYNC COMPLETE")
        print(f"   Total pushed: {len(referral_contacts) + len(client_contacts)}")
        print(f"   Referral Source list: {len(referral_contacts)}")
        print(f"   Client list: {len(client_contacts)}")
        
    finally:
        db.close()


if __name__ == "__main__":
    sync_all_to_brevo()


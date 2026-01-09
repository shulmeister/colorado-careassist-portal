#!/usr/bin/env python3
"""
Tag Brevo contacts by adding them to appropriate lists based on contact_type.
"""

import sys
from database import db_manager
from models import Contact
from brevo_service import BrevoService
import requests

def tag_contacts(dry_run=True):
    """Add contacts to appropriate lists based on their contact_type."""
    db = db_manager.SessionLocal()
    brevo = BrevoService()
    
    if not brevo.enabled:
        print("ERROR: Brevo not configured")
        return
    
    try:
        # First, create the lists we need
        print("Setting up lists...")
        
        lists_result = brevo.get_lists()
        existing_lists = {lst['name']: lst['id'] for lst in lists_result.get('lists', [])}
        
        # Create lists if they don't exist
        needed_lists = {
            'Referral Sources': None,
            'Clients': None,
            'Hot Leads': None,
            'Prospects': None
        }
        
        for list_name in needed_lists:
            if list_name in existing_lists:
                needed_lists[list_name] = existing_lists[list_name]
                print(f"  ✓ '{list_name}' exists (ID: {existing_lists[list_name]})")
            else:
                result = brevo.create_list(list_name)
                if result.get('success'):
                    needed_lists[list_name] = result.get('list_id')
                    print(f"  ✓ Created '{list_name}' (ID: {result.get('list_id')})")
                else:
                    print(f"  ✗ Failed to create '{list_name}': {result.get('error')}")
        
        # Get contacts from database with their types
        contacts = db.query(Contact).filter(
            Contact.email.isnot(None),
            Contact.email != ''
        ).all()
        
        # Categorize contacts
        referrals = []
        clients = []
        hot_leads = []
        prospects = []
        
        for c in contacts:
            email = c.email.lower().strip()
            contact_type = (c.contact_type or '').lower()
            status = (c.status or '').lower()
            
            if contact_type == 'referral':
                referrals.append(email)
            elif contact_type == 'client':
                clients.append(email)
            elif contact_type == 'prospect':
                prospects.append(email)
            
            if status == 'hot':
                hot_leads.append(email)
        
        print(f"\n=== CONTACT BREAKDOWN ===")
        print(f"Referral Sources: {len(referrals)}")
        print(f"Clients: {len(clients)}")
        print(f"Hot Leads: {len(hot_leads)}")
        print(f"Prospects: {len(prospects)}")
        
        if dry_run:
            print("\n[DRY RUN - No changes made]")
            print("\nSample Referrals:", referrals[:5])
            print("Sample Clients:", clients[:5])
            print("Sample Hot Leads:", hot_leads[:5])
            print("\nRun with --execute to add contacts to lists")
            return
        
        # Add contacts to their respective lists
        def add_emails_to_list(emails, list_id, list_name):
            if not emails or not list_id:
                return
            
            print(f"\nAdding {len(emails)} contacts to '{list_name}'...")
            
            # Brevo allows adding contacts to lists by email
            # Use the contacts/lists endpoint
            batch_size = 50
            success = 0
            
            for i in range(0, len(emails), batch_size):
                batch = emails[i:i+batch_size]
                
                response = requests.post(
                    f"{brevo.base_url}/contacts/lists/{list_id}/contacts/add",
                    headers=brevo._get_headers(),
                    json={"emails": batch}
                )
                
                if response.status_code in (200, 201, 204):
                    success += len(batch)
                else:
                    print(f"  Batch error: {response.status_code} - {response.text[:100]}")
            
            print(f"  ✓ Added {success}/{len(emails)} to '{list_name}'")
        
        add_emails_to_list(referrals, needed_lists.get('Referral Sources'), 'Referral Sources')
        add_emails_to_list(clients, needed_lists.get('Clients'), 'Clients')
        add_emails_to_list(hot_leads, needed_lists.get('Hot Leads'), 'Hot Leads')
        add_emails_to_list(prospects, needed_lists.get('Prospects'), 'Prospects')
        
        print("\n✅ Done! Check Brevo for updated lists.")
        
    finally:
        db.close()


if __name__ == "__main__":
    dry_run = "--execute" not in sys.argv
    tag_contacts(dry_run=dry_run)


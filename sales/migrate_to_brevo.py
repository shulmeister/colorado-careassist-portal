#!/usr/bin/env python3
"""
Migrate contacts from Dashboard to Brevo.
Only migrates contacts that have good data (name, email, preferably company).
"""

import sys
from database import db_manager
from models import Contact
from brevo_service import BrevoService

def migrate_to_brevo(dry_run=True):
    """Migrate good contacts to Brevo."""
    db = db_manager.SessionLocal()
    brevo = BrevoService()
    
    if not brevo.enabled:
        print("ERROR: Brevo not configured")
        return
    
    try:
        # Get all contacts with email
        all_contacts = db.query(Contact).filter(
            Contact.email.isnot(None),
            Contact.email != ''
        ).all()
        
        print(f"Total contacts with email: {len(all_contacts)}")
        
        # Filter for quality contacts
        # Priority 1: Has contact_type (referral/client) - these are tagged properly
        # Priority 2: Has company name - business contacts
        # Priority 3: Has real name (not just email prefix)
        
        priority_1 = []  # Referral/Client - definitely sync
        priority_2 = []  # Has company - likely sync
        priority_3 = []  # Has name only - maybe sync
        skip = []        # No useful data - skip
        
        for c in all_contacts:
            email = c.email.lower().strip()
            name = (c.name or '').strip()
            company = (c.company or '').strip()
            contact_type = (c.contact_type or '').strip()
            
            # Skip garbage
            if len(email) < 5 or '@' not in email:
                skip.append(c)
                continue
            
            # Check if name is just email prefix (garbage)
            email_prefix = email.split('@')[0].lower()
            name_is_email = name.lower().replace(' ', '') == email_prefix
            
            if contact_type in ('referral', 'client'):
                priority_1.append(c)
            elif company and len(company) > 2:
                priority_2.append(c)
            elif name and len(name) > 3 and not name_is_email:
                priority_3.append(c)
            else:
                skip.append(c)
        
        print(f"\n=== CONTACT BREAKDOWN ===")
        print(f"Priority 1 (Referral/Client): {len(priority_1)} - WILL SYNC")
        print(f"Priority 2 (Has Company): {len(priority_2)} - WILL SYNC")
        print(f"Priority 3 (Has Name only): {len(priority_3)} - REVIEW")
        print(f"Skip (No useful data): {len(skip)}")
        
        # Contacts to sync = Priority 1 + Priority 2
        to_sync = priority_1 + priority_2
        
        print(f"\n=== SYNCING {len(to_sync)} CONTACTS ===")
        
        if dry_run:
            print("\n[DRY RUN - No changes made]")
            print("\nSample contacts to sync:")
            for c in to_sync[:20]:
                print(f"  • {c.name or 'N/A'} | {c.email} | {c.company or 'N/A'} | {c.contact_type or 'N/A'}")
            if len(to_sync) > 20:
                print(f"  ... and {len(to_sync) - 20} more")
            
            print("\nSample Priority 3 (review):")
            for c in priority_3[:10]:
                print(f"  • {c.name or 'N/A'} | {c.email} | source={c.source or 'N/A'}")
            
            print("\nSample skipped:")
            for c in skip[:10]:
                print(f"  • {c.email} | name='{c.name}' | company='{c.company}'")
            
            print(f"\nRun with --execute to sync {len(to_sync)} contacts to Brevo")
            return
        
        # Build contact list for bulk import
        contacts_for_brevo = []
        for c in to_sync:
            # Get first/last name
            first_name = c.first_name
            last_name = c.last_name
            if not first_name and c.name:
                parts = c.name.split(' ', 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ''
            
            contacts_for_brevo.append({
                'email': c.email.lower().strip(),
                'first_name': first_name or '',
                'last_name': last_name or '',
                'company': c.company or '',
                'phone': c.phone or '',
                'title': c.title or '',
                'contact_type': c.contact_type or '',
                'status': c.status or '',
                'source': c.source or 'dashboard'
            })
        
        # First, ensure we have a list to import to
        lists_result = brevo.get_lists()
        list_id = None
        if lists_result.get('success'):
            for lst in lists_result.get('lists', []):
                if lst['name'] == 'All Contacts':
                    list_id = lst['id']
                    break
        
        if not list_id:
            print("Creating 'All Contacts' list...")
            create_result = brevo.create_list("All Contacts")
            if create_result.get('success'):
                list_id = create_result.get('list_id')
            else:
                print(f"Failed to create list: {create_result}")
                return
        
        print(f"\nImporting {len(contacts_for_brevo)} contacts to Brevo (list ID: {list_id})...")
        result = brevo.bulk_import_contacts(contacts_for_brevo, list_id=list_id)
        
        if result.get('success'):
            print(f"✅ SUCCESS: Imported {result.get('added', 0)} contacts to Brevo")
        else:
            print(f"❌ ERROR: {result.get('error')}")
            if result.get('errors'):
                for err in result['errors'][:5]:
                    print(f"  - {err}")
        
    finally:
        db.close()


if __name__ == "__main__":
    dry_run = "--execute" not in sys.argv
    migrate_to_brevo(dry_run=dry_run)


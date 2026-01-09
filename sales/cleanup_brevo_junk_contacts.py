#!/usr/bin/env python3
"""
Clean up junk contacts in Brevo that shouldn't be in a CRM system.
Identifies and removes/archives system emails, no-reply addresses, and other unwanted contacts.
"""

import os
import sys
import re
from typing import Tuple
from brevo_service import BrevoService
import time

# Patterns that indicate unwanted contacts
UNWANTED_EMAIL_PATTERNS = [
    r'no[-_]?reply',
    r'noreply',
    r'do[-_]?not[-_]?reply',
    r'donotreply',
    r'no[-_]?response',
    r'automated',
    r'notification',
    r'notifications',
    r'system',
    r'admin',
    r'support@',
    r'info@',
    r'hello@',
    r'contact@',
    r'sales@',
    r'marketing@',
    r'newsletter',
    r'unsubscribe',
    r'bounce',
    r'postmaster',
    r'mailer[-_]?daemon',
    r'daemon',
    r'robot',
    r'bot',
    r'alert',
    r'alerts',
    r'update',
    r'updates',
    r'digest',
    r'summary',
    r'report',
    r'reports',
    r'reminder',
    r'reminders',
    r'confirm',
    r'confirmation',
    r'receipt',
    r'invoice',
    r'payment',
    r'billing',
    r'account[-_]?services',
    r'customer[-_]?service',
    r'customerservice',
    r'help@',
    r'helpdesk',
    r'service@',
    r'team@',
    r'office@',
    r'reception@',
    r'general@',
    r'enquiries@',
    r'inquiries@',
    r'feedback@',
    r'press@',
    r'media@',
    r'jobs@',
    r'careers@',
    r'hr@',
    r'legal@',
    r'privacy@',
    r'security@',
    r'abuse@',
    r'webmaster@',
    r'www@',
    r'ftp@',
    r'root@',
    r'hostmaster@',
    r'null@',
    r'test@',
    r'example@',
    r'demo@',
    r'sample@',
    r'placeholder@',
    r'temp@',
    r'temporary@',
    r'delete@',
    r'remove@',
    r'archive@',
]

# Domains that are typically system/notification emails
UNWANTED_DOMAINS = [
    'reply.',
    'noreply.',
    'no-reply.',
    'mail.',
    'email.',
    'notification.',
    'notifications.',
    'system.',
    'automated.',
    'alert.',
    'alerts.',
    'update.',
    'updates.',
    'digest.',
    'summary.',
    'report.',
    'reports.',
    'reminder.',
    'reminders.',
    'confirm.',
    'confirmation.',
    'receipt.',
    'invoice.',
    'payment.',
    'billing.',
    'account.',
    'accounts.',
    'customer.',
    'customers.',
    'service.',
    'services.',
    'support.',
    'help.',
    'helpdesk.',
    'info.',
    'contact.',
    'sales.',
    'marketing.',
    'newsletter.',
    'unsubscribe.',
    'bounce.',
    'postmaster.',
    'mailer.',
    'daemon.',
    'robot.',
    'bot.',
    'test.',
    'example.',
    'demo.',
    'sample.',
    'placeholder.',
    'temp.',
    'temporary.',
    'delete.',
    'remove.',
    'archive.',
]

# Email addresses that are clearly system emails
SYSTEM_EMAILS = [
    'postmaster@',
    'mailer-daemon@',
    'mailerdaemon@',
    'daemon@',
    'root@',
    'nobody@',
    'null@',
    'test@',
    'example@',
    'demo@',
    'sample@',
    'placeholder@',
    'temp@',
    'temporary@',
    'delete@',
    'remove@',
    'archive@',
]

def is_unwanted_email(email: str) -> Tuple[bool, str]:
    """
    Check if an email address matches unwanted patterns.
    Returns (is_unwanted, reason)
    """
    if not email:
        return False, ""
    
    email_lower = email.strip().lower()
    
    # Check against system email patterns
    for pattern in SYSTEM_EMAILS:
        if email_lower.startswith(pattern):
            return True, f"System email pattern: {pattern}"
    
    # Check email prefix against unwanted patterns
    email_prefix = email_lower.split('@')[0] if '@' in email_lower else email_lower
    for pattern in UNWANTED_EMAIL_PATTERNS:
        if re.search(pattern, email_prefix, re.IGNORECASE):
            return True, f"Unwanted pattern: {pattern}"
    
    # Check domain against unwanted domains
    if '@' in email_lower:
        domain = email_lower.split('@')[1]
        for unwanted_domain in UNWANTED_DOMAINS:
            if unwanted_domain in domain:
                return True, f"Unwanted domain pattern: {unwanted_domain}"
    
    # Check for very long email addresses (often system-generated)
    if len(email_lower) > 80:
        return True, "Email address too long (likely system-generated)"
    
    # Check for email addresses with many special characters (often system-generated)
    special_char_count = sum(1 for c in email_lower if c in '+-_=')
    if special_char_count > 5:
        return True, "Too many special characters (likely system-generated)"
    
    return False, ""

def is_likely_personal_email(email: str) -> bool:
    """Check if email looks like a personal email (Gmail, Yahoo, etc.) without business context."""
    if not email:
        return False
    
    email_lower = email.strip().lower()
    personal_domains = [
        '@gmail.com',
        '@googlemail.com',
        '@yahoo.com',
        '@yahoo.co.uk',
        '@hotmail.com',
        '@outlook.com',
        '@live.com',
        '@msn.com',
        '@aol.com',
        '@icloud.com',
        '@me.com',
        '@mac.com',
        '@protonmail.com',
        '@proton.me',
        '@mail.com',
        '@yandex.com',
        '@zoho.com',
    ]
    
    return any(email_lower.endswith(domain) for domain in personal_domains)

def cleanup_brevo_contacts(
    dry_run=True,
    archive_unwanted=True,
    remove_personal=False,
    list_id=None,
    min_contacts_to_show=10
):
    """
    Clean up unwanted contacts in Brevo.
    
    Args:
        dry_run: If True, only show what would be removed without making changes
        archive_unwanted: If True, archive unwanted contacts to a separate list instead of deleting
        remove_personal: If True, also remove personal email addresses (Gmail, Yahoo, etc.)
        list_id: Optional list ID to clean only contacts in that list
        min_contacts_to_show: Minimum number of contacts to show details for (to avoid spam)
    """
    brevo = BrevoService()
    
    if not brevo.enabled:
        print("ERROR: Brevo not configured. Set BREVO_API_KEY environment variable.")
        return
    
    print("=" * 70)
    print("CLEANING UP UNWANTED BREVO CONTACTS")
    print("=" * 70)
    print(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'LIVE (will remove/archive contacts)'}")
    print(f"Archive unwanted: {archive_unwanted}")
    print(f"Remove personal emails: {remove_personal}")
    print()
    
    try:
        # Get contacts
        if list_id:
            print(f"Fetching contacts from list ID {list_id}...")
            all_contacts = []
            offset = 0
            limit = 50
            
            import requests
            while True:
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
        
        # Categorize contacts
        unwanted_contacts = []
        personal_contacts = []
        good_contacts = []
        
        for contact in all_contacts:
            email = contact.get('email', '').strip()
            if not email:
                continue
            
            attrs = contact.get('attributes', {})
            first_name = attrs.get('FIRSTNAME', '').strip()
            last_name = attrs.get('LASTNAME', '').strip()
            
            # Check if unwanted
            is_unwanted, reason = is_unwanted_email(email)
            if is_unwanted:
                unwanted_contacts.append({
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'reason': reason,
                    'contact_id': contact.get('id')
                })
                continue
            
            # Check if personal email (if enabled)
            if remove_personal and is_likely_personal_email(email):
                # Only flag as personal if it doesn't have a real name or company
                company = attrs.get('COMPANY', '').strip()
                if not first_name and not last_name and not company:
                    personal_contacts.append({
                        'email': email,
                        'first_name': first_name,
                        'last_name': last_name,
                        'reason': 'Personal email without business context',
                        'contact_id': contact.get('id')
                    })
                    continue
            
            good_contacts.append(contact)
        
        # Print summary
        print(f"=== CONTACT ANALYSIS ===")
        print(f"Total contacts: {len(all_contacts)}")
        print(f"Good contacts: {len(good_contacts)}")
        print(f"Unwanted contacts: {len(unwanted_contacts)}")
        if remove_personal:
            print(f"Personal emails (to remove): {len(personal_contacts)}")
        print()
        
        # Show unwanted contacts
        if unwanted_contacts:
            print(f"=== UNWANTED CONTACTS ({len(unwanted_contacts)}) ===")
            show_count = min(len(unwanted_contacts), min_contacts_to_show)
            for i, contact_info in enumerate(unwanted_contacts[:show_count], 1):
                name = f"{contact_info['first_name']} {contact_info['last_name']}".strip() or "No name"
                print(f"{i}. {contact_info['email']}")
                print(f"   Name: {name}")
                print(f"   Reason: {contact_info['reason']}")
            
            if len(unwanted_contacts) > show_count:
                print(f"\n   ... and {len(unwanted_contacts) - show_count} more unwanted contacts")
            print()
        
        # Show personal contacts if enabled
        if remove_personal and personal_contacts:
            print(f"=== PERSONAL EMAILS TO REMOVE ({len(personal_contacts)}) ===")
            show_count = min(len(personal_contacts), min_contacts_to_show)
            for i, contact_info in enumerate(personal_contacts[:show_count], 1):
                name = f"{contact_info['first_name']} {contact_info['last_name']}".strip() or "No name"
                print(f"{i}. {contact_info['email']}")
                print(f"   Name: {name}")
                print(f"   Reason: {contact_info['reason']}")
            
            if len(personal_contacts) > show_count:
                print(f"\n   ... and {len(personal_contacts) - show_count} more personal contacts")
            print()
        
        # Get or create archive list if archiving
        archive_list_id = None
        if archive_unwanted and not dry_run:
            lists_result = brevo.get_lists()
            if lists_result.get('success'):
                for lst in lists_result.get('lists', []):
                    if 'archived' in lst.get('name', '').lower() and 'unwanted' in lst.get('name', '').lower():
                        archive_list_id = lst.get('id')
                        break
                
                if not archive_list_id:
                    # Create archive list
                    create_result = brevo.create_list("Archived Unwanted Contacts")
                    if create_result.get('success'):
                        archive_list_id = create_result.get('list_id')
                        print(f"Created archive list: ID {archive_list_id}")
        
        # Process removals
        total_to_remove = len(unwanted_contacts) + (len(personal_contacts) if remove_personal else 0)
        
        if total_to_remove == 0:
            print("✅ No unwanted contacts found!")
            return
        
        if dry_run:
            print("=" * 70)
            print(f"DRY RUN COMPLETE")
            print(f"   Would remove/archive: {total_to_remove} contacts")
            print(f"   - Unwanted: {len(unwanted_contacts)}")
            if remove_personal:
                print(f"   - Personal: {len(personal_contacts)}")
            print()
            print("Run with --execute to apply these changes:")
            print("   python3 cleanup_brevo_junk_contacts.py --execute")
            if archive_unwanted:
                print("   (Contacts will be archived to 'Archived Unwanted Contacts' list)")
            else:
                print("   (Contacts will be DELETED from Brevo)")
        else:
            print("=" * 70)
            print(f"REMOVING/ARCHIVING CONTACTS...")
            print()
            
            removed_count = 0
            archived_count = 0
            error_count = 0
            
            all_to_remove = unwanted_contacts + (personal_contacts if remove_personal else [])
            
            for i, contact_info in enumerate(all_to_remove, 1):
                email = contact_info['email']
                
                try:
                    import requests
                    
                    if archive_unwanted and archive_list_id:
                        # Add to archive list first
                        response = requests.post(
                            f"{brevo.base_url}/contacts/lists/{archive_list_id}/contacts/add",
                            headers=brevo._get_headers(),
                            json={"emails": [email]}
                        )
                        
                        if response.status_code in (200, 201, 204):
                            archived_count += 1
                    
                    # Remove from all lists
                    response = requests.delete(
                        f"{brevo.base_url}/contacts/{email}",
                        headers=brevo._get_headers()
                    )
                    
                    if response.status_code in (200, 201, 204):
                        removed_count += 1
                        if i % 10 == 0:
                            print(f"   Processed {i}/{len(all_to_remove)}...")
                    else:
                        error_count += 1
                        if error_count <= 5:  # Only show first 5 errors
                            print(f"   ❌ Error removing {email}: {response.status_code}")
                    
                    # Rate limiting
                    if i < len(all_to_remove):
                        time.sleep(0.1)
                        
                except Exception as e:
                    error_count += 1
                    if error_count <= 5:
                        print(f"   ❌ Exception removing {email}: {str(e)}")
            
            print()
            print("=" * 70)
            print(f"CLEANUP COMPLETE")
            print(f"   Removed: {removed_count}")
            if archive_unwanted:
                print(f"   Archived: {archived_count}")
            print(f"   Errors: {error_count}")
            print(f"   Total processed: {len(all_to_remove)}")
            print("=" * 70)
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up unwanted Brevo contacts")
    parser.add_argument("--execute", action="store_true", help="Actually remove contacts (default is dry run)")
    parser.add_argument("--no-archive", action="store_true", help="Delete contacts instead of archiving")
    parser.add_argument("--remove-personal", action="store_true", help="Also remove personal email addresses (Gmail, Yahoo, etc.)")
    parser.add_argument("--list-id", type=int, help="Only clean contacts in this list ID")
    parser.add_argument("--show-all", action="store_true", help="Show all contacts (not just first 10)")
    
    args = parser.parse_args()
    
    cleanup_brevo_contacts(
        dry_run=not args.execute,
        archive_unwanted=not args.no_archive,
        remove_personal=args.remove_personal,
        list_id=args.list_id,
        min_contacts_to_show=1000 if args.show_all else 10
    )


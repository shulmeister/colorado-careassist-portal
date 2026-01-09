#!/usr/bin/env python3
"""Sync contacts from Mailchimp Referral Source segment to database (one-time)"""

import os
from dotenv import load_dotenv
from mailchimp_service import MailchimpService
from database import db_manager
from models import Contact
from sqlalchemy.orm import sessionmaker
from datetime import datetime

load_dotenv()

def sync_mailchimp_contacts():
    """Pull contacts from Mailchimp Referral Source segment and cache in database"""
    print("=" * 60)
    print("SYNCING CONTACTS FROM MAILCHIMP")
    print("=" * 60)
    
    Session = sessionmaker(bind=db_manager.engine)
    db = Session()
    
    try:
        mailchimp_service = MailchimpService()
        
        if not mailchimp_service.enabled:
            print("❌ Mailchimp not configured. Set MAILCHIMP_API_KEY, MAILCHIMP_SERVER_PREFIX, and MAILCHIMP_LIST_ID")
            return
        
        print("\n📡 Fetching contacts from Mailchimp 'Referral Source' segment...")
        members = mailchimp_service.get_segment_members("Referral Source")
        
        if not members:
            print("⚠️  No members found in segment or segment not found")
            return
        
        print(f"✅ Found {len(members)} members in segment")
        
        # Check existing contacts by email
        existing_emails = {c.email.lower() for c in db.query(Contact.email).filter(Contact.email.isnot(None)).all() if c.email}
        
        added_count = 0
        updated_count = 0
        skipped_count = 0
        
        for member in members:
            email = member.get('email_address', '').lower().strip()
            if not email or email in existing_emails:
                skipped_count += 1
                continue
            
            # Extract contact info from Mailchimp member
            merge_fields = member.get('merge_fields', {})
            
            # Build name from FNAME and LNAME or just use full name
            first_name = merge_fields.get('FNAME', '').strip()
            last_name = merge_fields.get('LNAME', '').strip()
            name = f"{first_name} {last_name}".strip() if first_name or last_name else email.split('@')[0]
            
            contact = Contact(
                name=name if name else None,
                company=merge_fields.get('COMPANY', '').strip() or None,
                email=email,
                phone=merge_fields.get('PHONE', '').strip() or None,
                address=merge_fields.get('ADDRESS', {}).get('addr1', '').strip() if isinstance(merge_fields.get('ADDRESS'), dict) else (merge_fields.get('ADDRESS', '').strip() if merge_fields.get('ADDRESS') else None),
                website=merge_fields.get('WEBSITE', '').strip() or None,
                title=merge_fields.get('TITLE', '').strip() or None,
                scanned_date=datetime.utcnow(),
                created_at=datetime.utcnow()
            )
            
            db.add(contact)
            existing_emails.add(email)
            added_count += 1
        
        db.commit()
        
        print(f"\n✅ Sync complete!")
        print(f"   Added: {added_count} new contacts")
        print(f"   Skipped: {skipped_count} (already in database)")
        print(f"   Total in database: {db.query(Contact).count()}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    sync_mailchimp_contacts()

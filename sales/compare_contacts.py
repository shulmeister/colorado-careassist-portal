#!/usr/bin/env python3
"""Compare dashboard contacts vs Mailchimp to find differences."""

import os
import sys
from database import db_manager
from models import Contact
from mailchimp_service import MailchimpService

def compare_contacts():
    db = db_manager.SessionLocal()
    mailchimp = MailchimpService()
    
    if not mailchimp.enabled:
        print("ERROR: Mailchimp not configured")
        return
    
    try:
        # Get all dashboard contacts with emails
        dashboard_contacts = db.query(Contact).filter(
            Contact.email.isnot(None),
            Contact.email != ''
        ).all()
        
        dashboard_emails = {c.email.lower().strip(): c for c in dashboard_contacts if c.email}
        print(f"Dashboard contacts with email: {len(dashboard_emails)}")
        
        # Get all Mailchimp contacts using the sync method
        print("Fetching Mailchimp contacts...")
        sync_result = mailchimp.sync_from_mailchimp()
        
        if not sync_result.get('success'):
            print(f"ERROR: Failed to fetch from Mailchimp: {sync_result.get('error')}")
            return
        
        mailchimp_contacts = sync_result.get('contacts', [])
        mailchimp_emails = {c['email'].lower().strip() for c in mailchimp_contacts if c.get('email')}
        print(f"Mailchimp contacts: {len(mailchimp_emails)}")
        
        # Find contacts in dashboard but NOT in Mailchimp
        only_in_dashboard = []
        for email, contact in dashboard_emails.items():
            if email not in mailchimp_emails:
                only_in_dashboard.append(contact)
        
        # Find contacts in Mailchimp but NOT in dashboard
        only_in_mailchimp = []
        for email in mailchimp_emails:
            if email not in dashboard_emails:
                only_in_mailchimp.append(email)
        
        print(f"\n{'='*60}")
        print(f"COMPARISON RESULTS")
        print(f"{'='*60}")
        print(f"In BOTH systems: {len(dashboard_emails) - len(only_in_dashboard)}")
        print(f"Only in DASHBOARD (not in Mailchimp): {len(only_in_dashboard)}")
        print(f"Only in MAILCHIMP (not in Dashboard): {len(only_in_mailchimp)}")
        
        # Analyze dashboard-only contacts
        if only_in_dashboard:
            print(f"\n{'='*60}")
            print(f"DASHBOARD-ONLY CONTACTS ({len(only_in_dashboard)})")
            print(f"These would need to be added to Mailchimp")
            print(f"{'='*60}")
            
            # Categorize by source
            by_source = {}
            for c in only_in_dashboard:
                source = c.source or 'unknown'
                if source not in by_source:
                    by_source[source] = []
                by_source[source].append(c)
            
            print("\nBy Source:")
            for source, contacts in sorted(by_source.items(), key=lambda x: -len(x[1])):
                print(f"  {source}: {len(contacts)}")
            
            # Categorize by contact_type
            by_type = {}
            for c in only_in_dashboard:
                ctype = c.contact_type or 'none'
                if ctype not in by_type:
                    by_type[ctype] = []
                by_type[ctype].append(c)
            
            print("\nBy Contact Type:")
            for ctype, contacts in sorted(by_type.items(), key=lambda x: -len(x[1])):
                print(f"  {ctype}: {len(contacts)}")
            
            # Show quality breakdown
            has_name = sum(1 for c in only_in_dashboard if c.name and len(c.name) > 2)
            has_company = sum(1 for c in only_in_dashboard if c.company and len(c.company) > 2)
            has_phone = sum(1 for c in only_in_dashboard if c.phone and len(c.phone) > 5)
            
            print(f"\nData Quality:")
            print(f"  Has name: {has_name}/{len(only_in_dashboard)}")
            print(f"  Has company: {has_company}/{len(only_in_dashboard)}")
            print(f"  Has phone: {has_phone}/{len(only_in_dashboard)}")
            
            # Show sample of good contacts (have name, company, and are referral/client type)
            good_contacts = [c for c in only_in_dashboard 
                          if c.name and len(c.name) > 2 
                          and c.company and len(c.company) > 2
                          and c.contact_type in ('referral', 'client')]
            
            print(f"\n{'='*60}")
            print(f"GOOD CANDIDATES FOR MAILCHIMP ({len(good_contacts)})")
            print(f"(Have name, company, and are referral/client)")
            print(f"{'='*60}")
            
            for c in good_contacts[:20]:
                print(f"  • {c.name} | {c.email} | {c.company} | {c.contact_type}")
            
            if len(good_contacts) > 20:
                print(f"  ... and {len(good_contacts) - 20} more")
            
            # Show questionable contacts
            questionable = [c for c in only_in_dashboard 
                          if not c.name or len(c.name) <= 2 
                          or not c.company or len(c.company) <= 2]
            
            print(f"\n{'='*60}")
            print(f"QUESTIONABLE CONTACTS ({len(questionable)})")
            print(f"(Missing name or company - review before adding)")
            print(f"{'='*60}")
            
            for c in questionable[:20]:
                print(f"  • {c.email} | name='{c.name}' | company='{c.company}' | source={c.source}")
            
            if len(questionable) > 20:
                print(f"  ... and {len(questionable) - 20} more")
        
    finally:
        db.close()

if __name__ == "__main__":
    compare_contacts()


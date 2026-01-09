#!/usr/bin/env python3
"""
Sync FROM Brevo (source of truth) TO Dashboard CRM to clean up dashboard data.
This prioritizes Brevo data over dashboard data.
"""

import sys
import os
import requests
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db_manager
from models import Contact, ReferralSource, Deal
from brevo_service import BrevoService
import json
import time
import requests

def sync_contacts_from_brevo(db, brevo):
    """Sync contacts FROM Brevo TO Dashboard, using Brevo as source of truth.
    Only syncs contacts from Client and Referral Source lists."""
    print("\n" + "="*60)
    print("SYNCING CONTACTS FROM BREVO → DASHBOARD")
    print("Only syncing from Client and Referral Source lists")
    print("="*60)
    
    # Get list IDs for Client and Referral Source lists
    lists_result = brevo.get_lists()
    if not lists_result.get('success'):
        print(f"ERROR: Failed to get lists from Brevo: {lists_result.get('error')}")
        return 0, 0
    
    client_list_id = None
    referral_list_id = None
    
    for lst in lists_result.get('lists', []):
        name = lst.get('name', '').lower()
        if 'client' in name and 'referral' not in name:
            client_list_id = lst.get('id')
            print(f"Found Client list: ID {client_list_id} ({lst.get('name')})")
        elif 'referral' in name and 'source' in name:
            referral_list_id = lst.get('id')
            print(f"Found Referral Source list: ID {referral_list_id} ({lst.get('name')})")
    
    if not client_list_id or not referral_list_id:
        print(f"ERROR: Could not find both lists. Client: {client_list_id}, Referral: {referral_list_id}")
        return 0, 0
    
    # Get contacts from Client list
    client_contacts = []
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
        client_contacts.extend(contacts_page)
        if len(contacts_page) < 50:
            break
        offset += 50
    
    # Get contacts from Referral Source list
    referral_contacts = []
    offset = 0
    while True:
        response = requests.get(
            f"{brevo.base_url}/contacts/lists/{referral_list_id}/contacts",
            headers=brevo._get_headers(),
            params={"limit": 50, "offset": offset}
        )
        if response.status_code != 200:
            break
        data = response.json()
        contacts_page = data.get('contacts', [])
        referral_contacts.extend(contacts_page)
        if len(contacts_page) < 50:
            break
        offset += 50
    
    # Combine and deduplicate by email
    all_brevo_contacts = {}
    for contact in client_contacts + referral_contacts:
        email = contact.get('email', '').strip().lower()
        if email:
            # Mark which list they're from
            if contact in client_contacts:
                contact['_list_type'] = 'client'
            else:
                contact['_list_type'] = 'referral'
            all_brevo_contacts[email] = contact
    
    brevo_contacts = list(all_brevo_contacts.values())
    print(f"Found {len(client_contacts)} contacts in Client list")
    print(f"Found {len(referral_contacts)} contacts in Referral Source list")
    print(f"Total unique contacts to sync: {len(brevo_contacts)}")
    
    added = 0
    updated = 0
    errors = 0
    
    for bc in brevo_contacts:
        try:
            email = bc.get('email', '').strip().lower()
            if not email:
                continue
            
            attrs = bc.get('attributes', {})
            first_name = attrs.get('FIRSTNAME', '').strip()
            last_name = attrs.get('LASTNAME', '').strip()
            
            # Find existing contact by email
            contact = db.query(Contact).filter(Contact.email == email).first()
            
            if contact:
                # Update existing - use Brevo data as source of truth
                updated_fields = []
                
                if first_name and contact.first_name != first_name:
                    contact.first_name = first_name
                    updated_fields.append('first_name')
                
                if last_name and contact.last_name != last_name:
                    contact.last_name = last_name
                    updated_fields.append('last_name')
                
                # Update name field
                full_name = f"{first_name} {last_name}".strip() or email
                if contact.name != full_name:
                    contact.name = full_name
                    updated_fields.append('name')
                
                # Update company if provided
                company = attrs.get('COMPANY', '').strip()
                if company and contact.company != company:
                    contact.company = company
                    updated_fields.append('company')
                
                # Update phone if provided
                phone = attrs.get('SMS', '').strip() or attrs.get('PHONE', '').strip()
                if phone and contact.phone != phone:
                    contact.phone = phone
                    updated_fields.append('phone')
                
                # Update title if provided
                title = attrs.get('TITLE', '').strip()
                if title and contact.title != title:
                    contact.title = title
                    updated_fields.append('title')
                
                # Update contact_type from list membership
                list_type = bc.get('_list_type', '')
                if list_type == 'client':
                    if contact.contact_type != 'client':
                        contact.contact_type = 'client'
                        updated_fields.append('contact_type')
                elif list_type == 'referral':
                    if contact.contact_type != 'referral':
                        contact.contact_type = 'referral'
                        updated_fields.append('contact_type')
                
                if updated_fields:
                    contact.updated_at = datetime.now()
                    updated += 1
                    if updated <= 10:
                        print(f"  Updated: {email} ({', '.join(updated_fields)})")
            else:
                # Create new contact from Brevo
                full_name = f"{first_name} {last_name}".strip() or email
                contact = Contact(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    name=full_name,
                    company=attrs.get('COMPANY', '').strip(),
                    phone=attrs.get('SMS', '').strip() or attrs.get('PHONE', '').strip(),
                    title=attrs.get('TITLE', '').strip(),
                    contact_type=attrs.get('CONTACT_TYPE', 'prospect'),
                    status=attrs.get('STATUS', 'cold')
                )
                
                # Determine contact_type from list membership
                list_type = bc.get('_list_type', '')
                if list_type == 'client':
                    contact.contact_type = 'client'
                elif list_type == 'referral':
                    contact.contact_type = 'referral'
                else:
                    contact.contact_type = 'prospect'
                
                db.add(contact)
                added += 1
                if added <= 10:
                    print(f"  Added: {email} ({full_name})")
            
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error syncing contact {bc.get('email')}: {str(e)}")
    
    db.commit()
    print(f"\n✓ Contacts: {added} added, {updated} updated, {errors} errors")
    
    return added + updated, errors


def sync_companies_from_brevo(db, brevo):
    """Sync companies FROM Brevo TO Dashboard, using Brevo as source of truth."""
    print("\n" + "="*60)
    print("SYNCING COMPANIES FROM BREVO → DASHBOARD")
    print("="*60)
    
    companies_result = brevo.get_brevo_companies(limit=1000)
    if not companies_result.get('success'):
        print(f"ERROR: Failed to get companies from Brevo: {companies_result.get('error')}")
        return 0, 0
    
    brevo_companies = companies_result.get('companies', [])
    print(f"Found {len(brevo_companies)} companies in Brevo")
    
    added = 0
    updated = 0
    errors = 0
    
    for bc in brevo_companies:
        try:
            name = bc.get('name', '').strip()
            if not name:
                continue
            
            attrs = bc.get('attributes', {})
            
            # Find existing company by name
            company = db.query(ReferralSource).filter(ReferralSource.name == name).first()
            
            if company:
                # Update existing - use Brevo data as source of truth
                updated_fields = []
                
                email = attrs.get('email', '').strip()
                if email and company.email != email:
                    company.email = email
                    updated_fields.append('email')
                
                phone = attrs.get('phone', '').strip()
                if phone and company.phone != phone:
                    company.phone = phone
                    updated_fields.append('phone')
                
                address = attrs.get('address', '').strip()
                if address and company.address != address:
                    company.address = address
                    updated_fields.append('address')
                
                website = attrs.get('website', '').strip()
                if website and company.website != website:
                    company.website = website
                    updated_fields.append('website')
                
                location = attrs.get('location', '').strip()
                if location and company.location != location:
                    company.location = location
                    updated_fields.append('location')
                
                county = attrs.get('county', '').strip()
                if county and company.county != county:
                    company.county = county
                    updated_fields.append('county')
                
                source_type = attrs.get('source_type', '').strip()
                if source_type and company.source_type != source_type:
                    company.source_type = source_type
                    updated_fields.append('source_type')
                
                notes = attrs.get('notes', '').strip()
                if notes and company.notes != notes:
                    company.notes = notes
                    updated_fields.append('notes')
                
                if updated_fields:
                    company.updated_at = datetime.now()
                    updated += 1
                    if updated <= 10:
                        print(f"  Updated: {name} ({', '.join(updated_fields)})")
            else:
                # Create new company from Brevo
                company = ReferralSource(
                    name=name,
                    organization=name,
                    email=attrs.get('email', '').strip(),
                    phone=attrs.get('phone', '').strip(),
                    address=attrs.get('address', '').strip(),
                    website=attrs.get('website', '').strip(),
                    location=attrs.get('location', '').strip(),
                    county=attrs.get('county', '').strip(),
                    source_type=attrs.get('source_type', '').strip(),
                    notes=attrs.get('notes', '').strip(),
                    status='active'
                )
                db.add(company)
                added += 1
                if added <= 10:
                    print(f"  Added: {name}")
            
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error syncing company {bc.get('name')}: {str(e)}")
    
    db.commit()
    print(f"\n✓ Companies: {added} added, {updated} updated, {errors} errors")
    
    return added + updated, errors


def sync_deals_from_brevo(db, brevo):
    """Sync deals FROM Brevo TO Dashboard, using Brevo as source of truth."""
    print("\n" + "="*60)
    print("SYNCING DEALS FROM BREVO → DASHBOARD")
    print("="*60)
    
    deals_result = brevo.get_brevo_deals(limit=1000)
    if not deals_result.get('success'):
        print(f"ERROR: Failed to get deals from Brevo: {deals_result.get('error')}")
        return 0, 0
    
    brevo_deals = deals_result.get('deals', [])
    print(f"Found {len(brevo_deals)} deals in Brevo")
    
    added = 0
    updated = 0
    errors = 0
    
    for bd in brevo_deals:
        try:
            name = bd.get('name', '').strip()
            if not name:
                continue
            
            attrs = bd.get('attributes', {})
            amount = attrs.get('amount', 0)
            if amount:
                amount = float(amount) / 100  # Convert from cents
            
            # Find existing deal by name
            deal = db.query(Deal).filter(Deal.name == name).first()
            
            if deal:
                # Update existing - use Brevo data as source of truth
                updated_fields = []
                
                if amount and deal.amount != amount:
                    deal.amount = amount
                    updated_fields.append('amount')
                
                category = attrs.get('category', '').strip()
                if category and deal.category != category:
                    deal.category = category
                    updated_fields.append('category')
                
                description = attrs.get('deal_notes', '').strip()
                if description and deal.description != description:
                    deal.description = description
                    updated_fields.append('description')
                
                # Map Brevo pipeline stage to our stage
                pipeline = bd.get('pipeline', '').lower()
                if pipeline:
                    stage_mapping = {
                        'open': 'opportunity',
                        'won': 'closed/won',
                        'lost': 'closed/lost'
                    }
                    new_stage = stage_mapping.get(pipeline, 'opportunity')
                    if deal.stage != new_stage:
                        deal.stage = new_stage
                        updated_fields.append('stage')
                
                if updated_fields:
                    deal.updated_at = datetime.now()
                    updated += 1
                    if updated <= 10:
                        print(f"  Updated: {name} ({', '.join(updated_fields)})")
            else:
                # Create new deal from Brevo
                pipeline = bd.get('pipeline', '').lower()
                stage_mapping = {
                    'open': 'opportunity',
                    'won': 'closed/won',
                    'lost': 'closed/lost'
                }
                stage = stage_mapping.get(pipeline, 'opportunity')
                
                deal = Deal(
                    name=name,
                    amount=amount,
                    category=attrs.get('category', '').strip(),
                    description=attrs.get('deal_notes', '').strip(),
                    stage=stage
                )
                db.add(deal)
                added += 1
                if added <= 10:
                    print(f"  Added: {name}")
            
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error syncing deal {bd.get('name')}: {str(e)}")
    
    db.commit()
    print(f"\n✓ Deals: {added} added, {updated} updated, {errors} errors")
    
    return added + updated, errors


def main():
    print("="*60)
    print("SYNC FROM BREVO TO DASHBOARD (CLEANUP)")
    print("Using Brevo as source of truth")
    print("="*60)
    
    db = db_manager.SessionLocal()
    brevo = BrevoService()
    
    if not brevo.enabled:
        print("ERROR: Brevo not configured")
        return
    
    # Test connection
    test = brevo.test_connection()
    if not test.get('success'):
        print(f"ERROR: Brevo connection failed: {test.get('error')}")
        return
    
    print(f"Connected to Brevo: {test.get('message')}")
    
    try:
        # Sync FROM Brevo TO Dashboard
        contact_success, contact_errors = sync_contacts_from_brevo(db, brevo)
        company_success, company_errors = sync_companies_from_brevo(db, brevo)
        deal_success, deal_errors = sync_deals_from_brevo(db, brevo)
        
        print("\n" + "="*60)
        print("SYNC COMPLETE")
        print("="*60)
        print(f"Contacts: {contact_success} synced, {contact_errors} errors")
        print(f"Companies: {company_success} synced, {company_errors} errors")
        print(f"Deals: {deal_success} synced, {deal_errors} errors")
        print("\n✓ Dashboard data cleaned up using Brevo as source of truth")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()


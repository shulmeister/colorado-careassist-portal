#!/usr/bin/env python3
"""
Bidirectional sync between Dashboard CRM and Brevo CRM.
Syncs: Contacts, Companies, Deals, Tasks, Pipeline Stages
"""

import sys
import os
import requests
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db_manager
from models import Contact, ReferralSource, Deal, ContactTask, CompanyTask, DealTask
from brevo_service import BrevoService
import json
import time

def sync_contacts_to_brevo(db, brevo):
    """Sync all contacts from Dashboard to Brevo CRM."""
    print("\n" + "="*60)
    print("SYNCING CONTACTS → BREVO")
    print("="*60)
    
    contacts = db.query(Contact).filter(
        Contact.email.isnot(None),
        Contact.email != ''
    ).all()
    
    print(f"Found {len(contacts)} contacts in dashboard")
    
    success = 0
    errors = 0
    
    for contact in contacts:
        try:
            # Normalize names
            first_name = contact.first_name or ''
            last_name = contact.last_name or ''
            if first_name and ' ' in first_name and not last_name:
                parts = first_name.split(' ', 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ''
            
            contact_data = {
                'email': contact.email,
                'first_name': first_name,
                'last_name': last_name,
                'company': contact.company or '',
                'phone': contact.phone or '',
                'title': contact.title or '',
                'contact_type': contact.contact_type or '',
                'status': contact.status or '',
                'source': contact.source or 'dashboard'
            }
            
            result = brevo.sync_contact_to_crm(contact_data)
            
            if result.get('success'):
                success += 1
            else:
                errors += 1
                if errors <= 5:
                    print(f"  Error: {contact.email}: {result.get('error', 'Unknown')}")
            
            # Rate limiting
            if (success + errors) % 50 == 0:
                time.sleep(1)
                
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Exception: {contact.email}: {str(e)}")
    
    print(f"\n✓ Contacts synced: {success}")
    if errors:
        print(f"✗ Errors: {errors}")
    
    return success, errors


def sync_companies_to_brevo(db, brevo):
    """Sync all companies from Dashboard to Brevo CRM."""
    print("\n" + "="*60)
    print("SYNCING COMPANIES → BREVO")
    print("="*60)
    
    companies = db.query(ReferralSource).all()
    print(f"Found {len(companies)} companies in dashboard")
    
    success = 0
    errors = 0
    
    for company in companies:
        try:
            company_data = {
                'name': company.name or company.organization or "Unknown Company",
                'email': company.email or '',
                'phone': company.phone or '',
                'address': company.address or '',
                'website': company.website or '',
                'location': company.location or '',
                'county': company.county or '',
                'source_type': company.source_type or '',
                'notes': company.notes or ''
            }
            
            result = brevo.create_or_update_company(company_data)
            
            if result.get('success'):
                success += 1
            else:
                errors += 1
                if errors <= 5:
                    print(f"  Error: {company.name}: {result.get('error', 'Unknown')}")
            
            # Rate limiting
            if (success + errors) % 20 == 0:
                time.sleep(1)
                
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Exception: {company.name}: {str(e)}")
    
    print(f"\n✓ Companies synced: {success}")
    if errors:
        print(f"✗ Errors: {errors}")
    
    return success, errors


def sync_deals_to_brevo(db, brevo):
    """Sync all deals from Dashboard to Brevo CRM."""
    print("\n" + "="*60)
    print("SYNCING DEALS → BREVO")
    print("="*60)
    
    deals = db.query(Deal).filter(Deal.archived_at.is_(None)).all()
    print(f"Found {len(deals)} active deals in dashboard")
    
    success = 0
    errors = 0
    
    for deal in deals:
        try:
            deal_data = {
                'name': deal.name or f"Deal #{deal.id}",
                'amount': deal.amount or 0,
                'category': deal.category or '',
                'description': deal.description or '',
                'stage': deal.stage or 'opportunity'
            }
            
            result = brevo.create_or_update_deal(deal_data)
            
            if result.get('success'):
                success += 1
            else:
                errors += 1
                if errors <= 5:
                    print(f"  Error: {deal.name}: {result.get('error', 'Unknown')}")
            
            # Rate limiting
            if (success + errors) % 20 == 0:
                time.sleep(1)
                
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Exception: {deal.name}: {str(e)}")
    
    print(f"\n✓ Deals synced: {success}")
    if errors:
        print(f"✗ Errors: {errors}")
    
    return success, errors


def sync_from_brevo_to_dashboard(db, brevo):
    """Sync contacts, companies, and deals FROM Brevo TO Dashboard."""
    print("\n" + "="*60)
    print("SYNCING BREVO → DASHBOARD")
    print("="*60)
    
    # Sync contacts from Brevo
    print("\nSyncing contacts from Brevo...")
    contacts_result = brevo.get_all_contacts(limit=1000)
    if contacts_result.get('success'):
        brevo_contacts = contacts_result.get('contacts', [])
        print(f"Found {len(brevo_contacts)} contacts in Brevo")
        
        added = 0
        updated = 0
        
        for bc in brevo_contacts:
            try:
                email = bc.get('email', '').strip().lower()
                if not email:
                    continue
                
                attrs = bc.get('attributes', {})
                first_name = attrs.get('FIRSTNAME', '').strip()
                last_name = attrs.get('LASTNAME', '').strip()
                
                # Find or create contact
                contact = db.query(Contact).filter(Contact.email == email).first()
                
                if contact:
                    # Update existing
                    if first_name and not contact.first_name:
                        contact.first_name = first_name
                    if last_name and not contact.last_name:
                        contact.last_name = last_name
                    if attrs.get('COMPANY') and not contact.company:
                        contact.company = attrs.get('COMPANY')
                    updated += 1
                else:
                    # Create new
                    contact = Contact(
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                        name=f"{first_name} {last_name}".strip() or email,
                        company=attrs.get('COMPANY', ''),
                        phone=attrs.get('SMS', ''),
                        title=attrs.get('TITLE', ''),
                        contact_type=attrs.get('CONTACT_TYPE', 'prospect'),
                        status=attrs.get('STATUS', 'cold')
                    )
                    db.add(contact)
                    added += 1
                
            except Exception as e:
                if updated + added < 5:
                    print(f"  Error syncing contact {bc.get('email')}: {str(e)}")
        
        db.commit()
        print(f"  ✓ Contacts: {added} added, {updated} updated")
    
    # Sync companies from Brevo
    print("\nSyncing companies from Brevo...")
    companies_result = brevo.get_brevo_companies(limit=100)
    if companies_result.get('success'):
        brevo_companies = companies_result.get('companies', [])
        print(f"Found {len(brevo_companies)} companies in Brevo")
        
        added = 0
        updated = 0
        
        for bc in brevo_companies:
            try:
                name = bc.get('name', '').strip()
                if not name:
                    continue
                
                # Find or create company
                company = db.query(ReferralSource).filter(ReferralSource.name == name).first()
                
                attrs = bc.get('attributes', {})
                
                if company:
                    # Update existing
                    if attrs.get('email') and not company.email:
                        company.email = attrs.get('email')
                    if attrs.get('phone') and not company.phone:
                        company.phone = attrs.get('phone')
                    updated += 1
                else:
                    # Create new
                    company = ReferralSource(
                        name=name,
                        organization=name,
                        email=attrs.get('email', ''),
                        phone=attrs.get('phone', ''),
                        address=attrs.get('address', ''),
                        website=attrs.get('website', ''),
                        location=attrs.get('location', ''),
                        county=attrs.get('county', ''),
                        source_type=attrs.get('source_type', ''),
                        notes=attrs.get('notes', ''),
                        status='active'
                    )
                    db.add(company)
                    added += 1
                
            except Exception as e:
                if updated + added < 5:
                    print(f"  Error syncing company {bc.get('name')}: {str(e)}")
        
        db.commit()
        print(f"  ✓ Companies: {added} added, {updated} updated")
    
    # Sync deals from Brevo
    print("\nSyncing deals from Brevo...")
    deals_result = brevo.get_brevo_deals(limit=100)
    if deals_result.get('success'):
        brevo_deals = deals_result.get('deals', [])
        print(f"Found {len(brevo_deals)} deals in Brevo")
        
        added = 0
        updated = 0
        
        for bd in brevo_deals:
            try:
                name = bd.get('name', '').strip()
                if not name:
                    continue
                
                # Find or create deal
                deal = db.query(Deal).filter(Deal.name == name).first()
                
                attrs = bd.get('attributes', {})
                amount = attrs.get('amount', 0)
                if amount:
                    amount = float(amount) / 100  # Convert from cents
                
                if deal:
                    # Update existing
                    if amount and not deal.amount:
                        deal.amount = amount
                    if attrs.get('category') and not deal.category:
                        deal.category = attrs.get('category')
                    updated += 1
                else:
                    # Create new
                    deal = Deal(
                        name=name,
                        amount=amount,
                        category=attrs.get('category', ''),
                        description=attrs.get('deal_notes', ''),
                        stage='opportunity'
                    )
                    db.add(deal)
                    added += 1
                
            except Exception as e:
                if updated + added < 5:
                    print(f"  Error syncing deal {bd.get('name')}: {str(e)}")
        
        db.commit()
        print(f"  ✓ Deals: {added} added, {updated} updated")


def main():
    print("="*60)
    print("BIDIRECTIONAL BREVO CRM SYNC")
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
        # Sync Dashboard → Brevo
        print("\n" + "="*60)
        print("SYNCING DASHBOARD → BREVO")
        print("="*60)
        
        contact_success, contact_errors = sync_contacts_to_brevo(db, brevo)
        company_success, company_errors = sync_companies_to_brevo(db, brevo)
        deal_success, deal_errors = sync_deals_to_brevo(db, brevo)
        
        # Sync Brevo → Dashboard
        sync_from_brevo_to_dashboard(db, brevo)
        
        print("\n" + "="*60)
        print("SYNC COMPLETE")
        print("="*60)
        print(f"Dashboard → Brevo:")
        print(f"  Contacts: {contact_success} synced, {contact_errors} errors")
        print(f"  Companies: {company_success} synced, {company_errors} errors")
        print(f"  Deals: {deal_success} synced, {deal_errors} errors")
        print(f"\nBrevo → Dashboard: (see details above)")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()


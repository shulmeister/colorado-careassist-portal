#!/usr/bin/env python3
"""
Compare Brevo lists with database contacts to identify discrepancies.
Helps verify data quality before sending newsletters.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db_manager
from models import Contact
from brevo_service import BrevoService


def compare_data():
    """Compare Brevo lists with database contacts."""
    print("=" * 60)
    print("BREVO vs DATABASE COMPARISON")
    print("=" * 60)
    
    # Database counts
    db = db_manager.SessionLocal()
    try:
        total_db = db.query(Contact).count()
        referrals_db = db.query(Contact).filter(Contact.contact_type == 'referral').count()
        referrals_db_email = db.query(Contact).filter(
            Contact.contact_type == 'referral',
            Contact.email.isnot(None),
            Contact.email != ''
        ).count()
        clients_db = db.query(Contact).filter(Contact.contact_type == 'client').count()
        clients_db_email = db.query(Contact).filter(
            Contact.contact_type == 'client',
            Contact.email.isnot(None),
            Contact.email != ''
        ).count()
        
        print("\n📊 DATABASE COUNTS:")
        print(f"   Total contacts: {total_db}")
        print(f"   Referrals (all): {referrals_db}")
        print(f"   Referrals (with email): {referrals_db_email}")
        print(f"   Clients (all): {clients_db}")
        print(f"   Clients (with email): {clients_db_email}")
        
    except Exception as e:
        print(f"Error querying database: {e}")
        return
    finally:
        db.close()
    
    # Brevo counts
    brevo = BrevoService()
    if not brevo.enabled:
        print("\n❌ Brevo not configured")
        return
    
    print("\n📬 BREVO LIST COUNTS:")
    lists_result = brevo.get_lists()
    if not lists_result.get('success'):
        print(f"   Error: {lists_result.get('error')}")
        return
    
    lists = lists_result.get('lists', [])
    referral_list = next((l for l in lists if 'referral' in l.get('name', '').lower()), None)
    client_list = next((l for l in lists if l.get('name', '').lower() == 'client'), None)
    
    if referral_list:
        referral_list_id = referral_list.get('id')
        referral_count_brevo = referral_list.get('uniqueSubscribers', 0)
        print(f"   Referral Source (ID {referral_list_id}): {referral_count_brevo} contacts")
    else:
        print("   Referral Source list not found")
        referral_list_id = None
        referral_count_brevo = 0
    
    if client_list:
        client_list_id = client_list.get('id')
        client_count_brevo = client_list.get('uniqueSubscribers', 0)
        print(f"   Client (ID {client_list_id}): {client_count_brevo} contacts")
    else:
        print("   Client list not found")
        client_list_id = None
        client_count_brevo = 0
    
    # Comparison
    print("\n🔍 COMPARISON:")
    if referral_list_id:
        diff_referrals = referral_count_brevo - referrals_db_email
        print(f"   Referrals: Brevo has {diff_referrals:+d} more than database (with email)")
        if diff_referrals > 100:
            print(f"   ⚠️  WARNING: Large discrepancy! Brevo has {diff_referrals} extra contacts.")
            print(f"      This could indicate:")
            print(f"      - Old/unclean data from Mailchimp migration")
            print(f"      - Contacts not in your CRM database")
            print(f"      - Duplicates or test contacts")
    
    if client_list_id:
        diff_clients = client_count_brevo - clients_db_email
        print(f"   Clients: Brevo has {diff_clients:+d} more than database (with email)")
        if abs(diff_clients) <= 5:
            print(f"   ✅ Client counts are very close (good match!)")
    
    # Sample analysis
    if referral_list_id and diff_referrals > 50:
        print("\n📋 RECOMMENDATIONS:")
        print("   1. Review Brevo 'Referral Source' list for:")
        print("      - Contacts without proper categorization")
        print("      - Old/test data")
        print("      - Duplicates")
        print("   2. Consider syncing database → Brevo to update lists")
        print("   3. Clean Brevo list before sending newsletter")
        print("\n   To sync database contacts to Brevo:")
        print("   - Use /api/push-to-brevo endpoint")
        print("   - Or review and clean Brevo lists manually")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    compare_data()


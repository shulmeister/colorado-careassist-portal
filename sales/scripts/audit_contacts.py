#!/usr/bin/env python3
"""Audit contact data quality in sales dashboard and Brevo"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models import Contact, ReferralSource
from sqlalchemy import func

def audit_sales_dashboard():
    db = next(get_db())

    print("SALES DASHBOARD CONTACT AUDIT")
    print("=" * 50)

    # Total contacts
    total = db.query(Contact).count()
    print(f"Total contacts: {total}")

    # Missing first name
    missing_first = db.query(Contact).filter(
        (Contact.first_name == None) | (Contact.first_name == '')
    ).count()
    print(f"Missing first name: {missing_first}")

    # Missing last name
    missing_last = db.query(Contact).filter(
        (Contact.last_name == None) | (Contact.last_name == '')
    ).count()
    print(f"Missing last name: {missing_last}")

    # Missing email
    missing_email = db.query(Contact).filter(
        (Contact.email == None) | (Contact.email == '')
    ).count()
    print(f"Missing email: {missing_email}")

    # Missing company
    missing_company = db.query(Contact).filter(
        Contact.company_id == None
    ).count()
    print(f"Missing company: {missing_company}")

    # Duplicates by email
    dupes = db.query(Contact.email, func.count(Contact.id)).filter(
        Contact.email != None, Contact.email != ''
    ).group_by(Contact.email).having(func.count(Contact.id) > 1).all()
    print(f"Duplicate emails: {len(dupes)} email addresses with multiple contacts")

    # Show some examples of issues
    print(f"\n--- Sample contacts missing email ---")
    no_email = db.query(Contact).filter(
        (Contact.email == None) | (Contact.email == '')
    ).limit(10).all()
    for c in no_email:
        print(f"  {c.id}: {c.first_name} {c.last_name} - {c.phone}")

    print(f"\n--- Sample contacts missing company ---")
    no_company = db.query(Contact).filter(Contact.company_id == None).limit(10).all()
    for c in no_company:
        print(f"  {c.id}: {c.first_name} {c.last_name} ({c.email})")

    print(f"\n--- Sample duplicate emails ---")
    for email, count in dupes[:10]:
        print(f"  {email}: {count} contacts")

    # Total companies
    total_companies = db.query(ReferralSource).count()
    print(f"\nTotal companies: {total_companies}")

    db.close()

    return {
        "total": total,
        "missing_first": missing_first,
        "missing_last": missing_last,
        "missing_email": missing_email,
        "missing_company": missing_company,
        "duplicate_emails": len(dupes)
    }

if __name__ == "__main__":
    audit_sales_dashboard()

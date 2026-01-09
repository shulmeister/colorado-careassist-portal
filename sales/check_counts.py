#!/usr/bin/env python3
"""Check actual database counts vs dashboard display."""

from database import db_manager
from models import Contact, Visit, ReferralSource
from sqlalchemy import func

db = db_manager.SessionLocal()

try:
    contacts = db.query(Contact).count()
    visits = db.query(Visit).count()
    companies = db.query(ReferralSource).count()

    print(f"=== Actual Database Counts ===")
    print(f"Contacts: {contacts}")
    print(f"Visits: {visits}")
    print(f"Companies: {companies}")
    print()
    
    # Check for duplicate emails
    dup_emails = db.query(
        Contact.email, 
        func.count(Contact.id).label('cnt')
    ).filter(
        Contact.email.isnot(None),
        Contact.email != ''
    ).group_by(Contact.email).having(func.count(Contact.id) > 1).all()
    
    print(f"Duplicate email groups: {len(dup_emails)}")
    if dup_emails:
        for email, cnt in dup_emails[:10]:
            print(f"  - {email}: {cnt} duplicates")
    
    # Check for duplicate visits (same date + business name)
    dup_visits = db.query(
        func.date(Visit.visit_date),
        Visit.business_name,
        func.count(Visit.id).label('cnt')
    ).group_by(
        func.date(Visit.visit_date), 
        Visit.business_name
    ).having(func.count(Visit.id) > 1).all()
    
    print(f"\nDuplicate visit groups: {len(dup_visits)}")
    if dup_visits:
        for date, biz, cnt in dup_visits[:10]:
            print(f"  - {date} / {biz[:30] if biz else 'Unknown'}: {cnt} duplicates")

finally:
    db.close()


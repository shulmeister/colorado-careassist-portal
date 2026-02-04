#!/usr/bin/env python3
"""
Comprehensive duplicate cleanup script for Visits, Contacts, and Companies.
Run on Mac Mini (Local): mac-mini run python scripts/cleanup_duplicates.py --app careassist-tracker
"""

import os
import sys
from datetime import datetime
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import sessionmaker
from models import Visit, Contact, ReferralSource, Lead, ActivityLog

# Get database URL
DATABASE_URL = os.getenv('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def normalize_string(s: str) -> str:
    """Normalize a string for comparison."""
    if not s:
        return ""
    return s.lower().strip().replace("  ", " ")


def normalize_business_name(name: str) -> str:
    """Normalize business name for duplicate detection."""
    if not name:
        return ""
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [' llc', ' inc', ' corp', ' ltd', ' co', ' company', ' health', ' hospital', ' rehab', ' rehabilitation']:
        name = name.replace(suffix, '')
    # Remove punctuation
    for char in ['.', ',', "'", '"', '&', '-']:
        name = name.replace(char, ' ')
    # Collapse whitespace
    while '  ' in name:
        name = name.replace('  ', ' ')
    return name.strip()


def cleanup_duplicate_visits(db, dry_run=True):
    """
    Find and remove duplicate visits based on:
    - Same date (date part only)
    - Same normalized business name
    - Same stop number (or both null)
    """
    print("\n" + "="*60)
    print("VISITS DUPLICATE CLEANUP")
    print("="*60)
    
    visits = db.query(Visit).order_by(Visit.visit_date.asc(), Visit.id.asc()).all()
    print(f"Total visits: {len(visits)}")
    
    # Group by (date, normalized_business, stop_number)
    groups = defaultdict(list)
    for v in visits:
        date_key = v.visit_date.date() if v.visit_date else None
        biz_key = normalize_business_name(v.business_name or "")
        stop_key = v.stop_number or 0
        key = (date_key, biz_key, stop_key)
        groups[key].append(v)
    
    duplicates_found = 0
    to_delete = []
    
    for key, group in groups.items():
        if len(group) > 1:
            duplicates_found += len(group) - 1
            # Keep the first (oldest by ID), mark rest for deletion
            keeper = group[0]
            for dup in group[1:]:
                to_delete.append(dup)
                print(f"  DUP: {dup.visit_date.date() if dup.visit_date else 'NoDate'} | "
                      f"{dup.business_name[:30] if dup.business_name else 'Unknown':<30} | "
                      f"Stop {dup.stop_number or 0} | ID {dup.id} (keeping ID {keeper.id})")
    
    print(f"\nDuplicates found: {duplicates_found}")
    print(f"Will keep: {len(visits) - duplicates_found}")
    
    if not dry_run and to_delete:
        print(f"\nDeleting {len(to_delete)} duplicate visits...")
        for v in to_delete:
            db.delete(v)
        db.commit()
        print("✓ Deleted")
    elif to_delete:
        print("\n[DRY RUN] Would delete above duplicates. Run with --execute to apply.")
    
    return len(to_delete)


def cleanup_duplicate_contacts(db, dry_run=True):
    """
    Find and merge duplicate contacts based on:
    - Same email address (primary key for dedup)
    - Same normalized name if no email
    """
    print("\n" + "="*60)
    print("CONTACTS DUPLICATE CLEANUP")
    print("="*60)
    
    contacts = db.query(Contact).order_by(Contact.id.asc()).all()
    print(f"Total contacts: {len(contacts)}")
    
    # Group by email
    by_email = defaultdict(list)
    no_email = []
    
    for c in contacts:
        email = (c.email or "").lower().strip()
        if email:
            by_email[email].append(c)
        else:
            no_email.append(c)
    
    duplicates_found = 0
    to_delete = []
    
    # Handle email duplicates
    for email, group in by_email.items():
        if len(group) > 1:
            duplicates_found += len(group) - 1
            # Keep the one with most data, or first by ID
            keeper = max(group, key=lambda c: (
                len(c.name or ""),
                len(c.company or ""),
                len(c.phone or ""),
                -c.id  # Prefer lower ID as tiebreaker
            ))
            for dup in group:
                if dup.id != keeper.id:
                    to_delete.append((dup, keeper))
                    print(f"  DUP EMAIL: {email} | {dup.name or 'No Name'} | ID {dup.id} → merge to ID {keeper.id}")
    
    # Handle no-email contacts by name
    by_name = defaultdict(list)
    for c in no_email:
        name_key = normalize_string(c.name or "")
        if name_key:
            by_name[name_key].append(c)
    
    for name, group in by_name.items():
        if len(group) > 1:
            duplicates_found += len(group) - 1
            keeper = group[0]
            for dup in group[1:]:
                to_delete.append((dup, keeper))
                print(f"  DUP NAME: {name} | ID {dup.id} → merge to ID {keeper.id}")
    
    print(f"\nDuplicates found: {duplicates_found}")
    
    if not dry_run and to_delete:
        print(f"\nMerging {len(to_delete)} duplicate contacts...")
        for dup, keeper in to_delete:
            # Transfer activity logs
            db.query(ActivityLog).filter(ActivityLog.contact_id == dup.id).update(
                {"contact_id": keeper.id}, synchronize_session=False
            )
            # Transfer deals (update contact_ids JSON)
            # Note: This is simplified - in production would parse JSON
            db.delete(dup)
        db.commit()
        print("✓ Merged and deleted duplicates")
    elif to_delete:
        print("\n[DRY RUN] Would merge above duplicates. Run with --execute to apply.")
    
    return len(to_delete)


def cleanup_duplicate_companies(db, dry_run=True):
    """
    Find and merge duplicate companies (ReferralSource) based on:
    - Normalized company name
    """
    print("\n" + "="*60)
    print("COMPANIES DUPLICATE CLEANUP")
    print("="*60)
    
    companies = db.query(ReferralSource).order_by(ReferralSource.id.asc()).all()
    print(f"Total companies: {len(companies)}")
    
    # Group by normalized name
    by_name = defaultdict(list)
    for c in companies:
        name_key = normalize_business_name(c.name or "")
        if name_key:
            by_name[name_key].append(c)
    
    duplicates_found = 0
    to_delete = []
    
    for name, group in by_name.items():
        if len(group) > 1:
            duplicates_found += len(group) - 1
            # Keep the one with most data
            keeper = max(group, key=lambda c: (
                len(c.name or ""),
                len(c.address or ""),
                len(c.website or ""),
                -c.id
            ))
            for dup in group:
                if dup.id != keeper.id:
                    to_delete.append((dup, keeper))
                    print(f"  DUP: '{dup.name}' → merge to '{keeper.name}' (ID {keeper.id})")
    
    print(f"\nDuplicates found: {duplicates_found}")
    
    if not dry_run and to_delete:
        print(f"\nMerging {len(to_delete)} duplicate companies...")
        for dup, keeper in to_delete:
            # Transfer contacts
            db.query(Contact).filter(Contact.company == dup.name).update(
                {"company": keeper.name, "company_id": keeper.id}, synchronize_session=False
            )
            # Transfer leads/deals
            db.query(Lead).filter(Lead.referral_source_id == dup.id).update(
                {"referral_source_id": keeper.id}, synchronize_session=False
            )
            db.delete(dup)
        db.commit()
        print("✓ Merged and deleted duplicates")
    elif to_delete:
        print("\n[DRY RUN] Would merge above duplicates. Run with --execute to apply.")
    
    return len(to_delete)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cleanup duplicate records")
    parser.add_argument("--execute", action="store_true", help="Actually delete/merge (default is dry run)")
    parser.add_argument("--visits", action="store_true", help="Only cleanup visits")
    parser.add_argument("--contacts", action="store_true", help="Only cleanup contacts")
    parser.add_argument("--companies", action="store_true", help="Only cleanup companies")
    args = parser.parse_args()
    
    dry_run = not args.execute
    run_all = not (args.visits or args.contacts or args.companies)
    
    print("="*60)
    print("DUPLICATE CLEANUP SCRIPT")
    print("="*60)
    print(f"Mode: {'EXECUTE (will modify data)' if not dry_run else 'DRY RUN (preview only)'}")
    print(f"Database: {DATABASE_URL[:50]}...")
    
    db = Session()
    
    try:
        total_dups = 0
        
        if run_all or args.visits:
            total_dups += cleanup_duplicate_visits(db, dry_run)
        
        if run_all or args.contacts:
            total_dups += cleanup_duplicate_contacts(db, dry_run)
        
        if run_all or args.companies:
            total_dups += cleanup_duplicate_companies(db, dry_run)
        
        print("\n" + "="*60)
        print(f"TOTAL DUPLICATES: {total_dups}")
        if dry_run:
            print("Run with --execute to apply changes")
        print("="*60)
        
    finally:
        db.close()


if __name__ == "__main__":
    main()


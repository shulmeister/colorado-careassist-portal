#!/usr/bin/env python3
"""
Merge duplicate companies (ReferralSource records with same organization name)
into a single company, and properly link all contacts.

This fixes the data model issue where one ReferralSource was created per person
instead of one company with multiple linked contacts.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func
from datetime import datetime
from database import db_manager
from models import ReferralSource, Contact


def merge_duplicate_companies():
    """Find and merge duplicate companies."""
    db = db_manager.get_session()
    
    try:
        # Find all organization names that appear more than once
        duplicates = (
            db.query(ReferralSource.organization, func.count(ReferralSource.id).label('count'))
            .filter(ReferralSource.organization.isnot(None))
            .filter(ReferralSource.organization != '')
            .group_by(ReferralSource.organization)
            .having(func.count(ReferralSource.id) > 1)
            .all()
        )
        
        print(f"Found {len(duplicates)} organizations with duplicates:")
        for org, count in duplicates:
            print(f"  - {org}: {count} records")
        
        if not duplicates:
            print("No duplicates to merge.")
            return
        
        total_merged = 0
        total_contacts_created = 0
        
        for org_name, count in duplicates:
            print(f"\nProcessing: {org_name}")
            
            # Get all records for this organization, ordered by id (keep oldest)
            records = (
                db.query(ReferralSource)
                .filter(ReferralSource.organization == org_name)
                .order_by(ReferralSource.id)
                .all()
            )
            
            if len(records) < 2:
                continue
            
            # Keep the first record as the canonical company
            canonical = records[0]
            duplicates_to_merge = records[1:]
            
            print(f"  Canonical company ID: {canonical.id}")
            print(f"  Merging {len(duplicates_to_merge)} duplicate(s)")
            
            # Merge data from duplicates into canonical (keep best non-null values)
            for dup in duplicates_to_merge:
                # Update canonical with any better data from duplicate
                if not canonical.website and dup.website:
                    canonical.website = dup.website
                if not canonical.logo_url and dup.logo_url:
                    canonical.logo_url = dup.logo_url
                if not canonical.county and dup.county:
                    canonical.county = dup.county
                if not canonical.facility_type_normalized and dup.facility_type_normalized:
                    canonical.facility_type_normalized = dup.facility_type_normalized
                if not canonical.address and dup.address:
                    canonical.address = dup.address
                if not canonical.phone and dup.phone:
                    canonical.phone = dup.phone
                
                # Extract contact info from the duplicate
                contact_name = dup.name or dup.contact_name or ""
                contact_email = dup.email or ""
                contact_phone = dup.phone or ""
                contact_title = ""  # ReferralSource doesn't have title field
                
                # Parse first/last name
                name_parts = contact_name.strip().split(" ", 1)
                first_name = name_parts[0] if name_parts else ""
                last_name = name_parts[1] if len(name_parts) > 1 else ""
                
                # Check if contact already exists
                existing_contact = None
                if contact_email:
                    existing_contact = db.query(Contact).filter(Contact.email == contact_email).first()
                
                if existing_contact:
                    # Update existing contact to link to canonical company
                    existing_contact.company_id = canonical.id
                    existing_contact.company = canonical.organization
                    if first_name:
                        existing_contact.first_name = first_name
                    if last_name:
                        existing_contact.last_name = last_name
                    if contact_title:
                        existing_contact.title = contact_title
                    existing_contact.updated_at = datetime.utcnow()
                    print(f"    Updated contact: {contact_name} ({contact_email})")
                elif contact_name:
                    # Create new contact linked to canonical company
                    new_contact = Contact(
                        first_name=first_name,
                        last_name=last_name,
                        name=contact_name,
                        email=contact_email,
                        phone=contact_phone,
                        title=contact_title,
                        company=canonical.organization,
                        company_id=canonical.id,
                        status="cold",
                        source="Merged from duplicate company",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                        last_seen=datetime.utcnow(),
                    )
                    db.add(new_contact)
                    total_contacts_created += 1
                    print(f"    Created contact: {contact_name} ({contact_email or 'no email'})")
                
                # Update any contacts already linked to the duplicate
                linked_contacts = db.query(Contact).filter(Contact.company_id == dup.id).all()
                for lc in linked_contacts:
                    lc.company_id = canonical.id
                    lc.company = canonical.organization
                    print(f"    Re-linked contact: {lc.name}")
                
                # Delete the duplicate company record
                db.delete(dup)
                total_merged += 1
            
            # Also ensure the canonical company has its own contact record
            canonical_contact_name = canonical.name or canonical.contact_name or ""
            if canonical_contact_name:
                name_parts = canonical_contact_name.strip().split(" ", 1)
                first_name = name_parts[0] if name_parts else ""
                last_name = name_parts[1] if len(name_parts) > 1 else ""
                
                existing = None
                if canonical.email:
                    existing = db.query(Contact).filter(Contact.email == canonical.email).first()
                
                if not existing and canonical_contact_name:
                    new_contact = Contact(
                        first_name=first_name,
                        last_name=last_name,
                        name=canonical_contact_name,
                        email=canonical.email or "",
                        phone=canonical.phone or "",
                        title="",  # ReferralSource doesn't have title field
                        company=canonical.organization,
                        company_id=canonical.id,
                        status="cold",
                        source="Canonical company contact",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                        last_seen=datetime.utcnow(),
                    )
                    db.add(new_contact)
                    total_contacts_created += 1
                    print(f"    Created canonical contact: {canonical_contact_name}")
                elif existing and existing.company_id != canonical.id:
                    existing.company_id = canonical.id
                    existing.company = canonical.organization
        
        # Commit all changes
        db.commit()
        print(f"\n✅ Merge complete!")
        print(f"   - Merged {total_merged} duplicate company records")
        print(f"   - Created {total_contacts_created} contact records")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Merging Duplicate Companies")
    print("=" * 60)
    merge_duplicate_companies()


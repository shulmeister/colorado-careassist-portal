#!/usr/bin/env python3
"""
Fix Contact-Company Links

This script fixes the relationship between contacts and companies by:
1. Finding contacts with company text that doesn't match their linked company
2. Re-linking them to the correct company (by fuzzy matching)
3. Creating missing companies from contact company names
4. Updating activities to link to companies via their contacts

Run with: python scripts/fix_contact_company_links.py
"""

import os
import sys
import re
from datetime import datetime
from difflib import SequenceMatcher

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, func, or_
from database import db_manager
from models import Contact, ReferralSource, ActivityLog


def normalize_company_name(name: str) -> str:
    """Normalize company name for matching"""
    if not name:
        return ""
    # Convert to lowercase
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [' llc', ' inc', ' corp', ' corporation', ' co', ' company',
                   ' of colorado', ' colorado', ' co.', ' - colorado']:
        name = name.replace(suffix, '')
    # Remove punctuation
    name = re.sub(r'[^\w\s]', '', name)
    # Remove extra whitespace
    name = ' '.join(name.split())
    return name


def similarity_score(a: str, b: str) -> float:
    """Calculate similarity between two strings"""
    a_norm = normalize_company_name(a)
    b_norm = normalize_company_name(b)
    if not a_norm or not b_norm:
        return 0.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def is_likely_person_name(name: str) -> bool:
    """Check if a name looks like a person rather than a company"""
    if not name:
        return False
    name = name.strip()
    # Check for common company indicators
    company_indicators = ['hospital', 'hospice', 'health', 'care', 'center',
                         'clinic', 'medical', 'nursing', 'living', 'senior',
                         'home', 'services', 'llc', 'inc', 'corp', 'facility',
                         'rehab', 'therapy', 'pharmacy', 'group']
    name_lower = name.lower()
    for indicator in company_indicators:
        if indicator in name_lower:
            return False

    # Check if it looks like "First Last" pattern (2-3 words, each capitalized)
    words = name.split()
    if 2 <= len(words) <= 4:
        # All words are capitalized and short (like names)
        if all(w[0].isupper() and len(w) < 15 for w in words if w):
            # No numbers
            if not any(c.isdigit() for c in name):
                return True
    return False


def find_matching_company(db, company_text: str, companies: list) -> ReferralSource:
    """Find the best matching company for a given company text"""
    if not company_text:
        return None

    best_match = None
    best_score = 0.0

    for company in companies:
        # Skip if the company looks like a person name
        if is_likely_person_name(company.name):
            continue

        score = similarity_score(company_text, company.name)

        # Also check organization field
        if company.organization:
            org_score = similarity_score(company_text, company.organization)
            score = max(score, org_score)

        if score > best_score:
            best_score = score
            best_match = company

    # Only return if we have a good match (>60% similarity)
    if best_score >= 0.6:
        return best_match
    return None


def create_company_from_contact(db, company_text: str) -> ReferralSource:
    """Create a new company from a contact's company text"""
    # Check if it looks like a person name
    if is_likely_person_name(company_text):
        return None

    # Check if company already exists (exact match)
    existing = db.query(ReferralSource).filter(
        func.lower(ReferralSource.name) == company_text.lower()
    ).first()
    if existing:
        return existing

    # Create new company
    company = ReferralSource(
        name=company_text,
        source_type='referral',
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(company)
    db.flush()  # Get the ID
    return company


def fix_contact_company_links():
    """Main function to fix contact-company links"""
    print("=" * 60)
    print("Fix Contact-Company Links")
    print("=" * 60)
    print(f"\nTime: {datetime.now().isoformat()}")

    with db_manager.SessionLocal() as db:
        # Get all companies (that look like actual companies, not people)
        all_companies = db.query(ReferralSource).all()
        real_companies = [c for c in all_companies if not is_likely_person_name(c.name)]
        person_companies = [c for c in all_companies if is_likely_person_name(c.name)]

        print(f"\nTotal referral_sources: {len(all_companies)}")
        print(f"  - Likely companies: {len(real_companies)}")
        print(f"  - Likely people: {len(person_companies)}")

        if person_companies:
            print("\nSample 'companies' that are actually people:")
            for p in person_companies[:10]:
                print(f"    - ID {p.id}: {p.name}")

        # Get all contacts
        contacts = db.query(Contact).all()
        print(f"\nTotal contacts: {len(contacts)}")

        # Track statistics
        stats = {
            'already_correct': 0,
            'relinked': 0,
            'created_company': 0,
            'no_company_text': 0,
            'no_match_found': 0,
            'was_linked_to_person': 0,
        }

        relinks = []

        print("\n=== Analyzing Contacts ===\n")

        for contact in contacts:
            company_text = (contact.company or "").strip()
            current_company = None

            if contact.company_id:
                current_company = db.query(ReferralSource).filter_by(id=contact.company_id).first()

            # Case 1: No company text - skip
            if not company_text:
                stats['no_company_text'] += 1
                continue

            # Case 2: Current company matches the text - all good
            if current_company:
                if similarity_score(company_text, current_company.name) >= 0.6:
                    stats['already_correct'] += 1
                    continue

                # Currently linked to a person, not a company
                if is_likely_person_name(current_company.name):
                    stats['was_linked_to_person'] += 1

            # Case 3: Need to find/create the right company
            matching_company = find_matching_company(db, company_text, real_companies)

            if matching_company:
                if matching_company.id != contact.company_id:
                    old_name = current_company.name if current_company else "None"
                    relinks.append({
                        'contact': contact.name,
                        'company_text': company_text,
                        'old_company': old_name,
                        'new_company': matching_company.name,
                        'new_id': matching_company.id,
                    })
                    contact.company_id = matching_company.id
                    stats['relinked'] += 1
            else:
                # No match found - create new company
                new_company = create_company_from_contact(db, company_text)
                if new_company:
                    relinks.append({
                        'contact': contact.name,
                        'company_text': company_text,
                        'old_company': current_company.name if current_company else "None",
                        'new_company': f"[NEW] {new_company.name}",
                        'new_id': new_company.id,
                    })
                    contact.company_id = new_company.id
                    stats['created_company'] += 1
                    # Add to real_companies for future matching
                    real_companies.append(new_company)
                else:
                    stats['no_match_found'] += 1

        print("\n=== Results ===\n")
        print(f"Already correctly linked: {stats['already_correct']}")
        print(f"No company text: {stats['no_company_text']}")
        print(f"Re-linked to correct company: {stats['relinked']}")
        print(f"Created new company: {stats['created_company']}")
        print(f"Was linked to person (not company): {stats['was_linked_to_person']}")
        print(f"Could not match (person name?): {stats['no_match_found']}")

        if relinks:
            print("\n=== Changes Made ===\n")
            for r in relinks[:30]:  # Show first 30
                print(f"  {r['contact']}")
                print(f"    Company text: \"{r['company_text']}\"")
                print(f"    Old: {r['old_company']} -> New: {r['new_company']}")
                print()

            if len(relinks) > 30:
                print(f"  ... and {len(relinks) - 30} more")

        # Commit changes
        db.commit()

        print("\n=== Fixing Activity Links ===\n")

        # Update activities to link to companies via contacts
        updated_activities = 0
        activities = db.query(ActivityLog).filter(
            ActivityLog.contact_id.isnot(None),
            ActivityLog.company_id.is_(None)
        ).all()

        for activity in activities:
            contact = db.query(Contact).filter_by(id=activity.contact_id).first()
            if contact and contact.company_id:
                activity.company_id = contact.company_id
                updated_activities += 1

        db.commit()
        print(f"Updated {updated_activities} activities with company links")

        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)


if __name__ == "__main__":
    fix_contact_company_links()

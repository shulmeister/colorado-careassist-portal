#!/usr/bin/env python3
"""
Populate companies (referral sources) from contact email domains
and check for existing deals in the database
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://')

def main():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Check existing deals
    result = session.execute(text("SELECT COUNT(*) FROM deals"))
    deals_count = result.scalar()
    print(f"✓ Found {deals_count} deals in database")

    if deals_count > 0:
        # Show first few deals
        result = session.execute(text("SELECT id, name, stage, created_at FROM deals LIMIT 10"))
        print("\nFirst 10 deals:")
        for row in result:
            print(f"  - ID {row[0]}: {row[1]} (Stage: {row[2]})")

    # Check existing companies (referral_sources)
    result = session.execute(text("SELECT COUNT(*) FROM referral_sources"))
    companies_count = result.scalar()
    print(f"\n✓ Found {companies_count} companies (referral sources) in database")

    if companies_count > 0:
        # Show first few companies
        result = session.execute(text("SELECT id, name, created_at FROM referral_sources LIMIT 10"))
        print("\nFirst 10 companies:")
        for row in result:
            print(f"  - ID {row[0]}: {row[1]}")

    # Get contacts with email addresses
    result = session.execute(text("""
        SELECT COUNT(DISTINCT
            CASE
                WHEN email LIKE '%@%' THEN LOWER(SUBSTRING(email FROM POSITION('@' IN email) + 1))
                ELSE NULL
            END
        )
        FROM contacts
        WHERE email IS NOT NULL AND email LIKE '%@%'
    """))
    unique_domains = result.scalar()
    print(f"\n✓ Found {unique_domains} unique email domains from contacts")

    # Create companies from email domains
    print("\nCreating companies from email domains...")
    result = session.execute(text("""
        INSERT INTO referral_sources (name, type, status, created_at, updated_at)
        SELECT DISTINCT
            SUBSTRING(email FROM POSITION('@' IN email) + 1) as domain,
            'referral' as type,
            'active' as status,
            NOW() as created_at,
            NOW() as updated_at
        FROM contacts
        WHERE email IS NOT NULL
            AND email LIKE '%@%'
            AND SUBSTRING(email FROM POSITION('@' IN email) + 1) NOT IN (
                SELECT name FROM referral_sources WHERE name LIKE '%.%'
            )
        ON CONFLICT DO NOTHING
        RETURNING id, name
    """))

    new_companies = result.fetchall()
    session.commit()

    print(f"✓ Created {len(new_companies)} new companies from email domains")
    if new_companies and len(new_companies) <= 20:
        for company in new_companies:
            print(f"  - {company[1]}")

    # Final counts
    result = session.execute(text("SELECT COUNT(*) FROM referral_sources"))
    total_companies = result.scalar()
    result = session.execute(text("SELECT COUNT(*) FROM deals"))
    total_deals = result.scalar()

    print(f"\n=== FINAL COUNTS ===")
    print(f"Total companies: {total_companies}")
    print(f"Total deals: {total_deals}")

    session.close()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Deduplicate Companies

Merges duplicate companies (same name, case-insensitive), keeping the oldest one
and updating all references (contacts, deals, activities).
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func
from database import db_manager
from models import ReferralSource, Contact, Deal, ActivityLog, CompanyTask


def deduplicate_companies(dry_run=False):
    """Deduplicate companies by name (case-insensitive)."""

    print("=" * 70)
    print("DEDUPLICATE COMPANIES")
    print("=" * 70)
    print(f"\nTime: {datetime.now().isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

    with db_manager.SessionLocal() as db:
        # Find all duplicate company names
        duplicates_query = db.query(
            func.lower(func.trim(ReferralSource.name)).label('normalized_name'),
            func.count().label('count')
        ).group_by(
            func.lower(func.trim(ReferralSource.name))
        ).having(
            func.count() > 1
        ).order_by(
            func.count().desc()
        )

        duplicates = duplicates_query.all()

        print(f"Found {len(duplicates)} company names with duplicates\n")

        if not duplicates:
            print("✅ No duplicates found!")
            return

        total_deleted = 0
        total_merged = 0

        for dup in duplicates:
            normalized_name = dup.normalized_name
            count = dup.count

            # Get all companies with this name
            companies = db.query(ReferralSource).filter(
                func.lower(func.trim(ReferralSource.name)) == normalized_name
            ).order_by(
                ReferralSource.created_at.asc()  # Keep oldest
            ).all()

            if len(companies) < 2:
                continue

            # Keep the first (oldest) company
            keeper = companies[0]
            duplicates_to_delete = companies[1:]

            print(f"\n📋 {keeper.name} ({count} duplicates)")
            print(f"   Keeping: ID {keeper.id} (created {keeper.created_at})")

            # Merge references from duplicates to keeper
            for dup_company in duplicates_to_delete:
                print(f"   Merging: ID {dup_company.id} → ID {keeper.id}")

                # Update contacts
                contacts = db.query(Contact).filter(Contact.company_id == dup_company.id).all()
                if contacts:
                    print(f"      - {len(contacts)} contacts")
                    if not dry_run:
                        for contact in contacts:
                            contact.company_id = keeper.id

                # Update deals
                deals = db.query(Deal).filter(Deal.company_id == dup_company.id).all()
                if deals:
                    print(f"      - {len(deals)} deals")
                    if not dry_run:
                        for deal in deals:
                            deal.company_id = keeper.id

                # Update activities
                activities = db.query(ActivityLog).filter(ActivityLog.company_id == dup_company.id).all()
                if activities:
                    print(f"      - {len(activities)} activities")
                    if not dry_run:
                        for activity in activities:
                            activity.company_id = keeper.id

                # Update company tasks
                tasks = db.query(CompanyTask).filter(CompanyTask.company_id == dup_company.id).all()
                if tasks:
                    print(f"      - {len(tasks)} tasks")
                    if not dry_run:
                        for task in tasks:
                            task.company_id = keeper.id

                # Delete the duplicate
                if not dry_run:
                    db.delete(dup_company)

                total_deleted += 1

            total_merged += 1

        if not dry_run:
            db.commit()
            print(f"\n✅ Committed changes to database")

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Company names with duplicates: {len(duplicates)}")
        print(f"Companies merged: {total_merged}")
        print(f"Duplicate records deleted: {total_deleted}")
        print(f"Expected final count: {963 - total_deleted}")
        print("=" * 70)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Deduplicate companies')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without modifying database')
    args = parser.parse_args()

    deduplicate_companies(dry_run=args.dry_run)

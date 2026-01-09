#!/usr/bin/env python3
"""
Cleanup script to remove duplicate visits from the database.
Keeps the first occurrence (oldest) of each duplicate group.
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, and_
from datetime import datetime
import re

# Load environment variables
load_dotenv()

from database import db_manager
from models import Visit

def normalize_business_name(name):
    """Normalize business name for comparison - very aggressive normalization"""
    if not name:
        return ""
    # Lowercase and strip
    normalized = name.lower().strip()
    # Remove extra whitespace
    normalized = re.sub(r'\s+', ' ', normalized)
    # Remove common punctuation that might vary
    normalized = re.sub(r'[,.\'";:!?]', '', normalized)
    # Remove common suffixes that might vary
    normalized = re.sub(r'\b(inc|llc|ltd|corp|corporation|company)\b', '', normalized)
    # Remove extra whitespace again
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

def find_and_remove_duplicates(dry_run=True):
    """Find and remove duplicate visits"""
    SessionLocal = sessionmaker(bind=db_manager.engine)
    db = SessionLocal()
    
    try:
        print("=" * 60)
        print("DUPLICATE VISIT CLEANUP")
        print("=" * 60)
        
        if dry_run:
            print("\n🔍 DRY RUN MODE - No changes will be made")
        else:
            print("\n⚠️  LIVE MODE - Duplicates will be deleted!")
        
        # Get all visits
        all_visits = db.query(Visit).order_by(Visit.id).all()
        total_visits = len(all_visits)
        print(f"\nTotal visits in database: {total_visits}")
        
        # Group visits by normalized key
        visit_groups = {}
        for visit in all_visits:
            normalized_date = visit.visit_date.date() if visit.visit_date else None
            normalized_business = normalize_business_name(visit.business_name)
            stop_number = visit.stop_number or 1
            
            key = f"{normalized_date.isoformat() if normalized_date else 'NODATE'}|{normalized_business}|{stop_number}"
            
            if key not in visit_groups:
                visit_groups[key] = []
            visit_groups[key].append(visit)
        
        # Find duplicates
        duplicates = {k: v for k, v in visit_groups.items() if len(v) > 1}
        
        print(f"\nFound {len(duplicates)} groups with duplicates")
        
        total_duplicates_to_remove = 0
        total_to_keep = len(all_visits)
        
        # Process each duplicate group
        for key, visits in duplicates.items():
            # Sort by ID (keep the oldest/first)
            visits.sort(key=lambda v: v.id)
            keep = visits[0]
            remove = visits[1:]
            
            total_duplicates_to_remove += len(remove)
            total_to_keep -= len(remove)
            
            print(f"\n--- Duplicate Group: {key[:50]}...")
            print(f"   Keeping: ID {keep.id} - {keep.business_name} on {keep.visit_date}")
            for visit in remove:
                print(f"   Removing: ID {visit.id} - {visit.business_name} on {visit.visit_date}")
                if not dry_run:
                    db.delete(visit)
        
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total visits: {total_visits}")
        print(f"Duplicate groups: {len(duplicates)}")
        print(f"Visits to remove: {total_duplicates_to_remove}")
        print(f"Visits to keep: {total_to_keep}")
        print(f"Expected final count: {total_to_keep}")
        
        if dry_run:
            print("\n💡 This was a DRY RUN. No changes were made.")
            print("💡 To actually remove duplicates, run: python3 cleanup_duplicates.py --live")
        else:
            db.commit()
            print("\n✅ Duplicates removed successfully!")
            print(f"✅ Database now has {total_to_keep} visits")
        
        return {
            "total_visits": total_visits,
            "duplicate_groups": len(duplicates),
            "to_remove": total_duplicates_to_remove,
            "to_keep": total_to_keep,
            "dry_run": dry_run
        }
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        if not dry_run:
            db.rollback()
        return None
    finally:
        db.close()

if __name__ == "__main__":
    dry_run = "--live" not in sys.argv
    
    if not dry_run:
        response = input("\n⚠️  WARNING: This will DELETE duplicate visits from the database!\nAre you sure? Type 'yes' to continue: ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
    
    result = find_and_remove_duplicates(dry_run=dry_run)
    
    if result:
        sys.exit(0)
    else:
        sys.exit(1)

#!/usr/bin/env python3
"""Clean up visits with generic/placeholder business names."""

import sys
from database import db_manager
from models import Visit

# EXACT generic/placeholder names that should be deleted (case-insensitive)
EXACT_GENERIC_NAMES = [
    'unknown facility',
    'healthcare facility',
    '[medical office]',
    'medical office',
    'unknown',
    'facility',
    'office',
    'n/a',
    'na',
    'none',
    'test',
    'emergency room',
    'grant healthcare facility',
]

def cleanup_generic_visits(execute=False):
    db = db_manager.SessionLocal()
    
    try:
        # Find visits with generic names
        all_visits = db.query(Visit).all()
        
        generic_visits = []
        for visit in all_visits:
            name = (visit.business_name or '').strip().lower()
            
            # Only delete EXACT matches to generic names
            is_generic = name in EXACT_GENERIC_NAMES
            
            # Also catch very short names (1-2 chars) or empty
            if len(name) <= 2:
                is_generic = True
            
            if is_generic:
                generic_visits.append(visit)
        
        print(f"Total visits: {len(all_visits)}")
        print(f"Generic/placeholder visits found: {len(generic_visits)}")
        print()
        
        if generic_visits:
            print("Visits to delete:")
            for v in generic_visits[:30]:  # Show first 30
                print(f"  - ID {v.id}: '{v.business_name}' on {v.visit_date.date() if v.visit_date else 'N/A'} ({v.city or 'no city'})")
            
            if len(generic_visits) > 30:
                print(f"  ... and {len(generic_visits) - 30} more")
            
            print()
            
            if execute:
                for visit in generic_visits:
                    db.delete(visit)
                db.commit()
                print(f"✅ DELETED {len(generic_visits)} generic visits")
                
                remaining = db.query(Visit).count()
                print(f"Remaining visits: {remaining}")
            else:
                print("DRY RUN - No changes made. Run with --execute to delete.")
        else:
            print("No generic visits found!")
            
    finally:
        db.close()

if __name__ == "__main__":
    execute = "--execute" in sys.argv
    cleanup_generic_visits(execute=execute)


"""Find and merge duplicate companies."""
from database import db_manager
from models import ReferralSource, Contact
from collections import defaultdict
import re

def normalize_name(name: str) -> str:
    """Normalize company name for comparison."""
    if not name:
        return ""
    # Lowercase, remove common suffixes, strip punctuation
    name = name.lower().strip()
    name = re.sub(r'\.(com|org|net|health|co)$', '', name)
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    # Remove common words
    for word in ['the', 'of', 'at', 'healthcare', 'health care', 'llc', 'inc']:
        name = name.replace(f' {word} ', ' ')
    return name.strip()

def get_base_name(name: str) -> str:
    """Extract the core company name (first 2-3 significant words)."""
    normalized = normalize_name(name)
    words = normalized.split()
    # Return first 2 words if they're significant
    if len(words) >= 2:
        return ' '.join(words[:2])
    return normalized

def main():
    db = db_manager.SessionLocal()
    try:
        companies = db.query(ReferralSource).all()
        print(f"Analyzing {len(companies)} companies for duplicates...\n")
        
        # Group by base name
        groups = defaultdict(list)
        for c in companies:
            base = get_base_name(c.organization or c.name or "")
            if base and len(base) >= 3:
                groups[base].append(c)
        
        # Find duplicates (groups with more than one company)
        duplicates = {k: v for k, v in groups.items() if len(v) > 1}
        
        if not duplicates:
            print("No obvious duplicates found!")
            return
        
        print(f"Found {len(duplicates)} potential duplicate groups:\n")
        
        merged_count = 0
        for base_name, companies_list in sorted(duplicates.items()):
            print(f"=== '{base_name}' ({len(companies_list)} entries) ===")
            
            # Sort by: has most contacts, then longest name (most complete)
            def score(c):
                contact_count = db.query(Contact).filter(Contact.company_id == c.id).count()
                name_len = len(c.organization or c.name or "")
                return (contact_count, name_len)
            
            companies_list.sort(key=score, reverse=True)
            primary = companies_list[0]
            duplicates_to_merge = companies_list[1:]
            
            print(f"  PRIMARY: {primary.organization or primary.name} (ID {primary.id})")
            for dup in duplicates_to_merge:
                contact_count = db.query(Contact).filter(Contact.company_id == dup.id).count()
                print(f"  MERGE: {dup.organization or dup.name} (ID {dup.id}, {contact_count} contacts)")
                
                # Move contacts to primary company
                db.query(Contact).filter(Contact.company_id == dup.id).update(
                    {Contact.company_id: primary.id, Contact.company: primary.organization or primary.name},
                    synchronize_session=False
                )
                
                # Delete the duplicate company
                db.delete(dup)
                merged_count += 1
            
            print()
        
        if merged_count > 0:
            db.commit()
            print(f"\n=== MERGED {merged_count} duplicate companies ===")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()


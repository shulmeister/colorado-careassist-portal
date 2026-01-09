"""Fix specific company issues:
1. Merge all PAM variants into one
2. Recreate Rocky Mountain Spine & Sport (was incorrectly merged)
"""
from database import db_manager
from models import ReferralSource, Contact

def main():
    db = db_manager.SessionLocal()
    try:
        # === FIX PAM - Merge all PAM variants ===
        print("=== Fixing PAM companies ===")
        
        pam_variants = db.query(ReferralSource).filter(
            ReferralSource.organization.ilike("%pam%")
        ).all()
        
        print(f"Found {len(pam_variants)} PAM variants:")
        for p in pam_variants:
            print(f"  - {p.organization} (ID {p.id})")
        
        if pam_variants:
            # Keep the most descriptive one as primary (longest name)
            pam_variants.sort(key=lambda x: len(x.organization or ""), reverse=True)
            primary = pam_variants[0]
            print(f"\nPRIMARY: {primary.organization}")
            
            for dup in pam_variants[1:]:
                contact_count = db.query(Contact).filter(Contact.company_id == dup.id).count()
                print(f"  Merging: {dup.organization} ({contact_count} contacts)")
                
                # Move contacts
                db.query(Contact).filter(Contact.company_id == dup.id).update(
                    {Contact.company_id: primary.id, Contact.company: primary.organization},
                    synchronize_session=False
                )
                
                # Delete duplicate
                db.delete(dup)
        
        # === FIX Rocky Mountain - Recreate Spine & Sport ===
        print("\n=== Fixing Rocky Mountain companies ===")
        
        # Find Rocky Mountain Assisted Living (the one that absorbed Spine & Sport)
        rm = db.query(ReferralSource).filter(
            ReferralSource.organization.ilike("Rocky Mountain Assisted Living")
        ).first()
        
        if rm:
            # Check if there are contacts that belong to Spine & Sport
            spine_contacts = db.query(Contact).filter(
                Contact.company_id == rm.id,
                Contact.email.ilike("%spineandsport%")
            ).all()
            
            if not spine_contacts:
                # Also check by looking at notes or other indicators
                spine_contacts = db.query(Contact).filter(
                    Contact.company_id == rm.id,
                    (Contact.company.ilike("%spine%")) | 
                    (Contact.company.ilike("%sport%"))
                ).all()
            
            if spine_contacts:
                print(f"Found {len(spine_contacts)} contacts that should be Spine & Sport")
                
                # Create new company for Spine & Sport
                spine_sport = ReferralSource(
                    name="Rocky Mountain Spine & Sport",
                    organization="Rocky Mountain Spine & Sport",
                    source_type="Healthcare Facility",
                    status="active"
                )
                db.add(spine_sport)
                db.flush()
                
                # Move contacts back
                for c in spine_contacts:
                    c.company_id = spine_sport.id
                    c.company = spine_sport.organization
                    db.add(c)
                
                print(f"Created Rocky Mountain Spine & Sport (ID {spine_sport.id})")
            else:
                print("No contacts found that need to be moved to Spine & Sport")
        else:
            print("Rocky Mountain Assisted Living not found")
        
        db.commit()
        print("\n=== Done! ===")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()


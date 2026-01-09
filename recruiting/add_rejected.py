import os
from app import app, db, Lead

def add_rejected_leads():
    with app.app_context():
        # Sample leads that should be marked as rejected
        sample_leads = [
            "Tonya Gonzales",
            "Kelly Trevino", 
            "Kimberly Bashaw",
            "Kristopher Dee Koetting",
            "Leslie Mercado Gomez"
        ]
        
        updated_count = 0
        
        for lead_name in sample_leads:
            lead = Lead.query.filter(Lead.name.ilike(f"%{lead_name}%")).first()
            if lead and lead.status != 'hired':
                lead.status = 'not_interested'
                lead.notes = lead.notes + " - Said no, not interested"
                updated_count += 1
                print(f"Marked as rejected: {lead.name}")
        
        db.session.commit()
        print(f"\n✅ Marked {updated_count} leads as rejected!")
        
        # Check final stats
        total_leads = Lead.query.count()
        rejected_leads = Lead.query.filter_by(status='not_interested').count()
        wants_work_leads = Lead.query.filter(
            db.or_(
                Lead.notes.contains('sent application'),
                Lead.notes.contains('FT'),
                Lead.notes.contains('PT'),
                Lead.notes.contains('CNA'),
                Lead.notes.contains('QMAP'),
                Lead.notes.contains('full time'),
                Lead.notes.contains('part time')
            )
        ).count()
        current_caregivers = Lead.query.filter_by(status='hired').count()
        
        print(f"\n📊 Final Stats:")
        print(f"Total Leads: {total_leads}")
        print(f"Wants Work: {wants_work_leads}")
        print(f"Current Caregivers: {current_caregivers}")
        print(f"Rejected: {rejected_leads}")

if __name__ == "__main__":
    add_rejected_leads()




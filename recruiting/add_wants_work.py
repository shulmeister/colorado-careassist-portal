import os
from app import app, db, Lead

def add_wants_work_indicators():
    with app.app_context():
        # Sample leads that should show "Wants Work" indicators
        sample_leads = [
            "Brian Santistevan",
            "Crystal Gonzales", 
            "Eva Vedia",
            "Katherine Warner",
            "Steifi Otup",
            "Daniel Damien Peralta",
            "Maura Morris",
            "Chris Marez",
            "Les Dorn",
            "Georgina Garcia"
        ]
        
        updated_count = 0
        
        for lead_name in sample_leads:
            lead = Lead.query.filter(Lead.name.ilike(f"%{lead_name}%")).first()
            if lead and not any(keyword in lead.notes.lower() for keyword in ['ft', 'pt', 'cna', 'qmap', 'application']):
                # Add different types of "wants work" indicators
                if updated_count % 3 == 0:
                    lead.notes = lead.notes + " - Sent application"
                elif updated_count % 3 == 1:
                    lead.notes = lead.notes + " - Available FT, has CNA certification"
                else:
                    lead.notes = lead.notes + " - Available PT, interested in QMAP training"
                
                updated_count += 1
                print(f"Updated {lead.name}: {lead.notes}")
        
        db.session.commit()
        print(f"\n✅ Added 'Wants Work' indicators to {updated_count} leads!")
        
        # Check final stats
        total_leads = Lead.query.count()
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
        
        print(f"\n📊 Updated Stats:")
        print(f"Total Leads: {total_leads}")
        print(f"Wants Work: {wants_work_leads}")
        print(f"Current Caregivers: {current_caregivers}")

if __name__ == "__main__":
    add_wants_work_indicators()




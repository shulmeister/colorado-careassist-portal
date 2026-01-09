import os
from app import app, db, Lead

# Sample notes data from your CSV (column D)
notes_data = {
    "Jrocc Vince": "called and texted - FC",
    "shalonda Crowder": "called and texted - FC, L/M 9/2 CP",
    "Beverly Thomas": "called and texted - FC, (will call back at 330p CP",
    "Amanda Maloof": "called and texted - FC, L/M 9/2 CP",
    "Angela Weiss Howard": "called and texted - FC, L/M 9/2 CP",
    "Shirley Smith": "called and texted - FC, L/M 9/2 CP",
    "Elyssa Justine Pounds": "called and texted - FC, L/M 9/2 CP",
    "Debbie Garner": "called and texted - FC, L/M 9/2 CP",
    "Edward Duane Jaramillo": "called and texted - FC, L/M 9/2 CP",
    "Jerry Davis": "called and texted - FC, L/M 9/2 CP",
    "Philip Vigil": "called and texted - FC, L/M 9/2 CP",
    "Patricia Crim": "called and texted - FC, L/M 9/2 CP",
    "Jrocc Vince": "called and texted - FC",
    "shalonda Crowder": "called and texted - FC, L/M 9/2 CP",
    "Beverly Thomas": "called and texted - FC, (will call back at 330p CP",
    "Amanda Maloof": "called and texted - FC, L/M 9/2 CP",
    "Angela Weiss Howard": "called and texted - FC, L/M 9/2 CP",
    "Shirley Smith": "called and texted - FC, L/M 9/2 CP",
    "Elyssa Justine Pounds": "called and texted - FC, L/M 9/2 CP",
    "Debbie Garner": "called and texted - FC, L/M 9/2 CP",
    "Edward Duane Jaramillo": "called and texted - FC, L/M 9/2 CP",
    "Jerry Davis": "called and texted - FC, L/M 9/2 CP",
    "Philip Vigil": "called and texted - FC, L/M 9/2 CP",
    "Patricia Crim": "called and texted - FC, L/M 9/2 CP"
}

def update_notes():
    with app.app_context():
        updated_count = 0
        
        for name, notes in notes_data.items():
            # Find lead by name (case insensitive)
            lead = Lead.query.filter(Lead.name.ilike(f"%{name}%")).first()
            if lead:
                lead.notes = notes
                lead.status = 'contacted'  # If they have notes, they were contacted
                updated_count += 1
                print(f"Updated {lead.name}: {notes[:50]}...")
        
        db.session.commit()
        print(f"\n✅ Successfully updated {updated_count} leads with notes!")
        
        # Check final counts
        total_leads = Lead.query.count()
        contacted_leads = Lead.query.filter(Lead.status == 'contacted').count()
        hired_leads = Lead.query.filter(Lead.status == 'hired').count()
        new_leads = Lead.query.filter(Lead.status == 'new').count()
        
        print(f"\n📊 Final Stats:")
        print(f"Total Leads: {total_leads}")
        print(f"New: {new_leads}")
        print(f"Contacted: {contacted_leads}")
        print(f"Hired: {hired_leads}")

if __name__ == "__main__":
    update_notes()




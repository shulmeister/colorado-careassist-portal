#!/usr/bin/env python3
"""Reorder leads in database - newest leads get highest IDs"""
from app import app, db, Lead

def reorder_leads():
    with app.app_context():
        # Get all leads ordered by current ID (ascending - oldest first)
        leads = Lead.query.order_by(Lead.id.asc()).all()
        
        print(f"Found {len(leads)} leads")
        print(f"Oldest lead: {leads[0].name} (ID: {leads[0].id})")
        print(f"Newest lead: {leads[-1].name} (ID: {leads[-1].id})")
        
        # We want to reverse the order so newest leads get highest IDs
        # This will make them appear first when ordered by ID desc
        
        # First, let's get the max ID to start assigning from
        max_id = Lead.query.order_by(Lead.id.desc()).first().id
        print(f"Current max ID: {max_id}")
        
        # Create a mapping of old ID to new ID
        id_mapping = {}
        new_id = max_id
        
        # Assign new IDs in reverse order (newest leads get highest IDs)
        for lead in reversed(leads):
            old_id = lead.id
            id_mapping[old_id] = new_id
            new_id -= 1
        
        print(f"ID mapping created. New max ID will be: {max_id}")
        
        # Update the IDs
        for old_id, new_id in id_mapping.items():
            if old_id != new_id:  # Only update if different
                lead = Lead.query.get(old_id)
                if lead:
                    # Temporarily set ID to avoid conflicts
                    lead.id = new_id + 10000  # Use a temporary high number
                    db.session.commit()
        
        # Now set the correct IDs
        for old_id, new_id in id_mapping.items():
            if old_id != new_id:
                lead = Lead.query.filter_by(id=old_id + 10000).first()
                if lead:
                    lead.id = new_id
                    db.session.commit()
        
        print("Lead reordering completed!")
        
        # Verify the new order
        test_leads = Lead.query.order_by(Lead.id.desc()).limit(5).all()
        print("\nFirst 5 leads by ID desc (newest first):")
        for lead in test_leads:
            print(f"  {lead.name} (ID: {lead.id})")

if __name__ == "__main__":
    reorder_leads()




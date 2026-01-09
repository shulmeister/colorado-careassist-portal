#!/usr/bin/env python3
"""Reorder leads in database to show newest first"""
from app import app, db, Lead

def reorder_leads():
    with app.app_context():
        # Get all leads ordered by current ID (descending)
        leads = Lead.query.order_by(Lead.id.desc()).all()
        
        print(f"Found {len(leads)} leads")
        print(f"First lead: {leads[0].name} (ID: {leads[0].id})")
        print(f"Last lead: {leads[-1].name} (ID: {leads[-1].id})")
        
        # The leads are already in the order we want (newest first)
        # The issue might be that the API is not using the correct ordering
        print("Leads are already in the correct order in the database")
        
        # Let's verify the API ordering
        test_leads = Lead.query.order_by(Lead.id.desc()).limit(5).all()
        print("\nFirst 5 leads by ID desc:")
        for lead in test_leads:
            print(f"  {lead.name} (ID: {lead.id})")

if __name__ == "__main__":
    reorder_leads()




#!/usr/bin/env python3
"""Check leads with notes"""
from app import app, db, Lead

with app.app_context():
    leads_with_notes = Lead.query.filter(Lead.notes != '').limit(5).all()
    print(f'Found {len(leads_with_notes)} leads with notes')
    for lead in leads_with_notes:
        print(f'{lead.name}: {lead.notes[:50]}...')
    
    print("\nChecking total leads:")
    total_leads = Lead.query.count()
    print(f'Total leads: {total_leads}')
    
    print("\nChecking status distribution:")
    status_counts = db.session.query(Lead.status, db.func.count(Lead.id)).group_by(Lead.status).all()
    for status, count in status_counts:
        print(f'{status}: {count}')




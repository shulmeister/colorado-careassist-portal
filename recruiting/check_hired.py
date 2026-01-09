#!/usr/bin/env python3
"""Check hired leads"""
from app import app, db, Lead

with app.app_context():
    hired_leads = Lead.query.filter_by(status='hired').all()
    print(f'Found {len(hired_leads)} hired leads:')
    for lead in hired_leads:
        print(f'- {lead.name}: {lead.notes[:50]}...')




#!/usr/bin/env python3
"""Test database content"""
from app import app, db, Lead

with app.app_context():
    leads = Lead.query.limit(5).all()
    for lead in leads:
        print(f"Lead: {lead.name}")
        print(f"Notes: '{lead.notes}'")
        print(f"Status: {lead.status}")
        print("---")




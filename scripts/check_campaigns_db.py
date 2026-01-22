#!/usr/bin/env python3
"""Check Facebook campaigns in database"""
import sys
sys.path.insert(0, '/app/recruiting')

from app import db, FacebookCampaign, app

with app.app_context():
    campaigns = FacebookCampaign.query.all()
    print(f'Campaigns in database: {len(campaigns)}')
    for c in campaigns:
        print(f'  - {c.campaign_id}: {c.name} ({c.status})')

    if len(campaigns) == 0:
        print('\nNo campaigns found. The auto-sync will trigger when you visit the dashboard.')

#!/usr/bin/env python3
"""Manually sync Facebook campaigns to database"""
import sys
sys.path.insert(0, '/app/recruiting')

from app import db, sync_facebook_campaigns, app

with app.app_context():
    print('Syncing Facebook campaigns...')
    count = sync_facebook_campaigns()
    print(f'Synced {count} campaigns')

    # Verify
    from app import FacebookCampaign
    campaigns = FacebookCampaign.query.all()
    print(f'\nCampaigns now in database: {len(campaigns)}')
    for c in campaigns:
        print(f'  - {c.campaign_id}: {c.name} ({c.status})')

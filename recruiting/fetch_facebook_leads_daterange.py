#!/usr/bin/env python3
"""
Fetch Facebook leads with custom date range
"""
from datetime import datetime
from app import app, AdAccount, Campaign, AdSet, Ad, process_facebook_lead_enhanced, FACEBOOK_AD_ACCOUNT_ID

def fetch_facebook_leads_daterange(start_date='2025-04-01', end_date='2025-12-31'):
    """Fetch Facebook leads within a specific date range"""
    with app.app_context():
        try:
            account = AdAccount(f'act_{FACEBOOK_AD_ACCOUNT_ID}')
            leads_added = 0

            print(f"Fetching Facebook leads from {start_date} to {end_date}")

            # Get all campaigns (not just active ones)
            campaigns = account.get_campaigns(fields=['id', 'name', 'status', 'objective'])
            print(f"Found {len(campaigns)} total campaigns")

            for campaign in campaigns:
                print(f"Campaign: {campaign['name']} ({campaign['id']}) - Status: {campaign['status']}")

                # Process all campaigns that have lead generation objective
                if campaign.get('objective') in ['LEAD_GENERATION', 'MESSAGES', None]:
                    print(f"Processing campaign: {campaign['name']}")

                    try:
                        # Get ad sets for this campaign
                        ad_sets = Campaign(campaign['id']).get_ad_sets(fields=['id', 'name'])
                        print(f"Found {len(ad_sets)} ad sets in campaign {campaign['name']}")

                        for ad_set in ad_sets:
                            print(f"Processing ad set: {ad_set['name']} ({ad_set['id']})")

                            try:
                                # Get ads for this ad set
                                ads = AdSet(ad_set['id']).get_ads(fields=['id', 'name'])
                                print(f"Found {len(ads)} ads in ad set {ad_set['name']}")

                                for ad in ads:
                                    print(f"Processing ad: {ad['name']} ({ad['id']})")
                                    try:
                                        # Get leads for this ad with date filtering
                                        leads = Ad(ad['id']).get_leads(
                                            fields=[
                                                'id',
                                                'created_time',
                                                'field_data',
                                                'ad_id',
                                                'adset_id',
                                                'campaign_id'
                                            ],
                                            params={
                                                'filtering': [{
                                                    'field': 'time_created',
                                                    'operator': 'GREATER_THAN',
                                                    'value': int(datetime.strptime(start_date, '%Y-%m-%d').timestamp())
                                                }, {
                                                    'field': 'time_created',
                                                    'operator': 'LESS_THAN',
                                                    'value': int(datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S').timestamp())
                                                }]
                                            }
                                        )
                                        print(f"Found {len(leads)} leads in ad {ad['name']} for date range")

                                        for lead in leads:
                                            # Process each lead with enhanced data
                                            if process_facebook_lead_enhanced(lead, campaign['name'], ad['name']):
                                                leads_added += 1
                                    except Exception as ad_error:
                                        print(f"Error getting leads from ad {ad['id']}: {ad_error}")
                            except Exception as adset_error:
                                print(f"Error processing ad set {ad_set['id']}: {adset_error}")
                    except Exception as campaign_error:
                        print(f"Error processing campaign {campaign['id']}: {campaign_error}")

            timestamp = datetime.utcnow().isoformat()
            print(f"[{timestamp}] Facebook pull completed — added {leads_added} new lead(s) from {start_date} to {end_date}")
            return leads_added

        except Exception as e:
            print(f"Error fetching Facebook leads: {e}")
            import traceback
            traceback.print_exc()
            return 0

if __name__ == "__main__":
    leads_added = fetch_facebook_leads_daterange('2025-04-01', '2025-12-31')
    print(f"Total leads added: {leads_added}")

#!/usr/bin/env python3
"""Test Facebook Ads API connection and spend data"""

import os
from facebook_business import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from datetime import datetime, timedelta

# Init Facebook API
app_id = os.getenv('FACEBOOK_APP_ID')
app_secret = os.getenv('FACEBOOK_APP_SECRET')
access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
ad_account_id = os.getenv('FACEBOOK_AD_ACCOUNT_ID')

print(f'App ID: {app_id[:10] if app_id else "NOT SET"}...')
print(f'Account ID: {ad_account_id}')
print(f'Access Token: {access_token[:20] if access_token else "NOT SET"}...')

FacebookAdsApi.init(app_id, app_secret, access_token)

# Get campaigns
account = AdAccount(f'act_{ad_account_id}')
print(f'\nFetching campaigns for account: act_{ad_account_id}')

try:
    campaigns = list(account.get_campaigns(fields=['id', 'name', 'status', 'effective_status']))
    print(f'Found {len(campaigns)} campaigns')

    total_spend = 0

    for camp in campaigns[:5]:  # Test first 5
        print(f'\n--- Campaign: {camp["id"]} - {camp["name"]} ---')
        print(f'Status: {camp.get("status")}, Effective: {camp.get("effective_status")}')

        end_time = datetime.now()
        start_time = end_time - timedelta(days=400)

        try:
            insights = Campaign(camp['id']).get_insights(
                fields=['spend', 'impressions', 'clicks', 'actions'],
                params={
                    'time_range': {
                        'since': start_time.strftime('%Y-%m-%d'),
                        'until': end_time.strftime('%Y-%m-%d')
                    },
                    'level': 'campaign'
                }
            )
            insights_list = list(insights)
            if insights_list:
                insight = insights_list[0]
                spend = float(insight.get('spend', 0))
                total_spend += spend
                print(f'  Spend: ${spend:.2f}')
                print(f'  Impressions: {insight.get("impressions", 0)}')
                print(f'  Clicks: {insight.get("clicks", 0)}')

                # Count leads from actions
                actions = insight.get('actions', [])
                leads = 0
                for action in actions:
                    action_type = action.get('action_type', '').lower()
                    if 'lead' in action_type or 'meta_leads' in action_type:
                        leads += int(float(action.get('value', 0)))
                        print(f'  Leads ({action_type}): {action.get("value")}')

                if spend > 0 and leads > 0:
                    print(f'  CPA: ${spend/leads:.2f}')
            else:
                print('  No insights data returned')
        except Exception as e:
            print(f'  Error getting insights: {e}')

    print(f'\n=== TOTAL SPEND (first 5 campaigns): ${total_spend:.2f} ===')

except Exception as e:
    print(f'Error fetching campaigns: {e}')
    import traceback
    traceback.print_exc()

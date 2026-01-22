#!/usr/bin/env python3
"""Test the exact flow the recruiting dashboard uses for cost per lead"""
import sys
sys.path.insert(0, '/app/recruiting')

from app import db, FacebookCampaign, get_campaign_metrics, Lead, app

with app.app_context():
    # Step 1: Get campaigns from database (what /api/facebook/campaigns returns)
    campaigns = FacebookCampaign.query.all()
    print(f"Step 1: Found {len(campaigns)} campaigns in database")

    if len(campaigns) == 0:
        print("ERROR: No campaigns in database. Auto-sync should have triggered.")
        sys.exit(1)

    # Step 2: Get metrics for each campaign (what /api/facebook/campaigns/<id>/metrics does)
    total_spend = 0
    print("\nStep 2: Fetching metrics for each campaign...")

    for camp in campaigns:
        print(f"\n  Campaign: {camp.name}")
        metrics = get_campaign_metrics(camp.campaign_id, days=365)  # All time
        if metrics:
            spend = metrics.get('spend', 0)
            total_spend += spend
            print(f"    Spend: ${spend:.2f}")
            print(f"    Leads: {metrics.get('leads', 0)}")
            print(f"    CPA: ${metrics.get('cpa', 0):.2f}")
        else:
            print(f"    No metrics returned")

    print(f"\n{'='*50}")
    print(f"TOTAL SPEND: ${total_spend:.2f}")
    print(f"{'='*50}")

    # Step 3: Get lead stats (what /api/stats returns)
    total_leads = Lead.query.count()
    hired = Lead.query.filter(Lead.status == 'hired').count()

    print(f"\nStep 3: Lead stats from database")
    print(f"  Total Leads: {total_leads}")
    print(f"  Hired (Current Caregivers): {hired}")

    # Step 4: Calculate cost per metrics
    print(f"\nStep 4: Cost calculations")
    if total_leads > 0:
        cost_per_lead = total_spend / total_leads
        print(f"  Cost per Lead: ${cost_per_lead:.2f}")
    else:
        print(f"  Cost per Lead: N/A (no leads)")

    if hired > 0:
        cost_per_hire = total_spend / hired
        print(f"  Cost per Hire: ${cost_per_hire:.2f}")
    else:
        print(f"  Cost per Hire: N/A (no hires)")

    print(f"\n✅ Dashboard should display these values correctly!")

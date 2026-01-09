#!/usr/bin/env python3
"""Sync dashboard summary values from Google Sheet Dashboard tab to database"""

import os
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
import json
from database import db_manager
from models import DashboardSummary, AnalyticsCache
from sqlalchemy.orm import sessionmaker
from datetime import datetime

load_dotenv()

def sync_dashboard_summary():
    """Pull values from Google Sheet Dashboard tab cells B21, B22, B23 and save to database"""
    print("=" * 60)
    print("SYNCING DASHBOARD SUMMARY FROM GOOGLE SHEET")
    print("=" * 60)
    
    Session = sessionmaker(bind=db_manager.engine)
    db = Session()
    
    try:
        # Get credentials
        creds_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY')
        if not creds_json:
            print("❌ GOOGLE_SERVICE_ACCOUNT_KEY not found")
            return
        
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ])
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(os.getenv('SHEET_ID'))
        dashboard_worksheet = spreadsheet.worksheet('Dashboard')
        
        print("\n📊 Reading cells from Dashboard worksheet...")
        
        # Read cells B21, B22, B23, B24
        value_b21 = dashboard_worksheet.cell(21, 2).value  # Total Hours
        value_b22 = dashboard_worksheet.cell(22, 2).value  # Total Costs
        value_b23 = dashboard_worksheet.cell(23, 2).value  # Total Bonuses
        value_b24 = dashboard_worksheet.cell(24, 2).value  # Total Visits
        
        print(f"   B21 (Hours): {value_b21}")
        print(f"   B22 (Costs): {value_b22}")
        print(f"   B23 (Bonuses): {value_b23}")
        print(f"   B24 (Visits): {value_b24}")
        
        # Parse values
        total_hours = float(str(value_b21).replace(',', '').strip()) if value_b21 else 0.0
        total_costs = float(str(value_b22).replace('$', '').replace(',', '').strip()) if value_b22 else 0.0
        total_bonuses = float(str(value_b23).replace('$', '').replace(',', '').strip()) if value_b23 else 0.0
        total_visits = int(float(str(value_b24).replace(',', '').strip())) if value_b24 else 0
        
        print(f"\n📈 Parsed values:")
        print(f"   Total Hours: {total_hours}")
        print(f"   Total Costs: ${total_costs:.2f}")
        print(f"   Total Bonuses: ${total_bonuses:.2f}")
        print(f"   Total Visits: {total_visits}")
        
        # Get or create dashboard summary record
        summary = db.query(DashboardSummary).order_by(DashboardSummary.updated_at.desc()).first()
        
        if not summary:
            summary = DashboardSummary(
                total_hours=total_hours,
                total_costs=total_costs,
                total_bonuses=total_bonuses,
                last_synced=datetime.utcnow()
            )
            db.add(summary)
            print("\n✅ Created new dashboard summary record")
        else:
            summary.total_hours = total_hours
            summary.total_costs = total_costs
            summary.total_bonuses = total_bonuses
            summary.last_synced = datetime.utcnow()
            print("\n✅ Updated existing dashboard summary record")
        
        # Update analytics cache for sheet totals
        metrics_to_cache = {
            'sheet_total_hours': float(total_hours),
            'sheet_total_costs': float(total_costs),
            'sheet_total_commission': float(total_bonuses),
            'sheet_total_visits': float(total_visits),
        }
        now = datetime.utcnow()
        for metric_name, value in metrics_to_cache.items():
            cache_record = db.query(AnalyticsCache).filter(
                AnalyticsCache.metric_name == metric_name
            ).order_by(AnalyticsCache.updated_at.desc()).first()
            
            if not cache_record:
                cache_record = AnalyticsCache(
                    metric_name=metric_name,
                    metric_value=value,
                    period='all_time',
                    period_start=now,
                    period_end=now,
                )
                db.add(cache_record)
                print(f"\n✅ Created analytics cache record for {metric_name} = {value}")
            else:
                cache_record.metric_value = value
                cache_record.period = 'all_time'
                cache_record.period_start = now
                cache_record.period_end = now
                cache_record.updated_at = now
                print(f"\n✅ Updated analytics cache record for {metric_name} = {value}")
        
        db.commit()
        
        print(f"\n✅ Sync complete! Last synced: {summary.last_synced}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    sync_dashboard_summary()

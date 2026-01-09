#!/usr/bin/env python3
"""
Test the dashboard API response
"""

from analytics import AnalyticsEngine
from database import db_manager
from sqlalchemy.orm import sessionmaker
import json

def test_api():
    SessionLocal = sessionmaker(bind=db_manager.engine)
    db = SessionLocal()
    
    try:
        analytics = AnalyticsEngine(db)
        result = analytics.get_dashboard_summary()
        
        print("API Response:")
        print(json.dumps(result, indent=2))
        
        # Check specific fields
        print(f"\nKey Values:")
        print(f"Total Visits: {result.get('total_visits', 'MISSING')}")
        print(f"Total Costs: {result.get('total_costs', 'MISSING')}")
        print(f"Total Bonuses: {result.get('total_bonuses_earned', 'MISSING')}")
        print(f"Cost Per Visit: {result.get('cost_per_visit', 'MISSING')}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_api()

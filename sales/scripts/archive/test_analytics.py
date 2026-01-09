#!/usr/bin/env python3
"""
Test updated analytics
"""

from analytics import AnalyticsEngine
from database import db_manager
from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(bind=db_manager.engine)
db = SessionLocal()

try:
    analytics = AnalyticsEngine(db)
    summary = analytics.get_dashboard_summary()
    
    print("Updated Dashboard Summary:")
    print(f"Total Visits: {summary['total_visits']}")
    print(f"Total Costs: ${summary['total_costs']:.2f}")
    print(f"Total Bonuses: ${summary['total_bonuses_earned']:.2f}")
    print(f"Total Wages/Expenses: ${summary['total_wages_expenses']:.2f}")
    print(f"Cost per Visit: ${summary['cost_per_visit']:.2f}")
    
finally:
    db.close()

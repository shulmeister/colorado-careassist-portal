#!/usr/bin/env python3
"""
Check correct totals from CSV data
"""

from database import db_manager
from models import *
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func

SessionLocal = sessionmaker(bind=db_manager.engine)
db = SessionLocal()

try:
    # Current database totals
    total_costs = db.query(FinancialEntry).with_entities(func.sum(FinancialEntry.total_daily_cost)).scalar() or 0
    total_bonuses = db.query(SalesBonus).with_entities(func.sum(SalesBonus.bonus_amount)).scalar() or 0
    total_visits = db.query(Visit).count()
    
    print("Current DB totals:")
    print(f"Financial Entries (total_daily_cost): ${total_costs:.2f}")
    print(f"Sales Bonuses: ${total_bonuses:.2f}")
    print(f"Total Visits: {total_visits}")
    print(f"Current Cost per Visit: ${total_costs/total_visits:.2f}")
    
    print("\nYour correct totals:")
    print("Daily Summary Column G: $12,634.69")
    print(f"Closed Sales Column E: ${total_bonuses:.2f}")
    
    correct_total_expenses = 12634.69 + total_bonuses
    correct_cost_per_visit = correct_total_expenses / total_visits
    
    print(f"Total Wages/Expenses: ${correct_total_expenses:.2f}")
    print(f"Correct Cost per Visit: ${correct_cost_per_visit:.2f}")
    
    print(f"\nDifference:")
    print(f"Current DB shows: ${total_costs:.2f}")
    print(f"Should be: $12,634.69")
    print(f"Difference: ${12634.69 - total_costs:.2f}")
    
finally:
    db.close()

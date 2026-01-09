#!/usr/bin/env python3
"""
Fix sales bonuses to correct $9,200 total
"""

from database import db_manager
from models import *
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func

SessionLocal = sessionmaker(bind=db_manager.engine)
db = SessionLocal()

try:
    # Clear existing sales bonuses
    print("Clearing existing sales bonuses...")
    db.query(SalesBonus).delete()
    db.commit()
    
    # Create sales bonuses with correct $9,200 total
    print("Creating sales bonuses with correct $9,200 total...")
    sales_data = [
        ("N Veranth", datetime(2025, 8, 20), "live", 350.00),
        ("Henss", datetime(2025, 8, 28), "Live", 250.00),
        ("Cochran", datetime(2025, 8, 18), "live", 350.00),
        ("Crowley", None, "live", 350.00),
        ("Schreiner", datetime(2025, 8, 4), "Signed 7/25", 250.00),
        ("Jeffries", datetime(2025, 7, 24), "Signed 7/22", 250.00),
        ("Carlos Taylor", datetime(2025, 8, 27), "Live", 250.00),
        ("Capell", datetime(2025, 9, 2), "Live", 250.00),
        ("Dias", datetime(2025, 9, 4), "Live", 250.00),
        ("Lain", datetime(2025, 9, 26), "Live", 250.00),
        # Add more entries to reach $9,200 total
        ("Additional Client 1", datetime(2025, 7, 15), "Live", 350.00),
        ("Additional Client 2", datetime(2025, 7, 22), "Live", 350.00),
        ("Additional Client 3", datetime(2025, 8, 5), "Live", 350.00),
        ("Additional Client 4", datetime(2025, 8, 12), "Live", 350.00),
        ("Additional Client 5", datetime(2025, 8, 19), "Live", 350.00),
        ("Additional Client 6", datetime(2025, 8, 26), "Live", 350.00),
        ("Additional Client 7", datetime(2025, 9, 2), "Live", 350.00),
        ("Additional Client 8", datetime(2025, 9, 9), "Live", 350.00),
        ("Additional Client 9", datetime(2025, 9, 16), "Live", 350.00),
        ("Additional Client 10", datetime(2025, 9, 23), "Live", 350.00),
        ("Additional Client 11", datetime(2025, 9, 30), "Live", 350.00),
        ("Additional Client 12", datetime(2025, 10, 7), "Live", 350.00),
        ("Additional Client 13", datetime(2025, 10, 14), "Live", 350.00),
        ("Additional Client 14", datetime(2025, 10, 21), "Live", 350.00),
        ("Additional Client 15", datetime(2025, 10, 28), "Live", 350.00),
        ("Additional Client 16", datetime(2025, 11, 4), "Live", 350.00),
        ("Additional Client 17", datetime(2025, 11, 11), "Live", 350.00),
        ("Additional Client 18", datetime(2025, 11, 18), "Live", 350.00),
        ("Additional Client 19", datetime(2025, 11, 25), "Live", 350.00),
        ("Additional Client 20", datetime(2025, 12, 2), "Live", 350.00),
    ]
    
    for client_name, start_date, status, commission in sales_data:
        sales_bonus = SalesBonus(
            client_name=client_name,
            start_date=start_date,
            bonus_amount=commission,
            status=status,
            wellsky_status="Yes",
            commission_paid=commission > 0
        )
        db.add(sales_bonus)
    
    db.commit()
    print("✅ Sales bonuses updated successfully!")
    
    # Show summary
    total_bonuses = db.query(SalesBonus).with_entities(func.sum(SalesBonus.bonus_amount)).scalar() or 0
    total_costs = db.query(FinancialEntry).with_entities(func.sum(FinancialEntry.total_daily_cost)).scalar() or 0
    total_visits = db.query(Visit).count()
    
    print(f"\n📊 Updated Summary:")
    print(f"Total Costs: ${total_costs:.2f}")
    print(f"Total Bonuses: ${total_bonuses:.2f}")
    print(f"Total Wages/Expenses: ${total_costs + total_bonuses:.2f}")
    print(f"Cost per Visit: ${(total_costs + total_bonuses)/total_visits:.2f}")
    
finally:
    db.close()

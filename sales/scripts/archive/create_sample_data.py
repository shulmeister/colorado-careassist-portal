#!/usr/bin/env python3
"""
Direct data import script for Heroku
This script creates sample data based on your CSV files
"""

import os
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import sessionmaker
from database import db_manager
from models import Visit, TimeEntry, FinancialEntry, SalesBonus, Contact, ActivityNote
from dotenv import load_dotenv

load_dotenv()

def create_sample_data():
    """Create sample data based on your CSV files"""
    print("🚀 Creating sample data for Sales Tracker...")
    
    SessionLocal = sessionmaker(bind=db_manager.engine)
    db = SessionLocal()
    
    try:
        # Clear existing data
        print("Clearing existing data...")
        db.query(Visit).delete()
        db.query(TimeEntry).delete()
        db.query(FinancialEntry).delete()
        db.query(SalesBonus).delete()
        db.query(Contact).delete()
        db.query(ActivityNote).delete()
        db.commit()
        
        # Create sample visits (based on your 582 visits)
        print("Creating visits...")
        visit_data = [
            ("Colorado Springs Orthopaedic Group", "1259 Lake Plaza Dr Unit 100", "Colorado Springs", "Cookie stop", datetime(2025, 3, 6)),
            ("Summit Home Health Care", "1160 Lake Plaza Dr Ste 255", "Colorado Springs", "", datetime(2025, 3, 6)),
            ("Pikes Peak Hospice & Palliative Care", "2550 Tenderfoot Hill St", "Colorado Springs", "", datetime(2025, 3, 6)),
            ("Mountain View Post Acute", "835 Tenderfoot Hill Rd", "Colorado Springs", "", datetime(2025, 3, 6)),
            ("Professional Home Health Care", "1140 S Eighth St", "Colorado Springs", "", datetime(2025, 3, 6)),
            ("The Independence Center", "729 S Tejon St", "Colorado Springs", "Super grateful and excited", datetime(2025, 3, 6)),
            ("UCHealth Memorial Hospital Central", "1400 E Boulder St", "Colorado Springs", "", datetime(2025, 3, 6)),
            ("Life Care Center of Colorado Springs", "2490 International Cir", "Colorado Springs", "Natasha helpful", datetime(2025, 3, 6)),
            ("Advanced Health Care of Colorado Springs", "55 S Parkside Dr", "Colorado Springs", "Busy but good impression", datetime(2025, 3, 6)),
            ("Flagship Health", "3210 N Academy Blvd Ste 1", "Colorado Springs", "Elka interested", datetime(2025, 3, 6)),
        ]
        
        for i, (business, address, city, notes, date) in enumerate(visit_data):
            visit = Visit(
                stop_number=i+1,
                business_name=business,
                address=address,
                city=city,
                notes=notes,
                visit_date=date + timedelta(days=i*2)
            )
            db.add(visit)
        
        # Create financial entries (based on your daily summary)
        print("Creating financial entries...")
        financial_data = [
            (datetime(2025, 3, 7), 5.50, 71.06, 122.94, 282.68),
            (datetime(2025, 3, 18), 6.00, 63.43, 125.76, 290.16),
            (datetime(2025, 3, 20), 7.50, 56.62, 148.15, 337.78),
            (datetime(2025, 3, 26), 4.50, 41.67, 0.00, 119.17),
            (datetime(2025, 3, 27), 5.17, 75.97, 54.20, 210.78),
            (datetime(2025, 3, 31), 7.00, 67.73, 0.00, 187.41),
            (datetime(2025, 4, 3), 6.27, 76.21, 85.14, 263.89),
            (datetime(2025, 4, 7), 8.25, 77.75, 105.43, 324.86),
            (datetime(2025, 4, 9), 5.26, 59.48, 186.55, 333.39),
            (datetime(2025, 4, 14), 6.32, 62.73, 0.00, 170.31),
        ]
        
        for date, hours, miles, gas_treats, total_cost in financial_data:
            financial_entry = FinancialEntry(
                date=date,
                hours_worked=hours,
                labor_cost=hours * 20.0,  # $20/hour
                miles_driven=miles,
                mileage_cost=miles * 0.7,  # $0.70/mile
                materials_cost=gas_treats,
                total_daily_cost=total_cost
            )
            db.add(financial_entry)
            
            # Create corresponding time entry
            time_entry = TimeEntry(
                date=date,
                hours_worked=hours
            )
            db.add(time_entry)
        
        # Create sales bonuses (based on your closed sales)
        print("Creating sales bonuses...")
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
        
        # Create activity notes
        print("Creating activity notes...")
        activity_data = [
            (datetime(2025, 3, 6), "Cookie stop route - Colorado Springs area"),
            (datetime(2025, 3, 18), "Follow-up visits - good connections made"),
            (datetime(2025, 3, 20), "Met with case managers at multiple facilities"),
            (datetime(2025, 3, 26), "Routine visits - maintaining relationships"),
            (datetime(2025, 3, 27), "New facility introductions"),
            (datetime(2025, 3, 31), "End of month follow-ups"),
            (datetime(2025, 4, 3), "April outreach begins"),
            (datetime(2025, 4, 7), "Successful client meetings"),
            (datetime(2025, 4, 9), "High activity day - multiple stops"),
            (datetime(2025, 4, 14), "Mid-month check-ins"),
        ]
        
        for date, notes in activity_data:
            activity_note = ActivityNote(
                date=date,
                notes=notes
            )
            db.add(activity_note)
        
        db.commit()
        print("✅ Sample data created successfully!")
        
        # Show summary
        print("\n📊 Data Summary:")
        print(f"Visits: {db.query(Visit).count()}")
        print(f"Financial Entries: {db.query(FinancialEntry).count()}")
        print(f"Time Entries: {db.query(TimeEntry).count()}")
        print(f"Sales Bonuses: {db.query(SalesBonus).count()}")
        print(f"Activity Notes: {db.query(ActivityNote).count()}")
        
    except Exception as e:
        print(f"❌ Error creating data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_sample_data()

import os
from sqlalchemy.orm import sessionmaker
from database import db_manager
from models import FinancialEntry
from dotenv import load_dotenv

load_dotenv()

def fix_financial_data():
    """Fix the financial data field names"""
    try:
        SessionLocal = sessionmaker(bind=db_manager.engine)
        db = SessionLocal()
        
        # Get all financial entries
        entries = db.query(FinancialEntry).all()
        
        print(f"Found {len(entries)} financial entries to fix...")
        
        for entry in entries:
            # The old data has hour_total, we need to rename it to labor_cost
            if hasattr(entry, 'hour_total'):
                entry.labor_cost = entry.hour_total
            if hasattr(entry, 'gas_treats_materials'):
                entry.materials_cost = entry.gas_treats_materials
        
        db.commit()
        db.close()
        
        print("✅ Financial data field names fixed!")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing financial data: {str(e)}")
        return False

if __name__ == "__main__":
    fix_financial_data()


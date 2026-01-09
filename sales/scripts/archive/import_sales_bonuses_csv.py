import csv
import os
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from database import db_manager
from models import SalesBonus
from dotenv import load_dotenv

load_dotenv()

def import_sales_bonuses_csv(csv_file_path):
    """Import sales bonuses from closed sales CSV"""
    try:
        # Get database session
        SessionLocal = sessionmaker(bind=db_manager.engine)
        db = SessionLocal()
        
        imported_count = 0
        
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            
            # Skip header row
            next(csv_reader)
            
            for row_num, row in enumerate(csv_reader, 2):
                if not row or len(row) < 5:
                    continue
                
                # Skip empty rows
                if not any(cell.strip() for cell in row):
                    continue
                
                try:
                    # Extract data from CSV columns
                    client_name = row[0].strip() if row[0].strip() else None
                    start_date = row[1].strip() if len(row) > 1 and row[1].strip() else None
                    wellsky_status = row[2].strip() if len(row) > 2 and row[2].strip() else None
                    status = row[3].strip() if len(row) > 3 and row[3].strip() else None
                    commission_paid = row[4].strip() if len(row) > 4 and row[4].strip() else None
                    
                    # Skip rows without client name
                    if not client_name:
                        continue
                    
                    # Determine bonus amount based on status
                    bonus_amount = 0
                    if "live" in status.lower() or "signed" in status.lower():
                        if "$350" in commission_paid:
                            bonus_amount = 350
                        elif "$250" in commission_paid:
                            bonus_amount = 250
                        else:
                            bonus_amount = 250  # Default bonus
                    
                    # Skip if no bonus earned
                    if bonus_amount == 0:
                        continue
                    
                    # Parse start date
                    bonus_date = datetime.utcnow()
                    if start_date and start_date not in ['NA', 'Unknown']:
                        try:
                            # Handle different date formats
                            if '/' in start_date:
                                bonus_date = datetime.strptime(start_date, '%m/%d')
                                # Assume current year
                                bonus_date = bonus_date.replace(year=2025)
                        except ValueError:
                            pass
                    
                    # Determine if commission was paid
                    commission_paid_bool = False
                    if commission_paid and "$" in commission_paid:
                        commission_paid_bool = True
                    
                    # Create sales bonus record
                    sales_bonus = SalesBonus(
                        client_name=client_name,
                        bonus_amount=bonus_amount,
                        commission_paid=commission_paid_bool,
                        start_date=bonus_date,
                        wellsky_status=wellsky_status,
                        status=status
                    )
                    
                    db.add(sales_bonus)
                    imported_count += 1
                    
                    print(f"✅ Imported bonus: {client_name} - ${bonus_amount}")
                    
                except (ValueError, TypeError) as e:
                    print(f"⚠️  Skipped row {row_num}: {str(e)} - {row[:2]}")
                    continue
        
        # Commit all changes
        db.commit()
        db.close()
        
        print(f"🎉 Successfully imported {imported_count} sales bonuses!")
        return imported_count
        
    except Exception as e:
        print(f"❌ Error importing sales bonuses CSV: {str(e)}")
        return 0

if __name__ == "__main__":
    csv_file = "/Users/jasonshulman/Desktop/Sales Tracker - Closed Sales.csv"
    import_sales_bonuses_csv(csv_file)


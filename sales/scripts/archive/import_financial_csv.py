import csv
import os
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from database import db_manager
from models import FinancialEntry
from dotenv import load_dotenv

load_dotenv()

def import_financial_csv(csv_file_path):
    """Import financial data from daily summary CSV"""
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
                if not row or len(row) < 7:
                    continue
                
                # Skip empty rows
                if not any(cell.strip() for cell in row):
                    continue
                
                try:
                    # Extract data from CSV columns
                    date_str = row[0].strip()
                    hours_worked = row[1].strip()
                    hour_total = row[2].strip()
                    miles_driven = row[3].strip()
                    mileage_cost = row[4].strip()
                    gas_treats_materials = row[5].strip()
                    total_daily_cost = row[6].strip()
                    
                    # Skip if no date or essential financial data
                    if not date_str or not hour_total or not total_daily_cost:
                        continue
                    
                    # Parse date
                    if '/' in date_str:
                        if len(date_str.split('/')[2]) == 4:  # MM/DD/YYYY
                            entry_date = datetime.strptime(date_str, '%m/%d/%Y')
                        else:  # MM/DD/YY
                            entry_date = datetime.strptime(date_str, '%m/%d/%y')
                    else:
                        continue
                    
                    # Parse financial values (remove $ and commas)
                    def parse_currency(value):
                        if not value or value.strip() == '':
                            return 0.0
                        # Remove $ and commas, handle negative values
                        clean_value = value.replace('$', '').replace(',', '').strip()
                        if clean_value.startswith('(') and clean_value.endswith(')'):
                            clean_value = '-' + clean_value[1:-1]
                        try:
                            return float(clean_value)
                        except ValueError:
                            return 0.0
                    
                    hours_worked_val = float(hours_worked) if hours_worked else 0.0
                    hour_total_val = parse_currency(hour_total)
                    miles_driven_val = float(miles_driven) if miles_driven else 0.0
                    mileage_cost_val = parse_currency(mileage_cost)
                    gas_treats_materials_val = parse_currency(gas_treats_materials)
                    total_daily_cost_val = parse_currency(total_daily_cost)
                    
                    # Only import if we have meaningful financial data
                    if hour_total_val > 0 or total_daily_cost_val > 0:
                        financial_entry = FinancialEntry(
                            date=entry_date,
                            hours_worked=hours_worked_val,
                            labor_cost=hour_total_val,
                            miles_driven=miles_driven_val,
                            mileage_cost=mileage_cost_val,
                            materials_cost=gas_treats_materials_val,
                            total_daily_cost=total_daily_cost_val
                        )
                        
                        db.add(financial_entry)
                        imported_count += 1
                        
                        if imported_count % 20 == 0:
                            print(f"✅ Imported {imported_count} financial entries...")
                    
                except (ValueError, TypeError) as e:
                    print(f"⚠️  Skipped row {row_num}: {str(e)} - {row[:3]}")
                    continue
        
        # Commit all changes
        db.commit()
        db.close()
        
        print(f"🎉 Successfully imported {imported_count} financial entries!")
        return imported_count
        
    except Exception as e:
        print(f"❌ Error importing financial CSV: {str(e)}")
        return 0

if __name__ == "__main__":
    csv_file = "/Users/jasonshulman/Desktop/Sales Tracker - Daily Summary.csv"
    import_financial_csv(csv_file)
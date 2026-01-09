import csv
import os
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from database import db_manager
from models import TimeEntry
from dotenv import load_dotenv

load_dotenv()

def import_daily_summary_csv(csv_file_path):
    """Import daily summary CSV data into database"""
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
                if not row or len(row) < 2:
                    continue
                
                # Skip empty rows
                if not any(cell.strip() for cell in row):
                    continue
                
                date_str = row[0].strip()
                hours_str = row[1].strip()
                
                # Skip if no date or hours
                if not date_str or not hours_str:
                    continue
                
                try:
                    # Parse date - handle different formats
                    if '/' in date_str:
                        if len(date_str.split('/')[2]) == 4:  # MM/DD/YYYY
                            entry_date = datetime.strptime(date_str, '%m/%d/%Y')
                        else:  # MM/DD/YY
                            entry_date = datetime.strptime(date_str, '%m/%d/%y')
                    else:
                        continue
                    
                    # Parse hours
                    hours_worked = float(hours_str)
                    
                    # Only import if hours > 0
                    if hours_worked > 0:
                        time_entry = TimeEntry(
                            date=entry_date,
                            hours_worked=hours_worked
                        )
                        db.add(time_entry)
                        imported_count += 1
                        
                        print(f"✅ Imported {hours_worked} hours for {entry_date.strftime('%Y-%m-%d')}")
                    
                except (ValueError, TypeError) as e:
                    print(f"⚠️  Skipped row {row_num}: {str(e)} - {row}")
                    continue
        
        # Commit all changes
        db.commit()
        db.close()
        
        print(f"🎉 Successfully imported {imported_count} time entries from daily summary CSV!")
        return imported_count
        
    except Exception as e:
        print(f"❌ Error importing CSV: {str(e)}")
        return 0

if __name__ == "__main__":
    csv_file = "/Users/jasonshulman/Desktop/Sales Tracker - Daily Summary.csv"
    import_daily_summary_csv(csv_file)


import csv
import os
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from database import db_manager
from models import Visit, TimeEntry, Contact
from dotenv import load_dotenv

load_dotenv()

def import_dashboard_csv(csv_file_path):
    """Import dashboard CSV data into database"""
    try:
        # Get database session
        SessionLocal = sessionmaker(bind=db_manager.engine)
        db = SessionLocal()
        
        imported_count = 0
        
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            
            for row_num, row in enumerate(csv_reader, 1):
                if not row or len(row) < 2:
                    continue
                
                # Skip empty rows
                if not any(cell.strip() for cell in row):
                    continue
                
                # Look for visit data patterns
                if len(row) >= 2 and row[0] and row[1]:
                    city = row[0].strip()
                    visits_str = row[1].strip()
                    
                    # Check if this looks like visit data (city, number)
                    if city and visits_str.isdigit():
                        try:
                            visit_count = int(visits_str)
                            
                            # Create multiple visit records for this city
                            for i in range(visit_count):
                                visit = Visit(
                                    stop_number=i + 1,
                                    business_name=f"Visit in {city}",
                                    address=f"Various locations in {city}",
                                    city=city,
                                    notes=f"Imported from dashboard CSV - Visit {i+1} of {visit_count}",
                                    visit_date=datetime.now()
                                )
                                db.add(visit)
                                imported_count += 1
                            
                            print(f"✅ Imported {visit_count} visits for {city}")
                            
                        except ValueError:
                            continue
        
        # Commit all changes
        db.commit()
        db.close()
        
        print(f"🎉 Successfully imported {imported_count} visits from dashboard CSV!")
        return imported_count
        
    except Exception as e:
        print(f"❌ Error importing CSV: {str(e)}")
        return 0

if __name__ == "__main__":
    csv_file = "/Users/jasonshulman/Desktop/Sales Tracker - Dashboard.csv"
    import_dashboard_csv(csv_file)


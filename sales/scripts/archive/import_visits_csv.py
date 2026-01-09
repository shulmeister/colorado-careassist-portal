import csv
import os
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from database import db_manager
from models import Visit
from dotenv import load_dotenv

load_dotenv()

def import_visits_csv(csv_file_path):
    """Import visits CSV data into database"""
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
                if not row or len(row) < 6:
                    continue
                
                # Skip empty rows
                if not any(cell.strip() for cell in row):
                    continue
                
                try:
                    # Extract data from CSV columns
                    stop_number = int(row[0]) if row[0].strip() else 1
                    business_name = row[1].strip() if row[1].strip() else "Unknown Facility"
                    address = row[2].strip() if len(row) > 2 and row[2].strip() else None
                    city = row[3].strip() if len(row) > 3 and row[3].strip() else None
                    notes = row[4].strip() if len(row) > 4 and row[4].strip() else None
                    date_str = row[5].strip() if len(row) > 5 and row[5].strip() else None
                    
                    # Parse date
                    visit_date = datetime.utcnow()  # Default to now
                    if date_str and date_str != "—":
                        try:
                            # Handle different date formats
                            if " " in date_str:
                                visit_date = datetime.strptime(date_str.split()[0], '%Y-%m-%d')
                            else:
                                visit_date = datetime.strptime(date_str, '%Y-%m-%d')
                        except ValueError:
                            # Keep default if parsing fails
                            pass
                    
                    # Truncate fields to fit database constraints
                    if address and len(address) > 500:
                        address = address[:500]
                    if city and len(city) > 500:
                        city = city[:500]
                    if notes and len(notes) > 1000:
                        notes = notes[:1000]
                    
                    # Create visit record
                    visit = Visit(
                        stop_number=stop_number,
                        business_name=business_name,
                        address=address,
                        city=city,
                        notes=notes,
                        visit_date=visit_date
                    )
                    
                    db.add(visit)
                    imported_count += 1
                    
                    if imported_count % 100 == 0:
                        print(f"✅ Imported {imported_count} visits...")
                    
                except (ValueError, TypeError) as e:
                    print(f"⚠️  Skipped row {row_num}: {str(e)} - {row[:3]}")
                    continue
        
        # Commit all changes
        db.commit()
        db.close()
        
        print(f"🎉 Successfully imported {imported_count} visits from visits CSV!")
        return imported_count
        
    except Exception as e:
        print(f"❌ Error importing CSV: {str(e)}")
        return 0

if __name__ == "__main__":
    csv_file = "/Users/jasonshulman/Desktop/Sales Tracker - Visits.csv"
    import_visits_csv(csv_file)


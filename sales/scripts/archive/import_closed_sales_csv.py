import csv
import os
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from database import db_manager
from models import Contact
from dotenv import load_dotenv

load_dotenv()

def import_closed_sales_csv(csv_file_path):
    """Import closed sales CSV data as contacts"""
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
                if not row or len(row) < 4:
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
                    commission = row[4].strip() if len(row) > 4 and row[4].strip() else None
                    
                    # Skip rows without client name
                    if not client_name:
                        continue
                    
                    # Parse start date
                    contact_date = datetime.utcnow()
                    if start_date and start_date not in ['NA', 'Unknown']:
                        try:
                            # Handle different date formats
                            if '/' in start_date:
                                contact_date = datetime.strptime(start_date, '%m/%d')
                                # Assume current year
                                contact_date = contact_date.replace(year=2025)
                        except ValueError:
                            pass
                    
                    # Create notes from the sales data
                    notes_parts = []
                    if wellsky_status:
                        notes_parts.append(f"Wellsky: {wellsky_status}")
                    if status:
                        notes_parts.append(f"Status: {status}")
                    if commission:
                        notes_parts.append(f"Commission: {commission}")
                    
                    notes = " | ".join(notes_parts) if notes_parts else "Closed Sales Contact"
                    
                    # Create contact record
                    contact = Contact(
                        name=client_name,
                        company="Colorado CareAssist Client",
                        title="Client",
                        notes=notes,
                        scanned_date=contact_date
                    )
                    
                    db.add(contact)
                    imported_count += 1
                    
                    print(f"✅ Imported client: {client_name}")
                    
                except (ValueError, TypeError) as e:
                    print(f"⚠️  Skipped row {row_num}: {str(e)} - {row[:2]}")
                    continue
        
        # Commit all changes
        db.commit()
        db.close()
        
        print(f"🎉 Successfully imported {imported_count} closed sales contacts!")
        return imported_count
        
    except Exception as e:
        print(f"❌ Error importing CSV: {str(e)}")
        return 0

if __name__ == "__main__":
    csv_file = "/Users/jasonshulman/Desktop/Sales Tracker - Closed Sales.csv"
    import_closed_sales_csv(csv_file)


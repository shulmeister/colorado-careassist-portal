import gspread
from google.oauth2.service_account import Credentials
import json
import os
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func
from database import db_manager
from models import Visit, TimeEntry, Contact
import re

logger = logging.getLogger(__name__)

class GoogleSheetsMigrator:
    """Migrate data from Google Sheets to database"""
    
    def __init__(self):
        self.sheet_id = os.getenv("SHEET_ID", "1rKBP_5eLgvIVprVEzOYRnyL9J3FMf9H-6SLjIvIYFgg")
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Google Sheets client"""
        try:
            service_account_key = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
            
            if not service_account_key:
                raise Exception("GOOGLE_SERVICE_ACCOUNT_KEY environment variable not set")
            
            credentials_info = json.loads(service_account_key)
            
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            
            credentials = Credentials.from_service_account_info(
                credentials_info, 
                scopes=scope
            )
            
            self.client = gspread.authorize(credentials)
            logger.info(f"Successfully connected to Google Sheet: {self.sheet_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {str(e)}")
            raise Exception(f"Google Sheets initialization failed: {str(e)}")
    
    def migrate_all_data(self):
        """Migrate all data from Google Sheets to database"""
        try:
            # Get database session
            SessionLocal = sessionmaker(bind=db_manager.engine)
            db = SessionLocal()
            
            # Migrate visits
            visits_result = self.migrate_visits(db)
            visits_migrated = visits_result if isinstance(visits_result, int) else visits_result.get('migrated', 0)
            
            # Migrate time entries
            time_entries_result = self.migrate_time_entries(db)
            time_entries_migrated = time_entries_result if isinstance(time_entries_result, int) else time_entries_result.get('migrated', 0)
            
            # Commit all changes
            db.commit()
            db.close()
            
            logger.info(f"Migration complete: {visits_migrated} visits, {time_entries_migrated} time entries")
            
            return {
                "success": True,
                "visits_migrated": visits_migrated,
                "time_entries_migrated": time_entries_migrated
            }
            
        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    def _enhance_business_name(self, business_name: str, address: str, notes: str) -> str:
        """Enhance business name using intelligence - prioritize address/notes over sheet value"""
        # Known healthcare facilities
        known_facilities = {
            "uchealth memorial hospital": "UCHealth Memorial Hospital Central",
            "uchealth memorial": "UCHealth Memorial Hospital Central",
            "memorial hospital": "UCHealth Memorial Hospital Central",
            "pikes peak hospice": "Pikes Peak Hospice",
            "independence center": "The Independence Center",
            "penrose hospital": "Penrose Hospital",
            "centura health": "Centura Health",
            "st francis medical center": "St. Francis Medical Center",
        }
        
        text_to_search = f"{address} {notes}".lower() if address or notes else ""
        
        # FIRST: Check against known facilities in address/notes
        for keyword, facility_name in known_facilities.items():
            if keyword in text_to_search:
                return facility_name
        
        # SECOND: Extract business name from address using healthcare patterns (high confidence)
        if address:
            healthcare_patterns = [
                r'(\w+(?:\s+\w+)*)\s+(?:Hospital|Medical Center|Health Center|Healthcare Center)',
                r'(\w+(?:\s+\w+)*)\s+(?:Care Center|Rehabilitation Center|Rehab Center)',
                r'(\w+(?:\s+\w+)*)\s+(?:Assisted Living|Senior Living|Memory Care)',
                r'(\w+(?:\s+\w+)*)\s+(?:Hospice|Palliative Care)',
                r'(\w+(?:\s+\w+)*)\s+(?:Clinic|Medical Clinic|Health Clinic)',
                r'(\w+(?:\s+\w+)*)\s+(?:Emergency Room|ER|Emergency Department)',
                r'(\w+(?:\s+\w+)*)\s+(?:Recovery|Treatment Center)',
            ]
            
            for pattern in healthcare_patterns:
                match = re.search(pattern, address, re.IGNORECASE)
                if match:
                    name_part = match.group(1).strip()
                    if len(name_part) > 2 and name_part.lower() not in ['the', 'at', 'of', 'and']:
                        return name_part
        
        # THIRD: Try extracting from address line: "Business Name, 123 Main St" or "Business Name - 123 Main St"
        if address:
            name_patterns = [
                r'^([^,]+?),\s*\d+',  # Name before comma and number
                r'^([^-\d]+?)\s*[-–]\s*\d+',  # Name before dash and number
                r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+?)\s+(?:at|@)\s+\d+',  # Name before "at" and number
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, address, re.IGNORECASE)
                if match:
                    potential_name = match.group(1).strip()
                    # Validate it looks like a business name (not just street name)
                    if len(potential_name) > 5:
                        # Check for street suffixes (these indicate it's not a business name)
                        if not re.search(r'\b(st|street|ave|avenue|blvd|boulevard|rd|road|dr|drive|ln|lane|ct|court|pl|place|way)\b', potential_name, re.IGNORECASE):
                            words = potential_name.split()
                            # If it's multi-word and capitalized, likely a business name
                            if len(words) >= 2 and all(word[0].isupper() for word in words if word and word[0].isalpha()):
                                return potential_name
                            # Or if it contains healthcare keywords
                            if any(keyword in potential_name.lower() for keyword in ['health', 'medical', 'care', 'hospital', 'clinic', 'center', 'assisted', 'living', 'nursing']):
                                return potential_name
        
        # FOURTH: Extract from capitalized words in address (before street number)
        if address:
            # Get part before first comma (usually business name + street)
            address_parts = address.split(',')[0].split()
            capitalized_words = []
            street_suffixes = ['st', 'street', 'ave', 'avenue', 'blvd', 'boulevard', 'rd', 'road', 'dr', 'drive', 'ln', 'lane', 'ct', 'court', 'pl', 'place', 'way']
            
            for part in address_parts:
                # Stop if we hit a street number (digits) after finding some capitalized words
                if part.isdigit() and capitalized_words:
                    break
                # Collect capitalized words that aren't street suffixes
                if part and part[0].isupper() and len(part) > 2 and part.lower() not in street_suffixes:
                    capitalized_words.append(part)
                elif part and part.isdigit():
                    # If we hit a number before collecting words, this isn't a business name pattern
                    capitalized_words = []
            
            if len(capitalized_words) >= 2:
                return " ".join(capitalized_words)
        
        # FIFTH: Use sheet value if it exists and is valid (not empty, not brackets)
        if business_name and business_name.strip() and not business_name.strip().startswith('['):
            return business_name.strip()
        
        # LAST: Default fallback
        return business_name.strip() if business_name else "Unknown Facility"
    
    def _enhance_city(self, city: str, address: str, notes: str) -> str:
        """Extract city from address or notes using intelligence - prioritize address/notes over sheet value"""
        # Common Colorado cities
        cities = ["Denver", "Colorado Springs", "Pueblo", "Aurora", "Fort Collins", 
                 "Lakewood", "Thornton", "Arvada", "Westminster", "Centennial",
                 "Boulder", "Greeley", "Longmont", "Loveland", "Grand Junction",
                 "Broomfield", "Commerce City", "Northglenn", "Parker", "Castle Rock",
                 "Fountain", "Monument", "Manitou Springs"]
        
        # Denver street names (these indicate Denver, not Colorado Springs)
        denver_streets = [
            "iliff", "cornell", "yale", "jewell", "hampden", "evans", "alameda",
            "mississippi", "louisiana", "colorado blvd", "broadway", "downing",
            "humboldt", "logan", "speer", "federal", "colfax", "leetsdale",
            "hampton", "franklin", "park", "washington", "tremont", "monaco",
            "tower", "quebec", "dahlia", "fairfax", "oneida", "syracuse"
        ]
        
        combined_text = f"{address} {notes}".lower()
        
        # FIRST: Check for Denver street names (highest priority - these are definitive)
        for street in denver_streets:
            if street in combined_text:
                return "Denver"
        
        # SECOND: Search for city names in address (more reliable than sheet column)
        address_lower = address.lower() if address else ""
        for city_name in cities:
            if city_name.lower() in address_lower:
                return city_name
        
        # THIRD: Search in notes
        notes_lower = notes.lower() if notes else ""
        for city_name in cities:
            if city_name.lower() in notes_lower:
                return city_name
        
        # FOURTH: Try to extract from address pattern: "123 Main St, City Name, CO"
        if address:
            city_pattern = r',\s*([A-Za-z\s]+?)(?:,\s*(?:CO|Colorado))?\s*$'
            match = re.search(city_pattern, address, re.IGNORECASE)
            if match:
                extracted_city = match.group(1).strip()
                if extracted_city and len(extracted_city) > 2:
                    # Validate against known cities
                    for city_name in cities:
                        if city_name.lower() == extracted_city.lower():
                            return city_name
                    # Return extracted city if it looks valid
                    if len(extracted_city.split()) <= 3:  # City names are usually 1-3 words
                        return extracted_city.title()
        
        # LAST: Use sheet value if it exists and is valid (but only as fallback)
        if city and city.strip() and city.strip().lower() != "unknown":
            return city.strip()
        
        return ""
    
    def _get_date_from_daily_summary(self, target_row_index: int, all_visit_rows: list = None) -> Optional[datetime]:
        """Get date from Daily Summary tab based on visit row position and grouping"""
        try:
            spreadsheet = self.client.open_by_key(self.sheet_id)
            
            # Find Daily Summary worksheet
            worksheets = spreadsheet.worksheets()
            daily_summary_worksheet = None
            
            for ws in worksheets:
                if ws.title.lower() in ['daily summary', 'daily', 'summary']:
                    daily_summary_worksheet = ws
                    break
            
            if not daily_summary_worksheet:
                return None
            
            all_values = daily_summary_worksheet.get_all_values()
            data_rows = all_values[1:] if len(all_values) > 1 else []
            
            # Get all dates from Daily Summary in chronological order
            daily_dates = []
            for row in data_rows:
                if not row or not row[0]:
                    continue
                date_str = row[0].strip()
                if date_str:
                    try:
                        if '/' in date_str:
                            date_obj = datetime.strptime(date_str, '%m/%d/%Y')
                        elif '-' in date_str:
                            if len(date_str.split('-')[0]) == 4:
                                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            else:
                                date_obj = datetime.strptime(date_str, '%m-%d-%Y')
                        else:
                            continue
                        daily_dates.append(date_obj.date())
                    except:
                        continue
            
            if not daily_dates:
                return None
            
            daily_dates.sort()  # Sort chronologically
            
            # Get visits worksheet to find date groupings
            visits_worksheet = None
            for ws in worksheets:
                ws_name_lower = ws.title.lower()
                if 'visit' in ws_name_lower:
                    visits_worksheet = ws
                    break
            
            if not visits_worksheet or not all_visit_rows:
                return None
            
            # Find the last date before this row
            last_date = None
            for idx in range(target_row_index):
                row = all_visit_rows[idx]
                if len(row) >= 6 and row[5]:
                    date_str = row[5].strip()
                    if date_str and date_str != "—":
                        try:
                            if ' ' in date_str:
                                date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                            else:
                                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            if not last_date or date_obj.date() > last_date:
                                last_date = date_obj.date()
                        except:
                            pass
            
            if not last_date:
                # No previous date found - use first date from Daily Summary
                # But only if we're in the missing date range (after row 434)
                if target_row_index >= 434:  # After last date in visits
                    return datetime.combine(daily_dates[0], datetime.min.time())
                return None
            
            # Count how many consecutive rows without dates we've seen
            # This helps us map to the right date in Daily Summary
            rows_without_date_count = 0
            for idx in range(target_row_index, min(target_row_index + 50, len(all_visit_rows))):
                row = all_visit_rows[idx]
                if len(row) >= 6 and (not row[5] or not row[5].strip() or row[5].strip() == "—"):
                    rows_without_date_count += 1
                else:
                    break
            
            # Find dates after last_date
            dates_after = [d for d in daily_dates if d > last_date]
            
            if dates_after:
                # Use the first date after last_date for the start of this group
                # Group visits into ~15 visit chunks (typical daily count)
                group_index = rows_without_date_count // 15  # Rough grouping
                if group_index < len(dates_after):
                    return datetime.combine(dates_after[group_index], datetime.min.time())
                # If we've run out of dates, use the last one
                return datetime.combine(dates_after[-1], datetime.min.time())
            
            return None
        except Exception as e:
            logger.warning(f"Error getting date from Daily Summary: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _infer_missing_date(self, row_index: int, all_rows: list, existing_visit_date: datetime = None) -> Optional[datetime]:
        """Infer missing date from context (neighboring rows or existing visit)"""
        # First, try to preserve existing date if available
        if existing_visit_date:
            today = datetime.now().date()
            # Only use existing date if it's not today (to avoid overwriting old dates with today)
            if existing_visit_date.date() != today:
                return existing_visit_date
        
        # Try to find date from neighboring rows (look at previous rows first)
        for offset in range(1, min(10, row_index)):  # Look up to 10 rows back
            check_row = all_rows[row_index - offset]
            if len(check_row) >= 6 and check_row[5]:
                date_str = check_row[5].strip()
                if date_str:
                    try:
                        if ' ' in date_str:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        else:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        # Only use if it's not today
                        if date_obj.date() != datetime.now().date():
                            return date_obj
                    except:
                        pass
        
        # Look ahead (future rows)
        for offset in range(1, min(10, len(all_rows) - row_index)):
            check_row = all_rows[row_index + offset]
            if len(check_row) >= 6 and check_row[5]:
                date_str = check_row[5].strip()
                if date_str:
                    try:
                        if ' ' in date_str:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        else:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        # Only use if it's not today
                        if date_obj.date() != datetime.now().date():
                            return date_obj
                    except:
                        pass
        
        # No date found - return None (will be handled by caller)
        return None

    def migrate_visits(self, db):
        """Migrate visits from Google Sheets - only adds new visits, skips duplicates"""
        try:
            spreadsheet = self.client.open_by_key(self.sheet_id)
            
            # Try to find the visits worksheet
            worksheets = spreadsheet.worksheets()
            visits_worksheet = None
            
            for ws in worksheets:
                if ws.title.lower() in ['visits', 'tracker', 'visit tracker']:
                    visits_worksheet = ws
                    break
            
            if not visits_worksheet:
                logger.warning("No visits worksheet found")
                return 0
            
            # Get all data
            all_values = visits_worksheet.get_all_values()
            
            if len(all_values) <= 1:  # Only header or empty
                logger.info("No visit data to migrate")
                return 0
            
            # Skip header row
            data_rows = all_values[1:]
            
            migrated_count = 0
            skipped_count = 0
            error_count = 0
            
            # Get existing visits to check for exact duplicates (same date, business, stop, address)
            # This prevents importing the exact same row twice, but allows multiple visits to same business
            existing_visits = db.query(Visit).all()
            existing_visit_keys = set()
            for visit in existing_visits:
                # Create a unique key: date + business_name + stop_number + address
                # This only prevents exact duplicates, allows same business on different dates
                date_key = visit.visit_date.date().isoformat() if visit.visit_date else ""
                business_name_normalized = (visit.business_name or "").strip().lower()
                address_normalized = (visit.address or "").strip().lower()
                key = f"{date_key}|{business_name_normalized}|{visit.stop_number}|{address_normalized}"
                existing_visit_keys.add(key)
            
            logger.info(f"Found {len(existing_visit_keys)} existing visits in database")
            
            for row in data_rows:
                if not row or len(row) < 3:  # Skip empty rows
                    continue
                
                try:
                    # Parse the row data
                    # Actual format: Stop, Business Name, Location (Address), City, Notes, Date, ...
                    visit_date = None
                    stop_number = None
                    business_name = ""
                    address = ""
                    city = ""
                    notes = ""
                    
                    # Stop (column 0)
                    if len(row) >= 1 and row[0]:
                        try:
                            stop_number = int(float(row[0]))  # Handle numbers as strings
                        except:
                            stop_number = 1
                    
                    # Business Name (column 1)
                    if len(row) >= 2:
                        business_name = (row[1] or "Unknown Facility").strip()
                    
                    # Location/Address (column 2)
                    if len(row) >= 3:
                        address = (row[2] or "").strip()[:500]  # Truncate to 500 chars
                    
                    # City (column 3)
                    if len(row) >= 4:
                        city = (row[3] or "").strip()[:500]  # Truncate to 500 chars
                    
                    # Notes (column 4)
                    if len(row) >= 5:
                        notes = (row[4] or "").strip()[:1000]  # Truncate to 1000 chars
                    
                    # ENHANCE business name and city using intelligence (similar to PDF extractor)
                    business_name = self._enhance_business_name(business_name, address, notes)
                    city = self._enhance_city(city, address, notes)
                    
                    # Date (column 5) - IMPORTANT: Don't default to today if date is missing
                    visit_date = None
                    existing_visit_for_date = None
                    normalized_business = (business_name or "").strip().lower()
                    
                    if len(row) >= 6 and row[5]:
                        date_str = row[5].strip()
                        if date_str and date_str != "—":  # Skip em dash and empty
                            try:
                                # Try to parse date - format: '2025-03-06 00:00:00' or '2025-03-06'
                                if ' ' in date_str:
                                    visit_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                                else:
                                    visit_date = datetime.strptime(date_str, '%Y-%m-%d')
                            except:
                                try:
                                    # Try other common formats
                                    visit_date = datetime.strptime(date_str, '%m/%d/%Y')
                                except:
                                    try:
                                        visit_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                                    except:
                                        try:
                                            # Try more formats
                                            visit_date = datetime.strptime(date_str, '%m-%d-%Y')
                                        except:
                                            # If all parsing fails, will try to infer
                                            visit_date = None
                    
                    # If no date found, try to infer from context
                    if not visit_date:
                        # First check for existing visit with same business/stop
                        existing_visit_for_date = db.query(Visit).filter(
                            func.lower(func.trim(Visit.business_name)) == normalized_business,
                            Visit.stop_number == (stop_number or 1)
                        ).order_by(Visit.visit_date.desc()).first()
                        
                        # Use inference method with row index and all rows
                        row_index = data_rows.index(row)
                        
                        # First try Daily Summary mapping (pass all rows for context)
                        daily_summary_date = self._get_date_from_daily_summary(row_index, data_rows)
                        if daily_summary_date:
                            visit_date = daily_summary_date
                            logger.info(f"Got date {visit_date.date()} from Daily Summary for visit {stop_number} {business_name} at row {row_index+2}")
                        else:
                            # Fall back to neighboring rows
                            inferred_date = self._infer_missing_date(
                                row_index, 
                                data_rows, 
                                existing_visit_for_date.visit_date if existing_visit_for_date and existing_visit_for_date.visit_date else None
                            )
                            
                            if inferred_date:
                                visit_date = inferred_date
                                logger.debug(f"Inferred date {visit_date.date()} for visit {stop_number} {business_name}")
                        
                        # If still no date, try existing visit
                        if not visit_date and existing_visit_for_date and existing_visit_for_date.visit_date:
                            # Preserve the date from existing visit if available
                            visit_date = existing_visit_for_date.visit_date
                            logger.debug(f"Preserving existing date {visit_date.date()} for {business_name}")
                        
                        # Last resort: only use today if we truly have no existing visit and can't infer
                        if not visit_date:
                            visit_date = datetime.now()
                            logger.warning(f"No date in sheet for visit {stop_number} {business_name}, using today - this may be incorrect")
                    
                    # Check if this exact visit already exists (same date, business, stop, address)
                    # This only prevents importing the exact same row twice
                    date_key = visit_date.date().isoformat() if visit_date else datetime.now().date().isoformat()
                    business_name_normalized = (business_name or "").strip().lower()
                    address_normalized = (address or "").strip().lower()
                    visit_key = f"{date_key}|{business_name_normalized}|{stop_number or 1}|{address_normalized}"
                    
                    if visit_key in existing_visit_keys:
                        skipped_count += 1
                        if skipped_count <= 5:  # Log first few skips for debugging
                            logger.debug(f"Skipping exact duplicate: {visit_key}")
                        continue  # Skip exact duplicate only
                    
                                            # Create visit record with enhanced data
                    # Don't default to "Unknown" - if we can't determine city, leave it empty
                    final_city = city if city else ""
                    visit = Visit(
                        stop_number=stop_number or 1,
                        business_name=business_name,
                        address=address,
                        city=final_city,
                        notes=notes,
                        visit_date=visit_date or datetime.now()
                    )
                    
                    db.add(visit)
                    migrated_count += 1
                    
                    # Add to existing set to prevent duplicates within this batch
                    existing_visit_keys.add(visit_key)
                    
                except Exception as e:
                    error_count += 1
                    logger.warning(f"Failed to migrate visit row: {row}, error: {str(e)}")
                    continue
            
            logger.info(f"Migration complete: {migrated_count} new visits added, {skipped_count} duplicates skipped, {error_count} errors")
            logger.info(f"Total rows processed: {len(data_rows)}, Existing in DB: {len(existing_visit_keys)}")
            return migrated_count
            
        except Exception as e:
            logger.error(f"Error migrating visits: {str(e)}")
            import traceback
            traceback.print_exc()
            return 0
    
    def migrate_time_entries(self, db):
        """Migrate time entries from Daily Summary worksheet - only adds new entries, skips duplicates"""
        try:
            from models import TimeEntry
            from sqlalchemy import and_
            
            spreadsheet = self.client.open_by_key(self.sheet_id)
            
            # Try to find the Daily Summary worksheet
            worksheets = spreadsheet.worksheets()
            daily_summary_worksheet = None
            
            for ws in worksheets:
                if ws.title.lower() in ['daily summary', 'daily', 'summary', 'hours']:
                    daily_summary_worksheet = ws
                    break
            
            if not daily_summary_worksheet:
                logger.warning("No Daily Summary worksheet found")
                return 0
            
            # Get all data
            all_values = daily_summary_worksheet.get_all_values()
            
            if len(all_values) <= 1:  # Only header or empty
                logger.info("No time entry data to migrate")
                return 0
            
            # Skip header row
            data_rows = all_values[1:]
            
            migrated_count = 0
            skipped_count = 0
            error_count = 0
            
            for row in data_rows:
                if not row or len(row) < 2:  # Skip empty rows
                    continue
                
                try:
                    # Parse the row data
                    # Assuming format: Date, Hours Worked, ...
                    date_str = row[0] if len(row) > 0 else None
                    hours_str = row[1] if len(row) > 1 else None
                    
                    if not date_str or not hours_str:
                        continue
                    
                    # Parse date
                    entry_date = None
                    try:
                        entry_date = datetime.strptime(date_str.strip(), '%Y-%m-%d')
                    except:
                        try:
                            entry_date = datetime.strptime(date_str.strip(), '%m/%d/%Y')
                        except:
                            try:
                                entry_date = datetime.strptime(date_str.strip(), '%Y-%m-%d %H:%M:%S')
                            except:
                                error_count += 1
                                continue
                    
                    # Parse hours
                    try:
                        hours_worked = float(hours_str)
                    except:
                        error_count += 1
                        continue
                    
                    # Check if time entry already exists for this date
                    existing = db.query(TimeEntry).filter(
                        TimeEntry.date == entry_date.date()
                    ).first()
                    
                    if existing:
                        skipped_count += 1
                        continue  # Skip duplicate
                    
                    # Create time entry record
                    time_entry = TimeEntry(
                        date=entry_date,
                        hours_worked=hours_worked
                    )
                    
                    db.add(time_entry)
                    migrated_count += 1
                    
                except Exception as e:
                    error_count += 1
                    logger.warning(f"Failed to migrate time entry row: {row}, error: {str(e)}")
                    continue
            
            logger.info(f"Time entries migration: {migrated_count} new, {skipped_count} duplicates skipped, {error_count} errors")
            return migrated_count
            
        except Exception as e:
            logger.error(f"Error migrating time entries: {str(e)}")
            import traceback
            traceback.print_exc()
            return 0

def run_migration():
    """Run the migration process"""
    migrator = GoogleSheetsMigrator()
    result = migrator.migrate_all_data()
    
    if result["success"]:
        print(f"✅ Migration successful!")
        print(f"   📊 Visits migrated: {result['visits_migrated']}")
        print(f"   ⏰ Time entries migrated: {result['time_entries_migrated']}")
    else:
        print(f"❌ Migration failed: {result['error']}")

if __name__ == "__main__":
    run_migration()

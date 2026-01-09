import gspread
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import json
import os
import logging
from typing import List, Dict, Any
import pickle
import base64

logger = logging.getLogger(__name__)

class GoogleSheetsManager:
    """Manage Google Sheets integration for visit tracking.
    
    NOTE: Google Sheets sync is DISABLED as of Dec 2025.
    Maryssa was the only user of the sheet sync and has left.
    The sync is now a no-op to save API calls and simplify the system.
    """
    
    # Set to False to disable all Google Sheets sync
    ENABLED = False
    
    def __init__(self):
        self.sheet_id = os.getenv("SHEET_ID", "1rKBP_5eLgvIVprVEzOYRnyL9J3FMf9H-6SLjIvIYFgg")
        self.worksheet_name = "Visits"
        self.client = None
        self.worksheet = None
        
        # Skip initialization if disabled
        if not self.ENABLED:
            logger.info("Google Sheets sync is DISABLED")
            return
            
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Google Sheets client"""
        try:
            # Get service account credentials from environment or local file
            service_account_key = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
            service_account_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY_PATH") or os.path.join(
                os.path.dirname(__file__), "service_account.json"
            )

            def _load_credentials(raw: str) -> Dict[str, Any]:
                """
                Be tolerant of:
                - Escaped newlines in private_key
                - Base64-encoded JSON blobs
                - Single-quoted JSON
                """
                cleaned = raw.strip()
                # Fix common mistake: single quotes instead of double
                if cleaned.startswith("{'") and cleaned.endswith("'}"):
                    cleaned = cleaned.replace("'", '"')
                # Try plain JSON first
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass
                # Try base64-decoding then JSON
                try:
                    decoded = base64.b64decode(cleaned).decode("utf-8")
                    return json.loads(decoded)
                except Exception:
                    pass
                raise Exception("Invalid JSON in GOOGLE_SERVICE_ACCOUNT_KEY")

            credentials_info: Dict[str, Any] = {}
            load_error: Exception | None = None

            # Prefer local file if present (most reliable)
            if os.path.exists(service_account_path):
                try:
                    with open(service_account_path, "r", encoding="utf-8") as f:
                        file_content = f.read()
                    credentials_info = _load_credentials(file_content)
                except Exception as e:
                    load_error = e

            # If file missing or failed, fall back to env
            if not credentials_info and service_account_key:
                try:
                    credentials_info = _load_credentials(service_account_key)
                except Exception as e:
                    load_error = e

            if not credentials_info:
                if load_error:
                    raise load_error
                raise Exception(
                    "Google service account credentials not found (env or service_account.json)"
                )

            # Ensure private_key has real newlines (not literal '\n')
            if "private_key" in credentials_info and isinstance(credentials_info["private_key"], str):
                credentials_info["private_key"] = credentials_info["private_key"].replace("\\n", "\n")
            
            # Set up credentials
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            
            credentials = Credentials.from_service_account_info(
                credentials_info, 
                scopes=scope
            )
            
            # Initialize client
            self.client = gspread.authorize(credentials)
            
            # Open the spreadsheet
            spreadsheet = self.client.open_by_key(self.sheet_id)
            self.worksheet = spreadsheet.worksheet(self.worksheet_name)
            
            logger.info(f"Successfully connected to Google Sheet: {self.sheet_id}")
            
        except Exception as e:
            # Do not crash the app if Sheets credentials are malformed; continue without Sheets.
            logger.warning(f"Google Sheets disabled: {str(e)}")
            self.client = None
            self.worksheet = None
    
    def append_visits(self, visits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Append visits to the Google Sheet"""
        # Return early if disabled
        if not self.ENABLED:
            return {"success": True, "message": "Google Sheets sync disabled", "rows_added": 0}
        
        try:
            if not self.worksheet:
                raise Exception("Google Sheets not initialized")
            
            if not visits:
                raise Exception("No visits to append")
            
            # Prepare data for insertion
            rows_to_add = []
            
            for visit in visits:
                # Handle both "stop" and "stop_number" keys, "location" and "address" keys
                stop = visit.get("stop") or visit.get("stop_number") or ""
                business_name = visit.get("business_name") or ""
                address = visit.get("location") or visit.get("address") or ""
                city = visit.get("city") or ""
                notes = visit.get("notes") or ""
                
                row = [
                    stop,
                    business_name,
                    address,
                    city,
                    notes
                ]
                rows_to_add.append(row)
            
            # Append to worksheet
            self.worksheet.append_rows(rows_to_add)
            
            logger.info(f"Successfully appended {len(visits)} visits to Google Sheet")
            
            return {
                "success": True,
                "appended_count": len(visits),
                "message": f"Added {len(visits)} visits to the tracker"
            }
            
        except Exception as e:
            logger.error(f"Error appending visits to sheet: {str(e)}")
            raise Exception(f"Failed to append visits: {str(e)}")
    
    def get_recent_visits(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent visits from the sheet"""
        if not self.ENABLED:
            return []
        
        try:
            if not self.worksheet:
                raise Exception("Google Sheets not initialized")
            
            # Get all records
            records = self.worksheet.get_all_records()
            
            # Return most recent (assuming they're added in order)
            recent = records[-limit:] if len(records) > limit else records
            
            return recent
            
        except Exception as e:
            logger.error(f"Error getting recent visits: {str(e)}")
            raise Exception(f"Failed to get recent visits: {str(e)}")
    
    def get_visit_count(self) -> int:
        """Get total number of visits in the sheet"""
        if not self.ENABLED:
            return 0
        
        try:
            if not self.worksheet:
                raise Exception("Google Sheets not initialized")
            
            # Get all records and count non-empty rows
            records = self.worksheet.get_all_records()
            return len(records)
            
        except Exception as e:
            logger.error(f"Error getting visit count: {str(e)}")
            return 0
    
    def update_daily_summary(self, date: str, hours_worked: float = None, visit_count: int = None) -> Dict[str, Any]:
        """Update Daily Summary tab with hours worked and/or visit count for a specific date"""
        if not self.ENABLED:
            return {"success": True, "message": "Google Sheets sync disabled"}
        
        try:
            if not self.client:
                raise Exception("Google Sheets not initialized")
            
            if hours_worked is None and visit_count is None:
                raise Exception("At least one of hours_worked or visit_count must be provided")
            
            # Open the Daily Summary worksheet
            spreadsheet = self.client.open_by_key(self.sheet_id)
            daily_summary = spreadsheet.worksheet("Daily Summary")
            
            # Get all existing data
            all_values = daily_summary.get_all_values()
            
            # Find the row with the matching date
            date_row_index = None
            existing_row = None
            for i, row in enumerate(all_values):
                if row and len(row) > 0 and row[0] == date:
                    date_row_index = i + 1  # Google Sheets is 1-indexed
                    existing_row = row
                    break
            
            if date_row_index:
                # Update existing row
                updates = {}
                if hours_worked is not None:
                    # Column B (index 2) for hours worked
                    daily_summary.update_cell(date_row_index, 2, hours_worked)
                    updates['hours'] = hours_worked
                    logger.info(f"Updated hours in row {date_row_index} for date {date} with {hours_worked} hours")
                
                if visit_count is not None:
                    # Column C (index 3) for visit count
                    daily_summary.update_cell(date_row_index, 3, visit_count)
                    updates['visits'] = visit_count
                    logger.info(f"Updated visit count in row {date_row_index} for date {date} with {visit_count} visits")
                
                return {
                    "success": True,
                    "message": f"Successfully updated Daily Summary for {date}",
                    "date": date,
                    **updates
                }
            else:
                # Add new row
                # Ensure row has enough columns: Date, Hours, Visits, and other columns
                new_row = [date, "", "", "", "", "", ""]
                if hours_worked is not None:
                    new_row[1] = hours_worked  # Column B
                if visit_count is not None:
                    new_row[2] = visit_count  # Column C
                
                daily_summary.append_row(new_row)
                logger.info(f"Added new row for date {date} with hours={hours_worked}, visits={visit_count}")
                
                return {
                    "success": True,
                    "message": f"Successfully added new row to Daily Summary for {date}",
                    "date": date,
                    "hours": hours_worked,
                    "visits": visit_count
                }
            
        except Exception as e:
            logger.error(f"Error updating Daily Summary: {str(e)}")
            raise Exception(f"Failed to update Daily Summary: {str(e)}")
    
    def test_connection(self) -> bool:
        """Test the Google Sheets connection"""
        if not self.ENABLED:
            return False
        
        try:
            if not self.worksheet:
                return False
            
            # Try to read the first row
            self.worksheet.row_values(1)
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets connection test failed: {str(e)}")
            return False

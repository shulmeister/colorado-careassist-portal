"""
Voucher Sync Service
Monitors Google Drive folder for new vouchers, extracts data using OCR,
and syncs to both the portal database and Google Sheets
"""
import os
import io
import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Google APIs
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.cloud import vision
import gspread

# Portal imports
from portal_database import db_manager
from portal_models import Voucher

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Configuration
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_VOUCHER_FOLDER_ID")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_VOUCHER_ID", "1f0lk54-zyAnZd2Ok9KNezHgTjYeuH4zCwaLASGjMZAM")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_CLOUD_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID")

# Scopes needed
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/spreadsheets',
]

class VoucherSyncService:
    """Service to sync vouchers from Google Drive using OCR"""
    
    def __init__(self):
        self.credentials = None
        self.drive_service = None
        self.vision_client = None
        self.sheets_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Google API clients"""
        try:
            if not GOOGLE_SERVICE_ACCOUNT_JSON:
                logger.warning("No Google service account credentials found")
                return
            
            # Load service account credentials
            import json
            service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
            
            # Create credentials
            self.credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=SCOPES
            )
            
            # Initialize Drive API
            self.drive_service = build('drive', 'v3', credentials=self.credentials)
            
            # Initialize Vision API
            self.vision_client = vision.ImageAnnotatorClient(
                credentials=self.credentials
            )
            
            # Initialize Sheets API
            self.sheets_client = gspread.authorize(self.credentials)
            
            logger.info("Google API clients initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google API clients: {str(e)}")
            raise
    
    def get_new_vouchers_from_drive(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        Get new voucher files from Google Drive folder
        
        Args:
            hours_back: How many hours back to check for new files
        
        Returns:
            List of file metadata dictionaries
        """
        if not self.drive_service or not GOOGLE_DRIVE_FOLDER_ID:
            logger.warning("Drive service not initialized or folder ID not set")
            return []
        
        try:
            # Calculate cutoff time
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
            cutoff_str = cutoff_time.isoformat() + 'Z'
            
            # Query for new PDF and image files in the folder
            query = (
                f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents "
                f"and (mimeType contains 'image/' or mimeType = 'application/pdf') "
                f"and createdTime > '{cutoff_str}' "
                f"and trashed = false"
            )
            
            results = self.drive_service.files().list(
                q=query,
                fields="files(id, name, mimeType, createdTime, webViewLink)",
                orderBy="createdTime desc",
                corpora='allDrives',
                includeItemsFromAllDrives=True,
                supportsAllDrives=True
            ).execute()
            
            files = results.get('files', [])
            logger.info(f"Found {len(files)} new voucher files in Drive")
            
            return files
            
        except Exception as e:
            logger.error(f"Error getting files from Drive: {str(e)}")
            return []
    
    def download_file(self, file_id: str) -> Optional[bytes]:
        """Download a file from Google Drive"""
        try:
            request = self.drive_service.files().get_media(fileId=file_id, supportsAllDrives=True)
            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_buffer.seek(0)
            return file_buffer.read()
            
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {str(e)}")
            return None
    
    def extract_text_from_image(self, image_bytes: bytes, is_pdf: bool = False) -> str:
        """Extract text from image using Google Vision API with Tesseract fallback"""
        try:
            # If it's a PDF, convert first page to image
            if is_pdf:
                try:
                    from pdf2image import convert_from_bytes
                    from PIL import Image
                    import io as image_io
                    
                    logger.info("Converting PDF to image...")
                    # Convert first page of PDF to image with explicit poppler path
                    images = convert_from_bytes(
                        image_bytes, 
                        first_page=1, 
                        last_page=1,
                        dpi=300  # Higher DPI for better OCR
                    )
                    
                    if not images:
                        logger.error("Failed to convert PDF to image - no images returned")
                        return self._extract_with_tesseract_fallback(image_bytes, is_pdf=True)
                    
                    logger.info(f"Successfully converted PDF to image: {images[0].size}")
                    
                    # Convert PIL Image to bytes
                    img_byte_arr = image_io.BytesIO()
                    images[0].save(img_byte_arr, format='PNG')
                    image_bytes = img_byte_arr.getvalue()
                    
                except ImportError as e:
                    logger.error(f"pdf2image library not available: {str(e)}")
                    return self._extract_with_tesseract_fallback(image_bytes, is_pdf=True)
                except Exception as e:
                    logger.error(f"Error converting PDF to image: {str(e)}", exc_info=True)
                    return self._extract_with_tesseract_fallback(image_bytes, is_pdf=True)
            
            # Try Google Vision API first
            if self.vision_client:
                try:
                    logger.info("Attempting OCR with Google Vision API...")
                    image = vision.Image(content=image_bytes)
                    response = self.vision_client.text_detection(image=image)
                    
                    if response.error.message:
                        logger.error(f"Vision API error: {response.error.message}")
                        return self._extract_with_tesseract_fallback(image_bytes, is_pdf=False)
                    
                    texts = response.text_annotations
                    if texts and len(texts) > 0:
                        extracted_text = texts[0].description
                        logger.info(f"Successfully extracted {len(extracted_text)} characters with Vision API")
                        return extracted_text
                    else:
                        logger.warning("Vision API returned no text, trying Tesseract...")
                        return self._extract_with_tesseract_fallback(image_bytes, is_pdf=False)
                        
                except Exception as e:
                    logger.error(f"Vision API exception: {str(e)}", exc_info=True)
                    return self._extract_with_tesseract_fallback(image_bytes, is_pdf=False)
            else:
                logger.warning("Vision client not initialized, using Tesseract")
                return self._extract_with_tesseract_fallback(image_bytes, is_pdf=False)
            
        except Exception as e:
            logger.error(f"Error extracting text from image: {str(e)}", exc_info=True)
            return self._extract_with_tesseract_fallback(image_bytes, is_pdf=False)
    
    def _extract_with_tesseract_fallback(self, image_bytes: bytes, is_pdf: bool = False) -> str:
        """Fallback OCR using Tesseract (like your biz card scanner)"""
        try:
            import pytesseract
            from PIL import Image
            import io as image_io
            import os as os_module
            
            # Set Tesseract data directory for Heroku
            if 'TESSDATA_PREFIX' not in os_module.environ:
                os_module.environ['TESSDATA_PREFIX'] = '/app/.apt/usr/share/tesseract-ocr/5/tessdata/'
            
            logger.info("Attempting OCR with Tesseract...")
            
            # If PDF, try to convert it first
            if is_pdf:
                try:
                    from pdf2image import convert_from_bytes
                    images = convert_from_bytes(image_bytes, first_page=1, last_page=1, dpi=300)
                    if images:
                        img = images[0]
                    else:
                        logger.error("Could not convert PDF for Tesseract")
                        return ""
                except Exception as e:
                    logger.error(f"PDF conversion failed for Tesseract: {str(e)}")
                    return ""
            else:
                # Load image from bytes
                img = Image.open(image_io.BytesIO(image_bytes))
            
            # Use Tesseract to extract text
            text = pytesseract.image_to_string(img, config='--psm 6')
            logger.info(f"Tesseract extracted {len(text)} characters")
            return text
            
        except ImportError:
            logger.error("Tesseract not available - no OCR method available")
            return ""
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {str(e)}", exc_info=True)
            return ""
    
    def parse_voucher_data(self, text: str, file_name: str, file_url: str) -> Optional[Dict[str, Any]]:
        """
        Parse voucher data from OCR text
        
        Expected patterns:
        - Voucher numbers: XXXXX-CODE#### format (e.g., 12357-ROS8227)
        - Client names: Extracted from 3-letter code (ROS=Rosell, BES=Besch, etc.)
        - Dates: MM/DD/YYYY or Month DD - Month DD format
        - Amounts: hours × $30/hour (6 hours = $180, 15 hours = $450)
        """
        try:
            # Client code mapping (from existing vouchers)
            CLIENT_CODE_MAP = {
                "ROS": "Shirley Rosell",
                "BES": "Charles Besch",
                "BRO": "Christine Brock",
                "BRN": "Margot Brown",
                "BUR": "Herbert Burley",
                "THO": "Mildred Tomkins",
                "FLE": "Jessica Whelehan Trow (Ann Fletcher)",
                "JON": "Joanne Jones",
                "BEC": "Judy Tuetken",
                "LIP": "Betty Jean Lipsy",
                "LIG": "Dawn Light (Ed Witt)",
                "GRI": "Mary Poole",
                "SAL": "Marlene Morin",
                "LIV": "Christine Brock",  # Alternative code
                "RAY": "Margarita Rubio",
            }
            
            voucher_data = {
                "voucher_image_url": file_url,
                "notes": f"Auto-imported from {file_name}"
            }
            
            # Extract voucher number (e.g., "12345-ABC1234")
            voucher_pattern = r'\b(\d{4,5})\s*-?\s*([A-Z]{3,})\s*(\d{3,5})\b'
            voucher_match = re.search(voucher_pattern, text, re.IGNORECASE)
            
            if voucher_match:
                voucher_num = voucher_match.group(1)
                client_code = voucher_match.group(2).upper()[:3]
                suffix = voucher_match.group(3)
                voucher_data["voucher_number"] = f"{voucher_num}-{client_code} {suffix}"
                
                # Map client code to full name
                voucher_data["client_name"] = CLIENT_CODE_MAP.get(client_code, f"Unknown Client ({client_code})")
            else:
                # Try alternative pattern from filename
                filename_pattern = r'(\d{4,5}).*?([A-Z]{3})[^\d]*(\d+)'
                filename_match = re.search(filename_pattern, file_name, re.IGNORECASE)
                if filename_match:
                    voucher_num = filename_match.group(1)
                    client_code = filename_match.group(2).upper()
                    suffix = filename_match.group(3)
                    voucher_data["voucher_number"] = f"{voucher_num}-{client_code}{suffix}"
                    voucher_data["client_name"] = CLIENT_CODE_MAP.get(client_code, f"Unknown Client ({client_code})")
                else:
                    logger.warning(f"Could not find voucher number in {file_name}")
                    return None
            
            # Extract dates
            # Pattern 1: "July 1 - July 31" or "Aug 1 - Aug 31"
            date_range_pattern = r'([A-Z][a-z]+\s+\d{1,2})\s*-\s*([A-Z][a-z]+\s+\d{1,2}(?:,\s*\d{4})?)'
            date_range_match = re.search(date_range_pattern, text)
            
            if date_range_match:
                start_str = date_range_match.group(1).strip()
                end_str = date_range_match.group(2).strip()
                
                # Parse dates
                current_year = datetime.now().year
                try:
                    voucher_data["voucher_start_date"] = datetime.strptime(
                        f"{start_str} {current_year}", "%B %d %Y"
                    ).date().isoformat()
                except:
                    try:
                        voucher_data["voucher_start_date"] = datetime.strptime(
                            f"{start_str} {current_year}", "%b %d %Y"
                        ).date().isoformat()
                    except:
                        pass
                
                try:
                    if ',' in end_str:
                        voucher_data["voucher_end_date"] = datetime.strptime(
                            end_str, "%B %d, %Y"
                        ).date().isoformat()
                    else:
                        voucher_data["voucher_end_date"] = datetime.strptime(
                            f"{end_str} {current_year}", "%B %d %Y"
                        ).date().isoformat()
                except:
                    try:
                        voucher_data["voucher_end_date"] = datetime.strptime(
                            f"{end_str} {current_year}", "%b %d %Y"
                        ).date().isoformat()
                    except:
                        pass
            
            # Extract invoice date (usually current month)
            invoice_pattern = r'(?:Invoice Date|Date):\s*(\d{1,2}/\d{1,2}/\d{2,4})'
            invoice_match = re.search(invoice_pattern, text, re.IGNORECASE)
            if invoice_match:
                try:
                    voucher_data["invoice_date"] = datetime.strptime(
                        invoice_match.group(1), "%m/%d/%Y"
                    ).date().isoformat()
                except:
                    try:
                        date_obj = datetime.strptime(invoice_match.group(1), "%m/%d/%y")
                        voucher_data["invoice_date"] = date_obj.date().isoformat()
                    except:
                        pass
            
            # If no invoice date, calculate from voucher end date (first of next month)
            if "invoice_date" not in voucher_data:
                if "voucher_end_date" in voucher_data:
                    # Parse the end date and add 1 month
                    end_date = datetime.fromisoformat(voucher_data["voucher_end_date"])
                    # First day of next month
                    if end_date.month == 12:
                        invoice_date = datetime(end_date.year + 1, 1, 1).date()
                    else:
                        invoice_date = datetime(end_date.year, end_date.month + 1, 1).date()
                    voucher_data["invoice_date"] = invoice_date.isoformat()
                else:
                    # Fallback to first of current month
                    today = datetime.now()
                    voucher_data["invoice_date"] = today.replace(day=1).date().isoformat()
            
            # Extract hours and calculate amount (rate is always $30/hour)
            HOURLY_RATE = 30.0
            
            # First, try to find dollar amounts directly (most reliable)
            amount_patterns = [
                r'\$\s*(\d{1,4})(?:\.\d{2})?',  # "$180", "$450.00"
                r'(?:Amount|Total|Value):\s*\$?\s*(\d{1,4})',  # "Amount: 180"
                r'\b(\d{3,4})\s*(?:dollars?|\$)',  # "180 dollars"
            ]
            
            found_amount = False
            for pattern in amount_patterns:
                amount_match = re.search(pattern, text, re.IGNORECASE)
                if amount_match:
                    amount_str = amount_match.group(1).replace(',', '')
                    amount_val = float(amount_str)
                    # Validate it's a reasonable voucher amount (30-500)
                    if 30 <= amount_val <= 500:
                        voucher_data["amount"] = amount_val
                        found_amount = True
                        logger.info(f"Found amount ${amount_val} in text")
                        break
            
            # If no dollar amount found, try to extract hours
            if not found_amount:
                hours_patterns = [
                    r'(?:Units of Service|Units)\s+(\d+(?:\.\d+)?)@',  # "Units of Service 6.0@"
                    r'(\d+(?:\.\d+)?)\s*@\s*\$?\s*30',  # "6.0 @ $30"
                    r'(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)',  # "6 hours", "15 hrs"
                    r'(?:hours?|hrs?):\s*(\d+(?:\.\d+)?)',  # "Hours: 6"
                    r'\b(\d+)\s+hours?\b',  # "6 hours"
                ]
                
                hours = None
                for pattern in hours_patterns:
                    hours_match = re.search(pattern, text, re.IGNORECASE)
                    if hours_match:
                        hours = float(hours_match.group(1))
                        # Validate reasonable hours (1-20)
                        if 1 <= hours <= 20:
                            voucher_data["amount"] = hours * HOURLY_RATE
                            found_amount = True
                            logger.info(f"Found {hours} hours, calculated ${hours * HOURLY_RATE}")
                            break
            
            # Last resort: check for common amounts in text
            if not found_amount:
                # Look for exact dollar amounts in text
                if re.search(r'\b450\b', text):
                    voucher_data["amount"] = 450.0  # 15 hours × $30
                    logger.info("Found 450 in text")
                elif re.search(r'\b180\b', text):
                    voucher_data["amount"] = 180.0  # 6 hours × $30
                    logger.info("Found 180 in text")
                elif re.search(r'\b360\b', text):
                    voucher_data["amount"] = 360.0  # 12 hours × $30
                    logger.info("Found 360 in text")
                else:
                    # Absolute fallback: default to 6 hours
                    voucher_data["amount"] = 180.0
                    logger.warning(f"Could not find amount in text, defaulting to $180")
            
            # Set status
            voucher_data["status"] = "Pending"
            
            logger.info(f"Parsed voucher data: {voucher_data}")
            return voucher_data
            
        except Exception as e:
            logger.error(f"Error parsing voucher data: {str(e)}")
            return None
    
    def save_to_database(self, voucher_data: Dict[str, Any]) -> Optional[int]:
        """Save voucher to database"""
        db = db_manager.get_session()
        
        try:
            # Check if voucher already exists
            existing = db.query(Voucher).filter(
                Voucher.voucher_number == voucher_data.get("voucher_number")
            ).first()
            
            if existing:
                logger.info(f"Voucher {voucher_data.get('voucher_number')} already exists in database")
                return existing.id
            
            # Create new voucher
            voucher = Voucher(
                client_name=voucher_data.get("client_name"),
                voucher_number=voucher_data.get("voucher_number"),
                voucher_start_date=datetime.fromisoformat(voucher_data["voucher_start_date"]).date() if voucher_data.get("voucher_start_date") else None,
                voucher_end_date=datetime.fromisoformat(voucher_data["voucher_end_date"]).date() if voucher_data.get("voucher_end_date") else None,
                invoice_date=datetime.fromisoformat(voucher_data["invoice_date"]).date() if voucher_data.get("invoice_date") else None,
                amount=voucher_data.get("amount"),
                status=voucher_data.get("status", "Pending"),
                notes=voucher_data.get("notes"),
                voucher_image_url=voucher_data.get("voucher_image_url"),
                created_by="auto-sync"
            )
            
            db.add(voucher)
            db.commit()
            db.refresh(voucher)
            
            logger.info(f"Saved voucher {voucher.voucher_number} to database (ID: {voucher.id})")
            return voucher.id
            
        except Exception as e:
            logger.error(f"Error saving voucher to database: {str(e)}")
            db.rollback()
            return None
        finally:
            db.close()
    
    def save_to_google_sheet(self, voucher_data: Dict[str, Any]):
        """Append voucher to Google Sheet"""
        try:
            if not self.sheets_client:
                logger.warning("Sheets client not initialized")
                return
            
            # Open the spreadsheet
            sheet = self.sheets_client.open_by_key(GOOGLE_SHEETS_ID)
            worksheet = sheet.get_worksheet(0)  # First sheet
            
            # Format the row data to match the sheet structure
            # Columns: Client, Voucher No, Voucher Dates, Invoice Date, Amount, Invoiced Correctly?, Notes, Voucher Image
            
            voucher_dates = ""
            if voucher_data.get("voucher_start_date") and voucher_data.get("voucher_end_date"):
                start = datetime.fromisoformat(voucher_data["voucher_start_date"])
                end = datetime.fromisoformat(voucher_data["voucher_end_date"])
                voucher_dates = f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
            
            invoice_date = ""
            if voucher_data.get("invoice_date"):
                inv_date = datetime.fromisoformat(voucher_data["invoice_date"])
                invoice_date = inv_date.strftime("%m/%d/%Y")
            
            row = [
                voucher_data.get("client_name", ""),
                voucher_data.get("voucher_number", ""),
                voucher_dates,
                invoice_date,
                voucher_data.get("amount", ""),
                voucher_data.get("status", "Pending"),
                voucher_data.get("notes", "Auto-imported via OCR"),
                voucher_data.get("voucher_image_url", "")
            ]
            
            # Append the row
            worksheet.append_row(row, value_input_option='USER_ENTERED')
            logger.info(f"Added voucher {voucher_data.get('voucher_number')} to Google Sheet")
            
        except Exception as e:
            logger.error(f"Error saving to Google Sheet: {str(e)}")
    
    def sync_new_vouchers(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Main sync function - process new vouchers from Drive
        
        Args:
            hours_back: How many hours back to check for new files
        
        Returns:
            Summary of sync operation
        """
        summary = {
            "files_found": 0,
            "files_processed": 0,
            "files_failed": 0,
            "vouchers_created": [],
            "errors": []
        }
        
        try:
            # Get new files from Drive
            files = self.get_new_vouchers_from_drive(hours_back)
            summary["files_found"] = len(files)
            
            for file_info in files:
                try:
                    file_id = file_info['id']
                    file_name = file_info['name']
                    file_url = file_info.get('webViewLink', '')
                    mime_type = file_info.get('mimeType', '')
                    
                    logger.info(f"Processing file: {file_name} (type: {mime_type})")
                    
                    # Download the file
                    image_bytes = self.download_file(file_id)
                    if not image_bytes:
                        summary["files_failed"] += 1
                        summary["errors"].append(f"Failed to download {file_name}")
                        continue
                    
                    # Check if it's a PDF
                    is_pdf = mime_type == 'application/pdf' or file_name.lower().endswith('.pdf')
                    
                    # Extract text using OCR
                    text = self.extract_text_from_image(image_bytes, is_pdf=is_pdf)
                    if not text:
                        summary["files_failed"] += 1
                        summary["errors"].append(f"No text extracted from {file_name}")
                        continue
                    
                    logger.info(f"Extracted text from {file_name}:\n{text[:200]}...")
                    
                    # Parse voucher data
                    voucher_data = self.parse_voucher_data(text, file_name, file_url)
                    if not voucher_data:
                        summary["files_failed"] += 1
                        summary["errors"].append(f"Failed to parse data from {file_name}")
                        continue
                    
                    # Save to database
                    voucher_id = self.save_to_database(voucher_data)
                    if voucher_id:
                        # Save to Google Sheet
                        self.save_to_google_sheet(voucher_data)
                        
                        summary["files_processed"] += 1
                        summary["vouchers_created"].append({
                            "voucher_number": voucher_data.get("voucher_number"),
                            "client_name": voucher_data.get("client_name"),
                            "amount": voucher_data.get("amount")
                        })
                    else:
                        summary["files_failed"] += 1
                        summary["errors"].append(f"Failed to save {file_name} to database")
                    
                except Exception as e:
                    logger.error(f"Error processing file {file_info.get('name')}: {str(e)}")
                    summary["files_failed"] += 1
                    summary["errors"].append(f"Error processing {file_info.get('name')}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error in sync_new_vouchers: {str(e)}")
            summary["errors"].append(f"Sync error: {str(e)}")
        
        return summary

# Singleton instance
voucher_sync = VoucherSyncService()

def run_sync(hours_back: int = 24):
    """Run voucher sync - can be called from scheduler or API"""
    logger.info(f"Starting voucher sync (checking last {hours_back} hours)")
    summary = voucher_sync.sync_new_vouchers(hours_back)
    
    logger.info(f"Sync complete: {summary}")
    return summary

if __name__ == "__main__":
    # For testing
    result = run_sync(hours_back=48)
    print("\nSync Summary:")
    print(f"Files found: {result['files_found']}")
    print(f"Files processed: {result['files_processed']}")
    print(f"Files failed: {result['files_failed']}")
    if result['vouchers_created']:
        print("\nVouchers created:")
        for v in result['vouchers_created']:
            print(f"  - {v['voucher_number']}: {v['client_name']} (${v['amount']})")
    if result['errors']:
        print("\nErrors:")
        for err in result['errors']:
            print(f"  - {err}")


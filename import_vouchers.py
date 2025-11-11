"""
Import voucher data into the database
"""
import os
from datetime import datetime
from dotenv import load_dotenv
from portal_database import db_manager
from portal_models import Voucher

load_dotenv()

# Sample voucher data from the Google Sheet
VOUCHER_DATA = [
    {
        "client_name": "Shirley Rosell",
        "voucher_number": "10733-BES8469",
        "voucher_dates": "July 1 - July 31",
        "invoice_date": "7/1/2024",
        "amount": 180,
        "status": "Valid for July, we have invoiced with June dates",
        "notes": "This is mentioned in Melanie email"
    },
    {
        "client_name": "Charles Besch",
        "voucher_number": "10739-BRO8622",
        "voucher_dates": "Jul 1 - July 31",
        "invoice_date": "7/1/2024",
        "amount": 180,
        "status": "Valid for July, we have invoiced with June dates",
        "notes": ""
    },
    {
        "client_name": "Christine Brock",
        "voucher_number": "10787-BRN5197",
        "voucher_dates": "July 9 - July 31",
        "invoice_date": "8/1/2024",
        "amount": 180,
        "status": "Yes",
        "notes": ""
    },
    {
        "client_name": "Charles Besch",
        "voucher_number": "10784-ROS8227",
        "voucher_dates": "July 5 - July 31",
        "invoice_date": "8/1/2024",
        "amount": 180,
        "status": "Yes",
        "notes": ""
    },
    {
        "client_name": "Margot Brown",
        "voucher_number": "10843-ROS8227",
        "voucher_dates": "Aug 1 - Aug 31",
        "invoice_date": "8/1/2024",
        "amount": 180,
        "status": "already redeemed",
        "notes": "This is mentioned in Melanie email"
    },
    {
        "client_name": "Shirley Rosell",
        "voucher_number": "10848-BES8469",
        "voucher_dates": "Aug 1 - Aug 31",
        "invoice_date": "8/1/2024",
        "amount": 180,
        "status": "Valid for Aug, we have invoiced with July dates",
        "notes": ""
    },
    {
        "client_name": "Marlene Morin",
        "voucher_number": "10803-SAL 4672",
        "voucher_dates": "Aug 10- Sept 30",
        "invoice_date": "9/1/2024",
        "amount": 360,
        "status": "redeemed oct 2",
        "notes": ""
    },
    {
        "client_name": "Charles Besch",
        "voucher_number": "10889-BRN5197",
        "voucher_dates": "Aug 1 - Aug 31",
        "invoice_date": "9/1/2024",
        "amount": 180,
        "status": "paid oct 4",
        "notes": ""
    },
    {
        "client_name": "Shirley Rosell",
        "voucher_number": "10875-BRO8622",
        "voucher_dates": "Aug 1 - Aug 31",
        "invoice_date": "9/1/2024",
        "amount": 180,
        "status": "paid oct 4",
        "notes": ""
    },
    {
        "client_name": "Christine Brock",
        "voucher_number": "10866-LIV9544",
        "voucher_dates": "Aug 1 - Aug 31",
        "invoice_date": "9/1/2024",
        "amount": 180,
        "status": "paid oct 4",
        "notes": ""
    },
    {
        "client_name": "Margarita Rubio",
        "voucher_number": "10902-RAY-6179",
        "voucher_dates": "Aug 1- Sep 30",
        "invoice_date": "10/1/2024",
        "amount": 360,
        "status": "redeemed oct 2 and nov 1",
        "notes": ""
    },
    {
        "client_name": "Charles Besch",
        "voucher_number": "10906-BES8469",
        "voucher_dates": "Sept 1 - Sept 30",
        "invoice_date": "10/1/2024",
        "amount": 180,
        "status": "redeemed oct 2",
        "notes": ""
    },
    {
        "client_name": "Mildred Tomkins",
        "voucher_number": "12079-THO 0185",
        "voucher_dates": "Sep 1 - Sep 30",
        "invoice_date": "10/1/2024",
        "amount": 450,
        "status": "Redeemed 10/1",
        "notes": ""
    },
    {
        "client_name": "Jessica Whelehan Trow (Ann Fletcher)",
        "voucher_number": "12081-FLE 1484",
        "voucher_dates": "Sep 1 - Sep 30",
        "invoice_date": "10/1/2024",
        "amount": 450,
        "status": "Redeemed 10/1",
        "notes": ""
    },
    {
        "client_name": "Judy Tuetken",
        "voucher_number": "12084-BEC 1733",
        "voucher_dates": "Sep 1 - Sep 30",
        "invoice_date": "10/1/2024",
        "amount": 450,
        "status": "Redeemed 10/1",
        "notes": ""
    },
    {
        "client_name": "Joanne Jones",
        "voucher_number": "12091-JON 3551",
        "voucher_dates": "Sep 1 - Sep 30",
        "invoice_date": "10/1/2024",
        "amount": 450,
        "status": "Redeemed 10/1",
        "notes": ""
    },
    {
        "client_name": "Charles Besch",
        "voucher_number": "12112-BES8469",
        "voucher_dates": "Sep 1 - Sep 30",
        "invoice_date": "10/1/2024",
        "amount": 180,
        "status": "Redeemed 10/1",
        "notes": ""
    },
    {
        "client_name": "Herbert Burley",
        "voucher_number": "12137-BUR7225",
        "voucher_dates": "Sep 1 - Sep 30",
        "invoice_date": "10/1/2024",
        "amount": 450,
        "status": "Redeemed 10/1",
        "notes": ""
    },
    {
        "client_name": "Margot Brown",
        "voucher_number": "12136-BRN5197",
        "voucher_dates": "Sep 1 - Sep 30",
        "invoice_date": "10/1/2024",
        "amount": 180,
        "status": "Redeemed 10/1",
        "notes": ""
    },
    {
        "client_name": "Shirley Rosell",
        "voucher_number": "12162-ROS8227",
        "voucher_dates": "Sep 4 - Sep 30",
        "invoice_date": "10/1/2024",
        "amount": 180,
        "status": "Redeemed 10/1",
        "notes": ""
    },
    {
        "client_name": "Christine Brock",
        "voucher_number": "12164-BRO8622",
        "voucher_dates": "Sep 4 - Sep 30",
        "invoice_date": "10/1/2024",
        "amount": 180,
        "status": "Redeemed 10/1",
        "notes": ""
    },
    {
        "client_name": "Betty Jean Lipsy",
        "voucher_number": "12171-LIP4876",
        "voucher_dates": "Sep 17- Sep 30",
        "invoice_date": "10/1/2024",
        "amount": 180,
        "status": "Redeemed 10/1",
        "notes": ""
    },
    {
        "client_name": "Dawn Light (Ed Witt)",
        "voucher_number": "12211-LIG 6967",
        "voucher_dates": "Oct 1 - Oct 31",
        "invoice_date": "11/1/2024",
        "amount": 450,
        "status": "Redeemed 11/1",
        "notes": ""
    },
    {
        "client_name": "Charles Besch",
        "voucher_number": "12204-BES8469",
        "voucher_dates": "Oct 1- Oct 31",
        "invoice_date": "11/1/2024",
        "amount": 180,
        "status": "Redeemed 11/1",
        "notes": ""
    },
    {
        "client_name": "Mary Poole",
        "voucher_number": "12170-GRI2286",
        "voucher_dates": "Sept 11 - Oct 31",
        "invoice_date": "11/1/2024",
        "amount": 450,
        "status": "Redeemed 11/1",
        "notes": ""
    },
    {
        "client_name": "Mildred Tomkins",
        "voucher_number": "12266-THO 0185",
        "voucher_dates": "Oct 1 - Oct 31",
        "invoice_date": "11/1/2024",
        "amount": 450,
        "status": "Redeemed 11/1",
        "notes": ""
    },
    {
        "client_name": "Shirley Rosell",
        "voucher_number": "12256-ROS8227",
        "voucher_dates": "Oct 1 - Oct 31",
        "invoice_date": "11/1/2024",
        "amount": 180,
        "status": "Redeemed 11/1",
        "notes": ""
    },
    # November 2024 vouchers
    {
        "client_name": "Jessica Whelehan Trow (Ann Fletcher)",
        "voucher_number": "12275-FLE 1484",
        "voucher_dates": "Nov 1 - Nov 30",
        "invoice_date": "12/1/2024",
        "amount": 450,
        "status": "Valid for Nov",
        "notes": ""
    },
    {
        "client_name": "Joanne Jones",
        "voucher_number": "12282-JON 3551",
        "voucher_dates": "Oct 16 - Nov 30",
        "invoice_date": "12/1/2024",
        "amount": 450,
        "status": "Valid for Nov",
        "notes": ""
    },
    {
        "client_name": "Judy Tuetken",
        "voucher_number": "12289-BEC 1733",
        "voucher_dates": "Nov 1 - Nov 30",
        "invoice_date": "12/1/2024",
        "amount": 450,
        "status": "Valid for Nov",
        "notes": ""
    },
    {
        "client_name": "Charles Besch",
        "voucher_number": "12344-BES8469",
        "voucher_dates": "Nov 1 - Nov 30",
        "invoice_date": "12/1/2024",
        "amount": 180,
        "status": "Valid for Nov",
        "notes": ""
    },
    {
        "client_name": "Christine Brock",
        "voucher_number": "12321-BRO8622",
        "voucher_dates": "Nov 1 - Nov 30",
        "invoice_date": "12/1/2024",
        "amount": 180,
        "status": "Valid for Nov",
        "notes": ""
    },
    {
        "client_name": "Margot Brown",
        "voucher_number": "12358-BRN5197",
        "voucher_dates": "Nov 1 - Nov 30",
        "invoice_date": "12/1/2024",
        "amount": 180,
        "status": "Valid for Nov",
        "notes": ""
    },
    {
        "client_name": "Shirley Rosell",
        "voucher_number": "12357-ROS8227",
        "voucher_dates": "Nov 1 - Nov 30",
        "invoice_date": "12/1/2024",
        "amount": 180,
        "status": "Valid for Nov",
        "notes": ""
    }
]

def parse_date_range(date_str):
    """Parse date range string into start and end dates"""
    if not date_str or date_str == '-':
        return None, None
    
    try:
        # Common formats: "July 1 - July 31", "Aug 1 - Aug 31"
        parts = date_str.split('-')
        if len(parts) == 2:
            start_str = parts[0].strip()
            end_str = parts[1].strip()
            
            # Try to parse with current year
            current_year = datetime.now().year
            
            # Parse start date
            try:
                start_date = datetime.strptime(f"{start_str} {current_year}", "%B %d %Y").date()
            except:
                try:
                    start_date = datetime.strptime(f"{start_str} {current_year}", "%b %d %Y").date()
                except:
                    start_date = None
            
            # Parse end date
            try:
                end_date = datetime.strptime(f"{end_str} {current_year}", "%B %d %Y").date()
            except:
                try:
                    end_date = datetime.strptime(f"{end_str} {current_year}", "%b %d %Y").date()
                except:
                    try:
                        end_date = datetime.strptime(end_str, "%B %d, %Y").date()
                    except:
                        try:
                            end_date = datetime.strptime(end_str, "%b %d, %Y").date()
                        except:
                            end_date = None
            
            return start_date, end_date
    except:
        pass
    
    return None, None

def parse_invoice_date(date_str):
    """Parse invoice date string"""
    if not date_str or date_str == '-':
        return None
    
    try:
        # Try common date formats
        for fmt in ["%m/%d/%Y", "%m/%d", "%Y-%m-%d"]:
            try:
                parsed = datetime.strptime(date_str, fmt)
                # If year is not provided, use current year
                if fmt == "%m/%d":
                    return parsed.replace(year=2024).date()
                return parsed.date()
            except:
                continue
    except:
        pass
    
    return None

db = db_manager.get_session()

try:
    added_count = 0
    skipped_count = 0
    
    for voucher_data in VOUCHER_DATA:
        # Check if voucher already exists
        existing = db.query(Voucher).filter(
            Voucher.voucher_number == voucher_data["voucher_number"]
        ).first()
        
        if existing:
            print(f"⏭️  Voucher already exists: {voucher_data['voucher_number']}")
            skipped_count += 1
            continue
        
        # Parse dates
        start_date, end_date = parse_date_range(voucher_data.get("voucher_dates", ""))
        invoice_date = parse_invoice_date(voucher_data.get("invoice_date", ""))
        
        # Create voucher
        voucher = Voucher(
            client_name=voucher_data["client_name"],
            voucher_number=voucher_data["voucher_number"],
            voucher_start_date=start_date,
            voucher_end_date=end_date,
            invoice_date=invoice_date,
            amount=voucher_data["amount"],
            status=voucher_data.get("status", "Pending"),
            notes=voucher_data.get("notes"),
            created_by="system"
        )
        
        db.add(voucher)
        added_count += 1
        print(f"✅ Added: {voucher_data['client_name']} - {voucher_data['voucher_number']}")
    
    db.commit()
    
    # Show summary
    total_vouchers = db.query(Voucher).count()
    print(f"\n📊 Import Summary:")
    print(f"   Added: {added_count}")
    print(f"   Skipped: {skipped_count}")
    print(f"   Total vouchers in database: {total_vouchers}")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()


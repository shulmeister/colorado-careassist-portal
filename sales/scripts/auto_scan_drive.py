#!/usr/bin/env python3
"""
Auto-Scan Google Drive Folders for Business Cards, MyWay Routes, and Expenses

This script runs daily via Heroku Scheduler and:
1. Scans three Google Drive folders
2. Processes only NEW files (tracks processed files in DB)
3. Extracts data using Gemini AI
4. Populates Contacts/Companies, Visits/Mileage, and Expenses

Folders:
- Business Cards: 1aGO6vxe50yA-1UcanPDEVlIFrXOMRYK4
- MyWay Routes: 1IHiYvGxOaA6nyjd1Ecvgt1FbB114P5mB
- Expenses: 16OmBFwNzEKzVBBjmDtSTdM21pb3wGhSb

Usage:
    python scripts/auto_scan_drive.py

Or via Heroku:
    heroku run python scripts/auto_scan_drive.py --app careassist-unified
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Folder IDs (extracted from URLs)
FOLDERS = {
    'business_cards_jacob': '1aGO6vxe50yA-1UcanPDEVlIFrXOMRYK4',
    'business_cards_jen': '1MItlSLjrtsq2X4hJmYECEb9wn9Aeql7B',
    'business_cards_cosprings': '1m7T4QKiydcr2p55B5D0Mx0DIApK8lbak',
    'myway_routes': '1IHiYvGxOaA6nyjd1Ecvgt1FbB114P5mB',
    'expenses': '16OmBFwNzEKzVBBjmDtSTdM21pb3wGhSb'
}

# Folder type to user mapping
FOLDER_USERS = {
    'business_cards_jacob': 'jacob@coloradocareassist.com',
    'business_cards_jen': 'jen@coloradocareassist.com',
    'business_cards_cosprings': 'cosprings@coloradocareassist.com',  # UPDATE WITH ACTUAL EMAIL
    'myway_routes': 'jacob@coloradocareassist.com',
    'expenses': 'jacob@coloradocareassist.com'
}

# Default user for all imports (fallback)
DEFAULT_USER = 'jacob@coloradocareassist.com'

# Mileage rate for expense calculation
MILEAGE_RATE = 0.70  # dollars per mile


def get_db_session():
    """Create database session"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise Exception("DATABASE_URL not set")

    # Handle Heroku's postgres:// vs postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session(), engine


def ensure_table_exists(engine):
    """Ensure ProcessedDriveFile table exists"""
    from models import Base, ProcessedDriveFile
    Base.metadata.create_all(engine, tables=[ProcessedDriveFile.__table__], checkfirst=True)
    logger.info("✅ Ensured ProcessedDriveFile table exists")


def get_drive_service():
    """Initialize Google Drive service"""
    from google_drive_service import GoogleDriveService
    service = GoogleDriveService()
    if not service.enabled:
        raise Exception("Google Drive API not configured. Set GOOGLE_SERVICE_ACCOUNT_KEY.")
    return service


def get_processed_file_ids(db, folder_type: str) -> set:
    """Get set of already-processed Drive file IDs for a folder type"""
    from models import ProcessedDriveFile

    results = db.query(ProcessedDriveFile.drive_file_id).filter(
        ProcessedDriveFile.folder_type == folder_type
    ).all()

    return {r[0] for r in results}


def mark_file_processed(db, drive_file_id: str, filename: str, folder_type: str,
                        result_type: str, result_id: int = None, error_message: str = None):
    """Mark a file as processed"""
    from models import ProcessedDriveFile

    record = ProcessedDriveFile(
        drive_file_id=drive_file_id,
        filename=filename,
        folder_type=folder_type,
        result_type=result_type,
        result_id=result_id,
        error_message=error_message
    )
    db.add(record)
    db.commit()


def process_business_card(db, content: bytes, filename: str, file_id: str, user_email: str = None) -> Dict[str, Any]:
    """Process a business card image and create Contact + Company + Activity log"""
    if not user_email:
        user_email = user_email
    from models import Contact, ReferralSource, ProcessedDriveFile
    from ai_document_parser import ai_parser
    from activity_logger import ActivityLogger

    result = ai_parser.parse_business_card(content, filename)

    if not result.get('success'):
        return {'success': False, 'error': result.get('error', 'AI parsing failed')}

    first_name = (result.get('first_name') or '').strip()
    last_name = (result.get('last_name') or '').strip()
    company_name = (result.get('company') or '').strip()
    email = (result.get('email') or '').strip()
    phone = (result.get('phone') or '').strip()
    title = (result.get('title') or '').strip()
    address = (result.get('address') or '').strip()
    website = (result.get('website') or '').strip()
    notes = (result.get('notes') or '').strip()

    if not first_name and not last_name and not company_name:
        return {'success': False, 'error': 'No data extracted'}

    # Find or create Company
    company_id = None
    company_created = False
    if company_name:
        existing = db.query(ReferralSource).filter(
            ReferralSource.organization.ilike(f'%{company_name}%')
        ).first()

        if existing:
            company_id = existing.id
        else:
            new_company = ReferralSource(
                name=f"{first_name} {last_name}".strip() or company_name,
                organization=company_name,
                contact_name=f"{first_name} {last_name}".strip() if first_name or last_name else None,
                email=email,
                phone=phone,
                address=address,
                source_type="Healthcare Facility",
                status="incoming",
                notes=notes,
            )
            db.add(new_company)
            db.flush()
            company_id = new_company.id
            company_created = True

    # Find or create Contact
    contact_created = False
    contact_updated = False
    contact_id = None

    existing_contact = None
    if email:
        existing_contact = db.query(Contact).filter(Contact.email == email).first()

    if existing_contact:
        if first_name:
            existing_contact.first_name = first_name
        if last_name:
            existing_contact.last_name = last_name
        if company_name:
            existing_contact.company = company_name
        if company_id:
            existing_contact.company_id = company_id
        if title:
            existing_contact.title = title
        if phone:
            existing_contact.phone = phone
        if address:
            existing_contact.address = address
        existing_contact.updated_at = datetime.utcnow()
        existing_contact.last_seen = datetime.utcnow()
        existing_contact.account_manager = user_email
        contact_id = existing_contact.id
        contact_updated = True
    else:
        new_contact = Contact(
            first_name=first_name,
            last_name=last_name,
            name=f"{first_name} {last_name}".strip(),
            company=company_name,
            company_id=company_id,
            title=title,
            email=email,
            phone=phone,
            address=address,
            website=website,
            notes=notes,
            status="cold",
            account_manager=user_email,
            source="Auto-Scan Business Card",
            scanned_date=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_seen=datetime.utcnow(),
        )
        db.add(new_contact)
        db.flush()
        contact_id = new_contact.id
        contact_created = True

    # Log the business card scan as an activity
    if contact_id and contact_created:
        try:
            ActivityLogger.log_business_card_scan(
                db=db,
                contact_id=contact_id,
                user_email=user_email,
                contact_name=f"{first_name} {last_name}".strip(),
                filename=filename,
                commit=False  # We'll commit at the end
            )
        except Exception as e:
            logger.warning(f"Failed to log business card scan activity: {e}")

    db.commit()

    return {
        'success': True,
        'contact_id': contact_id,
        'contact_created': contact_created,
        'contact_updated': contact_updated,
        'company_id': company_id,
        'company_created': company_created,
        'name': f"{first_name} {last_name}".strip(),
        'company': company_name
    }


def process_myway_pdf(db, content: bytes, filename: str, file_id: str, user_email: str = None) -> Dict[str, Any]:
    """Process a MyWay route PDF and create Visits + Mileage entry + Activity logs"""
    if not user_email:
        user_email = DEFAULT_USER
    from models import Visit, FinancialEntry, ReferralSource, Contact
    from ai_document_parser import ai_parser
    from activity_logger import ActivityLogger

    result = ai_parser.parse_myway_pdf(content, filename)

    if not result.get('success'):
        return {'success': False, 'error': result.get('error', 'AI parsing failed')}

    visits = result.get('visits', [])
    mileage = result.get('mileage')
    pdf_date = result.get('date')

    if not visits:
        return {'success': False, 'error': 'No visits extracted'}

    # Check for duplicate visits (same date + stop number + business name)
    saved_count = 0
    skipped_count = 0
    activities_logged = 0

    for visit_data in visits:
        visit_date = visit_data.get('visit_date') or pdf_date or datetime.utcnow()
        business_name = visit_data.get('business_name', 'Unknown')
        stop_number = visit_data.get('stop_number', 0)

        # Check for existing visit
        if isinstance(visit_date, datetime):
            date_only = visit_date.date()
        else:
            date_only = visit_date

        existing = db.query(Visit).filter(
            Visit.visit_date >= datetime.combine(date_only, datetime.min.time()),
            Visit.visit_date < datetime.combine(date_only, datetime.max.time()),
            Visit.stop_number == stop_number,
            Visit.business_name.ilike(f'%{business_name[:20]}%')
        ).first()

        if existing:
            skipped_count += 1
            continue

        new_visit = Visit(
            stop_number=stop_number,
            business_name=business_name,
            address=visit_data.get('address', ''),
            city=visit_data.get('city', ''),
            notes=visit_data.get('notes', ''),
            visit_date=visit_date,
            user_email=user_email,
            created_at=datetime.utcnow()
        )
        db.add(new_visit)
        db.flush()  # Get the visit ID
        saved_count += 1

        # Find matching company (ReferralSource) by name
        company_id = None
        contact_id = None
        if business_name and business_name != 'Unknown':
            # Try to find company by name match
            company = db.query(ReferralSource).filter(
                ReferralSource.name.ilike(f'%{business_name[:30]}%')
            ).first()
            if not company:
                # Try organization field
                company = db.query(ReferralSource).filter(
                    ReferralSource.organization.ilike(f'%{business_name[:30]}%')
                ).first()
            if company:
                company_id = company.id
                # Find a contact at this company
                contact = db.query(Contact).filter(
                    Contact.company_id == company_id
                ).first()
                if contact:
                    contact_id = contact.id

        # Log the visit as an activity
        try:
            ActivityLogger.log_visit(
                db=db,
                visit_id=new_visit.id,
                business_name=business_name,
                user_email=user_email,
                visit_date=visit_date if isinstance(visit_date, datetime) else datetime.combine(visit_date, datetime.min.time()),
                contact_id=contact_id,
                company_id=company_id,
                commit=False  # We'll commit at the end
            )
            activities_logged += 1
        except Exception as e:
            logger.warning(f"Failed to log visit activity: {e}")

    # Save mileage to FinancialEntry
    mileage_saved = False
    if mileage and pdf_date:
        # Check if mileage entry already exists for this date
        if isinstance(pdf_date, datetime):
            date_only = pdf_date.date()
        else:
            date_only = pdf_date

        existing_entry = db.query(FinancialEntry).filter(
            FinancialEntry.date >= datetime.combine(date_only, datetime.min.time()),
            FinancialEntry.date < datetime.combine(date_only, datetime.max.time()),
            FinancialEntry.user_email == user_email
        ).first()

        if existing_entry:
            # Update existing entry with mileage
            existing_entry.miles_driven = mileage
            existing_entry.mileage_cost = mileage * MILEAGE_RATE
            existing_entry.total_daily_cost = (
                (existing_entry.labor_cost or 0) +
                (mileage * MILEAGE_RATE) +
                (existing_entry.materials_cost or 0)
            )
            mileage_saved = True
        else:
            # Create new entry for mileage
            new_entry = FinancialEntry(
                date=pdf_date,
                hours_worked=0,
                labor_cost=0,
                miles_driven=mileage,
                mileage_cost=mileage * MILEAGE_RATE,
                materials_cost=0,
                total_daily_cost=mileage * MILEAGE_RATE,
                user_email=user_email,
                created_at=datetime.utcnow()
            )
            db.add(new_entry)
            mileage_saved = True

    db.commit()

    return {
        'success': True,
        'visits_saved': saved_count,
        'visits_skipped': skipped_count,
        'activities_logged': activities_logged,
        'mileage': mileage,
        'mileage_saved': mileage_saved,
        'date': pdf_date.isoformat() if pdf_date else None
    }


def process_expense_receipt(db, content: bytes, filename: str, file_id: str, drive_url: str, user_email: str = None) -> Dict[str, Any]:
    """Process an expense receipt and create Expense entry"""
    if not user_email:
        user_email = DEFAULT_USER
    from models import Expense
    from ai_document_parser import ai_parser

    result = ai_parser.parse_receipt(content, filename)

    if not result.get('success'):
        return {'success': False, 'error': result.get('error', 'AI parsing failed')}

    amount = result.get('amount')
    vendor = result.get('vendor', 'Unknown')
    date_str = result.get('date')
    category = result.get('category', 'Other')
    description = result.get('description', '')

    if not amount or amount <= 0:
        return {'success': False, 'error': 'No valid amount extracted'}

    # Parse date
    expense_date = datetime.utcnow()
    if date_str:
        try:
            expense_date = datetime.strptime(date_str, '%Y-%m-%d')
        except:
            pass

    # Create expense
    new_expense = Expense(
        user_email=user_email,
        amount=amount,
        description=f"{vendor}: {description}".strip(': '),
        category=category,
        date=expense_date,
        receipt_url=drive_url,
        status='pending',
        created_at=datetime.utcnow()
    )
    db.add(new_expense)
    db.commit()

    return {
        'success': True,
        'expense_id': new_expense.id,
        'amount': amount,
        'vendor': vendor,
        'category': category,
        'date': expense_date.isoformat()
    }


def scan_folder(db, drive_service, folder_id: str, folder_type: str) -> Dict[str, Any]:
    """Scan a folder and process new files"""
    logger.info(f"\n{'='*50}")
    logger.info(f"Scanning {folder_type} folder: {folder_id}")
    logger.info(f"{'='*50}")

    # Get already processed files
    processed_ids = get_processed_file_ids(db, folder_type)
    logger.info(f"Already processed: {len(processed_ids)} files")

    # List files in folder
    folder_url = f"https://drive.google.com/drive/folders/{folder_id}"

    # Determine if we need images only or all files
    image_only = folder_type.startswith('business_cards') or folder_type == 'expenses'

    files = drive_service.list_files_in_folder(folder_url, image_only=image_only, recursive=True)
    logger.info(f"Found {len(files)} files in folder")

    # Filter to new files only
    new_files = [f for f in files if f.get('id') not in processed_ids]
    logger.info(f"New files to process: {len(new_files)}")

    results = {
        'folder_type': folder_type,
        'total_files': len(files),
        'new_files': len(new_files),
        'processed': 0,
        'success': 0,
        'errors': []
    }

    for file_info in new_files:
        file_id = file_info.get('id')
        filename = file_info.get('name', 'unknown')

        logger.info(f"Processing: {filename}")

        try:
            # Download file
            download_result = drive_service.download_file_by_id(file_id)
            if not download_result:
                error_msg = f"Failed to download {filename}"
                logger.error(error_msg)
                mark_file_processed(db, file_id, filename, folder_type, 'error', error_message=error_msg)
                results['errors'].append(error_msg)
                continue

            content, _, _ = download_result
            drive_url = f"https://drive.google.com/file/d/{file_id}/view"

            # Determine user email for this folder
            folder_user = FOLDER_USERS.get(folder_type, user_email)

            # Process based on folder type
            if folder_type.startswith('business_cards'):
                process_result = process_business_card(db, content, filename, file_id, user_email=folder_user)
                result_type = 'contact' if process_result.get('success') else 'error'
                result_id = process_result.get('contact_id')

            elif folder_type == 'myway_routes':
                process_result = process_myway_pdf(db, content, filename, file_id, user_email=folder_user)
                result_type = 'visit' if process_result.get('success') else 'error'
                result_id = None  # Multiple visits created

            elif folder_type == 'expenses':
                process_result = process_expense_receipt(db, content, filename, file_id, drive_url, user_email=folder_user)
                result_type = 'expense' if process_result.get('success') else 'error'
                result_id = process_result.get('expense_id')

            else:
                process_result = {'success': False, 'error': f'Unknown folder type: {folder_type}'}
                result_type = 'error'
                result_id = None

            # Mark as processed
            error_msg = process_result.get('error') if not process_result.get('success') else None
            mark_file_processed(db, file_id, filename, folder_type, result_type, result_id, error_msg)

            results['processed'] += 1
            if process_result.get('success'):
                results['success'] += 1
                logger.info(f"  ✅ Success: {process_result}")
            else:
                results['errors'].append(f"{filename}: {error_msg}")
                logger.warning(f"  ⚠️ Failed: {error_msg}")

            # Small delay to avoid rate limiting
            time.sleep(0.5)

        except Exception as e:
            error_msg = f"{filename}: {str(e)}"
            logger.error(f"  ❌ Error: {e}")
            results['errors'].append(error_msg)

            try:
                mark_file_processed(db, file_id, filename, folder_type, 'error', error_message=str(e))
            except:
                pass

    return results


def main():
    """Main entry point for auto-scanning"""
    logger.info("="*60)
    logger.info("AUTO-SCAN GOOGLE DRIVE FOLDERS")
    logger.info(f"Started at: {datetime.utcnow().isoformat()}")
    logger.info("="*60)

    try:
        # Initialize
        db, engine = get_db_session()
        ensure_table_exists(engine)
        drive_service = get_drive_service()

        all_results = {}

        # Scan each folder
        for folder_type, folder_id in FOLDERS.items():
            try:
                result = scan_folder(db, drive_service, folder_id, folder_type)
                all_results[folder_type] = result
            except Exception as e:
                logger.error(f"Error scanning {folder_type}: {e}")
                all_results[folder_type] = {'error': str(e)}

        # Summary
        logger.info("\n" + "="*60)
        logger.info("SCAN SUMMARY")
        logger.info("="*60)

        total_new = 0
        total_success = 0
        total_errors = 0

        for folder_type, result in all_results.items():
            if 'error' in result and isinstance(result.get('error'), str):
                logger.info(f"{folder_type}: ERROR - {result['error']}")
            else:
                new = result.get('new_files', 0)
                success = result.get('success', 0)
                errors = len(result.get('errors', []))

                total_new += new
                total_success += success
                total_errors += errors

                logger.info(f"{folder_type}: {new} new files, {success} processed successfully, {errors} errors")

        logger.info("-"*60)
        logger.info(f"TOTAL: {total_new} new files, {total_success} successful, {total_errors} errors")
        logger.info("="*60)

        # Sync Gmail activities (emails sent to/from contacts)
        logger.info("\n" + "="*60)
        logger.info("SYNCING GMAIL ACTIVITIES")
        logger.info("="*60)
        try:
            from gmail_activity_sync import GmailActivitySync
            gmail_sync = GmailActivitySync()
            if gmail_sync.gmail_service.enabled:
                gmail_sync.sync_recent_emails(db, max_results=100, since_minutes=1440)  # Last 24 hours
                logger.info("✅ Gmail activity sync completed")
            else:
                logger.info("⏭️ Gmail service not enabled, skipping")
        except Exception as e:
            logger.error(f"❌ Gmail sync error: {e}")

        # Sync RingCentral call logs
        logger.info("\n" + "="*60)
        logger.info("SYNCING RINGCENTRAL CALLS")
        logger.info("="*60)
        try:
            from ringcentral_service import RingCentralService
            rc_service = RingCentralService()
            if rc_service.enabled:
                synced = rc_service.sync_call_logs_to_activities(db, since_minutes=1440)  # Last 24 hours
                logger.info(f"✅ RingCentral sync completed: {synced} calls")
            else:
                logger.info("⏭️ RingCentral service not enabled, skipping")
        except Exception as e:
            logger.error(f"❌ RingCentral sync error: {e}")

        db.close()

        return all_results

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()

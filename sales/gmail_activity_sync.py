"""
Gmail Activity Sync - Automatically log emails as activities in CRM
"""
import logging
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from gmail_service import GmailService
from activity_logger import ActivityLogger
from models import Contact, Lead
from database import get_db

logger = logging.getLogger(__name__)


class GmailActivitySync:
    """Sync Gmail emails and log them as CRM activities"""
    
    def __init__(self):
        self.gmail_service = GmailService()
        
    def find_contact_by_email(self, db: Session, email: str) -> Optional[Contact]:
        """Find a contact by email address"""
        try:
            return db.query(Contact).filter(Contact.email == email).first()
        except Exception as e:
            logger.error(f"Error finding contact by email: {e}")
            return None
    
    def find_deal_by_contact(self, db: Session, contact_id: int) -> Optional[Lead]:
        """Find active deal for a contact"""
        try:
            return db.query(Lead).filter(
                Lead.contact_name == db.query(Contact).filter(Contact.id == contact_id).first().name,
                Lead.stage.in_(["incoming", "ongoing", "pending"])
            ).first()
        except Exception as e:
            logger.error(f"Error finding deal by contact: {e}")
            return None
    
    def extract_email_address(self, email_string: str) -> str:
        """Extract email address from 'Name <email@domain.com>' format"""
        match = re.search(r'<(.+?)>', email_string)
        if match:
            return match.group(1).lower().strip()
        return email_string.lower().strip()
    
    def sync_recent_emails(self, db: Session, max_results: int = 50, since_minutes: int = 60):
        """
        Sync recent emails and log them as activities
        
        Args:
            db: Database session
            max_results: Maximum number of emails to process
            since_minutes: Only process emails from last N minutes
        """
        if not self.gmail_service.enabled:
            logger.warning("Gmail service not enabled, skipping email sync")
            return
        
        try:
            # Get recent emails
            emails = self.gmail_service.list_recent_emails(
                max_results=max_results,
                since_minutes=since_minutes
            )
            
            if not emails:
                logger.info("No recent emails to sync")
                return
            
            synced_count = 0
            
            for email_data in emails:
                try:
                    # Extract email details
                    subject = email_data.get('subject', 'No Subject')
                    sender = self.extract_email_address(email_data.get('from', ''))
                    recipient = self.extract_email_address(email_data.get('to', ''))
                    date = email_data.get('date')
                    message_id = email_data.get('message_id')
                    gmail_url = f"https://mail.google.com/mail/u/0/#inbox/{message_id}"
                    
                    # Skip if we've already logged this email
                    from models import ActivityLog
                    existing = db.query(ActivityLog).filter(
                        ActivityLog.activity_type == "email",
                        ActivityLog.extra_data.like(f'%{message_id}%')
                    ).first()
                    
                    if existing:
                        logger.debug(f"Email already synced: {subject}")
                        continue
                    
                    # Find related contact (check both sender and recipient)
                    contact = self.find_contact_by_email(db, sender)
                    if not contact:
                        contact = self.find_contact_by_email(db, recipient)
                    
                    # Find related deal if contact exists
                    deal_id = None
                    if contact:
                        deal = self.find_deal_by_contact(db, contact.id)
                        deal_id = deal.id if deal else None
                    
                    # Log the email activity
                    ActivityLogger.log_email(
                        db=db,
                        subject=subject,
                        sender=sender,
                        recipient=recipient,
                        contact_id=contact.id if contact else None,
                        deal_id=deal_id,
                        email_url=gmail_url,
                        metadata={
                            "message_id": message_id,
                            "date": date.isoformat() if date else None,
                            "snippet": email_data.get('snippet', '')[:200]
                        }
                    )
                    
                    synced_count += 1
                    logger.info(f"Synced email: {subject}")
                    
                except Exception as e:
                    logger.error(f"Error processing email: {e}")
                    continue
            
            logger.info(f"Successfully synced {synced_count} emails")
            
        except Exception as e:
            logger.error(f"Error syncing emails: {e}")
    
    def sync_emails_for_contact(self, db: Session, contact_id: int, max_results: int = 20):
        """
        Sync all emails for a specific contact
        
        Args:
            db: Database session
            contact_id: ID of contact to sync emails for
            max_results: Maximum number of emails to fetch
        """
        try:
            contact = db.query(Contact).filter(Contact.id == contact_id).first()
            if not contact or not contact.email:
                logger.warning(f"Contact {contact_id} not found or has no email")
                return
            
            # Search for emails with this contact's email
            query = f"from:{contact.email} OR to:{contact.email}"
            emails = self.gmail_service.search_emails(query=query, max_results=max_results)
            
            if not emails:
                logger.info(f"No emails found for contact: {contact.email}")
                return
            
            synced_count = 0
            for email_data in emails:
                try:
                    subject = email_data.get('subject', 'No Subject')
                    sender = self.extract_email_address(email_data.get('from', ''))
                    recipient = self.extract_email_address(email_data.get('to', ''))
                    date = email_data.get('date')
                    message_id = email_data.get('message_id')
                    gmail_url = f"https://mail.google.com/mail/u/0/#inbox/{message_id}"
                    
                    # Skip if already logged
                    from models import ActivityLog
                    existing = db.query(ActivityLog).filter(
                        ActivityLog.activity_type == "email",
                        ActivityLog.extra_data.like(f'%{message_id}%')
                    ).first()
                    
                    if existing:
                        continue
                    
                    # Find related deal
                    deal = self.find_deal_by_contact(db, contact_id)
                    
                    # Log the email
                    ActivityLogger.log_email(
                        db=db,
                        subject=subject,
                        sender=sender,
                        recipient=recipient,
                        contact_id=contact_id,
                        deal_id=deal.id if deal else None,
                        email_url=gmail_url,
                        metadata={
                            "message_id": message_id,
                            "date": date.isoformat() if date else None
                        }
                    )
                    synced_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing email for contact: {e}")
                    continue
            
            logger.info(f"Synced {synced_count} emails for contact {contact.name}")
            
        except Exception as e:
            logger.error(f"Error syncing emails for contact: {e}")


def sync_gmail_activities_job():
    """Background job to sync Gmail activities"""
    try:
        db = next(get_db())
        syncer = GmailActivitySync()
        syncer.sync_recent_emails(db, max_results=100, since_minutes=30)
    except Exception as e:
        logger.error(f"Error in Gmail sync job: {e}")
    finally:
        db.close()


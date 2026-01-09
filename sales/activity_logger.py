"""
Activity Logger - Automatic activity logging for all CRM interactions
"""
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from models import ActivityLog

logger = logging.getLogger(__name__)


class ActivityLogger:
    """Helper class for logging all CRM activities"""
    
    @staticmethod
    def log_activity(
        db: Session,
        activity_type: str,
        description: str,
        user_email: Optional[str] = None,
        contact_id: Optional[int] = None,
        deal_id: Optional[int] = None,
        company_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        url: Optional[str] = None,
        *,
        commit: bool = True,
    ) -> Optional[ActivityLog]:
        """
        Log an activity in the CRM system
        
        Args:
            db: Database session
            activity_type: Type of activity (card_scan, visit, call, email, note, etc.)
            description: Human-readable description
            user_email: Email of user who performed the action
            contact_id: ID of related contact
            deal_id: ID of related deal
            company_id: ID of related company
            metadata: Additional data (JSON-encodable dict)
            url: Related URL (email link, document, etc.)
        
        Returns:
            Created ActivityLog object
        """
        activity_log = ActivityLog(
            activity_type=activity_type,
            description=description,
            user_email=user_email,
            contact_id=contact_id,
            deal_id=deal_id,
            company_id=company_id,
            extra_data=json.dumps(metadata) if metadata else None,
            url=url,
            created_at=datetime.utcnow(),
        )

        # IMPORTANT:
        # - When commit=True: this method owns the transaction boundaries.
        # - When commit=False: this method MUST NOT rollback the caller's transaction.
        try:
            if commit:
                db.add(activity_log)
                db.commit()
                db.refresh(activity_log)
            else:
                # Use a SAVEPOINT so failures never rollback the outer transaction
                with db.begin_nested():
                    db.add(activity_log)
                    db.flush()
                # Refresh only if we have a primary key assigned after flush
                try:
                    db.refresh(activity_log)
                except Exception:
                    # Not critical; caller will commit/rollback outer transaction
                    pass

            logger.info("Logged activity: %s - %s", activity_type, description)
            return activity_log
        except Exception as e:
            logger.error("Failed to log activity: %s", e, exc_info=True)
            if commit:
                db.rollback()
            return None
    
    @staticmethod
    def log_business_card_scan(
        db: Session,
        contact_id: int,
        user_email: str,
        contact_name: str,
        filename: str,
        *,
        commit: bool = True,
    ):
        """Log a business card scan activity"""
        return ActivityLogger.log_activity(
            db=db,
            activity_type="card_scan",
            description=f"Scanned business card for {contact_name} from {filename}",
            user_email=user_email,
            contact_id=contact_id,
            metadata={"filename": filename},
            commit=commit,
        )
    
    @staticmethod
    def log_visit(
        db: Session,
        visit_id: int,
        business_name: str,
        user_email: str,
        visit_date: datetime,
        contact_id: Optional[int] = None,
        company_id: Optional[int] = None,
        *,
        commit: bool = True,
    ):
        """Log a sales visit activity"""
        return ActivityLogger.log_activity(
            db=db,
            activity_type="visit",
            description=f"Visited {business_name} on {visit_date.strftime('%Y-%m-%d')}",
            user_email=user_email,
            contact_id=contact_id,
            company_id=company_id,
            metadata={
                "visit_id": visit_id,
                "business_name": business_name,
                "visit_date": visit_date.isoformat()
            },
            commit=commit,
        )
    
    @staticmethod
    def log_email(
        db: Session,
        subject: str,
        sender: str,
        recipient: str,
        contact_id: Optional[int] = None,
        deal_id: Optional[int] = None,
        email_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        commit: bool = True,
    ):
        """Log an email activity"""
        return ActivityLogger.log_activity(
            db=db,
            activity_type="email",
            description=f"Email: {subject}",
            user_email=sender,
            contact_id=contact_id,
            deal_id=deal_id,
            url=email_url,
            metadata={
                "subject": subject,
                "sender": sender,
                "recipient": recipient,
                **(metadata or {})
            },
            commit=commit,
        )
    
    @staticmethod
    def log_call(
        db: Session,
        contact_id: Optional[int],
        phone_number: str,
        duration: Optional[int],
        user_email: str,
        call_direction: str = "outbound",  # "outbound" or "inbound"
        metadata: Optional[Dict[str, Any]] = None,
        *,
        commit: bool = True,
    ):
        """Log a phone call activity"""
        direction_label = "Called" if call_direction == "outbound" else "Received call from"
        duration_str = f" ({duration}s)" if duration else ""
        
        return ActivityLogger.log_activity(
            db=db,
            activity_type="call",
            description=f"{direction_label} {phone_number}{duration_str}",
            user_email=user_email,
            contact_id=contact_id,
            metadata={
                "phone_number": phone_number,
                "duration": duration,
                "direction": call_direction,
                **(metadata or {})
            },
            commit=commit,
        )
    
    @staticmethod
    def log_deal_stage_change(
        db: Session,
        deal_id: int,
        old_stage: str,
        new_stage: str,
        user_email: str,
        deal_name: str,
        *,
        commit: bool = True,
    ):
        """Log a deal stage change activity"""
        return ActivityLogger.log_activity(
            db=db,
            activity_type="deal_stage_change",
            description=f"Moved '{deal_name}' from {old_stage} to {new_stage}",
            user_email=user_email,
            deal_id=deal_id,
            metadata={
                "old_stage": old_stage,
                "new_stage": new_stage,
                "deal_name": deal_name
            },
            commit=commit,
        )
    
    @staticmethod
    def log_task_created(
        db: Session,
        task_title: str,
        user_email: str,
        contact_id: Optional[int] = None,
        deal_id: Optional[int] = None,
        company_id: Optional[int] = None,
        due_date: Optional[datetime] = None,
        *,
        commit: bool = True,
    ):
        """Log a task creation activity"""
        due_str = f" (due {due_date.strftime('%Y-%m-%d')})" if due_date else ""
        return ActivityLogger.log_activity(
            db=db,
            activity_type="task_created",
            description=f"Created task: {task_title}{due_str}",
            user_email=user_email,
            contact_id=contact_id,
            deal_id=deal_id,
            company_id=company_id,
            metadata={
                "task_title": task_title,
                "due_date": due_date.isoformat() if due_date else None
            },
            commit=commit,
        )
    
    @staticmethod
    def log_note(
        db: Session,
        note_content: str,
        user_email: str,
        contact_id: Optional[int] = None,
        deal_id: Optional[int] = None,
        company_id: Optional[int] = None,
        *,
        commit: bool = True,
    ):
        """Log a note/comment activity"""
        preview = note_content[:100] + "..." if len(note_content) > 100 else note_content
        return ActivityLogger.log_activity(
            db=db,
            activity_type="note",
            description=f"Added note: {preview}",
            user_email=user_email,
            contact_id=contact_id,
            deal_id=deal_id,
            company_id=company_id,
            metadata={"note_content": note_content},
            commit=commit,
        )


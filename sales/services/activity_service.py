"""
Unified Activity Service for CRM Timeline

Handles:
- Logging activities to the unified timeline
- Deal stage change tracking
- Timeline queries for contacts/companies/deals
- Activity deduplication
"""

import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from models import ActivityLog, Contact, Deal, ReferralSource, DealStageHistory, DealContact


# Activity type constants
class ActivityType:
    NOTE = "note"
    CARD_SCAN = "card_scan"
    VISIT = "visit"
    EMAIL_SENT = "email_sent"
    EMAIL_RECEIVED = "email_received"
    CALL_INBOUND = "call_inbound"
    CALL_OUTBOUND = "call_outbound"
    CALL_MISSED = "call_missed"
    DEAL_CREATED = "deal_created"
    DEAL_STAGE_CHANGE = "deal_stage_change"
    DEAL_WON = "deal_won"
    DEAL_LOST = "deal_lost"
    CONTACT_CREATED = "contact_created"
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    DOCUMENT = "document"


def log_activity(
    db: Session,
    activity_type: str,
    title: str = None,
    description: str = None,
    contact_id: int = None,
    deal_id: int = None,
    company_id: int = None,
    user_email: str = None,
    occurred_at: datetime = None,
    direction: str = None,
    duration_seconds: int = None,
    external_id: str = None,
    external_url: str = None,
    content: str = None,
    extra_data: dict = None,
    auto_link: bool = True,
) -> ActivityLog:
    """
    Central function to log any activity to the unified timeline.

    Args:
        db: Database session
        activity_type: Type of activity (use ActivityType constants)
        title: Short title for timeline display
        description: Detailed description
        contact_id: Link to contact
        deal_id: Link to deal
        company_id: Link to company
        user_email: User who performed the action
        occurred_at: When the activity happened (defaults to now)
        direction: "inbound" or "outbound" for communications
        duration_seconds: Duration for calls
        external_id: External system ID (Gmail, RingCentral, etc.)
        external_url: Link to external system
        content: Full content (email body, note text, etc.)
        extra_data: Additional JSON metadata
        auto_link: Automatically link to company if contact has company_id

    Returns:
        Created ActivityLog record
    """
    # Auto-link: If contact has company_id, also link to company
    if auto_link and contact_id and not company_id:
        contact = db.query(Contact).filter_by(id=contact_id).first()
        if contact and contact.company_id:
            company_id = contact.company_id

    # Create activity
    activity = ActivityLog(
        activity_type=activity_type,
        title=title,
        description=description,
        contact_id=contact_id,
        deal_id=deal_id,
        company_id=company_id,
        user_email=user_email,
        occurred_at=occurred_at or datetime.utcnow(),
        direction=direction,
        duration_seconds=duration_seconds,
        external_id=external_id,
        external_url=external_url,
        content=content,
        extra_data=json.dumps(extra_data) if extra_data else None,
    )
    db.add(activity)

    # Update last_activity on related entities
    if contact_id:
        db.query(Contact).filter_by(id=contact_id).update({
            "last_activity": activity.occurred_at,
            "last_seen": activity.occurred_at
        })

    db.flush()  # Get the ID
    return activity


def update_deal_stage(
    db: Session,
    deal: Deal,
    new_stage: str,
    user_email: str = None,
) -> Optional[DealStageHistory]:
    """
    Update deal stage with history tracking.

    Args:
        db: Database session
        deal: Deal object to update
        new_stage: New stage name
        user_email: User making the change

    Returns:
        DealStageHistory record if stage changed, None if no change
    """
    if deal.stage == new_stage:
        return None  # No change

    # Calculate time in previous stage
    duration = None
    if deal.stage_entered_at:
        duration = int((datetime.utcnow() - deal.stage_entered_at).total_seconds())

    # Create history record
    history = DealStageHistory(
        deal_id=deal.id,
        from_stage=deal.stage,
        to_stage=new_stage,
        changed_by=user_email,
        duration_seconds=duration
    )
    db.add(history)

    old_stage = deal.stage

    # Update deal
    deal.stage = new_stage
    deal.stage_entered_at = datetime.utcnow()

    # Log activity
    log_activity(
        db=db,
        activity_type=ActivityType.DEAL_STAGE_CHANGE,
        title=f"Stage: {old_stage} → {new_stage}",
        description=f"Deal moved from {old_stage or 'New'} to {new_stage}",
        deal_id=deal.id,
        company_id=deal.company_id,
        user_email=user_email,
    )

    return history


def get_timeline(
    db: Session,
    contact_id: int = None,
    company_id: int = None,
    deal_id: int = None,
    activity_types: List[str] = None,
    start_date: datetime = None,
    end_date: datetime = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Get unified timeline for an entity.

    Args:
        db: Database session
        contact_id: Filter by contact
        company_id: Filter by company
        deal_id: Filter by deal
        activity_types: Filter by activity types
        start_date: Start of date range
        end_date: End of date range
        limit: Max records to return
        offset: Pagination offset

    Returns:
        Dict with timeline items and metadata
    """
    query = db.query(ActivityLog)

    # Build filters
    filters = []
    if contact_id:
        filters.append(ActivityLog.contact_id == contact_id)
    if company_id:
        filters.append(ActivityLog.company_id == company_id)
    if deal_id:
        filters.append(ActivityLog.deal_id == deal_id)

    if filters:
        query = query.filter(or_(*filters))

    if activity_types:
        query = query.filter(ActivityLog.activity_type.in_(activity_types))

    if start_date:
        query = query.filter(ActivityLog.occurred_at >= start_date)
    if end_date:
        query = query.filter(ActivityLog.occurred_at <= end_date)

    # Get total count
    total = query.count()

    # Get paginated results
    activities = query.order_by(desc(ActivityLog.occurred_at)).offset(offset).limit(limit).all()

    # Group by date for display
    grouped = {}
    for activity in activities:
        date_key = activity.display_time.date().isoformat() if activity.display_time else "Unknown"
        if date_key not in grouped:
            grouped[date_key] = []
        grouped[date_key].append(activity.to_dict())

    return {
        "timeline": [a.to_dict() for a in activities],
        "grouped": grouped,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }


def get_stale_deals(
    db: Session,
    days_threshold: int = 30,
    limit: int = 50,
) -> List[Deal]:
    """
    Get deals that have been in the same stage for too long.

    Args:
        db: Database session
        days_threshold: Number of days to consider stale
        limit: Max records to return

    Returns:
        List of stale deals
    """
    threshold_date = datetime.utcnow() - timedelta(days=days_threshold)

    deals = db.query(Deal).filter(
        Deal.stage_entered_at < threshold_date,
        Deal.archived_at.is_(None),
    ).order_by(Deal.stage_entered_at.asc()).limit(limit).all()

    return deals


def get_deal_stage_history(db: Session, deal_id: int) -> List[DealStageHistory]:
    """Get full stage history for a deal"""
    return db.query(DealStageHistory).filter_by(deal_id=deal_id).order_by(
        DealStageHistory.changed_at.asc()
    ).all()


def get_stage_analytics(db: Session) -> Dict[str, Any]:
    """
    Get analytics on stage durations.

    Returns:
        Dict with average time per stage, etc.
    """
    from sqlalchemy import func

    # Average time per stage
    stage_stats = db.query(
        DealStageHistory.from_stage,
        func.avg(DealStageHistory.duration_seconds).label("avg_duration"),
        func.count(DealStageHistory.id).label("count"),
    ).filter(
        DealStageHistory.duration_seconds.isnot(None),
        DealStageHistory.from_stage.isnot(None),
    ).group_by(DealStageHistory.from_stage).all()

    return {
        "stage_durations": [
            {
                "stage": row[0],
                "avg_duration_seconds": round(row[1]) if row[1] else 0,
                "avg_duration_days": round(row[1] / 86400, 1) if row[1] else 0,
                "transitions": row[2],
            }
            for row in stage_stats
        ]
    }


# Deal-Contact relationship helpers

def add_contact_to_deal(
    db: Session,
    deal_id: int,
    contact_id: int,
    role: str = None,
    is_primary: bool = False,
) -> DealContact:
    """
    Add a contact to a deal with optional role.

    Args:
        db: Database session
        deal_id: Deal ID
        contact_id: Contact ID
        role: Role (decision_maker, influencer, user, champion, blocker)
        is_primary: Whether this is the primary contact

    Returns:
        DealContact record
    """
    # Check if already exists
    existing = db.query(DealContact).filter_by(
        deal_id=deal_id, contact_id=contact_id
    ).first()

    if existing:
        # Update existing
        existing.role = role or existing.role
        if is_primary:
            # Clear other primary flags
            db.query(DealContact).filter(
                DealContact.deal_id == deal_id,
                DealContact.id != existing.id
            ).update({"is_primary": False})
            existing.is_primary = True
        return existing

    # If setting as primary, clear others
    if is_primary:
        db.query(DealContact).filter_by(deal_id=deal_id).update({"is_primary": False})

    # Create new
    deal_contact = DealContact(
        deal_id=deal_id,
        contact_id=contact_id,
        role=role,
        is_primary=is_primary,
    )
    db.add(deal_contact)
    return deal_contact


def remove_contact_from_deal(db: Session, deal_id: int, contact_id: int) -> bool:
    """Remove a contact from a deal"""
    result = db.query(DealContact).filter_by(
        deal_id=deal_id, contact_id=contact_id
    ).delete()
    return result > 0


def get_deal_contacts(db: Session, deal_id: int) -> List[Dict[str, Any]]:
    """Get all contacts for a deal with their roles"""
    associations = db.query(DealContact).filter_by(deal_id=deal_id).all()
    result = []
    for assoc in associations:
        contact = db.query(Contact).filter_by(id=assoc.contact_id).first()
        if contact:
            result.append({
                "contact": contact.to_dict(),
                "role": assoc.role,
                "is_primary": assoc.is_primary,
            })
    return result


def get_contact_deals(db: Session, contact_id: int) -> List[Dict[str, Any]]:
    """Get all deals for a contact with their roles"""
    associations = db.query(DealContact).filter_by(contact_id=contact_id).all()
    result = []
    for assoc in associations:
        deal = db.query(Deal).filter_by(id=assoc.deal_id).first()
        if deal:
            result.append({
                "deal": deal.to_dict(),
                "role": assoc.role,
                "is_primary": assoc.is_primary,
            })
    return result

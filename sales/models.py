from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import json

Base = declarative_base()


# ============================================================================
# Phase 1: Relationship Graph - Association Tables
# ============================================================================

class DealContact(Base):
    """Association table for Deal <-> Contact many-to-many relationship with roles"""
    __tablename__ = "deal_contacts"

    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(Integer, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(100), nullable=True)  # "decision_maker", "influencer", "user", "champion", "blocker"
    is_primary = Column(Boolean, default=False)  # Primary contact for this deal
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('deal_id', 'contact_id', name='uq_deal_contact'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "deal_id": self.deal_id,
            "contact_id": self.contact_id,
            "role": self.role,
            "is_primary": self.is_primary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================================
# Phase 1: Time-in-Stage Tracking
# ============================================================================

class DealStageHistory(Base):
    """Track every stage change for a deal - enables time-in-stage analytics"""
    __tablename__ = "deal_stage_history"

    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(Integer, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    from_stage = Column(String(100), nullable=True)  # NULL for initial stage
    to_stage = Column(String(100), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow, index=True)
    changed_by = Column(String(255), nullable=True)  # User email who made the change
    duration_seconds = Column(Integer, nullable=True)  # Time spent in from_stage

    # Relationship
    deal = relationship("Deal", back_populates="stage_history")

    def to_dict(self):
        return {
            "id": self.id,
            "deal_id": self.deal_id,
            "from_stage": self.from_stage,
            "to_stage": self.to_stage,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
            "changed_by": self.changed_by,
            "duration_seconds": self.duration_seconds,
            "duration_days": round(self.duration_seconds / 86400, 1) if self.duration_seconds else None,
        }

class Visit(Base):
    """Visit records from MyWay route PDFs"""
    __tablename__ = "visits"
    
    id = Column(Integer, primary_key=True, index=True)
    stop_number = Column(Integer, nullable=False)
    business_name = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    city = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    visit_date = Column(DateTime, default=datetime.utcnow)
    user_email = Column(String(255), nullable=True, index=True)  # Track which salesperson made the visit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        # Format visit_date as date-only string (YYYY-MM-DD) to avoid timezone issues
        visit_date_str = None
        if self.visit_date:
            # Use date() to get just the date part, avoiding timezone conversion
            visit_date_str = self.visit_date.date().isoformat() if hasattr(self.visit_date, 'date') else str(self.visit_date).split('T')[0]
        
        return {
            "id": self.id,
            "stop_number": self.stop_number,
            "business_name": self.business_name,
            "address": self.address,
            "city": self.city,
            "notes": self.notes,
            "visit_date": visit_date_str,
            "user_email": self.user_email,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class TimeEntry(Base):
    """Time tracking entries from time tracking PDFs"""
    __tablename__ = "time_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False)
    hours_worked = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "hours_worked": self.hours_worked,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Contact(Base):
    """Business contacts from scanned business cards"""
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)  # Legacy: full name
    company = Column(String(255), nullable=True)  # Legacy: company name string
    company_id = Column(Integer, ForeignKey("referral_sources.id"), nullable=True)  # FK to ReferralSource
    title = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    website = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    scanned_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(50), nullable=True)
    contact_type = Column(String(50), nullable=True)  # prospect, referral, client
    tags = Column(Text, nullable=True)  # JSON-encoded string list
    last_activity = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)  # Alias for last_activity for frontend
    account_manager = Column(String(255), nullable=True)
    source = Column(String(255), nullable=True)

    # Relationships (Phase 1: Relationship Graph)
    company_rel = relationship("ReferralSource", back_populates="contacts", foreign_keys=[company_id])
    deal_associations = relationship("DealContact", backref="contact", cascade="all, delete-orphan")
    activities = relationship("ActivityLog", back_populates="contact", foreign_keys="ActivityLog.contact_id")
    tasks = relationship("ContactTask", backref="contact_rel", cascade="all, delete-orphan")

    @property
    def deals(self):
        """Get all deals this contact is associated with"""
        return [assoc.deal for assoc in self.deal_associations if assoc.deal]

    @property
    def deals_count(self):
        """Count of deals associated with this contact"""
        return len(self.deal_associations)

    def to_dict(self):
        tag_list = []
        if self.tags:
            try:
                tag_list = json.loads(self.tags)
            except json.JSONDecodeError:
                tag_list = [tag.strip() for tag in self.tags.split(",") if tag.strip()]
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "name": self.name,
            "company": self.company,
            "company_id": self.company_id,
            "title": self.title,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "website": self.website,
            "notes": self.notes,
            "scanned_date": self.scanned_date.isoformat() if self.scanned_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status,
            "contact_type": self.contact_type,
            "tags": tag_list,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "account_manager": self.account_manager,
            "source": self.source,
        }

class FinancialEntry(Base):
    """Financial tracking entries from daily summary data"""
    __tablename__ = "financial_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False)
    hours_worked = Column(Float, nullable=False)
    labor_cost = Column(Float, nullable=False)  # Hour Total ($) - $20/hour
    miles_driven = Column(Float, nullable=True)
    mileage_cost = Column(Float, nullable=True)  # Mileage Cost ($) - $0.70/mile
    materials_cost = Column(Float, nullable=True)  # Gas/Treats/Materials ($) - cookies, gas, etc
    total_daily_cost = Column(Float, nullable=False)  # Total Daily Cost ($)
    user_email = Column(String(255), nullable=True)  # Optional: track user for this entry
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "hours_worked": self.hours_worked,
            "labor_cost": self.labor_cost,
            "miles_driven": self.miles_driven,
            "mileage_cost": self.mileage_cost,
            "materials_cost": self.materials_cost,
            "total_daily_cost": self.total_daily_cost,
            "user_email": self.user_email,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class SalesBonus(Base):
    """Sales bonuses from closed sales"""
    __tablename__ = "sales_bonuses"
    
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(255), nullable=False)
    bonus_amount = Column(Float, nullable=False)  # $250 or $350
    commission_paid = Column(Boolean, default=False)
    start_date = Column(DateTime, nullable=True)
    wellsky_status = Column(String(100), nullable=True)
    status = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "client_name": self.client_name,
            "bonus_amount": self.bonus_amount,
            "commission_paid": self.commission_paid,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "wellsky_status": self.wellsky_status,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Deal(Base):
    """Simple deals table for CRM deal tracking"""
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    company_id = Column(Integer, ForeignKey("referral_sources.id"), nullable=True)  # FK to ReferralSource
    contact_ids = Column(Text, nullable=True)  # JSON array of contact ids (legacy - use deal_contacts)
    category = Column(String(100), nullable=True)
    stage = Column(String(100), nullable=True, default="opportunity")
    stage_entered_at = Column(DateTime, nullable=True)  # Phase 1: Time-in-stage tracking
    description = Column(Text, nullable=True)
    amount = Column(Float, nullable=True, default=0)
    is_monthly_recurring = Column(Boolean, nullable=True, default=False)  # Track if revenue is MRR
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    archived_at = Column(DateTime, nullable=True)
    expected_closing_date = Column(DateTime, nullable=True)
    sales_id = Column(String(255), nullable=True)  # User email who owns this deal
    index = Column(Integer, nullable=True)
    est_weekly_hours = Column(Float, nullable=True)

    # Relationships (Phase 1: Relationship Graph)
    company = relationship("ReferralSource", back_populates="deals", foreign_keys=[company_id])
    contact_associations = relationship("DealContact", backref="deal", cascade="all, delete-orphan")
    stage_history = relationship("DealStageHistory", back_populates="deal", order_by="DealStageHistory.changed_at", cascade="all, delete-orphan")
    activities = relationship("ActivityLog", back_populates="deal", foreign_keys="ActivityLog.deal_id")

    @property
    def contacts(self):
        """Get all contacts associated with this deal"""
        return [assoc.contact for assoc in self.contact_associations if assoc.contact]

    @property
    def primary_contact(self):
        """Get the primary contact for this deal"""
        for assoc in self.contact_associations:
            if assoc.is_primary and assoc.contact:
                return assoc.contact
        # Fallback to first contact
        return self.contacts[0] if self.contacts else None

    @property
    def days_in_current_stage(self) -> int:
        """Calculate days in current stage"""
        if self.stage_entered_at:
            return (datetime.utcnow() - self.stage_entered_at).days
        return 0

    @property
    def is_stale(self) -> bool:
        """Check if deal is stale (>30 days in same stage)"""
        return self.days_in_current_stage > 30 and self.archived_at is None

    def to_dict(self):
        # Legacy contact_ids support
        ids = []
        if self.contact_ids:
            try:
                ids = json.loads(self.contact_ids)
            except json.JSONDecodeError:
                ids = []
        return {
            "id": self.id,
            "name": self.name,
            "company_id": self.company_id,
            "company_name": self.company.name if self.company else None,
            "contact_ids": ids,
            "contacts": [{"id": c.id, "name": c.name, "role": next((a.role for a in self.contact_associations if a.contact_id == c.id), None)} for c in self.contacts],
            "primary_contact_id": self.primary_contact.id if self.primary_contact else None,
            "category": self.category,
            "stage": self.stage,
            "stage_entered_at": self.stage_entered_at.isoformat() if self.stage_entered_at else None,
            "days_in_stage": self.days_in_current_stage,
            "is_stale": self.is_stale,
            "description": self.description,
            "amount": self.amount,
            "is_monthly_recurring": self.is_monthly_recurring,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "expected_closing_date": self.expected_closing_date.isoformat()
            if self.expected_closing_date
            else None,
            "sales_id": self.sales_id,
            "index": self.index,
            "est_weekly_hours": self.est_weekly_hours,
        }

class ActivityNote(Base):
    """Activity notes for tracking daily activities and observations"""
    __tablename__ = "activity_notes"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False)
    notes = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class AnalyticsCache(Base):
    """Cached analytics data for performance"""
    __tablename__ = "analytics_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    period = Column(String(50), nullable=False)  # daily, weekly, monthly, yearly
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "period": self.period,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class DashboardSummary(Base):
    """Synced dashboard summary values from Google Sheet Dashboard tab"""
    __tablename__ = "dashboard_summary"
    
    id = Column(Integer, primary_key=True, index=True)
    total_hours = Column(Float, nullable=False, default=0.0)  # From B21
    total_costs = Column(Float, nullable=False, default=0.0)  # From B22
    total_bonuses = Column(Float, nullable=False, default=0.0)  # From B23
    last_synced = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "total_hours": self.total_hours,
            "total_costs": self.total_costs,
            "total_bonuses": self.total_bonuses,
            "last_synced": self.last_synced.isoformat() if self.last_synced else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class EmailCount(Base):
    """Cached email count from Gmail API (emails sent in last 7 days)"""
    __tablename__ = "email_count"
    
    id = Column(Integer, primary_key=True, index=True)
    emails_sent_7_days = Column(Integer, nullable=False, default=0)
    user_email = Column(String, nullable=False)  # Email of the user whose emails we're counting
    last_synced = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "emails_sent_7_days": self.emails_sent_7_days,
            "user_email": self.user_email,
            "last_synced": self.last_synced.isoformat() if self.last_synced else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class ActivityLog(Base):
    """Unified activity timeline for contacts, deals, and companies - tracks all interactions"""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Activity type and description
    # Types: note, card_scan, visit, email_sent, email_received, call_inbound, call_outbound,
    #        call_missed, deal_created, deal_stage_change, deal_won, deal_lost,
    #        contact_created, task_created, task_completed, document
    activity_type = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=True)  # Phase 2: Short title for timeline display
    description = Column(Text, nullable=True)  # Human-readable description

    # Relationships (can link to multiple entities)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True, index=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True, index=True)  # Now links to deals table
    company_id = Column(Integer, ForeignKey("referral_sources.id"), nullable=True, index=True)

    # User who performed the action
    user_email = Column(String(255), nullable=True, index=True)

    # Phase 2: Communication metadata
    direction = Column(String(20), nullable=True)  # "inbound", "outbound"
    duration_seconds = Column(Integer, nullable=True)  # Call duration
    participants = Column(Text, nullable=True)  # JSON array of emails/phones
    content = Column(Text, nullable=True)  # Full email body, note content, call transcript
    attachments = Column(Text, nullable=True)  # JSON array of attachment info

    # External references
    external_id = Column(String(255), nullable=True, index=True)  # Gmail ID, RingCentral ID, Drive ID
    external_url = Column(Text, nullable=True)  # Link to original (Gmail, Drive, etc.)

    # Legacy Google Drive fields (for backward compatibility)
    file_id = Column(String(255), nullable=True, unique=True, index=True)  # Google Drive file ID
    name = Column(String(500), nullable=True)  # Document name
    url = Column(Text, nullable=True)  # Original URL
    preview_url = Column(Text, nullable=True)
    edit_url = Column(Text, nullable=True)
    owner = Column(String(255), nullable=True)
    modified_time = Column(DateTime, nullable=True)
    created_time = Column(DateTime, nullable=True)
    manually_added = Column(Boolean, default=False)

    # Additional metadata (JSON for flexibility)
    extra_data = Column(Text, nullable=True)

    # Phase 2: When the activity occurred (vs when it was logged)
    occurred_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (Phase 1)
    contact = relationship("Contact", back_populates="activities", foreign_keys=[contact_id])
    deal = relationship("Deal", back_populates="activities", foreign_keys=[deal_id])
    company = relationship("ReferralSource", back_populates="activities", foreign_keys=[company_id])

    @property
    def display_time(self):
        """Get the most relevant time for display (occurred_at or created_at)"""
        return self.occurred_at or self.created_at

    @property
    def icon(self):
        """Get icon for activity type"""
        icons = {
            "note": "📝",
            "card_scan": "📇",
            "visit": "🚗",
            "email_sent": "📧",
            "email_received": "📥",
            "call_inbound": "📞",
            "call_outbound": "📱",
            "call_missed": "📵",
            "deal_created": "🎯",
            "deal_stage_change": "🔄",
            "deal_won": "🎉",
            "deal_lost": "❌",
            "contact_created": "👤",
            "task_created": "✅",
            "task_completed": "☑️",
            "document": "📄",
        }
        return icons.get(self.activity_type, "📌")

    def to_dict(self):
        result = {
            "id": self.id,
            "activity_type": self.activity_type,
            "icon": self.icon,
            "title": self.title,
            "description": self.description,
            "contact_id": self.contact_id,
            "deal_id": self.deal_id,
            "company_id": self.company_id,
            "user_email": self.user_email,
            "direction": self.direction,
            "duration_seconds": self.duration_seconds,
            "duration_display": f"{self.duration_seconds // 60}m {self.duration_seconds % 60}s" if self.duration_seconds else None,
            "external_id": self.external_id,
            "external_url": self.external_url or self.url,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "display_time": self.display_time.isoformat() if self.display_time else None,
        }

        # Parse extra_data if present
        if self.extra_data:
            try:
                result["extra"] = json.loads(self.extra_data)
            except json.JSONDecodeError:
                result["extra"] = {}

        # Legacy fields (if present)
        if self.file_id:
            result["file_id"] = self.file_id
            result["name"] = self.name or f'Activity Log ({self.file_id[:8]}...)'
            result["preview_url"] = self.preview_url
            result["edit_url"] = self.edit_url
            result["owner"] = self.owner or 'Unknown'
            result["modified_time"] = self.modified_time.isoformat() if self.modified_time else None
            result["manually_added"] = self.manually_added

        # Include linked entity names if relationships loaded
        if self.contact:
            result["contact_name"] = self.contact.name
        if self.company:
            result["company_name"] = self.company.name
        if self.deal:
            result["deal_name"] = self.deal.name

        return result

# ============================================================================
# Lead Pipeline Models (CRM Features)
# ============================================================================

class PipelineStage(Base):
    """Pipeline stages for lead/deal management (Incoming, Ongoing, Pending, Closed/Won)"""
    __tablename__ = "pipeline_stages"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)  # e.g., "Incoming", "Ongoing", "Pending", "Closed/Won"
    order_index = Column(Integer, nullable=False, default=0)  # For display order
    weighting = Column(Float, nullable=False, default=1.0)  # Probability weighting for revenue forecasting (0.0-1.0)
    color = Column(String(50), nullable=True, default="#3b82f6")  # Hex color for UI
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    leads = relationship("Lead", back_populates="stage")
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "order_index": self.order_index,
            "weighting": self.weighting,
            "color": self.color,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class ReferralSource(Base):
    """Referral sources for tracking where leads come from (Companies)"""
    __tablename__ = "referral_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)  # Person or organization name
    organization = Column(String(255), nullable=True)  # Organization name (if person is from org)
    contact_name = Column(String(255), nullable=True)  # Contact person name
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    source_type = Column(String(100), nullable=True)  # e.g., "Healthcare Facility", "Individual", "Agency"
    location = Column(String(255), nullable=True)  # e.g., "Westminster", "Golden", "Denver" for multi-location companies
    # Enrichment fields (normalized, stable filter keys)
    county = Column(String(100), nullable=True)  # e.g., "El Paso"
    facility_type_normalized = Column(String(100), nullable=True)  # e.g., "skilled_nursing"
    website = Column(String(255), nullable=True)  # e.g., "https://example.com"
    logo_url = Column(Text, nullable=True)  # optional explicit logo/fav icon URL
    status = Column(String(50), nullable=False, default="active")  # "incoming", "ongoing", "active", "inactive"
    notes = Column(Text, nullable=True)
    # AI Enrichment fields (Phase 3)
    employee_count = Column(String(50), nullable=True)  # e.g., "50-200"
    industry = Column(String(100), nullable=True)  # e.g., "Skilled Nursing"
    enriched_at = Column(DateTime, nullable=True)  # When AI enrichment was last run
    enrichment_confidence = Column(Float, nullable=True)  # 0.0-1.0 confidence score
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (Phase 1: Relationship Graph)
    leads = relationship("Lead", back_populates="referral_source")
    contacts = relationship("Contact", back_populates="company_rel", foreign_keys="Contact.company_id")
    deals = relationship("Deal", back_populates="company", foreign_keys="Deal.company_id")
    activities = relationship("ActivityLog", back_populates="company", foreign_keys="ActivityLog.company_id")
    tasks = relationship("CompanyTask", backref="company_rel", cascade="all, delete-orphan")

    @property
    def contacts_count(self):
        """Count of contacts at this company"""
        return len(self.contacts) if self.contacts else 0

    @property
    def deals_count(self):
        """Count of deals with this company"""
        return len(self.deals) if self.deals else 0

    @property
    def active_deals_count(self):
        """Count of active (non-archived) deals"""
        return len([d for d in self.deals if d.archived_at is None]) if self.deals else 0

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "organization": self.organization,
            "contact_name": self.contact_name,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "source_type": self.source_type,
            "location": self.location,
            "county": self.county,
            "facility_type_normalized": self.facility_type_normalized,
            "website": self.website,
            "logo_url": self.logo_url,
            "status": self.status,
            "notes": self.notes,
            "employee_count": self.employee_count,
            "industry": self.industry,
            "enriched_at": self.enriched_at.isoformat() if self.enriched_at else None,
            "enrichment_confidence": self.enrichment_confidence,
            "contacts_count": self.contacts_count,
            "deals_count": self.deals_count,
            "active_deals_count": self.active_deals_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

class Lead(Base):
    """Leads/Deals in the sales pipeline"""
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)  # Lead/client name
    contact_name = Column(String(255), nullable=True)  # Contact person (if different from lead name)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(255), nullable=True)
    
    # Sales-specific fields
    source = Column(String(100), nullable=True)  # e.g., "Referral", "Direct", "Website", "Cold Call"
    payor_source = Column(String(100), nullable=True)  # e.g., "Medicaid", "Private Pay", "Medicare", "Insurance"
    expected_close_date = Column(DateTime, nullable=True)
    expected_revenue = Column(Float, nullable=True)  # Expected monthly revenue
    priority = Column(String(50), nullable=True, default="medium")  # "high", "medium", "low"
    notes = Column(Text, nullable=True)
    
    # Pipeline management
    stage_id = Column(Integer, ForeignKey("pipeline_stages.id"), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)  # For drag-and-drop ordering within stage
    status = Column(String(50), nullable=False, default="active")  # "active", "closed_won", "closed_lost"
    
    # Referral source relationship
    referral_source_id = Column(Integer, ForeignKey("referral_sources.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)  # When deal was closed (won or lost)
    
    # Relationships
    stage = relationship("PipelineStage", back_populates="leads")
    referral_source = relationship("ReferralSource", back_populates="leads")
    tasks = relationship("LeadTask", back_populates="lead", cascade="all, delete-orphan")
    activities = relationship("LeadActivity", back_populates="lead", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "contact_name": self.contact_name,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "city": self.city,
            "source": self.source,
            "payor_source": self.payor_source,
            "expected_close_date": self.expected_close_date.isoformat() if self.expected_close_date else None,
            "expected_revenue": self.expected_revenue,
            "priority": self.priority,
            "notes": self.notes,
            "stage_id": self.stage_id,
            "stage_name": self.stage.name if self.stage else None,
            "order_index": self.order_index,
            "status": self.status,
            "referral_source_id": self.referral_source_id,
            "referral_source_name": self.referral_source.name if self.referral_source else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "tasks": [task.to_dict() for task in self.tasks] if self.tasks else [],
            "activities": [activity.to_dict() for activity in self.activities] if self.activities else []
        }

class LeadTask(Base):
    """Tasks/updates for leads (e.g., Assessment Scheduled, Contract Signed)"""
    __tablename__ = "lead_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    title = Column(String(255), nullable=False)  # e.g., "Assessment Scheduled", "Contract Signed"
    description = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # "pending", "completed", "cancelled"
    completed_at = Column(DateTime, nullable=True)
    assigned_to = Column(String(255), nullable=True)  # Email of assigned user
    created_by = Column(String(255), nullable=True)  # Email of creator
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    lead = relationship("Lead", back_populates="tasks")
    
    def to_dict(self):
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "assigned_to": self.assigned_to,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class LeadActivity(Base):
    """Activity log for tracking all lead changes"""
    __tablename__ = "lead_activities"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    activity_type = Column(String(100), nullable=False)  # e.g., "created", "stage_changed", "notes_updated"
    description = Column(Text, nullable=False)  # Human-readable description
    old_value = Column(Text, nullable=True)  # For change tracking
    new_value = Column(Text, nullable=True)  # For change tracking
    user_email = Column(String(255), nullable=True)  # Who made the change
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    lead = relationship("Lead", back_populates="activities")
    
    def to_dict(self):
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "activity_type": self.activity_type,
            "description": self.description,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "user_email": self.user_email,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class CompanyTask(Base):
    """Tasks attached to referral sources (companies) for admin UI"""
    __tablename__ = "company_tasks"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("referral_sources.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, completed, cancelled
    completed_at = Column(DateTime, nullable=True)
    assigned_to = Column(String(255), nullable=True)  # Email of assigned user
    created_by = Column(String(255), nullable=True)  # Email of creator
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "assigned_to": self.assigned_to,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class ContactTask(Base):
    """Tasks attached to contacts for follow-ups and relationship management"""
    __tablename__ = "contact_tasks"

    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, completed, cancelled
    completed_at = Column(DateTime, nullable=True)
    assigned_to = Column(String(255), nullable=True)  # Email of assigned user
    created_by = Column(String(255), nullable=True)  # Email of creator
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "contact_id": self.contact_id,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "created_by": self.created_by,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class DealTask(Base):
    """Tasks attached to deals/leads for pipeline management"""
    __tablename__ = "deal_tasks"

    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, completed, cancelled
    completed_at = Column(DateTime, nullable=True)
    assigned_to = Column(String(255), nullable=True)  # Email of assigned user
    created_by = Column(String(255), nullable=True)  # Email of creator
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "deal_id": self.deal_id,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "created_by": self.created_by,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class Expense(Base):
    """Expense tracking for team members (e.g. Jacob, Maryssa)"""
    __tablename__ = "expenses"
    
    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(255), nullable=False)
    amount = Column(Float, nullable=True)
    description = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)  # e.g., "Meals", "Travel", "Supplies"
    date = Column(DateTime, nullable=False, default=datetime.utcnow)
    receipt_url = Column(Text, nullable=True)
    status = Column(String(50), default="pending")  # "pending", "approved", "paid"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_email": self.user_email,
            "amount": self.amount,
            "description": self.description,
            "category": self.category,
            "date": self.date.isoformat() if self.date else None,
            "receipt_url": self.receipt_url,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ProcessedDriveFile(Base):
    """Track processed Google Drive files to avoid duplicates during auto-scanning"""
    __tablename__ = "processed_drive_files"

    id = Column(Integer, primary_key=True, index=True)
    drive_file_id = Column(String(255), nullable=False, unique=True, index=True)
    filename = Column(String(500), nullable=True)
    folder_type = Column(String(50), nullable=False)  # 'business_cards', 'myway_routes', 'expenses'
    processed_at = Column(DateTime, default=datetime.utcnow)
    result_type = Column(String(50), nullable=True)  # 'contact', 'visit', 'expense', 'error'
    result_id = Column(Integer, nullable=True)  # ID of created record if applicable
    error_message = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "drive_file_id": self.drive_file_id,
            "filename": self.filename,
            "folder_type": self.folder_type,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "result_type": self.result_type,
            "result_id": self.result_id,
            "error_message": self.error_message
        }

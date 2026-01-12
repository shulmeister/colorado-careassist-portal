from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, Date, Numeric, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import json

Base = declarative_base()

class PortalTool(Base):
    """Portal tools available in the Colorado CareAssist Portal"""
    __tablename__ = "portal_tools"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    icon = Column(Text)  # Emoji, icon identifier, or logo URL
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "icon": self.icon,
            "description": self.description,
            "category": self.category,
            "display_order": self.display_order,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class UserSession(Base):
    """Track user login sessions"""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(255), nullable=False, index=True)
    user_name = Column(String(255), nullable=True)
    login_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    logout_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)  # Duration in seconds
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_email": self.user_email,
            "user_name": self.user_name,
            "login_time": self.login_time.isoformat() if self.login_time else None,
            "logout_time": self.logout_time.isoformat() if self.logout_time else None,
            "duration_seconds": self.duration_seconds,
            "duration_formatted": self._format_duration(),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent
        }
    
    def _format_duration(self):
        """Format duration in human-readable format"""
        if not self.duration_seconds:
            return None
        hours = self.duration_seconds // 3600
        minutes = (self.duration_seconds % 3600) // 60
        seconds = self.duration_seconds % 60
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

class ToolClick(Base):
    """Track tool clicks"""
    __tablename__ = "tool_clicks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(255), nullable=False, index=True)
    user_name = Column(String(255), nullable=True)
    tool_id = Column(Integer, nullable=False, index=True)
    tool_name = Column(String(255), nullable=False)
    tool_url = Column(Text, nullable=False)
    clicked_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_email": self.user_email,
            "user_name": self.user_name,
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "tool_url": self.tool_url,
            "clicked_at": self.clicked_at.isoformat() if self.clicked_at else None,
            "ip_address": self.ip_address
        }

class Voucher(Base):
    """AAA Voucher tracking and reconciliation"""
    __tablename__ = "vouchers"
    
    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(255), nullable=False, index=True)
    voucher_number = Column(String(100), nullable=False, unique=True, index=True)
    voucher_start_date = Column(Date, nullable=True)
    voucher_end_date = Column(Date, nullable=True)
    invoice_date = Column(Date, nullable=True, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(100), nullable=True)  # e.g., "Valid", "Redeemed", "Pending"
    notes = Column(Text, nullable=True)
    voucher_image_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "client_name": self.client_name,
            "voucher_number": self.voucher_number,
            "voucher_start_date": self.voucher_start_date.isoformat() if self.voucher_start_date else None,
            "voucher_end_date": self.voucher_end_date.isoformat() if self.voucher_end_date else None,
            "voucher_date_range": self._format_date_range(),
            "invoice_date": self.invoice_date.isoformat() if self.invoice_date else None,
            "amount": float(self.amount) if self.amount else None,
            "status": self.status,
            "notes": self.notes,
            "voucher_image_url": self.voucher_image_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by
        }
    
    def _format_date_range(self):
        """Format voucher date range"""
        if self.voucher_start_date and self.voucher_end_date:
            start = self.voucher_start_date.strftime("%b %d")
            end = self.voucher_end_date.strftime("%b %d, %Y")
            return f"{start} - {end}"
        return None

class MarketingMetricSnapshot(Base):
    """
    Cached snapshot of marketing metrics for a given data source
    (e.g., facebook_social, google_ads_overview) and date range.
    """
    __tablename__ = "marketing_metric_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(100), nullable=False, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    data = Column(Text, nullable=False)  # JSON payload
    comparison_data = Column(Text, nullable=True)  # Optional JSON
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def data_json(self):
        try:
            return json.loads(self.data) if self.data else {}
        except Exception:
            return {}
    
    def comparison_json(self):
        try:
            return json.loads(self.comparison_data) if self.comparison_data else {}
        except Exception:
            return {}
    
    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "data": self.data_json(),
            "comparison_data": self.comparison_json(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class BrevoWebhookEvent(Base):
    """
    Store Brevo marketing webhook events for metrics aggregation.
    Uses webhooks for real-time event data (opens, clicks, unsubscribes, etc.)
    """
    __tablename__ = "brevo_webhook_events"
    
    id = Column(Integer, primary_key=True, index=True)
    webhook_id = Column(Integer, nullable=True, index=True)  # Brevo webhook event ID (for deduplication)
    event_type = Column(String(50), nullable=False, index=True)  # delivered, opened, click, hardBounce, softBounce, spam, unsubscribed
    email = Column(String(255), nullable=False, index=True)
    campaign_id = Column(Integer, nullable=True, index=True)
    campaign_name = Column(String(255), nullable=True)
    date_sent = Column(DateTime, nullable=True)
    date_event = Column(DateTime, nullable=True, index=True)
    click_url = Column(Text, nullable=True)  # For click events
    event_metadata = Column(Text, nullable=True)  # JSON-encoded additional data (metadata is reserved in SQLAlchemy)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        metadata_json = {}
        if self.event_metadata:
            try:
                metadata_json = json.loads(self.event_metadata)
            except Exception:
                pass
        return {
            "id": self.id,
            "webhook_id": self.webhook_id,
            "event_type": self.event_type,
            "email": self.email,
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "date_sent": self.date_sent.isoformat() if self.date_sent else None,
            "date_event": self.date_event.isoformat() if self.date_event else None,
            "click_url": self.click_url,
            "metadata": metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OAuthToken(Base):
    """Store OAuth tokens for external service integrations"""
    __tablename__ = "oauth_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(255), nullable=False, index=True)  # User who connected the service
    service = Column(String(100), nullable=False, index=True)  # e.g., 'linkedin', 'google_ads', 'facebook'
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_type = Column(String(50), default="Bearer")
    expires_at = Column(DateTime, nullable=True)
    scope = Column(Text, nullable=True)  # Granted scopes
    extra_data = Column(JSON, nullable=True)  # Additional service-specific data
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_email": self.user_email,
            "service": self.service,
            "token_type": self.token_type,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "scope": self.scope,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
    
    def is_expired(self) -> bool:
        """Check if the token is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at


# ============================================================================
# Client Satisfaction Models
# ============================================================================

class ClientSurveyResponse(Base):
    """Client satisfaction survey responses (from Google Forms or manual entry)"""
    __tablename__ = "client_survey_responses"

    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(255), nullable=False, index=True)
    client_id = Column(String(100), nullable=True, index=True)  # WellSky client ID if available
    survey_date = Column(Date, nullable=False, index=True)

    # Satisfaction ratings (1-5 scale)
    overall_satisfaction = Column(Integer, nullable=True)  # 1-5
    caregiver_satisfaction = Column(Integer, nullable=True)  # 1-5
    communication_rating = Column(Integer, nullable=True)  # 1-5
    reliability_rating = Column(Integer, nullable=True)  # 1-5
    would_recommend = Column(Boolean, nullable=True)  # NPS-style

    # Open-ended feedback
    feedback_comments = Column(Text, nullable=True)
    improvement_suggestions = Column(Text, nullable=True)

    # Metadata
    source = Column(String(50), default="manual")  # google_form, manual, phone, email
    google_form_response_id = Column(String(255), nullable=True, unique=True)
    caregiver_name = Column(String(255), nullable=True)
    respondent_relationship = Column(String(100), nullable=True)  # client, family_member, poa

    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(255), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "client_name": self.client_name,
            "client_id": self.client_id,
            "survey_date": self.survey_date.isoformat() if self.survey_date else None,
            "overall_satisfaction": self.overall_satisfaction,
            "caregiver_satisfaction": self.caregiver_satisfaction,
            "communication_rating": self.communication_rating,
            "reliability_rating": self.reliability_rating,
            "would_recommend": self.would_recommend,
            "feedback_comments": self.feedback_comments,
            "improvement_suggestions": self.improvement_suggestions,
            "source": self.source,
            "caregiver_name": self.caregiver_name,
            "respondent_relationship": self.respondent_relationship,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ClientComplaint(Base):
    """Track client complaints and resolution"""
    __tablename__ = "client_complaints"

    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(255), nullable=False, index=True)
    client_id = Column(String(100), nullable=True, index=True)
    complaint_date = Column(Date, nullable=False, index=True)

    # Complaint details
    category = Column(String(100), nullable=True)  # scheduling, caregiver, billing, communication, care_quality, other, auto_detected
    severity = Column(String(50), default="medium")  # low, medium, high, critical
    description = Column(Text, nullable=False)
    details = Column(Text, nullable=True)  # Full message or additional context
    caregiver_involved = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)  # Internal notes, tracking IDs

    # Resolution
    status = Column(String(50), default="open", index=True)  # open, in_progress, resolved, closed
    resolution_date = Column(Date, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_by = Column(String(255), nullable=True)

    # Follow-up
    follow_up_required = Column(Boolean, default=False)
    follow_up_date = Column(Date, nullable=True)
    follow_up_notes = Column(Text, nullable=True)

    # Metadata
    source = Column(String(50), default="manual")  # phone, email, in_person, wellsky, manual
    reported_by = Column(String(255), nullable=True)  # Who reported the complaint

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "client_name": self.client_name,
            "client_id": self.client_id,
            "complaint_date": self.complaint_date.isoformat() if self.complaint_date else None,
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "details": self.details,
            "notes": self.notes,
            "caregiver_involved": self.caregiver_involved,
            "status": self.status,
            "resolution_date": self.resolution_date.isoformat() if self.resolution_date else None,
            "resolution_notes": self.resolution_notes,
            "resolved_by": self.resolved_by,
            "follow_up_required": self.follow_up_required,
            "follow_up_date": self.follow_up_date.isoformat() if self.follow_up_date else None,
            "source": self.source,
            "reported_by": self.reported_by,
            "days_open": self._days_open(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def _days_open(self):
        if self.status in ("resolved", "closed") and self.resolution_date:
            return (self.resolution_date - self.complaint_date).days
        from datetime import date
        return (date.today() - self.complaint_date).days if self.complaint_date else None


class QualityVisit(Base):
    """Quality assurance visits to clients"""
    __tablename__ = "quality_visits"

    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(255), nullable=False, index=True)
    client_id = Column(String(100), nullable=True, index=True)
    visit_date = Column(Date, nullable=False, index=True)

    # Visit details
    visit_type = Column(String(100), default="routine")  # routine, follow_up, complaint_response, initial
    conducted_by = Column(String(255), nullable=True)
    caregiver_present = Column(String(255), nullable=True)

    # Assessment scores (1-5 scale)
    home_environment_score = Column(Integer, nullable=True)
    care_quality_score = Column(Integer, nullable=True)
    client_wellbeing_score = Column(Integer, nullable=True)
    caregiver_performance_score = Column(Integer, nullable=True)
    care_plan_adherence_score = Column(Integer, nullable=True)

    # Observations
    observations = Column(Text, nullable=True)
    concerns_identified = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)

    # Follow-up
    follow_up_required = Column(Boolean, default=False)
    follow_up_date = Column(Date, nullable=True)
    follow_up_notes = Column(Text, nullable=True)

    # Status
    status = Column(String(50), default="completed")  # scheduled, completed, cancelled, rescheduled

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "client_name": self.client_name,
            "client_id": self.client_id,
            "visit_date": self.visit_date.isoformat() if self.visit_date else None,
            "visit_type": self.visit_type,
            "conducted_by": self.conducted_by,
            "caregiver_present": self.caregiver_present,
            "home_environment_score": self.home_environment_score,
            "care_quality_score": self.care_quality_score,
            "client_wellbeing_score": self.client_wellbeing_score,
            "caregiver_performance_score": self.caregiver_performance_score,
            "care_plan_adherence_score": self.care_plan_adherence_score,
            "average_score": self._average_score(),
            "observations": self.observations,
            "concerns_identified": self.concerns_identified,
            "recommendations": self.recommendations,
            "follow_up_required": self.follow_up_required,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def _average_score(self):
        scores = [s for s in [
            self.home_environment_score,
            self.care_quality_score,
            self.client_wellbeing_score,
            self.caregiver_performance_score,
            self.care_plan_adherence_score
        ] if s is not None]
        return round(sum(scores) / len(scores), 1) if scores else None


class ClientReview(Base):
    """External reviews (Google, Facebook, etc.)"""
    __tablename__ = "client_reviews"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), nullable=False, index=True)  # google, facebook, yelp, caring_com
    review_date = Column(Date, nullable=False, index=True)

    # Review details
    reviewer_name = Column(String(255), nullable=True)
    rating = Column(Integer, nullable=False)  # 1-5 stars
    review_text = Column(Text, nullable=True)

    # Response
    responded = Column(Boolean, default=False)
    response_date = Column(Date, nullable=True)
    response_text = Column(Text, nullable=True)
    responded_by = Column(String(255), nullable=True)

    # Metadata
    external_review_id = Column(String(255), nullable=True, unique=True)
    review_url = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "platform": self.platform,
            "review_date": self.review_date.isoformat() if self.review_date else None,
            "reviewer_name": self.reviewer_name,
            "rating": self.rating,
            "review_text": self.review_text,
            "responded": self.responded,
            "response_date": self.response_date.isoformat() if self.response_date else None,
            "response_text": self.response_text,
            "review_url": self.review_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CarePlanStatus(Base):
    """Track care plan status and updates"""
    __tablename__ = "care_plan_statuses"

    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(255), nullable=False, index=True)
    client_id = Column(String(100), nullable=True, index=True)

    # Care plan details
    care_plan_date = Column(Date, nullable=False)  # Date of current care plan
    next_review_date = Column(Date, nullable=True, index=True)
    status = Column(String(50), default="current", index=True)  # current, pending_review, expired, updated

    # Services
    services_authorized = Column(Text, nullable=True)  # JSON list of services
    hours_per_week = Column(Float, nullable=True)

    # Changes
    last_updated = Column(Date, nullable=True)
    update_reason = Column(Text, nullable=True)
    updated_by = Column(String(255), nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        services = []
        if self.services_authorized:
            try:
                services = json.loads(self.services_authorized)
            except Exception:
                services = [self.services_authorized]
        return {
            "id": self.id,
            "client_name": self.client_name,
            "client_id": self.client_id,
            "care_plan_date": self.care_plan_date.isoformat() if self.care_plan_date else None,
            "next_review_date": self.next_review_date.isoformat() if self.next_review_date else None,
            "status": self.status,
            "services_authorized": services,
            "hours_per_week": self.hours_per_week,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "update_reason": self.update_reason,
            "days_until_review": self._days_until_review(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def _days_until_review(self):
        if not self.next_review_date:
            return None
        from datetime import date
        return (self.next_review_date - date.today()).days


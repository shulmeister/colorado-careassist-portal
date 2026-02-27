import json
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base

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
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
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
            "user_agent": self.user_agent,
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
            "ip_address": self.ip_address,
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
            "voucher_start_date": self.voucher_start_date.isoformat()
            if self.voucher_start_date
            else None,
            "voucher_end_date": self.voucher_end_date.isoformat()
            if self.voucher_end_date
            else None,
            "voucher_date_range": self._format_date_range(),
            "invoice_date": self.invoice_date.isoformat()
            if self.invoice_date
            else None,
            "amount": float(self.amount) if self.amount else None,
            "status": self.status,
            "notes": self.notes,
            "voucher_image_url": self.voucher_image_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
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
    webhook_id = Column(
        Integer, nullable=True, index=True
    )  # Brevo webhook event ID (for deduplication)
    event_type = Column(
        String(50), nullable=False, index=True
    )  # delivered, opened, click, hardBounce, softBounce, spam, unsubscribed
    email = Column(String(255), nullable=False, index=True)
    campaign_id = Column(Integer, nullable=True, index=True)
    campaign_name = Column(String(255), nullable=True)
    date_sent = Column(DateTime, nullable=True)
    date_event = Column(DateTime, nullable=True, index=True)
    click_url = Column(Text, nullable=True)  # For click events
    event_metadata = Column(
        Text, nullable=True
    )  # JSON-encoded additional data (metadata is reserved in SQLAlchemy)
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
    user_email = Column(
        String(255), nullable=False, index=True
    )  # User who connected the service
    service = Column(
        String(100), nullable=False, index=True
    )  # e.g., 'linkedin', 'google_ads', 'facebook'
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
            "last_used_at": self.last_used_at.isoformat()
            if self.last_used_at
            else None,
        }

    def is_expired(self) -> bool:
        """Check if the token is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at


class GigiInteractionFeedback(Base):
    """Track human feedback on Gigi interactions for quality improvement"""

    __tablename__ = "gigi_interaction_feedback"

    id = Column(Integer, primary_key=True, index=True)
    interaction_type = Column(String(20), nullable=False)  # voice, sms, telegram, dm
    interaction_id = Column(String(255), nullable=True, index=True)
    user_message = Column(Text, nullable=True)
    gigi_response = Column(Text, nullable=True)
    user_identifier = Column(String(255), nullable=True)
    rating = Column(String(20), nullable=False)  # good, needs_improvement
    improvement_notes = Column(Text, nullable=True)
    memory_id = Column(String(100), nullable=True)
    reviewed_by = Column(String(255), nullable=False)
    reviewed_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "interaction_type": self.interaction_type,
            "interaction_id": self.interaction_id,
            "user_message": self.user_message,
            "gigi_response": self.gigi_response,
            "user_identifier": self.user_identifier,
            "rating": self.rating,
            "improvement_notes": self.improvement_notes,
            "memory_id": self.memory_id,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ActivityFeedItem(Base):
    """
    Centralized Activity Feed for the Portal Homepage.
    Aggregates events from Gigi, Sales, and Recruiting.
    """

    __tablename__ = "activity_feed"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(
        String(50), nullable=False, index=True
    )  # Gigi, Sales, Recruiting, Portal
    event_type = Column(
        String(100), nullable=False, index=True
    )  # deal_won, call_out, new_lead
    description = Column(
        String(255), nullable=False
    )  # "John Doe closed a deal", "Gigi handled a call-out"
    details = Column(Text, nullable=True)  # Optional longer description
    metadata_json_str = Column(
        "metadata", Text, nullable=True
    )  # JSON payload for extra data (link url, icon, etc) - aliased to avoid conflict with SQLAlchemy metadata
    icon = Column(String(50), nullable=True)  # Emoji or icon name
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def get_metadata(self):
        try:
            return json.loads(self.metadata_json_str) if self.metadata_json_str else {}
        except Exception:
            return {}

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "event_type": self.event_type,
            "description": self.description,
            "details": self.details,
            "metadata": self.get_metadata(),
            "icon": self.icon,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "time_ago": self._time_ago(),
        }

    def _time_ago(self):
        """Format relative time (e.g. '2 mins ago')"""
        if not self.created_at:
            return ""
        diff = datetime.utcnow() - self.created_at
        seconds = diff.total_seconds()

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds // 3600)}h ago"
        else:
            return f"{int(seconds // 86400)}d ago"

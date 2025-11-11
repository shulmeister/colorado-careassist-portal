from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, Date, Numeric
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


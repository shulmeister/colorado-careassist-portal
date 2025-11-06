from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

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


import logging
import json
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any, List
from portal_database import db_manager
from portal_models import ActivityFeedItem

logger = logging.getLogger(__name__)

class ActivityStreamService:
    def log_activity(self, 
                    source: str, 
                    description: str, 
                    event_type: str = "info", 
                    details: Optional[str] = None, 
                    icon: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None):
        """
        Log an activity to the centralized feed.
        """
        db = db_manager.get_session()
        try:
            # Default icons based on source/type
            if not icon:
                if source == "Gigi":
                    icon = "🤖"
                elif source == "Sales":
                    icon = "💰"
                elif source == "Recruiting":
                    icon = "👥"
                elif source == "Operations":
                    icon = "🏥"
                else:
                    icon = "📌"
            
            activity = ActivityFeedItem(
                source=source,
                event_type=event_type,
                description=description,
                details=details,
                icon=icon,
                metadata_json_str=json.dumps(metadata) if metadata else None
            )
            
            db.add(activity)
            db.commit()
            logger.info(f"Logged activity: [{source}] {description}")
            return activity
            
        except Exception as e:
            logger.error(f"Error logging activity: {e}")
            db.rollback()
            return None
        finally:
            db.close()

    def get_recent_activities(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent activities for the dashboard"""
        db = db_manager.get_session()
        try:
            activities = db.query(ActivityFeedItem)\
                .order_by(ActivityFeedItem.created_at.desc())\
                .limit(limit)\
                .all()
            
            return [a.to_dict() for a in activities]
        except Exception as e:
            logger.error(f"Error fetching activities: {e}")
            return []
        finally:
            db.close()

activity_stream = ActivityStreamService()

"""
List all tools and their URLs
"""
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()

try:
    tools = db.query(PortalTool).order_by(PortalTool.display_order).all()
    for t in tools:
        print(f"{t.name} | {t.url}")
finally:
    db.close()

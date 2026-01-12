
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()
try:
    tools = db.query(PortalTool).all()
    print(f"Total tools in DB: {len(tools)}")
    for tool in tools:
        print(f"ID: {tool.id}, Name: {tool.name}, URL: {tool.url}")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()

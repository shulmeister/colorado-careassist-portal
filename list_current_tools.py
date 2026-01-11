
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()
try:
    tools = db.query(PortalTool).all()
    print(f"Total tools: {len(tools)}")
    print("-" * 60)
    print(f"{'ID':<4} | {'Name':<25} | {'Description':<40} | {'URL'}")
    print("-" * 60)
    for tool in tools:
        desc = tool.description[:37] + "..." if tool.description and len(tool.description) > 37 else (tool.description or "")
        print(f"{tool.id:<4} | {tool.name:<25} | {desc:<40} | {tool.url}")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()

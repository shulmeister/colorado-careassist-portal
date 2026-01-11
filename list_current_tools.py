
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()
try:
    tools = db.query(PortalTool).all()
    print(f"Total tools: {len(tools)}")
    print("-" * 60)
    print(f"{'ID':<4} | {'Name':<25} | {'Icon':<10} | {'Description':<40} | {'URL'}")
    print("-" * 100)
    for tool in tools:
        desc = tool.description[:37] + "..." if tool.description and len(tool.description) > 37 else (tool.description or "")
        icon = tool.icon[:10] + "..." if tool.icon and len(tool.icon) > 10 else (tool.icon or "")
        print(f"{tool.id:<4} | {tool.name:<25} | {icon:<10} | {desc:<40} | {tool.url}")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()

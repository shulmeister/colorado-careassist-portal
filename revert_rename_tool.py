
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()
try:
    tool = db.query(PortalTool).filter(PortalTool.id == 86).first()
    if tool:
        print(f"Reverting {tool.name} to 'Google'")
        tool.name = "Google"
        db.commit()
        print("Done.")
    else:
        print("Tool 86 not found.")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()

"""
Update CBI logo to use local file
"""
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()

try:
    tool = db.query(PortalTool).filter(PortalTool.name == "Colorado Bureau of Investigation").first()
    if tool:
        print(f"Current CBI Icon: {tool.icon}")
        tool.icon = "/static/logos/cbi-logo.png"
        db.commit()
        print("✅ Updated CBI logo to local file: /static/logos/cbi-logo.png")
    else:
        print("❌ CBI tool not found")
except Exception as e:
    print(f"❌ Error: {str(e)}")
    db.rollback()
finally:
    db.close()


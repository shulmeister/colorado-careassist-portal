"""
Update RingCentral logo to use text-based logo
"""
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()

try:
    tool = db.query(PortalTool).filter(PortalTool.name == "RingCentral").first()
    if tool:
        print(f"Current RingCentral Icon: {tool.icon}")
        tool.icon = "/static/logos/ringcentral-text.png"
        db.commit()
        print("✅ Updated RingCentral logo to text-based logo: /static/logos/ringcentral-text.png")
    else:
        print("❌ RingCentral tool not found")
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()





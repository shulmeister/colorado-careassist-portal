"""
Update VA HSRM logo to use CCRA logo
"""
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()

try:
    tool = db.query(PortalTool).filter(PortalTool.name == "VA HSRM").first()
    if tool:
        print(f"Current VA HSRM Icon: {tool.icon}")
        tool.icon = "/static/logos/va-hsrm.svg"
        db.commit()
        print("✅ Updated VA HSRM logo to CCRA logo: /static/logos/va-hsrm.svg")
    else:
        print("❌ VA HSRM tool not found")
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()


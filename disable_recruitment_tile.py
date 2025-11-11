"""
Disable the Recruitment Dashboard tile since the app doesn't exist yet
"""
import os
from dotenv import load_dotenv
from portal_database import db_manager
from portal_models import PortalTool

load_dotenv()

db = db_manager.get_session()

try:
    # Find and disable Recruitment Dashboard tile
    recruitment_dashboard = db.query(PortalTool).filter(
        PortalTool.name == "Recruitment Dashboard"
    ).first()
    
    if recruitment_dashboard:
        recruitment_dashboard.is_active = False
        db.commit()
        print(f"✅ Disabled Recruitment Dashboard tile")
        print(f"   (App doesn't exist yet at {recruitment_dashboard.url})")
    else:
        print(f"❌ Recruitment Dashboard tile not found")
    
    # Verify Sales Dashboard is still active
    sales_dashboard = db.query(PortalTool).filter(
        PortalTool.name == "Sales Dashboard"
    ).first()
    
    if sales_dashboard and sales_dashboard.is_active:
        print(f"✅ Sales Dashboard is active at {sales_dashboard.url}")
    
    print(f"\n📊 Active Dashboard Tiles:")
    active_dashboards = db.query(PortalTool).filter(
        PortalTool.is_active == True,
        PortalTool.name.like("%Dashboard%")
    ).all()
    
    for tool in active_dashboards:
        print(f"   {tool.icon} {tool.name} → {tool.url}")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()


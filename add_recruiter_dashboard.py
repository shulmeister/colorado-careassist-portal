import os
from dotenv import load_dotenv
from portal_database import db_manager
from portal_models import PortalTool

load_dotenv()

db = db_manager.get_session()

try:
    # Check if Recruiter Dashboard exists
    existing = db.query(PortalTool).filter(PortalTool.name == "Recruiter Dashboard").first()
    
    if existing:
        print(f"✅ Recruiter Dashboard already exists (ID: {existing.id})")
        print(f"   Active: {existing.is_active}")
        print(f"   URL: {existing.url}")
        
        # Make sure it's active
        if not existing.is_active:
            existing.is_active = True
            db.commit()
            print("   ✅ Reactivated!")
    else:
        # Add Recruiter Dashboard
        tool_data = {
            "name": "Recruiter Dashboard",
            "url": "/recruitment",
            "icon": "👥",
            "description": "View recruitment metrics and candidate pipeline",
            "category": "Analytics",
            "display_order": 4,
            "is_active": True
        }
        
        tool = PortalTool(**tool_data)
        db.add(tool)
        db.commit()
        print(f"✅ Added Recruiter Dashboard (ID: {tool.id})")
    
    # Show all active tools
    print("\n📊 All Active Tools:")
    print("-" * 60)
    active_tools = db.query(PortalTool).filter(PortalTool.is_active == True).order_by(PortalTool.display_order, PortalTool.name).all()
    for tool in active_tools:
        print(f"  {tool.display_order:2d}. {tool.icon} {tool.name:30s} → {tool.url}")
    
    print(f"\n✅ Total active tools: {len(active_tools)}")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()


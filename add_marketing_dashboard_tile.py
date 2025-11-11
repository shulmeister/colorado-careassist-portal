"""
Utility script to add the Marketing Dashboard tile to the portal.
"""
import os
from dotenv import load_dotenv
from portal_database import db_manager
from portal_models import PortalTool

load_dotenv()

db = db_manager.get_session()

try:
    marketing_tool = db.query(PortalTool).filter(
        PortalTool.name == "Marketing Dashboard"
    ).first()
    
    if marketing_tool:
        marketing_tool.url = "/marketing"
        marketing_tool.icon = "📢"
        marketing_tool.description = "Marketing performance dashboard (Social + Ads)"
        marketing_tool.category = "Analytics"
        marketing_tool.is_active = True
        print("✅ Updated existing Marketing Dashboard tile.")
    else:
        marketing_tool = PortalTool(
            name="Marketing Dashboard",
            url="/marketing",
            icon="📢",
            description="Marketing performance dashboard (Social + Ads)",
            category="Analytics",
            display_order=3,
            is_active=True
        )
        db.add(marketing_tool)
        print("✅ Added Marketing Dashboard tile.")
    
    db.commit()
    
    tools = db.query(PortalTool).filter(PortalTool.is_active == True).order_by(
        PortalTool.display_order, PortalTool.name
    ).all()
    print(f"\n📊 Total active tools: {len(tools)}")
    for tool in tools:
        print(f" - {tool.icon or '🔗'} {tool.name} ({tool.url})")

except Exception as exc:
    print(f"❌ Error updating marketing tile: {exc}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()


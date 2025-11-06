"""
Add Secure Fax and VA HSRM tools to the portal
"""
import os
from dotenv import load_dotenv
from portal_database import db_manager
from portal_models import PortalTool

load_dotenv()

db = db_manager.get_session()

try:
    tools_to_add = [
        {
            "name": "Secure Fax",
            "url": "https://id.alohi.com/",
            "icon": "📠",
            "description": "Secure fax service",
            "category": "Communication",
            "display_order": 22
        },
        {
            "name": "VA HSRM",
            "url": "https://ccracommunity.va.gov/",
            "icon": "🏛️",
            "description": "VA Health Services Resource Management",
            "category": "Healthcare",
            "display_order": 23
        }
    ]
    
    for tool_data in tools_to_add:
        # Check if tool already exists
        existing = db.query(PortalTool).filter(PortalTool.url == tool_data["url"]).first()
        
        if existing:
            print(f"⏭️  Tool already exists: {existing.name}")
        else:
            tool = PortalTool(**tool_data)
            db.add(tool)
            print(f"✅ Added: {tool_data['icon']} {tool_data['name']}")
    
    db.commit()
    
    # Show all tools
    all_tools = db.query(PortalTool).filter(PortalTool.is_active == True).order_by(PortalTool.display_order, PortalTool.name).all()
    print(f"\n📊 Total active tools: {len(all_tools)}")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()


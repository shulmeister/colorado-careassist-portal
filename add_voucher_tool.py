"""
Add Voucher List tool to the portal
"""
import os
from dotenv import load_dotenv
from portal_database import db_manager
from portal_models import PortalTool

load_dotenv()

db = db_manager.get_session()

try:
    tool_data = {
        "name": "Voucher List",
        "url": "https://docs.google.com/spreadsheets/d/1f0lk54-zyAnZd2Ok9KNezHgTjYeuH4zCwaLASGjMZAM/edit?usp=sharing",
        "icon": "📋",
        "description": "AAA Voucher Reconciliation spreadsheet",
        "category": "Administration",
        "display_order": 25
    }
    
    # Check if tool already exists
    existing = db.query(PortalTool).filter(PortalTool.url == tool_data["url"]).first()
    
    if existing:
        print(f"⏭️  Tool already exists: {existing.name}")
    else:
        tool = PortalTool(**tool_data)
        db.add(tool)
        db.commit()
        print(f"✅ Added: {tool_data['icon']} {tool_data['name']}")
    
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


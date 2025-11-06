"""
Add Zingage and Joke of the Day tools
"""
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()

try:
    tools_to_add = [
        {
            "name": "Zingage",
            "url": "https://portal.zingage.com/login",
            "icon": "https://www.google.com/s2/favicons?domain=zingage.com&sz=128",
            "description": "Zingage portal login",
            "category": "Productivity",
            "display_order": 25
        },
        {
            "name": "Joke of the Day",
            "url": "#joke-of-the-day",
            "icon": "😄",
            "description": "Get a daily dose of humor",
            "category": "Fun",
            "display_order": 26
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
            print(f"✅ Added: {tool_data.get('icon', '🔗')} {tool_data['name']}")
    
    db.commit()
    print(f"\n📊 Total active tools: {db.query(PortalTool).filter(PortalTool.is_active == True).count()}")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()


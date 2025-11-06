"""
Update logos to use the new high-quality versions
"""
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()

try:
    # Map of tool names to updated logo paths
    LOGO_UPDATES = {
        "SocialPilot": "/static/logos/socialpilot-new.png",
        "Google Ads": "/static/logos/google-ads-new.png",
        "Facebook Ads Manager": "/static/logos/facebook-ads.png",
        "Adams Keegan Efficenter": "/static/logos/adams-keegan.svg",
    }
    
    updated_count = 0
    
    for tool_name, logo_url in LOGO_UPDATES.items():
        tool = db.query(PortalTool).filter(PortalTool.name == tool_name).first()
        if tool:
            old_icon = tool.icon
            tool.icon = logo_url
            updated_count += 1
            print(f"✅ Updated: {tool_name}")
            print(f"   Old: {old_icon}")
            print(f"   New: {logo_url}")
        else:
            print(f"⏭️  Not found: {tool_name}")
    
    db.commit()
    print(f"\n🎉 Updated {updated_count} logos!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()


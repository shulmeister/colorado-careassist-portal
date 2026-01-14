"""
Update logos for portal dashboard tiles
"""
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()

try:
    # Map of tool names to updated logo paths
    LOGO_UPDATES = {
        "Google Business Profile": "/static/logos/google-business-profile.png",
        "Hostinger": "/static/logos/hostinger-new.avif",
        "GoFormz": "/static/logos/goformz.png",
        "QuickBooks": "/static/logos/quickbooks-online.png",
        "QuickBooks Online": "/static/logos/quickbooks-online.png",
        "Google Ads": "/static/logos/google-ads-icon.png",
    }

    updated_count = 0

    for tool_name, logo_url in LOGO_UPDATES.items():
        tool = db.query(PortalTool).filter(PortalTool.name == tool_name).first()
        if tool:
            old_icon = tool.icon
            tool.icon = logo_url
            updated_count += 1
            print(f"Updated: {tool_name}")
            print(f"   Old: {old_icon}")
            print(f"   New: {logo_url}")
        else:
            print(f"Not found: {tool_name}")

    db.commit()
    print(f"\nUpdated {updated_count} logos!")

except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()

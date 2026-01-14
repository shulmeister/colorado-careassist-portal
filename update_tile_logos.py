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
        # QuickBooks (named "Intuit" in database) - smaller version
        "Intuit": "/static/logos/quickbooks-online-small.png",
        # Adams Keegan
        "Adams Keegan": "/static/logos/adams-keegan.png",
        # Predis.ai
        "Predis.ai": "/static/logos/predis.webp",
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

    # Handle tiles by current icon URL (when they share generic names like "Meta" or "Google")
    ICON_UPDATES = {
        # Meta Business Suite
        "https://static.xx.fbcdn.net/rsrc.php/v3/yJ/r/8dK8qmqxzpA.png": "/static/logos/meta-business-suite.webp",
        # Facebook Ads Manager
        "https://static.xx.fbcdn.net/rsrc.php/v3/yZ/r/OTB6Bkrf2Ah.png": "/static/logos/facebook-ads-manager.jpeg",
        # Google Ads (named "Google" in database)
        "https://www.gstatic.com/ads-frontend/compass_icons/compass_icon_192.png": "/static/logos/google-ads-icon.webp",
    }

    for old_icon, new_icon in ICON_UPDATES.items():
        tool = db.query(PortalTool).filter(PortalTool.icon == old_icon).first()
        if tool:
            tool.icon = new_icon
            updated_count += 1
            print(f"Updated by icon: {tool.name}")
            print(f"   Old: {old_icon}")
            print(f"   New: {new_icon}")
        else:
            print(f"Not found by icon: {old_icon[:50]}...")

    db.commit()
    print(f"\nUpdated {updated_count} logos!")

except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()

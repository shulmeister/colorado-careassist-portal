"""
Update tool icons to use high-quality logo URLs
Using direct favicon URLs and better sources for crisp, vector-quality logos
"""
from portal_database import db_manager
from portal_models import PortalTool

# Map of tool names to high-quality logo URLs
# Using direct favicon URLs and Google's favicon service with larger sizes
LOGO_MAP = {
    "Gmail": "https://www.google.com/s2/favicons?domain=gmail.com&sz=128",
    "Google Drive": "https://www.google.com/s2/favicons?domain=drive.google.com&sz=128",
    "Google Calendar": "https://www.google.com/s2/favicons?domain=calendar.google.com&sz=128",
    "RingCentral": "https://www.google.com/s2/favicons?domain=ringcentral.com&sz=128",
    "GoFormz": "https://www.google.com/s2/favicons?domain=goformz.com&sz=128",
    "Mailchimp": "https://www.google.com/s2/favicons?domain=mailchimp.com&sz=128",
    "Adams Keegan Efficenter": "https://www.google.com/s2/favicons?domain=adamskeegan.com&sz=128",
    "Wellsky": "https://www.google.com/s2/favicons?domain=wellsky.com&sz=128",
    "QuickBooks": "https://www.google.com/s2/favicons?domain=intuit.com&sz=128",
    "Predis.ai": "https://www.google.com/s2/favicons?domain=predis.ai&sz=128",
    "WordPress": "https://www.google.com/s2/favicons?domain=wordpress.com&sz=128",
    "Facebook Ads Manager": "https://www.google.com/s2/favicons?domain=facebook.com&sz=128",
    "Meta Business Suite": "https://www.google.com/s2/favicons?domain=facebook.com&sz=128",
    "Google Ads": "https://www.google.com/s2/favicons?domain=ads.google.com&sz=128",
    "Google Analytics": "https://www.google.com/s2/favicons?domain=analytics.google.com&sz=128",
}

db = db_manager.get_session()

try:
    updated_count = 0
    
    for tool_name, logo_url in LOGO_MAP.items():
        tool = db.query(PortalTool).filter(PortalTool.name == tool_name).first()
        if tool:
            tool.icon = logo_url
            updated_count += 1
            print(f"✅ Updated: {tool_name}")
        else:
            print(f"⏭️  Not found: {tool_name}")
    
    db.commit()
    print(f"\n🎉 Updated {updated_count} tools with high-quality logos!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()

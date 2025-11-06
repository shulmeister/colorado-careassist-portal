"""
Update tool icons to use actual logos instead of emojis
"""
from portal_database import db_manager
from portal_models import PortalTool

# Map of tool names to their logo URLs
LOGO_MAP = {
    "Gmail": "https://www.google.com/s2/favicons?domain=gmail.com&sz=64",
    "Google Drive": "https://www.google.com/s2/favicons?domain=drive.google.com&sz=64",
    "Google Calendar": "https://www.google.com/s2/favicons?domain=calendar.google.com&sz=64",
    "RingCentral": "https://www.google.com/s2/favicons?domain=ringcentral.com&sz=64",
    "GoFormz": "https://www.google.com/s2/favicons?domain=goformz.com&sz=64",
    "Mailchimp": "https://www.google.com/s2/favicons?domain=mailchimp.com&sz=64",
    "Adams Keegan Efficenter": "https://www.google.com/s2/favicons?domain=adamskeegan.com&sz=64",
    "Wellsky": "https://www.google.com/s2/favicons?domain=wellsky.com&sz=64",
    "QuickBooks": "https://www.google.com/s2/favicons?domain=intuit.com&sz=64",
    "SocialPilot": "https://www.google.com/s2/favicons?domain=socialpilot.co&sz=64",
    "WordPress": "https://www.google.com/s2/favicons?domain=wordpress.com&sz=64",
    "Facebook Ads Manager": "https://www.google.com/s2/favicons?domain=facebook.com&sz=64",
    "Meta Business Suite": "https://www.google.com/s2/favicons?domain=facebook.com&sz=64",
    "Google Ads": "https://www.google.com/s2/favicons?domain=ads.google.com&sz=64",
    "Google Analytics": "https://www.google.com/s2/favicons?domain=analytics.google.com&sz=64",
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
    print(f"\n🎉 Updated {updated_count} tools with logos!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()


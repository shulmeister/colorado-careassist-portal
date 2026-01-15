"""Update Google Ads, Predis.ai, and QuickBooks to use smaller logos"""
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()

updates = [
    ("Google Ads", "/static/logos/google-ads-small.png"),
    ("Predis.ai", "/static/logos/predis-small.png"),
    ("Intuit QuickBooks", "/static/logos/quickbooks-online-small.png"),
]

for name, new_icon in updates:
    tool = db.query(PortalTool).filter(PortalTool.name == name).first()
    if tool:
        old_icon = tool.icon_url
        tool.icon_url = new_icon
        print(f"Updated {name}: {old_icon} -> {new_icon}")
    else:
        print(f"Tool not found: {name}")

db.commit()
db.close()
print("Done!")

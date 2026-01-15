"""Update Google Ads, Predis.ai, and QuickBooks to use smaller logos"""
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()

# Update by matching icon path pattern
updates = [
    ("google-ads", "/static/logos/google-ads-small.png"),
    ("predis", "/static/logos/predis-small.png"),
]

for pattern, new_icon in updates:
    tool = db.query(PortalTool).filter(PortalTool.icon.like(f"%{pattern}%")).first()
    if tool:
        old_icon = tool.icon
        tool.icon = new_icon
        print(f"Updated {tool.name}: {old_icon} -> {new_icon}")
    else:
        print(f"No tool found with icon matching: {pattern}")

db.commit()
db.close()
print("Done!")

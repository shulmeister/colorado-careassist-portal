"""Update Google Ads, Predis.ai, and QuickBooks to use smaller logos"""
from portal_database import db_manager
from portal_models import PortalTool

db = db_manager.get_session()

# First list all tools to see exact names
print("Available tools:")
tools = db.query(PortalTool).all()
for t in tools:
    if any(x in t.name.lower() for x in ['ads', 'predis', 'quickbooks', 'intuit']):
        print(f"  - '{t.name}' -> {t.icon}")

updates = [
    ("Google", "Ads", "/static/logos/google-ads-small.png"),
    ("Predis.ai", None, "/static/logos/predis-small.png"),
    ("Intuit", "QuickBooks", "/static/logos/quickbooks-online-small.png"),
]

for name, subtitle, new_icon in updates:
    if subtitle:
        tool = db.query(PortalTool).filter(PortalTool.name == name, PortalTool.subtitle == subtitle).first()
    else:
        tool = db.query(PortalTool).filter(PortalTool.name == name).first()
    if tool:
        old_icon = tool.icon
        tool.icon = new_icon
        print(f"Updated {name} {subtitle or ''}: {old_icon} -> {new_icon}")
    else:
        print(f"Tool not found: {name} {subtitle or ''}")

db.commit()
db.close()
print("Done!")

"""
Utility script to add/update the Activity Tracker tile in the portal.
"""
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
from portal_database import db_manager
from portal_models import PortalTool

if load_dotenv:
    load_dotenv()

db = db_manager.get_session()

try:
    tool = db.query(PortalTool).filter(PortalTool.name == "Activity Tracker").first()

    if tool:
        tool.url = "/activity-tracker"
        tool.icon = "📋"
        tool.description = "Summary, visits, uploads, and logs"
        tool.category = "Field Ops"
        tool.is_active = True
        print("✅ Updated existing Activity Tracker tile.")
    else:
        tool = PortalTool(
            name="Activity Tracker",
            url="/activity-tracker",
            icon="📋",
            description="Summary, visits, uploads, and logs",
            category="Field Ops",
            display_order=4,
            is_active=True,
        )
        db.add(tool)
        print("✅ Added Activity Tracker tile.")

    db.commit()

    tools = (
        db.query(PortalTool)
        .filter(PortalTool.is_active == True)
        .order_by(PortalTool.display_order, PortalTool.name)
        .all()
    )
    print(f"\n📊 Total active tools: {len(tools)}")
    for portal_tool in tools:
        print(f" - {portal_tool.icon or '🔗'} {portal_tool.name} ({portal_tool.url})")

except Exception as exc:
    print(f"❌ Error updating Activity Tracker tile: {exc}")
    import traceback

    traceback.print_exc()
    db.rollback()
finally:
    db.close()



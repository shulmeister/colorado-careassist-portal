"""Utility script to add or update the Client Satisfaction dashboard tile."""
import os
from dotenv import load_dotenv
from portal_database import db_manager
from portal_models import PortalTool

load_dotenv()

db = db_manager.get_session()

CLIENT_SAT_NAME = "Client Satisfaction"
CLIENT_SAT_URL = os.getenv(
    "CLIENT_SATISFACTION_URL",
    "https://client-satisfaction-15d412babc2f.herokuapp.com/",
)

try:
    tool = db.query(PortalTool).filter(PortalTool.name == CLIENT_SAT_NAME).first()

    if tool:
        tool.url = CLIENT_SAT_URL
        tool.icon = "❤️"
        tool.description = "Client care satisfaction tracker"
        tool.category = "Operations"
        tool.is_active = True
        print("✅ Updated existing Client Satisfaction tile.")
    else:
        display_order = 8
        existing = db.query(PortalTool).count()
        if existing:
            display_order = existing + 1
        tool = PortalTool(
            name=CLIENT_SAT_NAME,
            url=CLIENT_SAT_URL,
            icon="❤️",
            description="Client care satisfaction tracker",
            category="Operations",
            display_order=display_order,
            is_active=True,
        )
        db.add(tool)
        print("✅ Added Client Satisfaction tile.")

    db.commit()

    tools = (
        db.query(PortalTool)
        .filter(PortalTool.is_active == True)
        .order_by(PortalTool.display_order, PortalTool.name)
        .all()
    )
    print(f"\n📊 Total active tools: {len(tools)}")
    for t in tools:
        print(f" - {t.icon or '🔗'} {t.name} ({t.url})")
except Exception as exc:
    print(f"❌ Error updating client satisfaction tile: {exc}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()

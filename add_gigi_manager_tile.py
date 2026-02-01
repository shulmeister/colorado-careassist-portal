import os
import sys
from sqlalchemy.orm import Session

# Add portal directory to path
sys.path.insert(0, os.path.join(os.getcwd(), 'portal'))

from portal_database import db_manager
from portal_models import PortalTool

def add_gigi_manager_tile():
    with db_manager.get_session() as db:
        # Check if already exists
        existing = db.query(PortalTool).filter(PortalTool.name == "Gigi Manager").first()
        if existing:
            print("Gigi Manager tile already exists.")
            existing.url = "/gigi/dashboard"
            existing.icon = "🧠"
            existing.description = "Management Portal for Gigi AI (Issues, Schedule, Escalations)"
            existing.category = "AI Operations"
            db.commit()
            print("Updated existing Gigi Manager tile.")
            return

        # Add new tool
        tool = PortalTool(
            name="Gigi Manager",
            url="/gigi/dashboard",
            icon="🧠",
            description="Management Portal for Gigi AI (Issues, Schedule, Escalations)",
            category="AI Operations",
            display_order=-1, # Put it at the top
            is_active=True
        )
        db.add(tool)
        db.commit()
        print("Added Gigi Manager tile successfully.")

if __name__ == "__main__":
    add_gigi_manager_tile()

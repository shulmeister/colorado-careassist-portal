"""
Update the Weather tile on the portal to link to PowderPulse ski weather app.
Run with: python update_weather_tile.py [powderpulse_url]
Default URL is /powderpulse (internal route)
"""
import sys
from portal_database import db_manager
from portal_models import PortalTool

def update_weather_tile(powderpulse_url: str = "/powderpulse"):
    db = db_manager.get_session()
    try:
        # Find the weather tile by URL pattern
        tool = db.query(PortalTool).filter(PortalTool.url.like('%#weather%')).first()

        if not tool:
            # Try finding by name
            tool = db.query(PortalTool).filter(PortalTool.name.ilike('%weather%')).first()

        if not tool:
            print("Weather tile not found. Creating new PowderPulse tile...")
            tool = PortalTool(
                name="PowderPulse",
                url=powderpulse_url,
                icon="🎿",
                description="Ski Weather Dashboard",
                category="Personal",
                display_order=100,
                is_active=True
            )
            db.add(tool)
        else:
            print(f"Found weather tile: {tool.name} (ID: {tool.id})")
            print(f"  Current URL: {tool.url}")

            # Update to PowderPulse
            tool.name = "PowderPulse"
            tool.url = powderpulse_url
            tool.icon = "🎿"
            tool.description = "Ski Weather Dashboard"

        db.commit()
        print(f"Updated tile to PowderPulse: {powderpulse_url}")
        return True

    except Exception as e:
        print(f"Error: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "/powderpulse"
    success = update_weather_tile(url)
    sys.exit(0 if success else 1)

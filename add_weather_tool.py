#!/usr/bin/env python3
"""
Add Weather tool to the portal database
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from portal_database import db_manager
from portal_models import PortalTool

def add_weather_tool():
    """Add Weather tool to database"""
    db = db_manager.get_session()
    
    try:
        # Check if Weather tool already exists
        existing = db.query(PortalTool).filter(PortalTool.name == "Weather").first()
        if existing:
            print("Weather tool already exists!")
            return
        
        # Create Weather tool
        weather_tool = PortalTool(
            name="Weather",
            url="#weather",
            icon="🌤️",
            description="Get current weather for your location or any city",
            category="UTILITIES",
            display_order=999,
            is_active=True
        )
        
        db.add(weather_tool)
        db.commit()
        print("✅ Weather tool added successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error adding Weather tool: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_weather_tool()


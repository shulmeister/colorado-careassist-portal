"""
Setup script to initialize the portal database with default tools.
Run this after setting up the database to add initial tools.
"""
import os
from dotenv import load_dotenv
from portal_database import db_manager
from portal_models import PortalTool
from datetime import datetime

load_dotenv()

def setup_default_tools():
    """Add default tools to the portal"""
    db = db_manager.get_session()
    
    try:
        # Check if tools already exist
        existing_tools = db.query(PortalTool).count()
        if existing_tools > 0:
            print(f"Database already has {existing_tools} tools. Skipping setup.")
            return
        
        # Default tools
        default_tools = [
            {
                "name": "Sales Dashboard",
                "url": "https://tracker.coloradocareassist.com",
                "icon": "📊",
                "description": "View sales metrics, visits, and analytics",
                "category": "Analytics",
                "display_order": 1
            },
            {
                "name": "Google Drive",
                "url": "https://drive.google.com",
                "icon": "📁",
                "description": "Access Google Drive files and folders",
                "category": "Productivity",
                "display_order": 2
            },
            {
                "name": "Gmail",
                "url": "https://mail.google.com",
                "icon": "📧",
                "description": "Access Gmail inbox",
                "category": "Communication",
                "display_order": 3
            },
            {
                "name": "Google Calendar",
                "url": "https://calendar.google.com",
                "icon": "📅",
                "description": "View and manage calendar events",
                "category": "Productivity",
                "display_order": 4
            }
        ]
        
        for tool_data in default_tools:
            tool = PortalTool(**tool_data)
            db.add(tool)
        
        db.commit()
        print(f"Successfully added {len(default_tools)} default tools!")
        
        # Print added tools
        for tool_data in default_tools:
            print(f"  - {tool_data['icon']} {tool_data['name']}")
            
    except Exception as e:
        print(f"Error setting up default tools: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Setting up default portal tools...")
    setup_default_tools()
    print("Setup complete!")


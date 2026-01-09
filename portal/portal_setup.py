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
                "url": "/sales",
                "icon": "📊",
                "description": "View sales metrics, visits, and analytics",
                "category": "Analytics",
                "display_order": 1
            },
            {
                "name": "Recruiter Dashboard",
                "url": "/recruiting",
                "icon": "👥",
                "description": "Manage applicants and recruiting pipeline",
                "category": "HR",
                "display_order": 2
            },
            {
                "name": "Wellsky (AK) Payroll Converter",
                "url": "/payroll",
                "icon": "💰",
                "description": "Convert Wellsky payroll data for Alaska",
                "category": "Payroll",
                "display_order": 3
            },
            {
                "name": "GoFormz",
                "url": "https://app.goformz.com",
                "icon": "📋",
                "description": "Digital forms and mobile data collection",
                "category": "Forms",
                "display_order": 4
            },
            {
                "name": "Wellsky",
                "url": "https://www.wellsky.com",
                "icon": "🏥",
                "description": "Home health care management software",
                "category": "Healthcare",
                "display_order": 5
            },
            {
                "name": "Google Drive",
                "url": "https://drive.google.com",
                "icon": "📁",
                "description": "Access Google Drive files and folders",
                "category": "Productivity",
                "display_order": 6
            },
            {
                "name": "Gmail",
                "url": "https://mail.google.com",
                "icon": "📧",
                "description": "Access Gmail inbox",
                "category": "Communication",
                "display_order": 7
            },
            {
                "name": "Google Calendar",
                "url": "https://calendar.google.com",
                "icon": "📅",
                "description": "View and manage calendar events",
                "category": "Productivity",
                "display_order": 8
            },
            {
                "name": "QuickBooks",
                "url": "https://qbo.intuit.com",
                "icon": "💼",
                "description": "Accounting and financial management",
                "category": "Finance",
                "display_order": 9
            },
            {
                "name": "Google Ads",
                "url": "https://ads.google.com",
                "icon": "🎯",
                "description": "Manage Google advertising campaigns",
                "category": "Marketing",
                "display_order": 10
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


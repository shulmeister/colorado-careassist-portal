#!/usr/bin/env python3
"""
Add Google Admin, Google Cloud, Mac Mini (Local), and Hostinger tools to the portal database
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from portal_database import db_manager
from portal_models import PortalTool

def add_cloud_tools():
    """Add cloud management tools to database"""
    db = db_manager.get_session()
    
    try:
        tools_to_add = [
            {
                "name": "Google Admin",
                "url": "https://admin.google.com/ac/home",
                "icon": "⚙️",  # Using emoji for now, can be updated to logo later
                "description": "Manage Google Workspace settings and users",
                "category": "ADMIN",
                "display_order": 1000
            },
            {
                "name": "Google Cloud",
                "url": "https://console.cloud.google.com/welcome",
                "icon": "/static/logos/google-cloud.svg",
                "description": "Google Cloud Platform console",
                "category": "CLOUD",
                "display_order": 1001
            },
            {
                "name": "Mac Mini (Local)",
                "url": "https://dashboard.mac-mini.com/apps",
                "icon": "💜",  # Using emoji for now, can be updated to logo later
                "description": "Mac Mini (Local) application dashboard",
                "category": "CLOUD",
                "display_order": 1002
            },
            {
                "name": "Hostinger",
                "url": "https://hpanel.hostinger.com/",
                "icon": "🌐",  # Using emoji for now, can be updated to logo later
                "description": "Hostinger hosting control panel",
                "category": "CLOUD",
                "display_order": 1003
            }
        ]
        
        added_count = 0
        for tool_data in tools_to_add:
            # Check if tool already exists
            existing = db.query(PortalTool).filter(PortalTool.name == tool_data["name"]).first()
            if existing:
                print(f"⚠️  {tool_data['name']} already exists, skipping...")
                continue
            
            # Create tool
            tool = PortalTool(
                name=tool_data["name"],
                url=tool_data["url"],
                icon=tool_data["icon"],
                description=tool_data["description"],
                category=tool_data["category"],
                display_order=tool_data["display_order"],
                is_active=True
            )
            
            db.add(tool)
            added_count += 1
            print(f"✅ Added {tool_data['name']}")
        
        db.commit()
        print(f"\n🎉 Successfully added {added_count} new tools!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error adding tools: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_cloud_tools()


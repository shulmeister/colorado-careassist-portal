#!/usr/bin/env python3
"""
Update Google Admin, Heroku, and Hostinger tools to use their logos
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from portal_database import db_manager
from portal_models import PortalTool

def update_cloud_tool_logos():
    """Update cloud tools to use their logos"""
    db = db_manager.get_session()
    
    try:
        logo_updates = [
            {
                "name": "Google Admin",
                "icon": "/static/logos/google-admin.png"
            },
            {
                "name": "Heroku",
                "icon": "/static/logos/heroku.png"
            },
            {
                "name": "Hostinger",
                "icon": "/static/logos/hostinger.png"
            }
        ]
        
        updated_count = 0
        for update_data in logo_updates:
            tool = db.query(PortalTool).filter(PortalTool.name == update_data["name"]).first()
            if tool:
                tool.icon = update_data["icon"]
                updated_count += 1
                print(f"✅ Updated {update_data['name']} logo")
            else:
                print(f"⚠️  {update_data['name']} not found, skipping...")
        
        db.commit()
        print(f"\n🎉 Successfully updated {updated_count} tool logos!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error updating logos: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    update_cloud_tool_logos()




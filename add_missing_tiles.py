#!/usr/bin/env python3
"""
Add missing portal tiles: RingCentral, CBI, CAPS, Google Cloud Console, Google Admin
"""
import os
from dotenv import load_dotenv
from portal.portal_database import db_manager
from portal.portal_models import PortalTool

load_dotenv()

def add_missing_tiles():
    """Add 5 missing tiles to the portal"""
    db = db_manager.get_session()

    try:
        new_tools = [
            {
                "name": "RingCentral",
                "url": "https://app.ringcentral.com",
                "icon": "https://app.ringcentral.com/favicon.ico",
                "description": "Business phone and communications",
                "category": "Communication",
                "display_order": 32,
                "is_active": True
            },
            {
                "name": "CBI InstaCheck",
                "url": "https://www.cbirecordscolorado.com/",
                "icon": "https://www.cbirecordscolorado.com/images/CBI_LOGO.png",
                "description": "Colorado Bureau of Investigation background checks",
                "category": "HR",
                "display_order": 33,
                "is_active": True
            },
            {
                "name": "CAPS",
                "url": "https://www.colorado.gov/pacific/cdhs/adult-protective-services",
                "icon": "https://www.colorado.gov/favicon.ico",
                "description": "Colorado Adult Protective Services reporting",
                "category": "Operations",
                "display_order": 34,
                "is_active": True
            },
            {
                "name": "Google Cloud Console",
                "url": "https://console.cloud.google.com",
                "icon": "https://www.gstatic.com/pantheon/images/welcome/supercloud.svg",
                "description": "Google Cloud Platform management",
                "category": "Development",
                "display_order": 35,
                "is_active": True
            },
            {
                "name": "Google Admin",
                "url": "https://admin.google.com",
                "icon": "https://ssl.gstatic.com/ui/v1/icons/mail/rfr/logo_admin_2x.png",
                "description": "Google Workspace administration",
                "category": "Productivity",
                "display_order": 36,
                "is_active": True
            }
        ]

        for tool_data in new_tools:
            # Check if tool already exists
            existing = db.query(PortalTool).filter_by(name=tool_data["name"]).first()
            if existing:
                print(f"⚠️  Tool '{tool_data['name']}' already exists. Skipping.")
                continue

            tool = PortalTool(**tool_data)
            db.add(tool)
            print(f"✅ Added: {tool_data['name']} ({tool_data['category']})")

        db.commit()
        print(f"\n🎉 Successfully added missing portal tiles!")

    except Exception as e:
        print(f"❌ Error adding tiles: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("Adding missing portal tiles...")
    print("="*60)
    add_missing_tiles()
    print("="*60)
    print("Done!")

#!/usr/bin/env python3
"""
Add new portal tiles: Retell AI, DigitalOcean, Cloudflare, EbizCharge, Fax.Plus
"""
import os
from dotenv import load_dotenv
from portal.portal_database import db_manager
from portal.portal_models import PortalTool

load_dotenv()

def add_new_tiles():
    """Add 5 new tiles to the portal"""
    db = db_manager.get_session()

    try:
        new_tools = [
            {
                "name": "Retell AI",
                "url": "https://dashboard.retellai.com/agents",
                "icon": "https://assets-global.website-files.com/6597424b923cc19ee2895fd8/65990a15e28e4e522c858e39_favicon.png",
                "description": "AI voice agents and phone automation",
                "category": "Development",
                "display_order": 27,
                "is_active": True
            },
            {
                "name": "DigitalOcean",
                "url": "https://cloud.digitalocean.com/login",
                "icon": "https://www.digitalocean.com/_next/static/media/favicon.594d6067.ico",
                "description": "Cloud infrastructure and hosting",
                "category": "Development",
                "display_order": 28,
                "is_active": True
            },
            {
                "name": "Cloudflare",
                "url": "https://dash.cloudflare.com/64fdb3764a8fc8ffae0860415a00c1d6/home/domains",
                "icon": "https://dash.cloudflare.com/favicon.ico",
                "description": "DNS, CDN, and security management",
                "category": "Development",
                "display_order": 29,
                "is_active": True
            },
            {
                "name": "EbizCharge",
                "url": "https://qboapp1.ebizcharge.net/",
                "icon": "https://www.cenpos.com/wp-content/uploads/2019/05/EBizCharge-for-QuickBooks-Logo.png",
                "description": "QuickBooks payment processing",
                "category": "Finance",
                "display_order": 30,
                "is_active": True
            },
            {
                "name": "Fax.Plus",
                "url": "https://app.fax.plus/faxes/inbox",
                "icon": "https://app.fax.plus/favicon.ico",
                "description": "Online fax service",
                "category": "Communication",
                "display_order": 31,
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
        print(f"\n🎉 Successfully added new portal tiles!")

    except Exception as e:
        print(f"❌ Error adding tiles: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("Adding new portal tiles...")
    print("="*60)
    add_new_tiles()
    print("="*60)
    print("Done!")

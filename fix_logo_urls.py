#!/usr/bin/env python3
"""
Fix logo URLs with direct working URLs
"""
import os
from dotenv import load_dotenv
from portal.portal_database import db_manager
from portal.portal_models import PortalTool

load_dotenv()

def fix_logo_urls():
    """Update logos with verified working URLs"""
    db = db_manager.get_session()

    try:
        logo_updates = [
            {
                "name": "EbizCharge",
                "icon": "https://www.ebizcharge.com/wp-content/themes/cenpos-child/images/logo.png"
            },
            {
                "name": "Fax.Plus",
                "icon": "https://cdn.prod.website-files.com/5e1c4fb9dd524e37c7025f88/5e1c4fb9dd524e0a66026015_fax-plus-logo.svg"
            },
            {
                "name": "CBI InstaCheck",
                "icon": "https://ucdenver.edu/sites/g/files/lkoglw1426/files/styles/small/public/2023-04/cbi_colorado-department-of-public-safety_logo.png"
            },
            {
                "name": "CAPS",
                "icon": "https://cdpsdocs.state.co.us/img/cocoportal-logo.png"
            }
        ]

        for update in logo_updates:
            tool = db.query(PortalTool).filter_by(name=update["name"]).first()
            if tool:
                old_icon = tool.icon
                tool.icon = update["icon"]
                print(f"✅ Updated {update['name']}")
                print(f"   Old: {old_icon}")
                print(f"   New: {update['icon']}")
            else:
                print(f"⚠️  Tool '{update['name']}' not found")

        db.commit()
        print(f"\n🎉 Successfully updated logo URLs!")

    except Exception as e:
        print(f"❌ Error updating logos: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("Fixing logo URLs...")
    print("="*60)
    fix_logo_urls()
    print("="*60)
    print("Done!")

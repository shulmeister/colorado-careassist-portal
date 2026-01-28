#!/usr/bin/env python3
"""
Fix portal logos - replace paperclip placeholders with real logos
"""
import os
from dotenv import load_dotenv
from portal.portal_database import db_manager
from portal.portal_models import PortalTool

load_dotenv()

def fix_logos():
    """Update logos for tiles that are showing paperclips"""
    db = db_manager.get_session()

    try:
        logo_updates = [
            {
                "name": "EbizCharge",
                "icon": "https://www.ebizcharge.com/wp-content/uploads/2023/02/ebizcharge-logo.svg"
            },
            {
                "name": "Fax.Plus",
                "icon": "https://assets-global.website-files.com/5e1c4fb9dd524e37c7025f88/5e1c4fb9dd524e0a66026015_fax-plus-logo.svg"
            },
            {
                "name": "CBI InstaCheck",
                "icon": "https://coloradoabi.com/wp-content/uploads/2020/08/CBI-Logo.png"
            },
            {
                "name": "CAPS",
                "icon": "https://www.colorado.gov/pacific/sites/default/files/Colorado_logo.png"
            },
            {
                "name": "Google Admin",
                "icon": "https://www.gstatic.com/images/branding/product/2x/admin_2020q4_48dp.png"
            },
            {
                "name": "AI Tools",
                "icon": "https://cdn-icons-png.flaticon.com/512/4712/4712027.png"
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
        print(f"\n🎉 Successfully updated portal logos!")

    except Exception as e:
        print(f"❌ Error updating logos: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("Fixing portal logos...")
    print("="*60)
    fix_logos()
    print("="*60)
    print("Done!")

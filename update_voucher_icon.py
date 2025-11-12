import os
from dotenv import load_dotenv
from portal_database import db_manager
from portal_models import PortalTool

load_dotenv()

db = db_manager.get_session()

try:
    # Find the Voucher List tool
    voucher_tool = db.query(PortalTool).filter(PortalTool.name == "Voucher List").first()
    
    if voucher_tool:
        print(f"Found Voucher List tool (ID: {voucher_tool.id})")
        print(f"Current icon: {voucher_tool.icon}")
        print(f"Current URL: {voucher_tool.url}")
        
        # Update to use the voucher image
        voucher_tool.icon = "/static/icons/voucher-icon.png"
        
        db.commit()
        print(f"\n✅ Updated icon to: {voucher_tool.icon}")
    else:
        print("❌ Voucher List tool not found!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()


"""
Update Voucher List tool URL to point to internal page
"""
import os
from dotenv import load_dotenv
from portal_database import db_manager
from portal_models import PortalTool

load_dotenv()

db = db_manager.get_session()

try:
    # Find the Voucher List tool
    voucher_tool = db.query(PortalTool).filter(
        PortalTool.name == "Voucher List"
    ).first()
    
    if voucher_tool:
        old_url = voucher_tool.url
        voucher_tool.url = "/vouchers"
        voucher_tool.description = "AAA Voucher Reconciliation - View and manage all vouchers"
        
        db.commit()
        
        print(f"✅ Updated Voucher List tool")
        print(f"   Old URL: {old_url}")
        print(f"   New URL: {voucher_tool.url}")
    else:
        print("⚠️  Voucher List tool not found")
        print("   Creating new tool...")
        
        # Create the tool if it doesn't exist
        voucher_tool = PortalTool(
            name="Voucher List",
            url="/vouchers",
            icon="📋",
            description="AAA Voucher Reconciliation - View and manage all vouchers",
            category="Administration",
            display_order=25
        )
        
        db.add(voucher_tool)
        db.commit()
        
        print(f"✅ Created Voucher List tool")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()


#!/usr/bin/env python3
"""
Add Pikes Peak Vouchers tool to the portal database
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from portal_database import db_manager
from portal_models import PortalTool

def add_pikes_peak_vouchers():
    """Add Pikes Peak Vouchers tool to database"""
    db = db_manager.get_session()
    
    try:
        # Check if tool already exists
        existing = db.query(PortalTool).filter(PortalTool.name == "Pikes Peak Vouchers").first()
        if existing:
            print("Pikes Peak Vouchers tool already exists!")
            return
        
        # Create tool
        tool = PortalTool(
            name="Pikes Peak Vouchers",
            url="https://ppacg.oaa-sys.net/public/ActiveYear/Vouchers/Default.aspx",
            icon="🎫",  # Using ticket emoji as placeholder
            description="Access Pikes Peak Area Council of Governments vouchers",
            category="ADMIN",
            display_order=1004,
            is_active=True
        )
        
        db.add(tool)
        db.commit()
        print("✅ Pikes Peak Vouchers tool added successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error adding Pikes Peak Vouchers tool: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_pikes_peak_vouchers()


#!/usr/bin/env python3
"""Add VA RFS Converter tile to portal"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'portal'))

from portal_database import db_manager
from portal_models import PortalTool

def add_va_rfs_tile():
    db = db_manager.get_session()

    try:
        # Check if already exists
        existing = db.query(PortalTool).filter(
            PortalTool.name == 'VA RFS Converter'
        ).first()

        if existing:
            print(f"VA RFS tool already exists with ID {existing.id}")
            print(f"URL: {existing.url}")
            print(f"Active: {existing.is_active}")
            return

        # Add the tile
        va_rfs_tool = PortalTool(
            name='VA RFS Converter',
            url='/va-rfs-converter',
            icon='https://cdn-icons-png.flaticon.com/512/3004/3004458.png',
            description='Convert referral face sheets to VA Form 10-10172 RFS',
            category='Operations',
            display_order=26,
            is_active=True
        )

        db.add(va_rfs_tool)
        db.commit()

        print("✓ VA RFS Converter tile added successfully!")
        print(f"  Name: {va_rfs_tool.name}")
        print(f"  URL: {va_rfs_tool.url}")
        print(f"  Category: {va_rfs_tool.category}")
        print(f"  Display Order: {va_rfs_tool.display_order}")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_va_rfs_tile()

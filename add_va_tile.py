#!/usr/bin/env python3
"""Add VA Plan of Care Generator tile to portal"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'portal'))

from portal_database import db_manager
from portal_models import PortalTool

def add_va_tile():
    db = db_manager.get_session()

    try:
        # Check if already exists
        existing = db.query(PortalTool).filter(
            PortalTool.name == 'VA Plan of Care Generator'
        ).first()

        if existing:
            print(f"VA tool already exists with ID {existing.id}")
            print(f"URL: {existing.url}")
            print(f"Active: {existing.is_active}")
            return

        # Add the tile
        va_tool = PortalTool(
            name='VA Plan of Care Generator',
            url='/va-plan-of-care',
            icon='https://cdn-icons-png.flaticon.com/512/2910/2910791.png',
            description='Convert VA Form 10-7080 to Plan of Care with automatic PDF naming',
            category='Operations',
            display_order=25,
            is_active=True
        )

        db.add(va_tool)
        db.commit()

        print("✓ VA Plan of Care Generator tile added successfully!")
        print(f"  Name: {va_tool.name}")
        print(f"  URL: {va_tool.url}")
        print(f"  Category: {va_tool.category}")
        print(f"  Display Order: {va_tool.display_order}")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_va_tile()

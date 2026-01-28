#!/usr/bin/env python3
"""
Add AI Tools tile to portal
"""
import os
from dotenv import load_dotenv
from portal.portal_database import db_manager
from portal.portal_models import PortalTool

load_dotenv()

def add_ai_tile():
    """Add AI Tools tile to the portal"""
    db = db_manager.get_session()

    try:
        # Check if AI Tools already exists
        existing = db.query(PortalTool).filter_by(name="AI Tools").first()
        if existing:
            print("⚠️  AI Tools tile already exists. Skipping.")
            return

        ai_tool = PortalTool(
            name="AI Tools",
            url="#ai-tools-dropdown",
            icon="https://cdn-icons-png.flaticon.com/512/8637/8637099.png",
            description="ChatGPT, Gemini, Claude, and Grok",
            category="Productivity",
            display_order=37,
            is_active=True
        )

        db.add(ai_tool)
        db.commit()
        print("✅ Added: AI Tools (Productivity)")
        print("🎉 Successfully added AI Tools tile!")

    except Exception as e:
        print(f"❌ Error adding AI Tools tile: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("Adding AI Tools tile...")
    print("="*60)
    add_ai_tile()
    print("="*60)
    print("Done!")

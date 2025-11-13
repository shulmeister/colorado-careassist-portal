#!/usr/bin/env python3
"""
Update SocialPilot to Predis.ai in the portal database
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from portal_database import db_manager
from portal_models import PortalTool

def update_to_predis():
    """Update SocialPilot tool to Predis.ai"""
    db = db_manager.get_session()
    
    try:
        # Find SocialPilot tool
        social_pilot = db.query(PortalTool).filter(PortalTool.name == "SocialPilot").first()
        
        if not social_pilot:
            print("❌ SocialPilot tool not found in database")
            return
        
        print(f"Found tool: {social_pilot.name}")
        print(f"  Current URL: {social_pilot.url}")
        print(f"  Current icon: {social_pilot.icon}")
        
        # Update to Predis.ai
        social_pilot.name = "Predis.ai"
        social_pilot.url = "https://app.predis.ai/app/dashboard"
        social_pilot.icon = "https://www.google.com/s2/favicons?domain=predis.ai&sz=128"
        social_pilot.description = "AI-powered social media content creation and scheduling"
        
        db.commit()
        print("\n✅ Successfully updated to Predis.ai!")
        print(f"  New URL: {social_pilot.url}")
        print(f"  New icon: {social_pilot.icon}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error updating tool: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    update_to_predis()


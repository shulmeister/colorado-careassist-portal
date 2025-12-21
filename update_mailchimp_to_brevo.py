#!/usr/bin/env python3
"""
Update the Mailchimp tile to Brevo in the portal.
"""

import os
import sys

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from portal_database import SessionLocal
from portal_models import PortalTool

def update_mailchimp_to_brevo():
    """Update Mailchimp tile to Brevo."""
    db = SessionLocal()
    
    try:
        # Find the Mailchimp tile
        mailchimp_tool = db.query(PortalTool).filter(
            PortalTool.name.ilike('%mailchimp%')
        ).first()
        
        if not mailchimp_tool:
            print("Mailchimp tile not found. Listing all tools:")
            all_tools = db.query(PortalTool).all()
            for tool in all_tools:
                print(f"  {tool.id}: {tool.name} - {tool.url}")
            return
        
        print(f"Found Mailchimp tile: ID {mailchimp_tool.id}")
        print(f"  Current name: {mailchimp_tool.name}")
        print(f"  Current URL: {mailchimp_tool.url}")
        print(f"  Current icon: {mailchimp_tool.icon}")
        print(f"  Current description: {mailchimp_tool.description}")
        
        # Update to Brevo
        mailchimp_tool.name = "Brevo"
        mailchimp_tool.url = "https://app.brevo.com"
        mailchimp_tool.icon = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ0m1SXGbCH7BNq8pNJ1uGQZ9P3z4v6q3D8Xg&s"  # Brevo logo
        mailchimp_tool.description = "Email marketing and CRM"
        
        db.commit()
        
        print("\n✅ Updated to Brevo:")
        print(f"  New name: {mailchimp_tool.name}")
        print(f"  New URL: {mailchimp_tool.url}")
        print(f"  New icon: {mailchimp_tool.icon}")
        print(f"  New description: {mailchimp_tool.description}")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    update_mailchimp_to_brevo()


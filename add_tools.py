"""
Add all Colorado CareAssist tools to the portal database
"""
import os
from dotenv import load_dotenv
from portal_database import db_manager
from portal_models import PortalTool
from datetime import datetime

load_dotenv()

def add_all_tools():
    """Add all tools to the portal"""
    db = db_manager.get_session()
    
    try:
        # Define all tools
        tools = [
            {
                "name": "Recruitment Dashboard",
                "url": "https://recruit.coloradocareassist.com/",
                "icon": "👥",
                "description": "Caregiver recruitment and management",
                "category": "HR",
                "display_order": 5
            },
            {
                "name": "AK Payroll Converter",
                "url": "http://payroll.coloradocareassist.com/index.html",
                "icon": "💰",
                "description": "Convert payroll data for Adams Keegan",
                "category": "Payroll",
                "display_order": 6
            },
            {
                "name": "RingCentral",
                "url": "https://login.ringcentral.com/",
                "icon": "📞",
                "description": "Phone and communication system",
                "category": "Communication",
                "display_order": 7
            },
            {
                "name": "GoFormz",
                "url": "https://app.goformz.com/forms",
                "icon": "📝",
                "description": "Digital forms and data collection",
                "category": "Productivity",
                "display_order": 8
            },
            {
                "name": "Mailchimp",
                "url": "https://login.mailchimp.com/",
                "icon": "📧",
                "description": "Email marketing and campaigns",
                "category": "Marketing",
                "display_order": 9
            },
            {
                "name": "QuickBooks",
                "url": "https://accounts.intuit.com/app/sign-in",
                "icon": "📊",
                "description": "Accounting and financial management",
                "category": "Finance",
                "display_order": 10
            },
            {
                "name": "Adams Keegan Efficenter",
                "url": "https://www.adamskeegan.com/efficenter/",
                "icon": "🏢",
                "description": "HR and payroll management system",
                "category": "HR",
                "display_order": 11
            },
            {
                "name": "SocialPilot",
                "url": "https://app.socialpilot.co/",
                "icon": "📱",
                "description": "Social media management and scheduling",
                "category": "Marketing",
                "display_order": 12
            },
            {
                "name": "WordPress",
                "url": "https://coloradocareassist.com/wp-admin/index.php",
                "icon": "🌐",
                "description": "Website content management",
                "category": "Marketing",
                "display_order": 13
            },
            {
                "name": "Paradigm Solutions",
                "url": "https://paradigmseniors.us.auth0.com/u/login",
                "icon": "🏥",
                "description": "VA and Medicaid billing platform",
                "category": "Billing",
                "display_order": 14
            },
            {
                "name": "Facebook Ads Manager",
                "url": "https://adsmanager.facebook.com/adsmanager/manage/campaigns",
                "icon": "📢",
                "description": "Manage Facebook advertising campaigns",
                "category": "Marketing",
                "display_order": 15
            },
            {
                "name": "Meta Business Suite",
                "url": "https://business.facebook.com/latest/inbox/all/",
                "icon": "💬",
                "description": "Manage Facebook and Instagram messages",
                "category": "Marketing",
                "display_order": 16
            },
            {
                "name": "Google Ads",
                "url": "https://ads.google.com/aw/campaigns",
                "icon": "🔍",
                "description": "Manage Google advertising campaigns",
                "category": "Marketing",
                "display_order": 17
            },
            {
                "name": "Google Analytics",
                "url": "https://analytics.google.com/analytics/web/#/a317522534p445403783/reports/intelligenthome",
                "icon": "📈",
                "description": "Website analytics and insights",
                "category": "Analytics",
                "display_order": 18
            }
        ]
        
        added_count = 0
        skipped_count = 0
        
        for tool_data in tools:
            # Check if tool already exists (by URL)
            existing = db.query(PortalTool).filter(PortalTool.url == tool_data["url"]).first()
            
            if existing:
                print(f"⏭️  Skipped (already exists): {tool_data['name']}")
                skipped_count += 1
                continue
            
            tool = PortalTool(**tool_data)
            db.add(tool)
            added_count += 1
            print(f"✅ Added: {tool_data['icon']} {tool_data['name']}")
        
        db.commit()
        
        print(f"\n🎉 Successfully added {added_count} new tools!")
        if skipped_count > 0:
            print(f"⏭️  Skipped {skipped_count} tools (already exist)")
        
        # Print all tools
        all_tools = db.query(PortalTool).filter(PortalTool.is_active == True).order_by(PortalTool.display_order, PortalTool.name).all()
        print(f"\n📊 Total active tools: {len(all_tools)}")
        
    except Exception as e:
        print(f"❌ Error adding tools: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Adding all Colorado CareAssist tools to portal...")
    print("=" * 60)
    add_all_tools()
    print("=" * 60)
    print("✅ Complete!")


"""
Setup script to initialize the portal database with default tools.
Run this after setting up the database to add initial tools.
"""
import os
from dotenv import load_dotenv
from portal_database import db_manager
from portal_models import PortalTool
from datetime import datetime

load_dotenv()

def setup_default_tools():
    """Add default tools to the portal"""
    db = db_manager.get_session()
    
    try:
        # Check if tools already exist
        existing_tools = db.query(PortalTool).count()
        if existing_tools > 0:
            print(f"Database already has {existing_tools} tools. Skipping setup.")
            return
        
        # Default tools
        default_tools = [
            {
                "name": "Sales Dashboard",
                "url": "/sales",
                "icon": "https://tracker.coloradocareassist.com/static/favicon.svg",
                "description": "View sales metrics, visits, and analytics",
                "category": "Analytics",
                "display_order": 1
            },
            {
                "name": "Recruiter Dashboard",
                "url": "/recruiting",
                "icon": "👥",
                "description": "Manage applicants and recruiting pipeline",
                "category": "HR",
                "display_order": 2
            },
            {
                "name": "Wellsky (AK) Payroll Converter",
                "url": "/payroll",
                "icon": "💰",
                "description": "Convert Wellsky payroll data for Alaska",
                "category": "Payroll",
                "display_order": 3
            },
            {
                "name": "GoFormz",
                "url": "https://app.goformz.com",
                "icon": "https://app.goformz.com/favicon.ico",
                "description": "Digital forms and mobile data collection",
                "category": "Forms",
                "display_order": 4
            },
            {
                "name": "Wellsky",
                "url": "https://www.wellsky.com",
                "icon": "https://www.wellsky.com/favicon.ico",
                "description": "Home health care management software",
                "category": "Healthcare",
                "display_order": 5
            },
            {
                "name": "Google Drive",
                "url": "https://drive.google.com",
                "icon": "https://ssl.gstatic.com/images/branding/product/1x/drive_2020q4_32dp.png",
                "description": "Access Google Drive files and folders",
                "category": "Productivity",
                "display_order": 6
            },
            {
                "name": "Gmail",
                "url": "https://mail.google.com",
                "icon": "https://ssl.gstatic.com/ui/v1/icons/mail/rfr/gmail.ico",
                "description": "Access Gmail inbox",
                "category": "Communication",
                "display_order": 7
            },
            {
                "name": "Google Calendar",
                "url": "https://calendar.google.com",
                "icon": "https://calendar.google.com/googlecalendar/images/favicons_2020q4/calendar_31.ico",
                "description": "View and manage calendar events",
                "category": "Productivity",
                "display_order": 8
            },
            {
                "name": "QuickBooks",
                "url": "https://qbo.intuit.com",
                "icon": "https://qbo.intuit.com/favicon.ico",
                "description": "Accounting and financial management",
                "category": "Finance",
                "display_order": 9
            },
            {
                "name": "Google Ads",
                "url": "https://ads.google.com",
                "icon": "https://www.gstatic.com/images/branding/product/1x/google_ads_32dp.png",
                "description": "Manage Google advertising campaigns",
                "category": "Marketing",
                "display_order": 10
            },
            {
                "name": "Google Analytics",
                "url": "https://analytics.google.com",
                "icon": "https://www.gstatic.com/analytics-suite/header/suite/v2/ic_analytics.svg",
                "description": "Web analytics and reporting",
                "category": "Analytics",
                "display_order": 11
            },
            {
                "name": "Google Cloud Console",
                "url": "https://console.cloud.google.com",
                "icon": "https://www.gstatic.com/devrel-devsite/prod/vbf66f6c36316c321f03d50e142b426ee316c88952ceb993e4be77e49bf3c73dd/cloud/images/favicons/onecloud/favicon.ico",
                "description": "Google Cloud Platform management",
                "category": "Development",
                "display_order": 12
            },
            {
                "name": "Brevo",
                "url": "https://app.brevo.com",
                "icon": "https://app.brevo.com/favicon.ico",
                "description": "Email marketing and automation",
                "category": "Marketing",
                "display_order": 13
            },
            {
                "name": "Predis.ai",
                "url": "https://app.predis.ai",
                "icon": "https://app.predis.ai/favicon.ico",
                "description": "AI-powered social media content",
                "category": "Marketing",
                "display_order": 14
            },
            {
                "name": "Meta Business Suite",
                "url": "https://business.facebook.com",
                "icon": "https://static.xx.fbcdn.net/rsrc.php/yb/r/hLRJ1GG_y0J.ico",
                "description": "Manage Facebook and Instagram business",
                "category": "Marketing",
                "display_order": 15
            },
            {
                "name": "Facebook Ads Manager",
                "url": "https://www.facebook.com/adsmanager",
                "icon": "https://static.xx.fbcdn.net/rsrc.php/yb/r/hLRJ1GG_y0J.ico",
                "description": "Create and manage Facebook ads",
                "category": "Marketing",
                "display_order": 16
            },
            {
                "name": "Adams Keegan",
                "url": "https://www.adamskeegan.com",
                "icon": "https://www.adamskeegan.com/favicon.ico",
                "description": "HR and payroll services",
                "category": "HR",
                "display_order": 17
            }
        ]
        
        for tool_data in default_tools:
            tool = PortalTool(**tool_data)
            db.add(tool)
        
        db.commit()
        print(f"Successfully added {len(default_tools)} default tools!")
        
        # Print added tools
        for tool_data in default_tools:
            print(f"  - {tool_data['icon']} {tool_data['name']}")
            
    except Exception as e:
        print(f"Error setting up default tools: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Setting up default portal tools...")
    setup_default_tools()
    print("Setup complete!")


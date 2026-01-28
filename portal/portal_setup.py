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
                "url": "/go/recruiting",
                "icon": "https://cdn-icons-png.flaticon.com/512/681/681443.png",
                "description": "Manage applicants and recruiting pipeline",
                "category": "HR",
                "display_order": 2
            },
            {
                "name": "Marketing Dashboard",
                "url": "/marketing",
                "icon": "https://cdn-icons-png.flaticon.com/512/3135/3135706.png",
                "description": "Social media, ads, email, and website analytics",
                "category": "Marketing",
                "display_order": 3
            },
            {
                "name": "Wellsky (AK) Payroll Converter",
                "url": "/payroll",
                "icon": "https://cdn-icons-png.flaticon.com/512/2830/2830284.png",
                "description": "Convert Wellsky payroll data for Alaska",
                "category": "Payroll",
                "display_order": 4
            },
            {
                "name": "GoFormz",
                "url": "https://app.goformz.com",
                "icon": "https://www.goformz.com/wp-content/themes/goformz-theme/assets/images/goformz-logo-blue.svg",
                "description": "Digital forms and mobile data collection",
                "category": "Forms",
                "display_order": 5
            },
            {
                "name": "Wellsky",
                "url": "https://www.wellsky.com",
                "icon": "https://www.wellsky.com/favicon.ico",
                "description": "Home health care management software",
                "category": "Healthcare",
                "display_order": 6
            },
            {
                "name": "Google Drive",
                "url": "https://drive.google.com",
                "icon": "https://ssl.gstatic.com/images/branding/product/1x/drive_2020q4_32dp.png",
                "description": "Access Google Drive files and folders",
                "category": "Productivity",
                "display_order": 7
            },
            {
                "name": "Gmail",
                "url": "https://mail.google.com",
                "icon": "https://ssl.gstatic.com/ui/v1/icons/mail/rfr/gmail.ico",
                "description": "Access Gmail inbox",
                "category": "Communication",
                "display_order": 8
            },
            {
                "name": "Google Calendar",
                "url": "https://calendar.google.com",
                "icon": "https://calendar.google.com/googlecalendar/images/favicons_2020q4/calendar_31.ico",
                "description": "View and manage calendar events",
                "category": "Productivity",
                "display_order": 9
            },
            {
                "name": "QuickBooks",
                "url": "https://qbo.intuit.com",
                "icon": "https://plugin.intuitcdn.net/sbg-web-shell-ui/6.4024.0/shell/harmony/images/favicons/favicon-qbo.ico",
                "description": "Accounting and financial management",
                "category": "Finance",
                "display_order": 10
            },
            {
                "name": "Google Ads",
                "url": "https://ads.google.com",
                "icon": "https://www.gstatic.com/ads-frontend/compass_icons/compass_icon_192.png",
                "description": "Manage Google advertising campaigns",
                "category": "Marketing",
                "display_order": 11
            },
            {
                "name": "Google Analytics",
                "url": "https://analytics.google.com",
                "icon": "https://www.gstatic.com/analytics-suite/header/suite/v2/ic_analytics.svg",
                "description": "Web analytics and reporting",
                "category": "Analytics",
                "display_order": 12
            },
            {
                "name": "Google Cloud Console",
                "url": "https://console.cloud.google.com",
                "icon": "https://www.gstatic.com/pantheon/images/welcome/supercloud.svg",
                "description": "Google Cloud Platform management",
                "category": "Development",
                "display_order": 13
            },
            {
                "name": "Brevo",
                "url": "https://app.brevo.com",
                "icon": "https://app.brevo.com/favicon.ico",
                "description": "Email marketing and automation",
                "category": "Marketing",
                "display_order": 14
            },
            {
                "name": "Predis.ai",
                "url": "https://app.predis.ai",
                "icon": "https://app.predis.ai/assets/logo-Cm63XoNc.png",
                "description": "AI-powered social media content",
                "category": "Marketing",
                "display_order": 15
            },
            {
                "name": "Meta Business Suite",
                "url": "https://business.facebook.com",
                "icon": "https://static.xx.fbcdn.net/rsrc.php/v3/yJ/r/8dK8qmqxzpA.png",
                "description": "Manage Facebook and Instagram business",
                "category": "Marketing",
                "display_order": 16
            },
            {
                "name": "Facebook Ads Manager",
                "url": "https://www.facebook.com/adsmanager",
                "icon": "https://static.xx.fbcdn.net/rsrc.php/v3/yZ/r/OTB6Bkrf2Ah.png",
                "description": "Create and manage Facebook ads",
                "category": "Marketing",
                "display_order": 17
            },
            {
                "name": "Adams Keegan",
                "url": "https://www.adamskeegan.com",
                "icon": "https://www.adamskeegan.com/wp-content/uploads/2022/12/cropped-AK-Favicon-32x32.png",
                "description": "HR and payroll services",
                "category": "HR",
                "display_order": 18
            },
            {
                "name": "HPanel",
                "url": "https://hpanel.hostinger.com",
                "icon": "https://www.hostinger.com/h-assets/images/logo-transparent.svg",
                "description": "Hostinger control panel",
                "category": "Development",
                "display_order": 19
            },
            {
                "name": "Heroku",
                "url": "https://dashboard.heroku.com",
                "icon": "https://www.herokucdn.com/favicons/favicon.ico",
                "description": "Cloud platform dashboard",
                "category": "Development",
                "display_order": 20
            },
            {
                "name": "GitHub",
                "url": "https://github.com/shulmeister",
                "icon": "https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png",
                "description": "Source code repositories",
                "category": "Development",
                "display_order": 21
            },
            {
                "name": "Google Tag Manager",
                "url": "https://tagmanager.google.com",
                "icon": "https://www.gstatic.com/analytics-suite/header/suite/v2/ic_tag_manager.svg",
                "description": "Manage website tracking tags",
                "category": "Marketing",
                "display_order": 22
            },
            {
                "name": "Google Groups",
                "url": "https://groups.google.com",
                "icon": "https://www.gstatic.com/images/branding/product/1x/groups_48dp.png",
                "description": "Manage email groups and forums",
                "category": "Communication",
                "display_order": 23
            },
            {
                "name": "Google Business Profile",
                "url": "https://business.google.com",
                "icon": "https://www.gstatic.com/identity/boq/accountsettingsmobile/account_settings_96x96_db66f976ef3a88f2bb71860d5c34a613.png",
                "description": "Manage Google Business listings",
                "category": "Marketing",
                "display_order": 24
            },
            {
                "name": "VA Plan of Care Generator",
                "url": "/va-plan-of-care",
                "icon": "https://cdn-icons-png.flaticon.com/512/2910/2910791.png",
                "description": "Convert VA Form 10-7080 to Plan of Care with automatic PDF naming",
                "category": "Operations",
                "display_order": 25
            },
            {
                "name": "VA RFS Converter",
                "url": "/va-rfs-converter",
                "icon": "https://cdn-icons-png.flaticon.com/512/3004/3004458.png",
                "description": "Convert referral face sheets to VA Form 10-10172 RFS",
                "category": "Operations",
                "display_order": 26
            },
            {
                "name": "Retell AI",
                "url": "https://dashboard.retellai.com/agents",
                "icon": "https://assets-global.website-files.com/6597424b923cc19ee2895fd8/65990a15e28e4e522c858e39_favicon.png",
                "description": "AI voice agents and phone automation",
                "category": "Development",
                "display_order": 27
            },
            {
                "name": "DigitalOcean",
                "url": "https://cloud.digitalocean.com/login",
                "icon": "https://www.digitalocean.com/_next/static/media/favicon.594d6067.ico",
                "description": "Cloud infrastructure and hosting",
                "category": "Development",
                "display_order": 28
            },
            {
                "name": "Cloudflare",
                "url": "https://dash.cloudflare.com/64fdb3764a8fc8ffae0860415a00c1d6/home/domains",
                "icon": "https://dash.cloudflare.com/favicon.ico",
                "description": "DNS, CDN, and security management",
                "category": "Development",
                "display_order": 29
            },
            {
                "name": "EbizCharge",
                "url": "https://qboapp1.ebizcharge.net/",
                "icon": "https://www.cenpos.com/wp-content/uploads/2019/05/EBizCharge-for-QuickBooks-Logo.png",
                "description": "QuickBooks payment processing",
                "category": "Finance",
                "display_order": 30
            },
            {
                "name": "Fax.Plus",
                "url": "https://app.fax.plus/faxes/inbox",
                "icon": "https://app.fax.plus/favicon.ico",
                "description": "Online fax service",
                "category": "Communication",
                "display_order": 31
            },
            {
                "name": "RingCentral",
                "url": "https://app.ringcentral.com",
                "icon": "https://app.ringcentral.com/favicon.ico",
                "description": "Business phone and communications",
                "category": "Communication",
                "display_order": 32
            },
            {
                "name": "CBI InstaCheck",
                "url": "https://www.cbirecordscolorado.com/",
                "icon": "https://www.cbirecordscolorado.com/images/CBI_LOGO.png",
                "description": "Colorado Bureau of Investigation background checks",
                "category": "HR",
                "display_order": 33
            },
            {
                "name": "CAPS",
                "url": "https://www.colorado.gov/pacific/cdhs/adult-protective-services",
                "icon": "https://www.colorado.gov/favicon.ico",
                "description": "Colorado Adult Protective Services reporting",
                "category": "Operations",
                "display_order": 34
            },
            {
                "name": "Google Admin",
                "url": "https://admin.google.com",
                "icon": "https://ssl.gstatic.com/ui/v1/icons/mail/rfr/logo_admin_2x.png",
                "description": "Google Workspace administration",
                "category": "Productivity",
                "display_order": 35
            },
            {
                "name": "AI Tools",
                "url": "#ai-tools-dropdown",
                "icon": "https://cdn-icons-png.flaticon.com/512/8637/8637099.png",
                "description": "ChatGPT, Gemini, Claude, and Grok",
                "category": "Productivity",
                "display_order": 36
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


from portal_database import db_manager
from portal_models import PortalTool

def get_tool_info(url, current_name):
    u = url.lower()
    
    # Google Tools
    if 'drive.google.com' in u: return 'Google', 'Drive'
    if 'mail.google.com' in u: return 'Google', 'Gmail'
    if 'calendar.google.com' in u: return 'Google', 'Calendar'
    if 'ads.google.com' in u: return 'Google', 'Ads'
    if 'analytics.google.com' in u: return 'Google', 'Analytics'
    if 'console.cloud.google.com' in u: return 'Google', 'Cloud Platform'
    if 'tagmanager.google.com' in u: return 'Google', 'Tag Manager'
    if 'groups.google.com' in u: return 'Google', 'Groups'
    if 'business.google.com' in u: return 'Google', 'Business Profile'
    
    # Meta/Facebook
    if 'business.facebook.com' in u: return 'Meta', 'Business Suite'
    if 'facebook.com/adsmanager' in u: return 'Meta', 'Ads Manager'
    
    # Financial
    if 'intuit' in u or 'quickbooks' in u: return 'Intuit', 'QuickBooks'
    if 'adamskeegan' in u: return 'Adams Keegan', 'HR & Payroll'
    
    # Operations
    if 'wellsky' in u: return 'WellSky', 'Home Health Software'
    if 'goformz' in u: return 'GoFormz', 'Mobile Forms'
    if 'brevo' in u: return 'Brevo', 'CRM & Email'
    if 'hostinger' in u: return 'Hostinger', 'Web Hosting'
    if 'heroku' in u: return 'Salesforce', 'Heroku Cloud'
    if 'github' in u: return 'GitHub', 'Repositories'
    
    # Marketing
    if 'predis' in u: return 'Predis.ai', 'Social AI'
    
    # Widgets
    if '#weather' in u: return 'IBM', 'Weather'
    if '#joke' in u: return 'Joke of the Day', 'Daily Humor'
    
    # Fallback: keep current name, just ensure description isn't "Company"
    return current_name, "Portal Tool"

def main():
    db = db_manager.get_session()
    try:
        tools = db.query(PortalTool).all()
        count = 0
        for tool in tools:
            if tool.url.startswith('/'): continue
            
            new_name, new_desc = get_tool_info(tool.url, tool.name)
            
            # Only update if changed or if description is broken (contains "Company" redundantly)
            if tool.name != new_name or tool.description == f"{new_name} Company":
                print(f"Updating {tool.url}")
                print(f"   Name: {tool.name} -> {new_name}")
                print(f"   Desc: {tool.description} -> {new_desc}")
                
                tool.name = new_name
                tool.description = new_desc
                count += 1
        
        if count > 0:
            db.commit()
            print(f"\n✅ Successfully fixed {count} tiles!")
        else:
            print("\nNo tiles needed fixing.")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()

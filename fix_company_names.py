
from portal_database import db_manager
from portal_models import PortalTool

def get_company_from_url(url):
    u = url.lower()
    if 'google' in u: return 'Google'
    if 'facebook' in u or 'meta' in u: return 'Meta'
    if 'intuit' in u or 'quickbooks' in u: return 'Intuit'
    if 'wellsky' in u: return 'WellSky'
    if 'adamskeegan' in u: return 'Adams Keegan'
    if 'goformz' in u: return 'GoFormz'
    if 'brevo' in u: return 'Brevo'
    if 'predis' in u: return 'Predis.ai'
    if 'hostinger' in u: return 'Hostinger'
    if 'mac-mini' in u: return 'Salesforce'
    if 'weather' in u: return 'IBM'
    if 'joke' in u: return 'Joke of the Day'
    if 'github' in u: return 'GitHub'
    return None

def main():
    db = db_manager.get_session()
    try:
        tools = db.query(PortalTool).all()
        count = 0
        for tool in tools:
            if tool.url.startswith('/'): continue
            
            company = get_company_from_url(tool.url)
            if company:
                # Update Name to Company
                # Update Description to include specific details if needed, or keep generic
                
                # If name isn't already the company name
                if tool.name != company:
                    print(f"Updating {tool.name} -> {company} ({tool.url})")
                    tool.name = company
                    
                    # Ensure description mentions the specific tool/purpose
                    # We'll leave description as is if it looks good, or append tool type?
                    # Previous script set description to "Company Name Company". 
                    # Let's revert description to something useful if we can, or just leave it.
                    # The user said "derive the name of the company... so it just has the company name and logo"
                    
                    count += 1
        
        if count > 0:
            db.commit()
            print(f"Updated {count} tools.")
        else:
            print("No tools needed updating.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()

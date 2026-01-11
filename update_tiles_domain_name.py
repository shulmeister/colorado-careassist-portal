
import re
from urllib.parse import urlparse
from portal_database import db_manager
from portal_models import PortalTool

def get_domain(url):
    try:
        if 'http' in url:
            parsed = urlparse(url)
            return parsed.netloc
        return url
    except:
        return url

def main():
    db = db_manager.get_session()
    try:
        # Get all tools
        tools = db.query(PortalTool).all()
        print(f"Found {len(tools)} tools to process...")
        
        updated_count = 0
        
        for tool in tools:
            # Skip internal paths
            if tool.url.startswith('/'):
                continue
                
            current_name = tool.name # This is currently the Company Name (e.g. Google)
            url = tool.url
            domain = get_domain(url)
            
            # Check if we need to swap
            # If current name is NOT the domain, and looks like a Company Name
            if current_name != domain:
                print(f"Updating: {current_name} ({url})")
                print(f"   Name: {current_name} -> {domain}")
                
                # Set description to the Company Name
                new_description = f"{current_name} Company"
                if tool.description and "Company" in tool.description:
                     # Keep existing description if it already has "Company" but ensure it starts with Company Name if brief
                     # Actually, simpler to just set it to "Company Name" as requested "just says company underneath"
                     pass 
                
                print(f"   Description: {tool.description} -> {new_description}")
                
                tool.name = domain
                tool.description = new_description
                
                updated_count += 1
            else:
                print(f"   Skipping {current_name} (already matches domain)")
        
        if updated_count > 0:
            db.commit()
            print(f"\n✅ Successfully updated {updated_count} tiles to show Domain as Name!")
        else:
            print("\nNo changes needed.")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()

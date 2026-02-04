"""
Enrich company tiles with official company names derived from their domains using Gemini.
"""
import os
import re
import time
from urllib.parse import urlparse
from dotenv import load_dotenv
import google.generativeai as genai
from portal_database import db_manager
from portal_models import PortalTool

load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ GEMINI_API_KEY not found in environment variables.")
    # Attempt to read from config if not in env
    try:
        import subprocess
        result = subprocess.run(["mac-mini", "config:get", "GEMINI_API_KEY", "-a", "careassist-unified"], 
                                capture_output=True, text=True)
        if result.returncode == 0:
            api_key = result.stdout.strip()
            print("✅ Retrieved GEMINI_API_KEY from Mac Mini (Local) config")
    except Exception as e:
        print(f"⚠️ Could not retrieve API key from Mac Mini (Local): {e}")

if not api_key:
    print("❌ Cannot proceed without GEMINI_API_KEY")
    exit(1)

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash-exp')

def get_company_name(domain_or_url):
    """Ask Gemini for the company name based on domain/URL"""
    try:
        # Extract domain if full URL
        if 'http' in domain_or_url:
            parsed = urlparse(domain_or_url)
            domain = parsed.netloc
        else:
            domain = domain_or_url
            
        prompt = f"""
        What is the official company name for the website '{domain}'? 
        Return ONLY the company name, nothing else. 
        For example, if the domain is 'google.com', return 'Google'.
        If the domain is 'paychex.com', return 'QuickBooks' or 'Paychex' appropriately.
        If it's a government site like 'va.gov', return 'Veterans Affairs'.
        """
        
        response = model.generate_content(prompt)
        company_name = response.text.strip()
        
        # Cleanup response if it contains extra text
        company_name = re.sub(r'[\""]', '', company_name)
        if '\n' in company_name:
            company_name = company_name.split('\n')[0]
            
        return company_name
    except Exception as e:
        print(f"⚠️ Error asking Gemini for {domain_or_url}: {e}")
        return None

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
                
            original_name = tool.name
            url = tool.url
            
            print(f"Processing: {original_name} ({url})")
            
            # Ask Gemini for the company name
            company_name = get_company_name(url)
            
            if company_name and company_name != original_name:
                print(f"   ✨ Gemini suggests: '{company_name}' (was '{original_name}')")
                
                # Update name
                tool.name = company_name
                
                # Update description to include "Company" if appropriate and missing
                if tool.description:
                    if "company" not in tool.description.lower() and "portal" not in tool.description.lower():
                        tool.description = f"{tool.description} - {company_name} Company"
                else:
                    tool.description = f"Official {company_name} Company Portal"
                
                updated_count += 1
                
                # Rate limiting to be nice to API
                time.sleep(10)
            else:
                print("   Skipping update (name match or failed)")
        
        if updated_count > 0:
            db.commit()
            print(f"\n✅ Successfully enriched {updated_count} tiles!")
        else:
            print("\nNo changes needed.")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()

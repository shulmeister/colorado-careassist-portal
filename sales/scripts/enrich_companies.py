import os
import sys
import re
import time
from urllib.parse import urlparse
from dotenv import load_dotenv
import google.generativeai as genai

# Add parent directory to path to import database and models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db_manager
from models import ReferralSource

load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ GEMINI_API_KEY not found in environment variables.")
    # Attempt to read from config if not in env
    try:
        import subprocess
        result = subprocess.run(["heroku", "config:get", "GEMINI_API_KEY", "-a", "careassist-unified"], 
                                capture_output=True, text=True)
        if result.returncode == 0:
            api_key = result.stdout.strip()
            print("✅ Retrieved GEMINI_API_KEY from Heroku config")
    except Exception as e:
        print(f"⚠️ Could not retrieve API key from Heroku: {e}")

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
        If the domain is generic (e.g. gmail.com), return None.
        """
        
        response = model.generate_content(prompt)
        company_name = response.text.strip()
        
        # Cleanup response if it contains extra text
        company_name = re.sub(r'["\"]', '', company_name)
        if '\n' in company_name:
            company_name = company_name.split('\n')[0]
            
        if company_name.lower() == 'none':
            return None
            
        return company_name
    except Exception as e:
        print(f"⚠️ Error asking Gemini for {domain_or_url}: {e}")
        return None

def main():
    db = db_manager.get_session()
    try:
        # Get all referral sources (companies)
        companies = db.query(ReferralSource).all()
        print(f"Found {len(companies)} companies to process...")
        
        updated_count = 0
        
        for company in companies:
            original_name = company.name
            website = company.website
            email = company.email
            
            # Determine domain to check
            target_domain = None
            if website:
                target_domain = website
            elif email and '@' in email:
                domain = email.split('@')[1]
                if domain not in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com', 'icloud.com', 'me.com']:
                    target_domain = domain
            
            # Skip if name already looks like a proper name (no dots, spaces present) and doesn't look like a domain
            # But the user specifically complained about domain names being used as names.
            # So if the name looks like a domain, we DEFINITELY want to fix it.
            is_domain_name = '.' in original_name and ' ' not in original_name
            
            if not target_domain and is_domain_name:
                target_domain = original_name
            
            if target_domain:
                print(f"Processing: {original_name} (Domain: {target_domain})")
                
                # Ask Gemini for the company name
                new_name = get_company_name(target_domain)
                
                if new_name and new_name != original_name:
                    print(f"   ✨ Gemini suggests: '{new_name}' (was '{original_name}')")
                    
                    company.name = new_name
                    # Also set organization field if empty, as that's often used for display
                    if not company.organization:
                        company.organization = new_name
                        
                    updated_count += 1
                    
                    # Rate limiting (strict 10 RPM limit = 1 request every 6 seconds minimum)
                    time.sleep(10) # 10 seconds to be very safe
                else:
                    print("   Skipping update (name match or failed)")
            else:
                print(f"   Skipping {original_name} (no domain found)")
        
        if updated_count > 0:
            db.commit()
            print(f"\n✅ Successfully enriched {updated_count} companies!")
        else:
            print("\nNo changes needed.")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
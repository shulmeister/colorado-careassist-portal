#!/usr/bin/env python3
"""Check Gmail API setup and configuration"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

def check_gmail_setup():
    """Check if Gmail API is properly configured"""
    print("=" * 60)
    print("GMAIL API SETUP CHECK")
    print("=" * 60)
    print()
    
    # Check environment variables
    service_account_email = os.getenv('GMAIL_SERVICE_ACCOUNT_EMAIL')
    service_account_key = os.getenv('GMAIL_SERVICE_ACCOUNT_KEY')
    user_email = os.getenv('GMAIL_USER_EMAIL', 'maryssa@coloradocareassist.com')
    
    print("1. Environment Variables:")
    print("-" * 60)
    
    if service_account_email:
        print(f"   ✅ GMAIL_SERVICE_ACCOUNT_EMAIL: {service_account_email}")
    else:
        print("   ❌ GMAIL_SERVICE_ACCOUNT_EMAIL: NOT SET")
    
    if service_account_key:
        try:
            key_data = json.loads(service_account_key)
            print(f"   ✅ GMAIL_SERVICE_ACCOUNT_KEY: Valid JSON")
            print(f"      Project ID: {key_data.get('project_id', 'N/A')}")
            print(f"      Client Email: {key_data.get('client_email', 'N/A')}")
        except json.JSONDecodeError:
            print("   ❌ GMAIL_SERVICE_ACCOUNT_KEY: Invalid JSON format")
        except Exception as e:
            print(f"   ⚠️  GMAIL_SERVICE_ACCOUNT_KEY: Error parsing - {e}")
    else:
        print("   ❌ GMAIL_SERVICE_ACCOUNT_KEY: NOT SET")
    
    print(f"   ✅ GMAIL_USER_EMAIL: {user_email}")
    print()
    
    # Try to initialize Gmail service
    print("2. Gmail Service Initialization:")
    print("-" * 60)
    try:
        from gmail_service import GmailService
        gmail_service = GmailService()
        
        if gmail_service.enabled:
            print("   ✅ Gmail service enabled")
            print(f"   ✅ User email: {gmail_service.user_email}")
            
            # Test connection
            print()
            print("3. Connection Test:")
            print("-" * 60)
            result = gmail_service.test_connection()
            
            if result.get('success'):
                print("   ✅ Connection successful!")
                print(f"      Email: {result.get('email')}")
                print(f"      Total Messages: {result.get('messages_total', 'N/A')}")
            else:
                print("   ❌ Connection failed:")
                print(f"      Error: {result.get('error', 'Unknown error')}")
                print()
                print("   Common issues:")
                print("   - Domain-wide delegation not configured in Google Admin Console")
                print("   - Gmail API not enabled in Google Cloud Console")
                print("   - Service account doesn't have correct permissions")
        else:
            print("   ❌ Gmail service disabled - check environment variables")
            
    except ImportError as e:
        print(f"   ❌ Failed to import gmail_service: {e}")
    except Exception as e:
        print(f"   ❌ Error initializing Gmail service: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("SETUP CHECK COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    check_gmail_setup()

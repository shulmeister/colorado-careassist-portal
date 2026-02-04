import os
import sys
import requests
import json
from datetime import datetime

# Point to app root
APP_ROOT = "/Users/shulmeister/mac-mini-apps/careassist-unified"
sys.path.insert(0, APP_ROOT)

def test_rc_auth():
    print("🔍 DIAGNOSING RINGCENTRAL AUTH\n")
    
    # Load env vars
    from dotenv import load_dotenv
    load_dotenv(os.path.join(APP_ROOT, ".gigi-env"))
    
    client_id = os.getenv("RINGCENTRAL_CLIENT_ID", "VbxfL4RkN8ncFItIqSP5k7")
    client_secret = os.getenv("RINGCENTRAL_CLIENT_SECRET")
    jwt_token = os.getenv("RINGCENTRAL_JWT_TOKEN")
    server = os.getenv("RINGCENTRAL_SERVER_URL", "https://platform.ringcentral.com")
    
    print(f"Client ID: {client_id}")
    print(f"Client Secret: {'SET' if client_secret else 'MISSING'}")
    print(f"JWT Token: {'SET' if jwt_token else 'MISSING'}")
    print(f"Server: {server}")
    
    if not all([client_id, client_secret, jwt_token]):
        print("\n❌ CRITICAL: Missing credentials in .gigi-env")
        return

    url = f"{server}/restapi/oauth/token"
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token
    }
    
    print(f"\nAttempting authentication to {url}...")
    try:
        response = requests.post(
            url,
            data=data,
            auth=(client_id, client_secret),
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("✅ SUCCESS: Authenticated successfully!")
            token_data = response.json()
            access_token = token_data.get("access_token")
            
            # Now test an actual API call
            headers = {"Authorization": f"Bearer {access_token}"}
            me_res = requests.get(f"{server}/restapi/v1.0/account/~/extension/~/", headers=headers)
            if me_res.status_code == 200:
                me_data = me_res.json()
                print(f"✅ API TEST: Verified extension {me_data.get('extensionNumber')} ({me_data.get('contact', {}).get('firstName')})")
            else:
                print(f"❌ API TEST FAILED: {me_res.status_code} - {me_res.text}")
        else:
            print(f"❌ AUTH FAILED: {response.text}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    test_rc_auth()

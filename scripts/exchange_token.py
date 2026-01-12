import requests
import os
import sys

def exchange_token(short_token):
    # Credentials from previous configuration
    app_id = os.getenv('FACEBOOK_APP_ID', '1826010391596353')
    app_secret = os.getenv('FACEBOOK_APP_SECRET', '1746c8402ef815d0a2449ba254e9b2a7')
    
    url = "https://graph.facebook.com/v18.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token
    }
    
    print(f"Exchanging token for App ID: {app_id}...")
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if "access_token" in data:
        print("\nSUCCESS: Long-lived token generated.")
        print(f"Token: {data['access_token']}")
        print(f"Expires in: {data.get('expires_in', 'Unknown')}")
        return data['access_token']
    else:
        print("\nERROR: Could not exchange token.")
        print(data)
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python exchange_token.py <short_token>")
        sys.exit(1)
    
    short_token = sys.argv[1]
    exchange_token(short_token)

"""
RingCentral Webhook Setup Script
Run this to register the webhook with RingCentral
"""
import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()

# RingCentral credentials
CLIENT_ID = "cqaJllTcFyndtgsussicsd"
CLIENT_SECRET = "1PwhkkpeFYEcaHcZmQ3cCialR3hQ79DnDfVSpRPOUqYT"
SERVER = "https://platform.ringcentral.com"
JWT_TOKEN = "eyJraWQiOiI4NzYyZjU5OGQwNTk0NGRiODZiZjVjYTk3ODA0NzYwOCIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0.eyJhdWQiOiJodHRwczovL3BsYXRmb3JtLnJpbmdjZW50cmFsLmNvbS9yZXN0YXBpL29hdXRoL3Rva2VuIiwic3ViIjoiMjYyNzQwMDA5IiwiaXNzIjoiaHR0cHM6Ly9wbGF0Zm9ybS5yaW5nY2VudHJhbC5jb20iLCJleHAiOjM5MTAyNDA5NjUsImlhdCI6MTc2Mjc1NzMxOCwianRpIjoiZ3Jsd0pPWGFTM2EwalpibThvTmtZdyJ9.WA9DUSlb_4SlCo9UHNjscHKrVDoJTF4iW3D7Rre9E2qg5UQ_hWfCgysiZJMXlL8-vUuJ2XDNivvpfbxriESKIEPAEEY85MolJZS9KG3g90ga-3pJtHq7SC87mcacXtDWqzmbBS_iDOjmNMHiynWFR9Wgi30DMbz9rQ1U__Bl88qVRTvZfY17ovu3dZDhh-FmLUWRnKOc4LQUvRChQCO-21LdSquZPvEAe7qHEsh-blS8Cvh98wvX-9vaiurDR-kC9Tp007x4lTI74MwQ5rJif7tL7Hslqaoag0WoNEIP9VPrp4x-Q7AzKIzBNbrGr9kIPthIebmeOBDMIIrw6pg_lg"

# Your webhook URL
WEBHOOK_URL = "https://careassist-tracker-0fcf2cecdb22.herokuapp.com/webhooks/ringcentral"

def get_access_token():
    """Get access token using JWT"""
    print("Getting access token...")
    
    url = f"{SERVER}/restapi/oauth/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": JWT_TOKEN
    }
    
    response = requests.post(url, headers=headers, data=data, auth=(CLIENT_ID, CLIENT_SECRET))
    
    if response.status_code == 200:
        token_data = response.json()
        print("✅ Access token obtained")
        return token_data["access_token"]
    else:
        print(f"❌ Error getting token: {response.status_code}")
        print(response.text)
        return None

def list_existing_subscriptions(access_token):
    """List existing webhook subscriptions"""
    print("\nChecking existing subscriptions...")
    
    url = f"{SERVER}/restapi/v1.0/subscription"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        subscriptions = response.json()
        if subscriptions.get("records"):
            print(f"Found {len(subscriptions['records'])} existing subscription(s):")
            for sub in subscriptions["records"]:
                print(f"  - ID: {sub['id']}")
                print(f"    Status: {sub['status']}")
                print(f"    Delivery Mode: {sub['deliveryMode']['address']}")
                print(f"    Events: {sub.get('eventFilters', [])}")
        else:
            print("No existing subscriptions found")
        return subscriptions.get("records", [])
    else:
        print(f"❌ Error listing subscriptions: {response.status_code}")
        print(response.text)
        return []

def delete_subscription(access_token, subscription_id):
    """Delete an existing subscription"""
    print(f"\nDeleting subscription {subscription_id}...")
    
    url = f"{SERVER}/restapi/v1.0/subscription/{subscription_id}"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    response = requests.delete(url, headers=headers)
    
    if response.status_code == 204:
        print("✅ Subscription deleted")
        return True
    else:
        print(f"❌ Error deleting subscription: {response.status_code}")
        print(response.text)
        return False

def create_webhook_subscription(access_token):
    """Create a new webhook subscription for call events"""
    print("\nCreating new webhook subscription...")
    
    url = f"{SERVER}/restapi/v1.0/subscription"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Webhook configuration
    data = {
        "eventFilters": [
            "/restapi/v1.0/account/~/extension/~/telephony/sessions",  # Call sessions
        ],
        "deliveryMode": {
            "transportType": "WebHook",
            "address": WEBHOOK_URL,
            "verificationToken": "your-verification-token-123"  # Optional security token
        },
        "expiresIn": 630720000  # 20 years (max allowed)
    }
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        subscription = response.json()
        print("✅ Webhook subscription created successfully!")
        print(f"   Subscription ID: {subscription['id']}")
        print(f"   Status: {subscription['status']}")
        print(f"   Webhook URL: {subscription['deliveryMode']['address']}")
        print(f"   Events: {subscription['eventFilters']}")
        return subscription
    else:
        print(f"❌ Error creating subscription: {response.status_code}")
        print(response.text)
        return None

def verify_webhook():
    """Test if webhook endpoint is accessible"""
    print(f"\nVerifying webhook URL is accessible...")
    print(f"Webhook URL: {WEBHOOK_URL}")
    
    try:
        # Try to reach the webhook URL (will return error but confirms it's reachable)
        response = requests.get(WEBHOOK_URL.replace("/webhooks/ringcentral", "/health"))
        print(f"✅ Webhook endpoint is reachable (status: {response.status_code})")
    except Exception as e:
        print(f"⚠️  Warning: Could not verify webhook endpoint: {e}")
        print("   This is OK if your server is running")

def main():
    print("=" * 60)
    print("RingCentral Webhook Setup")
    print("=" * 60)
    
    # Step 1: Verify webhook endpoint
    verify_webhook()
    
    # Step 2: Get access token
    access_token = get_access_token()
    if not access_token:
        print("\n❌ Failed to get access token. Cannot continue.")
        return
    
    # Step 3: List existing subscriptions
    existing_subs = list_existing_subscriptions(access_token)
    
    # Step 4: Ask to delete existing subscriptions
    if existing_subs:
        print("\n⚠️  Found existing subscriptions.")
        choice = input("Delete all existing subscriptions? (y/n): ")
        if choice.lower() == 'y':
            for sub in existing_subs:
                delete_subscription(access_token, sub['id'])
    
    # Step 5: Create new subscription
    print("\n" + "=" * 60)
    choice = input("Create new webhook subscription? (y/n): ")
    if choice.lower() == 'y':
        subscription = create_webhook_subscription(access_token)
        
        if subscription:
            print("\n" + "=" * 60)
            print("🎉 SUCCESS! Webhook is now active!")
            print("=" * 60)
            print(f"\nYour RingCentral calls will now be logged automatically at:")
            print(f"  {WEBHOOK_URL}")
            print(f"\nSubscription ID (save this): {subscription['id']}")
            print("\nTest it by making a call from your RingCentral phone.")
            print("The call should appear in your CRM activity feed!")
    else:
        print("\nSetup cancelled. Run this script again when ready.")

if __name__ == "__main__":
    main()


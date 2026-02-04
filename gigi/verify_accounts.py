import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Creds to test
ADS_TOKEN = "1//04dq0ao88aTNkCgYIARAAGAQSNwF-L9IrnxWXj3ESunPD1EvFxWdsdIM7M41voTuGst3ur471S295KF9b-paTGfdOWfYriVLanWo"
ADS_CLIENT_ID = "888987085559-k0mbk3qah1h6dmjbce1kaebsolgsu2au.apps.googleusercontent.com"
ADS_CLIENT_SECRET = "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"

def verify():
    print("Testing ADS token scope...")
    try:
        creds = Credentials(
            token=None,
            refresh_token=ADS_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=ADS_CLIENT_ID,
            client_secret=ADS_CLIENT_SECRET
        )
        creds.refresh(Request())
        service = build('gmail', 'v1', credentials=creds)
        profile = service.users().getProfile(userId='me').execute()
        print(f"✅ SUCCESS: {profile.get('emailAddress')}")
    except Exception as e:
        print(f"❌ FAILED: {e}")

if __name__ == "__main__":
    verify()
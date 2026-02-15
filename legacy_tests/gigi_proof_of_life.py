import os
import sys
import asyncio
from datetime import datetime

# CRITICAL: Correctly point to the actual app directory on the Mac Mini
APP_ROOT = "/Users/shulmeister/mac-mini-apps/careassist-unified"
sys.path.insert(0, APP_ROOT)

async def prove_gigi_skills():
    print("🚀 GIGI SKILLS PROOF-OF-LIFE CHECK\n")
    
    # 1. PROVE GMAIL & CALENDAR
    print("--- 📬 Testing Gmail & 🗓️ Calendar ---")
    try:
        from gigi.google_service import google_service
        emails = google_service.search_emails(max_results=1)
        if emails:
            print(f"✅ GMAIL IS LIVE. Latest email from: {emails[0]['from']}")
        
        events = google_service.get_calendar_events(days=3, max_results=1)
        if events:
            print(f"✅ CALENDAR IS LIVE. Next event: '{events[0]['summary']}' at {events[0]['start']}")
    except Exception as e:
        print(f"❌ Google Error: {e}")

    # 2. PROVE WELLSKY
    print("\n--- 🏥 Testing WellSky API ---")
    try:
        from services.wellsky_service import WellSkyService
        ws = WellSkyService()
        clients = ws.get_clients(limit=1)
        if clients:
            print(f"✅ WELLSKY IS LIVE. Found real client: {clients[0].full_name}")
    except Exception as e:
        print(f"❌ WellSky Error: {e}")

    # 3. PROVE WEATHER
    print("\n--- ❄️ Testing Weather API ---")
    try:
        # Search for the right function in gigi/main.py
        from gigi.main import get_weather
        weather = await get_weather("Eldora")
        print(f"✅ WEATHER IS LIVE. Eldora status: {weather.get('condition', 'Unknown')}, {weather.get('temp_f')}°F")
    except Exception as e:
        print(f"❌ Weather Error: {e}")

    # 4. PROVE RINGCENTRAL
    print("\n--- 💬 Testing RingCentral ---")
    try:
        from services.ringcentral_messaging_service import ringcentral_messaging_service
        # Need to set credentials from environment if they aren't loaded
        token = ringcentral_messaging_service._get_access_token()
        if token:
            print(f"✅ RINGCENTRAL IS LIVE. Successfully obtained access token.")
            teams = ringcentral_messaging_service.list_teams()
            if teams:
                print(f"   Found {len(teams)} active teams (e.g., '{teams[0].get('name')}')")
    except Exception as e:
        print(f"❌ RingCentral Error: {e}")

if __name__ == "__main__":
    # Load env vars first
    from dotenv import load_dotenv
    load_dotenv(os.path.join(APP_ROOT, ".gigi-env"))
    
    asyncio.run(prove_gigi_skills())

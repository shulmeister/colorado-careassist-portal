import os
import sys
import asyncio
from datetime import datetime

# Point to app root
APP_ROOT = "/Users/shulmeister/heroku-apps/careassist-unified"
sys.path.insert(0, APP_ROOT)

async def prove_chief_of_staff_skills():
    print("🚀 GIGI ELITE CHIEF-OF-STAFF PROOF-OF-LIFE\n")
    
    # Load env vars for Telegram/APIs
    from dotenv import load_dotenv
    load_dotenv(os.path.join(APP_ROOT, ".gigi-env"))

    try:
        from gigi.chief_of_staff_tools import cos_tools, pending_sessions
        
        # 1. TEST CONCERT SEARCH
        print("--- 🎸 Testing Concert Search ---")
        concerts = await cos_tools.search_concerts("Red Rocks")
        if concerts.get("success"):
            print(f"✅ SUCCESS: Found {len(concerts['matches'])} upcoming shows Gigi can see.")
            for m in concerts['matches']:
                print(f"   - {m['artist']} @ {m['venue']} ({m['date']})")
        
        # 2. TEST TICKET PURCHASE & 2FA TRIGGER
        print("\n--- 🎟️ Testing Ticket 2FA Trigger ---")
        # This will actually send a text to your Telegram!
        buy_res = await cos_tools.buy_tickets_request("Dogs In A Pile", "Ogden Theatre", 2)
        if buy_res.get("success"):
            session_id = buy_res["session_id"]
            print(f"✅ SUCCESS: 2FA Request sent to Jason's phone.")
            print(f"   Message: '{buy_res['message']}'")
            print(f"   Session ID: {session_id}")
            
            # 3. TEST CONFIRMATION LOGIC
            print("\n--- 🔐 Testing Confirmation Handshake ---")
            conf_res = await cos_tools.confirm_purchase(session_id)
            if conf_res.get("success"):
                print(f"✅ SUCCESS: Verified session confirmation flow.")
                print(f"   Gigi Response: '{conf_res['message']}'")

        # 4. TEST RESTAURANT 2FA TRIGGER
        print("\n--- 🍽️ Testing Restaurant 2FA Trigger ---")
        book_res = await cos_tools.book_table_request("Flagstaff House", 2, "Friday", "7:30 PM")
        if book_res.get("success"):
            print(f"✅ SUCCESS: Restaurant 2FA Request sent to Jason's phone.")
            print(f"   Message: '{book_res['message']}'")

    except Exception as e:
        print(f"❌ Skill Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(prove_chief_of_staff_skills())

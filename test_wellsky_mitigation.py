
import os
import sys
import logging
import json
from datetime import date, datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_wellsky")

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from services.wellsky_service import WellSkyService, ClientStatus
except ImportError:
    # Fallback for running from root
    sys.path.append(os.getcwd())
    from services.wellsky_service import WellSkyService, ClientStatus

def test_mitigation():
    print("\n=== WELLSKY API MITIGATION TEST ===\n")
    
    ws = WellSkyService() 
    
    print(f"Configuration Status:")
    print(f"  - Configured: {ws.is_configured}")
    print(f"  - Environment: {ws.environment}")
    print(f"  - API Mode: {ws.api_mode}")
    print(f"  - Base URL: {ws.base_url}")
    
    if not ws.is_configured:
        print("\n❌ Error: WellSky service is not configured (credentials missing).")
        return

    # 1. Test Auth
    print("\n1. Testing Authentication...")
    token = ws._get_access_token()
    if token:
        print(f"  ✅ Auth Success! Token: {token[:10]}...")
    else:
        print("  ❌ Auth Failed!")
        return

    # 2. Test Read (Client Search)
    print("\n2. Testing Read (Client Search)...")
    clients = ws.get_clients(limit=5)
    print(f"  Found {len(clients)} clients.")
    
    active_clients = [c for c in clients if c.status == ClientStatus.ACTIVE]
    print(f"  Active clients in batch: {len(active_clients)}")
    
    if not active_clients:
        # Try to find specific active client
        print("  No active clients in first 5, searching for any active...")
        active_clients = ws.get_clients(status=ClientStatus.ACTIVE, limit=5)
        print(f"  Found {len(active_clients)} active clients.")

    target_client = active_clients[0] if active_clients else None
    
    if target_client:
        print(f"  Target Client: {target_client.full_name} (ID: {target_client.id})")
        
        # 3. Test Note Sync (Encounter Strategy)
        print(f"\n3. Testing Note Sync for {target_client.full_name}...")
        print("  Attempting to add note using 'Encounter Search + TaskLog' strategy...")
        
        # We use a unique string to identify this test
        note_content = f"Test Note from Gigi Mitigation Check {datetime.now().strftime('%H:%M:%S')}" 
        
        # Capture logs to see what happens internally
        # (In a real script we rely on the output of add_note_to_client)
        success, message = ws.add_note_to_client(
            client_id=target_client.id,
            note=note_content,
            note_type="test",
            source="gigi_cli"
        )
        
        print(f"  Result: {success}")
        print(f"  Message: {message}")
        
        if "Encounter" in message:
            print("  ✅ SUCCESS: Note attached to valid Encounter/Shift!")
        elif "locally" in message:
            print("  ⚠️ PARTIAL: Note saved locally only (No recent encounter found or sync failed).")
            print("     This is expected behavior if the client hasn\'t had a shift in the last 14 days.")
        else:
            print(f"  ❓ Unknown outcome: {message}")

    else:
        print("  ❌ Could not find an active client to test notes with.")

    # 4. Test Admin Task (Local Fallback)
    print("\n4. Testing Admin Task (Local Fallback)...")
    success = ws.create_admin_task(
        title="Test Admin Task",
        description="This should log locally only",
        related_client_id=target_client.id if target_client else None
    )
    if success:
        print("  ✅ Admin Task creation returned True (as expected for local fallback).")
    else:
        print("  ❌ Admin Task creation failed.")

    # 5. Verify Local Log
    print("\n5. Verifying Local Database Log...")
    try:
        import sqlite3
        conn = sqlite3.connect('portal.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gigi_documentation_log ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            print(f"  ✅ Found entry in DB: ID={row[0]}, Type={row[1]}, ID={row[2]}")
            print(f"     Note: {row[3][:50]}...")
            print(f"     Synced: {row[6]}")
        else:
            print("  ❌ No entries found in local DB!")
    except Exception as e:
        print(f"  ❌ Error checking DB: {e}")

if __name__ == "__main__":
    test_mitigation()

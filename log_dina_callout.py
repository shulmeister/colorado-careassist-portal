import os
import sys
from datetime import date
sys.path.insert(0, os.path.abspath(".")) # Add current dir to path

from services.wellsky_service import WellSkyService

def main():
    """
    This script performs the final step of logging the Dina Ortega call-out event
    to WellSky by creating a Task and a Care Alert.
    """
    ws = WellSkyService()
    if not ws.is_configured:
        print("❌ WellSky credentials are not configured. Aborting.")
        return

    DINA_ID = "6641837"
    DINA_NAME = "Dina Ortega"
    
    # 1. Find the client "Judy" to get her ID
    print("Finding client 'Judy Tuetken'...")
    clients = ws.search_patients(last_name="Tuetken", limit=1)
    if not clients:
        print("❌ Could not find client 'Judy Tuetken'. Cannot create linked tasks.")
        return
    judy = clients[0]
    print(f"✅ Found Client: {judy.full_name} (ID: {judy.id})")

    # 2. Create the "Shift Needs Filling" Task
    print("\nCreating WellSky Task for shift coverage...")
    task_success = ws.create_admin_task(
        title=f"Shift Needs Filling: {judy.full_name}",
        description=(
            f"{DINA_NAME} called out via text for her shift on Jan 30. "
            f"Gigi has marked the shift as OPEN and notified potential replacements. "
            f"The conversation has been assigned to Israt in BeeTexting for morning follow-up."
        ),
        related_client_id=judy.id,
        related_caregiver_id=DINA_ID,
        priority="high",
        due_date=date(2026, 1, 30)
    )
    if task_success:
        print("✅ SUCCESS: Task for filling the shift has been created in WellSky.")
    else:
        print("❌ FAILED: Could not create the shift-filling task.")

    # 3. Create the "Care Alert" Task
    print("\nCreating WellSky Care Alert...")
    alert_success = ws.create_admin_task(
        title=f"CARE ALERT: Caregiver Call-Out",
        description=(
            f"Caregiver Dina Ortega ({DINA_ID}) reported a call-out via text message at 7:52 PM "
            f"for her upcoming shift with Judy Tuetken ({judy.id})."
        ),
        related_client_id=judy.id,
        related_caregiver_id=DINA_ID,
        priority="high" # Using 'high' as a proxy for an urgent alert
    )
    if alert_success:
        print("✅ SUCCESS: Care Alert has been created in WellSky.")
    else:
        print("❌ FAILED: Could not create the Care Alert.")

if __name__ == "__main__":
    main()

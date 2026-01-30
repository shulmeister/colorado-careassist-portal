"""
Manual Call-Out Logger for WellSky

This script allows an administrator to manually log a call-out event,
creating the necessary Task and Care Alert in WellSky. This is useful
when automated systems fail or when a call-out is received via a channel
Gigi does not monitor.

Usage:
  python3 scripts/log_manual_callout.py "Dina Ortega" "Judy Tuetken" "2026-01-30" "Text at 7:52pm"
"""

import os
import sys
from datetime import date, datetime
sys.path.insert(0, os.path.abspath("."))

from services.wellsky_service import WellSkyService

def log_callout(caregiver_name: str, client_name: str, shift_date_str: str, reason: str):
    ws = WellSkyService()
    if not ws.is_configured:
        print("❌ WellSky credentials must be configured as environment variables.")
        return

    # --- 1. Find Caregiver ---
    print(f"Finding caregiver '{caregiver_name}'...")
    cg_first = caregiver_name.split()[0]
    caregivers = ws.search_practitioners(first_name=cg_first, limit=5)
    if not caregivers:
        print(f"❌ Could not find caregiver '{caregiver_name}'.")
        return
    caregiver = caregivers[0]
    print(f"✅ Found: {caregiver.full_name} (ID: {caregiver.id})")

    # --- 2. Find Client ---
    print(f"Finding client '{client_name}'...")
    cl_last = client_name.split()[-1]
    clients = ws.search_patients(last_name=cl_last, limit=5)
    if not clients:
        print(f"❌ Could not find client '{client_name}'.")
        return
    client = clients[0]
    print(f"✅ Found: {client.full_name} (ID: {client.id})")

    # --- 3. Create Task for Coverage ---
    print("\nCreating WellSky Task for shift coverage...")
    task_success = ws.create_admin_task(
        title=f"Shift Needs Filling: {client.full_name}",
        description=(
            f"{caregiver.full_name} called out for the shift on {shift_date_str}.\n"
            f"Reason: {reason}\n\n"
            f"Please find replacement coverage and confirm with the client."
        ),
        related_client_id=client.id,
        related_caregiver_id=caregiver.id,
        priority="high",
        due_date=datetime.strptime(shift_date_str, "%Y-%m-%d").date()
    )
    if task_success:
        print("✅ SUCCESS: Task for filling the shift created.")
    else:
        print("❌ FAILED to create the shift-filling task.")

    # --- 4. Create Care Alert ---
    print("\nCreating WellSky Care Alert...")
    alert_success = ws.create_admin_task(
        title=f"CARE ALERT: Caregiver Call-Out",
        description=(
            f"Caregiver {caregiver.full_name} ({caregiver.id}) reported a call-out.\n"
            f"Client: {client.full_name} ({client.id})\n"
            f"Shift Date: {shift_date_str}\n"
            f"Reason: {reason}"
        ),
        related_client_id=client.id,
        related_caregiver_id=caregiver.id,
        priority="high"
    )
    if alert_success:
        print("✅ SUCCESS: Care Alert created.")
    else:
        print("❌ FAILED to create the Care Alert.")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(1)
    
    # Set credentials from env for script execution
    required_vars = ["WELLSKY_CLIENT_ID", "WELLSKY_CLIENT_SECRET", "WELLSKY_AGENCY_ID"]
    if not all(v in os.environ for v in required_vars):
        print("Error: Missing required WellSky environment variables.")
        sys.exit(1)
        
    log_callout(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])

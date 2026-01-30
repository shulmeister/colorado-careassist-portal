"""
Resilient WellSky Job Executor

This script will not fail on temporary API timeouts. It retries a given
job with exponential backoff until it succeeds or a max timeout is reached.
"""

import os
import sys
import time
from datetime import date, datetime
from typing import Callable
sys.path.insert(0, os.path.abspath("."))

from services.wellsky_service import WellSkyService

# --- Configuration ---
MAX_ATTEMPTS = 3
INITIAL_DELAY_SECONDS = 15 # Increased delay to be respectful
MAX_DELAY_SECONDS = 30

def execute_with_retries(job: Callable[[], bool], job_name: str):
    """
    Runs a given job function, retrying on failure.

    Args:
        job: A zero-argument function that returns True on success.
        job_name: A human-readable name for the job for logging.
    """
    for i in range(MAX_ATTEMPTS):
        attempt = i + 1
        print(f"\n--- Attempt {attempt}/{MAX_ATTEMPTS}: {job_name} ---")
        try:
            success = job()
            if success:
                print(f"✅ SUCCESS: Job '{job_name}' completed on attempt {attempt}.")
                return True
            else:
                print(f"⚠️ Job '{job_name}' failed. The API responded but reported a failure.")
        except Exception as e:
            print(f"🔥 An exception occurred: {e}")

        if attempt < MAX_ATTEMPTS:
            delay = min(INITIAL_DELAY_SECONDS * (2 ** i), MAX_DELAY_SECONDS)
            print(f"Retrying in {delay} seconds...")
            time.sleep(delay)
    
    print(f"\n❌ FAILED: Job '{job_name}' did not succeed after {MAX_ATTEMPTS} attempts.")
    return False

def run_dina_callout_jobs():
    """
    Defines and runs the specific jobs for logging the Dina Ortega call-out.
    """
    ws = WellSkyService()
    if not ws.is_configured:
        print("❌ WellSky credentials are not configured. Aborting.")
        return

    # --- Job 1: Create the 'Shift Needs Filling' Task ---
    def create_shift_task():
        clients = ws.search_patients(last_name="Tuetken", limit=1)
        if not clients:
            print("  - Could not find client 'Judy Tuetken'.")
            return False
        judy = clients[0]

        return ws.create_admin_task(
            title=f"Shift Needs Filling: {judy.full_name}",
            description=(
                f"Dina Ortega called out via text for her shift on Jan 30. "
                f"Reason: Text at 7:52pm. Shift marked OPEN. Thread assigned to Israt."
            ),
            related_client_id=judy.id,
            related_caregiver_id="6641837", # Dina's ID
            priority="high",
            due_date=date(2026, 1, 30)
        )

    # --- Job 2: Create the 'Care Alert' Task ---
    def create_alert_task():
        clients = ws.search_patients(last_name="Tuetken", limit=1)
        if not clients:
            print("  - Could not find client 'Judy Tuetken'.")
            return False
        judy = clients[0]

        return ws.create_admin_task(
            title=f"CARE ALERT: Caregiver Call-Out",
            description=(
                f"Caregiver Dina Ortega (ID: 6641837) reported a call-out via text at 7:52 PM "
                f"for her upcoming shift with Judy Tuetken (ID: {judy.id})."
            ),
            related_client_id=judy.id,
            related_caregiver_id="6641837",
            priority="high"
        )
    
    # --- Execute Jobs ---
    task_ok = execute_with_retries(create_shift_task, "Create Shift Coverage Task")
    if task_ok:
        execute_with_retries(create_alert_task, "Create Care Alert")

if __name__ == "__main__":
    required_vars = ["WELLSKY_CLIENT_ID", "WELLSKY_CLIENT_SECRET", "WELLSKY_AGENCY_ID"]
    if not all(v in os.environ for v in required_vars):
        print("Error: Missing required WellSky environment variables.")
        sys.exit(1)
    
    run_dina_callout_jobs()

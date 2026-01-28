import os
import requests
import time
import sys

RETELL_API_KEY = os.getenv('RETELL_API_KEY')
BATCH_ID = 'test_batch_193c3907fa4e'
BASE_URL = 'https://api.retellai.com'

headers = {
    'Authorization': f'Bearer {RETELL_API_KEY}',
    'Content-Type': 'application/json'
}

def get_batch_test(batch_job_id):
    """Get batch test status."""
    response = requests.get(
        f'{BASE_URL}/get-batch-test/{batch_job_id}',
        headers=headers,
        timeout=30
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f'Error getting batch test: {response.status_code}')
        return None

def list_test_runs(batch_job_id):
    """List individual test runs from a batch."""
    response = requests.get(
        f'{BASE_URL}/list-test-runs/{batch_job_id}',
        headers=headers,
        timeout=30
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f'Error listing test runs: {response.status_code}')
        return []

def main():
    print(f"Polling Batch Test: {BATCH_ID}")
    
    while True:
        status = get_batch_test(BATCH_ID)
        if status:
            batch_status = status.get('status')
            print(f"Status: {batch_status}")
            
            if batch_status not in ('in_progress', 'pending', 'created'):
                break
        else:
            print("Failed to get status.")
            break
        
        time.sleep(10)

    print("\nTest Run Completed.")
    print("=" * 60)
    
    runs = list_test_runs(BATCH_ID)
    passed = 0
    failed = 0
    
    for run in runs:
        status = run.get('status', 'unknown')
        name = run.get('test_case_definition_snapshot', {}).get('name', 'Unknown Test')
        explanation = run.get('result_explanation', '')
        
        if status == 'pass':
            passed += 1
            print(f"✓ PASS: {name}")
        elif status == 'fail':
            failed += 1
            print(f"✗ FAIL: {name}")
            if explanation:
                print(f"        Reason: {explanation}")
        else:
            print(f"? {status.upper()}: {name}")

    print("-" * 60)
    print(f"Total: {len(runs)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    if len(runs) > 0:
        print(f"Success Rate: {(passed/len(runs))*100:.1f}%")

if __name__ == "__main__":
    main()

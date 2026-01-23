#!/usr/bin/env python3
"""Run Retell AI simulation tests via API."""

import os
import json
import requests
import time
import sys

RETELL_API_KEY = os.getenv('RETELL_API_KEY')
CONVERSATION_FLOW_ID = 'conversation_flow_7226ef696925'
BASE_URL = 'https://api.retellai.com'

headers = {
    'Authorization': f'Bearer {RETELL_API_KEY}',
    'Content-Type': 'application/json'
}

def list_test_definitions():
    """List all test case definitions for this conversation flow."""
    response = requests.get(
        f'{BASE_URL}/list-test-case-definitions',
        headers=headers,
        params={
            'type': 'conversation-flow',
            'conversation_flow_id': CONVERSATION_FLOW_ID
        },
        timeout=30
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f'Error listing tests: {response.status_code}')
        print(response.text[:500])
        return []

def create_batch_test(test_definition_ids):
    """Create and run a batch test."""
    response = requests.post(
        f'{BASE_URL}/create-batch-test',
        headers=headers,
        json={
            'test_case_definition_ids': test_definition_ids,
            'conversation_flow_id': CONVERSATION_FLOW_ID
        },
        timeout=30
    )
    if response.status_code in (200, 201):
        return response.json()
    else:
        print(f'Error creating batch test: {response.status_code}')
        print(response.text[:500])
        return None

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
    if not RETELL_API_KEY:
        print("ERROR: RETELL_API_KEY not set")
        sys.exit(1)

    print("=" * 60)
    print("RETELL AI SIMULATION TESTS")
    print("=" * 60)
    print(f"Conversation Flow: {CONVERSATION_FLOW_ID}")
    print()

    # Step 1: List existing test definitions
    print("Fetching test definitions...")
    tests = list_test_definitions()
    
    if not tests:
        print("No test definitions found. Creating default tests...")
        # We could create test definitions here
        return

    print(f"Found {len(tests)} test definition(s):")
    for t in tests:
        print(f"  - {t.get('name', 'Unnamed')}: {t.get('test_case_definition_id')}")
    print()

    # Step 2: Run batch test with all test definitions
    test_ids = [t['test_case_definition_id'] for t in tests]
    print(f"Running batch test with {len(test_ids)} test(s)...")
    
    batch = create_batch_test(test_ids)
    if not batch:
        print("Failed to create batch test")
        return

    batch_id = batch.get('test_case_batch_job_id')
    print(f"Batch test started: {batch_id}")
    print()

    # Step 3: Poll for completion
    print("Waiting for results", end="", flush=True)
    max_wait = 120  # 2 minutes max
    waited = 0
    
    while waited < max_wait:
        time.sleep(5)
        waited += 5
        print(".", end="", flush=True)
        
        status = get_batch_test(batch_id)
        if status:
            batch_status = status.get('status')
            if batch_status not in ('in_progress', 'pending'):
                print()
                break
    
    print()
    print("=" * 60)
    print("TEST RESULTS")
    print("=" * 60)

    # Step 4: Get individual test results
    runs = list_test_runs(batch_id)
    
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
                print(f"        Reason: {explanation[:200]}")
        else:
            print(f"? {status.upper()}: {name}")
    
    print()
    print(f"Results: {passed} passed, {failed} failed out of {len(runs)} tests")
    
    # Calculate pass rate
    if runs:
        pass_rate = (passed / len(runs)) * 100
        print(f"Pass rate: {pass_rate:.0f}%")

if __name__ == "__main__":
    main()

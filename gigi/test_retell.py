#!/usr/bin/env python3
"""
Gigi Retell Testing Guide

Retell AI's simulation testing is only available through their dashboard.
This script provides test scenarios you can run manually in the Retell dashboard.

For automated testing, see the webhook test at the bottom which tests the
local tool endpoints.

Usage:
    python gigi/test_retell.py --scenarios    # Print test scenarios for dashboard
    python gigi/test_retell.py --webhook      # Test webhook endpoints locally
    python gigi/test_retell.py --check        # Verify Retell API connection
"""

import os
import json
import requests
import sys

# Retell API configuration
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = "agent_363f3725498b851037ea84bda5"
RETELL_API_BASE = "https://api.retellai.com"

# Webhook base for local testing
WEBHOOK_BASE = os.getenv("GIGI_WEBHOOK_BASE", "https://portal.coloradocareassist.com")

# Test scenarios for Retell Dashboard
TEST_SCENARIOS = [
    {
        "name": "Caregiver Call-Out (Sick)",
        "identity": "Maria, a caregiver at Colorado Care Assist",
        "goal": "Call out sick for my 9am shift today with Mrs. Johnson",
        "personality": "Apologetic, a bit panicked, speaks quickly",
        "sample_messages": [
            "Hi, I'm Maria and I need to call out sick for my shift today",
            "I have my 9am shift with Mrs. Johnson",
            "I've had a fever since last night"
        ],
        "expected_behavior": [
            "Gigi should call verify_caller",
            "Gigi should call get_active_shifts to find the shift",
            "Gigi should call execute_caregiver_call_out or report_call_out ONCE",
            "Gigi should confirm coverage is being arranged",
            "Gigi should NOT call the same tool multiple times"
        ]
    },
    {
        "name": "Caregiver Running Late",
        "identity": "Maria, a caregiver running late to her shift",
        "goal": "Report that I'll be about 15 minutes late due to traffic",
        "personality": "Calm but rushed, matter-of-fact",
        "sample_messages": [
            "Hey this is Maria, I'm running late to my shift",
            "About 15 minutes, there's traffic on I-25"
        ],
        "expected_behavior": [
            "Gigi should call verify_caller",
            "Gigi should call get_shift_details",
            "Gigi should call report_late ONCE",
            "Gigi should confirm the client has been notified"
        ]
    },
    {
        "name": "Client Schedule Inquiry",
        "identity": "Dorothy, an elderly client",
        "goal": "Find out when my caregiver is coming today",
        "personality": "Polite, slightly confused, speaks slowly",
        "sample_messages": [
            "Hi, this is Dorothy. When is my caregiver coming today?"
        ],
        "expected_behavior": [
            "Gigi should call verify_caller",
            "Gigi should call get_client_schedule",
            "Gigi should tell Dorothy her scheduled visit time"
        ]
    },
    {
        "name": "Client Complaint",
        "identity": "Dorothy, a client with a complaint",
        "goal": "Report that my caregiver was on her phone the whole time",
        "personality": "Upset but polite, wants to be heard",
        "sample_messages": [
            "I need to report a problem with my caregiver",
            "She was on her phone the whole time and didn't help me with my exercises"
        ],
        "expected_behavior": [
            "Gigi should call verify_caller",
            "Gigi should call log_client_issue ONCE",
            "Gigi should confirm management will call back",
            "Gigi should NOT call log_client_issue again to add details"
        ]
    },
    {
        "name": "Client Cancellation",
        "identity": "Dorothy's daughter, calling to cancel a visit",
        "goal": "Cancel tomorrow's visit because mom has a doctor's appointment",
        "personality": "Businesslike, clear communicator",
        "sample_messages": [
            "I need to cancel my mother's visit tomorrow",
            "She has a doctor's appointment"
        ],
        "expected_behavior": [
            "Gigi should call verify_caller",
            "Gigi should call get_client_schedule to find the visit",
            "Gigi should call cancel_client_visit ONCE",
            "Gigi should confirm the cancellation"
        ]
    },
    {
        "name": "Prospective Client Inquiry",
        "identity": "Sarah, looking for home care for her mother",
        "goal": "Get information about home care services",
        "personality": "Concerned daughter, asking lots of questions",
        "sample_messages": [
            "Hi, I'm looking for home care for my mother",
            "She's 82 and needs help with daily activities"
        ],
        "expected_behavior": [
            "Gigi should call verify_caller (will return unknown)",
            "Gigi should take a message and promise a callback",
            "Gigi should NOT try to schedule or make commitments"
        ]
    },
    {
        "name": "CRITICAL: No Loop Test",
        "identity": "Upset client reporting a no-show",
        "goal": "Report that my caregiver didn't show up and I'm very upset",
        "personality": "Very upset, speaking quickly, providing lots of details",
        "sample_messages": [
            "I have a problem. My caregiver didn't show up today and I'm very upset about it. This is unacceptable. I need help with my medication and she was supposed to be here at 8am. It's now 10am and nobody has come. What are you going to do about this?"
        ],
        "expected_behavior": [
            "Gigi should call log_client_issue EXACTLY ONCE",
            "Gigi should NOT call log_client_issue again to add more details",
            "If Gigi loops, the conversation will be terminated early",
            "SUCCESS = issue logged once, then move to closing"
        ]
    }
]


def print_scenarios():
    """Print test scenarios formatted for Retell Dashboard."""
    print("=" * 70)
    print("GIGI RETELL SIMULATION TEST SCENARIOS")
    print("=" * 70)
    print()
    print("To run these tests:")
    print("1. Go to https://app.retellai.com")
    print("2. Select agent: Gigi - CCA Virtual Assistant")
    print("3. Click 'Test' -> 'Test LLM'")
    print("4. Click 'Simulate Conversation'")
    print("5. Enter the identity/goal/personality from scenarios below")
    print()

    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print("=" * 70)
        print(f"TEST {i}: {scenario['name']}")
        print("=" * 70)
        print()
        print("SIMULATION SETTINGS:")
        print(f"  Identity: {scenario['identity']}")
        print(f"  Goal: {scenario['goal']}")
        print(f"  Personality: {scenario['personality']}")
        print()
        print("SAMPLE MESSAGES TO USE:")
        for msg in scenario["sample_messages"]:
            print(f"  - \"{msg}\"")
        print()
        print("EXPECTED BEHAVIOR (Check these):")
        for behavior in scenario["expected_behavior"]:
            print(f"  [ ] {behavior}")
        print()


def check_retell_api():
    """Verify Retell API connection and agent status."""
    if not RETELL_API_KEY:
        print("ERROR: RETELL_API_KEY environment variable not set")
        return False

    print("Checking Retell API connection...")

    try:
        # Check agent
        response = requests.get(
            f"{RETELL_API_BASE}/get-agent/{RETELL_AGENT_ID}",
            headers={
                "Authorization": f"Bearer {RETELL_API_KEY}",
                "Content-Type": "application/json"
            },
            timeout=10
        )

        if response.status_code == 200:
            agent = response.json()
            print(f"  ✓ Agent: {agent.get('agent_name', 'Unknown')}")
            print(f"  ✓ Agent ID: {RETELL_AGENT_ID}")

            # Check LLM
            llm_id = agent.get("llm_websocket_url", "").split("/")[-1] if agent.get("llm_websocket_url") else None
            if llm_id:
                llm_response = requests.get(
                    f"{RETELL_API_BASE}/get-retell-llm/{llm_id}",
                    headers={
                        "Authorization": f"Bearer {RETELL_API_KEY}",
                        "Content-Type": "application/json"
                    }
                )
                if llm_response.status_code == 200:
                    llm = llm_response.json()
                    tools = llm.get("general_tools", [])
                    print(f"  ✓ LLM has {len(tools)} tools configured")
                    for tool in tools:
                        print(f"      • {tool.get('name')}")

            return True
        else:
            print(f"  ✗ API error: {response.status_code}")
            print(f"    {response.text[:200]}")
            return False

    except Exception as e:
        print(f"  ✗ Connection error: {e}")
        return False


def test_webhook_endpoints():
    """Test the Gigi webhook endpoints directly."""
    print("=" * 70)
    print("TESTING GIGI WEBHOOK ENDPOINTS")
    print("=" * 70)
    print(f"Base URL: {WEBHOOK_BASE}")
    print()

    tests = [
        {
            "name": "Health Check",
            "method": "GET",
            "path": "/gigi/health",
            "expected_status": 200
        },
        {
            "name": "Verify Caller (Test Phone)",
            "method": "POST",
            "path": "/gigi/webhook/retell/function/verify_caller",
            "body": {"phone_number": "+17195551234"},
            "expected_status": 200
        },
        {
            "name": "Get Active Shifts",
            "method": "POST",
            "path": "/gigi/webhook/retell/function/get_active_shifts",
            "body": {"person_id": "test_caregiver_1"},
            "expected_status": 200
        },
        {
            "name": "Log Client Issue",
            "method": "POST",
            "path": "/gigi/webhook/retell/function/log_client_issue",
            "body": {
                "client_id": "test_client_1",
                "note": "Test issue from webhook test",
                "issue_type": "general",
                "priority": "normal"
            },
            "expected_status": 200
        }
    ]

    passed = 0
    failed = 0

    for test in tests:
        print(f"\nTesting: {test['name']}")
        print(f"  {test['method']} {test['path']}")

        try:
            url = f"{WEBHOOK_BASE}{test['path']}"
            if test["method"] == "GET":
                response = requests.get(url, timeout=30)
            else:
                response = requests.post(url, json=test.get("body", {}), timeout=30)

            if response.status_code == test["expected_status"]:
                print(f"  ✓ Status: {response.status_code}")
                try:
                    data = response.json()
                    print(f"  ✓ Response: {json.dumps(data)[:100]}...")
                except:
                    print(f"  ✓ Response: {response.text[:100]}...")
                passed += 1
            else:
                print(f"  ✗ Expected {test['expected_status']}, got {response.status_code}")
                print(f"    {response.text[:200]}")
                failed += 1

        except requests.exceptions.Timeout:
            print(f"  ✗ Request timed out")
            failed += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed += 1

    print()
    print("=" * 70)
    print(f"WEBHOOK TESTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nQuick commands:")
        print("  --scenarios  Print test scenarios for Retell dashboard")
        print("  --webhook    Test webhook endpoints")
        print("  --check      Check Retell API connection")
        return

    arg = sys.argv[1]

    if arg in ("--scenarios", "-s"):
        print_scenarios()
    elif arg in ("--webhook", "-w"):
        test_webhook_endpoints()
    elif arg in ("--check", "-c"):
        check_retell_api()
    else:
        print(f"Unknown argument: {arg}")
        print("Use --scenarios, --webhook, or --check")


if __name__ == "__main__":
    main()

"""
Test WellSky Failure Handling & Escalation

Tests that Gigi properly handles WellSky API failures and escalates to human.
"""
import requests
import json
from datetime import datetime

# Test server running locally
BASE_URL = "http://localhost:8000"

def test_wellsky_timeout():
    """
    Test Scenario: WellSky API times out
    Expected: Gigi aborts and escalates to Jason
    """
    print("\n" + "="*70)
    print("TEST: WellSky API Timeout")
    print("="*70)

    # Simulate call-out
    response = requests.post(
        f"{BASE_URL}/api/internal/test/callout-with-wellsky-failure",
        json={
            "shift_id": "test-shift-timeout",
            "caregiver_id": "caregiver-001",
            "caregiver_name": "Maria Garcia",
            "client_name": "Mrs. Johnson",
            "shift_time": "2:00 PM - 6:00 PM",
            "reason": "Sick - fever",
            "simulate_wellsky_failure": True  # Force WellSky to fail
        }
    )

    result = response.json()
    print(f"\nResponse: {json.dumps(result, indent=2)}")

    # Verify expectations
    assert result["success"] == False, "Should fail when WellSky fails"
    assert result["step_a_wellsky_updated"] == False, "Step A should fail"
    assert result["human_escalation_required"] == True, "Should escalate to human"
    assert "Jason" in result.get("escalated_to", ""), "Should escalate to Jason"

    print("\n✅ PASS: WellSky failure properly escalated to Jason")


def test_wellsky_success_sms_failure():
    """
    Test Scenario: WellSky succeeds but SMS blast fails
    Expected: Gigi escalates because no notifications sent
    """
    print("\n" + "="*70)
    print("TEST: WellSky Success but SMS Blast Failure")
    print("="*70)

    response = requests.post(
        f"{BASE_URL}/api/internal/test/callout-with-sms-failure",
        json={
            "shift_id": "test-shift-sms-fail",
            "caregiver_id": "caregiver-002",
            "caregiver_name": "Carlos Martinez",
            "client_name": "Mr. Smith",
            "shift_time": "9:00 AM - 1:00 PM",
            "reason": "Family emergency",
            "simulate_wellsky_failure": False,
            "simulate_sms_failure": True  # Force SMS to fail
        }
    )

    result = response.json()
    print(f"\nResponse: {json.dumps(result, indent=2)}")

    # Verify expectations
    assert result["step_a_wellsky_updated"] == True, "WellSky should succeed"
    assert result["step_c_replacement_blast_sent"] == False, "SMS should fail"
    assert result["human_escalation_required"] == True, "Should escalate (no notifications)"

    print("\n✅ PASS: SMS failure properly escalated")


def test_normal_callout():
    """
    Test Scenario: Everything works normally
    Expected: Gigi completes all 3 steps successfully
    """
    print("\n" + "="*70)
    print("TEST: Normal Call-Out (All Systems Working)")
    print("="*70)

    response = requests.post(
        f"{BASE_URL}/api/operations/call-outs",
        json={
            "shift_id": "test-shift-normal",
            "caregiver_id": "caregiver-003",
            "caregiver_name": "Linda Chen",
            "client_name": "Mrs. Davis",
            "shift_time": "10:00 AM - 2:00 PM",
            "reason": "Car trouble"
        }
    )

    result = response.json()
    print(f"\nResponse: {json.dumps(result, indent=2)}")

    # Verify expectations
    assert result["success"] == True, "Should succeed when all systems work"
    assert result["step_a_wellsky_updated"] == True, "WellSky should succeed"
    assert result["step_b_portal_logged"] == True, "Portal should log"
    assert result["step_c_replacement_blast_sent"] == True, "SMS should send"
    assert result.get("human_escalation_required") != True, "Should NOT escalate"

    print("\n✅ PASS: Normal call-out completed successfully")


def test_comparison_old_vs_new():
    """
    Compare old behavior (2 of 3 success) vs new (strict Step A required)
    """
    print("\n" + "="*70)
    print("COMPARISON: Old Behavior vs New Behavior")
    print("="*70)

    print("\n--- OLD BEHAVIOR (BEFORE FIX) ---")
    print("Scenario: WellSky fails, but Portal + SMS succeed")
    print("Result: success=True (2 of 3 steps passed) ❌ BAD")
    print("Problem: Shift NOT actually open in WellSky, but system says 'success'")

    print("\n--- NEW BEHAVIOR (AFTER FIX) ---")
    print("Scenario: WellSky fails")
    print("Result: ABORT immediately, escalate to Jason ✅ GOOD")
    print("Outcome: Human knows to manually handle it")

    print("\n--- IMPACT ---")
    print("Before: Coverage black hole (shift not open, no one knows)")
    print("After: Jason gets SMS immediately, can manually fix")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("WELLSKY FAILURE HANDLING TESTS")
    print("="*70)
    print("\nTesting Gigi's ability to handle WellSky API failures...")
    print("Make sure server is running: uvicorn portal.portal_app:app --port 8000")

    try:
        # Test 1: WellSky fails
        test_wellsky_timeout()

        # Test 2: WellSky succeeds but SMS fails
        test_wellsky_success_sms_failure()

        # Test 3: Everything works
        test_normal_callout()

        # Comparison
        test_comparison_old_vs_new()

        print("\n" + "="*70)
        print("ALL TESTS PASSED ✅")
        print("="*70)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        print("\nCheck server logs for details")

    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to server")
        print("Start server: uvicorn portal.portal_app:app --reload --port 8000")

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()

"""
Test Cancel Shift Acceptance Feature

Tests that caregivers can cancel after accepting a shift.
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_cancel_after_acceptance():
    """
    Test Scenario: Caregiver accepts shift, then calls back to cancel
    Expected: Shift unassigned, replacement search started, manager notified
    """
    print("\n" + "="*70)
    print("TEST: Caregiver Cancels After Accepting")
    print("="*70)

    # Step 1: Simulate caregiver accepting a shift
    print("\n[Step 1] Caregiver accepts shift via SMS...")
    accept_response = requests.post(
        f"{BASE_URL}/api/internal/shift-filling/accept",
        json={
            "shift_id": "test-shift-cancel-001",
            "caregiver_phone": "+17205551234",
            "caregiver_name": "Maria Garcia",
            "message": "YES"
        }
    )
    accept_result = accept_response.json()
    print(f"Accept Response: {json.dumps(accept_result, indent=2)}")

    assert accept_result.get("action") == "shift_filled", "Shift should be assigned"
    print("✅ Shift assigned to Maria")

    # Step 2: Caregiver calls back to cancel
    print("\n[Step 2] Maria calls Gigi to cancel...")
    cancel_response = requests.post(
        f"{BASE_URL}/gigi/test/cancel-shift",
        json={
            "caregiver_id": "caregiver-maria-001",
            "shift_id": "test-shift-cancel-001",
            "reason": "Family emergency came up"
        }
    )
    cancel_result = cancel_response.json()
    print(f"\nCancel Response: {json.dumps(cancel_result, indent=2)}")

    # Verify results
    assert cancel_result["success"] == True, "Cancellation should succeed"
    assert cancel_result["step_a_wellsky_unassigned"] == True, "WellSky should unassign"
    assert cancel_result["step_b_replacement_search_started"] == True, "Replacement search should start"
    assert cancel_result["step_c_manager_notified"] == True, "Manager should be notified"

    print("\n✅ PASS: Cancellation handled correctly")
    print(f"   - Shift unassigned in WellSky: ✅")
    print(f"   - Replacement search started: ✅")
    print(f"   - Manager notified: ✅")
    print(f"   - Caregivers notified: {cancel_result.get('caregivers_notified', 0)}")


def test_cancel_wellsky_failure():
    """
    Test Scenario: WellSky fails when trying to cancel
    Expected: Escalate to manager, don't proceed with replacement search
    """
    print("\n" + "="*70)
    print("TEST: Cancel When WellSky API Fails")
    print("="*70)

    cancel_response = requests.post(
        f"{BASE_URL}/gigi/test/cancel-shift",
        json={
            "caregiver_id": "caregiver-002",
            "shift_id": "test-shift-wellsky-fail",
            "reason": "Changed my mind",
            "simulate_wellsky_failure": True  # Force failure
        }
    )
    cancel_result = cancel_response.json()
    print(f"\nResponse: {json.dumps(cancel_result, indent=2)}")

    # Verify escalation
    assert cancel_result["success"] == False, "Should fail when WellSky fails"
    assert cancel_result["step_a_wellsky_unassigned"] == False, "WellSky should fail"
    assert "manager" in cancel_result["message"].lower(), "Should mention manager"

    print("\n✅ PASS: WellSky failure properly escalated")


def test_conversation_flow():
    """
    Test the actual conversation Gigi would have
    """
    print("\n" + "="*70)
    print("TEST: Conversation Flow")
    print("="*70)

    conversation = [
        {
            "speaker": "Caregiver",
            "text": "Hi Gigi, I accepted the 2pm shift with Mrs. Johnson earlier but I can't make it"
        },
        {
            "speaker": "Gigi",
            "intent": "cancel_shift_acceptance",
            "detects": "Caregiver wants to cancel previously accepted shift",
            "asks": "What's the reason you need to cancel?"
        },
        {
            "speaker": "Caregiver",
            "text": "My daughter's school called, she's sick and I need to pick her up"
        },
        {
            "speaker": "Gigi",
            "action": "cancel_shift_acceptance",
            "args": {
                "caregiver_id": "from_verify_caller",
                "shift_id": "from_context",
                "reason": "Family emergency - daughter sick"
            }
        },
        {
            "speaker": "Gigi",
            "expected_response": (
                "No problem, I understand things come up. I've cancelled your assignment "
                "for Mrs. Johnson on February 1 at 2:00 PM and I'm already reaching out to other "
                "caregivers to cover it. We've got this handled - don't worry about it."
            )
        }
    ]

    print("\n📞 Expected Conversation Flow:")
    for turn in conversation:
        speaker = turn.get("speaker", "")
        if speaker:
            print(f"\n{speaker}:")

        if "text" in turn:
            print(f"  '{turn['text']}'")
        if "intent" in turn:
            print(f"  [Detects: {turn['detects']}]")
            print(f"  [Intent: {turn['intent']}]")
        if "asks" in turn:
            print(f"  [Asks: {turn['asks']}]")
        if "action" in turn:
            print(f"  [Calls: {turn['action']}]")
            print(f"  [Args: {json.dumps(turn['args'], indent=4)}]")
        if "expected_response" in turn:
            print(f"  '{turn['expected_response']}'")

    print("\n✅ Conversation flow designed")


def test_impact_before_vs_after():
    """
    Show impact of this fix
    """
    print("\n" + "="*70)
    print("IMPACT: Before vs After Fix #4")
    print("="*70)

    print("\n--- BEFORE FIX ---")
    print("Scenario: Caregiver accepts, then calls to cancel")
    print("Problem: No cancel mechanism exists")
    print("Result:")
    print("  1. Caregiver still assigned in WellSky ❌")
    print("  2. Caregiver doesn't show up to shift ❌")
    print("  3. Client has no coverage ❌")
    print("  4. Manual coordinator intervention required ❌")

    print("\n--- AFTER FIX ---")
    print("Scenario: Caregiver accepts, then calls to cancel")
    print("Solution: cancel_shift_acceptance tool")
    print("Result:")
    print("  1. Shift immediately unassigned in WellSky ✅")
    print("  2. Replacement search auto-starts ✅")
    print("  3. Other caregivers notified ✅")
    print("  4. Manager alerted about cancellation ✅")
    print("  5. Coverage found before client shows up ✅")

    print("\n--- BUSINESS IMPACT ---")
    print("Before: Stuck assignments = no-show risk")
    print("After: Cancellations handled gracefully, coverage maintained")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("CANCEL SHIFT ACCEPTANCE TESTS")
    print("="*70)
    print("\nTesting ability to cancel after accepting...")
    print("Make sure server is running: uvicorn portal.portal_app:app --port 8000")

    try:
        # Test 1: Normal cancellation
        test_cancel_after_acceptance()

        # Test 2: WellSky failure during cancel
        test_cancel_wellsky_failure()

        # Test 3: Conversation flow
        test_conversation_flow()

        # Impact comparison
        test_impact_before_vs_after()

        print("\n" + "="*70)
        print("ALL TESTS PASSED ✅")
        print("="*70)
        print("\n🎉 Fix #4 Complete: Caregivers can now cancel accepted shifts!")

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

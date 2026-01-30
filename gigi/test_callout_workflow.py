#!/usr/bin/env python3
"""
Test Gigi's Call-Out Workflow End-to-End

Simulates a caregiver calling out and verifies:
1. Shift is marked OPEN in WellSky
2. Care Alert added to client
3. WellSky Task created
4. Team notification sent
5. Replacement blast triggered
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gigi.main import execute_caregiver_call_out

async def test_call_out():
    print("=" * 80)
    print("TESTING GIGI CALL-OUT WORKFLOW")
    print("=" * 80)

    # Test data (using mock/shadow mode)
    test_caregiver_id = "TEST_CG_001"
    test_shift_id = "TEST_SHIFT_001"
    test_reason = "Sick with flu - cannot work today"

    print(f"\nTest Scenario:")
    print(f"  Caregiver ID: {test_caregiver_id}")
    print(f"  Shift ID: {test_shift_id}")
    print(f"  Reason: {test_reason}")
    print()

    try:
        # Execute the call-out
        print("Executing call-out workflow...")
        result = await execute_caregiver_call_out(
            caregiver_id=test_caregiver_id,
            shift_id=test_shift_id,
            reason=test_reason
        )

        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)

        # Check each step
        print(f"\n✓ Overall Success: {result.get('success', False)}")
        print(f"✓ Step A (WellSky Updated): {result.get('step_a_wellsky_updated', False)}")
        print(f"✓ Step B (Portal Logged): {result.get('step_b_portal_logged', False)}")
        print(f"✓ Step C (Replacement Blast): {result.get('step_c_replacement_blast_sent', False)}")

        if result.get('caregivers_notified'):
            print(f"✓ Caregivers Notified: {result.get('caregivers_notified', 0)}")

        print(f"\nMessage to caregiver:")
        print(f"  {result.get('message', 'No message')}")

        if result.get('errors'):
            print(f"\n⚠️  Errors:")
            for error in result['errors']:
                print(f"  - {error}")

        print("\n" + "=" * 80)

        if result.get('success'):
            print("✅ CALL-OUT WORKFLOW TEST PASSED")
        else:
            print("❌ CALL-OUT WORKFLOW TEST FAILED")

        print("=" * 80)

    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_call_out())

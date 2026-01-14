#!/usr/bin/env python3
"""
Test script for Shift Filling POC

Run this to verify the complete shift filling workflow.
"""

import sys
from datetime import date

def test_wellsky_mock():
    """Test WellSky mock service"""
    print("\n1. Testing WellSky Mock Service")
    print("=" * 50)

    from wellsky_mock import wellsky_mock

    # Test clients
    clients = list(wellsky_mock._clients.values())
    print(f"   Clients loaded: {len(clients)}")

    # Test caregivers
    caregivers = wellsky_mock.get_available_caregivers(date.today())
    print(f"   Available caregivers: {len(caregivers)}")

    # Test shifts
    shifts = wellsky_mock.get_open_shifts()
    print(f"   Open shifts: {len(shifts)}")

    assert len(clients) > 0, "No clients loaded"
    assert len(caregivers) > 0, "No caregivers available"
    print("   ✓ WellSky Mock Service working")
    return True


def test_matcher():
    """Test caregiver matching algorithm"""
    print("\n2. Testing Caregiver Matcher")
    print("=" * 50)

    from matcher import CaregiverMatcher
    from wellsky_mock import wellsky_mock

    matcher = CaregiverMatcher(wellsky_mock)
    shifts = wellsky_mock.get_open_shifts()

    if not shifts:
        print("   No open shifts to test with")
        return False

    shift = shifts[0]
    matches = matcher.find_replacements(shift)

    print(f"   Shift: {shift.id} - {shift.client.full_name if shift.client else 'Unknown'}")
    print(f"   Matches found: {len(matches)}")
    print(f"   Tier 1: {sum(1 for m in matches if m.tier == 1)}")
    print(f"   Tier 2: {sum(1 for m in matches if m.tier == 2)}")
    print(f"   Tier 3: {sum(1 for m in matches if m.tier == 3)}")

    if matches:
        top = matches[0]
        print(f"\n   Top match: {top.caregiver.full_name}")
        print(f"   Score: {top.score}")
        print(f"   Reasons: {top.reasons[:2]}")

    assert len(matches) > 0, "No matches found"
    assert matches[0].score > 0, "Score should be positive"
    print("   ✓ Caregiver Matcher working")
    return True


def test_sms_service():
    """Test SMS service"""
    print("\n3. Testing SMS Service")
    print("=" * 50)

    from sms_service import sms_service
    from wellsky_mock import wellsky_mock
    from models import CaregiverResponseType

    shifts = wellsky_mock.get_open_shifts()
    caregivers = wellsky_mock.get_available_caregivers(date.today())

    if not shifts or not caregivers:
        print("   Missing test data")
        return False

    shift = shifts[0]
    caregiver = caregivers[0]

    # Test message building
    message = sms_service.build_shift_message(shift, caregiver)
    print(f"   Message length: {len(message)} chars")
    assert len(message) > 50, "Message too short"
    assert caregiver.first_name in message, "Should include caregiver name"

    # Test response parsing
    assert sms_service.parse_response("yes") == CaregiverResponseType.ACCEPTED
    assert sms_service.parse_response("no") == CaregiverResponseType.DECLINED
    assert sms_service.parse_response("maybe") == CaregiverResponseType.AMBIGUOUS

    print("   ✓ SMS Service working")
    return True


def test_engine():
    """Test shift filling engine"""
    print("\n4. Testing Shift Filling Engine")
    print("=" * 50)

    from engine import ShiftFillingEngine
    from models import OutreachStatus

    engine = ShiftFillingEngine()

    # Run demo
    result = engine.simulate_demo()

    print(f"   Demo result: {result.get('success')}")
    print(f"   Campaign ID: {result.get('campaign_id', 'N/A')[:20]}...")
    print(f"   Matches found: {result.get('matches_found')}")
    print(f"   Contacted: {result.get('caregivers_contacted')}")
    print(f"   Status: {result.get('campaign_status')}")
    print(f"   Winner: {result.get('winner')}")

    assert result.get('success'), "Demo should succeed"
    assert result.get('campaign_status') == 'filled', "Should fill shift"
    assert result.get('winner'), "Should have a winner"

    print("   ✓ Shift Filling Engine working")
    return True


def test_full_workflow():
    """Test complete workflow"""
    print("\n5. Testing Full Workflow (Calloff → Assignment)")
    print("=" * 50)

    from engine import ShiftFillingEngine
    from wellsky_mock import wellsky_mock
    from models import OutreachStatus

    engine = ShiftFillingEngine()

    # Get a shift with an assigned caregiver
    shifts = wellsky_mock.get_shifts()
    assigned_shift = None
    for s in shifts:
        if s.assigned_caregiver_id:
            assigned_shift = s
            break

    if not assigned_shift:
        print("   No assigned shifts to test calloff")
        return True

    print(f"   Original shift: {assigned_shift.id}")
    print(f"   Original caregiver: {assigned_shift.assigned_caregiver_id}")

    # Process calloff
    campaign = engine.process_calloff(
        shift_id=assigned_shift.id,
        caregiver_id=assigned_shift.assigned_caregiver_id,
        reason="Sick"
    )

    assert campaign is not None, "Campaign should be created"
    print(f"   Campaign created: {campaign.id[:20]}...")
    print(f"   Caregivers contacted: {campaign.total_contacted}")

    # Simulate first response accepting
    if campaign.caregivers_contacted:
        first_outreach = campaign.caregivers_contacted[0]
        result = engine.process_response(
            campaign_id=campaign.id,
            phone=first_outreach.phone,
            message_text="Yes I can cover"
        )

        print(f"   Response processed: {result.get('action')}")
        print(f"   Campaign status: {campaign.status.value}")

        if result.get('action') == 'shift_filled':
            print(f"   New caregiver: {result.get('assigned_caregiver')}")

    print("   ✓ Full Workflow working")
    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("SHIFT FILLING POC - TEST SUITE")
    print("=" * 60)

    tests = [
        ("WellSky Mock", test_wellsky_mock),
        ("Caregiver Matcher", test_matcher),
        ("SMS Service", test_sms_service),
        ("Shift Filling Engine", test_engine),
        ("Full Workflow", test_full_workflow),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"   ✗ {name} FAILED")
        except Exception as e:
            failed += 1
            print(f"   ✗ {name} ERROR: {e}")

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    # Change to script directory for imports
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    success = main()
    sys.exit(0 if success else 1)

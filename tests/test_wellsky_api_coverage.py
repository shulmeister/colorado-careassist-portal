#!/usr/bin/env python3
"""
Comprehensive WellSky API Coverage Test

Tests ALL FHIR Connect API methods on WellSkyService in mock mode.
Each method is tested for: existence, callability, correct return type.

Usage:
    export $(grep -v '^#' ~/.gigi-env | grep '=' | xargs)
    python3 tests/test_wellsky_api_coverage.py
"""

import sys
import os
import traceback
from datetime import date, datetime, timedelta

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.wellsky_service import WellSkyService


def create_mock_service() -> WellSkyService:
    """
    Create a WellSkyService instance forced into mock mode.

    The service has hardcoded credentials, so is_configured is always True.
    We override api_key to empty string after init, then manually
    initialize mock data to simulate mock mode.
    """
    svc = WellSkyService()
    # Force mock mode by clearing credentials
    svc.api_key = ""
    svc.api_secret = ""
    svc.agency_id = ""
    # Populate mock data stores
    svc._initialize_mock_data()
    assert svc.is_mock_mode, "Service should be in mock mode after clearing credentials"
    return svc


def get_valid_shift_id(svc) -> str:
    """Get a valid shift ID from mock data for testing clock in/out."""
    # Find a future scheduled shift that has not been clocked in
    for shift_id, shift in svc._mock_shifts.items():
        if shift.date and shift.date >= date.today() and shift.clock_in_time is None:
            return shift_id
    # Fallback: just use any shift
    if svc._mock_shifts:
        return next(iter(svc._mock_shifts))
    return "UNKNOWN"


def run_tests():
    """Run all API method tests and report results."""
    svc = create_mock_service()

    results = []  # list of (category, label, passed, error_msg)

    def test(category: str, method_name: str, call_fn, label: str = None):
        """
        Run a single test, capturing pass/fail and any error.

        Args:
            category: Test group name
            method_name: Actual method name on WellSkyService (for hasattr check)
            call_fn: Callable that exercises the method
            label: Display label (defaults to method_name)
        """
        display = label or method_name
        try:
            # Verify method exists
            assert hasattr(svc, method_name), f"Method '{method_name}' not found on WellSkyService"
            # Call it
            result = call_fn()
            results.append((category, display, True, None))
        except Exception as e:
            tb = traceback.format_exc()
            results.append((category, display, False, f"{e}\n{tb}"))

    # =========================================================================
    # Patient CRUD
    # =========================================================================
    test("Patient", "search_patients", lambda: svc.search_patients())
    test("Patient", "search_patients",
         lambda: svc.search_patients(first_name="Robert", active=True),
         label="search_patients (filtered)")

    test("Patient", "get_patient", lambda: svc.get_patient("C001"))
    test("Patient", "get_patient",
         lambda: svc.get_patient("NONEXISTENT"),
         label="get_patient (missing)")

    def _create_patient():
        result = svc.create_patient(
            first_name="Test",
            last_name="Patient",
            phone="3035551234",
            email="test@example.com",
            city="Denver",
            state="CO",
            zip_code="80202",
        )
        assert result is not None, "create_patient should return a WellSkyClient"
        return result
    test("Patient", "create_patient", _create_patient)

    def _update_patient():
        success, data = svc.update_patient("C001", first_name="Bobby")
        assert success is True, f"update_patient should succeed, got {data}"
        return success, data
    test("Patient", "update_patient", _update_patient)

    def _update_patient_missing():
        success, data = svc.update_patient("NONEXISTENT", first_name="Nope")
        assert success is False, "update_patient on missing ID should return False"
        return success, data
    test("Patient", "update_patient", _update_patient_missing,
         label="update_patient (missing)")

    def _delete_patient():
        success, data = svc.delete_patient("C003")
        assert success is True, f"delete_patient should succeed, got {data}"
        return success, data
    test("Patient", "delete_patient", _delete_patient)

    def _delete_patient_missing():
        success, data = svc.delete_patient("NONEXISTENT")
        assert success is False, "delete_patient on missing ID should return False"
        return success, data
    test("Patient", "delete_patient", _delete_patient_missing,
         label="delete_patient (missing)")

    # =========================================================================
    # Practitioner CRUD
    # =========================================================================
    test("Practitioner", "search_practitioners", lambda: svc.search_practitioners())
    test("Practitioner", "search_practitioners",
         lambda: svc.search_practitioners(first_name="Maria", active=True),
         label="search_practitioners (filtered)")

    test("Practitioner", "get_practitioner", lambda: svc.get_practitioner("CG001"))
    test("Practitioner", "get_practitioner",
         lambda: svc.get_practitioner("NONEXISTENT"),
         label="get_practitioner (missing)")

    def _create_practitioner():
        success, data = svc.create_practitioner(
            first_name="Test",
            last_name="Caregiver",
            phone="3035559876",
            email="caregiver@example.com",
            city="Aurora",
            is_hired=True,
        )
        assert success is True, f"create_practitioner should succeed, got {data}"
        return success, data
    test("Practitioner", "create_practitioner", _create_practitioner)

    def _update_practitioner():
        success, data = svc.update_practitioner("CG001", first_name="Maria-Updated")
        assert success is True, f"update_practitioner should succeed, got {data}"
        return success, data
    test("Practitioner", "update_practitioner", _update_practitioner)

    def _update_practitioner_missing():
        success, data = svc.update_practitioner("NONEXISTENT", first_name="Nope")
        assert success is False, "update_practitioner on missing ID should return False"
        return success, data
    test("Practitioner", "update_practitioner", _update_practitioner_missing,
         label="update_practitioner (missing)")

    def _delete_practitioner():
        success, data = svc.delete_practitioner("CG003")
        assert success is True, f"delete_practitioner should succeed, got {data}"
        return success, data
    test("Practitioner", "delete_practitioner", _delete_practitioner)

    def _delete_practitioner_missing():
        success, data = svc.delete_practitioner("NONEXISTENT")
        assert success is False, "delete_practitioner on missing ID should return False"
        return success, data
    test("Practitioner", "delete_practitioner", _delete_practitioner_missing,
         label="delete_practitioner (missing)")

    # =========================================================================
    # Appointment CRUD
    # =========================================================================
    test("Appointment", "search_appointments", lambda: svc.search_appointments(
        client_id="C001",
        start_date=date.today(),
        additional_days=6,
    ))

    def _create_appointment():
        success, data = svc.create_appointment(
            client_id="C001",
            caregiver_id="CG001",
            start_datetime="2026-02-10T08:00:00",
            end_datetime="2026-02-10T12:00:00",
        )
        assert success is True, f"create_appointment should succeed, got {data}"
        return success, data
    test("Appointment", "create_appointment", _create_appointment)

    test("Appointment", "get_appointment", lambda: svc.get_appointment("MOCK001"))

    def _update_appointment():
        success, data = svc.update_appointment("MOCK001", {"status": "CANCELLED"})
        assert success is True, f"update_appointment should succeed, got {data}"
        return success, data
    test("Appointment", "update_appointment", _update_appointment)

    def _delete_appointment():
        # In mock mode, nonexistent returns False -- method still runs without error
        success, data = svc.delete_appointment("NONEXISTENT")
        return success, data
    test("Appointment", "delete_appointment", _delete_appointment)

    # =========================================================================
    # Encounter CRUD
    # =========================================================================
    def _create_encounter():
        success, data = svc.create_encounter(
            patient_id="C001",
            practitioner_id="CG001",
            start_datetime="2026-02-04T09:00:00",
            end_datetime="2026-02-04T13:00:00",
        )
        assert success is True, f"create_encounter should succeed, got {data}"
        return success, data
    test("Encounter", "create_encounter", _create_encounter)

    def _get_encounter():
        success, data = svc.get_encounter("mock-encounter-123")
        assert success is True, f"get_encounter should succeed, got {data}"
        return success, data
    test("Encounter", "get_encounter", _get_encounter)

    def _search_encounters():
        success, data = svc.search_encounters(client_id="C001")
        assert success is True, f"search_encounters should succeed, got {data}"
        return success, data
    test("Encounter", "search_encounters", _search_encounters)

    def _update_encounter():
        success, data = svc.update_encounter("mock-encounter-123", status="COMPLETE")
        assert success is True, f"update_encounter should succeed, got {data}"
        return success, data
    test("Encounter", "update_encounter", _update_encounter)

    def _delete_encounter():
        success, data = svc.delete_encounter("mock-encounter-123")
        assert success is True, f"delete_encounter should succeed, got {data}"
        return success, data
    test("Encounter", "delete_encounter", _delete_encounter)

    # =========================================================================
    # Clock In / Clock Out
    # =========================================================================
    # Note: Python uses the LAST definition of clock_in_shift / clock_out_shift
    # in the file. The legacy version (line ~3913) has signature:
    #   clock_in_shift(shift_id, clock_in_time=None, notes="", lat=0.0, lon=0.0)
    #   clock_out_shift(shift_id, clock_out_time=None, notes="")
    # The mock mode checks _mock_shifts for a matching shift ID.

    valid_shift_id = get_valid_shift_id(svc)

    def _clock_in():
        success, msg = svc.clock_in_shift(valid_shift_id, notes="Test clock in")
        assert success is True, f"clock_in_shift should succeed, got {msg}"
        return success, msg
    test("ClockIn/Out", "clock_in_shift", _clock_in)

    def _clock_out():
        # clock_out requires the shift to have been clocked in first
        success, msg = svc.clock_out_shift(valid_shift_id, notes="Test clock out")
        assert success is True, f"clock_out_shift should succeed, got {msg}"
        return success, msg
    test("ClockIn/Out", "clock_out_shift", _clock_out)

    # =========================================================================
    # Task / TaskLog
    # =========================================================================
    def _create_task_log():
        success, data = svc.create_task_log(
            encounter_id="mock-encounter-123",
            title="Test Task",
            description="Testing task log creation",
        )
        assert success is True, f"create_task_log should succeed, got {data}"
        return success, data
    test("Task", "create_task_log", _create_task_log)

    def _get_task_logs():
        success, data = svc.get_task_logs("mock-encounter-123")
        assert success is True, f"get_task_logs should succeed, got {data}"
        return success, data
    test("Task", "get_task_logs", _get_task_logs)

    def _update_task():
        success, data = svc.update_task(
            encounter_id="mock-encounter-123",
            task_id="task-001",
            status="COMPLETE",
        )
        assert success is True, f"update_task should succeed, got {data}"
        return success, data
    test("Task", "update_task", _update_task)

    def _update_task_log():
        success, data = svc.update_task_log(
            encounter_id="mock-encounter-123",
            tasklog_id="tl-001",
            title="Updated Title",
            description="Updated description",
        )
        assert success is True, f"update_task_log should succeed, got {data}"
        return success, data
    test("Task", "update_task_log", _update_task_log)

    # =========================================================================
    # DocumentReference CRUD
    # =========================================================================
    def _create_document_reference():
        import base64
        content = base64.b64encode(b"Test document content").decode("utf-8")
        success, data = svc.create_document_reference(
            patient_id="C001",
            document_type="clinical-note",
            content_type="text/plain",
            data_base64=content,
            description="Test document",
        )
        assert success is True, f"create_document_reference should succeed, got {data}"
        return success, data
    test("DocumentReference", "create_document_reference", _create_document_reference)

    def _get_document_reference():
        success, data = svc.get_document_reference("mock-doc-123")
        assert success is True, f"get_document_reference should succeed, got {data}"
        return success, data
    test("DocumentReference", "get_document_reference", _get_document_reference)

    def _search_document_references():
        success, data = svc.search_document_references(patient_id="C001")
        assert success is True, f"search_document_references should succeed, got {data}"
        return success, data
    test("DocumentReference", "search_document_references", _search_document_references)

    def _update_document_reference():
        success, data = svc.update_document_reference(
            document_id="mock-doc-123",
            description="Updated description",
        )
        assert success is True, f"update_document_reference should succeed, got {data}"
        return success, data
    test("DocumentReference", "update_document_reference", _update_document_reference)

    def _delete_document_reference():
        success, data = svc.delete_document_reference("mock-doc-123")
        assert success is True, f"delete_document_reference should succeed, got {data}"
        return success, data
    test("DocumentReference", "delete_document_reference", _delete_document_reference)

    # =========================================================================
    # Subscription CRUD
    # =========================================================================
    def _create_subscription():
        success, data = svc.create_subscription(
            criteria="patient.created",
            endpoint_url="https://portal.coloradocareassist.com/webhooks/wellsky",
            reason="Test subscription",
        )
        assert success is True, f"create_subscription should succeed, got {data}"
        return success, data
    test("Subscription", "create_subscription", _create_subscription)

    def _get_subscription():
        success, data = svc.get_subscription("sub-001")
        assert success is True, f"get_subscription should succeed, got {data}"
        return success, data
    test("Subscription", "get_subscription", _get_subscription)

    def _search_subscriptions():
        success, data = svc.search_subscriptions(status="active")
        assert success is True, f"search_subscriptions should succeed, got {data}"
        return success, data
    test("Subscription", "search_subscriptions", _search_subscriptions)

    def _update_subscription():
        success, data = svc.update_subscription(
            subscription_id="sub-001",
            status="off",
        )
        assert success is True, f"update_subscription should succeed, got {data}"
        return success, data
    test("Subscription", "update_subscription", _update_subscription)

    def _delete_subscription():
        success, data = svc.delete_subscription("sub-001")
        assert success is True, f"delete_subscription should succeed, got {data}"
        return success, data
    test("Subscription", "delete_subscription", _delete_subscription)

    # =========================================================================
    # ProfileTags CRUD
    # =========================================================================
    def _create_profile_tag():
        success, data = svc.create_profile_tag(
            name="CNA",
            description="Certified Nursing Assistant",
            tag_type="certification",
        )
        assert success is True, f"create_profile_tag should succeed, got {data}"
        return success, data
    test("ProfileTags", "create_profile_tag", _create_profile_tag)

    def _get_profile_tag():
        success, data = svc.get_profile_tag("tag-001")
        assert success is True, f"get_profile_tag should succeed, got {data}"
        return success, data
    test("ProfileTags", "get_profile_tag", _get_profile_tag)

    def _search_profile_tags():
        success, data = svc.search_profile_tags(name="CNA")
        assert success is True, f"search_profile_tags should succeed, got {data}"
        return success, data
    test("ProfileTags", "search_profile_tags", _search_profile_tags)

    def _update_profile_tag():
        success, data = svc.update_profile_tag(
            tag_id="tag-001",
            name="CNA Updated",
        )
        assert success is True, f"update_profile_tag should succeed, got {data}"
        return success, data
    test("ProfileTags", "update_profile_tag", _update_profile_tag)

    def _delete_profile_tag():
        success, data = svc.delete_profile_tag("tag-001")
        assert success is True, f"delete_profile_tag should succeed, got {data}"
        return success, data
    test("ProfileTags", "delete_profile_tag", _delete_profile_tag)

    # =========================================================================
    # RelatedPerson CRUD
    # =========================================================================
    def _get_related_persons():
        success, data = svc.get_related_persons("C001")
        assert success is True, f"get_related_persons should succeed, got {data}"
        return success, data
    test("RelatedPerson", "get_related_persons", _get_related_persons)

    def _create_related_person():
        success, data = svc.create_related_person(
            patient_id="C001",
            first_name="Jane",
            last_name="Johnson",
            relationship_code="DAU",
            phone="3035554321",
            email="jane@example.com",
            is_emergency_contact=True,
        )
        assert success is True, f"create_related_person should succeed, got {data}"
        return success, data
    test("RelatedPerson", "create_related_person", _create_related_person)

    def _search_related_persons():
        success, data = svc.search_related_persons(patient_id="C001")
        assert success is True, f"search_related_persons should succeed, got {data}"
        return success, data
    test("RelatedPerson", "search_related_persons", _search_related_persons)

    def _update_related_person():
        success, data = svc.update_related_person(
            contact_id="rp-001",
            first_name="Jane-Updated",
            is_primary_contact=True,
        )
        assert success is True, f"update_related_person should succeed, got {data}"
        return success, data
    test("RelatedPerson", "update_related_person", _update_related_person)

    def _delete_related_person():
        success, data = svc.delete_related_person(
            patient_id="C001",
            contact_id="rp-001",
        )
        assert success is True, f"delete_related_person should succeed, got {data}"
        return success, data
    test("RelatedPerson", "delete_related_person", _delete_related_person)

    # =========================================================================
    # Report
    # =========================================================================
    print("\n" + "=" * 80)
    print("WELLSKY API COVERAGE TEST RESULTS")
    print("=" * 80)

    passed = 0
    failed = 0
    current_category = None

    for category, label, ok, err in results:
        if category != current_category:
            current_category = category
            print(f"\n  [{category}]")

        status = "PASS" if ok else "FAIL"
        icon = "+" if ok else "!"
        print(f"    [{icon}] {status}  {label}")
        if ok:
            passed += 1
        else:
            failed += 1
            # Print first line of error for context
            first_line = (err or "").split("\n")[0]
            print(f"           Error: {first_line}")

    total = passed + failed
    print(f"\n{'=' * 80}")
    print(f"SUMMARY: {passed}/{total} passed, {failed}/{total} failed")

    if failed == 0:
        print("STATUS: ALL TESTS PASSED")
    else:
        print(f"STATUS: {failed} TEST(S) FAILED")

    print("=" * 80 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

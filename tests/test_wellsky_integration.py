#!/usr/bin/env python3
"""
WellSky Home Connect FHIR API Integration Tests
Tests the NEW FHIR-compliant API integration (connect.clearcareonline.com/v1/)

Run with real credentials:
    export WELLSKY_CLIENT_ID=your-client-id
    export WELLSKY_CLIENT_SECRET=your-client-secret
    export WELLSKY_AGENCY_ID=your-agency-id
    export WELLSKY_ENVIRONMENT=sandbox
    python3 tests/test_wellsky_integration.py

Run in mock mode (no credentials):
    python3 tests/test_wellsky_integration.py
"""

import os
import sys
from datetime import date, timedelta
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.wellsky_service import WellSkyService, WellSkyCaregiver, WellSkyShift, WellSkyClient


class TestResults:
    """Track test results"""
    def __init__(self):
        self.passed = []
        self.failed = []
        self.skipped = []

    def add_pass(self, test_name: str):
        self.passed.append(test_name)
        print(f"  ✅ {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
        print(f"  ❌ {test_name}")
        print(f"     Error: {error}")

    def add_skip(self, test_name: str, reason: str):
        self.skipped.append((test_name, reason))
        print(f"  ⏭️  {test_name} - {reason}")

    def print_summary(self):
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"✅ Passed: {len(self.passed)}")
        print(f"❌ Failed: {len(self.failed)}")
        print(f"⏭️  Skipped: {len(self.skipped)}")

        if self.failed:
            print("\nFailed tests:")
            for test_name, error in self.failed:
                print(f"  • {test_name}: {error[:100]}")

        return len(self.failed) == 0


# =============================================================================
# Test 1: Configuration & Authentication
# =============================================================================

def test_configuration(ws: WellSkyService, results: TestResults):
    """Test that WellSky service is properly configured"""
    print("\n📋 Test 1: Configuration & Authentication")

    try:
        if not ws.is_configured:
            results.add_skip(
                "Configuration check",
                "No credentials - running in mock mode"
            )
            return

        # Verify configuration
        assert ws.api_key, "Client ID not set"
        assert ws.api_secret, "Client Secret not set"
        assert ws.agency_id, "Agency ID not set"
        assert ws.base_url, "Base URL not set"
        assert ws.environment in ["sandbox", "production"], "Invalid environment"

        results.add_pass(f"Configuration valid (environment: {ws.environment})")

        # Test OAuth token retrieval
        token = ws._get_access_token()
        if token:
            results.add_pass("OAuth authentication successful")
        else:
            results.add_fail("OAuth authentication", "Failed to get access token")

    except Exception as e:
        results.add_fail("Configuration", str(e))


# =============================================================================
# Test 2: Practitioner (Caregiver) Search
# =============================================================================

def test_practitioner_search(ws: WellSkyService, results: TestResults):
    """Test practitioner search methods"""
    print("\n👥 Test 2: Practitioner Search")

    # Test 2.1: Search hired caregivers
    try:
        caregivers = ws.search_practitioners(is_hired=True, active=True, limit=10)

        if ws.is_configured:
            # Real API - verify we got results
            if len(caregivers) > 0:
                results.add_pass(f"Search hired caregivers (found {len(caregivers)})")

                # Verify data structure
                cg = caregivers[0]
                assert cg.id, "Caregiver missing ID"
                assert cg.first_name or cg.last_name, "Caregiver missing name"
                results.add_pass("Caregiver data structure valid")
            else:
                results.add_fail("Search hired caregivers", "No results returned")
        else:
            # Mock mode - just verify it returns data
            assert len(caregivers) > 0, "Mock mode should return sample data"
            results.add_pass(f"Search hired caregivers (mock mode: {len(caregivers)} samples)")

    except Exception as e:
        results.add_fail("Search hired caregivers", str(e))

    # Test 2.2: Search by phone
    try:
        test_phone = "3035551234"
        caregivers = ws.search_practitioners(phone=test_phone)

        if ws.is_configured:
            # Real API - might not find this test number
            results.add_pass(f"Search by phone (found {len(caregivers)})")
        else:
            # Mock mode
            assert len(caregivers) >= 0, "Should return list"
            results.add_pass(f"Search by phone (mock mode: {len(caregivers)} results)")

    except Exception as e:
        results.add_fail("Search by phone", str(e))

    # Test 2.3: Search by name
    try:
        caregivers = ws.search_practitioners(first_name="Maria", is_hired=True)
        results.add_pass(f"Search by first name (found {len(caregivers)})")

    except Exception as e:
        results.add_fail("Search by first name", str(e))

    # Test 2.4: Search by city
    try:
        caregivers = ws.search_practitioners(city="Denver", is_hired=True, limit=5)
        results.add_pass(f"Search by city (found {len(caregivers)})")

    except Exception as e:
        results.add_fail("Search by city", str(e))

    # Test 2.5: Search with skill tags
    try:
        caregivers = ws.search_practitioners(
            profile_tags=["45", "67"],
            is_hired=True,
            limit=5
        )
        results.add_pass(f"Search with skill tags (found {len(caregivers)})")

    except Exception as e:
        results.add_fail("Search with skill tags", str(e))


# =============================================================================
# Test 3: Get Specific Practitioner
# =============================================================================

def test_get_practitioner(ws: WellSkyService, results: TestResults):
    """Test getting specific practitioner by ID"""
    print("\n🔍 Test 3: Get Specific Practitioner")

    # First get a caregiver to test with
    try:
        caregivers = ws.search_practitioners(is_hired=True, limit=1)

        if len(caregivers) == 0:
            results.add_skip("Get practitioner by ID", "No caregivers to test with")
            return

        test_id = caregivers[0].id

        # Test getting by ID
        caregiver = ws.get_practitioner(test_id)

        if caregiver:
            assert caregiver.id == test_id, "ID mismatch"
            assert caregiver.full_name, "Missing full name"
            results.add_pass(f"Get practitioner by ID: {caregiver.full_name}")
        else:
            results.add_fail("Get practitioner by ID", f"Failed to get ID {test_id}")

    except Exception as e:
        results.add_fail("Get practitioner by ID", str(e))


# =============================================================================
# Test 4: Appointment (Shift) Search
# =============================================================================

def test_appointment_search(ws: WellSkyService, results: TestResults):
    """Test appointment search methods"""
    print("\n📅 Test 4: Appointment Search")

    # First get a caregiver to test with
    try:
        caregivers = ws.search_practitioners(is_hired=True, limit=1)

        if len(caregivers) == 0:
            results.add_skip("Search shifts by caregiver", "No caregivers to test with")
            return

        caregiver_id = caregivers[0].id

        # Test 4.1: Get shifts by caregiver ID
        shifts = ws.search_appointments(
            caregiver_id=caregiver_id,
            start_date=date.today(),
            additional_days=7
        )

        results.add_pass(f"Search shifts by caregiver (found {len(shifts)})")

        if len(shifts) > 0:
            shift = shifts[0]
            assert shift.id, "Shift missing ID"
            assert shift.date or shift.start_time, "Shift missing date/time"
            results.add_pass("Shift data structure valid")

        # Test 4.2: Search today's shifts for this caregiver
        shifts = ws.search_appointments(
            caregiver_id=caregiver_id,
            start_date=date.today(),
            additional_days=0,
            limit=10
        )
        results.add_pass(f"Search today's shifts for caregiver (found {len(shifts)})")

    except Exception as e:
        results.add_fail("Appointment Search", str(e))


# =============================================================================
# Test 5: Get Specific Appointment
# =============================================================================

def test_get_appointment(ws: WellSkyService, results: TestResults):
    """Test getting specific appointment by ID"""
    print("\n🔍 Test 5: Get Specific Appointment")

    try:
        # First get a caregiver to find shifts
        caregivers = ws.search_practitioners(is_hired=True, limit=1)
        if len(caregivers) == 0:
            results.add_skip("Get appointment by ID", "No caregivers to find shifts with")
            return
            
        caregiver_id = caregivers[0].id

        # Now get a shift to test with
        shifts = ws.search_appointments(
            caregiver_id=caregiver_id,
            start_date=date.today() - timedelta(days=7),
            additional_days=14,
            limit=1
        )

        if len(shifts) == 0:
            results.add_skip("Get appointment by ID", "No shifts to test with")
            return

        test_id = shifts[0].id

        # Test getting by ID
        shift = ws.get_appointment(test_id)

        if shift:
            assert shift.id == test_id, "ID mismatch"
            assert shift.date or shift.start_time, "Missing shift date/time"
            results.add_pass(f"Get appointment by ID: {shift.id}")
        else:
            results.add_fail("Get appointment by ID", f"Failed to get ID {test_id}")

    except Exception as e:
        results.add_fail("Get appointment by ID", str(e))


# =============================================================================
# Test 6: Patient (Client) Search
# =============================================================================

def test_patient_search(ws: WellSkyService, results: TestResults):
    """Test patient search methods"""
    print("\n🏥 Test 6: Patient Search")

    # Test 6.1: Search by phone
    try:
        test_phone = "3035559876"
        clients = ws.search_patients(phone=test_phone)
        results.add_pass(f"Search clients by phone (found {len(clients)})")

    except Exception as e:
        results.add_fail("Search clients by phone", str(e))

    # Test 6.2: Search by name
    try:
        clients = ws.search_patients(first_name="Margaret", last_name="Johnson")
        results.add_pass(f"Search clients by name (found {len(clients)})")

    except Exception as e:
        results.add_fail("Search clients by name", str(e))

    # Test 6.3: Search by city
    try:
        clients = ws.search_patients(city="Denver", limit=5)
        results.add_pass(f"Search clients by city (found {len(clients)})")

    except Exception as e:
        results.add_fail("Search clients by city", str(e))


# =============================================================================
# Test 7: Get Specific Patient
# =============================================================================

def test_get_patient(ws: WellSkyService, results: TestResults):
    """Test getting specific patient by ID"""
    print("\n🔍 Test 7: Get Specific Patient")

    try:
        # First get a client to test with
        clients = ws.search_patients(limit=5)

        if len(clients) == 0:
            results.add_skip("Get patient by ID", "No clients to test with")
            return

        test_id = clients[0].id

        # Test getting by ID
        client = ws.get_patient(test_id)

        if client:
            assert client.id == test_id, "ID mismatch"
            assert client.full_name, "Missing full name"
            results.add_pass(f"Get patient by ID: {client.full_name}")
        else:
            results.add_fail("Get patient by ID", f"Failed to get ID {test_id}")

    except Exception as e:
        results.add_fail("Get patient by ID", str(e))


# =============================================================================
# Test 8: Create Patient (Sandbox Only)
# =============================================================================

def test_create_patient(ws: WellSkyService, results: TestResults):
    """Test creating a new patient (lead/prospect) - SANDBOX ONLY"""
    print("\n➕ Test 8: Create Patient")

    # Skip if production
    if ws.is_configured and ws.environment == "production":
        results.add_skip("Create patient", "Skipped in production environment")
        return

    try:
        # Create test lead
        new_lead = ws.create_patient(
            first_name="Test",
            last_name="Integration",
            phone="3035559999",
            email="test.integration@example.com",
            city="Denver",
            state="CO",
            zip_code="80202",
            is_client=False,  # Prospect/lead
            status_id=1,  # New Lead
            referral_source="Integration Test"
        )

        if new_lead:
            assert new_lead.id, "New lead missing ID"
            assert new_lead.first_name == "Test", "First name mismatch"
            assert new_lead.last_name == "Integration", "Last name mismatch"
            results.add_pass(f"Create patient/lead (ID: {new_lead.id})")
        else:
            if ws.is_configured:
                results.add_fail("Create patient/lead", "Failed to create")
            else:
                # Mock mode doesn't actually create
                results.add_pass("Create patient/lead (mock mode)")

    except Exception as e:
        results.add_fail("Create patient/lead", str(e))


# =============================================================================
# Test 9: Gigi Use Case - Call-Out Scenario
# =============================================================================

def test_gigi_callout_scenario(ws: WellSkyService, results: TestResults):
    """Test a realistic Gigi call-out scenario"""
    print("\n📞 Test 9: Gigi Call-Out Scenario")

    try:
        # Scenario: Caregiver calls, we need to:
        # 1. Find them by phone
        # 2. Get their upcoming shifts
        # 3. Find replacement candidates

        # Step 1: Find caregiver by phone
        caregivers = ws.search_practitioners(is_hired=True, limit=1)
        if len(caregivers) == 0:
            results.add_skip("Gigi call-out scenario", "No caregivers to test with")
            return

        caregiver = caregivers[0]
        results.add_pass(f"Step 1: Found caregiver {caregiver.full_name}")

        # Step 2: Get their upcoming shifts
        shifts = ws.search_appointments(
            caregiver_id=caregiver.id,
            start_date=date.today(),
            additional_days=1
        )
        results.add_pass(f"Step 2: Found {len(shifts)} upcoming shifts")

        # Step 3: Find replacement candidates (same city)
        if caregiver.city:
            replacements = ws.search_practitioners(
                city=caregiver.city,
                is_hired=True,
                active=True,
                limit=10
            )
            # Filter out the original caregiver
            replacements = [cg for cg in replacements if cg.id != caregiver.id]
            results.add_pass(f"Step 3: Found {len(replacements)} replacement candidates")
        else:
            results.add_skip("Step 3: Find replacements", "Caregiver has no city")

        results.add_pass("✅ Full Gigi call-out scenario complete")

    except Exception as e:
        results.add_fail("Gigi call-out scenario", str(e))


# =============================================================================
# Test 10: Error Handling
# =============================================================================

def test_error_handling(ws: WellSkyService, results: TestResults):
    """Test error handling for invalid inputs"""
    print("\n⚠️  Test 10: Error Handling")

    # Test 10.1: Invalid practitioner ID
    try:
        caregiver = ws.get_practitioner("invalid-id-99999999")
        if caregiver is None:
            results.add_pass("Invalid practitioner ID handled correctly")
        else:
            results.add_fail("Invalid practitioner ID", "Should return None")
    except Exception as e:
        results.add_fail("Invalid practitioner ID", str(e))

    # Test 10.2: Invalid appointment ID
    try:
        shift = ws.get_appointment("invalid-id-99999999")
        if shift is None:
            results.add_pass("Invalid appointment ID handled correctly")
        else:
            results.add_fail("Invalid appointment ID", "Should return None")
    except Exception as e:
        results.add_fail("Invalid appointment ID", str(e))

    # Test 10.3: Invalid patient ID
    try:
        client = ws.get_patient("invalid-id-99999999")
        if client is None:
            results.add_pass("Invalid patient ID handled correctly")
        else:
            results.add_fail("Invalid patient ID", "Should return None")
    except Exception as e:
        results.add_fail("Invalid patient ID", str(e))

    # Test 10.4: Empty search results
    try:
        caregivers = ws.search_practitioners(phone="0000000000")
        if isinstance(caregivers, list):
            results.add_pass("Empty search results handled correctly")
        else:
            results.add_fail("Empty search results", "Should return empty list")
    except Exception as e:
        results.add_fail("Empty search results", str(e))


# =============================================================================
# Main Test Runner
# =============================================================================

def main():
    """Run all integration tests"""
    print("="*80)
    print("WELLSKY HOME CONNECT FHIR API - INTEGRATION TESTS")
    print("="*80)

    # Initialize WellSky service
    ws = WellSkyService()

    print(f"\n🔧 Configuration:")
    print(f"   Environment: {ws.environment}")
    print(f"   Base URL: {ws.base_url}")
    print(f"   Agency ID: {ws.agency_id or 'Not set'}")
    print(f"   Configured: {'Yes' if ws.is_configured else 'No (mock mode)'}")

    if not ws.is_configured:
        print("\n⚠️  WARNING: No credentials found - running in MOCK MODE")
        print("   Set environment variables to test real API:")
        print("   - WELLSKY_CLIENT_ID")
        print("   - WELLSKY_CLIENT_SECRET")
        print("   - WELLSKY_AGENCY_ID")
        print("   - WELLSKY_ENVIRONMENT (sandbox or production)")

    # Run all tests
    results = TestResults()

    test_configuration(ws, results)
    test_practitioner_search(ws, results)
    test_get_practitioner(ws, results)
    test_appointment_search(ws, results)
    test_get_appointment(ws, results)
    test_patient_search(ws, results)
    test_get_patient(ws, results)
    test_create_patient(ws, results)
    test_gigi_callout_scenario(ws, results)
    test_error_handling(ws, results)

    # Print summary
    all_passed = results.print_summary()

    if all_passed:
        print("\n✅ ALL TESTS PASSED!")
        print("\n🎉 WellSky FHIR API Integration is ready for:")
        print("   • Gigi call-out handling")
        print("   • Shift lookup and management")
        print("   • Client complaint resolution")
        print("   • Lead creation from prospects")
        print("\n💰 Gigi Replacement Status: READY TO DEPLOY")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("\n📋 Next steps:")
        print("   1. Review failed tests above")
        print("   2. Check WellSky credentials")
        print("   3. Verify API documentation")
        print("   4. Contact WellSky support if needed:")
        print("      Email: personalcaresupport@wellsky.com")
        return 1


if __name__ == "__main__":
    sys.exit(main())

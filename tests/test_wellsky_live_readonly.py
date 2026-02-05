#!/usr/bin/env python3
"""
WellSky Live API - READ-ONLY Test Suite
========================================
Tests the live WellSky (ClearCare) Connect API with READ-ONLY operations.

CRITICAL: This script ONLY performs GET requests and POST _search requests.
          It NEVER creates, updates, or deletes any data in production.

Usage:
    export $(grep -v '^#' ~/.gigi-env | grep '=' | xargs)
    python3 tests/test_wellsky_live_readonly.py
"""

import os
import sys
import json
import requests
from datetime import date, datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CLIENT_ID = os.environ.get("WELLSKY_CLIENT_ID", "bFgTVuBv21g2K2IXbm8LzfXOYLnR9UbS")
CLIENT_SECRET = os.environ.get("WELLSKY_CLIENT_SECRET", "Do06wgoZuV7ni4zO")
TOKEN_URL = "https://connect.clearcareonline.com/oauth/accesstoken"
BASE_URL = "https://connect.clearcareonline.com/v1"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def separator(char="=", width=80):
    print(char * width)


def report(test_num, endpoint, status_code, record_count, passed, detail=""):
    """Print a single test result line."""
    tag = "PASS" if passed else "FAIL"
    print(f"  [{tag}]  Test {test_num}: {endpoint}")
    print(f"         HTTP {status_code} | Records: {record_count}")
    if detail:
        print(f"         Detail: {detail}")
    return passed


def extract_fhir_name(resource):
    """Extract display name from a FHIR resource (patient, practitioner, etc.)."""
    names = resource.get("name", [])
    if isinstance(names, list) and len(names) > 0:
        name_obj = names[0]
        # Prefer the 'text' field which is pre-formatted
        if name_obj.get("text"):
            return name_obj["text"]
        given = name_obj.get("given", [""])
        family = name_obj.get("family", "")
        first = given[0] if given else ""
        return f"{first} {family}".strip()
    return ""


def get_fhir_entries(data):
    """Extract the list of resource entries from a FHIR Bundle response."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "entry" in data:
            return data["entry"]
        if "data" in data and isinstance(data["data"], list):
            return data["data"]
        if "results" in data and isinstance(data["results"], list):
            return data["results"]
    return []


def get_resource(entry):
    """Unwrap a FHIR bundle entry to get the resource dict."""
    if isinstance(entry, dict) and "resource" in entry:
        return entry["resource"]
    return entry


def count_records(data):
    """Extract a record count from the API response."""
    entries = get_fhir_entries(data)
    if entries:
        return len(entries)
    if isinstance(data, dict):
        if "totalRecords" in data:
            return data["totalRecords"]
        if "total" in data:
            return data["total"]
        if "id" in data:
            return 1
    return 0


# ---------------------------------------------------------------------------
# Step 0: Obtain OAuth token
# ---------------------------------------------------------------------------

def get_token() -> str:
    """Obtain an OAuth2 access token using client_credentials grant."""
    print("\n--- Step 0: OAuth Token Acquisition ---")
    print(f"  Token URL : {TOKEN_URL}")
    print(f"  Client ID : {CLIENT_ID[:8]}...{CLIENT_ID[-4:]}")

    resp = requests.post(
        TOKEN_URL,
        json={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
        headers={"Content-Type": "application/json"},
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"  FATAL: Token request failed with HTTP {resp.status_code}")
        print(f"  Response: {resp.text[:500]}")
        sys.exit(1)

    data = resp.json()
    token = data.get("access_token")
    expires_in = data.get("expires_in", "?")
    print(f"  Token obtained successfully (expires in {expires_in}s)")
    return token


def auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Individual tests
# ---------------------------------------------------------------------------

def test_1_patient_search(token: str):
    """GET /v1/patients/ - search by last_name contains 'Sh', limit 5.
    Returns (passed, first_patient_id)."""
    endpoint = "GET /v1/patients/?last_name:contains=Sh&_count=5"
    url = f"{BASE_URL}/patients/"
    params = {"last_name:contains": "Sh", "_count": 5}

    first_patient_id = None
    try:
        resp = requests.get(url, headers=auth_headers(token), params=params, timeout=30)
        data = resp.json() if resp.status_code == 200 else {}
        n = count_records(data)
        passed = resp.status_code == 200 and n > 0
        detail = ""
        if resp.status_code == 200 and n > 0:
            entries = get_fhir_entries(data)
            resource = get_resource(entries[0])
            first_patient_id = str(resource.get("id", ""))
            name = extract_fhir_name(resource)
            detail = f"Sample: {name} (id={first_patient_id})"
        elif resp.status_code != 200:
            detail = resp.text[:200]
        p = report(1, endpoint, resp.status_code, n, passed, detail)
        return p, first_patient_id
    except Exception as e:
        p = report(1, endpoint, "ERR", 0, False, str(e)[:200])
        return p, None


def test_2_practitioner_search(token: str):
    """POST /v1/practitioners/_search/ - active hired practitioners, limit 5.
    Returns (passed, first_caregiver_id)."""
    endpoint = "POST /v1/practitioners/_search/ (active, hired, _count=5)"
    url = f"{BASE_URL}/practitioners/_search/"
    body = {"active": "true", "is_hired": "true"}
    params = {"_count": 5}

    first_cg_id = None
    try:
        resp = requests.post(url, headers=auth_headers(token), json=body, params=params, timeout=30)
        data = resp.json() if resp.status_code == 200 else {}
        n = count_records(data)
        passed = resp.status_code == 200 and n > 0
        detail = ""
        if resp.status_code == 200 and n > 0:
            entries = get_fhir_entries(data)
            resource = get_resource(entries[0])
            first_cg_id = str(resource.get("id", ""))
            name = extract_fhir_name(resource)
            detail = f"First caregiver: {name} (id={first_cg_id})"
        elif resp.status_code != 200:
            detail = resp.text[:200]
        p = report(2, endpoint, resp.status_code, n, passed, detail)
        return p, first_cg_id
    except Exception as e:
        report(2, endpoint, "ERR", 0, False, str(e)[:200])
        return False, None


def test_3_appointments(token: str, caregiver_id: str) -> bool:
    """GET /v1/appointment/ - shifts for a caregiver this week."""
    today_str = date.today().strftime("%Y%m%d")
    endpoint = f"GET /v1/appointment/?caregiverId={caregiver_id}&startDate={today_str}&additionalDays=6"
    url = f"{BASE_URL}/appointment/"
    params = {
        "caregiverId": caregiver_id,
        "startDate": today_str,
        "additionalDays": 6,
    }

    try:
        resp = requests.get(url, headers=auth_headers(token), params=params, timeout=30)
        data = resp.json() if resp.status_code == 200 else {}
        n = count_records(data)
        # A 200 with 0 records is acceptable (caregiver may have no shifts this week)
        passed = resp.status_code == 200
        detail = f"{n} shift(s) found for caregiver {caregiver_id} this week"
        if resp.status_code != 200:
            detail = resp.text[:200]
        return report(3, endpoint, resp.status_code, n, passed, detail)
    except Exception as e:
        return report(3, endpoint, "ERR", 0, False, str(e)[:200])


def test_4_related_person(token: str, patient_id: str) -> bool:
    """GET /v1/relatedperson/{patient_id}/ - family/contacts for a patient."""
    endpoint = f"GET /v1/relatedperson/{patient_id}/"
    url = f"{BASE_URL}/relatedperson/{patient_id}/"

    try:
        resp = requests.get(url, headers=auth_headers(token), timeout=30)
        data = resp.json() if resp.status_code == 200 else {}
        n = count_records(data)
        # 200 with 0 is fine (patient may have no related persons listed)
        passed = resp.status_code == 200
        detail = f"{n} related person(s) for patient {patient_id}"
        if resp.status_code == 200 and n > 0:
            entries = get_fhir_entries(data)
            resource = get_resource(entries[0])
            name = extract_fhir_name(resource)
            rel_code = ""
            rel = resource.get("relationship", {})
            codings = rel.get("coding", [])
            if codings:
                rel_code = codings[0].get("code", "")
            detail += f" | First: {name} (relationship: {rel_code})"
        elif resp.status_code != 200:
            detail = f"HTTP {resp.status_code}: {resp.text[:200]}"
        return report(4, endpoint, resp.status_code, n, passed, detail)
    except Exception as e:
        return report(4, endpoint, "ERR", 0, False, str(e)[:200])


def test_5_subscriptions(token: str) -> bool:
    """GET /v1/subscriptions/ - list webhook subscriptions."""
    endpoint = "GET /v1/subscriptions/"
    url = f"{BASE_URL}/subscriptions/"

    try:
        resp = requests.get(url, headers=auth_headers(token), timeout=30)
        data = resp.json() if resp.status_code == 200 else {}
        n = count_records(data)
        passed = resp.status_code == 200
        detail = f"{n} subscription(s) found"
        if resp.status_code != 200:
            detail = f"HTTP {resp.status_code}: {resp.text[:200]}"
        return report(5, endpoint, resp.status_code, n, passed, detail)
    except Exception as e:
        return report(5, endpoint, "ERR", 0, False, str(e)[:200])


def test_6_profile_tags(token: str) -> bool:
    """GET /v1/profileTags/ - list tags (ok if 404 or 405)."""
    endpoint = "GET /v1/profileTags/"
    url = f"{BASE_URL}/profileTags/"

    try:
        resp = requests.get(url, headers=auth_headers(token), timeout=30)
        data = resp.json() if resp.status_code == 200 else {}
        n = count_records(data)
        # 404 or 405 is acceptable for this optional endpoint
        passed = resp.status_code in (200, 404, 405)
        if resp.status_code == 404:
            detail = "Endpoint not available (404) -- acceptable"
        elif resp.status_code == 405:
            detail = "Method not allowed (405) -- GET not supported on this endpoint -- acceptable"
        elif resp.status_code == 200:
            detail = f"{n} tag(s) found"
        else:
            detail = f"HTTP {resp.status_code}: {resp.text[:200]}"
        return report(6, endpoint, resp.status_code, n, passed, detail)
    except Exception as e:
        return report(6, endpoint, "ERR", 0, False, str(e)[:200])


def test_7_locations(token: str) -> bool:
    """GET /v1/locations/ - list locations."""
    endpoint = "GET /v1/locations/"
    url = f"{BASE_URL}/locations/"

    try:
        resp = requests.get(url, headers=auth_headers(token), timeout=30)
        data = resp.json() if resp.status_code == 200 else {}
        n = count_records(data)
        # 404 is acceptable if endpoint doesn't exist
        passed = resp.status_code in (200, 404)
        if resp.status_code == 404:
            detail = "Endpoint not available (404) -- acceptable"
        elif resp.status_code == 200:
            entries = get_fhir_entries(data)
            names = []
            for entry in entries:
                r = get_resource(entry)
                loc_name = r.get("name", "")
                if loc_name:
                    names.append(loc_name.strip())
            detail = f"{n} location(s): {', '.join(names)}" if names else f"{n} location(s) found"
        else:
            detail = f"HTTP {resp.status_code}: {resp.text[:200]}"
        return report(7, endpoint, resp.status_code, n, passed, detail)
    except Exception as e:
        return report(7, endpoint, "ERR", 0, False, str(e)[:200])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    separator()
    print("  WELLSKY LIVE API -- READ-ONLY TEST SUITE")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Base URL: {BASE_URL}")
    print("  Mode: READ-ONLY (no create/update/delete)")
    separator()

    # --- Authenticate ---
    token = get_token()

    results = []

    # --- Test 1: Patient search ---
    print("\n--- Test 1: Patient Search (last_name contains 'Sh') ---")
    p1, first_patient_id = test_1_patient_search(token)
    results.append(p1)

    # --- Test 2: Practitioner search ---
    print("\n--- Test 2: Practitioner Search (active, hired) ---")
    p2, first_cg_id = test_2_practitioner_search(token)
    results.append(p2)

    # --- Test 3: Appointments ---
    print("\n--- Test 3: Appointments for Caregiver ---")
    if first_cg_id:
        p3 = test_3_appointments(token, first_cg_id)
    else:
        p3 = report(3, "GET /v1/appointment/", "SKIP", 0, False, "No caregiver ID from test 2")
    results.append(p3)

    # --- Test 4: Related person ---
    print("\n--- Test 4: Related Person (Family) for Patient ---")
    if first_patient_id:
        p4 = test_4_related_person(token, first_patient_id)
    else:
        p4 = report(4, "GET /v1/relatedperson/{id}/", "SKIP", 0, False, "No patient ID from test 1")
    results.append(p4)

    # --- Test 5: Subscriptions ---
    print("\n--- Test 5: Subscriptions ---")
    p5 = test_5_subscriptions(token)
    results.append(p5)

    # --- Test 6: Profile Tags ---
    print("\n--- Test 6: Profile Tags ---")
    p6 = test_6_profile_tags(token)
    results.append(p6)

    # --- Test 7: Locations ---
    print("\n--- Test 7: Locations ---")
    p7 = test_7_locations(token)
    results.append(p7)

    # --- Summary ---
    separator()
    total = len(results)
    passed_count = sum(1 for r in results if r)
    failed_count = total - passed_count
    print(f"\n  SUMMARY: {passed_count}/{total} tests passed, {failed_count} failed")
    if failed_count == 0:
        print("  All read-only tests passed.")
    else:
        print("  Some tests failed. Review details above.")
    separator()
    print()

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

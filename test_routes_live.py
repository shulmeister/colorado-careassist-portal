#!/usr/bin/env python3
"""
Live route testing for the unified portal.
Tests all specified routes against localhost:8765.
"""
import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8765"

ROUTES = [
    "/health",
    "/operations",
    "/gigi/dashboard",
    "/sales/health",
    "/sales",
    "/recruiting",
    "/gigi-agent/health",
    "/api/wellsky/status",
    "/api/wellsky/clients",
    "/api/wellsky/caregivers",
    "/api/operations/summary",
    "/vouchers",
    "/client-satisfaction",
    "/go/sales",
    "/activity-tracker",
]

def test_routes():
    """Test all routes and return results."""
    results = []

    for route in ROUTES:
        url = f"{BASE_URL}{route}"
        try:
            resp = requests.get(url, timeout=10, allow_redirects=False)
            status = resp.status_code
            # Consider 200, 302, 303, 307, 308 as success
            ok = status in [200, 302, 303, 307, 308]
            results.append({
                "route": route,
                "status": status,
                "ok": ok,
                "note": "redirect" if status in [302, 303, 307, 308] else ""
            })
        except requests.exceptions.ConnectionError:
            results.append({
                "route": route,
                "status": "CONNECTION_ERROR",
                "ok": False,
                "note": "Service not reachable"
            })
        except requests.exceptions.Timeout:
            results.append({
                "route": route,
                "status": "TIMEOUT",
                "ok": False,
                "note": "Request timed out"
            })
        except Exception as e:
            results.append({
                "route": route,
                "status": "ERROR",
                "ok": False,
                "note": str(e)
            })

    return results

def main():
    print(f"\n=== Route Test: {datetime.now().isoformat()} ===")
    print(f"Base URL: {BASE_URL}\n")

    results = test_routes()

    passed = sum(1 for r in results if r["ok"])
    failed = len(results) - passed

    print(f"{'Route':<35} {'Status':<20} {'Result':<10}")
    print("-" * 65)

    for r in results:
        status_str = str(r["status"])
        if r["note"]:
            status_str += f" ({r['note']})"
        result = "PASS" if r["ok"] else "FAIL"
        print(f"{r['route']:<35} {status_str:<20} {result:<10}")

    print("-" * 65)
    print(f"Total: {len(results)} | Passed: {passed} | Failed: {failed}")
    print()

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    exit(main())

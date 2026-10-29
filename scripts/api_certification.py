#!/usr/bin/env python3

"""
FAIA API GOLD MASTER CERTIFICATION SUITE
Version: v1.0.0

Validates:
- /health
- /version
- /schema
- /search
- /provider/{id}
- /repository/{id}
- error handling
"""

import requests
import json
import datetime
import sys

BASE_URL = "http://127.0.0.1:8000"

LOG_FILE = (
    f"api_certification_"
    f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)


def write_log(text):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def run_test(name, method, endpoint, expected_status=200, payload=None):

    try:

        if method == "GET":
            response = requests.get(
                f"{BASE_URL}{endpoint}",
                timeout=10
            )

        elif method == "POST":
            response = requests.post(
                f"{BASE_URL}{endpoint}",
                json=payload,
                timeout=10
            )

        else:
            raise ValueError("Unsupported HTTP method")

        passed = response.status_code == expected_status

        write_log("=" * 80)
        write_log(f"TEST: {name}")
        write_log("=" * 80)

        write_log(f"REQUEST: {method} {endpoint}")
        write_log(f"EXPECTED STATUS: {expected_status}")
        write_log(f"ACTUAL STATUS: {response.status_code}")

        try:
            write_log(
                json.dumps(
                    response.json(),
                    indent=2
                )
            )
        except Exception:
            write_log(response.text)

        return passed

    except Exception as exc:

        write_log("=" * 80)
        write_log(f"TEST: {name}")
        write_log("=" * 80)
        write_log(f"EXCEPTION: {exc}")

        return False


def main():

    print("\n=== FAIA API GOLD MASTER CERTIFICATION ===\n")

    tests = [

        (
            "01 - Health Endpoint",
            "GET",
            "/health",
            200,
            None
        ),

        (
            "02 - Version Endpoint",
            "GET",
            "/version",
            200,
            None
        ),

        (
            "03 - Schema Endpoint",
            "GET",
            "/schema",
            200,
            None
        ),

        (
            "04 - Repository Endpoint",
            "GET",
            "/repository/github_com_upstash_context7",
            200,
            None
        ),

        (
            "05 - Provider Endpoint",
            "GET",
            "/provider/upstash",
            200,
            None
        ),

        (
            "06 - Search Repository Query",
            "POST",
            "/search",
            200,
            {
                "query": "context7"
            }
        ),

        (
            "07 - Search Provider Query",
            "POST",
            "/search",
            200,
            {
                "query": "digital ocean"
            }
        ),

        (
            "08 - Search Capability Query",
            "POST",
            "/search",
            200,
            {
                "query": "workflow automation"
            }
        ),

        (
            "09 - No Match Query",
            "POST",
            "/search",
            200,
            {
                "query": "nonexistent_vendor_xyz"
            }
        ),

        (
            "10 - Empty Query Validation",
            "POST",
            "/search",
            400,
            {
                "query": ""
            }
        ),

        (
            "11 - Missing Repository",
            "GET",
            "/repository/not_real_repository",
            404,
            None
        ),

        (
            "12 - Missing Provider",
            "GET",
            "/provider/not_real_provider",
            404,
            None
        )
    ]

    passed = 0
    failed = 0

    write_log("=" * 80)
    write_log("FAIA API GOLD MASTER CERTIFICATION")
    write_log("=" * 80)

    for name, method, endpoint, expected, payload in tests:

        result = run_test(
            name,
            method,
            endpoint,
            expected,
            payload
        )

        if result:
            print(f"[PASS] {name}")
            passed += 1
        else:
            print(f"[FAIL] {name}")
            failed += 1

    print("\n========================================")
    print(f"PASSED : {passed}")
    print(f"FAILED : {failed}")
    print("========================================")

    write_log("")
    write_log(f"PASSED : {passed}")
    write_log(f"FAILED : {failed}")

    if failed == 0:

        print("\nFAIA_API_v1.0.2_GOLD_MASTER")
        print("STATUS: CERTIFIED")

        write_log("")
        write_log("FAIA_API_v1.0.2_GOLD_MASTER")
        write_log("STATUS: CERTIFIED")

        exit_code = 0

    else:

        print("\nSTATUS: CERTIFICATION FAILED")

        write_log("")
        write_log("STATUS: CERTIFICATION FAILED")

        exit_code = 1

    print(f"\nDetailed log: {LOG_FILE}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
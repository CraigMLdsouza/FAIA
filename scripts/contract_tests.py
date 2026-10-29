#!/usr/bin/env python3
"""
FAIA Discovery Contract Tests - v2.0.0
Adds discovery-related contract checks while preserving existing tests.
"""

import requests
import sys
import json

BASE_URL = "http://127.0.0.1:8000"


def run_discovery_contract_tests():
    payload = {"query": "context7"}
    try:
        resp = requests.post(f"{BASE_URL}/search", json=payload, timeout=10)
    except Exception as e:
        print(f"CT-ERROR: Could not reach API: {e}")
        return 1

    if resp.status_code != 200:
        print(f"CT-ERROR: /search returned status {resp.status_code}")
        return 1

    try:
        body = resp.json()
    except Exception as e:
        print(f"CT-ERROR: Response not JSON: {e}")
        return 1

    tests_passed = 0
    tests_failed = 0

    # CT-DISCOVERY-001: related_matches exists
    if "related_matches" in body:
        print("CT-DISCOVERY-001: related_matches exists [PASS]")
        tests_passed += 1
    else:
        print("CT-DISCOVERY-001: related_matches exists [FAIL]")
        tests_failed += 1

    # CT-DISCOVERY-002: related_matches is list
    if isinstance(body.get("related_matches", []), list):
        print("CT-DISCOVERY-002: related_matches is list [PASS]")
        tests_passed += 1
    else:
        print("CT-DISCOVERY-002: related_matches is list [FAIL]")
        tests_failed += 1

    # CT-DISCOVERY-003: related_matches items contain required fields
    required_fields = {"repository_id", "title", "provider", "confidence"}
    rm = body.get("related_matches", [])
    ok_items = 0
    for item in rm:
        if required_fields.issubset(set(item.keys())):
            ok_items += 1
    if ok_items == len(rm):
        print("CT-DISCOVERY-003: related_matches items contain required fields [PASS]")
        tests_passed += 1
    else:
        print("CT-DISCOVERY-003: related_matches items contain required fields [FAIL]")
        tests_failed += 1

    # CT-DISCOVERY-004: best match not duplicated in related_matches
    best_id = None
    if body.get("data") and isinstance(body.get("data"), dict):
        best_id = body["data"].get("repository_id") if body["data"].get("repository_id") else None
    # fallback to top of related repository in meta from resolver upstream
    duplication_found = False
    if best_id:
        for item in rm:
            if item.get("repository_id") == best_id:
                duplication_found = True
                break
    if not duplication_found:
        print("CT-DISCOVERY-004: best match not duplicated in related_matches [PASS]")
        tests_passed += 1
    else:
        print("CT-DISCOVERY-004: best match not duplicated in related_matches [FAIL]")
        tests_failed += 1

    # CT-DISCOVERY-005: related_matches count <= 4
    if len(rm) <= 4:
        print("CT-DISCOVERY-005: related_matches count <= 4 [PASS]")
        tests_passed += 1
    else:
        print("CT-DISCOVERY-005: related_matches count <= 4 [FAIL]")
        tests_failed += 1

    print(f"\nSUMMARY: {tests_passed} passed, {tests_failed} failed")
    return 0 if tests_failed == 0 else 1


def run_capability_ranking_regression_tests():
    """Verify that specific capability queries resolve to correct capabilities."""
    test_cases = [
        {"id": "CT-CAP-RANK-001", "query": "create workflow", "expected_capability": "CREATE_WORKFLOW"},
        {"id": "CT-CAP-RANK-002", "query": "create model", "expected_capability": "CREATE_MODEL"},
        {"id": "CT-CAP-RANK-003", "query": "read issue", "expected_capability": "READ_ISSUE"},
        {"id": "CT-CAP-RANK-004", "query": "read workflow", "expected_capability": "READ_WORKFLOW"},
        {"id": "CT-CAP-RANK-005", "query": "update workflow", "expected_capability": "UPDATE_WORKFLOW"},
        {"id": "CT-CAP-RANK-006", "query": "delete system", "expected_capability": "DELETE_SYSTEM"}
    ]

    tests_passed = 0
    tests_failed = 0

    for case in test_cases:
        query = case["query"]
        expected_cap = case["expected_capability"]
        try:
            resp = requests.post(f"{BASE_URL}/search", json={"query": query}, timeout=10)
        except Exception as e:
            print(f"{case['id']}: Could not reach API for query '{query}': {e} [FAIL]")
            tests_failed += 1
            continue

        if resp.status_code != 200:
            print(f"{case['id']}: /search returned status {resp.status_code} for query '{query}' [FAIL]")
            tests_failed += 1
            continue

        try:
            body = resp.json()
        except Exception as e:
            print(f"{case['id']}: Response not JSON for query '{query}': {e} [FAIL]")
            tests_failed += 1
            continue

        result_type = body.get("result_type")
        data = body.get("data", {})
        capability_name = data.get("capability") if isinstance(data, dict) else None

        if result_type == "CAPABILITY" and capability_name == expected_cap:
            print(f"{case['id']}: query '{query}' correctly resolved to {expected_cap} [PASS]")
            tests_passed += 1
        else:
            print(f"{case['id']}: query '{query}' returned {result_type}/{capability_name}, expected CAPABILITY/{expected_cap} [FAIL]")
            tests_failed += 1

    print(f"\nCAPABILITY RANKING REGRESSION SUMMARY: {tests_passed} passed, {tests_failed} failed")
    return 0 if tests_failed == 0 else 1


def run_capability_enumeration_contract_tests():
    """Verify that prefix-only queries still return CAPABILITY_GROUP."""
    test_cases = [
        {"id": "CT-CAP-GROUP-001", "query": "read", "expect_group": True},
        {"id": "CT-CAP-GROUP-002", "query": "create", "expect_group": True},
        {"id": "CT-CAP-GROUP-003", "query": "delete", "expect_group": True},
        {"id": "CT-CAP-GROUP-004", "query": "update", "expect_group": True}
    ]

    tests_passed = 0
    tests_failed = 0

    for case in test_cases:
        query = case["query"]
        try:
            resp = requests.post(f"{BASE_URL}/search", json={"query": query}, timeout=10)
        except Exception as e:
            print(f"{case['id']}: Could not reach API for query '{query}': {e} [FAIL]")
            tests_failed += 1
            continue

        if resp.status_code != 200:
            print(f"{case['id']}: /search returned status {resp.status_code} for query '{query}' [FAIL]")
            tests_failed += 1
            continue

        try:
            body = resp.json()
        except Exception as e:
            print(f"{case['id']}: Response not JSON for query '{query}': {e} [FAIL]")
            tests_failed += 1
            continue

        result_type = body.get("result_type")
        capabilities = body.get("data", {}).get("capabilities") if isinstance(body.get("data"), dict) else None

        if case["expect_group"]:
            if result_type == "CAPABILITY_GROUP" and isinstance(capabilities, list) and len(capabilities) > 1:
                print(f"{case['id']}: query '{query}' returned CAPABILITY_GROUP with {len(capabilities)} capabilities [PASS]")
                tests_passed += 1
            else:
                print(f"{case['id']}: query '{query}' did not return valid CAPABILITY_GROUP (got {result_type}) [FAIL]")
                tests_failed += 1

    print(f"\nCAPABILITY ENUMERATION SUMMARY: {tests_passed} passed, {tests_failed} failed")
    return 0 if tests_failed == 0 else 1


    contract_status = run_discovery_contract_tests()
    enumeration_status = run_capability_enumeration_contract_tests()
    ranking_status = run_capability_ranking_regression_tests()
    sys.exit(0 if contract_status == 0 and enumeration_status == 0 and ranking_status == 0 else 1)

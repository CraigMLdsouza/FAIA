#!/usr/bin/env python3
"""
FAIA Backend Upgrade Validation Report
========================================
Complete validation of v2.0.0, v2.1.0, and v2.1.1 upgrades

- v2.0.0: Multi-result discovery with ranked_matches and related_matches
- v2.1.0: Capability prefix enumeration with CAPABILITY_GROUP
- v2.1.1: Deterministic capability ranking for specific queries
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
REPORT = []

def test(category, name, condition, details=""):
    """Record test result"""
    status = "✓ PASS" if condition else "✗ FAIL"
    REPORT.append({"category": category, "name": name, "status": status, "details": details})
    print(f"{status}: {category} - {name}")
    if details:
        print(f"       {details}")

print("=" * 70)
print("FAIA BACKEND UPGRADE VALIDATION REPORT")
print("=" * 70)
print(f"Timestamp: {datetime.now().isoformat()}\n")

# ============================================================================
# PHASE 1: v2.0.0 - Discovery (ranked_matches, related_matches)
# ============================================================================
print("\n[PHASE 1] v2.0.0 - Multi-Result Discovery")
print("-" * 70)

try:
    resp = requests.post(f"{BASE_URL}/search", json={"query": "context7"}, timeout=5)
    data = resp.json()
    
    # Test 1: related_matches field exists
    has_related = "related_matches" in data
    test("Discovery", "related_matches field exists", has_related)
    
    # Test 2: related_matches is a list
    is_list = isinstance(data.get("related_matches"), list)
    test("Discovery", "related_matches is list", is_list)
    
    # Test 3: related_matches count <= 4
    count = len(data.get("related_matches", []))
    test("Discovery", "related_matches count <= 4", count <= 4, f"Count: {count}")
    
    # Test 4: No duplicate repository IDs
    repo_ids = [m.get("repository_id") for m in data.get("related_matches", [])]
    no_dupes = len(repo_ids) == len(set(repo_ids))
    test("Discovery", "No duplicate repositories", no_dupes)
    
    # Test 5: Required fields in related_matches
    if data.get("related_matches"):
        first_match = data["related_matches"][0]
        has_fields = all(k in first_match for k in ["repository_id", "repository_name", "confidence"])
        test("Discovery", "related_matches has required fields", has_fields)
    
except Exception as e:
    test("Discovery", "Search API call", False, str(e))

# ============================================================================
# PHASE 2: v2.1.0 - Capability Enumeration (CAPABILITY_GROUP)
# ============================================================================
print("\n[PHASE 2] v2.1.0 - Capability Prefix Enumeration")
print("-" * 70)

test_prefixes = [
    ("read", "READ", 14),
    ("create", "CREATE", 12),
    ("update", "UPDATE", 9),
    ("delete", "DELETE", 8),
]

for query, verb, expected_min in test_prefixes:
    try:
        resp = requests.post(f"{BASE_URL}/search", json={"query": query}, timeout=5)
        data = resp.json()
        
        is_capability_group = data.get("result_type") == "CAPABILITY_GROUP"
        test("Enumeration", f"'{query}' returns CAPABILITY_GROUP", is_capability_group)
        
        if is_capability_group:
            caps = data.get("data", {}).get("capabilities", [])
            count = len(caps)
            meets_minimum = count >= expected_min
            test("Enumeration", f"'{query}' has {expected_min}+ capabilities", meets_minimum, 
                 f"Found: {count}")
            
    except Exception as e:
        test("Enumeration", f"'{query}' prefix query", False, str(e))

# ============================================================================
# PHASE 3: v2.1.1 - Deterministic Capability Ranking
# ============================================================================
print("\n[PHASE 3] v2.1.1 - Deterministic Capability Ranking")
print("-" * 70)

ranking_tests = [
    ("create workflow", "CREATE_WORKFLOW"),
    ("create model", "CREATE_MODEL"),
    ("read issue", "READ_ISSUE"),
    ("read workflow", "READ_WORKFLOW"),
    ("update workflow", "UPDATE_WORKFLOW"),
    ("delete system", "DELETE_SYSTEM"),
]

for query, expected_cap in ranking_tests:
    try:
        resp = requests.post(f"{BASE_URL}/search", json={"query": query}, timeout=5)
        data = resp.json()
        
        actual_cap = data.get("data", {}).get("capability")
        matches = actual_cap == expected_cap
        test("Ranking", f"'{query}' → {expected_cap}", matches,
             f"Got: {actual_cap}")
        
    except Exception as e:
        test("Ranking", f"'{query}' capability query", False, str(e))

# ============================================================================
# BACKWARDS COMPATIBILITY: All Original Endpoints
# ============================================================================
print("\n[COMPATIBILITY] Backwards Compatibility - Original Endpoints")
print("-" * 70)

try:
    # Test /health
    resp = requests.get(f"{BASE_URL}/health", timeout=5)
    test("API", "/health endpoint", resp.status_code == 200)
    
    # Test /version
    resp = requests.get(f"{BASE_URL}/version", timeout=5)
    test("API", "/version endpoint", resp.status_code == 200)
    
    # Test /schema
    resp = requests.get(f"{BASE_URL}/schema", timeout=5)
    test("API", "/schema endpoint", resp.status_code == 200)
    
    # Test /repository/{id}
    resp = requests.get(f"{BASE_URL}/repository/github_com_heroku_heroku_mcp_server", timeout=5)
    test("API", "/repository endpoint", resp.status_code == 200)
    
    # Test /provider/{id}
    resp = requests.get(f"{BASE_URL}/provider/heroku", timeout=5)
    test("API", "/provider endpoint", resp.status_code == 200)
    
except Exception as e:
    test("API", "Endpoint availability", False, str(e))

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("VALIDATION SUMMARY")
print("=" * 70)

passed = sum(1 for r in REPORT if "PASS" in r["status"])
failed = sum(1 for r in REPORT if "FAIL" in r["status"])
total = len(REPORT)

print(f"\nTotal Tests: {total}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print(f"Success Rate: {100.0 * passed / total:.1f}%\n")

if failed == 0:
    print("✓ ALL PHASES VALIDATED SUCCESSFULLY")
    print("\nReleases Ready:")
    print("  • FAIA_DISCOVERY_BACKEND_v2.0.0")
    print("  • FAIA_CAPABILITY_ENUMERATION_v2.1.0")
    print("  • FAIA_BACKEND_CAPABILITY_RANKING_FIX_v2.1.1")
else:
    print(f"✗ {failed} TESTS FAILED - REVIEW REQUIRED")
    for r in REPORT:
        if "FAIL" in r["status"]:
            print(f"  - {r['category']}: {r['name']}")

print("\n" + "=" * 70)

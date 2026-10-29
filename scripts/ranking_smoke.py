#!/usr/bin/env python3
import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

print("Starting contract tests...", flush=True)

# Test 1: Create workflow should resolve to CREATE_WORKFLOW
print("\n=== Test: create workflow ===", flush=True)
try:
    resp = requests.post(f"{BASE_URL}/search", json={"query": "create workflow"}, timeout=5)
    print(f"Response status: {resp.status_code}", flush=True)
    data = resp.json()
    cap = data.get("data", {}).get("capability")
    print(f"Capability: {cap}", flush=True)
    assert cap == "CREATE_WORKFLOW", f"Expected CREATE_WORKFLOW, got {cap}"
    print("✓ PASS", flush=True)
except Exception as e:
    print(f"✗ FAIL: {e}", flush=True)

# Test 2: Create model
print("\n=== Test: create model ===", flush=True)
try:
    resp = requests.post(f"{BASE_URL}/search", json={"query": "create model"}, timeout=5)
    data = resp.json()
    cap = data.get("data", {}).get("capability")
    print(f"Capability: {cap}", flush=True)
    assert cap == "CREATE_MODEL", f"Expected CREATE_MODEL, got {cap}"
    print("✓ PASS", flush=True)
except Exception as e:
    print(f"✗ FAIL: {e}", flush=True)

# Test 3: Read workflow
print("\n=== Test: read workflow ===", flush=True)
try:
    resp = requests.post(f"{BASE_URL}/search", json={"query": "read workflow"}, timeout=5)
    data = resp.json()
    cap = data.get("data", {}).get("capability")
    print(f"Capability: {cap}", flush=True)
    assert cap == "READ_WORKFLOW", f"Expected READ_WORKFLOW, got {cap}"
    print("✓ PASS", flush=True)
except Exception as e:
    print(f"✗ FAIL: {e}", flush=True)

# Test 4: Read issue
print("\n=== Test: read issue ===", flush=True)
try:
    resp = requests.post(f"{BASE_URL}/search", json={"query": "read issue"}, timeout=5)
    data = resp.json()
    cap = data.get("data", {}).get("capability")
    print(f"Capability: {cap}", flush=True)
    assert cap == "READ_ISSUE", f"Expected READ_ISSUE, got {cap}"
    print("✓ PASS", flush=True)
except Exception as e:
    print(f"✗ FAIL: {e}", flush=True)

# Test 5: Update workflow
print("\n=== Test: update workflow ===", flush=True)
try:
    resp = requests.post(f"{BASE_URL}/search", json={"query": "update workflow"}, timeout=5)
    data = resp.json()
    cap = data.get("data", {}).get("capability")
    print(f"Capability: {cap}", flush=True)
    assert cap == "UPDATE_WORKFLOW", f"Expected UPDATE_WORKFLOW, got {cap}"
    print("✓ PASS", flush=True)
except Exception as e:
    print(f"✗ FAIL: {e}", flush=True)

# Test 6: Delete system
print("\n=== Test: delete system ===", flush=True)
try:
    resp = requests.post(f"{BASE_URL}/search", json={"query": "delete system"}, timeout=5)
    data = resp.json()
    cap = data.get("data", {}).get("capability")
    print(f"Capability: {cap}", flush=True)
    assert cap == "DELETE_SYSTEM", f"Expected DELETE_SYSTEM, got {cap}"
    print("✓ PASS", flush=True)
except Exception as e:
    print(f"✗ FAIL: {e}", flush=True)

print("\n=== All ranking tests completed ===", flush=True)

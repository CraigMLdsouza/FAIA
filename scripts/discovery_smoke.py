#!/usr/bin/env python3
import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

print("Testing discovery (related_matches)...", flush=True)

# Test discovery with a query that should have related_matches
resp = requests.post(f"{BASE_URL}/search", json={"query": "context7"}, timeout=5)
data = resp.json()

print(f"Result type: {data.get('result_type')}", flush=True)
print(f"Status: {data.get('status')}", flush=True)

# Check if related_matches exists
if "related_matches" in data:
    matches = data["related_matches"]
    print(f"Related matches count: {len(matches)}", flush=True)
    if matches:
        print(f"First match: {matches[0].get('repository_name')}", flush=True)
    print("✓ PASS - related_matches field exists", flush=True)
else:
    print("✗ FAIL - related_matches field missing", flush=True)

# Test capability enumeration with a prefix query
print("\nTesting capability enumeration...", flush=True)
resp = requests.post(f"{BASE_URL}/search", json={"query": "read"}, timeout=5)
data = resp.json()

print(f"Result type: {data.get('result_type')}", flush=True)
if data.get('result_type') == 'CAPABILITY_GROUP':
    caps = data.get('data', {}).get('capabilities', [])
    print(f"Capability count: {len(caps)}", flush=True)
    if len(caps) > 1:
        print(f"Sample capabilities: {[c.get('name') for c in caps[:3]]}", flush=True)
        print("✓ PASS - capability enumeration works", flush=True)
    else:
        print("✗ FAIL - not enough capabilities returned", flush=True)
else:
    print(f"✗ FAIL - Expected CAPABILITY_GROUP, got {data.get('result_type')}", flush=True)

print("\nAll tests completed", flush=True)

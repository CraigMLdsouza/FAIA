#!/usr/bin/env python3
from repository_resolver import FAIARepositoryResolver
import json

r = FAIARepositoryResolver()
res = r.resolve('create workflow', top_k=20)

print("=== RESOLVER OUTPUT DEBUG ===")
print(f"Query: {res.get('query')}")
print(f"Intent: {res.get('query_intent')}")
print(f"Status: {res.get('retrieval_status')}")
print(f"\nMatched repositories:")
for i, repo in enumerate(res.get('repositories', [])[:5]):
    print(f"{i+1}. {repo.get('repository_name')} - caps: {repo.get('matched_capabilities', [])}")

print(f"\nCapability Structure Index (sample):")
sample_keys = list(r.capability_structure_index.keys())[:5]
for key in sample_keys:
    entry = r.capability_structure_index[key]
    print(f"  {entry['capability_id']}: verb={entry['verb']}, resource={entry['resource']}")

print(f"\nQuery structure:")
query_struct = r._parse_query_structure('create workflow')
print(f"  verb={query_struct['verb']}, resource={query_struct['resource']}")

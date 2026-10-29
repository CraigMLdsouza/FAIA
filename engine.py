#!/usr/bin/env python3
"""
FAIA Discovery Engine - Version v1.3.1_certified_freeze
[PRODUCTION PLATFORM FREEZE - RELEASE v1.3 COMPLIANT]
Orchestrates capability-to-provider mappings and scales compound ranking vectors deterministically.

Future Roadmap (Deferred Tasks):
  - ENG-034: Logarithmic or Softmax Scaling over Multi-Capability Queries
  - ENG-035: Provider Score Explainability Expansion (Raw vs Normalized Weightings)
  - ENG-036: Discovery Analytics Logging Layer (engine_analytics.json)
  - ENG-037: Repository Resolution Layer (Capability -> Provider -> Repository) [Next Major Milestone]
  - ENG-038: Repository Ranking Engine (Popularity + Maintenance Activity Signals)
  - ENG-039: Tool Resolution Layer (Capability -> Provider -> Repository -> Tool)
  - ENG-040: Alternative Provider Recommendation Engine
"""

import os
import sys
import json
import time
import argparse
from collections import defaultdict
from typing import List, Dict, Any, Optional, Set, Tuple

# Safe import validation wrapper
try:
    from search_engine import CapabilitySearchEngine
except ImportError:
    raise ImportError(
        "[MANDATORY DEPENDENCY MISSING] search_engine.py could not be resolved. "
        "Ensure both core execution scripts are placed within the same directory."
    )

# Production System Identity Markers
SEARCH_ENGINE_VERSION = "v1.8.1_production_freeze"
SEARCH_ENGINE_STATUS = "FAIA_SEARCH_ENGINE_v1.8.1_CLEANED"
SEARCH_ENGINE_CHANGE_CONTROL = True


# =====================================================================
# Core Orchestration Architecture
# =====================================================================

class FAIAOrchestrationEngine:
    def __init__(self, target_dir: str = "catalog_output"):
        configured_dir = os.path.expanduser(target_dir)
        self.target_dir = (
            configured_dir
            if os.path.isabs(configured_dir)
            else os.path.join(os.path.dirname(os.path.abspath(__file__)), configured_dir)
        )
        
        # Memory-Cached Storage Pools
        self.capabilities: Dict[str, Any] = {}
        self.provider_matrix: Dict[str, Any] = {}
        self.provider_profiles: Dict[str, Any] = {}
        self.provider_rankings: Dict[str, Any] = {}
        
        # Schema Adapter Canonical Memory Cache (ENG-032)
        self.canonical_capabilities: Dict[str, Dict[str, Any]] = {}
        
        # O(1) Index Lookup Mappings
        self.provider_ranking_index: Dict[str, Dict[str, Any]] = {}
        
        # Search Engine Subsystem Reference
        self.search_core: Optional[CapabilitySearchEngine] = None
        
        # Bootstrap and normalize target fields immediately
        self._initialize_system_layers()

    def _refresh_state_pools(self) -> None:
        """Flushes cache configurations to guarantee deterministic memory maps."""
        self.capabilities.clear()
        self.provider_matrix.clear()
        self.provider_profiles.clear()
        self.provider_rankings.clear()
        self.provider_ranking_index.clear()
        self.canonical_capabilities.clear()

    def _initialize_system_layers(self) -> None:
        """Hydrates artifacts from target disk directory paths with fail-fast guards."""
        self._refresh_state_pools()
        
        mandatory_artifacts = {
            "capabilities.json": "capabilities",
            "capability_provider_matrix.json": "provider_matrix",
            "provider_profiles.json": "provider_profiles",
            "provider_rankings.json": "provider_rankings"
        }

        for filename, attr_bucket in mandatory_artifacts.items():
            filepath = os.path.join(self.target_dir, filename)
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"[FAIL-FAST CRITICAL] Missing mandatory file system entity: '{filepath}'")
            
            with open(filepath, "r", encoding="utf-8") as fs:
                setattr(self, attr_bucket, json.load(fs))

        if not self.capabilities or not self.provider_profiles or not self.provider_matrix:
            raise ValueError("[FAIL-FAST VALIDATION FAILED] Hydrated storage datasets must not be empty.")

        # Schema Adapter normalization pass mapping keys dynamically (ENG-032)
        for cap_id, record in self.capabilities.items():
            self.canonical_capabilities[cap_id] = {
                "capability_id": cap_id,
                "canonical_name": record.get("capability_name", record.get("name", str(cap_id))),
                "canonical_effect": record.get("effect", record.get("action", "")),
                "canonical_resource": record.get("primary_resource", record.get("resource", "")),
                "canonical_domain": record.get("capability_domain", record.get("domain", "UNKNOWN_DOMAIN")),
                "canonical_class": record.get("capability_class", record.get("class", "UNKNOWN_CLASS")),
                "canonical_group": record.get("capability_group", record.get("group", ""))
            }

        # Min-max normalization pass over provider scores
        global_rankings_list = self.provider_rankings.get("global_provider_rankings", [])
        scores = [float(x.get("score", 0.0)) for x in global_rankings_list if "score" in x]
        min_score = min(scores) if scores else 0.0
        max_score = max(scores) if scores else 1.0
        score_range = max_score - min_score if (max_score - min_score) > 0 else 1.0

        for item in global_rankings_list:
            p_id = item.get("provider_id")
            if not p_id:
                continue
            
            raw_score = float(item.get("score", 0.0))
            normalized_score = (raw_score - min_score) / score_range
            
            indexed_record = dict(item)
            indexed_record["normalized_score"] = round(normalized_score, 4)
            self.provider_ranking_index[p_id.lower()] = indexed_record

        # Synchronize core semantic retrieval structures
        self.search_core = CapabilitySearchEngine(target_dir=self.target_dir)

    def discover(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """
        Capability Discovery API Pipeline
        Normalizes composite authority vectors and maps trace parameters deterministically.
        """
        search_bundle = self.search_core.search(query=query, top_k=top_k)
        
        retrieval_status = search_bundle.get("retrieval_status", "NO_MATCHES_FOUND")
        detected_providers = search_bundle.get("detected_providers", [])
        query_intent = search_bundle.get("query_intent", "BROAD_SEARCH")
        
        # O(1) Constraint verification set cache
        detected_provider_set = {p.lower() for p in detected_providers if p}
        
        output_caps_list = []
        provider_evidence_map = defaultdict(set)
        matched_capability_ids = set()

        # Intermediate tracking arrays for cumulative score calculation strategies (ENG-033)
        provider_cumulative_scores = defaultdict(float)
        provider_breakdown_aggregates = defaultdict(lambda: {"search_confidence": 0.0, "provider_rank": 0.0, "capability_coverage": 0.0, "ecosystem_share": 0.0})

        for search_hit in search_bundle.get("capabilities", []):
            cap_id = search_hit["capability_id"]
            confidence = search_hit["confidence"]
            matched_capability_ids.add(cap_id)
            
            # Safe resource pull executing via the Adapter layer cache maps (ENG-032)
            cap_adapter = self.canonical_capabilities.get(cap_id, {})
            
            output_caps_list.append({
                "capability_id": cap_id,
                "confidence": confidence,
                "domain": cap_adapter.get("canonical_domain", "UNKNOWN_DOMAIN"),
                "class": cap_adapter.get("canonical_class", "UNKNOWN_CLASS")
            })

            matrix_entry = self.provider_matrix.get(cap_id, {})
            provider_candidates = matrix_entry.get("providers") or list(matrix_entry.get("provider_tools", {}).keys())

            for p_id in provider_candidates:
                p_key = p_id.lower()
                profile = self.provider_profiles.get(p_key)
                if not profile:
                    continue

                if detected_provider_set and p_key not in detected_provider_set:
                    continue

                provider_evidence_map[p_key].add(cap_id)

                # Fetch normalized performance metric scalar markers
                leaderboard_entry = self.provider_ranking_index.get(p_key, {"normalized_score": 0.0})
                
                # 4-Tier Normalized Scoring Pass
                search_confidence_component = (confidence / 100.0) * 0.50
                provider_rank_component = leaderboard_entry.get("normalized_score", 0.0) * 0.25
                capability_coverage_component = profile.get("capability_coverage", 0.0) * 0.15
                ecosystem_share_component = profile.get("ecosystem_share", 0.0) * 0.10

                composite_index_value = (
                    search_confidence_component + 
                    provider_rank_component + 
                    capability_coverage_component + 
                    ecosystem_share_component
                )
                composite_score_pct = composite_index_value * 100.0

                # Execute Additive Weighted Sum Aggregation across multi-capability loops (ENG-033)
                provider_cumulative_scores[p_key] += composite_score_pct
                
                provider_breakdown_aggregates[p_key]["search_confidence"] += search_confidence_component * 100.0
                provider_breakdown_aggregates[p_key]["provider_rank"] += provider_rank_component * 100.0
                provider_breakdown_aggregates[p_key]["capability_coverage"] += capability_coverage_component * 100.0
                provider_breakdown_aggregates[p_key]["ecosystem_share"] += ecosystem_share_component * 100.0

        # Format deduplicated final response array signatures
        final_sorted_providers = []
        for p_key in sorted(provider_cumulative_scores.keys()):
            profile = self.provider_profiles[p_key]
            raw_aggregated_score = provider_cumulative_scores[p_key]
            
            # Apply scale limiting ceiling cap
            final_score = round(min(100.0, raw_aggregated_score), 2)
            breakdown = {k: round(v, 2) for k, v in provider_breakdown_aggregates[p_key].items()}

            final_sorted_providers.append({
                "provider_id": p_key,
                "provider_rank": profile.get("provider_rank", 99),
                "provider_score": final_score,
                "archetype": profile.get("archetype", "GENERAL"),
                "tool_count": profile.get("tool_count", 0),
                "capability_count": profile.get("capability_count", 0),
                "ecosystem_share": profile.get("ecosystem_share", 0.0),
                "matched_capabilities": sorted(list(provider_evidence_map[p_key])),
                "ranking_breakdown": breakdown
            })

        final_sorted_providers.sort(key=lambda x: (-x["provider_score"], x["provider_id"]))

        discovery_evidence = {
            "detected_providers": sorted(list(detected_providers)),
            "matched_capabilities": sorted(list(matched_capability_ids)),
            "query_intent": query_intent,
            "score_aggregation_strategy": "weighted_sum"
        }

        return {
            "query": query,
            "intent": query_intent,
            "retrieval_status": retrieval_status,
            "discovery_evidence": discovery_evidence,
            "capabilities": output_caps_list[:top_k],
            "providers": final_sorted_providers[:top_k]
        }

    def capability(self, capability_id: str) -> Optional[Dict[str, Any]]:
        """Safe metadata accessor routing through the adapter matrix pools (ENG-032)."""
        cap_key = capability_id.strip()
        if cap_key not in self.canonical_capabilities:
            cap_key = cap_key.upper()
        if cap_key not in self.canonical_capabilities:
            return None
            
        cap = self.canonical_capabilities[cap_key]
        
        siblings = set()
        for c_id, c_data in self.canonical_capabilities.items():
            if c_id == cap_key:
                continue
            if c_data.get("canonical_group") == cap.get("capability_group") or \
               c_data.get("canonical_resource") == cap.get("canonical_resource"):
                siblings.add(c_id)
                
        matrix_entry = self.provider_matrix.get(cap_key, {})
        providers = matrix_entry.get("providers") or list((matrix_entry.get("provider_tools") or {}).keys())
        providers = sorted(list(set(providers)))
        
        provider_list = []
        for p_id in providers:
            profile = self.provider_profiles.get(p_id.lower())
            if profile:
                provider_list.append({
                    "provider_id": p_id.lower(),
                    "archetype": profile.get("archetype", "GENERAL"),
                    "provider_rank": profile.get("provider_rank", 99)
                })
                
        return {
            "capability_id": cap_key,
            "name": cap.get("canonical_name"),
            "effect": cap.get("canonical_effect"),
            "resource": cap.get("canonical_resource"),
            "domain": cap.get("canonical_domain"),
            "class": cap.get("canonical_class"),
            "providers": sorted(provider_list, key=lambda x: x["provider_rank"]),
            "related_capabilities": sorted(list(siblings))
        }

    def provider(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Queries profiles directly, bypassing retrieval layers entirely."""
        p_key = provider_id.strip().lower()
        profile = self.provider_profiles.get(p_key)
        
        if not profile:
            for k, v in self.provider_profiles.items():
                if k.lower() == p_key:
                    profile = v
                    p_key = k.lower()
                    break
                    
        if not profile:
            return None
            
        return {
            "provider_profile": profile,
            "capabilities": profile.get("capabilities_manifest", []),
            "repositories": profile.get("repositories", []),
            "domains": profile.get("covered_domains", []),
            "tool_count": profile.get("tool_count", 0)
        }


# =====================================================================
# CLI Orchestration & Automated Validation Harness
# =====================================================================

def run_engine_regression_suite(engine: FAIAOrchestrationEngine) -> int:
    """Automated Engine Test Suite validating cross-domain query targets."""
    print("=== FAIA DISCOVERY ENGINE REGRESSION SUITE ===", file=sys.stderr)
    test_cases = [
        {"query": "issue", "expected_status": "SUCCESS"},
        {"query": "incident tickets", "expected_status": "SUCCESS"},
        {"query": "github issues", "expected_status": "SUCCESS"},
        {"query": "query", "expected_status": "SUCCESS"},
        {"query": "queries", "expected_status": "SUCCESS"},
        {"query": "search documentation", "expected_status": "SUCCESS"},
        {"query": "workflow", "expected_status": "SUCCESS"},
        {"query": "upstash document", "expected_status": "SUCCESS"},
        {"query": "upstash issue", "expected_status": "NO_PROVIDER_SUPPORT"}
    ]
    
    failed_cases = 0
    for idx, case in enumerate(test_cases, 1):
        q_str = case["query"]
        expected = case["expected_status"]
        try:
            res = engine.discover(query=q_str, top_k=10)
            actual = res.get("retrieval_status")
            
            if actual != expected:
                print(f" -> Case {idx} '{q_str}': Status Mismatch! Expected {expected}, got {actual} [FAILED]", file=sys.stderr)
                failed_cases += 1
                continue
                
            if actual == "SUCCESS":
                if not res.get("capabilities") or not res.get("providers"):
                    print(f" -> Case {idx} '{q_str}': Missing payload arrays! [FAILED]", file=sys.stderr)
                    failed_cases += 1
                    continue
                if "ranking_breakdown" not in res["providers"][0]:
                    print(f" -> Case {idx} '{q_str}': Missing score breakdown sub-fields! [FAILED]", file=sys.stderr)
                    failed_cases += 1
                    continue
                    
            print(f" -> Case {idx}: Query '{q_str}' -> Status: {actual} [PASSED]", file=sys.stderr)
            
        except Exception as err:
            print(f" -> Case {idx} '{q_str}': Threw Exception: {err} [FAILED]", file=sys.stderr)
            failed_cases += 1

    print(f"\n=== ENGINE SUMMARY: {len(test_cases) - failed_cases}/{len(test_cases)} VERIFIED COMPLIANT ===\n", file=sys.stderr)
    return 1 if failed_cases > 0 else 0


def main():
    parser = argparse.ArgumentParser(description="FAIA Discovery Orchestration Engine Layer Client.")
    parser.add_argument("query", type=str, nargs="?", default=None, help="Discovery search string context parameter.")
    parser.add_argument("--top-k", type=int, default=10, help="Limiting count boundaries factor threshold.")
    parser.add_argument("--run-tests", action="store_true", help="Executes structural system validation suites.")
    args = parser.parse_args()

    try:
        orchestrator = FAIAOrchestrationEngine()
        
        if args.run_tests:
            exit_code = run_engine_regression_suite(orchestrator)
            sys.exit(exit_code)

        if args.query is None:
            parser.print_help()
            sys.exit(1)

        t_start = time.time()
        discovery_payload = orchestrator.discover(query=args.query, top_k=args.top_k)
        latency_ms = round((time.time() - t_start) * 1000, 2)
        
        print(json.dumps(discovery_payload, indent=2, sort_keys=True))
        
        top_cap = discovery_payload["capabilities"][0]["capability_id"] if discovery_payload["capabilities"] else "NONE"
        top_prov = discovery_payload["providers"][0]["provider_id"] if discovery_payload["providers"] else "NONE"
        
        print("\n=== FAIA DISCOVERY ENGINE METRICS ===", file=sys.stderr)
        print(f" -> Target Query Expression   : '{args.query}'", file=sys.stderr)
        print(f" -> Intent Track Resolved     : {discovery_payload['intent']}", file=sys.stderr)
        print(f" -> System Retrieval Status   : {discovery_payload['retrieval_status']}", file=sys.stderr)
        print(f" -> Matched Capability Count  : {len(discovery_payload['capabilities'])} records", file=sys.stderr)
        print(f" -> Deduplicated Provider Count: {len(discovery_payload['providers'])} targets", file=sys.stderr)
        print(f" -> Top Dominant Capability   : {top_cap}", file=sys.stderr)
        print(f" -> Top Benchmark Provider    : {top_prov}", file=sys.stderr)
        print(f" -> Processing Loop Latency   : {latency_ms} ms", file=sys.stderr)

    except Exception as exc:
        print(f"Orchestration Aborted: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
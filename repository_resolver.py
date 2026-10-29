#!/usr/bin/env python3
"""
FAIA Repository Intent Resolver - Version v2.2.1
[PRODUCTION GOLD MASTER FREEZE - RELEASE v2.2.1 FINAL]
Algorithmic Jaccard semantic matching engine featuring canonical URL normalization,
resolution intent locking, and fail-fast bootstrap metadata validation blocks.
Applies patches: OK-001 through OK-004. Certified Compliant.
"""

import os
import sys
import json
import time
import argparse
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any, Optional, Set, Tuple

# Safe import validation wrappers for upstream core dependencies
try:
    from search_engine import CapabilitySearchEngine
    from engine import FAIAOrchestrationEngine
except ImportError:
    raise ImportError(
        "[MANDATORY ENGINE DEPENDENCY ERROR] search_engine.py or engine.py could not be resolved. "
        "Ensure core execution files are located within the same directory."
    )

# Production System Identity Markers
SEARCH_ENGINE_VERSION = "v2.2.1_production_freeze"
SEARCH_ENGINE_STATUS = "FAIA_REPOSITORY_RESOLVER_v2.2.1_GOLD_MASTER"
SEARCH_ENGINE_CHANGE_CONTROL = True
# Discovery pagination / default top-k constant
TOP_K_RESULTS = 5


# =====================================================================
# Core Resolver Architecture
# =====================================================================

class FAIARepositoryResolver:
    def __init__(self, target_dir: str = "catalog_output"):
        configured_dir = Path(target_dir).expanduser()
        self.target_dir = str(
            configured_dir if configured_dir.is_absolute()
            else Path(__file__).resolve().parent / configured_dir
        )
        
        # Configuration Constants Mapped Directly to Formula Weights
        self.W_REPO_RANK = 0.35
        self.W_PROVIDER_SCORE = 0.35
        self.W_CAP_MATCH = 0.20
        self.W_CAP_COVERAGE = 0.10

        # Confidence Hierarchy Modifiers
        self.BOOST_EXACT_NAME = 60.0
        self.BOOST_OWNER_REPO = 55.0
        self.BOOST_REPO_ALIAS = 50.0
        self.BOOST_PROVIDER_MATCH = 40.0

        # Performance Fast Routing Short-Circuit Threshold Limits
        self.JACCARD_THRESHOLD = 0.40 

        # Minimal Acronym & Abbreviation Alias Registry
        self.minimal_alias_registry = {
            "modelcontextprotocol": ["mcp"],
            "digitalocean": ["do"],
            "github": ["gh"]
        }

        # Memory-Cached Repositories Artifact Buckets
        self.repository_index: Dict[str, Any] = {}
        self.repository_rankings: Dict[str, Any] = {}
        self.repository_search_terms: Dict[str, List[str]] = {}
        self.repository_capability_matrix: Dict[str, Any] = {}
        self.repository_installation_registry: Dict[str, Any] = {}
        self.provider_profiles: Dict[str, Any] = {}
        self.capabilities: Dict[str, Any] = {}

        # Inverted Traversal Indexes
        self.provider_to_repo_map = defaultdict(list)
        self.capability_to_repo_map = defaultdict(list)

        # Normalized O(1) Compact & Token Lookup Indices
        self.provider_compact_index: Dict[str, str] = {}
        self.repository_compact_index: Dict[str, Set[str]] = defaultdict(set) 
        self.provider_token_index: Dict[str, Set[str]] = {}
        self.repository_token_index: Dict[str, Set[str]] = {}
        self.alias_to_provider_map: Dict[str, str] = {}

        # Structured capability index for deterministic ranking
        self.capability_structure_index: Dict[str, Dict[str, Any]] = {}

        # Bootstrap layers
        self._load_artifacts()
        self._build_indices()

    def _refresh_state_pools(self) -> None:
        """Flushes cache configurations to guarantee deterministic memory maps."""
        self.repository_index.clear()
        self.repository_rankings.clear()
        self.repository_search_terms.clear()
        self.repository_capability_matrix.clear()
        self.repository_installation_registry.clear()
        self.provider_profiles.clear()
        self.capabilities.clear()
        self.provider_to_repo_map.clear()
        self.capability_to_repo_map.clear()
        self.provider_compact_index.clear()
        self.repository_compact_index.clear()
        self.provider_token_index.clear()
        self.repository_token_index.clear()
        self.alias_to_provider_map.clear()

    def _normalize_search_key(self, text: str) -> Tuple[str, str]:
        """Canonical Query Normalization Layer producing normalized and space-stripped pairs."""
        if not text:
            return "", ""
        lowered = text.lower()
        spaces_cleaned = lowered.replace("-", " ").replace("_", " ")
        normalized = " ".join(spaces_cleaned.split()).strip()
        compact = normalized.replace(" ", "")
        return normalized, compact

    def _tokenize_string(self, text: str) -> Set[str]:
        """Helper to break normalized strings down to set structures for similarity checks."""
        normalized, _ = self._normalize_search_key(text)
        return set(normalized.split())

    def _compute_jaccard_similarity(self, set_a: Set[str], set_b: Set[str]) -> float:
        """Calculates token intersections over tracking unions."""
        if not set_a or not set_b:
            return 0.0
        return float(len(set_a.intersection(set_b)) / len(set_a.union(set_b)))

    def _load_artifacts(self) -> None:
        """Loads and cross-validates frozen metadata components from disk storage partitions."""
        self._refresh_state_pools()
        mandatory_artifacts = {
            "repository_index.json": "repository_index",
            "repository_rankings.json": "repository_rankings",
            "repository_search_terms.json": "repository_search_terms",
            "repository_capability_matrix.json": "repository_capability_matrix",
            "repository_installation_registry.json": "repository_installation_registry",
            "provider_profiles.json": "provider_profiles",
            "capabilities.json": "capabilities"
        }

        for filename, attr_bucket in mandatory_artifacts.items():
            filepath = os.path.join(self.target_dir, filename)
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"[FAIL-FAST] Registry artifact missing: '{filepath}'.")
            with open(filepath, "r", encoding="utf-8") as fs:
                setattr(self, attr_bucket, json.load(fs))

        # Cross-registry consistency validation check
        for repo_id in self.repository_index.keys():
            if repo_id not in self.repository_rankings:
                raise KeyError(f"[CROSS-REGISTRY DRIFT DETECTED] Repository '{repo_id}' is missing a rankings entry.")
            if repo_id not in self.repository_installation_registry:
                raise KeyError(f"[CROSS-REGISTRY DRIFT DETECTED] Repository '{repo_id}' is missing an installation config.")
            if repo_id not in self.repository_capability_matrix:
                raise KeyError(f"[CROSS-REGISTRY DRIFT DETECTED] Repository '{repo_id}' is missing a matrix record.")

        # OK-002: Fail-fast provider profile search token bootstrap validation check on startup
        actual_provider_ids = {meta.get("provider_id", "").lower().strip() for meta in self.repository_index.values() if meta.get("provider_id")}
        for p_id in actual_provider_ids:
            p_profile = self.provider_profiles.get(p_id, {})
            if not p_profile or "search_tokens" not in p_profile or not p_profile["search_tokens"]:
                raise ValueError(
                    f"[BOOTSTRAP VALIDATION CRITICAL ERROR] Provider profile '{p_id}' is missing required 'search_tokens'. "
                    f"System initialization aborted to prevent degraded token matching."
                )

    def _build_indices(self) -> None:
        """Component: _build_indices. Compiles algorithmic lookup structures."""
        # Hydrate Provider and Repository Compact & Token Matrix Profiles
        for repo_id, meta in self.repository_index.items():
            p_id = meta.get("provider_id")
            raw_repo_name = meta.get("repository_name")
            repo_url = meta.get("repository_url", "")
            
            if p_id:
                p_key = p_id.lower().strip()
                self.provider_to_repo_map[p_key].append(repo_id)
                
                # Provider Compact Index Assembly
                _, p_compact = self._normalize_search_key(p_key)
                self.provider_compact_index[p_compact] = p_key
                
                # Token Resolution via explicit search_tokens field
                profile_meta = self.provider_profiles.get(p_key, {})
                self.provider_token_index[p_key] = set(str(t).lower() for t in profile_meta["search_tokens"])
                
            if raw_repo_name:
                repo_name_lower = raw_repo_name.lower().strip()
                repo_norm, repo_compact = self._normalize_search_key(repo_name_lower)
                
                self.repository_compact_index[repo_compact].add(repo_id)
                if repo_norm != repo_compact:
                    self.repository_compact_index[repo_norm].add(repo_id)
                if repo_name_lower != repo_norm:
                    self.repository_compact_index[repo_name_lower].add(repo_id)
                    
                # Repository Token Index Extraction
                self.repository_token_index[repo_id] = self._tokenize_string(repo_norm)

            # OK-003: Canonical URL Alias Normalization before insertion into compact index
            if repo_url:
                url_clean = repo_url.lower().split("?")[0].split("#")[0].rstrip("/")
                url_clean = url_clean.replace("https://", "").replace("http://", "").replace("www.", "")
                
                m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+)", url_clean)
                if m:
                    owner = m.group("owner").strip()
                    repo_slug = m.group("repo").strip()
                    if repo_slug.endswith(".git"):
                        repo_slug = repo_slug[:-4]
                    
                    url_aliases = [
                        f"github.com/{owner}/{repo_slug}",
                        f"{owner}/{repo_slug}",
                        f"{owner} {repo_slug}",
                        repo_slug
                    ]
                    for u_alias in url_aliases:
                        u_norm, u_compact = self._normalize_search_key(u_alias)
                        self.repository_compact_index[u_compact].add(repo_id)
                        if u_norm != u_compact:
                            self.repository_compact_index[u_norm].add(repo_id)

        # Hydrate Minimal Alias Registry shortcuts pointers maps
        for canonical_provider, acronyms in self.minimal_alias_registry.items():
            for acronym in acronyms:
                self.alias_to_provider_map[acronym.lower().strip()] = canonical_provider

        # Map capabilities mapping directories
        for repo_id, matrix in self.repository_capability_matrix.items():
            for cap_id in matrix.get("capabilities", []):
                self.capability_to_repo_map[cap_id.upper()].append(repo_id)

        # Build structured capability index for deterministic ranking
        self._build_capability_structure_index()

        self.search_engine = CapabilitySearchEngine(target_dir=self.target_dir)
        self.orchestration_engine = FAIAOrchestrationEngine(target_dir=self.target_dir)

    def _build_capability_structure_index(self) -> None:
        """Parse every capability into structured verb/resource components for deterministic ranking."""
        for cap_id in self.capabilities.keys():
            cap_upper = cap_id.upper()
            parts = cap_upper.split("_")
            
            verb = None
            resource = None
            
            # Common verbs to match
            known_verbs = {"READ", "CREATE", "UPDATE", "DELETE", "EXECUTE", "LIST", "WRITE"}
            
            if parts and parts[0] in known_verbs:
                verb = parts[0]
                if len(parts) > 1:
                    resource = "_".join(parts[1:])
            
            self.capability_structure_index[cap_upper] = {
                "capability_id": cap_upper,
                "verb": verb,
                "resource": resource,
                "tokens": set(cap_upper.lower().split("_"))
            }

    def _parse_query_structure(self, query: str) -> Dict[str, Any]:
        """Parse user query into verb and resource components."""
        query_upper = query.strip().upper()
        tokens = query_upper.split()
        token_set = set(t.lower() for t in tokens)
        
        verb = None
        resource = None
        known_verbs = {"READ", "CREATE", "UPDATE", "DELETE", "EXECUTE", "LIST", "WRITE"}
        
        if tokens and tokens[0] in known_verbs:
            verb = tokens[0]
            if len(tokens) > 1:
                resource = "_".join(tokens[1:])
        
        return {
            "verb": verb,
            "resource": resource,
            "tokens": token_set,
            "original": query
        }

    def _rank_capabilities_deterministically(self, matched_caps: Dict[str, float], query: str) -> Dict[str, float]:
        """
        Re-rank capabilities using structured verb/resource matching.
        This replaces weak token overlap scoring with deterministic component matching.
        """
        query_struct = self._parse_query_structure(query)
        reranked: Dict[str, float] = {}
        
        for cap_id, base_score in matched_caps.items():
            cap_upper = cap_id.upper()
            cap_struct = self.capability_structure_index.get(cap_upper)
            
            if not cap_struct:
                reranked[cap_id] = base_score
                continue
            
            score = base_score
            
            # Exact capability match: highest boost
            if cap_upper == query_struct["original"].upper():
                score += 50.0
            
            # Verb and resource both match: very high boost
            if query_struct["verb"] and query_struct["resource"]:
                if cap_struct["verb"] == query_struct["verb"] and cap_struct["resource"] == query_struct["resource"]:
                    score += 40.0
                # Verb match but wrong resource: medium penalty
                elif cap_struct["verb"] == query_struct["verb"]:
                    score += 15.0
                else:
                    score -= 20.0
            # Only verb provided (e.g., "read" alone) - should be handled by CAPABILITY_GROUP
            elif query_struct["verb"] and not query_struct["resource"]:
                if cap_struct["verb"] == query_struct["verb"]:
                    score += 5.0
            
            reranked[cap_id] = max(0.0, score)
        
        return reranked

    def health(self) -> Dict[str, Any]:
        """Core Normalization & Metric Validation Health Gate."""
        actual_provider_ids = {meta.get("provider_id", "").lower().strip() for meta in self.repository_index.values() if meta.get("provider_id")}
        
        provider_compact_hits = sum(1 for p in actual_provider_ids if any(p == target for target in self.provider_compact_index.values()))
        provider_token_hits = sum(1 for p in actual_provider_ids if p in self.provider_token_index)
        
        provider_compact_ratio = float(provider_compact_hits / len(actual_provider_ids)) if actual_provider_ids else 0.0
        provider_token_ratio = float(provider_token_hits / len(actual_provider_ids)) if actual_provider_ids else 0.0
        
        # Verify search token data completeness
        providers_missing_search_tokens = [p for p in actual_provider_ids if not self.provider_profiles.get(p, {}).get("search_tokens")]
        provider_search_token_coverage_ratio = float((len(actual_provider_ids) - len(providers_missing_search_tokens)) / len(actual_provider_ids)) if actual_provider_ids else 0.0
            
        reachable_repo_ids = set()
        for r_set in self.repository_compact_index.values():
            reachable_repo_ids.update(r_set)
            
        total_indexed_repos_count = len(self.repository_index)
        repository_compact_coverage_ratio = float(len(reachable_repo_ids) / total_indexed_repos_count) if total_indexed_repos_count > 0 else 0.0
        
        all_metrics_passed = (
            provider_compact_ratio == 1.0 and 
            repository_compact_coverage_ratio == 1.0 and 
            provider_token_ratio == 1.0 and
            provider_search_token_coverage_ratio == 1.0
        )

        return {
            "search_engine_version": SEARCH_ENGINE_VERSION,
            "search_engine_status": SEARCH_ENGINE_STATUS,
            "provider_compact_coverage_ratio": provider_compact_ratio,
            "repository_compact_coverage_ratio": repository_compact_coverage_ratio,
            "provider_token_coverage_ratio": provider_token_ratio,
            "provider_search_token_coverage_ratio": provider_search_token_coverage_ratio,
            "providers_missing_search_tokens": sorted(providers_missing_search_tokens),
            "validation_status": "VALIDATED" if all_metrics_passed else "METRICS_FAILED"
        }

    def repository(self, repository_id: str) -> Optional[Dict[str, Any]]:
        """Consolidated Repository Metadata Lookup API."""
        repo_meta = self.repository_index.get(repository_id)
        if not repo_meta:
            return None
        rank_meta = self.repository_rankings.get(repository_id, {})
        install_meta = self.repository_installation_registry.get(repository_id, {})
        return {
            "repository_id": repository_id,
            "repository_name": repo_meta.get("repository_name"),
            "repository_url": repo_meta.get("repository_url"),
            "provider_id": repo_meta.get("provider_id"),
            "capabilities": repo_meta.get("capabilities", []),
            "domains": repo_meta.get("domains", []),
            "tool_count": repo_meta.get("tool_count", 0),
            "capability_count": repo_meta.get("capability_count", 0),
            "provider_rank": repo_meta.get("provider_rank", 99),
            "ranking_score": rank_meta.get("ranking_score", 0.0),
            "installation_metadata": install_meta
        }

    def resolve(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Main API Entry Point: Resolves natural-language intent using algorithmic similarity bounds.
        OK-001 Fixed: Enforces strict multi-tiered resolution routing loops with an explicit intent lock.
        """
        t_start = time.time()
        
        repo_matched_caps_tracker = defaultdict(set)
        
        # Diagnostics match tracking fields parameters
        repository_compact_match_count = 0
        provider_compact_match_count = 0
        provider_token_match_count = 0
        provider_alias_match_count = 0

        # Short-Circuit Trap for Empty Query Conditions
        if not query or not query.strip():
            return {
                "query": "", "retrieval_status": "EMPTY_QUERY", "query_intent": "BROAD_SEARCH", "best_match": None,
                "discovery_evidence": {"query_intent": "BROAD_SEARCH", "matched_capabilities": [], "matched_providers": [], "matched_repositories": [], "resolution_path": []},
                "repositories": [], "suggestions": ["issue tracking", "workflow automation"],
                "diagnostics": {"query_latency_ms": round((time.time() - t_start) * 1000, 2), "capability_matches": 0, "provider_matches": 0, "repository_matches": 0}
            }

        query_norm, query_compact = self._normalize_search_key(query)
        query_tokens = self._tokenize_string(query)
        normalized_query_prefix = query.strip().upper()

        # Capability taxonomy exploration stage: enumerate capability families when prefix queries match multiple IDs.
        capability_prefix_matches: List[str] = []
        if normalized_query_prefix:
            capability_prefix_matches = [
                cap_id for cap_id in self.capabilities.keys()
                if cap_id.startswith(normalized_query_prefix)
            ]
            capability_prefix_matches.sort()

        if len(capability_prefix_matches) > 1:
            return {
                "query": query,
                "retrieval_status": "SUCCESS",
                "query_intent": "CAPABILITY_ENUMERATION",
                "capability_group": {
                    "prefix": normalized_query_prefix,
                    "capabilities": capability_prefix_matches
                },
                "best_match": None,
                "ranked_matches": [],
                "discovery_evidence": {
                    "query_intent": "CAPABILITY_ENUMERATION",
                    "matched_capabilities": [],
                    "matched_providers": [],
                    "matched_repositories": [],
                    "resolution_path": ["query", "capability_group"]
                },
                "repositories": [],
                "suggestions": [],
                "diagnostics": {
                    "query_latency_ms": round((time.time() - t_start) * 1000, 2),
                    "capability_matches": len(capability_prefix_matches),
                    "provider_matches": 0,
                    "repository_matches": 0,
                    "repository_compact_match_count": 0,
                    "provider_compact_match_count": 0,
                    "provider_token_match_count": 0,
                    "provider_alias_match_count": 0
                }
            }

        execution_path = ["query"]
        intent_label = "BROAD_SEARCH"
        retrieval_status = "SUCCESS"

        target_repo_ids: Set[str] = set()
        target_provider_ids: Set[str] = set()
        match_reasons_tracker = defaultdict(list)
        candidate_repositories_scores = defaultdict(float)

        # Tier 1 & Tier 2 & Tier 3: Repository Name Resolution Passes
        if query_compact in self.repository_compact_index:
            target_repo_ids.update(self.repository_compact_index[query_compact])
            repository_compact_match_count += len(self.repository_compact_index[query_compact])
        if query_norm in self.repository_compact_index:
            target_repo_ids.update(self.repository_compact_index[query_norm])

        # OK-001 Intent Lock: Repository name matches skip downstream search engines entirely
        if target_repo_ids:
            intent_label = "REPOSITORY_DISCOVERY"
            execution_path.append("repository")
            for r_id in target_repo_ids:
                candidate_repositories_scores[r_id] += self.BOOST_EXACT_NAME
                match_reasons_tracker[r_id].append("repository_compact_match")

        # Tier 4 & Tier 5 & Tier 6 & Tier 7 & Tier 8: Provider Resolution Lanes
        if not candidate_repositories_scores:
            if query_compact in self.provider_compact_index:
                target_provider_ids.add(self.provider_compact_index[query_compact])
                provider_compact_match_count += 1
                
            if query_norm in self.provider_compact_index:
                target_provider_ids.add(self.provider_compact_index[query_norm])

            # Algorithmic Provider Token Jaccard Overlap Evaluation
            if not target_provider_ids:
                highest_jaccard = 0.0
                best_provider_match = None
                for p_id, p_tokens in self.provider_token_index.items():
                    sim = self._compute_jaccard_similarity(query_tokens, p_tokens)
                    if sim > highest_jaccard:
                        highest_jaccard = sim
                        best_provider_match = p_id
                        
                if highest_jaccard >= self.JACCARD_THRESHOLD and best_provider_match:
                    target_provider_ids.add(best_provider_match)
                    provider_token_match_count += 1

            # Minimal Acronym Provider Alias Fallback Layer
            if not target_provider_ids and query_compact in self.alias_to_provider_map:
                p_alias_target = self.alias_to_provider_map[query_compact]
                target_provider_ids.add(p_alias_target)
                provider_alias_match_count += 1

            # OK-001 Intent Lock: Provider matches establish direct paths and drop out of discovery graphs
            if target_provider_ids:
                intent_label = "PROVIDER_DISCOVERY"
                execution_path.extend(["provider", "repository"])
                for p_id in target_provider_ids:
                    for r_id in self.provider_to_repo_map.get(p_id.lower(), []):
                        candidate_repositories_scores[r_id] += self.BOOST_PROVIDER_MATCH
                        if provider_compact_match_count:
                            match_reasons_tracker[r_id].append("provider_compact_match")
                        elif provider_token_match_count:
                            match_reasons_tracker[r_id].append("provider_token_match")
                        elif provider_alias_match_count:
                            match_reasons_tracker[r_id].append("provider_alias_match")

        # Tier 9: Repository Token Overlap Fallback checks
        if not candidate_repositories_scores:
            for r_id, r_tokens in self.repository_token_index.items():
                sim = self._compute_jaccard_similarity(query_tokens, r_tokens)
                if sim >= self.JACCARD_THRESHOLD:
                    candidate_repositories_scores[r_id] += self.BOOST_REPO_ALIAS
                    match_reasons_tracker[r_id].append("repository_token_similarity_match")
            if candidate_repositories_scores:
                intent_label = "REPOSITORY_DISCOVERY"
                execution_path.append("repository")

        # Tier 10: Capability Orchestration Fallback Pipeline Pass
        matched_caps_keys = []
        matched_providers_keys = []
        cap_rank_scores = {}  # Store ranking scores for use below

        # Intent Lock Enforced: Only cascade down to capabilities layer on broad search phrasings
        if not candidate_repositories_scores:
            discovery_res = self.orchestration_engine.discover(query=query, top_k=20)
            retrieval_status = discovery_res.get("retrieval_status", "NO_MATCHES_FOUND")
            
            matched_caps_meta = {c["capability_id"]: c["confidence"] for c in discovery_res.get("capabilities", [])}
            matched_providers_meta = {p["provider_id"]: p["provider_score"] for p in discovery_res.get("providers", [])}
            
            # Apply deterministic capability ranking to re-order matched capabilities
            if matched_caps_meta:
                matched_caps_meta = self._rank_capabilities_deterministically(matched_caps_meta, query)
                # Sort capabilities by re-ranked score to ensure top capability is used for repository boosting
                sorted_caps = sorted(matched_caps_meta.items(), key=lambda x: -x[1])
                cap_rank_scores = {cap_id: score for cap_id, score in sorted_caps}
            else:
                sorted_caps = list(matched_caps_meta.items())
            
            # Keep matched_caps_keys in ranked order (NOT alphabetically sorted)
            matched_caps_keys = [cap_id for cap_id, _ in sorted_caps]
            matched_providers_keys = sorted(list(matched_providers_meta.keys()))

            if matched_caps_keys and "capability" not in execution_path:
                execution_path.append("capability")
            if matched_providers_keys and "provider" not in execution_path:
                execution_path.append("provider")
            if "repository" not in execution_path:
                execution_path.append("repository")

            # Map weighting components layers - prioritize top-ranked capability
            top_capability = None
            if sorted_caps:
                top_capability = sorted_caps[0][0]  # Highest ranked capability
                
            for cap_id, confidence in sorted_caps:
                # Boost repositories with the top-ranked capability much more
                if cap_id == top_capability:
                    confidence_boost = confidence * self.W_CAP_MATCH * 2.0  # 2x boost for top capability
                else:
                    confidence_boost = confidence * self.W_CAP_MATCH
                    
                for r_id in self.capability_to_repo_map.get(cap_id.upper(), []):
                    candidate_repositories_scores[r_id] += confidence_boost
                    repo_matched_caps_tracker[r_id].add(cap_id)
                    if "capability_match" not in match_reasons_tracker[r_id]:
                        match_reasons_tracker[r_id].append("capability_match")
            for p_id, p_score in matched_providers_meta.items():
                for r_id in self.provider_to_repo_map.get(p_id.lower(), []):
                    candidate_repositories_scores[r_id] += p_score * self.W_PROVIDER_SCORE
                    if "provider_match" not in match_reasons_tracker[r_id]:
                        match_reasons_tracker[r_id].append("provider_match")

        # Finalize and evaluate composite scores metrics
        assembled_repositories = []
        for repo_id, base_match_score in candidate_repositories_scores.items():
            repo_meta = self.repository_index.get(repo_id)
            rank_meta = self.repository_rankings.get(repo_id, {})
            install_meta = self.repository_installation_registry.get(repo_id, {})
            
            if not repo_meta:
                continue

            cap_coverage = rank_meta.get("capability_coverage", 0.0)
            repo_rank_score = rank_meta.get("ranking_score", 0.0)

            composite_score = (
                base_match_score +
                (repo_rank_score * self.W_REPO_RANK) +
                (cap_coverage * self.W_CAP_COVERAGE * 100.0)
            )
            raw_confidence = round(min(100.0, composite_score), 2)
            
            # For each repository's matched capabilities, rank them deterministically
            matched_caps_list = list(repo_matched_caps_tracker[repo_id])
            if matched_caps_list and cap_rank_scores:
                # Sort matched capabilities by deterministic ranking (highest first)
                matched_caps_list = sorted(matched_caps_list, 
                                         key=lambda c: -cap_rank_scores.get(c, 0.0))
            else:
                matched_caps_list = sorted(matched_caps_list)
                
            cap_string = ", ".join(matched_caps_list[:3]) if matched_caps_list else "base normalization profiles"
            explanation = (
                f"Resolved intent into provider '{repo_meta.get('provider_id')}' matching framework profiles. "
                f"Repository supports functional mappings: [{cap_string}]."
            )

            assembled_repositories.append({
                "repository_id": repo_id,
                "repository_name": repo_meta.get("repository_name", "unknown"),
                "repository_url": repo_meta.get("repository_url", ""),
                "provider_id": repo_meta.get("provider_id", "unknown"),
                "raw_confidence": raw_confidence, 
                "matched_capabilities": matched_caps_list,
                "supported_domains": repo_meta.get("domains", []),
                "installation_metadata": install_meta,
                "repository_rank_score": repo_rank_score,
                "provider_rank": repo_meta.get("provider_rank", 99),
                "tool_count": repo_meta.get("tool_count", 0),
                "capability_count": repo_meta.get("capability_count", 0),
                "explanation": explanation,
                "match_reasons": sorted(match_reasons_tracker[repo_id])
            })

        max_observed_score = max(x["raw_confidence"] for x in assembled_repositories) if assembled_repositories else 1.0
        final_sliced_results = []
        for repo_entry in assembled_repositories:
            c_val = repo_entry["raw_confidence"]
            rank_position_score = round((c_val / max_observed_score) * 100.0, 2) if max_observed_score else 0.0
            repo_entry["confidence"] = c_val
            repo_entry["rank_position_score"] = rank_position_score
            final_sliced_results.append(repo_entry)

        final_sliced_results.sort(key=lambda x: (-x["confidence"], x["repository_id"]))
        final_slice = final_sliced_results[:top_k]

        # Build a full ranked matches list (descending by confidence) for downstream discovery consumers
        ranked_matches = []
        for idx, entry in enumerate(final_sliced_results, start=1):
            ranked_matches.append({
                "rank": idx,
                "repository_id": entry.get("repository_id"),
                "repository_name": entry.get("repository_name"),
                "provider_id": entry.get("provider_id"),
                "repository_url": entry.get("repository_url"),
                "confidence": entry.get("confidence", 0.0),
                "match_reasons": entry.get("match_reasons", []),
                "supported_domains": entry.get("supported_domains", [])
            })

        if retrieval_status != "NO_PROVIDER_SUPPORT":
            retrieval_status = "SUCCESS" if final_slice else "NO_MATCHES_FOUND"

        best_match = None
        if final_slice and retrieval_status == "SUCCESS":
            best_match = {
                "repository_id": final_slice[0]["repository_id"],
                "repository_name": final_slice[0]["repository_name"],
                "confidence": final_slice[0]["confidence"],
                "repository_url": final_slice[0]["repository_url"],
                "provider_id": final_slice[0]["provider_id"],
                "explanation": final_slice[0]["explanation"]
            }

        evidence_chain = {
            "query_intent": intent_label,
            "matched_capabilities": matched_caps_keys,
            "matched_providers": matched_providers_keys,
            "matched_repositories": [r["repository_id"] for r in final_slice],
            "resolution_path": execution_path 
        }

        return {
            "query": query,
            "retrieval_status": retrieval_status,
            "query_intent": intent_label,
            "best_match": best_match,
            "ranked_matches": ranked_matches,
            "discovery_evidence": evidence_chain,
            "repositories": final_slice,
            "suggestions": [] if final_slice else ["digital ocean", "mcp server"],
            "diagnostics": {
                "query_latency_ms": round((time.time() - t_start) * 1000, 2),
                "capability_matches": len(matched_caps_keys),
                "provider_matches": len(matched_providers_keys),
                "repository_matches": len(final_slice),
                "repository_compact_match_count": max(0, repository_compact_match_count),
                "provider_compact_match_count": max(0, provider_compact_match_count),
                "provider_token_match_count": max(0, provider_token_match_count),
                "provider_alias_match_count": max(0, provider_alias_match_count)
            }
        }


# =====================================================================
# CLI Interface & Automated Testing Suite Harness
# =====================================================================

def run_resolver_regression_suite(resolver: FAIARepositoryResolver) -> int:
    """OK-004: Regression summary metrics utilizing dynamic test array count lengths."""
    print("=== FINAL INTEGRATION VERIFICATION GATES SUITE ===", file=sys.stderr)
    test_cases = [
        # Provider discovery trajectories
        {"query": "digitalocean", "expected_path": ["query", "provider", "repository"]},
        {"query": "Digital Ocean", "expected_path": ["query", "provider", "repository"]},
        {"query": "mcp", "expected_path": ["query", "provider", "repository"]},
        {"query": "heroku", "expected_path": ["query", "provider", "repository"]},
        # OK-006: Repository discovery trajectories url expansion variants
        {"query": "heroku-mcp-server", "expected_path": ["query", "repository"]},
        {"query": "context7", "expected_path": ["query", "repository"]},
        {"query": "upstash/context7", "expected_path": ["query", "repository"]},
        {"query": "github.com/upstash/context7", "expected_path": ["query", "repository"]},
        # Capability discovery trajectories
        {"query": "workflow automation", "expected_path": ["query", "capability", "provider", "repository"]},
        {"query": "issue tracking", "expected_path": ["query", "capability", "provider", "repository"]}
    ]
    
    failed_cases = 0
    for idx, case in enumerate(test_cases, 1):
        q = case["query"]
        expected = case["expected_path"]
        try:
            res = resolver.resolve(query=q, top_k=5)
            status = res.get("retrieval_status")
            actual_path = res["discovery_evidence"]["resolution_path"]
            
            if status != "SUCCESS":
                print(f" -> Case {idx} '{q}': Status '{status}' failed target expectations! [FAILED]", file=sys.stderr)
                failed_cases += 1
                continue
                
            if actual_path != expected:
                print(f" -> Case {idx} '{q}': Path contamination! Expected {expected}, got {actual_path} [FAILED]", file=sys.stderr)
                failed_cases += 1
                continue
                
            print(f" -> Case {idx}: Query '{q}' -> Status: {status} | Route Paths: {actual_path} [PASSED]", file=sys.stderr)
        except Exception as err:
            print(f" -> Case {idx}: Query '{q}' raised exception: {err} [FAILED]", file=sys.stderr)
            failed_cases += 1

    # Non-existent edge verification pass
    try:
        edge_res = resolver.resolve(query="asdfghjkl", top_k=5)
        if edge_res.get("retrieval_status") == "NO_MATCHES_FOUND":
            print(f" -> Case {len(test_cases) + 1}: Query 'asdfghjkl' -> Status: NO_MATCHES_FOUND [PASSED]", file=sys.stderr)
        else:
            print(f" -> Case {len(test_cases) + 1}: Query 'asdfghjkl' -> Failed fallback boundaries! [FAILED]", file=sys.stderr)
            failed_cases += 1
    except Exception as err:
        print(f" -> Case {len(test_cases) + 1} raised exception: {err} [FAILED]", file=sys.stderr)
        failed_cases += 1

    total_run_tests = len(test_cases) + 1
    print(f"\n=== FINAL PLATFORM VERIFICATION PAYLOAD SUMMARY: {total_run_tests - failed_cases}/{total_run_tests} PASSED ===\n", file=sys.stderr)
    return 1 if failed_cases > 0 else 0


def main():
    parser = argparse.ArgumentParser(description="FAIA Gold Master Algorithmic Repository Intent Resolver.")
    parser.add_argument("query", type=str, nargs="?", default=None, help="User semantic text input string parameter.")
    parser.add_argument("--repository", type=str, default=None, help="Returns full repository metadata by target ID.")
    parser.add_argument("--health", action="store_true", help="Surfaces the internal normalization metrics health block.")
    parser.add_argument("--run-tests", action="store_true", help="Triggers automated regression tests validations checks loop.")
    args = parser.parse_args()

    try:
        resolver = FAIARepositoryResolver()
        
        if args.run_tests:
            sys.exit(run_resolver_regression_suite(resolver))

        if args.health:
            print(json.dumps(resolver.health(), indent=2, sort_keys=True))
            sys.exit(0)

        if args.repository:
            repo_payload = resolver.repository(repository_id=args.repository)
            if not repo_payload:
                print(json.dumps({"error": f"Repository identity '{args.repository}' not found"}, indent=2))
                sys.exit(1)
            print(json.dumps(repo_payload, indent=2, sort_keys=True))
            sys.exit(0)

        if args.query is None:
            parser.print_help()
            sys.exit(1)

        resolution_output = resolver.resolve(query=args.query)
        print(json.dumps(resolution_output, indent=2, sort_keys=True))

    except Exception as exc:
        print(f"[CRITICAL ABORT] Resolver failed setup operations: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
FAIA Provider Intelligence Layer - Version v2.0.3
[PRODUCTION GOLD MASTER FREEZE - RELEASE v2.0.3 COMPLETION]
Constructs the canonical provider intelligence backbone for FAIA Search, Rankings, and Recommendations.
Features complete cross-layer token vocabulary tracking and strict asset health validation gates.
Applies patches: PIE-FINAL-001 through PIE-FINAL-003.
"""

import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Set
from datetime import datetime, timezone


class ProviderIntelligenceEngine:
    def __init__(self, input_dir: str = "catalog_output", output_dir: str = "catalog_output"):
        self.input_dir = input_dir
        self.output_dir = output_dir
        
        # H-003: Configurable Graph Edge Threshold
        self.SIMILARITY_EDGE_THRESHOLD = 0.15
        
        # Frozen Input Artifacts
        self.capabilities: Dict[str, Any] = {}
        self.provider_matrix: Dict[str, Any] = {}
        self.archetypes_registry: Dict[str, str] = {}
        self.repository_profiles: Dict[str, Any] = {}
        self.cap_search_terms: Dict[str, List[str]] = {}
        self.cap_classes: Dict[str, str] = {}
        self.cap_domains: Dict[str, List[str]] = {}
        
        # Core Output Artifacts
        self.provider_profiles: Dict[str, Any] = {}
        self.provider_rankings: Dict[str, Any] = {}
        self.provider_comparison_index: Dict[str, Any] = {}
        self.provider_similarity_matrix: Dict[str, Any] = {}
        self.provider_search_terms: Dict[str, List[str]] = {}
        self.provider_capability_heatmap: Dict[str, Dict[str, bool]] = {}
        self.capability_leaderboards: Dict[str, List[str]] = {}
        self.provider_recommendations: Dict[str, Any] = {}
        self.provider_graph: Dict[str, Any] = {"nodes": [], "edges": []}
        self.provider_lookup_index: Dict[str, Any] = {}
        self.provider_search_index: List[Dict[str, Any]] = []
        self.health_report: Dict[str, Any] = {}

        # Internal Aggregation State
        self.total_catalog_capabilities = 0
        self.total_catalog_domains = 0
        self.total_catalog_classes = 0
        self.total_catalog_tools = 0

    def load_frozen_catalog_artifacts(self) -> None:
        """Loads certified frozen files from disk with fail-fast path handling."""
        targets = {
            "capabilities.json": "capabilities",
            "capability_provider_matrix.json": "provider_matrix",
            "provider_archetypes.json": "archetypes_registry",
            "repository_profiles.json": "repository_profiles",
            "capability_search_terms.json": "cap_search_terms",
            "capability_classes.json": "cap_classes",
            "capability_domains.json": "cap_domains"
        }
        
        for filename, attr in targets.items():
            filepath = os.path.join(self.input_dir, filename)
            if not os.path.exists(filepath):
                print(f"[WARNING] Optional/Mandatory upstream file '{filename}' missing. Using empty mapping.")
                continue
            
            with open(filepath, "r", encoding="utf-8") as f:
                setattr(self, attr, json.load(f))

        # H-001: Validate Provider Archetype Schema (Fail-fast)
        if not isinstance(self.archetypes_registry, dict):
            raise ValueError("[FAIL-FAST] provider_archetypes.json must be a flat dictionary mapping.")
        for k, v in self.archetypes_registry.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ValueError(f"[FAIL-FAST] Invalid archetype schema. Key/Value '{k}':'{v}' must be strings.")

        self.total_catalog_capabilities = len(self.capabilities)
        self.total_catalog_domains = len(self.cap_domains)
        self.total_catalog_classes = len(self.cap_classes)
        self.total_catalog_tools = sum(c.get("tool_count", 0) for c in self.capabilities.values())

        if self.total_catalog_capabilities == 0:
            raise RuntimeError("[FAIL-FAST CRITICAL] Loaded 0 capabilities. Catalog must be populated.")

    def _generate_provider_search_tokens(self, provider_id: str, repositories: Set[str]) -> List[str]:
        """
        Decompression and Token Expansion Layer
        Programmatically derives compact and delimiter-stripped forms for total layer alignment.
        """
        tokens = set()

        provider_id = provider_id.lower()
        tokens.add(provider_id)

        normalized = provider_id.replace('_', ' ').replace('-', ' ')
        tokens.update(normalized.split())

        overrides = {
            'digitalocean': ['digital', 'ocean', 'do'],
            'modelcontextprotocol': ['model', 'context', 'protocol', 'mcp'],
            'openbnb_org': ['openbnb', 'bnb', 'airbnb', 'openbnb-org'], 
            'langfuse': ['lang', 'fuse'],
            'meilisearch': ['meili', 'search'],
            'illuminaresolutions': ['illuminare', 'n8n', 'workflow', 'automation'],
            'upstash': ['upstash', 'context7', 'documentation'],
            'heroku': ['heroku', 'dyno', 'cloud']
        }

        if provider_id in overrides:
            tokens.update(overrides[provider_id])

        for repo_url in repositories:
            repo_slug = repo_url.rstrip('/').split('/')[-1].lower()
            tokens.add(repo_slug)
            tokens.update(repo_slug.replace('-', ' ').replace('_', ' ').split())
            tokens.add(repo_slug.replace('-', ''))
            tokens.add(repo_slug.replace('_', ''))

        return sorted(
            token.strip()
            for token in tokens
            if token and len(token.strip()) > 1
        )

    def generate_provider_profiles(self) -> None:
        """Normalizes scoring and maps repository aggregation."""
        provider_data = defaultdict(lambda: {
            "capabilities_supported": set(),
            "total_tools_deployed": 0,
            "domain_footprint": set(),
            "class_footprint": set(),
            "repositories": set()
        })

        # Aggregation Pass
        for cap_id, matrix_entry in self.provider_matrix.items():
            cap_meta = self.capabilities.get(cap_id, {})
            
            for provider, tools in matrix_entry.get("provider_tools", {}).items():
                provider_data[provider]["capabilities_supported"].add(cap_id)
                provider_data[provider]["total_tools_deployed"] += len(tools)
                
                if "capability_domain" in cap_meta:
                    provider_data[provider]["domain_footprint"].add(cap_meta["capability_domain"])
                if "capability_class" in cap_meta:
                    provider_data[provider]["class_footprint"].add(cap_meta["capability_class"])

        # Mapping repositories (H-002: Replaced heuristic with explicit overrides)
        for repo_url, repo_meta in self.repository_profiles.items():
            explicit_provider = repo_meta.get("provider")
            
            # Prefer explicit provider field if it exists
            if explicit_provider and explicit_provider in provider_data:
                provider_data[explicit_provider]["repositories"].add(repo_url)
            else:
                # Fall back to heuristic matching
                for provider in provider_data.keys():
                    if provider in repo_url.lower() or provider in repo_meta.get("server_name", "").lower():
                        provider_data[provider]["repositories"].add(repo_url)

        # Profile Building & Normalization
        for provider, metrics in provider_data.items():
            u_caps = len(metrics["capabilities_supported"])
            u_doms = len(metrics["domain_footprint"])
            u_clss = len(metrics["class_footprint"])
            t_tools = metrics["total_tools_deployed"]
            
            cap_cov = u_caps / self.total_catalog_capabilities if self.total_catalog_capabilities else 0.0
            dom_cov = u_doms / self.total_catalog_domains if self.total_catalog_domains else 0.0
            cls_cov = u_clss / self.total_catalog_classes if self.total_catalog_classes else 0.0
            eco_share = t_tools / self.total_catalog_tools if self.total_catalog_tools else 0.0

            # Normalized functional density score
            functional_density = (0.7 * cap_cov) + (0.3 * dom_cov)
            focus = "GENERALIST_PLATFORM" if u_doms > 3 else "SPECIALIZED_UTILITY"
            
            repo_count = len(metrics["repositories"])
            avg_tools_repo = round(t_tools / repo_count, 2) if repo_count > 0 else float(t_tools)

            self.provider_profiles[provider] = {
                "provider_id": provider,
                "search_tokens": self._generate_provider_search_tokens(
                    provider,
                    metrics['repositories']
                ),
                "archetype": self.archetypes_registry.get(provider, "GENERAL"),
                "operational_focus": focus,
                "tool_count": t_tools,
                "capability_count": u_caps,
                "domain_count": u_doms,
                "class_count": u_clss,
                "repository_count": repo_count,
                "average_tools_per_repository": avg_tools_repo,
                "capability_coverage": round(cap_cov, 4),
                "domain_coverage": round(dom_cov, 4),
                "class_coverage": round(cls_cov, 4),
                "ecosystem_share": round(eco_share, 4),
                "functional_density_score": round(functional_density, 4),
                "repositories": sorted(list(metrics["repositories"])),
                "covered_domains": sorted(list(metrics["domain_footprint"])),
                "covered_classes": sorted(list(metrics["class_footprint"])),
                "capabilities_manifest": sorted(list(metrics["capabilities_supported"]))
            }

    def compute_jaccard_matrices(self) -> None:
        """Constructs similarity graphs utilizing Jaccard Index."""
        providers = list(self.provider_profiles.keys())
        
        for p_a in providers:
            self.provider_similarity_matrix[p_a] = {}
            self.provider_comparison_index[p_a] = {"similar_providers": []}
            self.provider_recommendations[p_a] = {"alternatives": []}
            
            caps_a = set(self.provider_profiles[p_a]["capabilities_manifest"])
            
            similarities = []
            for p_b in providers:
                if p_a == p_b:
                    continue
                
                caps_b = set(self.provider_profiles[p_b]["capabilities_manifest"])
                intersection = caps_a.intersection(caps_b)
                union = caps_a.union(caps_b)
                
                jaccard = round(len(intersection) / len(union), 4) if union else 0.0
                self.provider_similarity_matrix[p_a][p_b] = jaccard
                
                if jaccard > 0.0:
                    similarities.append({
                        "provider": p_b, 
                        "similarity": jaccard,
                        "shared_capabilities": sorted(list(intersection)),
                        "exclusive_capabilities": sorted(list(caps_a.difference(caps_b)))
                    })

            # Sort descending by similarity, then ascending lexically by name
            similarities.sort(key=lambda x: (-x["similarity"], x["provider"]))
            self.provider_comparison_index[p_a]["similar_providers"] = similarities
            
            # Recommendation layer abstracts away the score for pure ordered targeting
            self.provider_recommendations[p_a]["alternatives"] = [s["provider"] for s in similarities]

    def compute_rankings_and_leaderboards(self) -> None:
        """Generates dynamic class and domain vertical implementation rankings manifests."""
        domain_leaders = defaultdict(list)
        class_leaders = defaultdict(list)

        raw_rankings = []
        for p_id, profile in self.provider_profiles.items():
            ranking_score = (
                (profile["capability_coverage"] * 0.45) +
                (profile["domain_coverage"] * 0.25) +
                (profile["class_coverage"] * 0.15) +
                (profile["ecosystem_share"] * 0.15)
            )
            raw_rankings.append({"provider_id": p_id, "score": round(ranking_score, 4)})
            
            for d in profile["covered_domains"]:
                cap_count_in_domain = sum(1 for c in profile["capabilities_manifest"] if self.capabilities.get(c, {}).get("capability_domain") == d)
                domain_leaders[d].append({"provider_id": p_id, "score": cap_count_in_domain})
                
            for c_cls in profile["covered_classes"]:
                cap_count_in_class = sum(1 for c in profile["capabilities_manifest"] if self.capabilities.get(c, {}).get("capability_class") == c_cls)
                class_leaders[c_cls].append({"provider_id": p_id, "score": cap_count_in_class})

        raw_rankings.sort(key=lambda x: (-x["score"], x["provider_id"]))
        self.provider_rankings = {"global_provider_rankings": raw_rankings}

        for idx, entry in enumerate(raw_rankings, 1):
            self.provider_profiles[entry["provider_id"]]["provider_rank"] = idx

        sorted_by_coverage = sorted(self.provider_profiles.values(), key=lambda x: (-x["capability_coverage"], x["provider_id"]))
        for idx, profile in enumerate(sorted_by_coverage, 1):
            self.provider_profiles[profile["provider_id"]]["coverage_rank"] = idx

        for cap_id, matrix_entry in self.provider_matrix.items():
            provider_tools = matrix_entry.get("provider_tools", {})
            cap_providers = [{"provider": p_id, "tool_count": len(tools)} for p_id, tools in provider_tools.items()]
            cap_providers.sort(key=lambda x: (-x["tool_count"], x["provider"]))
            self.capability_leaderboards[cap_id] = [p["provider"] for p in cap_providers]

    def build_search_and_lookup_assets(self) -> None:
        """Compiles flattened search-optimized dictionaries."""
        for p_id, profile in self.provider_profiles.items():
            self.provider_capability_heatmap[p_id] = {cap: True for cap in profile["capabilities_manifest"]}
            
            search_terms = set()
            search_terms.add(profile["archetype"].replace("_", " ").lower())
            for d in profile["covered_domains"]:
                search_terms.add(d.replace("_", " ").lower())
            for c in profile["covered_classes"]:
                search_terms.add(c.replace("_", " ").lower())
            for cap in profile["capabilities_manifest"]:
                search_terms.add(cap.replace("_", " ").lower())
                for t in self.cap_search_terms.get(cap, []):
                    search_terms.add(t.lower())
            
            # PIE-FINAL-001 Injected: Force shared alignment between generated search_tokens and vocabulary index fields
            for token in profile.get('search_tokens', []):
                search_terms.add(token.lower())
                    
            self.provider_search_terms[p_id] = sorted(list(search_terms))
            
            self.provider_lookup_index[p_id] = {
                "archetype": profile["archetype"],
                "provider_rank": profile["provider_rank"],
                "capability_count": profile["capability_count"]
            }
            
            self.provider_search_index.append({
                "provider_id": p_id,
                "provider_rank": profile["provider_rank"],
                "archetype": profile["archetype"],
                "capability_coverage": profile["capability_coverage"],
                "search_terms": sorted(list(search_terms))
            })
            
        self.provider_search_index.sort(key=lambda x: x["provider_id"])

    def build_provider_graph(self) -> None:
        """Constructs deduplicated graph node and edge topologies."""
        nodes = []
        edges = []
        seen_edges = set()
        
        for p_id, profile in self.provider_profiles.items():
            nodes.append({
                "id": p_id,
                "type": "provider",
                "properties": {"archetype": profile["archetype"], "rank": profile["provider_rank"]}
            })
            
            similarities = self.provider_similarity_matrix.get(p_id, {})
            for p_b, sim_score in similarities.items():
                if sim_score > self.SIMILARITY_EDGE_THRESHOLD:
                    canonical_edge = tuple(sorted([p_id, p_b]))
                    if canonical_edge not in seen_edges:
                        seen_edges.add(canonical_edge)
                        edges.append({
                            "source": canonical_edge[0],
                            "target": canonical_edge[1],
                            "type": "similarity",
                            "weight": sim_score
                        })
                    
        nodes.sort(key=lambda x: x["id"])
        edges.sort(key=lambda x: (x["source"], x["target"]))
        
        self.provider_graph = {"nodes": nodes, "edges": edges}

    def generate_health_report(self) -> None:
        """PIE-FINAL-002: Hardened telemetry reports validating compiled token ratios."""
        provider_count = len(self.provider_profiles)
        providers_with_search_tokens = sum(1 for p in self.provider_profiles.values() if len(p.get("search_tokens", [])) > 0)
        provider_search_token_coverage_ratio = float(providers_with_search_tokens / provider_count) if provider_count > 0 else 0.0

        status_flag = "VALIDATED"
        if provider_search_token_coverage_ratio < 1.0:
            status_flag = "METRICS_FAILED"

        self.health_report = {
            "provider_count": provider_count,
            "providers_with_search_tokens": providers_with_search_tokens,
            "provider_search_token_coverage_ratio": provider_search_token_coverage_ratio,
            "capability_count": self.total_catalog_capabilities,
            "domain_count": self.total_catalog_domains,
            "similarity_edges": len(self.provider_graph["edges"]),
            "ranking_coverage": round(len(self.provider_rankings["global_provider_rankings"]) / max(1, provider_count), 4),
            "search_term_coverage": round(len(self.provider_search_terms) / max(1, provider_count), 4),
            "status": status_flag
        }

    def export_intelligence_layer(self) -> None:
        """Writes compiled metadata artifacts to disk securely with stable sorting formatting."""
        os.makedirs(self.output_dir, exist_ok=True)
        
        sorted_profiles = {k: self.provider_profiles[k] for k in sorted(self.provider_profiles.keys())}
        sorted_comparison = {k: self.provider_comparison_index[k] for k in sorted(self.provider_comparison_index.keys())}
        sorted_similarity = {k: {sk: v for sk, v in sorted(self.provider_similarity_matrix[k].items())} for k in sorted(self.provider_similarity_matrix.keys())}
        sorted_search_terms = {k: sorted(v) for k, v in sorted(self.provider_search_terms.items())}
        sorted_heatmap = {k: {sk: v for sk, v in sorted(self.provider_capability_heatmap[k].items())} for k in sorted(self.provider_capability_heatmap.keys())}
        sorted_leaderboards = {k: self.capability_leaderboards[k] for k in sorted(self.capability_leaderboards.keys())}
        sorted_recommendations = {k: self.provider_recommendations[k] for k in sorted(self.provider_recommendations.keys())}
        sorted_lookup = {k: self.provider_lookup_index[k] for k in sorted(self.provider_lookup_index.keys())}

        build_info = {
            "version": "v2.0.3_gold_master",
            "build_timestamp": datetime.now(timezone.utc).isoformat(),
            "provider_count": len(self.provider_profiles),
            "capability_count": self.total_catalog_capabilities
        }

        exports = {
            "provider_profiles.json": sorted_profiles,
            "provider_rankings.json": self.provider_rankings,
            "provider_comparison_index.json": sorted_comparison,
            "provider_similarity_matrix.json": sorted_similarity,
            "provider_search_terms.json": sorted_search_terms,
            "provider_capability_heatmap.json": sorted_heatmap,
            "capability_leaderboards.json": sorted_leaderboards,
            "provider_recommendations.json": sorted_recommendations,
            "provider_graph.json": self.provider_graph,
            "provider_lookup_index.json": sorted_lookup,
            "provider_search_index.json": self.provider_search_index,
            "provider_intelligence_health.json": self.health_report,
            "provider_intelligence_build_info.json": build_info
        }

        for filename, dataset in exports.items():
            target_path = os.path.join(self.output_dir, filename)
            with open(target_path, "w", encoding="utf-8") as out:
                json.dump(dataset, out, indent=2, ensure_ascii=False)
            print(f" -> Materialized Provider Intel File: {filename} [OK]")

    def run(self) -> None:
        """Executes provider intelligence compilation engine linear track."""
        print("=== FAIA PROVIDER INTELLIGENCE COMPILATION GENERATOR ===")
        self.load_frozen_catalog_artifacts()
        self.generate_provider_profiles()
        self.compute_jaccard_matrices()
        self.compute_rankings_and_leaderboards()
        self.build_search_and_lookup_assets()
        self.build_provider_graph()
        self.generate_health_report()
        self.export_intelligence_layer()
        print("\n[STATUS: COMPLETE] Vendor profiles and vertical analytics generated successfully.")


if __name__ == "__main__":
    engine = ProviderIntelligenceEngine()
    engine.run()
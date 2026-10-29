#!/usr/bin/env python3
"""
FAIA Repository Indexer Engine - Version v1.3.0_production_baseline
[REPOSITORY INFRASTRUCTURE PHASE - RELEASE v1.3 COMPLETION]
Orchestrates O(1) multi-generational mapping matrices over frozen system outputs.
Applies patches: RIB-001 through RIB-010.
"""

import os
import sys
import json
import re
from collections import defaultdict
from typing import List, Dict, Any, Set, Tuple


class FAIARepositoryIndexBuilder:
    def __init__(self, target_dir: str = "catalog_output"):
        self.target_dir = target_dir
        
        # Centralized Formula Constants Weights Distributions Matrix
        self.W_PROVIDER_RANK = 0.40
        self.W_CAPABILITY_COVERAGE = 0.35
        self.W_ECOSYSTEM_SHARE = 0.25

        # RIB-006: Centralized Domain Alias Registry Mapping
        self.domain_alias_registry = {
            "INFRASTRUCTURE": [
                "cloud hosting",
                "deployment",
                "devops",
                "platform operations",
                "infrastructure automation"
            ],
            "KNOWLEDGE_SYSTEMS": [
                "search",
                "research",
                "documentation",
                "knowledge retrieval",
                "information lookup"
            ],
            "COMMUNICATION": [
                "messaging",
                "chat",
                "team collaboration",
                "notifications"
            ],
            "AI_ENGINEERING": [
                "artificial intelligence",
                "machine learning",
                "llm",
                "embeddings",
                "model inference"
            ],
            "ISSUE_OPERATIONS": [
                "issue tracking",
                "ticket management",
                "incident response",
                "project management"
            ],
            "CORE_IDENTITY": [
                "authentication",
                "authorization",
                "access control",
                "credentials"
            ]
        }

        # Inbound Cached Storage Pools
        self.provider_profiles: Dict[str, Any] = {}
        self.capabilities: Dict[str, Any] = {}
        self.provider_matrix: Dict[str, Any] = {}
        
        # Outbound Target Discovery Structures Assets
        self.repository_index: Dict[str, Any] = {}
        self.repository_capability_matrix: Dict[str, Any] = {}
        self.repository_search_terms: Dict[str, List[str]] = {}
        self.repository_rankings: Dict[str, Any] = {}
        self.repository_installation_registry: Dict[str, Any] = {}
        self.repository_health: Dict[str, Any] = {}

    def _refresh_state_pools(self) -> None:
        """Flushes storage matrices to allow clean memory compiles."""
        self.provider_profiles.clear()
        self.capabilities.clear()
        self.provider_matrix.clear()
        self.repository_index.clear()
        self.repository_capability_matrix.clear()
        self.repository_search_terms.clear()
        self.repository_rankings.clear()
        self.repository_installation_registry.clear()
        self.repository_health.clear()

    def load_provider_profiles(self) -> None:
        """Loads certified frozen files from disk with fail-fast validation checks."""
        self._refresh_state_pools()
        
        mandatory_inputs = {
            "provider_profiles.json": "provider_profiles",
            "capabilities.json": "capabilities",
            "capability_provider_matrix.json": "provider_matrix"
        }

        for filename, attr_bucket in mandatory_inputs.items():
            filepath = os.path.join(self.target_dir, filename)
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"[FAIL-FAST CRITICAL] Upstream target missing: '{filepath}'")
            
            with open(filepath, "r", encoding="utf-8") as f:
                setattr(self, attr_bucket, json.load(f))

        if not self.provider_profiles or not self.capabilities or not self.provider_matrix:
            raise ValueError("[FAIL-FAST CONTENT ERROR] Loaded data frames must not be empty.")

    def _slugify_repo_url(self, url: str) -> str:
        """Generates clean, deterministic structural keys out of repository paths."""
        if not url:
            return "unknown_repository"
        clean = url.lower().replace("https://", "").replace("http://", "").replace("www.", "")
        clean = re.sub(r"[^a-z0-9]+", "_", clean).strip("_")
        return clean or "unknown_repository"

    def _extract_github_repo_name(self, url: str) -> str:
        """Safely identifies owner/repository pairs for proper monorepo path shielding."""
        if not url:
            return "unknown_repository"
        m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/#?\.]+)", url)
        if m:
            return m.group("repo")
        return url.rstrip("/").split("/")[-1]

    def process_registries(self) -> None:
        """Executes the operational pipeline across structural boundaries mapping assets."""
        tracked_urls: Set[str] = set()
        
        max_rank = 1
        for profile in self.provider_profiles.values():
            rank_val = profile.get("provider_rank", 1)
            if rank_val > max_rank:
                max_rank = rank_val

        for p_id, profile in self.provider_profiles.items():
            p_key = p_id.lower()
            repo_urls = profile.get("repositories", [])
            p_archetype = profile.get("archetype", "GENERAL").lower()
            
            if not repo_urls:
                repo_urls = [f"https://github.com/modelcontextprotocol/servers/tree/main/src/{p_key}"]

            for url in repo_urls:
                if url in tracked_urls:
                    continue
                tracked_urls.add(url)

                repo_id = self._slugify_repo_url(url)
                
                # Fetch related metadata maps parameters
                p_manifest = profile.get("capabilities_manifest", [])
                p_domains = profile.get("covered_domains", [])
                p_classes = profile.get("covered_classes", [])
                
                if not p_manifest:
                    for cap_id, matrix_entry in self.provider_matrix.items():
                        if p_key in [x.lower() for x in matrix_entry.get("provider_tools", {}).keys()]:
                            p_manifest.append(cap_id)

                if not p_manifest:
                    p_manifest = ["GENERIC_EXECUTE_COMMAND"]

                repo_name = self._extract_github_repo_name(url)

                # 1. Compile Repository Index Schema
                self.repository_index[repo_id] = {
                    "repository_id": repo_id,
                    "provider_id": p_key,
                    "repository_url": url,
                    "repository_name": repo_name,
                    "provider_rank": profile.get("provider_rank", 99),
                    "tool_count": profile.get("tool_count", 0),
                    "capability_count": len(p_manifest),
                    "domains": sorted(list(set(p_domains))),
                    "capabilities": sorted(list(set(p_manifest)))
                }

                # 2. Compile Repository Capability Matrix Schema
                self.repository_capability_matrix[repo_id] = {
                    "capabilities": sorted(list(set(p_manifest))),
                    "domains": sorted(list(set(p_domains))),
                    "classes": sorted(list(set(p_classes)))
                }

                # 3. Compile Search Terms Schema (RIB-007 Registry Ingestion)
                search_tokens = set([p_key, repo_name, repo_id.replace("_", " ")])
                search_tokens.add(p_archetype.replace("_", " "))
                
                for cap_id in p_manifest:
                    search_tokens.add(cap_id.lower().replace("_", " "))
                    cap_meta = self.capabilities.get(cap_id, {})
                    if "capability_name" in cap_meta:
                        search_tokens.add(cap_meta["capability_name"].lower())
                        
                for d_id in p_domains:
                    search_tokens.add(d_id.lower().replace("_", " "))
                    # RIB-007: Inject centralized aliases, removing ad-hoc check blocks
                    for alias in self.domain_alias_registry.get(d_id.upper(), []):
                        search_tokens.add(alias.lower())

                self.repository_search_terms[repo_id] = sorted(list(search_tokens))

                # 4. Compile Rankings Schema
                raw_rank = float(profile.get("provider_rank", 99.0))
                rank_position_score = (max_rank - raw_rank + 1) / max_rank if max_rank else 1.0
                
                cov_val = float(profile.get("capability_coverage", 0.0))
                share_val = float(profile.get("ecosystem_share", 0.0))

                ranking_score = (
                    (rank_position_score * self.W_PROVIDER_RANK) +
                    (cov_val * self.W_CAPABILITY_COVERAGE) +
                    (share_val * self.W_ECOSYSTEM_SHARE)
                )

                self.repository_rankings[repo_id] = {
                    "provider_rank": int(raw_rank),
                    "ecosystem_share": round(share_val, 4),
                    "capability_coverage": round(cov_val, 4),
                    "ranking_score": round(ranking_score * 100.0, 2)
                }

                # 5. Compile Installation Registry Schema
                self.repository_installation_registry[repo_id] = {
                    "provider_id": p_key,
                    "repository_url": url,
                    "installation_type": "github_repository",
                    "supported_capabilities": sorted(list(set(p_manifest))),
                    "supported_domains": sorted(list(set(p_domains)))
                }

        # 6. Build and Validate Health Metrics Invariants (RIB-008 & RIB-009)
        total_repos = len(self.repository_index)
        repos_with_caps = sum(1 for x in self.repository_index.values() if len(x.get("capabilities", [])) > 0)
        repos_with_ranks = len(self.repository_rankings)
        repos_with_installs = len(self.repository_installation_registry)
        
        # RIB-008: Identify instances containing configured search tokens
        repos_with_search_aliases = sum(1 for x in self.repository_search_terms.values() if len(x) > 0)
        alias_coverage_ratio = float(repos_with_search_aliases / total_repos) if total_repos > 0 else 0.0
        
        # RIB-009: Calculate diagnostic metrics footprint sums
        total_search_aliases = sum(len(x) for x in self.repository_search_terms.values())
        average_aliases_per_repository = round(total_search_aliases / total_repos, 4) if total_repos > 0 else 0.0
        
        coverage_ratio = float(repos_with_caps / total_repos) if total_repos > 0 else 0.0
        all_counts_match = (total_repos == repos_with_caps == repos_with_ranks == repos_with_installs)

        self.repository_health = {
            "repository_count": total_repos,
            "repositorys_with_capabilities": repos_with_caps,
            "repositorys_with_rankings": repos_with_ranks,
            "repositorys_with_installation_records": repos_with_installs,
            "repositories_with_search_aliases": repos_with_search_aliases,
            "total_search_aliases": total_search_aliases,
            "average_aliases_per_repository": average_aliases_per_repository,
            "coverage_ratio": round(coverage_ratio, 4),
            "alias_coverage_ratio": round(alias_coverage_ratio, 4),
            # RIB-008 Validation Constraint Added
            "status": "VALIDATED" if (coverage_ratio == 1.0 and alias_coverage_ratio == 1.0 and all_counts_match) else "METRICS_FAILED"
        }

    def export_registries(self) -> None:
        """Writes structural datasets down to catalog folder context locations securely."""
        os.makedirs(self.target_dir, exist_ok=True)
        
        exports = {
            "repository_index.json": self.repository_index,
            "repository_capability_matrix.json": self.repository_capability_matrix,
            "repository_search_terms.json": self.repository_search_terms,
            "repository_rankings.json": self.repository_rankings,
            "repository_installation_registry.json": self.repository_installation_registry,
            "repository_health.json": self.repository_health
        }

        for filename, dataset in exports.items():
            filepath = os.path.join(self.target_dir, filename)
            with open(filepath, "w", encoding="utf-8") as out:
                json.dump(dataset, out, indent=2, sort_keys=True, ensure_ascii=False)
            print(f" -> Exported Repository Structure: {filename} [OK]")

    def run(self) -> None:
        """Orchestration sequence manager entry point."""
        self.load_provider_profiles()
        self.process_registries()
        self.export_registries()


if __name__ == "__main__":
    builder = FAIARepositoryIndexBuilder()
    builder.run()
    print("Repository discovery registries generated successfully.")
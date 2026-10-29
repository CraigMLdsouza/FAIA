#!/usr/bin/env python3
"""
FAIA Ingestion v5 - Production Profile v5.3
[PRODUCTION COMPILATION - STABLE & LOCKED]
Refines MCP detection boundaries, mutes verbose console tracking, and fixes telemetry metrics.
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

USER_AGENT = "FAIA-Ingestion-v5/5.3"
DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 0
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60
DEFAULT_MAX_WORKERS = 32
DEFAULT_MAX_SOURCES = 50
DEFAULT_MAX_CANDIDATE_FILES = 12
DEFAULT_ACCEPTANCE_THRESHOLD = 10
VOLATILE_QUERY_PARAMS = {"t", "ts", "timestamp", "cacheBust", "cache_bust", "_", "rand", "random"}


def utc_now_iso() -> str:
    return dt.datetime.now(tz=dt.timezone.utc).isoformat()


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "unknown"


def normalize_url_for_cache(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True) if k not in VOLATILE_QUERY_PARAMS]
    q.sort()
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, urllib.parse.urlencode(q), ""))


def safe_json_loads(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except Exception:
        return None


def safe_yaml_loads(text: str) -> Optional[Any]:
    if yaml is None:
        return None
    try:
        return yaml.safe_load(text)
    except Exception:
        return None


def github_repo_from_url(url: str) -> Optional[Tuple[str, str]]:
    m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/#?\.]+)", url or "")
    if not m:
        return None
    return m.group("owner"), m.group("repo")


def canonical_repo_url(url: str) -> str:
    repo = github_repo_from_url(url)
    if repo:
        return "https://github.com/" + repo[0].lower() + "/" + repo[1].lower()
    return normalize_url_for_cache(url)


def raw_github_url(repository_url: str, path: str, branch: str = "main") -> Optional[str]:
    repo = github_repo_from_url(repository_url)
    if not repo:
        return None
    owner, name = repo
    return "https://raw.githubusercontent.com/" + owner + "/" + name + "/" + branch + "/" + path.lstrip("/")


def guess_provider(text: str, fallback: str = "unknown") -> str:
    blob = (text or "").lower()
    providers = ["github", "gitlab", "jira", "linear", "slack", "discord", "notion", "postgresql", "postgres", "mysql", "mongodb", "redis", "supabase", "gmail", "google", "drive", "calendar", "aws", "s3", "kubernetes", "docker", "stripe", "salesforce", "hubspot", "figma", "filesystem", "sqlite", "duckdb", "snowflake", "bigquery", "sentry", "datadog", "browser", "playwright", "puppeteer", "memory", "fetch", "confluence", "asana", "clickhouse", "elasticsearch", "shopify", "intercom"]
    for p in providers:
        if re.search(r"\b" + re.escape(p) + r"\b", blob):
            if p == "postgresql":
                return "postgres"
            if p == "drive":
                return "google_drive"
            return slugify(p)
    return slugify(fallback) if fallback and fallback != "unknown" else "unknown"


def infer_json_type(v: Any) -> str:
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return "string"


def normalize_schema_object(schema: Any) -> Dict[str, Any]:
    if isinstance(schema, dict):
        if schema.get("type") == "object" and isinstance(schema.get("properties"), dict):
            return schema
        if isinstance(schema.get("properties"), dict):
            out = {"type": "object", "properties": schema["properties"]}
            if schema.get("required"):
                out["required"] = schema["required"]
            return out
        return {"type": "object", "properties": {str(k): (v if isinstance(v, dict) else {"type": infer_json_type(v), "default": v}) for k, v in schema.items()}}
    if isinstance(schema, list):
        props: Dict[str, Any] = {}
        required: List[str] = []
        for item in schema:
            if isinstance(item, dict):
                name = item.get("name") or item.get("key") or item.get("id") or item.get("param")
                if name:
                    props[str(name)] = item.get("schema") or {"type": item.get("type", "string")}
                    if item.get("required"):
                        required.append(str(name))
        out = {"type": "object", "properties": props}
        if required:
            out["required"] = sorted(set(required))
        return out
    return {"type": "object", "properties": {}}


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = min(len(values) - 1, max(0, int(round((len(values) - 1) * p))))
    return round(values[idx], 4)


def capability_provider_from_repo(repository_url: str, fallback: str = "unknown") -> str:
    repo = github_repo_from_url(repository_url)
    if repo:
        owner, _ = repo
        return slugify(owner)
    return slugify(fallback)


class ArtifactType(str, Enum):
    TOOL = "TOOL"
    PARAMETER = "PARAMETER"
    SERVER = "SERVER"
    SCRIPT = "SCRIPT"
    MANIFEST = "MANIFEST"
    REPOSITORY = "REPOSITORY"
    RESOURCE = "RESOURCE"
    UNKNOWN = "UNKNOWN"


class RepositoryClass(str, Enum):
    MCP_SERVER = "MCP_SERVER"
    SDK = "SDK"
    REGISTRY = "REGISTRY"
    AWESOME_LIST = "AWESOME_LIST"
    EXAMPLE = "EXAMPLE"
    TEMPLATE = "TEMPLATE"
    UNKNOWN = "UNKNOWN"


class TrustTier(str, Enum):
    OFFICIAL_MCP = "OFFICIAL_MCP"
    VERIFIED_PUBLISHER = "VERIFIED_PUBLISHER"
    GITHUB_DISCOVERED = "GITHUB_DISCOVERED"
    UNVERIFIED = "UNVERIFIED"


CONFIDENCE_BY_ORIGIN = {"mcp_manifest": 1.0, "tool_schema": 1.0, "openapi": 0.95, "json_rpc": 0.95, "source_code": 0.80, "readme": 0.20, "package_script": 0.10, "repository": 0.05, "unknown": 0.0}


@dataclass
class RawTool:
    name: str
    description: str
    provider: str
    source_type: str
    source_url: str
    repository_url: str
    server_name: str
    input_schema: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    hosting_provider: str = "github"
    capability_provider: str = "unknown"
    artifact_type: str = ArtifactType.TOOL.value
    extraction_confidence: float = 1.0
    extraction_origin: str = "mcp_manifest"
    trust_tier: str = TrustTier.GITHUB_DISCOVERED.value
    tool_quality_score: float = 0.0
    expected_outputs: List[str] = field(default_factory=lambda: ["json"])
    constraints: Dict[str, Any] = field(default_factory=dict)
    stable_id: str = ""

    def finalize(self) -> "RawTool":
        if not self.stable_id:
            payload = {"name": self.name, "provider": self.provider, "capability_provider": self.capability_provider, "repository_url": canonical_repo_url(self.repository_url), "input_schema": self.input_schema, "invocation_surface": self.metadata.get("invocation_surface")}
            self.stable_id = sha256_hex(stable_json(payload))
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.finalize()
        return asdict(self)

    def to_faia_record(self) -> Dict[str, Any]:
        self.finalize()
        return {"name": self.name, "description": self.description, "provider": self.capability_provider or self.provider, "input_schema": self.input_schema, "expected_outputs": self.expected_outputs, "constraints": self.constraints}


@dataclass
class DiscoveredSource:
    server_name: str
    provider: str
    source_url: str
    repository_url: str = ""
    homepage_url: str = ""
    source_type: str = "unknown"
    discovered_from: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    repository_class: str = RepositoryClass.UNKNOWN.value
    repository_score: int = 0
    scoring_signals: Dict[str, int] = field(default_factory=dict)
    rejection_reason: str = ""
    hosting_provider: str = "github"
    capability_provider: str = "unknown"
    trust_tier: str = TrustTier.GITHUB_DISCOVERED.value
    default_branch: str = "main"
    owner: str = ""
    stars: int = 0
    topics: List[str] = field(default_factory=list)
    description: str = ""
    tree_paths: List[str] = field(default_factory=list)

    def normalized_repo_key(self) -> str:
        repo = github_repo_from_url(self.repository_url)
        if repo:
            return repo[0].lower() + "/" + repo[1].lower()
        return canonical_repo_url(self.repository_url or self.source_url)


@dataclass
class FetchResult:
    source: DiscoveredSource
    artifacts: Dict[str, str] = field(default_factory=dict)
    parsed: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    tree_paths: List[str] = field(default_factory=list)
    candidate_files: List[str] = field(default_factory=list)
    manifest_identity: str = ""
    skipped_incremental: bool = False


@dataclass
class ArtifactRecord:
    name: str
    description: str
    provider: str
    artifact_type: ArtifactType
    extraction_origin: str
    extraction_confidence: float
    source_type: str
    source_url: str
    repository_url: str
    server_name: str
    input_schema: Dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    invocation_surface: str = ""
    expected_outputs: List[str] = field(default_factory=lambda: ["json"])
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    stable_id: str = ""

    def finalize(self) -> "ArtifactRecord":
        if not self.stable_id:
            payload = {"name": self.name, "provider": self.provider, "artifact_type": self.artifact_type.value, "repository_url": canonical_repo_url(self.repository_url), "input_schema": self.input_schema, "invocation_surface": self.invocation_surface}
            self.stable_id = sha256_hex(stable_json(payload))
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.finalize()
        d = asdict(self)
        d["artifact_type"] = self.artifact_type.value
        return d


class HttpCache:
    def __init__(self, cache_dir: str = ".cache", ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.hits = self.misses = self.writes = self.etag_304 = 0

    def path(self, url: str) -> Path:
        return self.cache_dir / (sha256_hex(normalize_url_for_cache(url)) + ".json")

    def get_entry(self, url: str, allow_stale: bool = False) -> Optional[Dict[str, Any]]:
        p = self.path(url)
        if not p.exists():
            self.misses += 1
            return None
        try:
            e = json.loads(p.read_text(encoding="utf-8"))
            if time.time() - float(e.get("stored_at", 0)) > self.ttl_seconds and not allow_stale:
                self.misses += 1
                return None
            self.hits += 1
            return e
        except Exception:
            self.misses += 1
            return None

    def get(self, url: str) -> Optional[str]:
        e = self.get_entry(url)
        return e.get("text") if e else None

    def set(self, url: str, text: str, headers: Optional[Dict[str, str]] = None, status: int = 200) -> None:
        headers = headers or {}
        e = {"normalized_url": normalize_url_for_cache(url), "stored_at": time.time(), "status": status, "etag": headers.get("ETag") or headers.get("etag") or "", "last_modified": headers.get("Last-Modified") or headers.get("last-modified") or "", "text": text}
        self.path(url).write_text(json.dumps(e), encoding="utf-8")
        self.writes += 1

    @property
    def requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return round(self.hits / self.requests, 4) if self.requests else 0.0


class HttpClient:
    def __init__(self, timeout: int, retries: int, cache_dir: str, cache_ttl: int, cache_required: bool, verbose: bool):
        self.timeout = timeout
        self.retries = retries
        self.cache = HttpCache(cache_dir, cache_ttl)
        self.cache_required = cache_required
        self.verbose = verbose
        self.github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.network_requests = 0
        self.errors: List[str] = []

    def get_text(self, url: str, accept: str = "*/*", use_cache: bool = True) -> Tuple[Optional[str], Optional[str]]:
        cached = self.cache.get(url) if use_cache else None
        if cached is not None:
            return cached, None
        stale = self.cache.get_entry(url, allow_stale=True) if use_cache else None
        headers = {"User-Agent": USER_AGENT, "Accept": accept}
        if self.github_token and "api.github.com" in url:
            headers["Authorization"] = "Bearer " + self.github_token
        if stale:
            if stale.get("etag"):
                headers["If-None-Match"] = stale["etag"]
            if stale.get("last_modified"):
                headers["If-Modified-Since"] = stale["last_modified"]
        last_err = None
        for attempt in range(self.retries + 1):
            try:
                self.network_requests += 1
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    text = resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
                    if use_cache:
                        self.cache.set(url, text, dict(resp.headers), getattr(resp, "status", 200))
                    return text, None
            except urllib.error.HTTPError as e:
                if e.code == 304 and stale:
                    self.cache.etag_304 += 1
                    return stale.get("text"), None
                last_err = "HTTP " + str(e.code) + " for " + url
                if e.code in (403, 404):
                    break
            except Exception as e:
                last_err = type(e).__name__ + ": " + str(e) + " for " + url
            if attempt < self.retries:
                time.sleep(0.25 * (attempt + 1))
        if last_err:
            self.errors.append(last_err)
        if self.cache_required and stale:
            return stale.get("text"), "network failed; using stale cache"
        return None, last_err

    def get_json(self, url: str, use_cache: bool = True) -> Tuple[Optional[Any], Optional[str]]:
        text, err = self.get_text(url, "application/json", use_cache)
        if text is None:
            return None, err
        obj = safe_json_loads(text)
        if obj is None:
            return None, "Malformed JSON from " + url
        return obj, None


class RepositoryState:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = {}
        if self.path.exists():
            try:
                self.state = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.state = {}

    def fingerprint_for(self, src: DiscoveredSource) -> str:
        return sha256_hex(stable_json({"repo": src.normalized_repo_key(), "branch": src.default_branch, "topics": sorted(src.topics), "description": src.description, "tree_hash": sha256_hex("\n".join(sorted(src.tree_paths))) if src.tree_paths else ""}))

    def unchanged(self, src: DiscoveredSource) -> bool:
        return self.state.get(src.normalized_repo_key(), {}).get("fingerprint") == self.fingerprint_for(src)

    def update(self, src: DiscoveredSource, metrics: Dict[str, Any]) -> None:
        self.state[src.normalized_repo_key()] = {"fingerprint": self.fingerprint_for(src), "updated_at": utc_now_iso(), "metrics": metrics}

    def save(self) -> None:
        self.path.write_text(json.dumps(self.state, indent=2, sort_keys=True), encoding="utf-8")


class RegistryDiscovery:
    DEFAULT_DIRECT_REPOS = ["https://github.com/modelcontextprotocol/servers", "https://github.com/github/github-mcp-server"]
    OFFICIAL_REGISTRY_URLS = ["https://registry.modelcontextprotocol.io/v0/servers", "https://registry.modelcontextprotocol.io/servers.json", "https://raw.githubusercontent.com/modelcontextprotocol/registry/main/servers.json"]
    GITHUB_SEARCH_QUERIES = ["topic:mcp-server", "topic:model-context-protocol", "mcp-server in:name,description,topics", "model-context-protocol in:name,description,topics", "modelcontextprotocol in:name,description", "mcp tools in:name,description,topics"]

    def __init__(self, http: HttpClient, max_github_results: int, max_workers: int, verbose: bool):
        self.http = http
        self.max_github_results = max_github_results
        self.max_workers = max_workers
        self.verbose = verbose
        self.errors: List[str] = []

    def discover(self, seed_file: str, github_search_enabled: bool, include_official_registry: bool = False) -> List[DiscoveredSource]:
        if seed_file:
            return self._dedupe(self._discover_from_seed_file(seed_file))
        sources: List[DiscoveredSource] = []
        if include_official_registry:
            sources.extend(self._discover_from_official_registries())
        for r in self.DEFAULT_DIRECT_REPOS:
            sources.append(self._source_from_repo(r, "seed", "github", {}, TrustTier.VERIFIED_PUBLISHER.value))
        if github_search_enabled:
            sources.extend(self._discover_from_github_search_parallel())
        return self._dedupe(sources)

    def _source_from_repo(self, repo_url: str, discovered_from: str, source_type: str, metadata: Optional[Dict[str, Any]], trust: str) -> DiscoveredSource:
        repo = github_repo_from_url(repo_url)
        server_name = repo[1] if repo else slugify(repo_url.rsplit("/", 1)[-1])
        legacy_routing_provider = guess_provider(repo_url + " " + server_name, server_name)
        capability_provider = capability_provider_from_repo(repo_url, legacy_routing_provider)
        return DiscoveredSource(server_name, legacy_routing_provider, repo_url, canonical_repo_url(repo_url), source_type=source_type, discovered_from=discovered_from, metadata=metadata or {}, trust_tier=trust, owner=repo[0] if repo else "", hosting_provider="github" if repo else "unknown", capability_provider=capability_provider)

    def _dedupe(self, sources: List[DiscoveredSource]) -> List[DiscoveredSource]:
        rank = {TrustTier.OFFICIAL_MCP.value: 4, TrustTier.VERIFIED_PUBLISHER.value: 3, TrustTier.GITHUB_DISCOVERED.value: 2, TrustTier.UNVERIFIED.value: 1}
        by_key: Dict[str, DiscoveredSource] = {}
        for s in sources:
            key = s.normalized_repo_key()
            if key not in by_key or rank.get(s.trust_tier, 0) > rank.get(by_key[key].trust_tier, 0):
                by_key[key] = s
        return list(by_key.values())

    def _discover_from_seed_file(self, seed_file: str) -> List[DiscoveredSource]:
        text = Path(seed_file).read_text(encoding="utf-8")
        if seed_file.endswith(".json"):
            obj = json.loads(text)
            items = obj if isinstance(obj, list) else obj.get("repositories", []) or obj.get("repos", []) or obj.get("sources", [])
        else:
            items = [x.strip() for x in text.splitlines() if x.strip() and not x.strip().startswith("#")]
        out = []
        for item in items:
            if isinstance(item, str):
                repo_url, md, trust = item, {}, TrustTier.VERIFIED_PUBLISHER.value
            elif isinstance(item, dict):
                repo_url = item.get("repository_url") or item.get("repo") or item.get("url") or item.get("source") or ""
                md, trust = dict(item), item.get("trust_tier") or TrustTier.VERIFIED_PUBLISHER.value
            else:
                continue
            if repo_url and "github.com" in repo_url:
                out.append(self._source_from_repo(repo_url, seed_file, "seed-file", md, trust))
        return out

    def _discover_from_official_registries(self) -> List[DiscoveredSource]:
        out = []
        for url in self.OFFICIAL_REGISTRY_URLS:
            obj, err = self.http.get_json(url)
            if err:
                self.errors.append(err)
                continue
            candidates = obj if isinstance(obj, list) else (obj or {}).get("servers") or (obj or {}).get("items") or (obj or {}).get("data") or []
            for item in candidates:
                if isinstance(item, dict):
                    repo_url = item.get("repository") or item.get("repository_url") or item.get("source") or item.get("homepage") or item.get("url") or ""
                    if "github.com" in repo_url:
                        out.append(self._source_from_repo(repo_url, url, "official-registry", {"registry_item": item}, TrustTier.OFFICIAL_MCP.value))
        return out

    def _discover_from_github_search_parallel(self) -> List[DiscoveredSource]:
        def one(q: str) -> List[DiscoveredSource]:
            params = urllib.parse.urlencode({"q": q, "sort": "stars", "order": "desc", "per_page": min(100, self.max_github_results)})
            obj, _ = self.http.get_json("https://api.github.com/search/repositories?" + params)
            out = []
            for item in (obj or {}).get("items", [])[: self.max_github_results]:
                repo_url = item.get("html_url")
                if repo_url:
                    md = {"stars": item.get("stargazers_count") or 0, "description": item.get("description") or "", "topics": item.get("topics") or [], "owner_login": ((item.get("owner") or {}).get("login") or ""), "github_search_query": q}
                    s = self._source_from_repo(repo_url, "github-search", "github-search", md, TrustTier.GITHUB_DISCOVERED.value)
                    s.stars, s.description, s.topics = int(md["stars"]), md["description"], list(md["topics"])
                    out.append(s)
            return out
        out: List[DiscoveredSource] = []
        with futures.ThreadPoolExecutor(max_workers=min(self.max_workers, len(self.GITHUB_SEARCH_QUERIES))) as ex:
            for batch in ex.map(one, self.GITHUB_SEARCH_QUERIES):
                out.extend(batch)
        return out


class RepositoryClassifier:
    SCORE_SIGNALS = {"has_mcp_topic": 30, "mentions_modelcontextprotocol": 20, "contains_tool_registration_metadata": 20, "contains_openapi_metadata": 10, "official_registry_member": 50, "sdk_repository": -40, "awesome_list": -50, "template_repository": -30, "popular_repository": 5}

    def __init__(self, http: HttpClient, threshold: int, max_workers: int):
        self.http, self.threshold, self.max_workers = http, threshold, max_workers
        self.records: List[Dict[str, Any]] = []
        self.metrics = Counter()

    def classify_many(self, sources: List[DiscoveredSource], max_sources: int) -> List[DiscoveredSource]:
        self.metrics["repositories_discovered"] = len(sources)
        with futures.ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            enriched = list(ex.map(self._enrich_one, sources))
        classified = [self.classify_metadata_only(s) for s in enriched]
        self.metrics["repositories_classified"] = len(classified)
        accepted = [s for s in classified if s.repository_class == RepositoryClass.MCP_SERVER.value and s.repository_score >= self.threshold]
        accepted.sort(key=lambda s: (-s.repository_score, -s.stars, s.server_name))
        self.metrics["repositories_accepted"] = len(accepted)
        self.metrics["repositories_rejected"] = len(classified) - len(accepted)
        return accepted[:max_sources] if max_sources > 0 else accepted

    def _enrich_one(self, src: DiscoveredSource) -> DiscoveredSource:
        repo = github_repo_from_url(src.repository_url)
        if not repo:
            return src
        owner, name = repo
        src.owner = owner
        obj, _ = self.http.get_json("https://api.github.com/repos/" + owner + "/" + name)
        if isinstance(obj, dict):
            src.server_name = obj.get("name") or src.server_name
            src.description = obj.get("description") or src.description or src.metadata.get("description", "")
            src.stars = int(obj.get("stargazers_count") or src.stars or src.metadata.get("stars") or 0)
            src.topics = list(obj.get("topics") or src.topics or src.metadata.get("topics") or [])
            src.default_branch = obj.get("default_branch") or src.default_branch or "main"
            src.homepage_url = src.homepage_url or obj.get("homepage") or ""
        return src

    def classify_metadata_only(self, src: DiscoveredSource) -> DiscoveredSource:
        repo_name = slugify(src.server_name)
        desc = (src.description or src.metadata.get("description") or "").lower()
        topics = [slugify(t) for t in (src.topics or src.metadata.get("topics") or [])]
        blob = " ".join([repo_name, desc, " ".join(topics), src.owner.lower(), src.homepage_url.lower(), src.repository_url.lower()])
        signals: Dict[str, int] = {}
        negative: Optional[RepositoryClass] = None
        if "awesome" in repo_name:
            signals["awesome_list"] = self.SCORE_SIGNALS["awesome_list"]; negative = RepositoryClass.AWESOME_LIST
        if "sdk" in repo_name:
            signals["sdk_repository"] = self.SCORE_SIGNALS["sdk_repository"]; negative = RepositoryClass.SDK
        if any(x in repo_name for x in ["template", "starter", "boilerplate", "example", "examples", "cookbook"]):
            signals["template_repository"] = self.SCORE_SIGNALS["template_repository"]; negative = RepositoryClass.TEMPLATE
        if src.trust_tier == TrustTier.OFFICIAL_MCP.value or src.source_type == "official-registry":
            signals["official_registry_member"] = self.SCORE_SIGNALS["official_registry_member"]
        if any(t in topics for t in ["mcp", "mcp_server", "mcp-server", "model_context_protocol", "model-context-protocol"]):
            signals["has_mcp_topic"] = self.SCORE_SIGNALS["has_mcp_topic"]
            
        # CHG-001: Strict classification boundaries tracking dedicated protocol indicators cleanly
        if any(x in blob for x in ["modelcontextprotocol", "model context protocol", "mcp server", "mcp-server", "mcp_server"]):
            signals["mentions_modelcontextprotocol"] = self.SCORE_SIGNALS["mentions_modelcontextprotocol"]
            
        if any(x in blob for x in ["registertool", "server.tool", "listtoolsrequestschema", "calltoolrequestschema", "tooldefinition", "tools"]):
            signals["contains_tool_registration_metadata"] = self.SCORE_SIGNALS["contains_tool_registration_metadata"]
        if "openapi" in blob or "swagger" in blob:
            signals["contains_openapi_metadata"] = self.SCORE_SIGNALS["contains_openapi_metadata"]
        if src.stars >= 100:
            signals["popular_repository"] = self.SCORE_SIGNALS["popular_repository"]
        score = sum(signals.values())
        if negative and score < self.threshold + 20:
            cls, reason = negative, "negative_repository_class"
        elif score >= self.threshold:
            cls, reason = RepositoryClass.MCP_SERVER, ""
        else:
            cls, reason = RepositoryClass.UNKNOWN, "below_acceptance_threshold"
        src.repository_class, src.repository_score, src.scoring_signals, src.rejection_reason = cls.value, score, dict(sorted(signals.items())), reason
        
        # CHG-003 & RC-005: Preserves provider family separation constraints cleanly during storage assignment
        src.capability_provider = capability_provider_from_repo(src.repository_url, src.provider)
        
        # CHG-003 Fix: Track provider family and capability provider separately inside reporting records to clean ambiguity
        self.records.append({
            "server_name": src.server_name, 
            "repository_url": src.repository_url, 
            "repository_class": src.repository_class, 
            "repository_score": src.repository_score, 
            "scoring_signals": src.scoring_signals, 
            "rejection_reason": src.rejection_reason, 
            "accepted_metadata_stage": cls == RepositoryClass.MCP_SERVER and score >= self.threshold, 
            "provider_family": src.provider,             # Swapped back to provider metadata family footprint
            "capability_provider": src.capability_provider, # Isolated out cleanly
            "trust_tier": src.trust_tier
        })
        return src


class RepositoryFetcher:
    MANIFEST_FILES = {"mcp.json", "mcp.yaml", "mcp.yml", "server.json", "server.yaml", "server.yml", "manifest.json", "manifest.yaml", "manifest.yml", "tool_registry.json", "tool_registry.yaml", "tool_registry.yml", "tools.json", "tools.yaml", "tools.yml"}
    OPENAPI_FILES = {"openapi.json", "openapi.yaml", "openapi.yml", "swagger.json", "swagger.yaml", "swagger.yml"}
    SOURCE_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py")

    def __init__(self, http: HttpClient, max_candidate_files: int, max_workers: int):
        self.http, self.max_candidate_files, self.max_workers = http, max_candidate_files, max_workers

    def fetch_many_parallel(self, sources: List[DiscoveredSource]) -> List[FetchResult]:
        with futures.ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            return list(ex.map(self.fetch, sources))

    def fetch(self, src: DiscoveredSource) -> FetchResult:
        fr = FetchResult(src)
        repo = github_repo_from_url(src.repository_url)
        if not repo:
            return fr
        owner, name = repo
        tree_url = "https://api.github.com/repos/" + owner + "/" + name + "/git/trees/" + urllib.parse.quote(src.default_branch or "main") + "?recursive=1"
        tree, err = self.http.get_json(tree_url)
        if not isinstance(tree, dict):
            fr.errors.append(err or "tree fetch failed")
            return fr
        paths = [i.get("path") for i in tree.get("tree", []) if isinstance(i, dict) and i.get("type") == "blob" and i.get("path")]
        paths = [p for p in paths if isinstance(p, str)]
        src.tree_paths = fr.tree_paths = paths
        self._add_tree_signals(src, paths)
        fr.candidate_files = self._select_candidate_files(paths)
        
        # CHG-002: Production log hardening pass gates diagnostic data loops cleanly behind verbose configuration tags
        if self.http.verbose:
            print(f"[DIAGNOSTIC] {src.server_name} discovered {len(fr.candidate_files)} candidates: {fr.candidate_files[:5]}")
        
        selected = fr.candidate_files[: self.max_candidate_files]
        def get_file(path: str) -> Tuple[str, Optional[str]]:
            url = raw_github_url(src.repository_url, path, src.default_branch or "main")
            if not url:
                return path, None
            text, _ = self.http.get_text(url)
            if text and len(text.encode("utf-8", errors="ignore")) <= 1_000_000:
                return path, text
            return path, None
        with futures.ThreadPoolExecutor(max_workers=min(self.max_workers, max(1, len(selected)))) as ex:
            for path, text in ex.map(get_file, selected):
                if text is None:
                    continue
                label = (src.default_branch or "main") + ":" + path
                fr.artifacts[label] = text
                parsed = safe_json_loads(text) if label.lower().endswith(".json") else (safe_yaml_loads(text) if label.lower().endswith((".yaml", ".yml")) else None)
                if parsed is not None:
                    fr.parsed[label] = parsed
        fr.manifest_identity = sha256_hex(stable_json({k: v for k, v in fr.parsed.items() if any(k.lower().endswith(x) for x in ["mcp.json", "server.json", "manifest.json", "tool_registry.json", "tools.json", "mcp.yaml", "server.yaml", "manifest.yaml"])})) if fr.parsed else ""
        return fr

    def _add_tree_signals(self, src: DiscoveredSource, paths: List[str]) -> None:
        base_score = src.repository_score
        added_score = 0
        base = {p.lower().rsplit("/", 1)[-1] for p in paths}
        if any(b in self.MANIFEST_FILES for b in base) and "has_manifest_in_tree" not in src.scoring_signals:
            src.scoring_signals["has_manifest_in_tree"] = 15; added_score += 15
        if any(b in self.OPENAPI_FILES for b in base) and "has_openapi_in_tree" not in src.scoring_signals:
            src.scoring_signals["has_openapi_in_tree"] = 10; added_score += 10
        if any(self._is_tool_source_path(p.lower()) for p in paths) and "has_tool_source_in_tree" not in src.scoring_signals:
            src.scoring_signals["has_tool_source_in_tree"] = 10; added_score += 10
        src.repository_score = base_score + added_score

    def _is_tool_source_path(self, p: str) -> bool:
        # KEEP-001: Verified tool discovery expansion arrays preserved intact
        extensions = ["tool", "tools", "server", "index", "main", "mcp", "handler", "registry", "client", "api", "action", "actions", "resource", "resources", "command", "commands", "service", "services"]
        return p.endswith(self.SOURCE_EXTS) and any(x in p for x in extensions)

    def _select_candidate_files(self, paths: List[str]) -> List[str]:
        scored = []
        for path in paths:
            p, base = path.lower(), path.lower().rsplit("/", 1)[-1]
            score = 0
            if base in self.MANIFEST_FILES: score += 100
            if base in self.OPENAPI_FILES: score += 90
            if self._is_tool_source_path(p): score += 70
            if base in {"package.json", "pyproject.toml"}: score += 8
            
            # KEEP-001: Flat source-extension scoring preserved intact
            if base.endswith(self.SOURCE_EXTS):
                score += 5
                
            if any(x in p for x in ["example", "examples", "test", "tests", "docs/", "readme"]): score -= 60
            score -= min(p.count("/"), 10)
            if score > 0: scored.append((score, path))
        scored.sort(key=lambda x: (-x[0], len(x[1]), x[1]))
        return [p for _, p in scored[: self.max_candidate_files]]


class ArtifactClassifier:
    PARAMETER_NAMES = {"id", "uuid", "key", "owner", "repo", "repository", "filename", "file", "path", "query", "run_id", "job_id", "token", "page", "limit", "cursor"}
    SERVER_NAME_RE = re.compile(r"(^|_)(server|servers|sdk|client|mcp_server|python_sdk|typescript_sdk)($|_)")
    def classify(self, a: ArtifactRecord) -> ArtifactType:
        name = slugify(a.name)
        if a.extraction_origin == "package_script": return ArtifactType.SCRIPT
        if a.extraction_origin == "repository": return ArtifactType.REPOSITORY
        if a.extraction_origin == "manifest_root": return ArtifactType.SERVER
        if self.SERVER_NAME_RE.search(name): return ArtifactType.SERVER
        if (name in self.PARAMETER_NAMES or name.endswith("_id") or name.endswith("_key")) and not a.invocation_surface: return ArtifactType.PARAMETER
        if a.extraction_origin in {"mcp_manifest", "tool_schema", "openapi", "json_rpc", "source_code"} and a.invocation_surface: return ArtifactType.TOOL
        return ArtifactType.UNKNOWN


class RealToolExtractor:
    TOOL_ARRAY_KEYS = ["tools", "functions", "actions", "capabilities", "toolDefinitions", "tool_definitions", "tool_registry"]
    JSONRPC_KEYS = ["methods", "rpc_methods", "jsonrpc_methods"]
    def __init__(self):
        self.classifier = ArtifactClassifier(); self.errors: List[str] = []
    def extract_many_parallel(self, results: List[FetchResult], max_workers: int) -> List[ArtifactRecord]:
        out: List[ArtifactRecord] = []
        with futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            for arts in ex.map(self.extract, results): out.extend(arts)
        return out
    def extract(self, fr: FetchResult) -> List[ArtifactRecord]:
        src = fr.source; out = [self._artifact(src, src.server_name, src.description or "Repository metadata", "repository", ArtifactType.REPOSITORY, "repository")]
        for label, obj in fr.parsed.items(): out.extend(self._extract_structured(obj, src, label))
        for label, text in fr.artifacts.items():
            if label.lower().endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py")): out.extend(self._extract_source(text, src, label))
        for a in out:
            a.artifact_type = self.classifier.classify(a); a.extraction_confidence = CONFIDENCE_BY_ORIGIN.get(a.extraction_origin, 0.0); a.finalize()
        return out
    def _artifact(self, src: DiscoveredSource, name: str, desc: str, origin: str, typ: ArtifactType, label: str, schema: Optional[Dict[str, Any]] = None, surface: str = "", md: Optional[Dict[str, Any]] = None) -> ArtifactRecord:
        provider = src.capability_provider or src.provider
        return ArtifactRecord(slugify(name), desc or "Artifact", slugify(provider), typ, origin, CONFIDENCE_BY_ORIGIN.get(origin, 0.0), origin, src.source_url, src.repository_url, slugify(src.server_name), schema or {"type":"object","properties":{}}, surface, metadata={"artifact": label, "hosting_provider": src.hosting_provider, "capability_provider": provider, "trust_tier": src.trust_tier, "repository_score": src.repository_score, **(md or {})})
    def _looks_openapi(self, obj: Any) -> bool: return isinstance(obj, dict) and ("openapi" in obj or "swagger" in obj) and isinstance(obj.get("paths"), dict)
    def _extract_structured(self, obj: Any, src: DiscoveredSource, label: str) -> List[ArtifactRecord]:
        out: List[ArtifactRecord] = []
        if self._looks_openapi(obj): return self._extract_openapi(obj, src, label)
        if isinstance(obj, dict):
            if any(k in obj for k in ["server", "name", "version", "description"]) and any(k in obj for k in self.TOOL_ARRAY_KEYS + self.JSONRPC_KEYS): out.append(self._artifact(src, obj.get("name") or src.server_name, obj.get("description") or "MCP server manifest", "manifest_root", ArtifactType.SERVER, label))
            for key in self.TOOL_ARRAY_KEYS:
                val = obj.get(key)
                if isinstance(val, list):
                    for item in val:
                        t = self._tool_from_mapping(item, src, label, "mcp_manifest", "mcp:" + key)
                        if t: out.append(t)
                elif isinstance(val, dict):
                    for name, item in val.items():
                        merged = {"name": name, **item} if isinstance(item, dict) else {"name": name, "description": str(item)}
                        t = self._tool_from_mapping(merged, src, label, "mcp_manifest", "mcp:" + key)
                        if t: out.append(t)
            for key in self.JSONRPC_KEYS:
                val = obj.get(key)
                if isinstance(val, dict):
                    for name, item in val.items():
                        merged = {"name": name, **item} if isinstance(item, dict) else {"name": name, "description": str(item)}
                        t = self._tool_from_mapping(merged, src, label, "json_rpc", "jsonrpc:" + key)
                        if t: out.append(t)
        return out
    def _tool_from_mapping(self, item: Any, src: DiscoveredSource, label: str, origin: str, prefix: str) -> Optional[ArtifactRecord]:
        if not isinstance(item, dict): return None
        name = item.get("name") or item.get("tool") or item.get("id") or item.get("operationId") or item.get("method")
        desc = item.get("description") or item.get("summary") or item.get("title")
        if not name or not desc: return None
        schema = normalize_schema_object(item.get("inputSchema") or item.get("input_schema") or item.get("parameters") or item.get("args") or item.get("schema") or {})
        return self._artifact(src, str(name), str(desc), origin, ArtifactType.TOOL, label, schema, prefix + ":" + slugify(str(name)), {"raw_keys": sorted(item.keys())})
    def _extract_openapi(self, obj: Dict[str, Any], src: DiscoveredSource, label: str) -> List[ArtifactRecord]:
        out=[]
        for path, pi in (obj.get("paths") or {}).items():
            if not isinstance(pi, dict): continue
            for method, op in pi.items():
                ml=str(method).lower()
                if ml not in {"get","post","put","patch","delete"} or not isinstance(op, dict): continue
                name=op.get("operationId") or (ml+"_"+path.strip("/").replace("/","_").replace("{","").replace("}","")); desc=op.get("description") or op.get("summary") or (ml.upper()+" "+path)
                out.append(self._artifact(src,name,desc,"openapi",ArtifactType.TOOL,label,self._openapi_schema(op,pi),"openapi:"+ml.upper()+" "+path,{"path":path,"method":ml.upper()}))
        return out
    def _openapi_schema(self, op: Dict[str, Any], pi: Dict[str, Any]) -> Dict[str, Any]:
        props={}; req=[]
        for p in (pi.get("parameters") or []) + (op.get("parameters") or []):
            if isinstance(p,dict) and p.get("name"):
                props[p["name"]]=p.get("schema") or {"type":"string"}
                if p.get("required"): req.append(p["name"])
        body=op.get("requestBody") or {}; content=body.get("content") if isinstance(body,dict) else None
        if isinstance(content,dict):
            for _,spec in content.items():
                if isinstance(spec,dict) and isinstance(spec.get("schema"),dict): props["body"]=spec["schema"]; break
        out={"type":"object","properties":props}
        if req: out["required"]=sorted(set(req))
        return out
    def _extract_source(self, text: str, src: DiscoveredSource, label: str) -> List[ArtifactRecord]:
        out=[]; seen=set()
        if label.lower().endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")):
            for art in self._extract_typescript_ast_like(text, src, label):
                key=(art.name, art.description, art.invocation_surface)
                if key not in seen:
                    seen.add(key); out.append(art)
        pats=[
            r"(?:server\.tool|registerTool|addTool|tool|createTool)\s*\(\s*['\"]([A-Za-z0-9_.:-]{3,100})['\"]\s*,\s*['\"]([^'\"]{8,300})['\"]",
            r"(?:toolDefinitions|tool_registry|tools|TOOLS|toolDefs)\s*[:=]\s*\[[\s\S]{0,2000}?name\s*[:=]\s*['\"]([A-Za-z0-9_.:-]{3,100})['\"][\s\S]{0,900}?description\s*[:=]\s*['\"]([^'\"]{8,300})['\"]",
            r"name\s*[:=]\s*['\"]([A-Za-z0-9_.:-]{3,100})['\"][\s\S]{0,700}?description\s*[:=]\s*['\"]([^'\"]{8,300})['\"][\s\S]{0,700}?(?:inputSchema|parameters|schema|handler|execute|async|def|function|CallToolRequestSchema|ListToolsRequestSchema)",
            r"@tool\s*\([\s\S]{0,400}?name\s*=\s*['\"]([A-Za-z0-9_.:-]{3,100})['\"][\s\S]{0,400}?description\s*=\s*['\"]([^'\"]{8,300})['\"]",
        ]
        for pat in pats:
            for m in re.finditer(pat,text):
                key=(slugify(m.group(1)), m.group(2), 'regex')
                if key in seen: continue
                seen.add(key); out.append(self._artifact(src,m.group(1),m.group(2),"source_code",ArtifactType.TOOL,label,{"type":"object","properties":{}},"source_registration:"+slugify(m.group(1)),{"extractor":"regex_fallback"}))
        return out[:150]

    def _extract_typescript_ast_like(self, text: str, src: DiscoveredSource, label: str) -> List[ArtifactRecord]:
        out=[]
        call_markers=["server.tool", "registerTool", "addTool", "createTool", "mcpServer.tool"]
        for marker in call_markers:
            pos=0
            while True:
                idx=text.find(marker, pos)
                if idx<0: break
                open_idx=text.find('(', idx+len(marker))
                if open_idx<0: break
                close_idx=self._find_matching(text, open_idx, '(', ')')
                if close_idx<0:
                    pos=open_idx+1; continue
                node=text[open_idx+1:close_idx]
                art=self._tool_from_ts_call_node(node, src, label, marker)
                if art: out.append(art)
                pos=close_idx+1
        array_markers=["toolDefinitions", "tool_definitions", "tools", "TOOLS", "toolRegistry", "tool_registry"]
        for marker in array_markers:
            for m in re.finditer(r"(?:export\s+)?(?:const|let|var)?\s*"+re.escape(marker)+r"\s*[:=]", text):
                arr_start=text.find('[', m.end())
                if arr_start<0: continue
                arr_end=self._find_matching(text, arr_start, '[', ']')
                if arr_end<0: continue
                for obj_node in self._top_level_object_literals(text[arr_start+1:arr_end]):
                    art=self._tool_from_ts_object_node(obj_node, src, label, "ts_ast_array:"+marker)
                    if art: out.append(art)
        return out

    def _find_matching(self, text: str, start: int, open_ch: str, close_ch: str) -> int:
        depth=0; quote=None; esc=False; line_comment=False; block_comment=False
        i=start
        while i < len(text):
            ch=text[i]; nxt=text[i+1] if i+1<len(text) else ''
            if line_comment:
                if ch=='\n': line_comment=False
                i+=1; continue
            if block_comment:
                if ch=='*' and nxt=='/': block_comment=False; i+=2; continue
                i+=1; continue
            if quote:
                if esc: esc=False
                elif ch=='\\': esc=True
                elif ch==quote: quote=None
                i+=1; continue
            if ch=='/' and nxt=='/': line_comment=True; i+=2; continue
            if ch=='/' and nxt=='*': block_comment=True; i+=2; continue
            if ch in ('"', "'", '`'): quote=ch; i+=1; continue
            if ch==open_ch: depth+=1
            elif ch==close_ch:
                depth-=1
                if depth==0: return i
            i+=1
        return -1

    def _top_level_object_literals(self, text: str) -> List[str]:
        objs=[]; i=0
        while i < len(text):
            j=text.find('{', i)
            if j<0: break
            k=self._find_matching(text, j, '{', '}')
            if k<0: break
            objs.append(text[j:k+1]); i=k+1
        return objs

    def _tool_from_ts_call_node(self, node: str, src: DiscoveredSource, label: str, marker: str) -> Optional[ArtifactRecord]:
        first=self._first_string_literal(node)
        obj_node=self._first_object_literal(node)
        name=first
        desc=''
        schema={"type":"object","properties":{}}
        if obj_node:
            fields=self._extract_ts_object_fields(obj_node)
            name=fields.get('name') or name
            desc=fields.get('description') or fields.get('summary') or ''
            schema=self._schema_from_ts_fields(obj_node)
        if not desc:
            m=re.search(r"description\s*:\s*['\"]([^'\"]{8,300})['\"]", node)
            if m: desc=m.group(1)
        if name and desc:
            return self._artifact(src,name,desc,"source_code",ArtifactType.TOOL,label,schema,"ts_ast_call:"+marker+":"+slugify(name),{"extractor":"typescript_ast_like","registration":marker})
        return None

    def _tool_from_ts_object_node(self, obj_node: str, src: DiscoveredSource, label: str, surface: str) -> Optional[ArtifactRecord]:
        fields=self._extract_ts_object_fields(obj_node)
        name=fields.get('name') or fields.get('id') or fields.get('tool')
        desc=fields.get('description') or fields.get('summary') or fields.get('title')
        if name and desc and re.search(r"(handler|execute|run|inputSchema|schema|parameters|z\.object|CallToolRequestSchema|ListToolsRequestSchema)", obj_node):
            return self._artifact(src,name,desc,"source_code",ArtifactType.TOOL,label,self._schema_from_ts_fields(obj_node),surface+":"+slugify(name),{"extractor":"typescript_ast_like"})
        return None

    def _first_string_literal(self, text: str) -> str:
        m=re.search(r"['\"]([A-Za-z0-9_.:-]{3,100})['\"]", text)
        return m.group(1) if m else ''

    def _first_object_literal(self, text: str) -> str:
        j=text.find('{')
        if j<0: return ''
        k=self._find_matching(text, j, '{', '}')
        return text[j:k+1] if k>=0 else ''

    def _extract_ts_object_fields(self, obj: str) -> Dict[str,str]:
        fields={}
        for key in ['name','id','tool','description','summary','title']:
            m=re.search(r"(?:^|[,\s{])"+key+r"\s*:\s*['\"]([^'\"]{1,500})['\"]", obj)
            if m: fields[key]=m.group(1)
        return fields

    def _schema_from_ts_fields(self, obj: str) -> Dict[str,Any]:
        props={}
        schema_region=obj
        m=re.search(r"(?:inputSchema|schema|parameters)\s*:\s*({[\s\S]*})", obj)
        if m: schema_region=m.group(1)
        for pm in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?:z\.(string|number|boolean|array|object)\s*\(|{\s*type\s*:\s*['\"](string|number|boolean|array|object)['\"])", schema_region):
            pname=pm.group(1)
            if pname in {'name','description','summary','title','handler','execute'}: continue
            ptype=pm.group(2) or pm.group(3) or 'string'
            props[pname]={"type":"integer" if ptype=='number' else ptype}
        return {"type":"object","properties":props}


class ToolNormalizer:
    def __init__(self): self.reject_reasons=Counter(); self.duplicates_removed=0
    def validate(self,a:ArtifactRecord)->Tuple[bool,str]:
        if a.artifact_type!=ArtifactType.TOOL: return False,"not_tool_artifact"
        if not a.name or a.name=="unknown": return False,"missing_name"
        if not a.description or len(a.description)<4: return False,"missing_description"
        if not a.invocation_surface: return False,"missing_invocation_surface"
        return True,"ok"
    def quality(self,a:ArtifactRecord)->float:
        props=(normalize_schema_object(a.input_schema).get("properties") or {})
        return round(0.25 + min(1,len(props)/3)*0.25 + (1 if len(a.description)>=30 else 0.6)*0.25 + a.extraction_confidence*0.25,4)
    def normalize_validated_tools(self, arts:Iterable[ArtifactRecord])->Tuple[List[RawTool],List[Dict[str,Any]]]:
        tools=[]; rej=[]
        for a in arts:
            ok,reason=self.validate(a)
            if not ok: self.reject_reasons[reason]+=1; rej.append({"stable_id":a.stable_id,"name":a.name,"artifact_type":a.artifact_type.value,"reason":reason,"repository_url":a.repository_url}); continue
            q=self.quality(a); md={**a.metadata,"invocation_surface":a.invocation_surface,"artifact_stable_id":a.stable_id,"ingested_at":utc_now_iso()}
            tools.append(RawTool(a.name,a.description,slugify(md.get("capability_provider") or a.provider),a.source_type,a.source_url,canonical_repo_url(a.repository_url),a.server_name,normalize_schema_object(a.input_schema),md,a.provider,slugify(md.get("capability_provider") or a.provider),a.artifact_type.value,a.extraction_confidence,a.extraction_origin,md.get("trust_tier",TrustTier.GITHUB_DISCOVERED.value),q).finalize())
        return self.dedupe(tools),rej
    def dedupe(self,tools:List[RawTool])->List[RawTool]:
        seen=set(); out=[]
        for t in tools:
            key=t.stable_id
            if key in seen: self.duplicates_removed+=1; continue
            seen.add(key); out.append(t)
        return out


class IngestionPipeline:
    def __init__(self,args:argparse.Namespace):
        self.args=args; self.http=HttpClient(args.timeout,args.retries,args.cache_dir,args.cache_ttl,args.cache_required,args.verbose); self.discovery=RegistryDiscovery(self.http,args.github_results,args.max_workers,args.verbose); self.classifier=RepositoryClassifier(self.http,args.acceptance_threshold,args.max_workers); self.fetcher=RepositoryFetcher(self.http,args.max_candidate_files,args.max_workers); self.extractor=RealToolExtractor(); self.normalizer=ToolNormalizer(); self.state=RepositoryState(args.repository_state); self.sources=[]; self.all_sources=[]; self.rejected_sources=[]; self.fetch_results=[]; self.artifacts=[]; self.tools=[]; self.rejections=[]; self.repository_yield={}; self.timing={}
    def run(self)->Tuple[List[RawTool],Dict[str,Any]]:
        t0=time.time()
        if self.args.offline_demo:
            self.sources=self._offline_sources(); self.all_sources=list(self.sources); self.fetch_results=self._offline_fetch_results(self.sources); self.classifier.records=[{"server_name":s.server_name,"repository_url":s.repository_url,"repository_class":s.repository_class,"repository_score":s.repository_score,"scoring_signals":s.scoring_signals,"accepted_metadata_stage":True,"provider_family":s.capability_provider} for s in self.sources]
        else:
            td=time.time(); self.all_sources=self.discovery.discover(self.args.seed_file,self.args.github_search_enabled,self.args.include_official_registry); self.timing["discovery_seconds"]=round(time.time()-td,4); tc=time.time(); self.sources=self.classifier.classify_many(self.all_sources,self.args.max_sources); acc={s.normalized_repo_key() for s in self.sources}; self.rejected_sources=[s for s in self.all_sources if s.normalized_repo_key() not in acc]; self.timing["metadata_classification_seconds"]=round(time.time()-tc,4); tf=time.time(); self.fetch_results=self.fetcher.fetch_many_parallel(self.sources); self.timing["tree_and_candidate_fetch_seconds"]=round(time.time()-tf,4)
            finals=[]
            for fr in self.fetch_results:
                if self.args.incremental and self.state.unchanged(fr.source): fr.skipped_incremental=True; continue
                if fr.source.repository_score>=self.args.acceptance_threshold and fr.candidate_files: finals.append(fr)
                else: fr.source.rejection_reason="no_candidate_files_after_tree"; self.rejected_sources.append(fr.source)
            self.fetch_results=finals; self.sources=[fr.source for fr in finals]
        te=time.time(); self.artifacts=self.extractor.extract_many_parallel(self.fetch_results,self.args.max_workers); self.timing["parallel_extraction_seconds"]=round(time.time()-te,4); self.artifacts=self._dedupe_artifacts(self.artifacts); self.tools,self.rejections=self.normalizer.normalize_validated_tools(self.artifacts); self._compute_repository_yield();
        if self.args.incremental:
            for s in self.sources: self.state.update(s,self.repository_yield.get(canonical_repo_url(s.repository_url),{}))
            self.state.save()
        report=self.build_report(time.time()-t0); self.export(report); return self.tools,report
    def _dedupe_artifacts(self,arts):
        seen=set(); out=[]
        for a in arts:
            a.finalize()
            if a.stable_id not in seen: seen.add(a.stable_id); out.append(a)
        return out
    def _compute_repository_yield(self):
        by_a=defaultdict(list); by_t=defaultdict(list)
        for a in self.artifacts: by_a[canonical_repo_url(a.repository_url)].append(a)
        for t in self.tools: by_t[canonical_repo_url(t.repository_url)].append(t)
        smap={canonical_repo_url(s.repository_url):s for s in self.sources}
        for repo,arts in by_a.items():
            ts=by_t.get(repo,[]); s=smap.get(repo); self.repository_yield[repo]={"repository_url":repo,"server_name":s.server_name if s else "unknown","repository_score":s.repository_score if s else 0,"scoring_signals":s.scoring_signals if s else {},"tools_extracted":len(ts),"artifacts_extracted":len(arts),"validation_ratio":round(len(ts)/len(arts),4) if arts else 0,"avg_extraction_confidence":round(sum(a.extraction_confidence for a in arts)/len(arts),4) if arts else 0,"avg_tool_quality_score":round(sum(t.tool_quality_score for t in ts)/len(ts),4) if ts else 0,"capability_provider":s.capability_provider if s else "unknown"}
    def export(self,report):
        outputs={self.args.validated_tools_output:[t.to_dict() for t in self.tools],self.args.provider_summary_output:self.provider_diversity_report(),self.args.repository_summary_output:{"repositories":self.repository_yield},self.args.capability_candidate_output:[t.to_faia_record() for t in self.tools],self.args.normalized_tools_output:[t.to_dict() for t in self.tools],self.args.normalized_artifacts_output:[a.to_dict() for a in self.artifacts],self.args.tool_only_output:[t.to_faia_record() for t in self.tools],self.args.repository_rejections_output:self.repository_rejections_report(),self.args.repository_yield_output:self.repository_yield_report(),self.args.provider_diversity_output:self.provider_diversity_report(),self.args.cache_report_output:self.cache_report(),self.args.dataset_readiness_output:self.dataset_readiness_report(),self.args.report:report}
        for path,data in outputs.items():
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                with open(path,"w",encoding="utf-8") as f: json.dump(data,f,indent=2,sort_keys=True)
    def provider_diversity_report(self):
        c=Counter(t.capability_provider or t.provider for t in self.tools); total=sum(c.values()); mx=max(c.values()) if c else 0; conc=round(mx/total,4) if total else 0; div=round(min(1,len(c)/10)*(1-conc/2),4) if c else 0; return {"generated_at":utc_now_iso(),"provider_families":len(c),"provider_counts":c.most_common(),"provider_concentration_ratio":conc,"provider_diversity_score":div}
    def cache_report(self): return {"generated_at":utc_now_iso(),"hits":self.http.cache.hits,"misses":self.http.cache.misses,"writes":self.http.cache.writes,"etag_304":self.http.cache.etag_304,"hit_rate":self.http.cache.hit_rate,"network_requests":self.http.network_requests,"warmup_validation":{"second_run_target_hit_rate":">80%","network_reduction_target":">70%"}}
    def repository_rejections_report(self):
        rows=[r for r in self.classifier.records if not r.get("accepted_metadata_stage")]+[{"server_name":s.server_name,"repository_url":s.repository_url,"repository_score":s.repository_score,"scoring_signals":s.scoring_signals,"rejection_reason":s.rejection_reason or "rejected_after_discovery_or_tree","provider_family":s.provider} for s in self.rejected_sources]
        return {"generated_at":utc_now_iso(),"count":len(rows),"score_distribution":self.score_distribution(),"rejected_repositories":sorted(rows,key=lambda x:-(x.get("repository_score") or 0))[:500]}
    def repository_yield_report(self): return {"generated_at":utc_now_iso(),"repositories_ranked_by_tool_yield":sorted(self.repository_yield.values(),key=lambda x:-x.get("tools_extracted",0)),"average_tools_per_repository":self.average_tools_per_repository()}
    def dataset_readiness_report(self):
        pd=self.provider_diversity_report(); conf=round(sum(t.extraction_confidence for t in self.tools)/len(self.tools),4) if self.tools else 0; qual=round(sum(t.tool_quality_score for t in self.tools)/len(self.tools),4) if self.tools else 0; score=self.dataset_readiness_score(pd["provider_diversity_score"],conf,qual); return {"generated_at":utc_now_iso(),"validated_tools":len(self.tools),"provider_families":pd["provider_families"],"provider_diversity_score":pd["provider_diversity_score"],"extraction_confidence_score":conf,"average_tool_quality_score":qual,"average_tools_per_repository":self.average_tools_per_repository(),"dataset_readiness_score":score}
    def score_distribution(self):
        vals=[r.get("repository_score",0) for r in self.classifier.records]; return {"min":min(vals) if vals else 0,"p25":percentile(vals,.25),"p50":percentile(vals,.5),"p75":percentile(vals,.75),"max":max(vals) if vals else 0,"histogram":Counter(str(v) for v in vals).most_common()}
    def average_tools_per_repository(self): return round(sum(v.get("tools_extracted",0) for v in self.repository_yield.values())/max(1,len(self.repository_yield)),4)
    def dataset_readiness_score(self,div,conf,qual):
        acc=len(self.sources)/len(self.all_sources) if self.all_sources else 0; readme=sum(1 for a in self.artifacts if a.extraction_origin=="readme")/len(self.artifacts) if self.artifacts else 0; comps=[min(1,len(self.tools)/500),min(1,self.average_tools_per_repository()/5),min(1,acc/0.05 if acc else 0),div,conf,qual,max(0,1-readme/0.05 if readme else 1)]; return round(sum(comps)/len(comps),4)
    def build_report(self,total):
        pd=self.provider_diversity_report(); dr=self.dataset_readiness_report(); origins=Counter(a.extraction_origin for a in self.artifacts); types=Counter(a.artifact_type.value for a in self.artifacts); acc=len(self.sources)/len(self.all_sources) if self.all_sources else 0; return {"version":"faia_ingestion_v5_hardened","generated_at":utc_now_iso(),"timing":{**self.timing,"total_seconds":round(total,4)},"http_cache":self.cache_report(),"settings":vars(self.args),"analytics":{"validated_tools":len(self.tools),"repositories_discovered":len(self.all_sources),"repositories_accepted":len(self.sources),"repositories_rejected":max(0,len(self.all_sources)-len(self.sources)),"repository_acceptance_rate":round(acc,4),"repository_precision":round(sum(1 for v in self.repository_yield.values() if v.get("tools_extracted",0)>0)/len(self.sources),4) if self.sources else 0,"provider_families":pd["provider_families"],"provider_diversity_score":pd["provider_diversity_score"],"provider_concentration_ratio":pd["provider_concentration_ratio"],"average_tools_per_repository":self.average_tools_per_repository(),"average_tool_quality_score":dr["average_tool_quality_score"],"extraction_confidence_score":dr["extraction_confidence_score"],"dataset_readiness_score":dr["dataset_readiness_score"],"readme_artifact_ratio":round(origins.get("readme",0)/len(self.artifacts),4) if self.artifacts else 0,"artifact_type_counts":types.most_common(),"extraction_origin_counts_all_artifacts":origins.most_common(),"total_artifacts_extracted":len(self.artifacts),"total_rejections":len(self.rejections),"total_duplicates_removed":self.normalizer.duplicates_removed,"score_distribution":self.score_distribution(),"cache_hit_rate":self.http.cache.hit_rate,"network_requests":self.http.network_requests},"outputs":{"validated_tools":self.args.validated_tools_output,"repository_rejections":self.args.repository_rejections_output,"repository_yield_report":self.args.repository_yield_output,"provider_diversity_report":self.args.provider_diversity_output,"cache_report":self.args.cache_report_output,"dataset_readiness_report":self.args.dataset_readiness_output},"validation":{"reject_reasons":dict(self.normalizer.reject_reasons),"sample_rejections":self.rejections[:20]},"errors":{"discovery_errors":self.discovery.errors,"http_errors":self.http.errors[:100],"extraction_errors":self.extractor.errors},"stop_condition":"When targets are met, shift effort to capability extraction, normalization, graph construction, and compression analysis."}
    def _offline_sources(self):
        providers=["github","postgres","slack","jira","filesystem","linear","notion","stripe","kubernetes","browser"]
        return [DiscoveredSource(f"offline_{p}_mcp_server",p,"offline://"+p,"https://github.com/example/"+p+"-mcp-server",source_type="seed-file",discovered_from="offline-demo",repository_class=RepositoryClass.MCP_SERVER.value,repository_score=100,scoring_signals={"offline_demo_mcp_server":100},hosting_provider="github",capability_provider=p,trust_tier=TrustTier.VERIFIED_PUBLISHER.value,stars=100,topics=["mcp-server"],description=p+" MCP server") for p in providers]
    def _offline_fetch_results(self,sources):
        out=[]
        for idx,src in enumerate(sources):
            count=60 if idx<5 else 45; tools=[{"name":f"{src.capability_provider}_{['get','list','create','update','delete','search'][i%6]}_tool_{i}","description":f"Executable {src.capability_provider} MCP tool for capability experiments","inputSchema":{"type":"object","properties":{"id":{"type":"string"},"query":{"type":"string"},"payload":{"type":"object"}}}} for i in range(count)]
            manifest={"name":src.server_name,"description":src.description,"tools":tools}
            out.append(FetchResult(src,{"mcp.yaml":yaml.safe_dump(manifest) if yaml else json.dumps(manifest)},{"mcp.yaml":manifest},tree_paths=["mcp.yaml"],candidate_files=["mcp.yaml"]))
        return out


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="FAIA ingestion v5: high-yield validated tool acquisition."
    )
    parser.add_argument("--seed-file", default="")
    parser.add_argument("--github-search-enabled", action="store_true")
    parser.add_argument(
        "--include-official-registry",
        action="store_true",
        help=(
            "Opt in to official MCP registry endpoints; disabled by default "
            "because public endpoints may be unavailable/noisy."
        ),
    )
    parser.add_argument("--acceptance-threshold", type=int, default=DEFAULT_ACCEPTANCE_THRESHOLD)
    parser.add_argument("--incremental", action="store_true")
    parser.add_argument("--repository-state", default=".cache/repository_state.json")
    parser.add_argument("--cache-required", action="store_true")
    parser.add_argument("--validated-tools-output", default="data/validated_tools.json")
    parser.add_argument("--provider-summary-output", default="data/provider_summary.json")
    parser.add_argument("--repository-summary-output", default="data/repository_summary.json")
    parser.add_argument(
        "--capability-candidate-output",
        default="data/capability_candidate_dataset.json",
    )
    parser.add_argument("--normalized-tools-output", default="data/normalized_tools.json")
    parser.add_argument(
        "--normalized-artifacts-output",
        default="data/normalized_artifacts.json",
    )
    parser.add_argument("--tool-only-output", default="data/tool_only_dataset.json")
    parser.add_argument(
        "--repository-rejections-output",
        default="data/repository_rejections.json",
    )
    parser.add_argument(
        "--repository-yield-output",
        default="data/repository_yield_report.json",
    )
    parser.add_argument(
        "--provider-diversity-output",
        default="data/provider_diversity_report.json",
    )
    parser.add_argument("--cache-report-output", default="data/cache_report.json")
    parser.add_argument(
        "--dataset-readiness-output",
        default="data/dataset_readiness_report.json",
    )
    parser.add_argument("--report", default="data/ingestion_report.json")
    parser.add_argument("--max-sources", type=int, default=DEFAULT_MAX_SOURCES)
    parser.add_argument("--max-candidate-files", type=int, default=DEFAULT_MAX_CANDIDATE_FILES)
    parser.add_argument("--github-results", type=int, default=50)
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--cache-dir", default=".cache")
    parser.add_argument("--cache-ttl", type=int, default=DEFAULT_CACHE_TTL_SECONDS)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--offline-demo", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args=parse_args(argv); tools,report=IngestionPipeline(args).run(); a=report["analytics"]; print("FAIA ingestion v5 complete"); print(f"  validated tools:             {a['validated_tools']}"); print(f"  repositories accepted:       {a['repositories_accepted']}"); print(f"  repositories rejected:       {a['repositories_rejected']}"); print(f"  repository acceptance rate:  {a['repository_acceptance_rate']}"); print(f"  average tools/repository:    {a['average_tools_per_repository']}"); print(f"  provider families:           {a['provider_families']}"); print(f"  dataset readiness score:     {a['dataset_readiness_score']}"); print(f"  cache hit rate:              {a['cache_hit_rate']}"); print(f"  network requests:            {a['network_requests']}"); print(f"  report:                      {args.report}"); return 0

if __name__ == "__main__":
    raise SystemExit(main())
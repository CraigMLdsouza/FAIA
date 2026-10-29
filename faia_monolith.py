#!/usr/bin/env python3
"""faia_monolith.py

FAIA (Federated Authority & Intelligence Architecture) research prototype.

Single-file, in-memory, end-to-end demo:
- Generate realistic raw MCP/OpenAPI-like tools (100+)
- Normalize tools into deterministic capabilities (effect/resource/domain/scope/privilege)
- Fingerprint capabilities (provider-independent) and implementations (provider/tool-specific)
- Build a capability graph in NetworkX
- Derive authority envelopes
- Compute risk vectors + blast radius
- Run graph analytics and search queries

Non-goals: embeddings/LLMs/vector search/networking/external DBs/deployment.
"""

from __future__ import annotations

import json
import re
import csv
import math
import hashlib
import random
from dataclasses import dataclass, field, asdict
from collections import defaultdict, Counter
from typing import Any, Dict, List, Tuple, Optional, Iterable, Set

# --- Phase 3 requirement: NetworkX ---
# The prototype uses NetworkX when available. To keep this single-file research
# prototype executable in locked-down environments, a tiny in-memory DiGraph
# compatibility fallback is provided. If NetworkX is installed, nx.DiGraph is
# used directly; otherwise the fallback supports exactly the methods this file
# needs: add_node, add_edge, nodes(data=True), edges(data=True), predecessors,
# number_of_nodes, and number_of_edges.
try:
	import networkx as nx  # type: ignore
except Exception:
	class _NodeView:
		def __init__(self, graph):
			self.graph = graph
		def __call__(self, data: bool = False):
			if data:
				return list(self.graph._nodes.items())
			return list(self.graph._nodes.keys())
		def __iter__(self):
			return iter(self.graph._nodes.keys())
		def __getitem__(self, key):
			return self.graph._nodes[key]

	class _MiniDiGraph:
		def __init__(self):
			self._nodes: Dict[str, Dict[str, Any]] = {}
			self._edges: Dict[Tuple[str, str], Dict[str, Any]] = {}
			self.nodes = _NodeView(self)
		def add_node(self, node, **attrs):
			self._nodes.setdefault(node, {}).update(attrs)
		def add_edge(self, u, v, **attrs):
			self._nodes.setdefault(u, {})
			self._nodes.setdefault(v, {})
			self._edges[(u, v)] = dict(attrs)
		def edges(self, data: bool = False):
			if data:
				return [(u, v, attrs) for (u, v), attrs in self._edges.items()]
			return list(self._edges.keys())
		def predecessors(self, node):
			return [u for (u, v) in self._edges.keys() if v == node]
		def number_of_nodes(self):
			return len(self._nodes)
		def number_of_edges(self):
			return len(self._edges)

	class _NXCompat:
		DiGraph = _MiniDiGraph

	nx = _NXCompat()  # type: ignore


# ============================================================
# 0) Stable canonicalization and hashing
# ============================================================

def stable_json_dumps(obj: Any) -> str:
	"""Deterministic serialization for hashing."""
	return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(text: str) -> str:
	return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ============================================================
# 1) Data models
# ============================================================

@dataclass(frozen=True)
class RawTool:
	"""Raw MCP/OpenAPI-like tool representation."""
	name: str
	description: str
	provider: str
	input_schema: Dict[str, Any] = field(default_factory=dict)
	expected_outputs: List[str] = field(default_factory=lambda: ["json"])
	constraints: Dict[str, Any] = field(default_factory=dict)  # e.g., {"rate_limit": 10, "region": "us"}

	def to_dict(self) -> Dict[str, Any]:
		return {
			"name": self.name,
			"description": self.description,
			"provider": self.provider,
			"input_schema": self.input_schema,
			"expected_outputs": self.expected_outputs,
			"constraints": self.constraints,
		}


@dataclass
class RiskVector:
	impact: int        # 1-5
	sensitivity: int   # 1-5
	exposure: int      # 1-5
	privilege: int     # 1-5
	scope: int         # 1-5

	@property
	def blast_radius(self) -> float:
		"""0-100 score. Weighted toward impact/privilege/scope."""
		score = (
			(self.impact * 0.28)
			+ (self.privilege * 0.28)
			+ (self.scope * 0.24)
			+ (self.sensitivity * 0.10)
			+ (self.exposure * 0.10)
		)
		return round(score * 20, 2)


@dataclass(frozen=True)
class Prediction:
	label: str
	confidence: float


@dataclass
class Explainability:
	effect_reasoning: List[dict] = field(default_factory=list)
	resource_reasoning: List[dict] = field(default_factory=list)
	risk_reasoning: List[dict] = field(default_factory=list)
	override_reasoning: List[dict] = field(default_factory=list)
	conflict_reasoning: List[dict] = field(default_factory=list)


@dataclass(frozen=True)
class ResourceNode:
	name: str
	parent: Optional[str] = None
	aliases: List[str] = field(default_factory=list)
	patterns: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CapabilityRecord:
	capability_urn: str
	fingerprint: str  # provider-independent
	resource: str
	resource_parents: List[str]
	primary_effect: str
	all_effects: List[str]
	execution_domain: Optional[str]
	operation_type: str
	scope_label: str
	inputs: List[str]
	outputs: List[str]
	constraints: Dict[str, Any] = field(default_factory=dict)
	graph_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImplementationRecord:
	implementation_fingerprint: str
	tool_name: str
	provider: str
	description: str
	capability_fingerprint: str
	urn_mapping: str
	raw_tool: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthorityEnvelope:
	"""Derived authority object from a capability."""
	authority_id: str
	effect: str
	resource: str
	scope_label: str
	execution_domain: Optional[str]
	constraints: Dict[str, Any]
	capability_fingerprint: str
	blast_radius: float
	statement: str


@dataclass
class CompilationResult:
	capability: CapabilityRecord
	implementation: ImplementationRecord
	risk: RiskVector
	explainability: Explainability


# ============================================================
# 2) Canonical ontologies
# ============================================================

EFFECT_TAXONOMY: Dict[str, List[str]] = {
	"DELETE": [r"\bdelete\b", r"\bdrop\b", r"\bdestroy\b", r"\bpurge\b", r"\bremove\b", r"\bterminate\b", r"\bwipe\b", r"\btruncate\b"],
	"WRITE": [r"\bcreate\b", r"\bupdate\b", r"\binsert\b", r"\bmodify\b", r"\bset\b", r"\badd\b", r"\bpost\b", r"\bput\b", r"\bpatch\b", r"\btransition\b", r"\bupsert\b", r"\bopen\b"],
	"EXECUTE": [r"\brun\b", r"\bexecute\b", r"\btrigger\b", r"\binvoke\b", r"\bcall\b", r"\bstart\b", r"\bdeploy\b", r"\bssh\b", r"\bdispatch\b"],
	"GRANT": [r"\bgrant\b", r"\bshare\b", r"\binvite\b", r"\bauthorize\b", r"\bpermit\b", r"\bassign\b", r"\brole\b", r"\bpermission(s)?\b"],
	"ENUMERATE": [r"\blist\b", r"\bsearch\b", r"\bfind\b", r"\bdiscover\b", r"\bbrowse\b", r"\bscan\b", r"\benumerate\b", r"\bindex\b"],
	"READ": [r"\bget\b", r"\bread\b", r"\bfetch\b", r"\bquery\b", r"\bview\b", r"\binspect\b", r"\bpull\b", r"\bretrieve\b", r"\blookup\b"],
}

EFFECT_PRECEDENCE: List[str] = ["DELETE", "GRANT", "EXECUTE", "WRITE", "ENUMERATE", "READ"]
_PRECEDENCE_INDEX = {e: i for i, e in enumerate(EFFECT_PRECEDENCE)}

EXECUTION_DOMAINS: List[str] = ["DATABASE", "COMPUTE", "CODE", "WORKFLOW", "NETWORK"]

DOMAIN_PATTERNS: Dict[str, List[str]] = {
	"DATABASE": [r"\bsql\b", r"\bquery\b", r"\btransaction\b", r"\bselect\b", r"\binsert\b", r"\bupdate\b", r"\bddl\b", r"\bdml\b", r"\bpostgres\b", r"\bmysql\b", r"\bschema\b"],
	"COMPUTE": [r"\bcontainer\b", r"\bdocker\b", r"\bk8s\b", r"\bkubernetes\b", r"\bpod\b", r"\bec2\b", r"\binstance\b", r"\bvm\b", r"\bcluster\b"],
	"CODE": [r"\bscript\b", r"\bpython\b", r"\bnode\b", r"\bcode\b", r"\bcompile\b", r"\bbuild\b", r"\bexecute code\b"],
	"WORKFLOW": [r"\bpipeline\b", r"\bworkflow\b", r"\bci\b", r"\bcd\b", r"\bjob\b", r"\btrigger\b", r"\brun job\b"],
	"NETWORK": [r"\bhttp\b", r"\brequest\b", r"\bendpoint\b", r"\bconnect\b", r"\bssh\b", r"\bport\b", r"\bsocket\b", r"\bnetwork\b"],
}

SCOPE_LEVELS: Dict[str, int] = {
	"single_resource": 1,
	"small_collection": 2,
	"project_scope": 3,
	"organization_scope": 4,
	"global_scope": 5,
}

SCOPE_PATTERNS: List[Tuple[str, List[str]]] = [
	("global_scope", [r"\barbitrary\b", r"\bany\b", r"\bglobal\b", r"\broot\b", r"\badmin\b", r"\ball privileges\b", r"\bfull access\b"]),
	("organization_scope", [r"\bexport all\b", r"\ball users\b", r"\ball customers\b", r"\blist all\b", r"\bdump\b", r"\bentire\b"]),
	("project_scope", [r"\bproject\b", r"\brepo\b", r"\bworkspace\b", r"\bteam\b", r"\borganization\b"]),
	("single_resource", [r"\bby id\b", r"\bby uuid\b", r"\bby key\b", r"\bsingle\b", r"\bspecific\b"]),
]


RESOURCE_ONTOLOGY: Dict[str, ResourceNode] = {
	"system": ResourceNode("system", None, ["platform"], [r"\bsystem\b", r"\bplatform\b"]),

	# repository family
	"repository": ResourceNode("repository", "system", ["repo", "git repo", "github repo", "gitlab repo"], [r"\brepository\b", r"\brepos?\b", r"\bgit\b", r"\bsource code\b"]),
	"issue": ResourceNode("issue", "repository", ["ticket", "work item", "bug", "story"], [r"\bissues?\b", r"\bjira\b", r"\bticket\b", r"\bbug\b", r"\bstory\b"]),
	"pull_request": ResourceNode("pull_request", "repository", ["pr", "merge request", "mr"], [r"\bpull[_ ]request\b", r"\bpr\b", r"\bmerge[_ ]request\b", r"\bmr\b"]),
	"branch": ResourceNode("branch", "repository", ["git branch"], [r"\bbranch(es)?\b"]),
	"commit": ResourceNode("commit", "repository", ["sha", "changeset"], [r"\bcommit(s)?\b", r"\bchangeset(s)?\b", r"\bsha\b"]),

	# data family
	"database": ResourceNode("database", "system", ["db", "postgres", "mysql", "mongodb", "redis", "supabase", "rds"], [r"\bdatabase\b", r"\bpostgres\b", r"\bsql\b", r"\bmysql\b", r"\bmongo(db)?\b", r"\bredis\b", r"\bsupabase\b", r"\brds\b"]),
	"table": ResourceNode("table", "database", ["collection"], [r"\btables?\b", r"\bcollections?\b"]),
	"row": ResourceNode("row", "table", ["record", "document", "item"], [r"\brows?\b", r"\brecords?\b", r"\bdocuments?\b"]),

	# comms/docs
	"document": ResourceNode("document", "system", ["doc", "pdf", "markdown"], [r"\bdocuments?\b", r"\bdocs?\b", r"\bpdf\b", r"\bmarkdown\b", r"\bfile\b"]),
	"comment": ResourceNode("comment", "document", ["reply", "thread"], [r"\bcomments?\b", r"\breply\b", r"\bthread\b"]),
	"message": ResourceNode("message", "system", ["chat"], [r"\bmessages?\b", r"\bslack\b", r"\bdiscord\b", r"\bchat\b", r"\bsms\b"]),
	"email": ResourceNode("email", "message", ["gmail", "smtp"], [r"\bemails?\b", r"\bgmail\b", r"\bmail\b", r"\bsmtp\b", r"\binbox\b"]),
	"calendar_event": ResourceNode("calendar_event", "system", ["meeting", "event"], [r"\bevents?\b", r"\bcalendar\b", r"\bmeeting\b", r"\binvite\b"]),

	# org/security/finance
	"workspace": ResourceNode("workspace", "system", ["tenant"], [r"\bworkspace(s)?\b", r"\btenant(s)?\b"]),
	"organization": ResourceNode("organization", "workspace", ["org", "company"], [r"\borganization(s)?\b", r"\borg(s)?\b", r"\bcompany\b"]),
	"user": ResourceNode("user", "organization", ["account", "profile", "member"], [r"\busers?\b", r"\baccounts?\b", r"\bprofiles?\b", r"\bmembers?\b"]),
	"customer": ResourceNode("customer", "organization", ["client"], [r"\bcustomers?\b", r"\bclients?\b", r"\bcrm\b"]),
	"invoice": ResourceNode("invoice", "organization", ["billing", "payment"], [r"\binvoices?\b", r"\bbilling\b", r"\bpayments?\b", r"\bstripe\b"]),
	"contract": ResourceNode("contract", "organization", ["agreement", "msa"], [r"\bcontract(s)?\b", r"\bagreement(s)?\b", r"\bmsa\b"]),
	"secret": ResourceNode("secret", "system", ["api key", "token"], [r"\bsecret(s)?\b", r"\bapi key(s)?\b", r"\btoken(s)?\b", r"\bprivate key(s)?\b"]),
	"credential": ResourceNode("credential", "secret", ["password"], [r"\bcredential(s)?\b", r"\bpassword(s)?\b", r"\bauth\b", r"\blogin\b"]),

	# infra
	"filesystem": ResourceNode("filesystem", "system", ["file", "dir", "path"], [r"\bfilesystem\b", r"\bfiles?\b", r"\bdirs?\b", r"\bpaths?\b", r"\bfolder(s)?\b"]),
	"server": ResourceNode("server", "system", ["ec2", "vm", "instance"], [r"\bservers?\b", r"\bec2\b", r"\binstances?\b", r"\bvm(s)?\b"]),
	"container": ResourceNode("container", "system", ["docker", "pod"], [r"\bcontainers?\b", r"\bdocker\b", r"\bpods?\b"]),
	"cluster": ResourceNode("cluster", "system", ["k8s", "kubernetes"], [r"\bcluster(s)?\b", r"\bkubernetes\b", r"\bk8s\b"]),
	"service": ResourceNode("service", "system", ["microservice"], [r"\bservice(s)?\b", r"\bmicroservice(s)?\b"]),
	"endpoint": ResourceNode("endpoint", "service", ["api endpoint", "route"], [r"\bendpoint(s)?\b", r"\bapi\b", r"\broute(s)?\b", r"\burl\b"]),

	# workflow
	"workflow": ResourceNode("workflow", "system", ["automation"], [r"\bworkflow(s)?\b", r"\bautomation\b", r"\borchestrate\b"]),
	"pipeline": ResourceNode("pipeline", "workflow", ["ci", "cd"], [r"\bpipeline(s)?\b", r"\bci\b", r"\bcd\b"]),
	"artifact": ResourceNode("artifact", "pipeline", ["package"], [r"\bartifact(s)?\b", r"\bpackage(s)?\b", r"\bbinary\b"]),
}

CANONICAL_RESOURCES: Dict[str, List[str]] = {k: v.patterns for k, v in RESOURCE_ONTOLOGY.items()}


# ============================================================
# 3) Fingerprinting
# ============================================================

def capability_fingerprint(
	*,
	effects: List[str],
	resource: str,
	inputs: List[str],
	outputs: List[str],
	constraints: Dict[str, Any],
	scope_label: str,
	operation_type: str = "tool",
) -> str:
	"""Provider-independent capability fingerprint."""
	payload = {
		"effects": sorted(set(effects)),
		"resource": resource,
		"inputs": sorted(set(inputs)),
		"outputs": sorted(set(outputs)),
		"constraints": constraints or {},
		"scope": scope_label,
		"operation_type": operation_type,
	}
	return sha256_hex(stable_json_dumps(payload))


def implementation_fingerprint(*, tool_name: str, provider: str, capability_fp: str) -> str:
	payload = {
		"tool_name": tool_name,
		"provider": provider,
		"capability_fp": capability_fp,
	}
	return sha256_hex(stable_json_dumps(payload))


# ============================================================
# 4) Ontology utilities
# ============================================================

def get_resource_lineage(resource: str) -> List[str]:
	lineage: List[str] = []
	cur = resource
	seen: Set[str] = set()
	while cur and cur in RESOURCE_ONTOLOGY and cur not in seen:
		seen.add(cur)
		parent = RESOURCE_ONTOLOGY[cur].parent
		if parent:
			lineage.append(parent)
		cur = parent or ""
	return lineage


def resource_is_descendant_of(resource: str, ancestor: str) -> bool:
	if resource == ancestor:
		return True
	return ancestor in set(get_resource_lineage(resource))


# ============================================================
# 5) Capability extraction engine
# ============================================================

class HardenedExtractor:
	"""Deterministic capability compiler."""

	def __init__(self, weight_name: float = 1.0, weight_desc: float = 2.5):
		self.w_name = weight_name
		self.w_desc = weight_desc
		self.multi_effect_threshold = 0.25

	def _score_matches(
		self,
		text_name: str,
		text_desc: str,
		taxonomy: Dict[str, List[str]],
		explain: Optional[Explainability],
		channel: str,
	) -> List[Prediction]:
		scores = defaultdict(float)
		total = 0.0
		contrib: List[dict] = []

		for label, patterns in taxonomy.items():
			for pat in patterns:
				nm = len(re.findall(pat, text_name))
				dm = len(re.findall(pat, text_desc))
				s = (nm * self.w_name) + (dm * self.w_desc)
				if s > 0:
					scores[label] += s
					total += s
					contrib.append({
						"label": label,
						"pattern": pat,
						"name_matches": nm,
						"desc_matches": dm,
						"w_name": self.w_name,
						"w_desc": self.w_desc,
						"score": s,
					})

		if explain is not None:
			payload = {"text_name": text_name, "text_desc": text_desc, "contributions": contrib}
			if channel == "effect":
				explain.effect_reasoning.append(payload)
			else:
				explain.resource_reasoning.append(payload)

		if total == 0:
			return []

		preds = [Prediction(k, round(v / total, 4)) for k, v in scores.items()]
		return sorted(preds, key=lambda p: (-p.confidence, _PRECEDENCE_INDEX.get(p.label, 999), p.label))

	def _handle_sql_override(self, resource: str, effect_preds: List[Prediction], desc: str, explain: Explainability) -> List[Prediction]:
		if resource not in ("database", "table", "row"):
			return effect_preds

		# Arbitrary SQL => EXECUTE
		if any(re.search(p, desc) for p in [r"\barbitrary\b", r"\braw sql\b", r"\bany sql\b"]):
			explain.override_reasoning.append({"type": "sql_override", "reason": "arbitrary_sql", "chosen": "EXECUTE"})
			return [Prediction("EXECUTE", 0.95)]

		# Read-only signals => READ
		if any(re.search(p, desc) for p in [r"\bread-only\b", r"\bselect-only\b", r"\bfetch-only\b"]) and not any(re.search(p, desc) for p in [r"\binsert\b", r"\bupdate\b", r"\bdelete\b", r"\bdrop\b"]):
			explain.override_reasoning.append({"type": "sql_override", "reason": "read_only", "chosen": "READ"})
			return [Prediction("READ", 0.95)]

		return effect_preds

	def _choose_primary_effect(self, effects: List[Prediction], explain: Explainability, near_tie_delta: float = 0.02) -> str:
		if not effects:
			return "READ"
		if len(effects) == 1:
			return effects[0].label
		top, second = effects[0], effects[1]
		if abs(top.confidence - second.confidence) <= near_tie_delta:
			tied_conf = top.confidence
			tied = [p for p in effects if abs(p.confidence - tied_conf) <= near_tie_delta]
			chosen = sorted(tied, key=lambda p: _PRECEDENCE_INDEX.get(p.label, 999))[0].label
			explain.conflict_reasoning.append({
				"type": "effect_tie_break",
				"near_tie_delta": near_tie_delta,
				"tied": [asdict(p) for p in tied],
				"chosen": chosen,
				"precedence": EFFECT_PRECEDENCE,
			})
			return chosen
		return top.label

	def _infer_execution_domain(self, resource: str, desc: str, primary_effect: str, explain: Explainability) -> Optional[str]:
		if primary_effect != "EXECUTE":
			return None
		# Deterministic resource defaults
		if resource in ("database", "table", "row"):
			explain.override_reasoning.append({"type": "execution_domain", "reason": "resource_database_family", "domain": "DATABASE"})
			return "DATABASE"
		if resource in ("server", "container", "cluster"):
			explain.override_reasoning.append({"type": "execution_domain", "reason": "resource_compute_family", "domain": "COMPUTE"})
			return "COMPUTE"
		if resource in ("workflow", "pipeline"):
			explain.override_reasoning.append({"type": "execution_domain", "reason": "resource_workflow_family", "domain": "WORKFLOW"})
			return "WORKFLOW"

		scores = defaultdict(int)
		for dom, pats in DOMAIN_PATTERNS.items():
			for p in pats:
				if re.search(p, desc):
					scores[dom] += 1
		if not scores:
			return None
		domain = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
		explain.override_reasoning.append({"type": "execution_domain", "reason": "pattern_match", "scores": dict(scores), "domain": domain})
		return domain

	def _infer_scope(self, desc: str, input_keys: List[str], explain: Explainability) -> str:
		text = desc.lower()
		id_like = {
			"id", "uuid", "key", "slug", "email",
			"user_id", "customer_id", "issue_id", "repo", "repository",
			"project_id", "org_id", "workspace_id",
		}
		if any(k.lower() in id_like for k in input_keys) and not re.search(r"\ball\b|\barbitrary\b|\bany\b|\bentire\b", text):
			explain.risk_reasoning.append({"type": "scope", "reason": "id_like_input", "scope": "single_resource"})
			return "single_resource"
		for scope, pats in SCOPE_PATTERNS:
			if any(re.search(p, text) for p in pats):
				explain.risk_reasoning.append({"type": "scope", "reason": "pattern_match", "scope": scope})
				return scope
		explain.risk_reasoning.append({"type": "scope", "reason": "default", "scope": "small_collection"})
		return "small_collection"

	def _infer_privilege(self, primary_effect: str, desc: str, explain: Explainability) -> int:
		text = desc.lower()
		if re.search(r"\b(admin|root|sudo)\b", text) or ("all privileges" in text) or re.search(r"\bgrant\b", text):
			explain.risk_reasoning.append({"type": "privilege", "reason": "admin_root_grant", "value": 5})
			return 5
		if primary_effect in ("READ", "ENUMERATE") and not re.search(r"\b(arbitrary|all|any)\b", text):
			explain.risk_reasoning.append({"type": "privilege", "reason": "scoped_read_enumerate", "value": 1})
			return 1
		explain.risk_reasoning.append({"type": "privilege", "reason": "default", "value": 2})
		return 2

	def _risk_dimensions(self, primary_effect: str, resource: str, privilege: int, scope_label: str, desc: str, explain: Explainability) -> RiskVector:
		impact = {"DELETE": 5, "GRANT": 5, "EXECUTE": 4, "WRITE": 3, "ENUMERATE": 2, "READ": 1}.get(primary_effect, 1)
		high_sens = {"database", "customer", "user", "invoice", "document", "message", "email", "calendar_event", "secret", "credential", "contract"}
		sensitivity = 4 if resource in high_sens else 2
		exposure = 4 if resource in {"server", "container", "cluster", "endpoint", "repository"} else 2
		scope = SCOPE_LEVELS.get(scope_label, 2)
		explain.risk_reasoning.append({
			"type": "risk_vector",
			"impact": impact,
			"sensitivity": sensitivity,
			"exposure": exposure,
			"privilege": privilege,
			"scope": scope,
		})
		return RiskVector(impact, sensitivity, exposure, privilege, scope)

	def compile(self, tool: RawTool) -> CompilationResult:
		explain = Explainability()
		name = tool.name.lower()
		desc = tool.description.lower()

		effect_preds = self._score_matches(name, desc, EFFECT_TAXONOMY, explain, "effect")
		resource_preds = self._score_matches(name, desc, CANONICAL_RESOURCES, explain, "resource")
		primary_resource = resource_preds[0] if resource_preds else Prediction("system", 1.0)

		effect_preds = self._handle_sql_override(primary_resource.label, effect_preds, desc, explain)
		if not effect_preds:
			explain.override_reasoning.append({"type": "effect_default", "chosen": "READ"})
			effect_preds = [Prediction("READ", 1.0)]

		# Retain multi-effects above threshold; fallback to top if empty
		valid = [p for p in effect_preds if p.confidence >= self.multi_effect_threshold]
		if not valid:
			valid = [effect_preds[0]]
			explain.override_reasoning.append({"type": "multi_effect_fallback", "threshold": self.multi_effect_threshold, "chosen": asdict(effect_preds[0])})
		valid = sorted(valid, key=lambda p: (-p.confidence, _PRECEDENCE_INDEX.get(p.label, 999), p.label))

		primary_effect = self._choose_primary_effect(valid, explain)
		all_effect_labels = [p.label for p in valid]

		inputs = list((tool.input_schema or {}).get("properties", {}).keys())
		outputs = tool.expected_outputs or ["json"]

		scope_label = self._infer_scope(desc, inputs, explain)
		privilege = self._infer_privilege(primary_effect, desc, explain)

		exec_domain = self._infer_execution_domain(primary_resource.label, desc, primary_effect, explain)

		risk = self._risk_dimensions(primary_effect, primary_resource.label, privilege, scope_label, desc, explain)

		urn = f"urn:faia:{primary_resource.label}:{primary_effect.lower()}"
		parents = get_resource_lineage(primary_resource.label)

		cap_fp = capability_fingerprint(
			effects=all_effect_labels,
			resource=primary_resource.label,
			inputs=inputs,
			outputs=outputs,
			constraints=tool.constraints,
			scope_label=scope_label,
			operation_type="tool",
		)

		impl_fp = implementation_fingerprint(tool_name=tool.name.lower(), provider=tool.provider.lower(), capability_fp=cap_fp)

		graph_metadata = {
			"resource": primary_resource.label,
			"resource_parents": parents,
			"primary_effect": primary_effect,
			"effects": sorted(set(all_effect_labels)),
			"execution_domain": exec_domain,
			"scope": scope_label,
			"risk": asdict(risk) | {"blast_radius": risk.blast_radius},
			"explainability": {
				"override_reasoning": explain.override_reasoning,
				"conflict_reasoning": explain.conflict_reasoning,
			},
		}

		cap = CapabilityRecord(
			capability_urn=urn,
			fingerprint=cap_fp,
			resource=primary_resource.label,
			resource_parents=parents,
			primary_effect=primary_effect,
			all_effects=sorted(set(all_effect_labels)),
			execution_domain=exec_domain,
			operation_type="tool",
			scope_label=scope_label,
			inputs=sorted(set(inputs)),
			outputs=sorted(set(outputs)),
			constraints=tool.constraints,
			graph_metadata=graph_metadata,
		)

		impl = ImplementationRecord(
			implementation_fingerprint=impl_fp,
			tool_name=tool.name.lower(),
			provider=tool.provider.lower(),
			description=tool.description,
			capability_fingerprint=cap_fp,
			urn_mapping=urn,
			raw_tool=tool.to_dict(),
		)

		return CompilationResult(capability=cap, implementation=impl, risk=risk, explainability=explain)


# ============================================================
# 6) Authority derivation
# ============================================================

def derive_authority(cap: CapabilityRecord, risk: RiskVector) -> AuthorityEnvelope:
	"""Derive an authority envelope from a capability."""
	constraints = cap.constraints or {}
	authority_id = sha256_hex(stable_json_dumps({
		"effect": cap.primary_effect,
		"resource": cap.resource,
		"scope": cap.scope_label,
		"constraints": constraints,
		"execution_domain": cap.execution_domain,
		"cap_fp": cap.fingerprint,
	}))

	statement = f"{cap.primary_effect}({cap.resource}) scoped={cap.scope_label}"
	if cap.execution_domain:
		statement += f" domain={cap.execution_domain}"
	if constraints:
		statement += f" constraints={stable_json_dumps(constraints)}"

	return AuthorityEnvelope(
		authority_id=authority_id,
		effect=cap.primary_effect,
		resource=cap.resource,
		scope_label=cap.scope_label,
		execution_domain=cap.execution_domain,
		constraints=constraints,
		capability_fingerprint=cap.fingerprint,
		blast_radius=risk.blast_radius,
		statement=statement,
	)


# ============================================================
# 7) Graph builder (NetworkX)
# ============================================================

class CapabilityGraph:
	"""Build and query the FAIA capability graph using NetworkX."""

	def __init__(self):
		self.G = nx.DiGraph()

	def add_ontology(self):
		# Effect nodes
		for eff in EFFECT_TAXONOMY.keys():
			self.G.add_node(f"effect:{eff}", type="Effect", effect=eff)

		# Resource nodes + hierarchy edges
		for r, node in RESOURCE_ONTOLOGY.items():
			self.G.add_node(f"resource:{r}", type="Resource", resource=r, aliases=node.aliases)
			if node.parent:
				self.G.add_edge(f"resource:{r}", f"resource:{node.parent}", type="PARENT_RESOURCE")

		# Execution domain nodes
		for d in EXECUTION_DOMAINS:
			self.G.add_node(f"domain:{d}", type="ExecutionDomain", domain=d)

		# Scope nodes
		for s, v in SCOPE_LEVELS.items():
			self.G.add_node(f"scope:{s}", type="Scope", scope=s, level=v)

	def add_compilation(self, comp: CompilationResult, authority: AuthorityEnvelope):
		cap = comp.capability
		impl = comp.implementation

		cap_node = f"cap:{cap.fingerprint}"
		impl_node = f"impl:{impl.implementation_fingerprint}"
		prov_node = f"provider:{impl.provider}"
		res_node = f"resource:{cap.resource}"
		eff_node = f"effect:{cap.primary_effect}"
		scope_node = f"scope:{cap.scope_label}"

		# nodes
		self.G.add_node(cap_node, type="Capability", **{
			"fingerprint": cap.fingerprint,
			"urn": cap.capability_urn,
			"resource": cap.resource,
			"primary_effect": cap.primary_effect,
			"effects": cap.all_effects,
			"execution_domain": cap.execution_domain,
			"scope": cap.scope_label,
			"inputs": cap.inputs,
			"outputs": cap.outputs,
			"constraints": cap.constraints,
			"risk": comp.risk.blast_radius,
		})

		self.G.add_node(impl_node, type="Implementation", **{
			"implementation_fingerprint": impl.implementation_fingerprint,
			"tool_name": impl.tool_name,
			"provider": impl.provider,
			"description": impl.description,
		})

		self.G.add_node(prov_node, type="Provider", provider=impl.provider)

		# edges
		self.G.add_edge(impl_node, cap_node, type="IMPLEMENTS")
		self.G.add_edge(cap_node, eff_node, type="USES_EFFECT")
		self.G.add_edge(cap_node, res_node, type="ACTS_ON")
		self.G.add_edge(impl_node, prov_node, type="PROVIDED_BY")
		self.G.add_edge(cap_node, scope_node, type="HAS_SCOPE")

		if cap.execution_domain:
			dom_node = f"domain:{cap.execution_domain}"
			self.G.add_edge(cap_node, dom_node, type="HAS_EXECUTION_DOMAIN")

		# store authority envelope as node (optional but useful)
		auth_node = f"auth:{authority.authority_id}"
		self.G.add_node(auth_node, type="Authority", **asdict(authority))
		self.G.add_edge(cap_node, auth_node, type="DERIVES_AUTHORITY")

		# link resource lineage edges for cap to parents (graph-ready)
		for parent in cap.resource_parents:
			self.G.add_edge(f"resource:{cap.resource}", f"resource:{parent}", type="PARENT_RESOURCE")

	# ------------------------
	# Phase 6: Search queries
	# ------------------------
	def find_capabilities_by_effect_resource(self, effect: str, resource: str) -> List[str]:
		"""Find capability node ids matching effect + resource."""
		out = []
		for n, data in self.G.nodes(data=True):
			if data.get("type") == "Capability":
				if data.get("primary_effect") == effect and data.get("resource") == resource:
					out.append(n)
		return out

	def find_capabilities_by_effect(self, effect: str) -> List[str]:
		return [n for n, d in self.G.nodes(data=True) if d.get("type") == "Capability" and d.get("primary_effect") == effect]

	def find_capabilities_by_resource(self, resource: str, include_descendants: bool = False) -> List[str]:
		out = []
		for n, d in self.G.nodes(data=True):
			if d.get("type") != "Capability":
				continue
			cap_res = d.get("resource")
			if cap_res == resource:
				out.append(n)
			elif include_descendants and resource_is_descendant_of(cap_res, resource):
				out.append(n)
		return out

	def implementations_of_capability_urn(self, capability_urn: str) -> List[str]:
		impls = []
		for n, d in self.G.nodes(data=True):
			if d.get("type") == "Capability" and d.get("urn") == capability_urn:
				# incoming implementations
				for pred in self.G.predecessors(n):
					if self.G.nodes[pred].get("type") == "Implementation":
						impls.append(pred)
		return impls

	def high_risk_capabilities(self, threshold: float = 80.0) -> List[str]:
		return [n for n, d in self.G.nodes(data=True) if d.get("type") == "Capability" and float(d.get("risk", 0.0)) >= threshold]

	def tools_affecting_resource(self, resource: str, include_descendants: bool = True) -> List[str]:
		caps = self.find_capabilities_by_resource(resource, include_descendants=include_descendants)
		tool_nodes: Set[str] = set()
		for cap_node in caps:
			for pred in self.G.predecessors(cap_node):
				if self.G.nodes[pred].get("type") == "Implementation":
					tool_nodes.add(pred)
		return sorted(tool_nodes)


# ============================================================
# 8) Analytics
# ============================================================

def graph_analytics(comps: List[CompilationResult], graph: CapabilityGraph) -> Dict[str, Any]:
	G = graph.G

	node_counts = Counter(d.get("type") for _, d in G.nodes(data=True))
	edge_counts = Counter(d.get("type") for _, _, d in G.edges(data=True))

	# Most common effects/resources/providers
	res_ctr = Counter()
	eff_ctr = Counter()
	prov_ctr = Counter()
	risk_vals: List[float] = []

	for n, d in G.nodes(data=True):
		if d.get("type") == "Capability":
			res_ctr[d.get("resource")] += 1
			eff_ctr[d.get("primary_effect")] += 1
			risk_vals.append(float(d.get("risk", 0.0)))
		elif d.get("type") == "Implementation":
			prov_ctr[d.get("provider")] += 1

	# Dedup stats
	impl_count = sum(1 for _, d in G.nodes(data=True) if d.get("type") == "Implementation")
	cap_count = sum(1 for _, d in G.nodes(data=True) if d.get("type") == "Capability")
	dedup_ratio = round(impl_count / cap_count, 3) if cap_count else None

	# Risk distribution buckets
	bins = [0, 20, 40, 60, 80, 100]
	bucket = Counter()
	for r in risk_vals:
		for i in range(len(bins) - 1):
			if bins[i] <= r < bins[i + 1]:
				bucket[f"{bins[i]}-{bins[i+1]}"] += 1
				break
		else:
			if r >= 100:
				bucket["100+"] += 1

	return {
		"node_counts": dict(node_counts),
		"edge_counts": dict(edge_counts),
		"most_common_resources": res_ctr.most_common(10),
		"most_common_effects": eff_ctr.most_common(10),
		"provider_statistics": prov_ctr.most_common(10),
		"risk_distribution": dict(bucket),
		"capability_count": cap_count,
		"implementation_count": impl_count,
		"capability_dedup_ratio_impl_per_cap": dedup_ratio,
	}


# ============================================================
# 9) Built-in dataset generator (100+ tools)
# ============================================================

def _schema(props: List[str]) -> Dict[str, Any]:
	return {"type": "object", "properties": {p: {"type": "string"} for p in props}}


def generate_sample_tools(min_tools: int = 120, seed: int = 42) -> List[RawTool]:
	random.seed(seed)

	providers = ["jira", "github", "postgres", "slack", "google_drive", "email", "kubernetes", "filesystem"]

	# Provider-specific templates (name, description, resource cues, effect cues, inputs)
	templates: List[Tuple[str, str, str, List[str], List[str]]] = [
		# Jira
		("jira_get_issue", "Fetch a Jira ticket by ID", "issue", ["get", "fetch"], ["issue_id"]),
		("jira_search_issues", "Search issues with JQL and list all matches", "issue", ["search", "list"], ["jql"]),
		("jira_create_issue", "Create a new issue in a project", "issue", ["create"], ["project_id", "title", "description"]),
		("jira_delete_issue", "Delete an issue by ID", "issue", ["delete"], ["issue_id"]),

		# GitHub
		("github_get_repo", "Get repository metadata", "repository", ["get"], ["owner", "repo"]),
		("github_list_branches", "List branches for a repository", "branch", ["list"], ["owner", "repo"]),
		("github_create_pr", "Open a pull request", "pull_request", ["create", "open"], ["owner", "repo", "head", "base"]),
		("github_merge_pr", "Merge a pull request", "pull_request", ["merge", "update"], ["owner", "repo", "pr_number"]),
		("github_delete_branch", "Delete a branch", "branch", ["delete"], ["owner", "repo", "branch"]),

		# Postgres / DB
		("postgres_query", "Execute read-only SQL to fetch rows", "database", ["query", "read-only", "select"], ["sql"]),
		("postgres_exec", "Executes arbitrary SQL statements", "database", ["execute", "arbitrary", "sql"], ["sql"]),
		("postgres_insert_row", "Insert a row into a table", "row", ["insert", "create"], ["table", "values"]),
		("postgres_export_all_customers", "Export all customers from database", "customer", ["export", "all"], ["format"]),

		# Slack
		("slack_post_message", "Post a message to a channel", "message", ["post", "create"], ["channel", "text"]),
		("slack_list_channels", "List all channels", "message", ["list", "all"], []),
		("slack_delete_message", "Delete a message", "message", ["delete"], ["channel", "ts"]),

		# Google Drive
		("drive_get_file", "Get a file metadata by ID", "document", ["get"], ["file_id"]),
		("drive_list_files", "List files in a folder", "document", ["list"], ["folder_id"]),
		("drive_upload_file", "Upload a file to Drive", "document", ["upload", "create"], ["folder_id", "name", "content"]),
		("drive_delete_file", "Delete a file", "document", ["delete"], ["file_id"]),

		# Email
		("email_send", "Send an email", "email", ["send", "create"], ["to", "subject", "body"]),
		("email_list_inbox", "List all emails in inbox", "email", ["list", "all"], []),
		("email_get_message", "Fetch email by message id", "email", ["get", "fetch"], ["message_id"]),

		# Kubernetes
		("k8s_run_container", "Run a container in a Kubernetes cluster", "container", ["run", "execute"], ["cluster", "image"]),
		("k8s_list_pods", "List pods in a namespace", "container", ["list"], ["namespace"]),
		("k8s_delete_pod", "Delete a pod", "container", ["delete"], ["namespace", "pod"]),
		("k8s_apply_manifest", "Apply a Kubernetes manifest", "cluster", ["apply", "deploy", "execute"], ["manifest"]),

		# Filesystem
		("fs_read_file", "Read a file by path", "filesystem", ["read", "get"], ["path"]),
		("fs_write_file", "Write content to a file", "filesystem", ["write", "create"], ["path", "content"]),
		("fs_delete_file", "Delete a file", "filesystem", ["delete"], ["path"]),
		("fs_list_dir", "List files in a directory", "filesystem", ["list"], ["path"]),
	]

	# Create many variants with provider naming differences but same capability intent
	tools: List[RawTool] = []

	def mk_constraints(provider: str) -> Dict[str, Any]:
		# Deterministic but varied constraints; included in capability fingerprint per requirements
		if provider in ("jira", "github"):
			return {"rate_limit": 60, "auth": "oauth"}
		if provider in ("postgres",):
			return {"region": "us-east", "auth": "password"}
		if provider in ("slack", "email"):
			return {"rate_limit": 120, "auth": "token"}
		if provider == "kubernetes":
			return {"cluster_scope": "namespace", "auth": "kubeconfig"}
		return {"auth": "token"}

	# Seed with templates
	for (base_name, base_desc, _resource_hint, cue_words, inputs) in templates:
		# decide provider from prefix
		provider = base_name.split("_")[0]
		provider = "kubernetes" if provider in ("k8s",) else provider
		provider = "google_drive" if provider in ("drive",) else provider
		provider = "email" if provider in ("email",) else provider
		provider = "filesystem" if provider in ("fs",) else provider
		provider = "postgres" if provider in ("postgres",) else provider

		desc = base_desc
		# Add effect cues into description for more robust matching
		if cue_words:
			desc = f"{base_desc}. " + " ".join([f"{w}" for w in cue_words])

		tools.append(RawTool(
			name=base_name,
			description=desc,
			provider=provider,
			input_schema=_schema(inputs),
			expected_outputs=["json"],
			constraints=mk_constraints(provider),
		))

	# Add provider-variant aliases that should dedupe to same capability (esp. database queries)
	variants = [
		RawTool(
			name="supabase_query",
			description="Execute read-only SQL to fetch rows from database. read-only select",
			provider="postgres",
			input_schema=_schema(["sql"]),
			expected_outputs=["json"],
			constraints=mk_constraints("postgres"),
		),
		RawTool(
			name="rds_query",
			description="Fetch rows from database using read-only SQL. select-only",
			provider="postgres",
			input_schema=_schema(["sql"]),
			expected_outputs=["json"],
			constraints=mk_constraints("postgres"),
		),
	]
	n_tools_before = len(tools)
	tools.extend(variants)

	# Expand to min_tools by generating synthetic but realistic mutations
	verbs = ["get", "list", "search", "create", "update", "delete", "grant", "execute", "export"]
	resources = ["issue", "pull_request", "repository", "branch", "commit", "database", "table", "row", "message", "document", "email", "container", "filesystem", "customer", "user", "secret"]

	while len(tools) < min_tools:
		provider = random.choice(providers)
		verb = random.choice(verbs)
		res = random.choice(resources)
		name = f"{provider}_{verb}_{res}_{len(tools)}"

		# Description contains cues for effect/resource
		parts = [
			f"{verb.title()} {res.replace('_', ' ')}",
			f"provider {provider}",
		]
		if verb in ("list", "search", "export"):
			parts.append("list all")
		if verb == "execute":
			parts.append("run")
		if provider == "postgres" and verb in ("execute", "get", "search"):
			parts.append("sql")
		if res in ("user", "customer") and verb in ("export", "list"):
			parts.append("organization")

		desc = ". ".join(parts)
		inputs = []
		if verb in ("get", "delete", "update"):
			inputs.append(f"{res}_id")
		if provider in ("postgres",) and ("sql" in desc):
			inputs = ["sql"]
		if verb in ("create", "update"):
			inputs += ["payload"]
		input_schema = _schema(sorted(set(inputs)))

		tools.append(RawTool(
			name=name,
			description=desc,
			provider=provider,
			input_schema=input_schema,
			expected_outputs=["json"],
			constraints=mk_constraints(provider),
		))

	# Ensure we are above 100
	assert len(tools) >= 100
	return tools


# ============================================================
# 10) Console reporting helpers
# ============================================================

def _print_header(title: str):
	print("\n" + "=" * 80)
	print(title)
	print("=" * 80)


def _short(s: str, n: int = 72) -> str:
	return s if len(s) <= n else s[: n - 3] + "..."


def print_capability_stats(comps: List[CompilationResult]):
	caps = [c.capability for c in comps]
	impls = [c.implementation for c in comps]

	cap_fp_unique = len({c.fingerprint for c in caps})
	impl_fp_unique = len({i.implementation_fingerprint for i in impls})

	_print_header("Capability Deduplication Report")
	print(f"Implementations: {len(impls)} (unique impl fingerprints: {impl_fp_unique})")
	print(f"Capabilities:     {cap_fp_unique} (unique cap fingerprints)")
	if cap_fp_unique:
		print(f"Impl per capability (avg): {round(len(impls) / cap_fp_unique, 3)}")

	# Show top deduped capabilities by implementation count
	by_cap = defaultdict(list)
	for c in comps:
		by_cap[c.capability.fingerprint].append(c)
	top = sorted(by_cap.items(), key=lambda kv: -len(kv[1]))[:5]
	print("\nTop deduped capabilities (most implementations share same capability):")
	for fp, items in top:
		ex = items[0].capability
		print(f"- {ex.capability_urn} | resource={ex.resource} effect={ex.primary_effect} scope={ex.scope_label} | impls={len(items)} | fp={fp[:16]}...")


def print_risk_summaries(comps: List[CompilationResult], top_n: int = 10):
	sorted_by_risk = sorted(comps, key=lambda c: -c.risk.blast_radius)[:top_n]
	_print_header(f"Top {top_n} High-Risk Capabilities")
	for c in sorted_by_risk:
		cap = c.capability
		print(f"- risk={cap.graph_metadata['risk']['blast_radius']:<6} urn={cap.capability_urn:<28} scope={cap.scope_label:<18} prov={c.implementation.provider:<12} tool={_short(c.implementation.tool_name, 28)}")


def print_sample_authorities(authorities: List[AuthorityEnvelope], n: int = 5):
	_print_header(f"Sample Authority Envelopes (n={n})")
	for a in authorities[:n]:
		print(f"- {a.statement} | blast_radius={a.blast_radius} | auth_id={a.authority_id[:16]}...")


# ============================================================
# 11) Runtime demo / main()
# ============================================================

def main():
	_print_header("FAIA Monolith Prototype: End-to-End Run")

	# Step 1: Generate sample tools
	tools = generate_sample_tools(min_tools=130, seed=42)
	print(f"Generated raw tools: {len(tools)}")
	print(f"Providers: {sorted(set(t.provider for t in tools))}")

	# Step 2: Extract capabilities
	extractor = HardenedExtractor(weight_name=1.0, weight_desc=2.5)
	comps: List[CompilationResult] = []
	authorities: List[AuthorityEnvelope] = []

	for t in tools:
		comp = extractor.compile(t)
		comps.append(comp)
		authorities.append(derive_authority(comp.capability, comp.risk))

	print_capability_stats(comps)
	print_risk_summaries(comps, top_n=10)
	print_sample_authorities(authorities, n=6)

	# Step 3: Build graph
	graph = CapabilityGraph()
	graph.add_ontology()
	for comp, auth in zip(comps, authorities):
		graph.add_compilation(comp, auth)

	# Step 4: Analytics
	stats = graph_analytics(comps, graph)
	_print_header("Graph Analytics")
	print(f"Node counts: {stats['node_counts']}")
	print(f"Edge counts: {stats['edge_counts']}")
	print(f"Capabilities: {stats['capability_count']}, Implementations: {stats['implementation_count']}")
	print(f"Dedup ratio (impl/cap): {stats['capability_dedup_ratio_impl_per_cap']}")
	print(f"Most common resources: {stats['most_common_resources']}")
	print(f"Most common effects: {stats['most_common_effects']}")
	print(f"Provider stats: {stats['provider_statistics']}")
	print(f"Risk distribution: {stats['risk_distribution']}")

	# Step 5: Search queries (Phase 6)
	_print_header("Search Queries")

	q1 = graph.find_capabilities_by_effect_resource("READ", "issue")
	print(f"Query: Find all READ(issue) capabilities -> {len(q1)} matches")
	for n in q1[:5]:
		d = graph.G.nodes[n]
		print(f"  - {d['urn']} fp={d['fingerprint'][:16]}... risk={d['risk']} scope={d['scope']}")

	q2 = graph.find_capabilities_by_effect_resource("WRITE", "repository")
	print(f"\nQuery: Find all WRITE(repository) capabilities -> {len(q2)} matches")
	for n in q2[:5]:
		d = graph.G.nodes[n]
		print(f"  - {d['urn']} fp={d['fingerprint'][:16]}... risk={d['risk']} scope={d['scope']}")

	q3 = graph.high_risk_capabilities(threshold=80.0)
	print(f"\nQuery: Find all high-risk capabilities (>=80) -> {len(q3)} matches")
	for n in q3[:8]:
		d = graph.G.nodes[n]
		print(f"  - risk={d['risk']:<6} urn={d['urn']:<28} resource={d['resource']:<12} effect={d['primary_effect']:<9} scope={d['scope']}")

	q4 = graph.implementations_of_capability_urn("urn:faia:database:read")
	print(f"\nQuery: Find all implementations of database.read -> {len(q4)} matches")
	for n in q4[:8]:
		d = graph.G.nodes[n]
		print(f"  - provider={d['provider']:<10} tool={d['tool_name']}")

	q5 = graph.find_capabilities_by_resource("customer", include_descendants=True)
	print(f"\nQuery: Find all capabilities affecting customer data -> {len(q5)} matches")
	for n in q5[:8]:
		d = graph.G.nodes[n]
		print(f"  - {d['urn']} risk={d['risk']} scope={d['scope']} provider_count={sum(1 for p in graph.G.predecessors(n) if graph.G.nodes[p].get('type')=='Implementation')}")

	# Step 6: Print a compact explainability sample
	_print_header("Explainability Sample")
	sample = next((c for c in comps if c.capability.resource == "database" and c.capability.primary_effect in ("READ", "EXECUTE")), comps[0])
	print(f"Tool: {sample.implementation.tool_name} ({sample.implementation.provider})")
	print(f"Capability URN: {sample.capability.capability_urn}")
	print(f"Capability FP: {sample.capability.fingerprint}")
	print(f"Risk: {sample.risk} blast_radius={sample.risk.blast_radius}")
	print("Override reasoning:")
	print(json.dumps(sample.explainability.override_reasoning[:3], indent=2))
	print("Conflict reasoning:")
	print(json.dumps(sample.explainability.conflict_reasoning[:3], indent=2))
	print("Risk reasoning:")
	print(json.dumps(sample.explainability.risk_reasoning[:3], indent=2))

	_print_header("FAIA Prototype Run Complete")
	print("Success criteria check:")
	print(f"- 100+ tools normalized: {'YES' if len(tools) >= 100 else 'NO'}")
	print(f"- Capabilities deduplicated: {'YES' if stats['capability_count'] < stats['implementation_count'] else 'NO'}")
	print(f"- Graph constructed: {'YES' if graph.G.number_of_nodes() > 0 and graph.G.number_of_edges() > 0 else 'NO'}")
	print(f"- Authority envelopes generated: {'YES' if len(authorities) == len(tools) else 'NO'}")
	print(f"- Search queries return results: {'YES' if (len(q1)+len(q2)+len(q3)+len(q4)+len(q5)) > 0 else 'NO'}")


if __name__ == "__main__":
	main()

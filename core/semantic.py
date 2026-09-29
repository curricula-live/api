import hashlib
import json
from collections import deque

from django.db import transaction

from core.models import (
    Concept,
    Relation,
    SemanticPublicationSnapshot,
    SemanticSnapshotConcept,
    SemanticSnapshotEdge,
)


PREREQUISITE_RELATION_TYPE = "prerequisite_of"
SCHEMA_VERSION = "sem-v1"
POLICY_VERSION = "strict-prior@1"
CANONICALIZATION_VERSION = "canonical-json-v1"
SCOPE_DIMENSIONS = ("framework", "stage", "subject", "course_context", "qualifier")


class SnapshotConflict(ValueError):
    pass


class SnapshotCycle(ValueError):
    pass


def canonical_bytes(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def content_hash(manifest):
    return hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def _normalized_scope(metadata):
    scope = metadata.get("scope", {}) if isinstance(metadata, dict) else {}
    if not isinstance(scope, dict):
        raise ValueError("relation metadata.scope must be an object")

    normalized = {}
    for dimension in SCOPE_DIMENSIONS:
        value = scope.get(dimension, "*")
        if not isinstance(value, str) or not value:
            raise ValueError(f"scope.{dimension} must be a non-empty string")
        normalized[dimension] = value
    return normalized


def _normalized_evidence(metadata):
    evidence = metadata.get("evidence", []) if isinstance(metadata, dict) else []
    if not isinstance(evidence, list) or not all(
        isinstance(item, str) and item for item in evidence
    ):
        raise ValueError("relation metadata.evidence must be a list of non-empty strings")
    return sorted(set(evidence))


def _find_cycle(edges):
    adjacency = {}
    nodes = set()
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        nodes.update((source, target))
        adjacency.setdefault(source, []).append(target)

    for values in adjacency.values():
        values.sort()

    state = {}
    stack = []

    def visit(node):
        state[node] = 1
        stack.append(node)
        for target in adjacency.get(node, []):
            if state.get(target, 0) == 0:
                cycle = visit(target)
                if cycle:
                    return cycle
            elif state.get(target) == 1:
                start = stack.index(target)
                return stack[start:] + [target]
        stack.pop()
        state[node] = 2
        return None

    for node in sorted(nodes):
        if state.get(node, 0) == 0:
            cycle = visit(node)
            if cycle:
                return cycle
    return None


def build_live_manifest():
    concepts = list(Concept.objects.order_by("slug").values_list("slug", flat=True))
    relations = (
        Relation.objects.filter(type_id=PREREQUISITE_RELATION_TYPE)
        .select_related("source", "target")
        .order_by("source_id", "target_id", "id")
    )

    edges = []
    for relation in relations:
        metadata = relation.metadata or {}
        edges.append(
            {
                "relation_id": str(relation.id),
                "source": relation.source_id,
                "type": PREREQUISITE_RELATION_TYPE,
                "target": relation.target_id,
                "scope": _normalized_scope(metadata),
                "evidence": _normalized_evidence(metadata),
            }
        )

    cycle = _find_cycle(edges)
    if cycle:
        raise SnapshotCycle("strict prerequisite graph contains cycle: " + " -> ".join(cycle))

    return {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "concepts": concepts,
        "edges": edges,
    }


@transaction.atomic
def publish_snapshot(snapshot_id):
    manifest = build_live_manifest()
    digest = content_hash(manifest)

    existing = SemanticPublicationSnapshot.objects.filter(snapshot_id=snapshot_id).first()
    if existing:
        if existing.content_hash == digest and existing.manifest == manifest:
            return existing, False
        raise SnapshotConflict(
            f"snapshot {snapshot_id} already exists with different immutable content"
        )

    snapshot = SemanticPublicationSnapshot.objects.create(
        snapshot_id=snapshot_id,
        schema_version=SCHEMA_VERSION,
        policy_version=POLICY_VERSION,
        canonicalization_version=CANONICALIZATION_VERSION,
        content_hash=digest,
        manifest=manifest,
    )
    SemanticSnapshotConcept.objects.bulk_create(
        [
            SemanticSnapshotConcept(snapshot=snapshot, slug=slug)
            for slug in manifest["concepts"]
        ]
    )
    SemanticSnapshotEdge.objects.bulk_create(
        [
            SemanticSnapshotEdge(
                snapshot=snapshot,
                source_relation_id=edge["relation_id"],
                source_slug=edge["source"],
                relation_type=edge["type"],
                target_slug=edge["target"],
                scope=edge["scope"],
                evidence=edge["evidence"],
            )
            for edge in manifest["edges"]
        ]
    )
    return snapshot, True


def scope_match(assertion_scope, plan_context):
    for dimension in SCOPE_DIMENSIONS:
        assertion_value = assertion_scope.get(dimension, "*")
        if assertion_value == "*":
            continue
        plan_value = plan_context.get(dimension)
        if plan_value in (None, "") or plan_value == "*":
            return "UNKNOWN"
        if assertion_value != plan_value:
            return "NO_MATCH"
    return "MATCH"


def _shortest_path(source, target, adjacency):
    queue = deque([(source, [])])
    visited = {source}

    while queue:
        current, path = queue.popleft()
        candidates = sorted(
            adjacency.get(current, []),
            key=lambda edge: (edge.target_slug, str(edge.source_relation_id)),
        )
        for edge in candidates:
            next_path = path + [edge]
            if edge.target_slug == target:
                return next_path
            if edge.target_slug not in visited:
                visited.add(edge.target_slug)
                queue.append((edge.target_slug, next_path))
    return []


def _predecessors(target, reverse_adjacency):
    visited = set()
    queue = deque([target])
    while queue:
        current = queue.popleft()
        for source in sorted(reverse_adjacency.get(current, [])):
            if source == target or source in visited:
                continue
            visited.add(source)
            queue.append(source)
    return visited


def validate_plan(snapshot, context, prior_items, plan_items):
    known = set(
        snapshot.concept_memberships.order_by("slug").values_list("slug", flat=True)
    )

    unresolved = []
    prior = []
    plan = []

    for collection, destination in ((prior_items, prior), (plan_items, plan)):
        for item in collection:
            ref = item.get("ref")
            kind = item.get("kind", "concept")
            if kind != "concept" or not isinstance(ref, str) or ref not in known:
                unresolved.append(str(ref))
            else:
                destination.append(ref)

    if unresolved:
        return {
            "outcome": "INDETERMINATE",
            "prior": prior,
            "resolved_plan": plan,
            "certificates": [],
            "unresolved_refs": sorted(set(unresolved)),
            "unknown_scope_assertions": [],
            "notes": ["One or more plan references cannot be resolved in this snapshot."],
        }

    matching = []
    unknown = []
    for edge in snapshot.edges.order_by(
        "source_slug", "target_slug", "source_relation_id"
    ):
        result = scope_match(edge.scope, context)
        if result == "MATCH":
            matching.append(edge)
        elif result == "UNKNOWN":
            unknown.append(edge)

    adjacency = {}
    reverse_adjacency = {}
    for edge in matching:
        adjacency.setdefault(edge.source_slug, []).append(edge)
        reverse_adjacency.setdefault(edge.target_slug, []).append(edge.source_slug)

    union_reverse = {key: list(values) for key, values in reverse_adjacency.items()}
    for edge in unknown:
        union_reverse.setdefault(edge.target_slug, []).append(edge.source_slug)

    relevant_unknown = set()
    for target in plan:
        relevant_nodes = _predecessors(target, union_reverse)
        for edge in unknown:
            if edge.target_slug == target or edge.target_slug in relevant_nodes:
                relevant_unknown.add(str(edge.source_relation_id))

    plan_hash = content_hash(
        {
            "snapshot": snapshot.snapshot_id,
            "policy": snapshot.policy_version,
            "context": context,
            "prior": prior,
            "plan": plan,
        }
    )

    certificates = []
    prior_set = set(prior)

    for target_index, target in enumerate(plan):
        predecessors = sorted(_predecessors(target, reverse_adjacency))
        earlier = set(plan[:target_index])
        for predecessor in predecessors:
            if predecessor in prior_set or predecessor in earlier:
                continue

            path = _shortest_path(predecessor, target, adjacency)
            relation_ids = [str(edge.source_relation_id) for edge in path]
            evidence = sorted(
                {item for edge in path for item in (edge.evidence or [])}
            )
            later = predecessor in plan[target_index + 1 :]
            base = {
                "snapshot": snapshot.snapshot_id,
                "policy": snapshot.policy_version,
                "target_index": target_index,
                "target_concept": target,
                "missing_or_late_concept": predecessor,
                "violation_kind": (
                    "intra_plan_order" if later else "missing_prior_support"
                ),
                "assertion_path": relation_ids,
            }
            certificates.append(
                {
                    "certificate_id": content_hash(base)[:20],
                    "snapshot": snapshot.snapshot_id,
                    "policy": snapshot.policy_version,
                    "context_id": context.get("context_id"),
                    "plan_hash": plan_hash,
                    **{key: value for key, value in base.items() if key not in {"snapshot", "policy"}},
                    "assertion_revision_path": relation_ids,
                    "source_evidence": evidence,
                    "witness_rule": "shortest_then_relation_id",
                }
            )

    if certificates:
        outcome = "INVALID"
        notes = []
    elif relevant_unknown:
        outcome = "INDETERMINATE"
        notes = ["Relevant prerequisite scope cannot be resolved from the supplied context."]
    else:
        outcome = "VALID"
        notes = []

    return {
        "outcome": outcome,
        "prior": prior,
        "resolved_plan": plan,
        "certificates": certificates,
        "unresolved_refs": [],
        "unknown_scope_assertions": sorted(relevant_unknown),
        "notes": notes,
    }

"""Read-only provisional concept documentation derived from existing legacy relations.

These unmanaged tables are not certified V2 knowledge. The only supported
inference rule is directional, exact-predicate subtype_of transitivity.
"""
from __future__ import annotations

from collections import deque
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from core.models import Concept, Relation

DEFAULT_DEPTH = 2
MAX_DEPTH = 3
MAX_NODES = 26
MAX_EDGES = 48
STATUS = "provisional_legacy_graph"
RULE = "subtype_of_transitivity"


def _name(slug: str) -> str:
    return slug.replace("_", " ").replace("-", " ").strip().capitalize()


def _article(noun: str) -> str:
    return "an" if noun[:1].lower() in "aeiou" else "a"


def _sentence(subject: str, predicate: str, target: str) -> str:
    """Generic predicate grammar, never pre-authored concept-specific facts."""
    left, right = _name(subject), _name(target).lower()
    if predicate == "subtype_of":
        return f"{left} is {_article(right)} {right}."
    if predicate == "part_of":
        return f"{left} is part of {right}."
    if predicate == "uses":
        return f"{left} uses {right}."
    if predicate == "prerequisite_of":
        return f"{left} is a recorded prerequisite of {right}."
    return f"{left} —{predicate}→ {_name(target)}."


def _relation_values(slug: str) -> list[dict]:
    return list(
        Relation.objects.filter(Q(source_id=slug) | Q(target_id=slug))
        .order_by("source_id", "type_id", "target_id", "id")
        .values("id", "source_id", "type_id", "target_id")[:MAX_EDGES + 1]
    )


def _read_neighborhood(slug: str, depth: int) -> tuple[dict[str, int], list[dict], bool]:
    """Bounded BFS in both directions; every statement retains the original UUID."""
    distances = {slug: 0}
    queue = deque([slug])
    seen_relations = set()
    edges = []
    truncated = False

    while queue:
        current = queue.popleft()
        current_depth = distances[current]
        if current_depth >= depth:
            continue

        rows = _relation_values(current)
        if len(rows) > MAX_EDGES:
            truncated = True

        for row in rows:
            relation_id = str(row["id"])
            if relation_id in seen_relations:
                continue
            seen_relations.add(relation_id)

            if len(edges) >= MAX_EDGES:
                truncated = True
                break

            source, target = row["source_id"], row["target_id"]
            neighbor = target if source == current else source
            if neighbor not in distances:
                if len(distances) >= MAX_NODES:
                    truncated = True
                    continue
                distances[neighbor] = current_depth + 1
                queue.append(neighbor)

            if source not in distances or target not in distances:
                truncated = True
                continue

            edges.append({
                "id": relation_id,
                "source": source,
                "predicate": row["type_id"],
                "target": target,
                "text": _sentence(source, row["type_id"], target),
                "status": STATUS,
                "hop": max(distances[source], distances[target]),
            })

    edges.sort(key=lambda edge: (
        edge["hop"], edge["source"], edge["predicate"], edge["target"], edge["id"]
    ))
    return distances, edges, truncated


def _derive_subtypes(slug: str, edges: list[dict], depth: int) -> list[dict]:
    """Same-graph subtype transitivity with exact supporting asserted-edge IDs."""
    by_source: dict[str, list[dict]] = {}
    direct = set()
    for edge in edges:
        if edge["predicate"] != "subtype_of":
            continue
        by_source.setdefault(edge["source"], []).append(edge)
        if edge["source"] == slug:
            direct.add(edge["target"])
    for outgoing in by_source.values():
        outgoing.sort(key=lambda edge: (edge["target"], edge["id"]))

    queue = deque([(slug, (slug,), ())])
    visited = {slug}
    conclusions = []
    while queue:
        current, node_path, premises = queue.popleft()
        if len(premises) >= depth:
            continue
        for edge in by_source.get(current, []):
            target = edge["target"]
            if target in node_path or target in visited:
                continue
            next_ids = (*premises, edge["id"])
            visited.add(target)
            queue.append((target, (*node_path, target), next_ids))
            if len(next_ids) > 1 and target not in direct:
                conclusions.append({
                    "subject": slug,
                    "predicate": "subtype_of",
                    "target": target,
                    "text": _sentence(slug, "subtype_of", target),
                    "rule": RULE,
                    "premise_ids": list(next_ids),
                    "status": "conditional_provisional_inference",
                })
    return conclusions


def build_documentation(slug: str, depth: int) -> dict:
    distances, edges, truncated = _read_neighborhood(slug, depth)
    # Classification is not claimed to be a complete, reviewed definition.
    direct_types = sorted(
        (edge for edge in edges if edge["source"] == slug and
         edge["predicate"] == "subtype_of"),
        key=lambda edge: (edge["target"], edge["id"]),
    )
    characterization = {
        "text": " ".join(edge["text"] for edge in direct_types),
        "assertion_ids": [edge["id"] for edge in direct_types],
        "status": STATUS,
        "method": "direct_subtype_statements_only",
    } if direct_types else None

    return {
        "contract_version": "legacy-concept-documentation@1",
        "concept": {"slug": slug, "label": _name(slug)},
        "source": {
            "kind": "legacy_concept_relation_tables",
            "status": STATUS,
            "is_published_v2": False,
            "is_peer_reviewed": False,
            "description": (
                "The existing legacy concept/relation graph is not the reviewed "
                "V2 federation. All recorded assertions and inferences are provisional."
            ),
        },
        "traversal": {
            "depth": depth, "max_depth": MAX_DEPTH,
            "max_nodes": MAX_NODES, "max_edges": MAX_EDGES,
            "truncated": truncated,
        },
        "graph": {
            "nodes": [{"slug": node, "label": _name(node), "hop": hop}
                      for node, hop in sorted(distances.items(),
                                              key=lambda entry: (entry[1], entry[0]))],
            "edges": edges,
        },
        "characterization": characterization,
        "asserted_statements": edges,
        "derived_statements": _derive_subtypes(slug, edges, depth),
        "derivation_policy": {
            "implemented_rules": [RULE],
            "rule_description": "If A subtype_of B and B subtype_of C, infer A subtype_of C.",
            "conditional_on_premises": True,
            "is_formal_proof_certificate": False,
            "uses_implies_prerequisite": False,
            "uses_implies_indexed_access": False,
        },
    }


@require_GET
def concept_documentation(request, slug):
    concept = get_object_or_404(Concept, slug=slug)
    raw_depth = request.GET.get("depth", str(DEFAULT_DEPTH))
    try:
        depth = int(raw_depth)
    except (TypeError, ValueError):
        return JsonResponse({"error": "depth must be an integer from 1 to 3"}, status=400)
    if depth < 1 or depth > MAX_DEPTH:
        return JsonResponse({"error": "depth must be between 1 and 3"}, status=400)

    response = JsonResponse(build_documentation(concept.slug, depth))
    response["Cache-Control"] = "no-store"
    return response

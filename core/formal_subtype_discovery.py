"""Discover an explicit, nonpublishing subtype-proof certificate from canonical JSONL.

No claim-specific hardcoded fixtures. Given a start and target UUID (or the CLI
slugs), find an ordered path of recorded subtype_of relations and construct a
proof certificate whose steps can be independently checked by the scoped rule
verifier. All source scopes are **assumed**, not reconstructed from the files.

Usage:
 python -m core.formal_subtype_discovery \
   --concepts ../data/knowledge/concepts.jsonl \
   --statements ../data/knowledge/statements.jsonl \
   --subject array --target data
"""
from __future__ import annotations

from collections import deque
from hashlib import sha256
import json
from pathlib import Path

from core.formal_recorded_statement_bridge import _read_jsonl, _uuid
from core.formal_scoped_subtype_proofs import (
    SCOPE, ScopedSubtypeProofError, verify_scoped_subtype_proof,
)

MAX_HOPS = 6


def discover_scoped_subtype_certificate(
    *,
    concepts_jsonl: bytes,
    statements_jsonl: bytes,
    subject_concept_id: str,
    object_concept_id: str,
    assumed_scope: str = "hypothetical_shared_taxonomy",
    max_hops: int = MAX_HOPS,
) -> dict:
    """Build a minimal deterministic >=2-edge proof certificate, or fail."""
    start = _uuid(subject_concept_id, "subject concept")
    target = _uuid(object_concept_id, "target concept")
    if not isinstance(assumed_scope, str) or not SCOPE.fullmatch(assumed_scope):
        raise ScopedSubtypeProofError("A hypothetical semantic scope is required")
    if type(max_hops) is not int or not 2 <= max_hops <= MAX_HOPS:
        raise ScopedSubtypeProofError("Discovery supports 2–6 hops")
    if start == target:
        raise ScopedSubtypeProofError("Reflexive/cyclic subtype proofs are not discovered by v0")

    concepts = _read_jsonl(concepts_jsonl, "concepts")
    statements = _read_jsonl(statements_jsonl, "statements")
    concept_by_id = {row["id"]: row for row in concepts}
    if len(concept_by_id) != len(concepts) or start not in concept_by_id or target not in concept_by_id:
        raise ScopedSubtypeProofError("Unknown or duplicated concept identity")
    rows_by_id = {row["id"]: row for row in statements}
    if len(rows_by_id) != len(statements):
        raise ScopedSubtypeProofError("Duplicate statement UUID")

    edges: dict[str, list[tuple[str, str]]] = {}
    for row in statements:
        if row.get("predicate") != "subtype_of":
            continue
        subject, obj = row.get("subject", {}), row.get("object", {})
        if subject.get("kind") != "concept" or obj.get("kind") != "concept":
            continue
        a, b = subject["id"], obj["id"]
        if a not in concept_by_id or b not in concept_by_id:
            raise ScopedSubtypeProofError("Malformed subtype reference to unknown concept")
        # A direct assertion of the requested goal is already recorded. Only
        # search for a distinct two-or-more-edge witness.
        if a == start and b == target:
            continue
        edges.setdefault(a, []).append((b, row["id"]))
    for outgoing in edges.values():
        outgoing.sort(key=lambda item: (item[0], item[1]))

    queue = deque([(start, (start,), ())])
    visited = {start}
    chosen: tuple[str, ...] | None = None
    while queue:
        current, vertices, statement_ids = queue.popleft()
        if len(statement_ids) >= max_hops:
            continue
        for neighbor, statement_id in edges.get(current, []):
            if neighbor in visited or neighbor in vertices:
                continue
            visited.add(neighbor)
            path = statement_ids + (statement_id,)
            if neighbor == target and len(path) >= 2:
                chosen = path
                break
            if len(path) < max_hops:
                queue.append((neighbor, vertices + (neighbor,), path))
        if chosen is not None:
            break

    if chosen is None:
        raise ScopedSubtypeProofError("No two-or-more-edge subtype proof path in recorded graph")

    steps: list[dict] = []
    for i, sid in enumerate(chosen, 1):
        steps.append({
            "id": f"h{i}",
            "rule": "recorded_subtype",
            "statement_id": sid,
            "assumed_scope": assumed_scope,
        })
    for i in range(1, len(chosen)):
        steps.append({
            "id": f"s{i}",
            "rule": "subtype_transitivity",
            "left": "h1" if i == 1 else f"s{i-1}",
            "right": f"h{i+1}",
        })

    candidate = {
        "schema_version": "formal-scoped-subtype-proof.v0",
        "scope": assumed_scope,
        "provenance": {
            "status": "synthetic_fixture",
            "source_scientific_review": "not_established",
            "scope_origin": "assumed_not_in_source",
        },
        "snapshot": {
            "concepts_sha256": "sha256:" + sha256(concepts_jsonl).hexdigest(),
            "statements_sha256": "sha256:" + sha256(statements_jsonl).hexdigest(),
        },
        "goal": {
            "subject_concept_id": start,
            "predicate": "subtype_of",
            "object_concept_id": target,
        },
        "steps": steps,
        "conclusion_step_id": f"s{len(chosen)-1}",
    }
    # Run the independent proof checker: discovery does not itself certify
    # a path, and the resulting certificate is never published.
    verify_scoped_subtype_proof(
        candidate, concepts_jsonl=concepts_jsonl, statements_jsonl=statements_jsonl
    )
    return candidate


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concepts", required=True, type=Path)
    parser.add_argument("--statements", required=True, type=Path)
    parser.add_argument("--subject", required=True, help="Existing canonical concept slug")
    parser.add_argument("--target", required=True, help="Existing canonical concept slug")
    parser.add_argument("--scope", default="hypothetical_shared_taxonomy")
    parser.add_argument("--max-hops", type=int, default=MAX_HOPS)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    concept_bytes, statement_bytes = args.concepts.read_bytes(), args.statements.read_bytes()
    entries = _read_jsonl(concept_bytes, "concepts")
    ids_by_slug = {entry["slug"]: entry["id"] for entry in entries}
    if len(ids_by_slug) != len(entries) or args.subject not in ids_by_slug or args.target not in ids_by_slug:
        parser.error("Unknown or ambiguous canonical concept slug")
    certificate = discover_scoped_subtype_certificate(
        concepts_jsonl=concept_bytes,
        statements_jsonl=statement_bytes,
        subject_concept_id=ids_by_slug[args.subject],
        object_concept_id=ids_by_slug[args.target],
        assumed_scope=args.scope,
        max_hops=args.max_hops,
    )
    result = verify_scoped_subtype_proof(
        certificate, concepts_jsonl=concept_bytes, statements_jsonl=statement_bytes
    )
    if args.format == "json":
        print(json.dumps({"certificate": certificate, "checked_proof": result},
                         ensure_ascii=False, indent=2))
    else:
        print("Generated conditional subtype proof · no human-authored concept file")
        for step in result["steps"]:
            print(
                f"{step['id']:>3}: {step['subject_label']} ⊑ {step['object_label']}"
                f"  [{step['rule']}, premises={','.join(step['original_statement_ids'])}]"
            )
        conclusion = result["conclusion"]
        print("∴", conclusion["subject_label"], "⊑", conclusion["object_label"])
        print("Assumed scope:", result["scope"])
        print("Source semantics independently verified:", result["semantic_scope_source_verified"])
        print("May publish:", result["may_publish"])


if __name__ == "__main__":
    main()

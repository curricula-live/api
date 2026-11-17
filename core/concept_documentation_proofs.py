"""Evidence-linked proof steps for the read-only teacher concept projection.

Only checks the exact recorded subtype chain retrieved from the legacy
database. The shared subtype interpretation is an external *assumption*,
not source-reviewed. This proof witness is not the experimental certified
proof contract from the formal-model branch and cannot publish statements.
"""
from __future__ import annotations


class ProvisionalProofError(ValueError):
    pass


def checked_subtype_trace(
    subject: str,
    target: str,
    premise_ids: list[str],
    recorded_edges: list[dict],
) -> dict:
    """Produce a deterministic typed derivation trace, or reject malformed paths."""
    indexed = {edge["id"]: edge for edge in recorded_edges}
    if len(indexed) != len(recorded_edges):
        raise ProvisionalProofError("Duplicate assertion IDs in graph projection")
    if len(premise_ids) < 2 or len(set(premise_ids)) != len(premise_ids):
        raise ProvisionalProofError("Subtype transitivity requires distinct ordered premises")

    current = subject
    visited = {subject}
    steps = []
    for index, statement_id in enumerate(premise_ids, 1):
        edge = indexed.get(statement_id)
        if edge is None:
            raise ProvisionalProofError(f"Unknown original assertion {statement_id}")
        if edge["predicate"] != "subtype_of" or edge["source"] != current:
            raise ProvisionalProofError("Premise must continue an oriented subtype_of chain")
        if edge["target"] in visited:
            raise ProvisionalProofError("Cyclic recorded path is not a supported witness")
        visited.add(edge["target"])
        steps.append({
            "id": f"h{index}",
            "kind": "recorded_premise",
            "rule": "recorded_subtype",
            "subject": edge["source"],
            "predicate": edge["predicate"],
            "target": edge["target"],
            "assertion_id": statement_id,
            "depends_on": [],
        })
        current = edge["target"]

    if current != target or subject == target:
        raise ProvisionalProofError("Derived target differs from claimed conclusion")

    for index in range(1, len(premise_ids)):
        next_edge = indexed[premise_ids[index]]
        steps.append({
            "id": f"s{index}",
            "kind": "derived_step",
            "rule": "subtype_of_transitivity",
            "subject": subject,
            "predicate": "subtype_of",
            "target": next_edge["target"],
            "assertion_id": None,
            "depends_on": ["h1" if index == 1 else f"s{index - 1}", f"h{index + 1}"],
        })

    return {
        "format": "provisional-subtype-trace@1",
        "scope": "provisional_legacy_graph",
        "scope_origin": "assumed_not_in_source",
        "rule_application_checked": True,
        "source_semantics_verified": False,
        "is_formal_proof_certificate": False,
        "may_publish": False,
        "conclusion_step_id": f"s{len(premise_ids) - 1}",
        "steps": steps,
    }

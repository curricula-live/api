"""Generic, bounded concept relation-profile projection for teacher diagnostics.

Counts apply only to the currently retrieved graph neighborhood; they are
NOT claims about full ontology/source coverage. No additional database reads,
scientific reinterpretation, or new inference rules.
"""
from __future__ import annotations

def build_relation_profile(
    slug: str,
    edges: list[dict],
    derived_statements: list[dict],
    *,
    truncated: bool,
) -> dict:
    incident = [edge for edge in edges if edge["source"] == slug or edge["target"] == slug]
    incoming = [edge for edge in incident if edge["target"] == slug]
    outgoing = [edge for edge in incident if edge["source"] == slug]
    by_predicate: dict[str, dict[str, int]] = {}
    names = sorted({edge["predicate"] for edge in incident})
    for predicate in names:
        by_predicate[predicate] = {
            "outgoing": sum(edge["predicate"] == predicate for edge in outgoing),
            "incoming": sum(edge["predicate"] == predicate for edge in incoming),
        }
    return {
        "scope": "retrieved_neighborhood_only",
        "source_status": "provisional_legacy_graph",
        "retrieval_truncated": bool(truncated),
        "direct_recorded_relations": len(incident),
        "outgoing_recorded_relations": len(outgoing),
        "incoming_recorded_relations": len(incoming),
        "by_predicate": by_predicate,
        "conditional_subtype_inferences": len(derived_statements),
        "scientific_completeness_established": False,
    }

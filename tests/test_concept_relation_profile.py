"""Graph read-profile counts are based exclusively on retrieved, provisional assertions."""
from __future__ import annotations

from core.concept_relation_profile import build_relation_profile


def e(identifier, source, predicate, target):
    return {"id": identifier, "source": source, "predicate": predicate, "target": target}


def test_mixed_directed_predicates_and_remote_edges():
    edges = [
        e("1", "algorithm", "implemented_by", "program"),
        e("2", "step", "part_of", "algorithm"),
        e("3", "complexity", "measures", "algorithm"),
        e("4", "program", "subtype_of", "software"),
    ]
    result = build_relation_profile("algorithm", edges, [], truncated=False)
    assert result == {
        "scope": "retrieved_neighborhood_only",
        "source_status": "provisional_legacy_graph",
        "retrieval_truncated": False,
        "direct_recorded_relations": 3,
        "outgoing_recorded_relations": 1,
        "incoming_recorded_relations": 2,
        "by_predicate": {
            "implemented_by": {"outgoing": 1, "incoming": 0},
            "measures": {"outgoing": 0, "incoming": 1},
            "part_of": {"outgoing": 0, "incoming": 1},
        },
        "conditional_subtype_inferences": 0,
        "scientific_completeness_established": False,
    }
    assert edges[-1]["predicate"] == "subtype_of"


def test_profile_is_relative_to_retrieved_neighborhood_not_global_ontology():
    edges = [e("1", "network", "subtype_of", "system")]
    proof = {"status": "conditional_provisional_inference"}
    result = build_relation_profile("network", edges, [proof], truncated=True)
    assert result["retrieval_truncated"] is True
    assert result["direct_recorded_relations"] == 1
    assert result["conditional_subtype_inferences"] == 1
    assert result["scientific_completeness_established"] is False


def test_isolated_concept_is_empty_not_assumed_defined():
    result = build_relation_profile("isolated", [], [], truncated=False)
    assert result["direct_recorded_relations"] == 0
    assert result["by_predicate"] == {}
    assert result["conditional_subtype_inferences"] == 0


def test_same_predicate_in_two_directions_is_counted_separately():
    result = build_relation_profile("network", [
        e("1", "network", "subtype_of", "system"),
        e("2", "internet", "subtype_of", "network"),
    ], [], truncated=False)
    assert result["by_predicate"]["subtype_of"] == {"incoming": 1, "outgoing": 1}
    assert result["direct_recorded_relations"] == 2


def test_source_data_are_not_modified_during_projection():
    original = [e("1", "a", "uses", "b")]
    preserved = [dict(x) for x in original]
    build_relation_profile("a", original, [], truncated=False)
    assert original == preserved
